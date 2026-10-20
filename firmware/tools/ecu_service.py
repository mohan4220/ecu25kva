#!/usr/bin/env python3
"""The laptop service tool: read and write the end-of-line record, and
flash the application, over USB (prototype), CAN channel 2, or the PC
simulator. One UDS subset on every link (docs/firmware.md, "The service
link").

    ecu_service.py --link usb:/dev/tty.usbmodem1 --secret key.bin info
    ecu_service.py --link can:socketcan:can0 --secret key.bin eol-read
    ecu_service.py --link sim --secret key.bin flash app.bin --sw-ver 0x00010002 \\
                   --hw-min 0x0100 --hw-max 0x01FF

The secret is the 16 bytes built into the firmware as SEC_SECRET; keep the
file off shared drives. pyserial and python-can/can-isotp are needed only
by their links.
"""
import argparse
import json
import pathlib
import struct
import sys
import time
import zlib

CAN_REQ, CAN_RESP = 0x7E0, 0x7E8
BLOCK = 1024

REASONS = {
    0x11: "service not supported", 0x12: "sub-function not supported",
    0x13: "wrong length", 0x22: "conditions not correct", 0x24: "wrong sequence",
    0x31: "out of range", 0x33: "security access denied", 0x35: "wrong key",
    0x36: "too many wrong keys: locked for 10 s", 0x72: "programming failure",
    0x7F: "not in this session",
}


class UdsError(Exception):
    def __init__(self, sid, code, text=None):
        self.sid, self.code = sid, code
        super().__init__(text or f"service 0x{sid:02X} refused: {REASONS.get(code, hex(code))}")


# ---- links -----------------------------------------------------------------

def crc16(data):
    c = 0xFFFF
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = (c << 1 ^ 0x1021 if c & 0x8000 else c << 1) & 0xFFFF
    return c


def frame(msg):
    return bytes([0x55]) + struct.pack("<H", len(msg)) + msg + struct.pack("<H", crc16(msg))


class UsbLink:
    """The STM32's USB virtual serial port: 0x55, length LE, payload, CRC-16 LE."""

    def __init__(self, port, timeout=2.0):
        import serial                    # pyserial, only for this link
        self.port = serial.Serial(port, 115200, timeout=0.05)
        self.timeout = timeout

    def request(self, req):
        self.port.reset_input_buffer()
        self.port.write(frame(bytes(req)))
        buf, end = b"", time.monotonic() + self.timeout
        while time.monotonic() < end:
            buf += self.port.read(4096)
            while buf:
                i = buf.find(b"\x55")
                if i < 0:
                    buf = b""
                    break
                buf = buf[i:]
                if len(buf) < 3:
                    break
                n = struct.unpack_from("<H", buf, 1)[0]
                if n == 0 or n > 4095:
                    buf = buf[1:]
                    continue
                if len(buf) < n + 5:
                    break
                msg = buf[3:3 + n]
                if struct.unpack_from("<H", buf, 3 + n)[0] == crc16(msg):
                    return msg
                buf = buf[1:]
        raise TimeoutError("no response on USB")

    def reconnect(self):
        time.sleep(1.0)                  # the unit resets; the port re-enumerates


class CanLink:
    """CAN channel 2 through python-can and can-isotp, 11-bit 0x7E0/0x7E8."""

    def __init__(self, interface, channel, timeout=2.0):
        import can                       # python-can and can-isotp, only for this link
        import isotp
        self.bus = can.Bus(interface=interface, channel=channel, bitrate=500000)
        addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=CAN_REQ, rxid=CAN_RESP)
        self.stack = isotp.CanStack(self.bus, address=addr, params={"tx_padding": 0xAA})
        self.timeout = timeout

    def request(self, req):
        self.stack.send(bytes(req))
        end = time.monotonic() + self.timeout
        while time.monotonic() < end:
            self.stack.process()
            if self.stack.available():
                return bytes(self.stack.recv())
            time.sleep(0.001)
        raise TimeoutError("no response on CAN channel 2")

    def reconnect(self):
        time.sleep(0.5)


