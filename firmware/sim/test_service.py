#!/usr/bin/env python3
"""The laptop service tool end to end, against a simulated unit (the C
application and bootloader through ctypes, a simulated flash).
Run: .venv/bin/python firmware/sim/test_service.py"""
import contextlib
import io
import json
import os
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "tools")]
import ecu_service  # noqa: E402
from ecu import Unit  # noqa: E402

TMP = pathlib.Path(tempfile.mkdtemp())
SECRET = TMP / "secret.bin"
SECRET.write_bytes(b"ECU25KVA-service")      # the build's default SEC_SECRET


def run(unit, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        rc = ecu_service.main(["--link", "sim", "--secret", str(SECRET), *args], link=unit)
    return rc, out.getvalue()


def eol_write(unit, *extra):
    trims = TMP / "trims.json"
    trims.write_text(json.dumps({"gain": [1.02, 1, 1, 1, 1, 0.98], "offset": [0.01, 0, 0, 0, 0, -0.02]}))
    return run(unit, "eol-write", "--serial", "SN0042", "--hw-rev", "0x0100", "--date", "20261020",
               "--trims", str(trims), "--station", "3", "--passed", *extra)


def test_eol():
    u = Unit()
    rc, out = eol_write(u)
    assert rc == 0, out
    rc, out = run(u, "eol-read")
    assert rc == 0 and "SN0042" in out and "1.02" in out and "20261020" in out, out
    assert "station 3" in out and "passed yes" in out and "locked no" in out, out
    rc, out = run(u, "eol-lock")
    assert rc == 0, out
    rc, out = eol_write(u)
    assert rc != 0 and "locked" in out, out
    rc, out = run(u, "eol-unlock")
    assert rc == 0, out
    rc, out = eol_write(u)
    assert rc == 0, out


def test_flash():
    u = Unit()
    assert eol_write(u)[0] == 0
    img = TMP / "a.bin"
    img.write_bytes(os.urandom(64 * 1024))
    rc, out = run(u, "flash", str(img), "--sw-ver", "0x00010002", "--hw-min", "0x0100", "--hw-max", "0x01FF")
    assert rc == 0, out
    assert u.mode == "app", u.mode                      # the bootloader decided "jump"
    assert u.image(64 * 1024) == img.read_bytes()
    img2 = TMP / "b.bin"
    img2.write_bytes(os.urandom(64 * 1024))
    u.cut_after(32)                                      # half of the 64 transfer blocks
    rc, out = run(u, "flash", str(img2), "--sw-ver", "3", "--hw-min", "0x0100", "--hw-max", "0x01FF")
    assert rc != 0, out
    u.power_on()
    assert u.mode == "boot", u.mode                      # no header: it stays
    rc, out = run(u, "flash", str(img2), "--sw-ver", "3", "--hw-min", "0x0100", "--hw-max", "0x01FF")
    assert rc == 0, out
    assert u.mode == "app" and u.image(64 * 1024) == img2.read_bytes()
    rc, out = run(u, "info")
    assert rc == 0 and "SN0042" in out, out


def test_wrong_hardware():
    u = Unit()
    assert eol_write(u)[0] == 0                          # hw_rev 0x0100
    img = TMP / "c.bin"
    img.write_bytes(os.urandom(4096))
    rc, out = run(u, "flash", str(img), "--sw-ver", "1", "--hw-min", "0x0200", "--hw-max", "0x02FF")
    assert u.mode == "boot", (u.mode, out)               # a good image for other hardware stays


def test_engine_turning():
    u = Unit()
    u.turning = True
    u.run(100)                                           # someone is cranking it
    rc, out = eol_write(u)
    assert rc != 0 and "engine must be stopped" in out, out


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(n for n in globals() if n.startswith("test_"))
    for n in names:
        globals()[n]()
        print("ok", n)
    print("service tool ok")
