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
ICPINS = os.path.join(ROOT, "hw", "lib", "ic_pins.json")

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


def build_tps3850(geom=None):
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
    def emit(nm, num, px, py, rot, et):
        body.append(pin(nm, num, px, py, rot, et))
        if geom is not None:
            geom[num] = (round(px, 2), round(py, 2))

    for i, (nm, num, et) in enumerate(TPS_LEFT):
        emit(nm, num, -hw - PIN_LEN, half - i * PITCH, 0, et)
    for i, (nm, num, et) in enumerate(TPS_RIGHT):
        emit(nm, num, hw + PIN_LEN, half - i * PITCH, 180, et)
    for nm, num, et, d in TPS_PWR:
        emit(nm, num, 0, (top + PIN_LEN) if d == "up" else (-top - PIN_LEN),
             270 if d == "up" else 90, et)
    body.append('    )')
    body.append('  )')
    return "\n".join(body)


# ---------------------------------------------------------------------
# Simple rectangular parts
# ---------------------------------------------------------------------
# Everything below is one builder. Each part is a table of pins and the
# side they come out of; the pin NUMBERS are the datasheet's, read from
# the retrieved document named in each entry's comment, and nothing here
# is transcribed twice.
def simple_symbol(name, fp, ds, mpn, desc, keywords,
                  left, right, top=(), bottom=(), hw=15.24, geom=None):
    """left/right/top/bottom are (pin_name, number, electrical_type).

    If `geom` is a dict it is filled with {pin_number: (dx, dy)} -- the
    symbol-local offset of every pin, rounded the same way the pins
    themselves are written. Sheets read that instead of re-deriving the
    body height from the pin counts, which is how the rails sheet first
    came out with every LDO pin two millimetres from its wire.
    """
    rows = max(len(left), len(right), 1)
    half = (rows - 1) * PITCH / 2
    top_y = half + PITCH * 1.5
    body = [f'  (symbol "{name}" (pin_names (offset 1.016)) (in_bom yes) '
            f'(on_board yes)',
            f'    (property "Reference" "U" (at 0 {top_y + 2.54} 0) '
            f'(effects (font (size 1.27 1.27))))',
            f'    (property "Value" "{name}" (at 0 {-top_y - 2.54} 0) '
            f'(effects (font (size 1.27 1.27))))',
            f'    (property "Footprint" "{fp}" (at 0 0 0) '
            f'(effects (font (size 1.27 1.27)) hide))',
            f'    (property "Datasheet" "{ds}" (at 0 0 0) '
            f'(effects (font (size 1.27 1.27)) hide))',
            f'    (property "MPN" "{mpn}" (at 0 0 0) '
            f'(effects (font (size 1.27 1.27)) hide))',
            f'    (property "ki_description" "{desc}" (at 0 0 0) '
            f'(effects (font (size 1.27 1.27)) hide))',
            f'    (property "ki_keywords" "{keywords}" (at 0 0 0) '
            f'(effects (font (size 1.27 1.27)) hide))',
            f'    (symbol "{name}_1_1"',
            f'      (rectangle (start {-hw} {top_y}) (end {hw} {-top_y})',
            '        (stroke (width 0.254) (type default))',
            '        (fill (type background))',
            '      )']
    def emit(nm, num, px, py, rot, et):
        body.append(pin(nm, num, px, py, rot, et))
        if geom is not None:
            geom[num] = (round(px, 2), round(py, 2))

    for i, (nm, num, et) in enumerate(left):
        emit(nm, num, -hw - PIN_LEN, half - i * PITCH, 0, et)
    for i, (nm, num, et) in enumerate(right):
        emit(nm, num, hw + PIN_LEN, half - i * PITCH, 180, et)
    span = (len(top) - 1) * PITCH * 2
    for i, (nm, num, et) in enumerate(top):
        emit(nm, num, -span / 2 + i * PITCH * 2, top_y + PIN_LEN, 270, et)
    span = (len(bottom) - 1) * PITCH * 2
    for i, (nm, num, et) in enumerate(bottom):
        emit(nm, num, -span / 2 + i * PITCH * 2, -top_y - PIN_LEN, 90, et)
    body.append('    )')
    body.append('  )')
    return "\n".join(body)


