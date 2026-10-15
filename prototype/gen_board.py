#!/usr/bin/env python3
"""Build prototype/prototype.kicad_pcb: place, route, fab files.

Runs under KiCad's own Python (pcbnew 10):
    KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
    $KP prototype/gen_board.py place

Uses hw/gen_pcb.py's helpers unchanged, with its rules module pointed at
proto_rules (production classes plus the prototype's), the same way
gen_prototype.py points hw/gen_project.py at prototype/.
"""
import math
import os
import sys
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(HERE, "..", "hw"))
import proto_rules as pr  # noqa: E402
import gen_pcb  # noqa: E402

gen_pcb.pr = pr                     # write_rules/net_settings use our tables
mm, crtyd, load_fp = gen_pcb.mm, gen_pcb.crtyd, gen_pcb.load_fp
GAP = gen_pcb.GAP


def bbox_mm(fps):
    bs = [crtyd(fp) for fp in fps]
    x0 = min(b.GetX() for b in bs) / 1e6
    y0 = min(b.GetY() for b in bs) / 1e6
    x1 = max(b.GetRight() for b in bs) / 1e6
    y1 = max(b.GetBottom() for b in bs) / 1e6
    return x0, y0, x1, y1


def move_to(fps, x, y):
    """Move a set of footprints so their courtyard box starts at board (x, y)."""
    x0, y0, _, _ = bbox_mm(fps)
    o = gen_pcb.ORIGIN
    d = pcbnew.VECTOR2I_MM(x + o[0] - x0, y + o[1] - y0)
    for fp in fps:
        fp.Move(d)


def shelf(items, region, name):
    """Shelf-pack items (lists of footprints moved as one) into region,
    tallest first. Stops, naming the block, when they cannot fit."""
    x0, y0, x1, y1 = region
    w, h = x1 - x0, y1 - y0
    sized = []
    for fps in items:
        a, b, c, d = bbox_mm(fps)
        if c - a > w and len(fps) == 1:
            fps[0].SetOrientationDegrees(90)
            a, b, c, d = bbox_mm(fps)
        sized.append((d - b, c - a, fps))
    need = sum((bw + GAP) * (bh + GAP) for bh, bw, _ in sized)
    if need > w * h:
        raise SystemExit(f"{name}: parts need {need:.0f} mm2, region has "
                         f"{w * h:.0f} mm2")
    x = y = row = 0.0
    for bh, bw, fps in sorted(sized, key=lambda s: (-s[0], -s[1])):
        if x + bw > w:
            x, y, row = 0.0, y + row + GAP, 0.0
        if y + bh > h:
            raise SystemExit(f"{name}: overflows its region by "
                             f"{y + bh - h:.1f} mm")
        move_to(fps, x0 + x, y0 + y)
        x += bw + GAP
        row = max(row, bh)


def tight(fps, name):
    """Pack a cluster into the smallest near-square box that holds it."""
    area = sum((b.GetWidth() / 1e6 + GAP) * (b.GetHeight() / 1e6 + GAP)
               for b in map(crtyd, fps))
    widest = max(max(b.GetWidth(), b.GetHeight()) / 1e6
                 for b in map(crtyd, fps))
    side = max(math.sqrt(area), widest + GAP)
    while True:
        try:
            shelf([[fp] for fp in fps], (0, 0, side, side * 3), name)
            if bbox_mm(fps)[3] - bbox_mm(fps)[1] <= side * 1.2:
                return
        except SystemExit:
            pass
        side *= 1.05


def cluster_refs(seeds, sheet, comps, nets):
    s = set(seeds.split())
    out = set(s)
    for n, nodes in nets.items():
        refs = {r for r, _, _ in nodes}
        if n != "GND" and refs & s:
            out |= {r for r in refs if r.startswith("C")
                    and comps[r]["sheet"] == sheet}
    return out


def mcu_core(fp_of, comps, nets):
    """U301 with one 100 nF beside each VDD/VBAT pad, radially outward."""
    u = fp_of["U301"]
    u.SetPosition(pcbnew.VECTOR2I_MM(0, 0))
    caps = sorted(r for r, _, _ in nets["/3V3_MCU"]
                  if comps[r]["sheet"] == "mcu_stm32" and r.startswith("C")
                  and comps[r]["value"] == "100nF")
    vdd = [p for p in u.Pads() if p.GetNetname() == "/3V3_MCU"]
    half = crtyd(u).GetWidth() / 2e6
    placed = [u]
    for cap, pad in zip(caps, sorted(vdd, key=lambda p: int(p.GetNumber()))):
        px, py = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
        c = fp_of[cap]
        if abs(px) > abs(py):
            c.SetOrientationDegrees(0)
            x, y = math.copysign(half + 1.25, px), py
        else:
            c.SetOrientationDegrees(90)
            x, y = px, math.copysign(half + 1.25, py)
        c.SetPosition(pcbnew.VECTOR2I_MM(x, y))
        placed.append(c)
    return placed


def rect_courtyard(fp):
    old = [g for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.F_CrtYd]
    b = old[0].GetBoundingBox()
    for g in old:
        b.Merge(g.GetBoundingBox())
        fp.Remove(g)
    s = pcbnew.PCB_SHAPE(fp)
    s.SetShape(pcbnew.SHAPE_T_RECT)
    s.SetLayer(pcbnew.F_CrtYd)
    s.SetWidth(pcbnew.FromMM(0.05))
    s.SetStart(b.GetOrigin())
    s.SetEnd(b.GetEnd())
    fp.Add(s)


