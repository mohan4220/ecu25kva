#!/usr/bin/env python3
"""Build hw/ecu25kva.kicad_pcb, ready for hand routing.

Runs under KiCad's own Python (pcbnew 10):
    KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
    $KP hw/gen_pcb.py              # build the board
    $KP hw/gen_pcb.py --selftest   # the generator's own checks, on a temp copy

The rules (classes, widths, housing placeholders, regions) are in
pcb_rules.py. The board is never regenerated over routing: if the
existing board has a track, only the rules are rewritten (net classes in
the .kicad_pro, the .kicad_dru), unless --force.
"""
import os
import shutil
import sys
import tempfile

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_rules as pr  # noqa: E402

HW = pr.HW
BOARD = os.path.join(HW, "ecu25kva.kicad_pcb")
PRO = os.path.join(HW, "ecu25kva.kicad_pro")


def selftest():
    with tempfile.TemporaryDirectory() as d:
        out, pro = os.path.join(d, "t.kicad_pcb"), os.path.join(d, "t.kicad_pro")
        shutil.copy(PRO, pro)

        def stops(contains, **kw):
            try:
                build(out, pro, **kw)
            except SystemExit as e:
                for s in contains:
                    assert s in str(e), (s, str(e))
                return
            raise AssertionError(f"expected a stop mentioning {contains}")

        # A footprint no library has: stop, naming the part and the name.
        stops(["C101", "NoSuch"], footprints={"C101": "ecu25kva:NoSuch"})
        # A block that cannot fit its region: stop, naming it and the area.
        small = dict(pr.REGIONS, injector=(9.0, 0.5, 19.0, 10.5))
        stops(["injector", "mm2"], regions=small)
        assert not os.path.exists(out), "nothing written on a stop"
        # A routed board is never overwritten without --force.
        build(out, pro)
        b = pcbnew.LoadBoard(out)
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I_MM(30, 30))
        t.SetEnd(pcbnew.VECTOR2I_MM(31, 30))
        b.Add(t)
        pcbnew.SaveBoard(out, b, True)
        before = os.stat(out).st_mtime_ns
        import json
        d = json.load(open(pro))
        d["net_settings"]["classes"] = []
        json.dump(d, open(pro, "w"))
        stops(["track", "--force", "rules updated"])
        assert os.stat(out).st_mtime_ns == before, "routed board touched"
        assert len(json.load(open(pro))["net_settings"]["classes"]) == \
            len(pr.CLASSES), "rules not updated on a routed board"
        build(out, pro, force=True)
        assert len(pcbnew.LoadBoard(out).GetTracks()) == 0
    print("selftest ok")


ORIGIN = (20.0, 20.0)                # board top-left on the page, mm
GAP = 0.5                            # between courtyards, mm
# Parts the schematic leaves without a footprint, until they are known.
PLACEHOLDER = {
    "J1001": "ecu25kva:Bosch_94_PLACEHOLDER",   # header not yet measured
    "D806": "Diode_SMD:D_SMA",                  # waits on the trip-loop pin
}
LIB_DIRS = {"ecu25kva": os.path.join(HW, "lib", "ecu25kva.pretty")}
# Footprints the schematic names that KiCad 10's library dropped,
# copied from KiCad 7.0.11 unchanged.
KICAD7 = os.path.join(HW, "lib", "kicad7.pretty")


def mm(x, y):
    return pcbnew.VECTOR2I_MM(ORIGIN[0] + x, ORIGIN[1] + y)


def load_fp(ref, fpid):
    lib, name = fpid.split(":")
    for d in (LIB_DIRS.get(lib, os.path.join(pr.FOOTPRINT_DIR, lib + ".pretty")),
              KICAD7):
        if os.path.exists(os.path.join(d, name + ".kicad_mod")):
            fp = pcbnew.FootprintLoad(d, name)
            fp.SetFPID(pcbnew.LIB_ID(lib, name))
            return fp
    raise SystemExit(f"{ref}: footprint {fpid} is in no library "
                     f"({pr.FOOTPRINT_DIR}, {LIB_DIRS}, {KICAD7})")


def crtyd(fp):
    fp.BuildCourtyardCaches()
    return fp.GetCourtyard(pcbnew.F_CrtYd).BBox()


def pack(block, fps, region):
    """Shelf-pack footprints into region, tallest first. Stops, naming the
    block and the shortfall, when they cannot fit."""
    x0, y0, x1, y1 = region
    w, h = x1 - x0, y1 - y0
    sized = []
    for fp in fps:
        b = crtyd(fp)
        if b.GetWidth() / 1e6 > w:
            fp.SetOrientationDegrees(90)
            b = crtyd(fp)
        sized.append((b.GetHeight() / 1e6, b.GetWidth() / 1e6, fp))
    need = sum((bw + GAP) * (bh + GAP) for bh, bw, _ in sized)
    if need > w * h:
        raise SystemExit(f"{block}: parts need {need:.0f} mm2, region "
                         f"has {w * h:.0f} mm2 (short {need - w * h:.0f} mm2)")
    x = y = shelf = 0.0
    for bh, bw, fp in sorted(sized, key=lambda s: (-s[0], -s[1])):
        if x + bw > w:
            x, y, shelf = 0.0, y + shelf + GAP, 0.0
        if y + bh > h:
            raise SystemExit(f"{block}: shelf packing overflows its region "
                             f"by {y + bh - h:.1f} mm of height "
                             f"(short {(y + bh - h) * w:.0f} mm2)")
        b = crtyd(fp)
        fp.Move(mm(x0 + x, y0 + y) - b.GetOrigin())
        x += bw + GAP
        shelf = max(shelf, bh)


