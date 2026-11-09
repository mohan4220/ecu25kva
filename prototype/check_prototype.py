#!/usr/bin/env python3
"""The production netlist gate, run on the prototype with NO open items,
and with production's Bosch power checks pointed at the screw terminals
that carry those pins. Run: .venv/bin/python prototype/check_prototype.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "hw"))
import check_netlist  # noqa: E402

ROOT = os.path.join(HERE, "prototype.kicad_sch")
# Bosch pin -> its terminal position (gen_sheet_lab_io.TERMINALS)
BOSCH_PINS = {"1": ("J1002", "1"), "2": ("J1002", "2"), "4": ("J1001", "2"),
              "21": ("J1007", "6"), "50": ("J1004", "4"), "71": ("J1007", "5")}


def main():
    return check_netlist.main(root=ROOT, expected_open={}, boundary_open={},
                              connector_ref="J1001", bosch_pins=BOSCH_PINS)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except check_netlist.Fail as e:
        print(f"  FAIL  {e}")
        sys.exit(1)