# --- LM5164, 100 V / 1 A synchronous buck ---------------------------
# Source: TI SNVSAU4D (Sep 2018, rev. Feb 2026), Table 4-1 Pin Functions
# and Figure 4-1 DDA package.
#
# WHY THIS PART AND NOT THE ONE IN THE BOM MEMO. research memo 07 sec.4
# lists TPS54360B-Q1, chosen there as "60 V-rated ... over 42 V LM5175-Q1
# for load-dump margin". That reasoning was sound when the TVS clamped
# below 60 V. It no longer is: raising the standoff to 43 V so the part
# stops conducting during a normal clamped dump raised the pulse 2a clamp
# to 73.3 V, and transient_clamp.cir now carries a passing check that says
# so outright -- "60 V-class parts are NO LONGER viable downstream". A
# 60 V buck on this input is a part that fails the first ISO 7637-2
# pulse 2a event.
#
# The LM5164 was already the part every rating check in the suite was
# written against (its -0.3 V / 100 V VIN limits are what negative_pulses
# and transient_clamp check); it just had never been reconciled with the
# BOM memo. 100 V input, 1 A, 6 V to 100 V operating range -- the 6 V end
# covers the cranking dip the spec's own input range is built around.
LM5164 = dict(
    name="LM5164", fp="Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm",
    ds="https://www.ti.com/lit/ds/symlink/lm5164.pdf", mpn="LM5164DDAR",
    desc="TI LM5164 -- 100 V input, 1 A synchronous buck, constant on-time "
         "with VIN feedforward. 6-100 V in, 1.2 V feedback reference.",
    keywords="buck DCDC synchronous 100V automotive LM5164",
    left=[("VIN", "2", "power_in"), ("EN/UVLO", "3", "input"),
          ("RON", "4", "input"), ("FB", "5", "input")],
    right=[("SW", "8", "output"), ("BST", "7", "power_in"),
           ("PGOOD", "6", "open_collector")],
    bottom=[("GND", "1", "power_in")])

# --- TLV767-Q1, fixed 3.3 V LDO --------------------------------------
# Source: TI SBVS381A (Apr 2020, rev. Dec 2020), Table 5-1 Pin Functions
# and Figure 5-2 (the FIXED version -- the adjustable one has FB on pin 3
# where this has SNS, and they are not interchangeable).
#
# Chosen for accuracy, which the supervisor made load-bearing: TPS3850G33
# trips below 3.143 V and above 3.459 V, so the rail has to stay inside
# that window over the whole temperature range or the board resets itself.
# TLV767-Q1 is 1% over load AND temperature, giving 3.267-3.333 V -- about
# 125 mV of margin at each end. research memo 07 sec.6 named
# TLV1117-33QDCYRQ1 as a representative part, explicitly "class pricing,
# not fetched"; this is the first 3V3 regulator in the project with a
# retrieved datasheet behind it.
TLV76733 = dict(
    name="TLV76733", fp="Package_SON:VSON-8-1EP_3x3mm_P0.65mm_EP1.65x2.4mm",
    ds="https://www.ti.com/lit/ds/symlink/tlv767-q1.pdf",
    mpn="TLV76733QWDRBRQ1",
    desc="TI TLV767-Q1 fixed 3.3 V LDO, 1 A, 2.5-16 V in, 1% accuracy over "
         "load and temperature, AEC-Q100. VSON-8 (DRB).",
    keywords="LDO regulator 3.3V automotive AEC-Q100 TLV767",
    left=[("IN", "8", "power_in"), ("EN", "5", "input")],
    right=[("OUT", "1", "power_out"), ("SNS", "3", "input"),
           ("NC", "2", "no_connect"), ("NC", "7", "no_connect")],
    bottom=[("GND", "4", "power_in"), ("GND", "6", "power_in")])


# --- TCAN1042HGV-Q1, high-speed CAN transceiver ----------------------
# Source: TI SLLSES9D (Feb 2016, rev. Oct 2021), Table 6-1 Pin Functions
# and Figure 6-3, the D (SOIC-8) package for the "V"-suffix devices.
#
# Not a new choice -- research memo 07 sec.10 already selected
# TCAN1042HGVDRQ1, with DigiKey pricing and a named second source
# (NXP TJA1051/TJA1042). What was missing was the pinout, and the
# variant's suffixes, which matter:
#
#   H   bus fault protection +/-70 V instead of +/-58 V. This is a
#       genset harness sharing a loom with contactors and an
#       alternator, so the wider figure is worth having.
#   V   adds the VIO pin, pin 5, where the non-V parts have NC. VIO
#       level-shifts TXD/RXD to whatever rail it is tied to. Tied to
#       3V3_MCU here, so the logic side matches the S32K148 directly
#       and no level shifter is needed. Without the V suffix the logic
#       pins sit at VCC = 5 V and every line needs translating.
#
# STB is an ACTIVE-HIGH standby input, so it is pulled low for normal
# operation. It is brought to a net rather than tied at the pin, since
# a GPIO could take it later for a low-power mode -- the pin map has no
# channel for it today.
TCAN1042 = dict(
    name="TCAN1042HGV", fp="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    ds="https://www.ti.com/lit/ds/symlink/tcan1042-q1.pdf",
    mpn="TCAN1042HGVDRQ1",
    desc="TI TCAN1042HGV-Q1 high-speed CAN transceiver, SOIC-8. "
         "+/-70 V bus fault protection, VIO pin for 3.3 V logic, "
         "active-high standby. AEC-Q100.",
    keywords="CAN transceiver J1939 automotive TCAN1042 ISO11898",
    left=[("TXD", "1", "input"), ("RXD", "4", "output"),
          ("STB", "8", "input")],
    right=[("CANH", "7", "bidirectional"), ("CANL", "6", "bidirectional")],
    top=[("VCC", "3", "power_in"), ("VIO", "5", "power_in")],
    bottom=[("GND", "2", "power_in")],
    hw=12.7)


