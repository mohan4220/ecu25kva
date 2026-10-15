#!/usr/bin/env python3
"""Prototype-only parts added to the built production sheets.

Test points on every rail and scope net, and the BOOST_MON divider. They
are appended after build(), so every production item keeps its text and
UUID, and they sit in a column right of everything already on the page:
nothing added can land on a production wire (the way RESET met WDO).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_sheet_mcu_stm32 import part  # noqa: E402

LOOP = "TestPoint:TestPoint_Keystone_5000-5004_Miniature"
PAD = "TestPoint:TestPoint_Pad_D1.5mm"

# ref -> (sheet, net, footprint)
TEST_POINTS = {f"TP{i}": v for i, v in enumerate([
    ("power_input", "VBAT_PROT", LOOP), ("power_input", "VBAT_INJ", LOOP),
    ("power_input", "VBAT_EGR", LOOP), ("power_input", "12V_GATE", LOOP),
    ("power_input", "5V_MAIN", LOOP), ("power_input", "GND", LOOP),
    ("rails", "3V3_MCU", LOOP), ("rails", "5V_SENSOR_A", LOOP),
    ("rails", "5V_SENSOR_B", LOOP), ("rails", "5V_SENSOR_C", LOOP),
    ("rails", "GND", LOOP),
    ("injector", "BOOST_100V", LOOP), ("injector", "GND", LOOP),
    ("injector", "GND", LOOP),
    ("injector", "ISNS_INJ_A", PAD), ("injector", "ISNS_INJ_B", PAD),
    ("metering_egr", "ISNS_MU", PAD), ("metering_egr", "ISNS_EGR", PAD),
    ("speed_inputs", "CRANK_EDGE", PAD), ("speed_inputs", "CAM_EDGE", PAD),
    ("can", "CAN1_H", PAD), ("can", "CAN1_L", PAD),
    ("can", "CAN2_H", PAD), ("can", "CAN2_L", PAD),
], start=1)}


def _free_x(sh):
    """A column 25.4 mm right of the rightmost thing on the page."""
    xs = [float(x) for it in sh.items
          for x in re.findall(r'\((?:at|xy) ([-\d.]+) [-\d.]+', it)]
    return round((max(xs) + 25.4) / 2.54) * 2.54


def apply(name, sh):
    x, y = _free_x(sh), 30.48
    for ref, (sheet, net, fp) in TEST_POINTS.items():
        if sheet != name:
            continue
        part(sh, "Connector:TestPoint", "TP", x, y,
             "TP HV 100V" if net == "BOOST_100V" else f"TP {net}", fp,
             {"1": net}, ref=ref,
             fields={"Note": "prototype test point (prototype/additions.py)"})
        if fp == PAD:
            # a bare pad is copper, not a part: out of the BOM, as its
            # footprint already says
            i = max(i for i, it in enumerate(sh.items)
                    if it.startswith('  (symbol (lib_id "Connector:TestPoint")'))
            sh.items[i] = sh.items[i].replace("(in_bom yes)", "(in_bom no)", 1)
        y += 15.24
    if name == "injector":
        boost_mon(sh, x, y + 15.24)


def boost_mon(sh, x, y):
    """BOOST_100V -> 2 x 499k -> BOOST_MON -> 24.9k -> GND, 10 nF across.
    Ratio 24.9 / 1022.9 = 0.02434: 116 V reads 2.82 V. Two 1206s share
    the 100 V, 50 V each against a 200 V rating."""
    src = {"Source": "prototype spec sec.3: boost-rail monitor"}
    r = "Resistor_SMD:R_1206_3216Metric"
    part(sh, "Device:R", "R", x, y, "499k", r, {"1": "BOOST_100V", "2": "BOOST_MON_A"}, fields=src)
    part(sh, "Device:R", "R", x, y + 20.32, "499k", r, {"1": "BOOST_MON_A", "2": "BOOST_MON"}, fields=src)
    part(sh, "Device:R", "R", x + 15.24, y + 20.32, "24.9k", "Resistor_SMD:R_0603_1608Metric",
         {"1": "BOOST_MON", "2": "GND"}, fields=src)
    part(sh, "Device:C", "C", x + 30.48, y + 20.32, "10nF", "Capacitor_SMD:C_0603_1608Metric",
         {"1": "BOOST_MON", "2": "GND"}, fields=src)
    sh.wire(x + 45.72, y + 10.16, x + 50.8, y + 10.16)
    sh.label("BOOST_MON", x + 45.72, y + 10.16, rot=180)
    sh.hlabel("BOOST_MON", x + 50.8, y + 10.16, shape="output")