def open_link(spec):
    kind, _, rest = spec.partition(":")
    if kind == "usb":
        return UsbLink(rest)
    if kind == "can":
        interface, _, channel = rest.partition(":")
        return CanLink(interface, channel)
    if kind == "sim":
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "sim"))
        from ecu import Unit             # the C core and bootloader through ctypes
        return Unit()
    raise SystemExit(f"unknown link {spec!r}: usb:PORT, can:INTERFACE:CHANNEL or sim")


# ---- the UDS client ----------------------------------------------------------

class Client:
    def __init__(self, link, secret):
        self.link, self.secret = link, secret

    def uds(self, *req):
        req = bytes(req[0]) if len(req) == 1 and not isinstance(req[0], int) else bytes(req)
        rsp = self.link.request(req)
        if not rsp:
            raise TimeoutError("empty response")
        if rsp[0] == 0x7F:
            raise UdsError(rsp[1], rsp[2])
        if rsp[0] != req[0] + 0x40:
            raise UdsError(req[0], 0, f"unexpected response {rsp.hex()}")
        return rsp

    def session(self, sub):
        try:
            return self.uds(0x10, sub)
        except UdsError as e:
            if e.code == 0x22:
                raise UdsError(0x10, 0x22, "the engine must be stopped (engine must be stopped)")
            raise

    def unlock(self):
        seed = struct.unpack("<I", self.uds(0x27, 0x01)[2:6])[0]
        key = zlib.crc32(struct.pack("<I", seed) + self.secret)
        self.uds(bytes([0x27, 0x02]) + struct.pack("<I", key))

    def read(self, did):
        return self.uds(bytes([0x22]) + struct.pack(">H", did))[3:]

    def write(self, did, data):
        try:
            self.uds(bytes([0x2E]) + struct.pack(">H", did) + data)
        except UdsError as e:
            if e.code == 0x22:
                raise UdsError(0x2E, 0x22, "refused: the record is locked, or the engine must be stopped")
            raise

    def routine(self, rid, data=b""):
        return self.uds(bytes([0x31, 0x01]) + struct.pack(">H", rid) + data)


def service_session(c):
    c.session(0x03)
    c.unlock()


def show_record(c, full):
    serial = c.read(0xF18C).rstrip(b"\0").decode(errors="replace")
    print(f"serial       {serial}")
    print(f"hardware rev 0x{struct.unpack('>H', c.read(0xF191))[0]:04X}")
    print(f"build date   {struct.unpack('>I', c.read(0xF18B))[0]}")
    print(f"software     0x{struct.unpack('>H', c.read(0xF195))[0]:04X}")
    print(f"bootloader   0x{struct.unpack('>H', c.read(0xF180))[0]:04X}")
    if full:
        t = struct.unpack("<12f", c.read(0x0100))
        names = ("clt", "oil", "rail", "boost", "egr", "5v")
        for i, n in enumerate(names):
            print(f"trim {n:5s}   gain {t[i]:.4f}  offset {t[6 + i]:+.4f} V")
        st, passed, locked = c.read(0x0101)
        print(f"station {st}  passed {'yes' if passed else 'no'}  locked {'yes' if locked else 'no'}")


