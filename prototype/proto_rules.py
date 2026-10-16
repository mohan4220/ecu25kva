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

# 300 x 200 (owner, 16 Oct: "you can use bigger board dimensions"). With
# corridors kept around every power part for its pour (gen_board.margin),
# 220 x 160 and then 240 x 180 left the injector stage too congested for
# its power nets to route at full class width.
OUTLINE = (300.0, 200.0)
HOLES = [(4.0, 4.0, 3.2), (296.0, 4.0, 3.2),
         (4.0, 196.0, 3.2), (296.0, 196.0, 3.2)]          # x, y, drill (M3)

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
(rule "L2 ground plane"
  (layer In1.Cu)
  (condition "A.NetName == 'GND' || B.NetName == 'GND'")
  (constraint clearance (min 0.2mm)))
(rule "tracks"
  (condition "A.Type == 'Track'")
  (constraint track_width (min 0.2mm)))
(rule "pin necks"
  (condition "A.Type == 'Track' && A.intersectsCourtyard('*')")
  (constraint track_width (min 0.15mm)))
"""
MIN_TRACK_MM = 0.15        # board setup minimum: a pin neck; "tracks" holds the rest at 0.2
# Pin necks (owner, 16 Oct): a track may narrow to 0.15 mm inside a
# part's courtyard, into a fine-pitch pin where 0.2 mm does not clear the
# neighbours; 0.2 mm everywhere else. (KiCad 10 cannot parse a condition
# on a track's length, and drops the whole file silently.) Flag 0.15 mm
# on 2 oz outer copper at quoting.
# L2 is internal copper: IPC-2221B table 6-1 (B1) asks 0.2 mm up to 150 V.
# At the outer-layer 0.6 mm, the rows of 1.1 mm-pitch pour vias cut the
# plane into islands.

# Terminals: ref -> (edge, position along it in mm, from the top or left).
# Right edge holds sensors and speed; switches and CAN go on the bottom
# because J1005-J1007 (142 mm) do not fit between the corner holes.
TERMINALS = {
    "J1001": ("left", 9.0), "J1002": ("left", 35.0), "J1003": ("left", 120.0),
    "J1004": ("top", 150.0),
    "J1005": ("right", 9.0), "J1006": ("right", 90.0),
    "J1008": ("bottom", 185.0), "J1007": ("bottom", 235.0),
}
FIXED = {"J1009": (232.0, 50.0, 0)}          # bridge header: x, y, rotation



# Sheet -> (x0, y0, x1, y1), board mm, y down. Power on the left beside
# its terminals, logic on the right beside its own; each block about 1.5x
# its spaced parts, and a 7 mm apron in front of the left terminals for
# the pours fanning out of them.
REGIONS = {
    "power_input":    (20.0, 1.0, 140.0, 92.0),
    "injector":       (20.0, 100.0, 175.0, 199.0),
    "metering_egr":   (145.0, 15.0, 200.0, 80.0),
    "rails":          (205.0, 1.0, 284.0, 45.0),
    "mcu_stm32":      (180.0, 85.0, 228.0, 140.0),
    "sensors_analog": (240.0, 47.0, 285.0, 88.0),
    "speed_inputs":   (240.0, 90.0, 285.0, 135.0),
    "discrete_io":    (232.0, 140.0, 285.0, 185.0),
    "can":            (180.0, 145.0, 228.0, 185.0),
}

# Critical loops (docs/layout-guide.md), each packed as one tight block
# before the rest of its sheet: seeds, plus every capacitor on the same
# sheet that shares a non-GND net with a seed.
CLUSTERS = {
    # one block per real loop: each bank's low sides, turn-off diodes and
    # shunt together, so a shunt sits beside the FETs it measures
    "bank_a": ("injector", "Q412 Q414 D412 D413 R428"),
    "bank_b": ("injector", "Q416 D414 R429"),
    "boost": ("injector", "U401 Q401 L401 D401 R402 C401 C420"),
    "high_sides": ("injector", "Q408 Q410 D408 D409 D410 D411 "
                   "C409 C411 C413 C415"),
    "buck": ("rails", "U201 L201"),
}
# The feed filters (L103/L104 and their dampers) are not a fast loop and
# were a cluster until 16 Oct; with pour corridors round every member the
# block packed at 1.6x its parts' area, so they pack with the rest.

# Pours (gen_board.pours), owner 16 Oct: POURS CARRY THE CURRENT. Each
# power-class net's power parts are joined by bars at the class width
# along the shortest tree through their pads. Bars go on B.Cu first: all
# parts are on top, so B.Cu has no SMD pads to cut them. A net whose bars
# would lose width to another's takes the next layer (In2 last, at
# double width). GND is the solid In1 (L2) plane.
# Tracks that reach small parts on a power net (dividers, decoupling,
# sense) may be pad-width: they carry no load current, and
# test_power_pours_connect proves it.
import re as _re  # noqa: E402
POWER_PART = _re.compile(r"TO-252|TO-263|SMPD|TO-277|D_SMC|^L_|^Fuse|"
                         r"CP_Elec|PhoenixContact")
POUR_CLASSES = ("PWR_HI", "HV100", "RTN", "PWR_LOOM", "PWR", "PWR_LV")
NECK_MIN = 3            # of 5 points across a bar, filled, all along it
VIA_AMPS = 2.0          # per 0.4 mm via, 25 um plating: conservative
ROUTER_WIDTH_UM = 250   # router stubs on power nets reach small parts only
