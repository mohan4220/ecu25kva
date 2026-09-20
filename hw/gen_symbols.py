#!/usr/bin/env python3
"""Generate the project's KiCad symbol library.

Two parts live here, for the same reason: KiCad 7 ships neither, and both
are drawn from a datasheet that was actually retrieved and read.

  S32K148_144LQFP   from NXP's own pin table (see below)
  TPS3850G33        from TI SBVS301B, Table 5-1 Pin Functions

Also writes hw/lib/s32k148_layout.json, the map of where each port pin
lands in the symbol. Sheet generators read it so a wire stub meets its
pin exactly, instead of re-deriving the layout and drifting from it.

--- S32K148 ---

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
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINS = os.path.join(ROOT, "refs", "s32k148-144lqfp-pins.csv")
OUT = os.path.join(ROOT, "hw", "lib", "ecu25kva.kicad_sym")
LAYOUT = os.path.join(ROOT, "hw", "lib", "s32k148_layout.json")

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


# ---------------------------------------------------------------------
# TPS3850G33 -- windowed supervisor with watchdog
# ---------------------------------------------------------------------
# Source: TI SBVS301B (Oct 2016, rev. Sep 2021), Table 5-1 "Pin
# Functions" and Figure 5-1 "DRC Package", both read from the retrieved
# datasheet. Research memo 11 sec.2.1 already had this part CONFIRMED on
# its electricals; what was missing, and is added here, is the pinout.
#
# WHY THE G33 VARIANT, from the datasheet's own Table 11-1 nomenclature
# (G = thresholds at +/-4% of nominal, H = +/-7%; 33 = 3.3 V) and its
# +/-0.8% threshold accuracy spec:
#
#              UV nominal   UV worst-low   OV nominal   OV worst-high
#     G33        3.168 V       3.143 V       3.432 V       3.459 V
#     H33        3.069 V       3.044 V       3.531 V       3.559 V
#
# The supervisor exists to assert BEFORE the MCU's own low-voltage
# detect does, so its undervoltage threshold has to clear the S32K148's
# LVD maximum of 3.0 V -- and the 2.97 V correctness floor under that --
# with margin that survives the part's own accuracy spec. G33 clears it
# by 143 mV worst case. H33 clears it by 44 mV, which is close enough to
# LVD that the two could fire in either order, and a supervisor that
# might lose the race to the thing it is supervising is not doing its
# job.
#
# The cost of the tighter window is that the rail has to live inside
# 3.143-3.459 V. A 3.3 V regulator at +/-2% spans 3.234-3.366 V, which
# leaves about 90 mV at each end. That is the constraint G33 puts on the
# rails sheet, and it is why the choice is recorded here rather than
# left as "a TPS3850-class part".
#
# RESET and WDO are open-drain and need external pullups (datasheet:
# "Connect RESET using a 1-kOhm to 100-kOhm resistor to VDD").
TPS_NAME = "TPS3850G33"
TPS_FOOTPRINT = "Package_SON:VSON-10-1EP_3x3mm_P0.5mm_EP1.2x2mm"
TPS_DATASHEET = "https://www.ti.com/lit/ds/symlink/tps3850.pdf"
# (name, number, electrical type) -- numbers are Figure 5-1's, not guessed
TPS_LEFT = [("SENSE", "10", "input"), ("WDI", "7", "input"),
            ("CWD", "2", "input"), ("CRST", "4", "input"),
            ("SET0", "3", "input"), ("SET1", "6", "input")]
TPS_RIGHT = [("~RESET", "9", "open_collector"),
             ("~WDO", "8", "open_collector")]
TPS_PWR = [("VDD", "1", "power_in", "up"), ("GND", "5", "power_in", "down")]


def build_tps3850():
    hw, rows = 12.7, max(len(TPS_LEFT), len(TPS_RIGHT))
    half = (rows - 1) * PITCH / 2
    top = half + PITCH
    body = [f'  (symbol "{TPS_NAME}" (pin_names (offset 1.016)) (in_bom yes) '
            f'(on_board yes)',
            '    (property "Reference" "U" '
            f'(at 0 {top + 2.54} 0) {"(effects (font (size 1.27 1.27)))"})',
            f'    (property "Value" "{TPS_NAME}" (at 0 {-top - 2.54} 0) '
            f'(effects (font (size 1.27 1.27))))',
            f'    (property "Footprint" "{TPS_FOOTPRINT}" (at 0 0 0) '
            f'(effects (font (size 1.27 1.27)) hide))',
            f'    (property "Datasheet" "{TPS_DATASHEET}" (at 0 0 0) '
            f'(effects (font (size 1.27 1.27)) hide))',
            '    (property "MPN" "TPS3850G33DRCT" (at 0 0 0) '
            '(effects (font (size 1.27 1.27)) hide))',
            '    (property "ki_description" "TI TPS3850G33 -- 3.3 V windowed '
            'supervisor with programmable window watchdog, VSON-10. '
            'Thresholds +/-4%: UV 3.168 V nom, OV 3.432 V nom. RESET and WDO '
            'are open-drain." (at 0 0 0) '
            '(effects (font (size 1.27 1.27)) hide))',
            '    (property "ki_keywords" "supervisor watchdog reset '
            'brownout window TPS3850" (at 0 0 0) '
            '(effects (font (size 1.27 1.27)) hide))',
            f'    (symbol "{TPS_NAME}_1_1"',
            f'      (rectangle (start {-hw} {top}) (end {hw} {-top})',
            '        (stroke (width 0.254) (type default))',
            '        (fill (type background))',
            '      )']
    for i, (nm, num, et) in enumerate(TPS_LEFT):
        y = half - i * PITCH
        body.append(pin(nm, num, -hw - PIN_LEN, y, 0, et))
    for i, (nm, num, et) in enumerate(TPS_RIGHT):
        y = half - i * PITCH
        body.append(pin(nm, num, hw + PIN_LEN, y, 180, et))
    for nm, num, et, d in TPS_PWR:
        if d == "up":
            body.append(pin(nm, num, 0, top + PIN_LEN, 270, et))
        else:
            body.append(pin(nm, num, 0, -top - PIN_LEN, 90, et))
    body.append('    )')
    body.append('  )')
    return "\n".join(body)


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

    assert total == 144, f"{total} pins emitted, expected 144"

    # Where each pin lands, so sheet generators do not re-derive it.
    layout = {}
    for i, (left, right, uname) in enumerate(units, start=1):
        rows = max(len(left), len(right))
        half = (rows - 1) * PITCH / 2
        for side, grp in (("L", left), ("R", right)):
            for j, r in enumerate(grp):
                # Keyed by PACKAGE PIN, not port name. Six pins are all
                # called VDD and seven all called VSS, so keying by name
                # silently keeps one of each and loses the rest.
                layout[r["pin"]] = {
                    "unit": i, "unit_name": uname, "side": side,
                    "port": r["port"], "label": r["label"],
                    "dx": (-25.4 - PIN_LEN) if side == "L" else (25.4 + PIN_LEN),
                    "dy": -(half - j * PITCH),
                }
    out.append(build_tps3850())
    out.append(')')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(out) + "\n")
    with open(LAYOUT, "w") as f:
        json.dump(layout, f, indent=1, sort_keys=True)
    print(f"{OUT}: {total} pins in {len(units)} units, plus TPS3850G33")
    print(f"{LAYOUT}: {len(layout)} pin positions")
    for i, (l, r, n) in enumerate(units, start=1):
        print(f"  unit {i}  {n:4} {len(l) + len(r):3} pins")


if __name__ == "__main__":
    main()
