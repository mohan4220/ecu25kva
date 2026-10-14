#!/usr/bin/env python3
"""Checks on pcb_rules: computed widths, classes, net assignment, regions.

Run: .venv/bin/python hw/test_pcb_rules.py   (needs kicad-cli on PATH)
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_rules as pr  # noqa: E402


def test_width():
    w = pr.width_mm(18, 0.070)
    assert 4.8 <= w <= 5.8, w
    assert pr.width_mm(18, 0.035, external=False) > 2 * w
    assert pr.width_mm(1, 0.070) >= 0.15
    assert abs(w / 0.05 - round(w / 0.05)) < 1e-9, "rounded to 0.05 mm"


def test_classes():
    assert pr.CLASSES["HV100"]["clearance"] == 0.6
    for name, c in pr.CLASSES.items():
        if c.get("amps"):
            assert c["track_width"] == pr.width_mm(c["amps"], 0.070), name


def test_classify_unclassified():
    _, unclassified, _ = pr.classify({"/X", "/NEW_PWR"}, {"/NEW_PWR"})
    assert "/NEW_PWR" in unclassified


def test_classify_stale():
    assign, _, stale = pr.classify({"/injector/VBAT_INJ"}, set())
    assert "/VBAT_INJ" in stale
    assert "/injector/VBAT_INJ" not in assign


def test_regions_inside_outline():
    w, h = pr.HOUSING["outline"]
    keep = [(x - d / 2 - pr.HOLE_KEEPOUT, y - d / 2 - pr.HOLE_KEEPOUT,
             x + d / 2 + pr.HOLE_KEEPOUT, y + d / 2 + pr.HOLE_KEEPOUT)
            for x, y, d in pr.HOUSING["holes"]]
    keep.append(pr.j1001_box())
    rs = list(pr.REGIONS.items())
    for name, (x0, y0, x1, y1) in rs:
        assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h, name
        for k in keep:
            assert not pr.overlap((x0, y0, x1, y1), k), (name, k)
    for i, (a, ra) in enumerate(rs):
        for b, rb in rs[i + 1:]:
            assert not pr.overlap(ra, rb), (a, b)
    band = pr.HOUSING["contact_band_mm"]
    for name in ("injector", "rails"):
        assert pr.REGIONS[name][1] < band, f"{name} must reach the contact band"


def test_assign_covers_netlist():
    with tempfile.TemporaryDirectory() as d:
        comps, nets = pr.read_netlist(pr.export_netlist(d))
    assert len(comps) == 379, len(comps)
    power = pr.power_nets(comps, nets)
    assert "/VBAT_INJ" in power and "/injector/BOOST_100V" in power
    assert "/injector/HSA_BOOST_GATE" not in power, "a gate is not a power net"
    _, unclassified, stale = pr.classify(set(nets), power)
    assert unclassified == [], unclassified
    assert stale == [], stale


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("pcb_rules ok")