# --- Generic single op-amp -------------------------------------------
# NOT A PART. KiCad ships no generic op-amp symbol, and every specific
# one in Amplifier_Operational carries a real pinout -- placing LM324
# here would assert a part choice nobody has made.
#
# So this symbol carries FUNCTION ONLY. Its pin numbers are 1-5 and they
# are placeholders: no footprint is assigned, and the sheet says so.
# What IS specified, from sensor_differential.cir, is the requirement it
# stands for:
#
#   Single 5 V supply, rail-to-rail input and output, and a difference
#   network whose resistor RATIO matching gives at least 60 dB CMRR --
#   the floor the block's own tolerance note tried and found the
#   differential argument still holds at. The netlist models 80 dB and
#   marks it INFERRED.
#
# 0.1% discrete resistors give roughly 48 dB, which does NOT clear that
# floor. A matched network (ratio matching 0.05% or better), or a
# dedicated difference amplifier with the network on-die, does.
OPAMP = dict(
    name="OPAMP_GENERIC", fp="",
    ds="", mpn="",
    desc="GENERIC op-amp placeholder -- function only, no part chosen. "
         "Requirement: single 5 V supply, rail-to-rail in and out, "
         "difference network matched for >=60 dB CMRR. Pin numbers are "
         "placeholders and no footprint is assigned.",
    keywords="opamp generic placeholder amplifier",
    left=[("IN+", "3", "input"), ("IN-", "2", "input")],
    right=[("OUT", "1", "output")],
    top=[("V+", "5", "power_in")],
    bottom=[("V-", "4", "power_in")],
    hw=10.16)


# --- Generic zero-cross comparator ------------------------------------
# NOT A PART, for the same reason OPAMP_GENERIC is not: every specific
# comparator symbol in the installed libraries carries a real pinout, and
# placing one would assert a choice nobody has made.
#
# The requirement this symbol stands for comes out of vr_conditioner.cir,
# and it is unusually relaxed in the places comparators are normally hard:
#
#   SUPPLY          single 3.3 V, taken from 3V3_MCU. The output then
#                   drives PTB2 directly with no level shift.
#   OUTPUT          push-pull, rail-to-rail. The hysteresis network's
#                   window is set by the output swing, so an open-drain
#                   part with an external pull-up would make the window
#                   depend on the pull-up's value and on VOL.
#   INPUT RANGE     mid-rail only. The VR pair is biased to VR_BIAS
#                   (1.65 V) by the front end, so the inputs never
#                   approach either rail -- a common-mode range that
#                   includes ground is NOT required here, which is the
#                   opposite of what a zero-cross comparator usually
#                   needs and is a direct consequence of biasing the
#                   floating sensor coil rather than level-shifting it.
#   PROP DELAY      <= 1 us. At 1500 rpm on a 60-tooth wheel one crank
#                   degree is 111 us, so 1 us is 0.009 crank degrees of
#                   timing error -- far below anything injection timing
#                   resolves.
#   OFFSET          the hysteresis window is +/-198 mV (see the sheet's
#                   own derivation), so input offset voltage and its
#                   tempco are non-issues at this scale: even 10 mV of
#                   offset is 5% of the window.
COMPARATOR = dict(
    name="COMPARATOR_GENERIC", fp="",
    ds="", mpn="",
    desc="GENERIC comparator placeholder -- function only, no part "
         "chosen. Requirement: single 3.3 V supply, PUSH-PULL "
         "rail-to-rail output, mid-rail input common-mode, propagation "
         "delay <=1 us. Pin numbers are placeholders and no footprint is "
         "assigned.",
    keywords="comparator generic placeholder zero-cross hysteresis",
    left=[("IN+", "3", "input"), ("IN-", "2", "input")],
    right=[("OUT", "1", "output")],
    top=[("V+", "5", "power_in")],
    bottom=[("V-", "4", "power_in")],
    hw=10.16)


