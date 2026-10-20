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
