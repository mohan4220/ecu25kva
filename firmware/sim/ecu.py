"""ctypes wrapper around the firmware core (build/libecu.*)."""
import ctypes as C
import pathlib
import struct
import sys
import zlib

HERE = pathlib.Path(__file__).resolve().parent
NCYL, CANQ = 3, 16
USB_IN, USB_OUT = 64, 512
EOL_FMT = "<HH16sHxxI6f6fBBBB"          # eol.h's eol_record, before its crc


def eol_record(serial=b"", hw_rev=0x0100, date=20261020, gain=(1.0,) * 6, offset=(0.0,) * 6,
               station=0, passed=0, locked=0):
    """A sealed end-of-line record, as the factory leaves it (84 bytes)."""
    body = struct.pack(EOL_FMT, 0xE01D, 1, serial, hw_rev, date, *gain, *offset,
                       station, passed, locked, 0)
    return body + struct.pack("<I", zlib.crc32(body))


class Can(C.Structure):
    _fields_ = [("id", C.c_uint32), ("len", C.c_uint8), ("data", C.c_uint8 * 8)]


class Inj(C.Structure):
    _fields_ = [("start_us", C.c_uint32), ("dur_us", C.c_uint32), ("seq", C.c_uint32)]


class IO(C.Structure):
    _fields_ = [
        *[(n, C.c_float) for n in ("v_clt", "v_oil", "v_rail", "v_boost", "v_egr", "v_5v")],
        ("ignition", C.c_uint8), ("droop_sw", C.c_uint8),
        ("v_bat", C.c_float), ("reset_cause", C.c_uint8),
        ("inj", Inj * NCYL),
        ("meter_duty", C.c_float),
        ("wdg", C.c_uint8),
        ("can", Can * CANQ),
        ("can_n", C.c_uint8),
        ("can_drops", C.c_uint16),
        ("nvm_save", C.c_uint8), ("nvm_slot", C.c_uint8),
        ("state", C.c_uint8), ("fault_n", C.c_uint8), ("synced", C.c_uint8),
        *[(n, C.c_float) for n in ("rpm", "fuel_mg", "rail_bar", "clt_c", "oil_kpa")],
        ("boot_ver", C.c_uint16),
        ("usb_in", C.c_uint8 * USB_IN), ("usb_in_n", C.c_uint8),
        ("usb_out", C.c_uint8 * USB_OUT), ("usb_out_n", C.c_uint16),
        ("can2", Can * CANQ), ("can2_n", C.c_uint8),
        ("eol_save", C.c_uint8), ("boot_req", C.c_uint8), ("reset_req", C.c_uint8),
        ("session", C.c_uint8),
    ]


OFF, WAIT, CRANK, RUN, SHUTDOWN = range(5)


class Ecu:
    def __init__(self):
        ext = "dylib" if sys.platform == "darwin" else "so"
        self.lib = C.CDLL(str(HERE / "build" / f"libecu.{ext}"))
        self.lib.ecu_io_size.restype = C.c_size_t
        self.lib.ecu_nvm_image.restype = C.c_void_p
        self.lib.ecu_eol_image.restype = C.c_void_p
        self.lib.rail_set_bar.restype = C.c_float
        self.lib.rail_set_bar.argtypes = [C.c_float]
        if C.sizeof(IO) != self.lib.ecu_io_size():
            raise RuntimeError("ecu.py IO layout does not match ecu.h")
        self.io = IO()
        self._p = C.byref(self.io)

    def init(self):
        self.lib.ecu_init(self._p)

    def crank_edge(self, t_us):
        self.lib.ecu_crank_edge(self._p, C.c_uint32(t_us & 0xFFFFFFFF))

    def cam_edge(self, t_us):
        self.lib.ecu_cam_edge(self._p, C.c_uint32(t_us & 0xFFFFFFFF))

    def tick(self, t_us):
        self.lib.ecu_tick_1ms(self._p, C.c_uint32(t_us & 0xFFFFFFFF))

    def nvm_image(self):
        n = C.c_uint32()
        p = self.lib.ecu_nvm_image(C.byref(n))
        return C.string_at(p, n.value)

    def nvm_load(self, a, b):
        n = len(self.nvm_image())
        a, b = (bytes(x[:n]).ljust(n, b"\0") for x in (a, b))
        self.lib.ecu_nvm_load(self._p, a, b, C.c_uint32(n))

    def can_rx(self, can_id, data):
        f = Can(can_id, len(data), (C.c_uint8 * 8)(*data))
        self.lib.ecu_can_rx(self._p, C.byref(f))

    def can2_rx(self, can_id, data):
        f = Can(can_id, len(data), (C.c_uint8 * 8)(*data))
        self.lib.ecu_can2_rx(self._p, C.byref(f))

    def eol_load(self, a, b):
        a, b = (bytes(x[:84]).ljust(84, b"\0") for x in (a, b))
        self.lib.ecu_eol_load(self._p, a, b)

    def eol_image(self):
        n = C.c_uint32()
        p = self.lib.ecu_eol_image(C.byref(n))
        return C.string_at(p, n.value)

    def rail_set_bar(self, fuel_mg):
        """The firmware's rail-pressure setpoint for this fuel."""
        return self.lib.rail_set_bar(fuel_mg)

    def background(self):
        self.lib.ecu_background(self._p)

    def drain_can(self):
        out = [(f.id, bytes(f.data[:f.len])) for f in self.io.can[:self.io.can_n]]
        self.io.can_n = 0
        return out