# --- The 94-way ECU connector ----------------------------------------
# The part number is NOT known. refs/ecu-pinout-extracted.md records the
# connector as 94-pin from GP3.8703.C4.pdf page 4 and nothing more --
# no Bosch part number, no keying, no mating half. So this symbol
# carries pin COUNT and pin NUMBERS, which are facts, and no footprint,
# which would be a guess.
#
# Pin NAMES come from the wiring diagram where it shows the pin and are
# "~" (KiCad's blank) where it does not. 44 of the 94 are shown; the
# diagram is a field-troubleshooting document and explicitly omits
# "power grounds, unused pins and internal-only pins". Naming a pin this
# project has not seen would put a guess in the one place a connector
# symbol must not have one.
CONN94_PINS = {
    "1": "G_G_B_AT1", "2": "G_G_B_AT2", "3": "INJ_HS_A", "4": "V_BAT_1R",
    "5": "INJ_HS_B", "6": "V_BAT_2R", "7": "INJ_LS_CYL3",
    "8": "SGND_RAIL", "9": "SYNC_GND", "11": "EXC_BOOST",
    "15": "EXC_EGR", "20": "AUDIO_ABORT", "21": "BATT_PLUS",
    "23": "SW_DROOP", "24": "OVERRIDE_SS", "29": "INJ_LS_CYL2",
    "30": "SGND_CRANK", "32": "EXC_RAIL", "33": "COOLANT_T",
    "34": "SGND_BOOST_COOLANT", "35": "RAIL_P", "36": "SGND_EGR_OIL",
    "37": "EGR_POS", "39": "EXC_OIL", "41": "BOOST_P", "43": "SW_COOLANT",
    "44": "SGND_CAM", "45": "EXC_CAM", "46": "CAM_FREQ",
    "50": "MAIN_RELAY", "52": "CRANK_HI", "55": "CAN1_H",
    "59": "EGR_HIGH", "69": "BUZZER_RELAY", "71": "IGNITION",
    "73": "INJ_LS_CYL1", "74": "CRANK_LO", "77": "CAN1_L",
    "79": "BOOST_T", "80": "OIL_P", "81": "EGR_LOW", "86": "CAN2_L",
    "87": "CAN2_H", "88": "MU_PWM",
}


def build_conn94(geom):
    left = [(CONN94_PINS.get(str(n), "~"), str(n), "passive")
            for n in range(1, 48)]
    right = [(CONN94_PINS.get(str(n), "~"), str(n), "passive")
             for n in range(48, 95)]
    return simple_symbol(
        name="CONN_ECU_94", fp="", ds="", mpn="",
        desc="94-way ECU harness connector. Pin COUNT and NUMBERS from "
             "GP3.8703.C4.pdf page 4; 44 pin functions from the same "
             "document's wiring diagram. No part number, no footprint -- "
             "neither is known.",
        keywords="connector ECU harness 94-way Bosch",
        left=left, right=right, hw=33.02, geom=geom)


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
    icgeom = {}
    g = {}
    out.append(build_tps3850(g))
    icgeom["TPS3850G33"] = g
    for part in (LM5164, TLV76733, TCAN1042, OPAMP, COMPARATOR):
        g = {}
        out.append(simple_symbol(geom=g, **part))
        icgeom[part["name"]] = g
    g = {}
    out.append(build_conn94(g))
    icgeom["CONN_ECU_94"] = g
    out.append(')')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(out) + "\n")
    with open(LAYOUT, "w") as f:
        json.dump(layout, f, indent=1, sort_keys=True)
    with open(ICPINS, "w") as f:
        json.dump(icgeom, f, indent=1, sort_keys=True)
    print(f"{OUT}: {total} pins in {len(units)} units, plus "
          f"TPS3850G33, LM5164, TLV76733, TCAN1042HGV, OPAMP_GENERIC, "
          f"COMPARATOR_GENERIC, CONN_ECU_94")
    print(f"{LAYOUT}: {len(layout)} pin positions")
    print(f"{ICPINS}: " + ", ".join(f"{k} {len(v)}p"
                                    for k, v in sorted(icgeom.items())))
    for i, (l, r, n) in enumerate(units, start=1):
        print(f"  unit {i}  {n:4} {len(l) + len(r):3} pins")


if __name__ == "__main__":
    main()
