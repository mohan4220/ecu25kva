#!/usr/bin/env python3
"""The production netlist gate, run on the prototype with NO open items:
the prototype's terminals close production's power-ground and trip-loop
items. Run: .venv/bin/python prototype/check_prototype.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "hw"))
import check_netlist  # noqa: E402

ROOT = os.path.join(HERE, "prototype.kicad_sch")


def main():
    return check_netlist.main(root=ROOT, expected_open={}, boundary_open={},
                              connector_ref="J1001")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except check_netlist.Fail as e:
        print(f"  FAIL  {e}")
        sys.exit(1)