def shape(board, kind, layer, a, b, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(kind)
    s.SetLayer(layer)
    s.SetWidth(pcbnew.FromMM(width))
    if kind == pcbnew.SHAPE_T_CIRCLE:
        s.SetCenter(a)
        s.SetEnd(b)
    else:
        s.SetStart(a)
        s.SetEnd(b)
    board.Add(s)


def text(board, layer, x, y, msg, size=2.0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(msg)
    t.SetLayer(layer)
    t.SetPosition(mm(x, y))
    t.SetTextSize(pcbnew.VECTOR2I_MM(size, size))
    t.SetTextThickness(pcbnew.FromMM(size * 0.15))
    board.Add(t)


def net_settings(pro):
    import json
    d = json.load(open(pro))
    ns = d.setdefault("net_settings", {})
    tmpl = next((c for c in ns.get("classes", []) if c["name"] == "Default"),
                {})
    classes = []
    for name, c in pr.CLASSES.items():
        e = dict(tmpl, name=name, clearance=c["clearance"],
                 track_width=c["track_width"], via_diameter=c["via_dia"],
                 via_drill=c["via_drill"])
        for k in ("diff_pair_width", "diff_pair_gap"):
            if k in c:
                e[k] = c[k]
        classes.append(e)
    ns["classes"] = classes
    ns["netclass_patterns"] = [{"netclass": c, "pattern": n}
                               for n, c in sorted(pr.ASSIGN.items())]
    with open(pro, "w") as f:
        json.dump(d, f, indent=2)
        f.write("\n")


def write_rules(pro):
    """Net classes into the project file, custom rules beside it."""
    net_settings(pro)
    with open(os.path.splitext(pro)[0] + ".kicad_dru", "w") as f:
        f.write(pr.DRU)


def build(out, pro, regions=None, footprints=None, force=False):
    regions = regions or pr.REGIONS
    if os.path.exists(out) and not force:
        if len(pcbnew.LoadBoard(out).GetTracks()):
            write_rules(pro)
            raise SystemExit(f"{out} has routing (a track or via): rules "
                             "updated, board not touched. Re-run with --force "
                             "to discard the routing and rebuild.")

    with tempfile.TemporaryDirectory() as d:
        comps, nets = pr.read_netlist(pr.export_netlist(d))

    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    board.SetCopperLayerCount(len(pr.STACKUP))
    ds.SetBoardThickness(pcbnew.FromMM(pr.HOUSING["thickness"]))

    pad_net = {}
    for name, nodes in nets.items():
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        for ref, pin, _ in nodes:
            pad_net[(ref, pin)] = ni

    blocks = {}
    for ref in sorted(comps):
        c = comps[ref]
        fpid = (footprints or {}).get(ref) or c["footprint"] or PLACEHOLDER.get(ref)
        if not fpid:
            raise SystemExit(f"{ref}: no footprint in the schematic and none "
                             "in PLACEHOLDER")
        fp = load_fp(ref, fpid)
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        if ref in PLACEHOLDER and not c["footprint"]:
            t = pcbnew.PCB_TEXT(fp)
            t.SetText("PLACEHOLDER")
            t.SetLayer(pcbnew.F_Fab)
            t.SetTextSize(pcbnew.VECTOR2I_MM(0.8, 0.8))
            fp.Add(t)
        nums = set()
        for pad in fp.Pads():
            n = pad.GetNumber()
            nums.add(n)
            if (ref, n) in pad_net:
                pad.SetNet(pad_net[(ref, n)])
        missing = {p for r, p in pad_net if r == ref} - nums
        if missing:
            raise SystemExit(f"{ref}: {fpid} has no pad {sorted(missing)}")
        board.Add(fp)
        blocks.setdefault(c["sheet"], []).append(fp)

    for sheet, fps in sorted(blocks.items()):
        g = pcbnew.PCB_GROUP(board)
        g.SetName(sheet)
        board.Add(g)
        for fp in fps:
            g.AddItem(fp)
        if sheet == "connector":
            x, y, rot = pr.HOUSING["j1001"]
            for fp in fps:
                fp.SetOrientationDegrees(rot)
                fp.SetPosition(mm(x, y))
        elif sheet not in regions:
            raise SystemExit(f"{sheet}: no region in pcb_rules.REGIONS")
        else:
            pack(sheet, fps, regions[sheet])

    w, h = pr.HOUSING["outline"]
    shape(board, pcbnew.SHAPE_T_RECT, pcbnew.Edge_Cuts, mm(0, 0), mm(w, h))
    for x, y, dia in pr.HOUSING["holes"]:
        shape(board, pcbnew.SHAPE_T_CIRCLE, pcbnew.Edge_Cuts, mm(x, y),
              mm(x + dia / 2, y))
    band = pr.HOUSING["contact_band_mm"]
    shape(board, pcbnew.SHAPE_T_RECT, pcbnew.Cmts_User, mm(0, 0), mm(w, band))
    text(board, pcbnew.Cmts_User, w / 2, band - 2,
         "HOUSING CONTACT BAND (PLACEHOLDER, measure)", 1.5)
    x0, y0, x1, y1 = pr.j1001_box()
    text(board, pcbnew.F_SilkS, (x0 + x1) / 2, y0 - 8,
         "PLACEHOLDER OUTLINE AND J1001 - DO NOT FABRICATE", 1.5)

    pcbnew.SaveBoard(out, board, True)
    write_rules(pro)
    print(f"{len(comps)} footprints, {len(nets)} nets, written {out}")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        build(BOARD, PRO, force="--force" in sys.argv)
