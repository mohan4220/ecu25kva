#!/usr/bin/env python3
"""Regenerating a sheet must not change its UUIDs: the PCB links each
footprint to its symbol by them. Run: .venv/bin/python hw/test_schlib.py"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schlib import Sheet  # noqa: E402


def build(extra_wire):
    sh = Sheet("t", ref_base=100)
    if extra_wire:
        sh.wire(0, 0, 10, 0)
    sh.place("Device:R", "R", 50, 50, "10k")
    sh.wire(50, 40, 50, 30)
    return sh.render()


def sym_uuid(text):
    return re.search(r'\(symbol \(lib_id "Device:R"\).*?\(uuid ([0-9a-f-]+)\)',
                     text, re.S).group(1)


if __name__ == "__main__":
    assert build(False) == build(False), "same sheet, different output"
    # an unrelated edit must not move a symbol's UUID
    assert sym_uuid(build(False)) == sym_uuid(build(True))
    print("schlib ok")