def edge_place(fp, edge, pos):
    """A terminal with its wire entry facing off the board, its courtyard
    flush with the edge, starting `pos` mm along it."""
    out = {"left": (-1, 0), "right": (1, 0), "top": (0, -1), "bottom": (0, 1)}[edge]
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        c = crtyd(fp)
        pads = [p.GetPosition() for p in fp.Pads()]
        px = sum(p.x for p in pads) / len(pads)
        py = sum(p.y for p in pads) / len(pads)
        dx, dy = c.GetCenter().x - px, c.GetCenter().y - py
        score = dx * out[0] + dy * out[1]
        if best is None or score > best[0]:
            best = (score, rot)
    fp.SetOrientationDegrees(best[1])
    W, H = pr.OUTLINE
    x0, y0, x1, y1 = bbox_mm([fp])
    w, h = x1 - x0, y1 - y0
    at = {"left": (0, pos), "right": (W - w, pos),
          "top": (pos, 0), "bottom": (pos, H - h)}[edge]
    move_to([fp], *at)


def place(out=pr.BOARD):
    with tempfile.TemporaryDirectory() as d:
        comps, nets = pr.read_netlist(pr.export_netlist(d, pr.ROOT_SCH))
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(len(pr.STACKUP))
    board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(1.6))
    pad_net = {}
    for name, nodes in nets.items():
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        for ref, pin, _ in nodes:
            pad_net[(ref, pin)] = ni

    fp_of, blocks = {}, {}
    for ref in sorted(comps):
        c = comps[ref]
        fpid = c["footprint"] or pr.PLACEHOLDER.get(ref)
        if not fpid:
            raise SystemExit(f"{ref}: no footprint and none in PLACEHOLDER")
        fp = load_fp(ref, fpid)
        if fpid in pr.RECT_COURTYARD:
            rect_courtyard(fp)
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetPath(pcbnew.KIID_PATH(c["path"]))
        fp.SetSheetname("/" + c["sheet"] + "/")
        fp.SetSheetfile(c["sheet"] + ".kicad_sch")
        for k, v in c["fields"].items():
            fp.SetField(k, v)
            fp.GetField(k).SetVisible(False)
        if ref in pr.PLACEHOLDER and not c["footprint"]:
            t = pcbnew.PCB_TEXT(fp)
            t.SetText("PLACEHOLDER")
            t.SetLayer(pcbnew.F_Fab)
            t.SetTextSize(pcbnew.VECTOR2I_MM(0.8, 0.8))
            fp.Add(t)
        ren = pr.PAD_RENAME.get(ref, {})
        nums = set()
        for pad in fp.Pads():
            if pad.GetNumber() in ren:
                pad.SetNumber(ren[pad.GetNumber()])
            nums.add(pad.GetNumber())
            if (ref, pad.GetNumber()) in pad_net:
                pad.SetNet(pad_net[(ref, pad.GetNumber())])
        missing = {p for r, p in pad_net if r == ref} - nums
        if missing:
            raise SystemExit(f"{ref}: {fpid} has no pad {sorted(missing)}")
        board.Add(fp)
        fp_of[ref] = fp
        blocks.setdefault(c["sheet"], []).append(fp)

    for ref, (edge, pos) in pr.TERMINALS.items():
        edge_place(fp_of[ref], edge, pos)
    for ref, (x, y, rot) in pr.FIXED.items():
        fp_of[ref].SetOrientationDegrees(rot)
        move_to([fp_of[ref]], x, y)

    taken = set(pr.TERMINALS) | set(pr.FIXED)
    items = {s: [] for s in pr.REGIONS}
    core = mcu_core(fp_of, comps, nets)
    items["mcu_stm32"].append(core)
    taken |= {fp.GetReference() for fp in core}
    for name, (sheet, seeds) in pr.CLUSTERS.items():
        refs = sorted(cluster_refs(seeds, sheet, comps, nets) - taken)
        fps = [fp_of[r] for r in refs]
        tight(fps, name)
        items[sheet].append(fps)
        taken |= set(refs)
    for sheet, fps in blocks.items():
        if sheet == "lab_io":
            continue
        items[sheet] += [[fp] for fp in fps
                         if fp.GetReference() not in taken]
    for sheet, its in items.items():
        shelf(its, pr.REGIONS[sheet], sheet)

    for sheet, fps in sorted(blocks.items()):
        g = pcbnew.PCB_GROUP(board)
        g.SetName(sheet)
        board.Add(g)
        for fp in fps:
            g.AddItem(fp)

    W, H = pr.OUTLINE
    gen_pcb.shape(board, pcbnew.SHAPE_T_RECT, pcbnew.Edge_Cuts, mm(0, 0), mm(W, H))
    for x, y, dia in pr.HOLES:
        gen_pcb.shape(board, pcbnew.SHAPE_T_CIRCLE, pcbnew.Edge_Cuts,
                      mm(x, y), mm(x + dia / 2, y))
    gen_pcb.text(board, pcbnew.F_SilkS, W / 2, H - 3,
                 "ECU25kVA PROTOTYPE - STM32G474 - BENCH ONLY", 1.5)
    pcbnew.SaveBoard(out, board, True)
    gen_pcb.write_rules(pr.PRO)
    print(f"{len(comps)} footprints, {len(nets)} nets, placed: {out}")
    return board


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "place"
    {"place": place}[stage]()
