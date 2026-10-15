#!/usr/bin/env python3
"""Stock KiCad symbols for the prototype sheets.

schlib.symbol_def() copies a symbol verbatim, which is wrong for a
DERIVED symbol: STM32G474VETx and USBLC6-2SC6 are `(extends "...")`
stubs with no pins, and a schematic's lib_symbols must hold the full
graphic. flatten() builds that once and seeds schlib's cache with it, so
Sheet.place() works on derived parts unchanged.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "hw"))
import schlib  # noqa: E402

_PIN = re.compile(r'\(pin \w+ \w+ \(at ([-\d.]+) ([-\d.]+) (\d+)\) '
                  r'\(length [\d.]+\)(?: hide)?\s*\(name "([^"]*)"[^\n]*\n'
                  r'\s*\(number "([^"]+)"')


def flatten(libid):
    """symbol_def() for a symbol that may `extends` another in its library."""
    body = schlib.symbol_def(libid)
    m = re.search(r'\(extends "([^"]+)"\)', body.splitlines()[0])
    if not m:
        return body
    lib, name = libid.split(":", 1)
    parent = schlib.symbol_def(f"{lib}:{m.group(1)}")
    # the parent's graphics and pins, under the child's name and properties
    units = parent[parent.index(f'(symbol "{m.group(1)}_'):]
    units = units.replace(f'(symbol "{m.group(1)}_', f'(symbol "{name}_')
    props = body[body.index("(property"):body.rindex(")")].rstrip()
    flags = re.search(r'^\(symbol "[^"]+"(.*?)\n', parent).group(1)
    out = f'(symbol "{libid}"{flags}\n    {props}\n    {units}'
    schlib._CACHE[libid] = out
    return out


def stock_pins(libid):
    """pin number -> (x, y, angle, name) in the symbol's own y-up frame."""
    return {num: (float(x), float(y), int(a), nm)
            for x, y, a, nm, num in _PIN.findall(flatten(libid))}


def stub_dir(angle):
    """Page-frame unit step pointing AWAY from the body at rot 0: a pin
    at angle 0 points right into the body, so its free end faces left."""
    return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[angle]


if __name__ == "__main__":
    p = stock_pins("MCU_ST_STM32G4:STM32G474VETx")
    assert len(p) == 100 and p["20"][3] == "PA0", (len(p), p.get("20"))
    print("symbols ok")
