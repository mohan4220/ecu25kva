#!/usr/bin/env python3
"""Project footprints, derived from KiCad's stock library by renumbering.

A footprint's pad numbers have to match its symbol's pin numbers, and
KiCad has no pin-to-pad map to fix a mismatch afterwards. Several stock
power packages number their pads for a different symbol than the one a
two-terminal part uses here:

    TO-277A (SMPC)   stock: 1, 2 = anode leads, 3 = cathode tab
                     Device:D / D_Schottky: 1 = K, 2 = A
    SOT-23 zener     BZX84-Q: 1 = anode, 2 = n.c., 3 = cathode
                     Device:D_Zener: 1 = K, 2 = A

Drawing the SS20PH102HM3 with the stock pads would have put the cathode
on the two small leads and the anode on the tab -- the same class of
error as a GSD FET symbol on a TO-252 footprint (see schlib.PINS).

So each footprint here is the stock one, copied byte for byte except for
its name and the pad numbers in REMAP. Unnumbered pads (paste
apertures) are left alone. Re-run after a KiCad library update.
"""
import os
import re

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "lib", "ecu25kva.pretty")
STOCK = "/usr/share/kicad/footprints"

# new name: (stock library, stock footprint, {stock pad: new pad})
REMAP = {
    "TO-277A_K1_A2": ("Package_TO_SOT_SMD", "TO-277A",
                      {"3": "1", "1": "2", "2": "2"}),
    # SOT-23 zeners (BZX84-Q): pin 1 anode, 2 n.c., 3 cathode.
    "SOT-23_Zener_K1_A2": ("Package_TO_SOT_SMD", "SOT-23",
                           {"3": "1", "1": "2", "2": "3"}),
}


def derive(name, lib, fp, padmap):
    src = open(os.path.join(STOCK, lib + ".pretty", fp + ".kicad_mod")).read()
    out = re.sub(r'^\(footprint "[^"]+"', f'(footprint "{name}"', src, count=1)
    out = out.replace(f'(value "{fp}"', f'(value "{name}"')
    out = re.sub(r'\(property "Value" "[^"]*"',
                 f'(property "Value" "{name}"', out)

    # Stock files write pad numbers both quoted and bare: (pad "1" ...)
    # in TO-277A, (pad 1 ...) in SOT-23.
    pad_re = r'\(pad (?:"([^"]*)"|([^\s")]+))'

    def pad(m):
        num = m.group(1) if m.group(1) is not None else m.group(2)
        return f'(pad "{padmap.get(num, num)}"'
    found = {m.group(1) if m.group(1) is not None else m.group(2)
             for m in re.finditer(pad_re, src)}
    out, n = re.subn(pad_re, pad, out)
    moved = sum(1 for k in padmap if k in found)
    if moved != len(padmap):
        raise SystemExit(f"{fp}: expected pads {sorted(padmap)} in the "
                         "stock footprint -- has the library changed?")
    with open(os.path.join(OUT, name + ".kicad_mod"), "w") as f:
        f.write(out)
    return n


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, (lib, fp, padmap) in REMAP.items():
        n = derive(name, lib, fp, padmap)
        print(f"{name}: from {lib}:{fp}, {n} pads, renumbered {padmap}")
