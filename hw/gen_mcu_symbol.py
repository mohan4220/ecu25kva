#!/usr/bin/env python3
"""Generate the S32K148 144-LQFP KiCad symbol from NXP's own pin table.

KiCad 7 ships no S32K symbol of any kind (checked: nothing matching S32K
under /usr/share/kicad/symbols), so this part has to be drawn. Drawing 144
pins by hand is exactly the kind of transcription the PCB roadmap warns is
"the most likely place to introduce a silent error", so it is generated
instead, straight from refs/s32k148-144lqfp-pins.csv -- which hw/
extract_pinmux.py pulls out of the Reference Manual's own embedded
workbook. Nobody retypes a pin number anywhere in this chain.

Six units, because a 144-pin part in one rectangle is unreadable and
because these are the boundaries the design already thinks in:

    1-5  PTA PTB PTC PTD PTE   one per port
    6    PWR                   VDD/VDDA/VREFH/VSS/VREFL

Reset pull state (PE/PS) is carried into each pin's name as a suffix,
because it is load-bearing here and invisible otherwise: supervisor.cir's
whole fail-safe argument turns on the six driver-gate pins being Hi-Z with
no pull at reset, and the cost of finding that out from a schematic is a
trip back to this spreadsheet.

    (no suffix)  PE=0, high impedance, no pull at reset
    [PU]         PE=1 PS=1, pulled up at reset
    [PD]         PE=1 PS=0, pulled down at reset
"""
import csv
import os
import re
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINS = os.path.join(ROOT, "refs", "s32k148-144lqfp-pins.csv")
OUT = os.path.join(ROOT, "hw", "lib", "ecu25kva.kicad_sym")

NAME = "S32K148_144LQFP"
FOOTPRINT = "Package_QFP:LQFP-144_20x20mm_P0.5mm"
DATASHEET = "https://www.nxp.com/docs/en/data-sheet/S32K1xx.pdf"

PITCH = 2.54
PIN_LEN = 5.08
# Pins whose electrical type is not plain bidirectional.
POWER_IN = {"VDD", "VDDA", "VREFH", "VSS", "VREFL"}


def port_key(name):
    """Sort PTA10 after PTA9, not before it."""
    m = re.match(r"PT([A-E])(\d+)$", name)
    return (m.group(1), int(m.group(2))) if m else (name, 0)


def pull_suffix(row):
    if row["pe"] != "1":
        return ""
    return "[PU]" if row["ps"] == "1" else "[PD]"


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def pin(name, number, x, y, rot, etype):
    return (f'      (pin {etype} line (at {x:.2f} {y:.2f} {rot}) '
            f'(length {PIN_LEN})\n'
            f'        (name "{esc(name)}" (effects (font (size 1.27 1.27))))\n'
            f'        (number "{number}" (effects (font (size 1.27 1.27))))\n'
            f'      )')


def unit(idx, unit_name, left, right, width=50.8):
    """One unit: `left` on the west edge, `right` on the east edge.

    Both columns start at the same top y so the body is symmetric, and the
    rectangle is sized to whichever column is longer.
    """
    rows = max(len(left), len(right))
    half = (rows - 1) * PITCH / 2
    top = half + PITCH
    hw = width / 2
    body = [f'    (symbol "{NAME}_{idx}_1"',
            f'      (rectangle (start {-hw:.2f} {top:.2f}) '
            f'(end {hw:.2f} {-top:.2f})',
            '        (stroke (width 0.254) (type default))',
            '        (fill (type background))',
            '      )']
    for i, r in enumerate(left):
        y = half - i * PITCH
        et = "power_in" if r["port"] in POWER_IN else "bidirectional"
        body.append(pin(r["label"], r["pin"], -hw - PIN_LEN, y, 0, et))
    for i, r in enumerate(right):
        y = half - i * PITCH
        et = "power_in" if r["port"] in POWER_IN else "bidirectional"
        body.append(pin(r["label"], r["pin"], hw + PIN_LEN, y, 180, et))
    body.append('    )')
    return "\n".join(body), unit_name


def main():
    rows = list(csv.DictReader(open(PINS)))
    for r in rows:
        r["label"] = r["port"] + pull_suffix(r)

    units = []
    for letter in "ABCDE":
        grp = sorted((r for r in rows if r["port"].startswith("PT" + letter)),
                     key=lambda r: port_key(r["port"]))
        mid = (len(grp) + 1) // 2
        units.append((grp[:mid], grp[mid:], f"PT{letter}"))

    # Power unit: supplies on the left, returns on the right, each in
    # package-pin order so a reader can check them off against the part.
    sup = [r for r in rows if r["pad_type"] == "SUPPLY"]
    pos = sorted((r for r in sup if r["port"] in ("VDD", "VDDA", "VREFH")),
                 key=lambda r: int(r["pin"]))
    neg = sorted((r for r in sup if r["port"] in ("VSS", "VREFL")),
                 key=lambda r: int(r["pin"]))
    units.append((pos, neg, "PWR"))

    out = ['(kicad_symbol_lib (version 20220914) (generator ecu25kva_gen)',
           f'  (symbol "{NAME}" (pin_names (offset 0.508)) (in_bom yes) '
           f'(on_board yes)',
           '    (property "Reference" "U" (at 0 2.54 0) '
           '(effects (font (size 1.27 1.27))))',
           f'    (property "Value" "{NAME}" (at 0 -2.54 0) '
           f'(effects (font (size 1.27 1.27))))',
           f'    (property "Footprint" "{FOOTPRINT}" (at 0 0 0) '
           f'(effects (font (size 1.27 1.27)) hide))',
           f'    (property "Datasheet" "{DATASHEET}" (at 0 0 0) '
           f'(effects (font (size 1.27 1.27)) hide))',
           '    (property "MPN" "FS32K148HAT0MLQT" (at 0 0 0) '
           '(effects (font (size 1.27 1.27)) hide))',
           '    (property "ki_description" "NXP S32K148, Cortex-M4F, 144-LQFP,'
           ' 80 MHz, -40..125C. Pins generated from the Reference Manual\'s '
           'embedded IO Signal Table -- see hw/extract_pinmux.py." '
           '(at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
           '    (property "ki_keywords" "S32K148 NXP Cortex-M4F automotive '
           'MCU CAN-FD" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))']
    total = 0
    for i, (left, right, uname) in enumerate(units, start=1):
        body, _ = unit(i, uname, left, right)
        out.append(body)
        total += len(left) + len(right)
    out.append('  )')
    out.append(')')

    assert total == 144, f"{total} pins emitted, expected 144"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(out) + "\n")
    print(f"{OUT}: {total} pins in {len(units)} units")
    for i, (l, r, n) in enumerate(units, start=1):
        print(f"  unit {i}  {n:4} {len(l) + len(r):3} pins")


if __name__ == "__main__":
    main()
