#!/usr/bin/env python3
"""Check the STM32 images build.py wrote, on the PC.

    .venv/bin/python firmware/stm32/test_image.py

  - the vector tables: stack top, reset handler in Thumb, at the address
    the bootloader jumps to (APP_VECTORS) or 0x08000000 (standalone)
  - the application's code stays in bank 1, so writes to bank 2 never
    stall it; RAM leaves room for the stack
  - the bootloader fits its 32 KiB, its boot info sits where the
    application reads it, and its RAM erase loop is really in RAM
  - no double-precision arithmetic (the M4F has a single-precision FPU:
    a double would be a slow software routine)
  - the real bootloader core (firmware/boot/boot.c, the PC build in
    firmware/sim/build) accepts app_signed.hex, and refuses it with one
    byte changed
"""
import ctypes as C
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "build")
sys.path.insert(0, HERE)
import build as B  # noqa: E402

fails = []


def check(ok, what):
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok:
        fails.append(what)


def read_hex(path):
    mem, upper = {}, 0
    for line in open(path):
        line = line.strip()
        if not line.startswith(":"):
            continue
        b = bytes.fromhex(line[1:])
        n, addr, t, data = b[0], b[1] << 8 | b[2], b[3], b[4:4 + b[0]]
        if t == 4:
            upper = struct.unpack(">H", data)[0] << 16
        elif t == 0:
            for i in range(n):
                mem[upper + addr + i] = data[i]
    return mem


def elf_word(elf, addr):
    """the 32-bit word at a flash address, from the ELF's program data"""
    d = open(elf, "rb").read()
    phoff, = struct.unpack_from("<I", d, 0x1C)
    phentsize, phnum = struct.unpack_from("<HH", d, 0x2A)
    for i in range(phnum):
        p_type, off, vaddr, paddr, filesz = struct.unpack_from("<IIIII", d, phoff + i * phentsize)
        if p_type == 1 and paddr <= addr < paddr + filesz:
            return struct.unpack_from("<I", d, off + addr - paddr)[0]
    return None


DOUBLE = ("__aeabi_dadd", "__aeabi_dmul", "__aeabi_ddiv", "__aeabi_dsub", "__adddf3", "__muldf3",
          "__divdf3", "__aeabi_f2d", "__extendsfdf2")
STACK_TOP = B.RAM0 + B.RAM_LEN


def vectors(name, base):
    elf = os.path.join(OUT, name + ".elf")
    s = B.symbols(elf)
    check(s.get("vectors", (0,))[0] == base, f"{name}: vector table at 0x{base:08X}")
    sp, rst = elf_word(elf, base), elf_word(elf, base + 4)
    check(sp == STACK_TOP, f"{name}: initial stack 0x{sp or 0:08X} = top of RAM")
    check(rst is not None and rst & 1 and rst == s["Reset_Handler"][0] | 1,
          f"{name}: reset vector is Reset_Handler, Thumb")
    bad = [d for d in DOUBLE if d in s]
    check(not bad, f"{name}: no double-precision routines {bad or ''}")
    return s


def main():
    print("STM32 images")
    for name in ("app", "app_model"):
        s = vectors(name, B.APP_VECTORS)
        end = s["_flash_end"][0]
        check(end <= 0x08040000, f"{name}: code ends 0x{end:08X}, in bank 1")
        ram = s["_ebss"][0]
        check(STACK_TOP - ram >= 16 * 1024, f"{name}: {(STACK_TOP - ram) // 1024} KiB left for the stack")
    vectors("app_standalone", 0x08000000)

    s = vectors("boot", 0x08000000)
    check(s["_flash_end"][0] <= 0x08007FE0, "boot: fits below its boot info")
    check(s.get("boot_info", (0,))[0] == 0x08007FE0, "boot: boot_info at 0x08007FE0")
    bi = elf_word(os.path.join(OUT, "boot.elf"), 0x08007FE0)
    check(bi == 0xB0071AF0, f"boot: boot info magic 0x{bi or 0:08X}")
    r = s.get("ram_erase_wait", (0,))[0]
    check(0x20000000 <= r < 0x20020000, f"boot: the bank-1 erase loop runs from RAM (0x{r:08X})")
    hx = read_hex(os.path.join(OUT, "boot.hex"))
    check(min(hx) == 0x08000000 and max(hx) < B.APP_BASE, "boot.hex: inside the boot area")

    # the bootloader core, on the PC, against the signed image
    ext = {"darwin": "dylib", "win32": "dll"}.get(sys.platform, "so")
    lib = os.path.join(ROOT, "firmware", "sim", "build", f"libboot.{ext}")
    if not os.path.exists(lib):
        check(False, f"{lib} missing: run ./verify.sh (its SIL libraries step) first")
        return finish()
    boot = C.CDLL(lib)
    mem = read_hex(os.path.join(OUT, "app_signed.hex"))
    lo, hi = B.APP_BASE, max(mem) + 1
    flash = bytearray(b"\xff" * (B.APP_END - B.APP_BASE))
    for a, v in mem.items():
        flash[a - lo] = v
    check(lo == min(mem), "app_signed.hex starts at the header, APP_BASE")
    app_bin = open(os.path.join(OUT, "app.bin"), "rb").read()
    check(bytes(flash[64:64 + len(app_bin)]) == app_bin, "app.bin is the signed image's payload")
    vec = struct.unpack_from("<II", flash, B.APP_VECTORS - B.APP_BASE)
    check(vec[0] == STACK_TOP, "the vectors sit at APP_VECTORS inside the image")

    ERASE = C.CFUNCTYPE(C.c_int, C.c_uint32, C.c_uint32)
    RW = C.CFUNCTYPE(C.c_int, C.c_uint32, C.POINTER(C.c_uint8), C.c_uint32)

    class BF(C.Structure):
        _fields_ = [("erase", ERASE), ("write", RW), ("read", RW), ("app_base", C.c_uint32),
                    ("app_size", C.c_uint32)]

    def rd(a, p, n):
        if a < lo or a - lo + n > len(flash):
            return -1
        C.memmove(p, bytes(flash[a - lo:a - lo + n]), n)
        return 0
    cbs = (ERASE(lambda a, n: -1), RW(lambda a, p, n: -1), RW(rd))
    bf = BF(*cbs, B.APP_BASE, B.APP_END - B.APP_BASE)
    check(boot.boot_decide(C.byref(bf), 0, 0) == 1, "boot.c accepts app_signed (blank EOL: revision 0)")
    check(boot.boot_decide(C.byref(bf), 0, 0x0100) == 1, "boot.c accepts it at revision 1.0")
    check(boot.boot_decide(C.byref(bf), 1, 0) == 0, "boot.c stays when the stay flag is set")
    flash[64 + len(app_bin) // 2] ^= 1
    check(boot.boot_decide(C.byref(bf), 0, 0) == 0, "boot.c refuses it with one bit changed")
    return finish()


def finish():
    print(f"{'ALL PASS' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
