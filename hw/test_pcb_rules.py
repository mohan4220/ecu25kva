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


def test_gnd_class():
    # Ground sits beside every fine-pitch pin: it keeps the default
    # clearance (a 100 V neighbour still gets 0.6 from its own class).
    assert pr.ASSIGN["GND"] == "RTN"
    assert pr.CLASSES["RTN"]["clearance"] == pr.CLASSES["Default"]["clearance"]


def test_land_pattern_rule():
    # Pads of one footprint are the maker's spacing, not ours to route.
    assert "A.Parent == B.Parent" in pr.DRU and "min 0mm" in pr.DRU


def test_fine_pitch_nets_routable():
    # Nets that land on 0.5 mm-pitch / LQFP pins: a 0.3-0.6 mm class
    # clearance would make the first track into the pin a DRC error.
    for n in ("/3V3_MCU", "/5V_MAIN", "/injector/VDD_BOOST",
              "/injector/ISNS_BOOST", "/injector/ISNS_INJ_A_SENSE",
              "/injector/ISNS_INJ_B_SENSE"):
        assert pr.CLASSES[pr.ASSIGN[n]]["clearance"] == 0.15, n


def test_loom_fused_feeds():
    # Pins 4 and 6 have only the 10 A loom fuse (decisions log 5): their
    # copper must carry what that fuse lets through, not just the load.
    for n in ("/V_BAT_1R", "/power_input/VBAT_INJ_IN", "/VBAT_INJ",
              "/V_BAT_2R", "/power_input/VBAT_EGR_IN", "/VBAT_EGR",
              "/EGR_HIGH_59", "/EGR_LOW_81", "/metering_egr/EGR_ISNS"):
        assert pr.CLASSES[pr.ASSIGN[n]]["amps"] >= pr.LOOM_FUSE_A, n


def test_egr_high_side_at_40v():
    # VBAT + 12 V reaches 52 V on a load dump: IPC-2221B B2 asks 0.6 mm from 31 V.
    for n in ("/metering_egr/EGR_AH_G", "/metering_egr/EGR_BH_G",
              "/metering_egr/EGR_A_VB", "/metering_egr/EGR_B_VB"):
        assert pr.CLASSES[pr.ASSIGN.get(n, "Default")]["clearance"] == 0.6, n


def test_kicad_name():
    refs = {"U301", "U201", "D408"}
    assert pr.kicad_name("unconnected-(U301A-PTA8-Pad144)", refs) == \
        "unconnected-(U301-PTA8-Pad144)"
    assert pr.kicad_name("Net-(U201-EN/UVLO)", refs) == "Net-(U201-EN{slash}UVLO)"
    assert pr.kicad_name("Net-(D408-K)", refs) == "Net-(D408-K)"
    assert pr.kicad_name("/injector/SW_BOOST", refs) == "/injector/SW_BOOST"


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
    for name in ("injector", "metering_egr"):
        assert pr.REGIONS[name][1] < band, f"{name} must reach the contact band"


def test_assign_covers_netlist():
    with tempfile.TemporaryDirectory() as d:
        comps, nets = pr.read_netlist(pr.export_netlist(d))
    assert len(comps) == 380, len(comps)      # 379 + D302 (19 Oct)
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