def eol_write(c, a):
    service_session(c)
    if c.read(0x0101)[2]:
        raise UdsError(0x2E, 0x22, "the end-of-line record is locked: eol-unlock first")
    if a.serial is not None:
        s = a.serial.encode("ascii")
        if not 1 <= len(s) <= 16:
            raise SystemExit("serial: 1 to 16 ASCII characters")
        c.write(0xF18C, s)
    if a.hw_rev is not None:
        c.write(0xF191, struct.pack(">H", a.hw_rev))
    if a.date is not None:
        c.write(0xF18B, struct.pack(">I", a.date))
    if a.trims:
        t = json.loads(pathlib.Path(a.trims).read_text())
        if len(t["gain"]) != 6 or len(t["offset"]) != 6:
            raise SystemExit("trims: 6 gains and 6 offsets (clt, oil, rail, boost, egr, 5v)")
        c.write(0x0100, struct.pack("<12f", *t["gain"], *t["offset"]))
    if a.station is not None or a.passed:
        st, passed, _ = c.read(0x0101)
        c.write(0x0101, bytes([a.station if a.station is not None else st, 1 if a.passed else passed]))
    print("end-of-line record written")


def flash(c, a):
    img = pathlib.Path(a.image).read_bytes()
    if not img:
        raise SystemExit("empty image")
    # the application leaves for the bootloader on 10 02; the bootloader takes it as is
    service_session(c)
    c.session(0x02)
    if hasattr(c.link, "reconnect"):
        c.link.reconnect()
    c.session(0x02)
    c.unlock()
    base, size = struct.unpack(">II", c.read(0xFD00))
    if len(img) > size - 64:
        raise SystemExit(f"image {len(img)} bytes; the application area holds {size - 64}")
    c.routine(0xFF00, struct.pack(">II", base, size))
    c.uds(bytes([0x34, 0x00, 0x44]) + struct.pack(">II", base + 64, len(img)))
    blocks = range(0, len(img), BLOCK)
    for i, at in enumerate(blocks):
        c.uds(bytes([0x36, (i + 1) & 0xFF]) + img[at:at + BLOCK])
        if i % 16 == 15 or i == len(blocks) - 1:
            print(f"  {min(at + BLOCK, len(img))} / {len(img)} bytes", flush=True)
    c.uds(0x37)
    c.routine(0xFF01, struct.pack(">IIHH", zlib.crc32(img), a.sw_ver, a.hw_min, a.hw_max))
    c.uds(0x11, 0x01)
    print("flashed and checked; the unit resets and runs it if its hardware revision fits")


def main(argv=None, link=None):
    num = lambda s: int(s, 0)  # noqa: E731
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--link", required=True, help="usb:PORT, can:INTERFACE:CHANNEL or sim")
    p.add_argument("--secret", required=True, help="file holding the 16-byte SEC_SECRET")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info")
    sub.add_parser("eol-read")
    w = sub.add_parser("eol-write")
    w.add_argument("--serial")
    w.add_argument("--hw-rev", type=num)
    w.add_argument("--date", type=int, help="yyyymmdd")
    w.add_argument("--trims", help="JSON {gain: [6], offset: [6]}")
    w.add_argument("--station", type=int)
    w.add_argument("--passed", action="store_true")
    sub.add_parser("eol-lock")
    sub.add_parser("eol-unlock")
    f = sub.add_parser("flash")
    f.add_argument("image")
    f.add_argument("--sw-ver", type=num, required=True)
    f.add_argument("--hw-min", type=num, required=True)
    f.add_argument("--hw-max", type=num, required=True)
    a = p.parse_args(argv)
    secret = pathlib.Path(a.secret).read_bytes()
    if len(secret) != 16:
        print("error: the secret file must hold exactly 16 bytes")
        return 2
    c = Client(link if link is not None else open_link(a.link), secret)
    try:
        if a.cmd in ("info", "eol-read"):
            show_record(c, a.cmd == "eol-read")
        elif a.cmd == "eol-write":
            eol_write(c, a)
        elif a.cmd in ("eol-lock", "eol-unlock"):
            service_session(c)
            c.routine(0xF000 if a.cmd == "eol-lock" else 0xF001)
            print(f"end-of-line record {'locked' if a.cmd == 'eol-lock' else 'unlocked'}")
        else:
            flash(c, a)
    except (UdsError, TimeoutError) as e:
        print(f"error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