BOOT_SIZE = 0x8000                       # boot.h
ERASE_CB = C.CFUNCTYPE(C.c_int, C.c_uint32, C.c_uint32)
WRITE_CB = C.CFUNCTYPE(C.c_int, C.c_uint32, C.POINTER(C.c_uint8), C.c_uint32)


class BootFlash(C.Structure):
    _fields_ = [("erase", ERASE_CB), ("write", WRITE_CB), ("read", WRITE_CB),
                ("app_base", C.c_uint32), ("app_size", C.c_uint32)]


class Unit:
    """A simulated board for the service tool: the C application and the C
    bootloader, the application flash as a byte array, the two end-of-line
    copies, and the stay flag (a RAM word a reset keeps, a power cut does
    not). request() takes one UDS request and returns its response."""

    def __init__(self, app_size=0x40000):
        ext = "dylib" if sys.platform == "darwin" else "so"
        self.boot = C.CDLL(str(HERE / "build" / f"libboot.{ext}"))
        self.boot.boot_state_size.restype = C.c_size_t
        self.boot.boot_handle.restype = C.c_uint16
        self.state = C.create_string_buffer(self.boot.boot_state_size())
        self.flash = bytearray(b"\xff" * (BOOT_SIZE + app_size))
        self._cbs = (ERASE_CB(self._erase), WRITE_CB(self._write), WRITE_CB(self._read))
        self.bf = BootFlash(*self._cbs, BOOT_SIZE, app_size)
        self.eol = [b"", b""]
        self.turning = False
        self.ms = 0
        self.writes = 0
        self.install(bytes(1024))                # a board comes off the line programmed
        self.power_on()

    def install(self, img, sw_ver=1, hw_min=0, hw_max=0xFFFF):
        """Program an image the way a debug probe would: data, then its header."""
        base = BOOT_SIZE
        self.flash[base:] = b"\xff" * (len(self.flash) - base)
        self.flash[base + 64:base + 64 + len(img)] = img
        self.flash[base:base + 24] = struct.pack("<IIIIIHH", 0x1A6EC25, 1, len(img),
                                                 zlib.crc32(img), sw_ver, hw_min, hw_max)

    # -- the flash, as the bootloader's host calls ----------------------
    def _erase(self, a, n):
        if a + n > len(self.flash):
            return -1
        self.flash[a:a + n] = b"\xff" * n
        return 0

    def _write(self, a, p, n):
        if self.cut_at is not None and self.writes >= self.cut_at:
            self.powered = False                 # the supply went at this write
            return -1
        if a % 8 or n % 8 or a + n > len(self.flash):
            return -1
        data = C.string_at(p, n)
        self.flash[a:a + n] = bytes(x & y for x, y in zip(self.flash[a:a + n], data))
        self.writes += 1
        return 0

    def _read(self, a, p, n):
        if a + n > len(self.flash):
            return -1
        C.memmove(p, bytes(self.flash[a:a + n]), n)
        return 0

    def cut_after(self, n):
        """Lose power at the n-th flash write from now."""
        self.cut_at = self.writes + n

    def image(self, n):
        return bytes(self.flash[BOOT_SIZE + 64:BOOT_SIZE + 64 + n])

    # -- power and resets ------------------------------------------------
    def hw_rev(self):
        for r in self.eol:
            if len(r) == 84 and r[:4] == b"\x1d\xe0\x01\x00" and \
                    zlib.crc32(r[:80]) == struct.unpack("<I", r[80:])[0]:
                return struct.unpack_from("<H", r, 20)[0]
        return 0

    def power_on(self):
        self.powered, self.cut_at, self.stay = True, None, False
        self._reset()

    def _reset(self):
        stay, self.stay = self.stay, False       # the bootloader reads and clears it
        hw = self.hw_rev()
        self.boot.boot_init(self.state, C.byref(self.bf), C.c_uint16(hw))
        if not stay and self.boot.boot_decide(C.byref(self.bf), 0, C.c_uint16(hw)) == 1:
            self.mode = "app"
            self.app = Ecu()
            self.app.init()
            io = self.app.io
            io.ignition = 1
            io.v_clt = io.v_oil = io.v_rail = io.v_boost = io.v_egr = 2.5
            io.v_5v = 5.0
            io.v_bat = 24.0
            self.app.nvm_load(b"", b"")
            self.app.eol_load(*self.eol)
            self.run(1100)                      # no tooth for 1 s: stopped
        else:
            self.mode = "boot"

    def run(self, ms):
        for _ in range(ms):
            self.ms += 1
            t = self.ms * 1000
            if self.turning and self.ms % 3 == 0:
                self.app.crank_edge(t)           # about 330 rpm on a 60-2 wheel
            self.app.tick(t)
            self.app.io.nvm_save = 0
            self.app.io.can_n = self.app.io.can2_n = 0

    # -- the link --------------------------------------------------------
    def request(self, req):
        if not self.powered:
            raise TimeoutError("no response: the unit is off")
        req = bytes(req)
        if self.mode == "boot":
            self.ms += 5
            out = C.create_string_buffer(64)
            n = self.boot.boot_handle(self.state, req, C.c_uint16(len(req)), out,
                                      C.c_uint32(self.ms), C.c_uint32(self.ms * 1000))
            if not self.powered:
                raise TimeoutError("no response: the unit lost power")
            rsp = out.raw[:n]
            if rsp[:1] == b"\x51":              # ECU reset: run the image if it is good
                self._reset()
            return rsp
        rsp = self._app_request(req)
        io = self.app.io
        if io.eol_save:                          # copy a, then copy b
            self.eol = [self.app.eol_image()] * 2
            io.eol_save = 0
        if io.boot_req:
            self.stay = True
            self._reset()
        elif io.reset_req:
            self._reset()
        return rsp

    def _app_request(self, req):
        lib, io = self.app.lib, self.app.io
        fr = C.create_string_buffer(len(req) + 5)
        n = lib.link_frame(req, C.c_uint16(len(req)), fr)
        for i in range(0, n, USB_IN):
            chunk = fr.raw[i:min(n, i + USB_IN)]
            C.memmove(io.usb_in, chunk, len(chunk))
            io.usb_in_n = len(chunk)
            self.app.background()
        self.run(5)
        rx, msg, ln, got = C.create_string_buffer(8192), C.create_string_buffer(4096), C.c_uint16(), b""
        for b in bytes(io.usb_out[:io.usb_out_n]):
            if lib.link_feed(rx, C.c_uint8(b), msg, C.byref(ln)):
                got = msg.raw[:ln.value]
        io.usb_out_n = 0
        return got


if __name__ == "__main__":
    e = Ecu()
    e.init()
    assert e.io.state == OFF
    e.nvm_load(b"", b"")
    img = e.nvm_image()
    assert img[:2] == b"\x25\xec", img[:4]
    e.eol_load(eol_record(b"T1"), b"")
    assert e.eol_image() == eol_record(b"T1"), "eol_record() and eol.h disagree"
    print("ecu.py ok")
