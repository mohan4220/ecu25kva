#!/usr/bin/env python3
"""Prototype board rules: production's pcb_rules with the prototype's
outline, regions, terminals and clusters. Keep it to the 3.9 stdlib:
gen_board.py imports it under KiCad's Python, check_pcb under .venv.

Production stack-up, classes, widths and clearances are used unchanged;
the prototype adds one class (USB) and the net names its two new sheets
introduce.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "hw"))
from pcb_rules import *  # noqa: E402,F401,F403
import pcb_rules as _pr  # noqa: E402

ROOT_SCH = os.path.join(HERE, "prototype.kicad_sch")
BOARD = os.path.join(HERE, "prototype.kicad_pcb")
PRO = os.path.join(HERE, "prototype.kicad_pro")

OUTLINE = (220.0, 160.0)
HOLES = [(4.0, 4.0, 3.2), (216.0, 4.0, 3.2),
         (4.0, 156.0, 3.2), (216.0, 156.0, 3.2)]          # x, y, drill (M3)

# USB full speed (12 Mbit/s): edges of several ns on a few cm of track
# are electrically short, so 90 ohm is a target, not a requirement.
# 0.25 / 0.2 on 2 oz L1 over the L2 plane is near it for a ~0.2 mm
# prepreg; the fab's stack-up sets the final numbers.
CLASSES = dict(_pr.CLASSES, USB=_pr._cls(0.15, width=0.25,
                                         diff_pair_width=0.25,
                                         diff_pair_gap=0.2))
# Production's table minus the sheet the prototype replaced, plus the
# prototype's own nets.
ASSIGN = dict({n: c for n, c in _pr.ASSIGN.items()
               if not n.startswith("/mcu/")},
              **{"/mcu_stm32/BULK_RTN": "PWR",
                 "/mcu_stm32/3V3_A": "PWR_LV",
                 "/injector/BOOST_MON_A": "HV100_SIG",
                 "/mcu_stm32/USB_DP": "USB", "/mcu_stm32/USB_DM": "USB"})

# Parity differences that are expected: D806's footprint comes from the
# placeholder map (production open item LOWV-CLAMP), and J302's shield
# pads are renamed (below).
PARITY_OK = {("footprint_symbol_mismatch", "D806")}
PLACEHOLDER = {"D806": "Diode_SMD:D_SMA"}
# KiCad 7's USB-C symbol calls the shield S1; KiCad 10's footprints SH.
PAD_RENAME = {"J302": {"SH": "S1"}}

# Stock footprints whose courtyard KiCad reports as self-intersecting
# (a zero-length segment and a gap at -6, -2.75): redrawn as their
# bounding rectangle, which is larger, so conservative.
RECT_COURTYARD = {"Sensor_Pressure:Freescale_98ARH99066A"}

# Production's rules plus one: a footprint's own holes against its own
# pads are the maker's land pattern too (the USB-C shell pegs).
DRU = _pr.DRU + """(rule "land pattern holes"
  (condition "A.Parent == B.Parent")
  (constraint hole_clearance (min 0mm)))
"""

# Terminals: ref -> (edge, position along it in mm, from the top or left).
# Right edge holds sensors and speed; switches and CAN go on the bottom
# because J1005-J1007 (142 mm) do not fit between the corner holes.
TERMINALS = {
    "J1001": ("left", 9.0), "J1002": ("left", 35.0), "J1003": ("left", 100.0),
    "J1004": ("top", 85.0),
    "J1005": ("right", 9.0), "J1006": ("right", 86.0),
    "J1008": ("bottom", 120.0), "J1007": ("bottom", 160.0),
}
FIXED = {"J1009": (175.0, 58.0, 0)}          # bridge header: x, y, rotation

# Sheet -> (x0, y0, x1, y1), board mm, y down.
REGIONS = {
    "power_input":    (15.0, 1.0, 83.0, 80.0),
    "injector":       (15.0, 82.0, 112.0, 158.0),
    "metering_egr":   (84.0, 15.0, 118.0, 72.0),
    "rails":          (120.0, 1.0, 178.0, 40.0),
    "mcu_stm32":      (120.0, 42.0, 170.0, 95.0),
    "sensors_analog": (180.0, 1.0, 206.0, 84.0),
    "speed_inputs":   (172.0, 86.0, 206.0, 120.0),
    "discrete_io":    (114.0, 97.0, 170.0, 145.0),
    "can":            (172.0, 122.0, 206.0, 145.0),
}

# Critical loops (docs/layout-guide.md), each packed as one tight block
# before the rest of its sheet: seeds, plus every capacitor on the same
# sheet that shares a non-GND net with a seed.
CLUSTERS = {
    "boost_turnoff": ("injector", "U401 Q401 L401 D401 R402 C401 C420 "
                      "D412 D413 D414 Q412 Q414 Q416 R428 R429"),
    "high_sides": ("injector", "Q408 Q410 D408 D409 D410 D411 "
                   "C409 C411 C413 C415"),
    "buck": ("rails", "U201 L201"),
    "feeds": ("power_input", "Q103 Q104 L103 L104 R110 R111 R112 R113 "
              "C113 C114 C117 C118"),
}
