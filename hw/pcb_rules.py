#!/usr/bin/env python3
"""PCB rules: stack-up, computed track widths, net classes, the net -> class
table, and the housing placeholders. One source for gen_pcb.py (KiCad's
Python 3.9) and check_pcb.py (.venv), so keep it to the 3.9 stdlib.

Every width is computed from a current, never typed. Every number that
depends on the old ECU housing lives in HOUSING and REGIONS; when the
housing is measured, edit those two tables and re-run gen_pcb.py.
"""
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

HW = os.path.dirname(os.path.abspath(__file__))
ROOT_SCH = os.path.join(HW, "ecu25kva.kicad_sch")
KICAD_CLI = shutil.which("kicad-cli") or \
    "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
FOOTPRINT_DIR = os.environ.get(
    "KICAD_FOOTPRINT_DIR",
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")

# ------------------------------------------------------------ stack-up
# 4 layers, 1.6 mm FR-4, Tg >= 170 C (engine bay). L2 is solid ground.
STACKUP = [("F.Cu", 0.070), ("In1.Cu", 0.035), ("In2.Cu", 0.035),
           ("B.Cu", 0.070)]                     # copper thickness, mm
T_RISE, T_AMB = 20.0, 85.0                      # C rise, at C ambient

MIL = 0.0254
MIN_TRACK = 0.15                                # fab minimum, mm


def width_mm(amps, copper_mm, external=True):
    """IPC-2221 track width for T_RISE, rounded up to 0.05 mm, never
    below the fab minimum.

    I = k * dT^0.44 * A^0.725, A in mil^2, k = 0.048 outer / 0.024 inner.
    Used instead of the IPC-2152 charts: closed form, and wider (safer)
    than IPC-2152 at these currents.
    """
    k = 0.048 if external else 0.024
    area = (amps / (k * T_RISE ** 0.44)) ** (1 / 0.725)       # mil^2
    w = area / (copper_mm / MIL) * MIL                        # mm
    return max(MIN_TRACK, round(-(-round(w / 0.05, 6) // 1) * 0.05, 2))


# ------------------------------------------------------------ classes
# Clearances: IPC-2221B table 6-1, external uncoated (B2). The 100 V
# class takes the 101-150 V row; the battery nets (24 V system, clamped
# transients) are held at 0.3 mm.
def _cls(clearance, amps=None, width=None, via=(0.6, 0.3), **kw):
    c = {"clearance": clearance, "via_dia": via[0], "via_drill": via[1]}
    if amps:
        c["amps"] = amps
        c["track_width"] = width_mm(amps, STACKUP[0][1])
    else:
        c["track_width"] = width
    c.update(kw)
    return c


CLASSES = {
    # Injector supply: 18 A peak-phase current.
    "PWR_HI": _cls(0.6, amps=18, via=(0.8, 0.4)),
    # Ground carries the same 18 A back (mostly in the L2 plane), but sits
    # beside every fine-pitch pin, so it keeps the default clearance.
    "GND": _cls(0.15, amps=18, via=(0.8, 0.4)),
    # EGR bridge, metering valve, fused logic supply, regulator trunks.
    "PWR": _cls(0.3, amps=6.4, via=(0.8, 0.4)),
    # The boost rail and everything the injector current crosses at up
    # to 100-116 V: the 18 A peak phase flows here too.
    "HV100": _cls(0.6, amps=18, via=(0.8, 0.4)),
    # Small nets that sit at boost-rail voltage: high-side gates and
    # bootstraps, divider midpoints, the PZTA42 collectors.
    "HV100_SIG": _cls(0.6, width=0.2),
    # 250 kbit/s CAN: width and gap are set from the fab's stack-up for
    # 120 ohm differential; these are the starting values.
    "CAN": _cls(0.2, width=0.2, diff_pair_width=0.2, diff_pair_gap=0.25),
    "ANALOG": _cls(0.2, width=0.25),
    "Default": _cls(0.15, width=0.2),
}

_NETS = {
    "PWR_HI": """/V_BAT_1R /power_input/VBAT_INJ_IN /VBAT_INJ
        Net-(D408-K) Net-(D410-K) /injector/ISNS_INJ_A_SENSE
        /injector/ISNS_INJ_B_SENSE""",
    "GND": "GND",
    "PWR": """/VBAT_IN Net-(F101-Pad2) /power_input/VBAT_EMI1
        /power_input/VBAT_CLAMPED /VBAT_PROT /V_BAT_2R
        /power_input/VBAT_EGR_IN /VBAT_EGR /EGR_HIGH_59 /EGR_LOW_81
        /metering_egr/EGR_ISNS /MU_RETURN /metering_egr/ISNS_MU_SENSE
        /injector/ISNS_BOOST /injector/VDD_BAT /injector/VDD_BOOST
        /rails/SW /rails/VSNS /5V_MAIN /3V3_MCU /12V_GATE /mcu/BULK_RTN""",
    "HV100": """/injector/BOOST_100V /injector/SW_BOOST /INJ_A_03 /INJ_B_05
        /INJ_LS1_73 /INJ_LS2_29 /INJ_LS3_07""",
    "HV100_SIG": """/injector/BOOST_MID /injector/FB_BOOST_MID
        /injector/BIAS_12V_MID /injector/Q1C_MID /injector/Q1C_12V
        /injector/VDD_REF_MID /injector/VDD_REF /injector/VDD_Q1C_MID
        /injector/VDD_Q1C /injector/UA1_VB /injector/UA2_VB
        /injector/UB1_VB /injector/UB2_VB /injector/HSA_BOOST_GATE
        /injector/HSA_BAT_GATE /injector/HSB_BOOST_GATE
        /injector/HSB_BAT_GATE""",
    "CAN": "/CAN1_H /CAN1_L /CAN2_H /CAN2_L",
    "ANALOG": """/BOOST_P_IN /BOOST_T_IN /COOLANT_T_IN /EGR_POS_IN /OIL_P_IN
        /RAIL_P_IN /SGND_34 /SGND_36
        /sensors_analog/BOOST_P_CL /sensors_analog/BOOST_T_CL
        /sensors_analog/COOLANT_T_CL /sensors_analog/EGR_POS_CL
        /sensors_analog/OIL_P_CL /sensors_analog/RAIL_P_CL
        /sensors_analog/V_BAT_1R_SNS_CL /sensors_analog/V_BAT_2R_SNS_CL
        /BOOST_P /BOOST_T /COOLANT_T /EGR_POS /OIL_P /RAIL_P /BARO
        /V_BAT_1R_SNS /V_BAT_2R_SNS /SENSOR_5V_MON
        /ISNS_INJ_A /ISNS_INJ_B /ISNS_MU /ISNS_EGR
        /CRANK_HI_52 /CRANK_LO_74 /speed_inputs/VR_HI_CLAMPED
        /speed_inputs/VR_LO_CLAMPED /speed_inputs/VR_BIAS""",
}
# Exact full net names only: "/VBAT_INJ" never matches "/x/VBAT_INJ".
ASSIGN = {n: c for c, names in _NETS.items() for n in names.split()}


# Custom DRC rules, written next to the board as ecu25kva.kicad_dru.
# Pad-to-pad spacing inside one footprint is the maker's land pattern
# (a 0.5 mm-pitch IC cannot meet a 0.3 mm net-class clearance); the
# classes govern the copper the router adds. KiCad 10 needs the units.
DRU = """(version 1)
(rule "land pattern"
  (condition "A.Type == 'Pad' && B.Type == 'Pad' && A.Parent == B.Parent")
  (constraint clearance (min 0mm)))
"""


def classify(net_names, power_nets):
    """-> (assignment for nets present, unclassified power nets, stale
    ASSIGN names that match no net)."""
    assign = {n: c for n, c in ASSIGN.items() if n in net_names}
    unclassified = sorted(n for n in power_nets if n not in assign)
    stale = sorted(n for n in ASSIGN if n not in net_names)
    return assign, unclassified, stale


# ------------------------------------------------------------ housing
# PLACEHOLDERS until the old ECU is measured (inspection brief, Group 6).
# All mm, board origin top-left, y down. J1001 on the bottom long edge.
#
# The outline is 180 x 130, not the spec's 160 x 120: the 379 parts
# shelf-pack to about 15 300 mm^2 on one side, and 160 x 120 left too
# little room once J1001 and the holes were out (the power-input block
# alone would not fit). The real housing decides: a smaller board means
# parts on both sides.
HOUSING = {
    "outline": (180.0, 130.0),
    "thickness": 1.6,
    "holes": [(4.0, 4.0, 3.2), (176.0, 4.0, 3.2),
              (4.0, 126.0, 3.2), (176.0, 126.0, 3.2)],     # x, y, drill
    "contact_band_mm": 25.0,          # along the edge opposite J1001
    "j1001": (100.5, 120.0, 0.0),     # centre x, y, rotation
    "j1001_size": (77.0, 16.0),       # courtyard of the placeholder
    "ground_pins": ("1", "2"),        # assumed: continuity check open
}
HOLE_KEEPOUT = 2.0                    # around the drill, for the screw head

# Sheet -> (x0, y0, x1, y1). Heat makers in the contact band (top);
# power input left of J1001, logic and I/O around the middle and right.
REGIONS = {
    "injector": (9.0, 0.5, 135.5, 48.0),
    "rails": (135.5, 9.0, 179.5, 41.0),
    "metering_egr": (135.5, 41.0, 179.5, 73.0),
    "power_input": (0.5, 48.0, 61.5, 121.5),
    "mcu": (61.5, 48.0, 101.5, 88.0),
    "sensors_analog": (101.5, 48.0, 135.5, 78.0),
    "speed_inputs": (101.5, 78.0, 135.5, 90.0),
    "discrete_io": (135.5, 73.0, 179.5, 95.0),
    "can": (139.5, 95.0, 179.5, 110.0),
}


def j1001_box():
    x, y, _ = HOUSING["j1001"]
    w, h = HOUSING["j1001_size"]
    return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)


def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# ------------------------------------------------------------ netlist
def export_netlist(tmpdir):
    path = os.path.join(tmpdir, "ecu25kva.xml")
    r = subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format",
                        "kicadxml", "-o", path, ROOT_SCH],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"kicad-cli failed:\n{r.stdout}\n{r.stderr}")
    return path


def read_netlist(path):
    """-> (comps {ref: {value, footprint, sheet}},
           nets {name: [(ref, pin, pinfunction)]})"""
    root = ET.parse(path).getroot()
    comps = {c.get("ref"): {
        "value": c.findtext("value") or "",
        "footprint": c.findtext("footprint") or "",
        "sheet": c.find("sheetpath").get("names").strip("/")}
        for c in root.find("components")}
    nets = {n.get("name"): [(x.get("ref"), x.get("pin"),
                             x.get("pinfunction") or "")
                            for x in n.findall("node")]
            for n in root.find("nets")}
    return comps, nets


# A power part: a power package, an inductor, the fuse, a milliohm shunt.
POWER_FP = re.compile(r"TO-252|TO-263|SMPD|TO-277|D_SMC|^L_|^Fuse")


def power_nets(comps, nets):
    """Nets touching a power part on any pin but a gate."""
    power = {r for r, c in comps.items()
             if POWER_FP.search(c["footprint"].split(":")[-1])
             or (r.startswith("R") and "mOhm" in c["value"])}
    return {n for n, nodes in nets.items()
            if any(ref in power and not fn.startswith("G")
                   for ref, _, fn in nodes)}
