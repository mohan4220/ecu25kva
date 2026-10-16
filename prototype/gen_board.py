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


SPACED = {}              # power part ref -> margin kept clear around it


def is_power(fp):
    return bool(pr.POWER_PART.search(fp.GetFPID().GetLibItemName().wx_str())
                or (fp.GetReference().startswith("R") and "mOhm" in fp.GetValue()))


def margin(fp):
    """Half the corridor the widest power net on this part's pads needs:
    its class width plus clearance both sides, plus half a grid step."""
    need = [pr.CLASSES[pr.ASSIGN[p.GetNetname()]]["track_width"]
            + 2 * pr.CLASSES[pr.ASSIGN[p.GetNetname()]]["clearance"]
            for p in fp.Pads() if pr.ASSIGN.get(p.GetNetname()) in pr.POUR_CLASSES]
    return max(need, default=0.0) / 2 + 0.25


def bbox_mm(fps):
    """Courtyard box of a group; a power part's grows by its margin, so a
    pour corridor of its widest net fits beside it."""
    xs0, ys0, xs1, ys1 = [], [], [], []
    for fp in fps:
        b = crtyd(fp)
        m = SPACED.get(fp.GetReference(), 0.0)
        xs0.append(b.GetX() / 1e6 - m)
        ys0.append(b.GetY() / 1e6 - m)
        xs1.append(b.GetRight() / 1e6 + m)
        ys1.append(b.GetBottom() / 1e6 + m)
    return min(xs0), min(ys0), max(xs1), max(ys1)


def move_to(fps, x, y):
    """Move a set of footprints so their courtyard box starts at board (x, y)."""
    x0, y0, _, _ = bbox_mm(fps)
    o = gen_pcb.ORIGIN
    d = pcbnew.VECTOR2I_MM(x + o[0] - x0, y + o[1] - y0)
    for fp in fps:
        fp.Move(d)


def shelf(items, region, name):
    """Skyline bottom-left packing of items (lists of footprints moved as
    one) into region: largest first, each where its top lands lowest, a
    single part in whichever orientation lands lower. Stops, naming the
    block and its shortfall, when one does not fit."""
    x0, y0, x1, y1 = region
    W, H = x1 - x0, y1 - y0
    sky = [(0.0, W, 0.0)]                         # (x, width, height)

    def size(fps):
        a, b, c, d = bbox_mm(fps)
        return c - a + GAP, d - b + GAP

    def spot(w):
        best = None
        for i in range(len(sky)):
            x = sky[i][0]
            if x + w > W + 1e-6:
                break
            top, span, j = 0.0, 0.0, i
            while span < w - 1e-6:
                top = max(top, sky[j][2])
                span += sky[j][1]
                j += 1
            if best is None or (top, x) < best[:2]:
                best = (top, x)
        return best

    def lay(x, w, top):
        nonlocal sky
        out = [s for s in sky if s[0] + s[1] <= x + 1e-6]
        out.append((x, w, top))
        for s in sky:
            if s[0] + s[1] > x + w + 1e-6:
                if s[0] < x + w:
                    out.append((x + w, s[0] + s[1] - x - w, s[2]))
                else:
                    out.append(s)
        sky = out

    order = sorted(items, key=lambda f: -(size(f)[0] * size(f)[1]))
    for fps in order:
        tries = [None]
        if len(fps) == 1:
            tries.append(90)
        best = None
        for turn in tries:
            if turn:
                fps[0].SetOrientationDegrees((fps[0].GetOrientationDegrees() + 90) % 360)
            w, h = size(fps)
            s = spot(w)
            if s and (best is None or s[0] + h < best[0]):
                best = (s[0] + h, s[1], turn)
            if turn:
                fps[0].SetOrientationDegrees((fps[0].GetOrientationDegrees() - 90) % 360)
        if best is None or best[0] - GAP > H:
            short = "no width" if best is None else f"{best[0] - GAP - H:.1f} mm"
            if os.environ.get("PACK_DEBUG"):
                for f in order[:10]:
                    print(f"   {size(f)[0]:5.1f} x {size(f)[1]:5.1f}  "
                          f"{[q.GetReference() for q in f][:6]}")
            raise SystemExit(f"{name}: overflows its region by {short}")
        top, x, turn = best
        if turn:
            fps[0].SetOrientationDegrees((fps[0].GetOrientationDegrees() + 90) % 360)
        w, h = size(fps)
        move_to(fps, x0 + x, y0 + top - h)
        lay(x, w, top)


def tight(items, name):
    """Pack items (lists of footprints moved as one) into the smallest
    square found over a sweep of widths."""
    fps = [fp for it in items for fp in it]
    boxes = [bbox_mm(it) for it in items]
    area = sum((c - a + GAP) * (d - b + GAP) for a, b, c, d in boxes)
    widest = max(max(c - a, d - b) for a, b, c, d in boxes) + GAP
    best, side = None, widest
    while side < 3 * math.sqrt(area):
        try:
            shelf(items, (0, 0, side, 10 * side), name)
            a, b, c, d = bbox_mm(fps)
            score = max(c - a, d - b) ** 2          # its enclosing square
            if best is None or score < best[0]:
                best = (score, side)
        except SystemExit:
            pass
        side *= 1.04
    shelf(items, (0, 0, best[1], 10 * best[1]), name)


def satellites(free, anchors, comps, nets):
    """{anchor: [refs]}: each small part in `free` (a resistor, capacitor
    or diode) joins the anchor it shares the most signal with, so it is
    packed beside it, not wherever its size fits. A net's weight is
    1 / (its parts - 1): a direct link counts, a rail barely. A part tied
    only to other small parts follows theirs (a divider chain). `anchors`
    maps each anchor part's ref to its anchor's name."""
    owner = dict(anchors)
    small = {r for r in free if r[0] in "RCD"}
    for _ in range(3):
        for r in sorted(small):
            score = {}
            for n, nodes in nets.items():
                refs = {x for x, _, _ in nodes}
                if n == "GND" or r not in refs or len(refs) < 2:
                    continue
                for x in refs - {r}:
                    if x in owner and comps[x]["sheet"] == comps[r]["sheet"]:
                        score[owner[x]] = score.get(owner[x], 0) + 1 / (len(refs) - 1)
            if score:
                owner[r] = max(sorted(score), key=score.get)
    out = {}
    for r in sorted(small):
        if r in owner:
            out.setdefault(owner[r], []).append(r)
    return out


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
        if is_power(fp) and c["sheet"] != "lab_io":
            SPACED[ref] = margin(fp)
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
    groups = {}                         # anchor name -> (sheet, [items])
    anchors = {}                        # ref -> anchor name
    for name, (sheet, seeds) in pr.CLUSTERS.items():
        refs = sorted(cluster_refs(seeds, sheet, comps, nets) - taken)
        fps = [fp_of[r] for r in refs]
        tight([[fp] for fp in fps], name)
        groups[name] = (sheet, [fps])
        anchors.update({r: name for r in refs})
        taken |= set(refs)
    # every other active part anchors the small parts around it: run 6
    # left a compensation resistor 102 mm from its controller
    for sheet, fps in blocks.items():
        for fp in fps:
            r = fp.GetReference()
            if sheet != "lab_io" and r not in taken and r[0] in "UQ":
                groups[r] = (sheet, [[fp]])
                anchors[r] = r
                taken.add(r)
    free = {fp.GetReference() for sheet, fps in blocks.items() if sheet != "lab_io"
            for fp in fps} - taken
    for name, refs in satellites(free, anchors, comps, nets).items():
        groups[name][1].extend([fp_of[r]] for r in refs)
        taken |= set(refs)
    for name, (sheet, its) in sorted(groups.items()):
        if len(its) > 1:
            tight(its, name)
        items[sheet].append([fp for it in its for fp in it])
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
    write_rules()
    print(f"{len(comps)} footprints, {len(nets)} nets, placed: {out}")
    return board


KICAD_CLI = pr.KICAD_CLI
FREEROUTING = os.path.expanduser("~/opt/freerouting/freerouting-2.4.1.jar")
FREEROUTING_URL = ("https://github.com/freerouting/freerouting/releases/"
                   "download/v2.4.1/freerouting-2.4.1.jar")
FREEROUTING_SHA = "251101c3eeac22d7e7dfcf6796603279e5d1000283eb82d8f093780f7afc6aa9"


def setup():
    """Fetch the pinned Freerouting jar and check its hash."""
    import hashlib
    import urllib.request
    os.makedirs(os.path.dirname(FREEROUTING), exist_ok=True)
    if not os.path.exists(FREEROUTING):
        urllib.request.urlretrieve(FREEROUTING_URL, FREEROUTING)
    got = hashlib.sha256(open(FREEROUTING, "rb").read()).hexdigest()
    if got != FREEROUTING_SHA:
        raise SystemExit(f"{FREEROUTING}: sha256 {got}, want {FREEROUTING_SHA}")
    print(f"freerouting ok: {FREEROUTING}")


def zone(board, net, layer, polys, prio=0, islands=pcbnew.ISLAND_REMOVAL_MODE_NEVER):
    """Pours over the union of `polys` (point lists, board mm): one zone
    per piece, since a KiCad zone saves one outline only. The outlines are
    built in place: a zone given a separate SHAPE_POLY_SET through
    SetOutline() crashes pcbnew on save. Islands are kept by default: a
    run between two layer hops touches only vias."""
    u = pcbnew.SHAPE_POLY_SET()
    for pts in polys:
        u.NewOutline()
        for x, y in pts:
            p = mm(x, y)
            u.Append(p.x, p.y)
    u.Simplify()
    for i in range(u.OutlineCount()):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(board.FindNet(net))
        z.SetAssignedPriority(prio)
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetIslandRemovalMode(islands)
        o = z.Outline()
        o.NewOutline()
        c = u.COutline(i)
        for k in range(c.PointCount()):
            o.Append(c.CPoint(k).x, c.CPoint(k).y)
        for h in range(u.HoleCount(i)):
            o.NewHole(0)
            c = u.CHole(i, h)
            for k in range(c.PointCount()):
                o.Append(c.CPoint(k).x, c.CPoint(k).y, 0, h)
        board.Add(z)


def power_pads(board):
    """{net: [pads]}: the pads of power parts on power-class nets and GND,
    gates excluded, on nets that join two or more power parts."""
    out = {}
    for fp in board.GetFootprints():
        name = fp.GetFPID().GetLibItemName().wx_str()
        if not (pr.POWER_PART.search(name) or (fp.GetReference().startswith("R")
                                               and "mOhm" in fp.GetValue())):
            continue
        for p in fp.Pads():
            n = p.GetNetname()
            if p.GetPinFunction().startswith("G") or not n:
                continue
            if n == "GND" or pr.ASSIGN.get(n) in pr.POUR_CLASSES:
                out.setdefault(n, []).append(p)
    return {n: ps for n, ps in out.items()
            if len({p.GetParentFootprint().GetReference() for p in ps}) > 1}


def _xy(pad):
    o = gen_pcb.ORIGIN
    return pad.GetPosition().x / 1e6 - o[0], pad.GetPosition().y / 1e6 - o[1]


def mst(points):
    """Prim's tree over points: [(i, j)] edges."""
    inside, edges = {0}, []
    while len(inside) < len(points):
        i, j = min(((i, j) for i in inside for j in range(len(points))
                    if j not in inside),
                   key=lambda e: math.dist(points[e[0]], points[e[1]]))
        inside.add(j)
        edges.append((i, j))
    return edges


def seg_dist(a, b, c, d):
    """Shortest distance between segments ab and cd."""
    def pt(p, q, r):
        dx, dy = r[0] - q[0], r[1] - q[1]
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((p[0] - q[0]) * dx + (p[1] - q[1]) * dy) / L))
        return math.dist(p, (q[0] + t * dx, q[1] + t * dy))

    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if (cross(a, b, c) * cross(a, b, d) < 0) and (cross(c, d, a) * cross(c, d, b) < 0):
        return 0.0
    return min(pt(a, c, d), pt(b, c, d), pt(c, a, b), pt(d, a, b))


def bar(p, q, w):
    """Rectangle around segment pq, w wide, reaching w/2 past each end."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L * w / 2, dy / L * w / 2
    nx, ny = -uy, ux
    return [(p[0] - ux + nx, p[1] - uy + ny), (q[0] + ux + nx, q[1] + uy + ny),
            (q[0] + ux - nx, q[1] + uy - ny), (p[0] - ux - nx, p[1] - uy - ny)]


def place_via(board, net, x, y, size, placed):
    """A pour via at (x, y) origin mm, recorded in `placed`; on the board
    unless `board` is None (a dry run)."""
    placed.append((x, y, size, net))
    if board is None:
        return
    o = gen_pcb.ORIGIN
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I_MM(o[0] + x, o[1] + y))
    v.SetWidth(pcbnew.FromMM(size[0]))
    v.SetDrill(pcbnew.FromMM(size[1]))
    v.SetNet(board.FindNet(net))
    board.Add(v)


def via_ok(x, y, size, net, clr, placed, obstacles, bars):
    """A via of `size` (dia, drill) for `net` at (x, y) clears every hole
    by 0.25 mm, and every other net's via, pad and bar by the clearance."""
    dia, drill = size
    for vx, vy, (vd, vdr), vn in placed:
        d = math.hypot(x - vx, y - vy)
        if d < (drill + vdr) / 2 + 0.25 or (vn != net and d < (dia + vd) / 2 + clr):
            return False
    for ob in obstacles:
        b = ob["box"]
        if ob["net"] == net or b[0] > x + 9 or b[2] < x - 9:
            continue
        dx, dy = max(b[0] - x, 0, x - b[2]), max(b[1] - y, 0, y - b[3])
        if math.hypot(dx, dy) < dia / 2 + max(clr, ob["clr"]):
            return False
    return all(n == net or seg_dist((x, y), (x, y), a, b) >= w / 2 + dia / 2 + max(clr, c)
               for n, _, a, b, w, c in bars)


def layers_at(net, x, y, dia, bars):
    """The layers on which one of `net`'s bars covers a via at (x, y)."""
    return {L for n, L, a, b, w, _ in bars
            if n == net and seg_dist((x, y), (x, y), a, b) <= w / 2 - dia / 2 - 0.1}


def pour_vias(board, net, amps, clr, spots, need, placed, obstacles, bars):
    """ceil(amps / VIA_AMPS) vias at the first `spots` (x, y, size) where
    `need(layers)` holds for the layers covering it and nothing else is in
    the way. Returns how many fell short."""
    want = max(1, math.ceil(amps / pr.VIA_AMPS))
    got = 0
    for x, y, size in spots:
        if got == want:
            break
        if need(layers_at(net, x, y, size[0], bars)) and \
                via_ok(x, y, size, net, clr, placed, obstacles, bars):
            place_via(board, net, x, y, size, placed)
            got += 1
    return want - got


def pad_spots(pad, small=(0.6, 0.3), big=(0.8, 0.4)):
    """Via spots inside an SMD pad on a grid, nearest its centre first."""
    if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
        return []
    b = _box(pad)
    size = small if min(b[2] - b[0], b[3] - b[1]) < 1.0 else big
    pitch, edge = size[0] + 0.3, size[0] / 2 + 0.05
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    xs = [cx] if b[2] - b[0] < 2 * edge else \
        [b[0] + edge + i * pitch for i in range(int((b[2] - b[0] - 2 * edge) / pitch) + 1)]
    ys = [cy] if b[3] - b[1] < 2 * edge else \
        [b[1] + edge + j * pitch for j in range(int((b[3] - b[1] - 2 * edge) / pitch) + 1)]
    return sorted(((x, y, size) for x in xs for y in ys),
                  key=lambda s: math.hypot(s[0] - cx, s[1] - cy))


def hop_radius(w, amps):
    """Inradius of a layer hop's via pad: the bar's half-width, or wider
    where the bar is too narrow to hold the vias its current needs."""
    n = max(1, math.ceil(amps / pr.VIA_AMPS))
    d = sorted(math.hypot(s[0], s[1]) for s in hop_spots(0, 0, 2 * math.sqrt(n) * 1.1))
    return max(w / 2, d[n - 1] + 0.4 + 0.1)


def hop_pad(x, y, r):
    """A 16-gon of inradius r round (x, y): a layer hop's via pad."""
    R = r / math.cos(math.pi / 16)
    return [(x + R * math.cos(math.pi * (2 * k + 1) / 16),
             y + R * math.sin(math.pi * (2 * k + 1) / 16)) for k in range(16)]


def hop_spots(x, y, w):
    """0.8/0.4 via spots on a 1.1 mm grid round a layer hop, nearest first."""
    r = int(w / 1.1) + 1
    return sorted(((x + i * 1.1, y + j * 1.1, (0.8, 0.4))
                   for i in range(-r, r + 1) for j in range(-r, r + 1)),
                  key=lambda s: math.hypot(s[0] - x, s[1] - y))


def _box(item):
    o = gen_pcb.ORIGIN
    b = item.GetBoundingBox()
    return [b.GetX() / 1e6 - o[0], b.GetY() / 1e6 - o[1],
            b.GetRight() / 1e6 - o[0], b.GetBottom() / 1e6 - o[1]]


def geometry(board, f_only=(), no_hop=()):
    """What power_router.py needs: every pad as an obstacle, and each power
    net's power pads. A power pad is an obstacle on every layer, because
    the vias that take it to its pour may go anywhere inside it."""
    pp = power_pads(board)
    # keyed by part and pad: SWIG hands out a new wrapper per access, so
    # id() never matches twice
    power = {(p.GetParentFootprint().GetReference(), p.GetNumber())
             for ps in pp.values() for p in ps}

    def clr(net):
        return pr.CLASSES[pr.ASSIGN.get(net, "RTN" if net == "GND" else "Default")]["clearance"]
    obstacles = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if not p.IsOnCopperLayer() and p.GetDrillSize().x == 0:
                continue                         # a paste-only aperture: no copper, no hole
            tht = p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD
            obstacles.append({"net": p.GetNetname(), "box": _box(p),
                              # a bare hole keeps 0.25 mm hole to hole
                              "clr": clr(p.GetNetname()) if p.IsOnCopperLayer() else 0.3,
                              "layers": ["*"] if tht or (fp.GetReference(), p.GetNumber())
                              in power else ["F.Cu"]})
    for x, y, dia in pr.HOLES:
        r = dia / 2 + 0.5
        obstacles.append({"net": "", "box": [x - r, y - r, x + r, y + r],
                          "clr": 0.0, "layers": ["*"]})
    def reach(p, amps, c):
        """A pour reaches an SMD pad off F.Cu only through vias in it: only
        where the pad holds enough of them for the current, each clear of
        every other net's pad."""
        if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            return ["B.Cu", "F.Cu", "In2.Cu"]
        if (p.GetParentFootprint().GetReference(), p.GetNumber()) in f_only:
            return ["F.Cu"]
        ok = [s for s in pad_spots(p) if via_ok(s[0], s[1], s[2], p.GetNetname(), c, [],
                                                 obstacles, [])]
        return ["B.Cu", "F.Cu", "In2.Cu"] if len(ok) >= math.ceil(amps / pr.VIA_AMPS) \
            else ["F.Cu"]
    nets = [{"net": n, "width": pr.CLASSES[pr.ASSIGN[n]]["track_width"],
             "clr": clr(n), "amps": pr.CLASSES[pr.ASSIGN[n]]["amps"],
             "hop_r": hop_radius(pr.CLASSES[pr.ASSIGN[n]]["track_width"],
                                 pr.CLASSES[pr.ASSIGN[n]]["amps"]),
             "pads": [{"xy": list(_xy(p)), "box": _box(p),
                       "layers": reach(p, pr.CLASSES[pr.ASSIGN[n]]["amps"], clr(n))}
                      for p in ps]}
            for n, ps in pp.items() if n != "GND"]
    return {"outline": list(pr.OUTLINE), "obstacles": obstacles, "nets": nets,
            "no_hop": [list(h) for h in no_hop]}


def seg_box(a, b, box):
    """Shortest distance from segment ab to the rectangle `box`."""
    x0, y0, x1, y1 = box
    if any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in (a, b)):
        return 0.0
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    return min(seg_dist(a, b, c, d) for c, d in edges)


GND_VIA, STUB = (0.6, 0.3), 0.25


def gnd_fanout(board, placed, obstacles, bars):
    """A via to the L2 plane for every SMD ground pad that has none: in
    the pad where it is 1.5 mm or more across, else beside it on a short
    F.Cu stub. Each clears every other net's pad, via and pour. Returns
    the stubs, and the pads left without one."""
    o = gen_pcb.ORIGIN
    clr = pr.CLASSES["RTN"]["clearance"]
    stubs, missed = [], []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != "GND" or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD \
                    or not p.IsOnLayer(pcbnew.F_Cu):
                continue
            b = _box(p)
            if any(n == "GND" and b[0] <= x <= b[2] and b[1] <= y <= b[3]
                   for x, y, _, n in placed):
                continue                                 # a pour via is in it
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            w, h = b[2] - b[0], b[3] - b[1]
            spots = [(x, y) for x, y, _ in pad_spots(p, small=GND_VIA, big=GND_VIA)] \
                if min(w, h) >= 1.5 else []
            # a pad over a power bar on an inner or the bottom layer stubs out
            # past it: In2 bars run to 10.7 mm wide
            for d in (0.15, 0.4, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0):
                for k in range(16):
                    dx, dy = math.cos(k * math.pi / 8), math.sin(k * math.pi / 8)
                    r = abs(dx) * w / 2 + abs(dy) * h / 2 + GND_VIA[0] / 2 + d
                    spots.append((cx + dx * r, cy + dy * r))

            def stub_ok(x, y):
                a, e = (cx, cy), (x, y)
                for ob in obstacles:
                    if ob["net"] != "GND" and ob["box"][0] < max(cx, x) + 3 and \
                            ob["box"][2] > min(cx, x) - 3 and \
                            seg_box(a, e, ob["box"]) < STUB / 2 + max(clr, ob["clr"]):
                        return False
                for n, L, s0, s1, bw, bc in bars:
                    if n != "GND" and L == "F.Cu" and \
                            seg_dist(a, e, s0, s1) < bw / 2 + STUB / 2 + max(clr, bc):
                        return False
                return all(n == "GND" or seg_dist(a, e, (vx, vy), (vx, vy)) >= vs[0] / 2 + STUB / 2 + clr
                           for vx, vy, vs, n in placed)
            def track(a, e):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I_MM(o[0] + a[0], o[1] + a[1]))
                t.SetEnd(pcbnew.VECTOR2I_MM(o[0] + e[0], o[1] + e[1]))
                t.SetWidth(pcbnew.FromMM(STUB))
                t.SetLayer(pcbnew.F_Cu)
                t.SetNet(board.FindNet("GND"))
                t.SetLocked(True)
                board.Add(t)
                stubs.append(t)
            for x, y in spots:
                inside = b[0] <= x <= b[2] and b[1] <= y <= b[3]
                if via_ok(x, y, GND_VIA, "GND", clr, placed, obstacles, bars) and \
                        (inside or stub_ok(x, y)):
                    place_via(board, "GND", x, y, GND_VIA, placed)
                    if not inside:
                        track((cx, cy), (x, y))
                    break
            else:
                path = stub_path((cx, cy), b, clr, placed, obstacles, bars)
                if path is None:
                    missed.append(f"{fp.GetReference()}.{p.GetNumber()}")
                    continue
                place_via(board, "GND", *path[-1], GND_VIA, placed)
                for a, e in zip(path, path[1:]):
                    track(a, e)
    return stubs, missed


def stub_path(start, pad, clr, placed, obstacles, bars, step=0.1, reach=8.0):
    """A bent F.Cu ground stub where no straight one fits: breadth-first
    on a `step` grid out to `reach` from the pad, to the nearest spot a
    ground via fits; the path pulled straight where it can go straight."""
    from collections import deque
    x0, y0 = start
    near_ob = [ob for ob in obstacles if ob["net"] != "GND" and
               ob["box"][0] < x0 + reach + 2 and ob["box"][2] > x0 - reach - 2 and
               ob["box"][1] < y0 + reach + 2 and ob["box"][3] > y0 - reach - 2]
    near_bars = [bb for bb in bars if bb[0] != "GND" and bb[1] == "F.Cu" and
                 seg_dist(start, start, bb[2], bb[3]) < reach + bb[4]]
    near_vias = [v for v in placed if v[3] != "GND" and math.dist(start, v[:2]) < reach + 2]

    def free(a, e):
        h = STUB / 2
        return all(seg_box(a, e, ob["box"]) >= h + max(clr, ob["clr"]) for ob in near_ob) and \
            all(seg_dist(a, e, bb[2], bb[3]) >= bb[4] / 2 + h + max(clr, bb[5]) for bb in near_bars) and \
            all(seg_dist(a, e, v[:2], v[:2]) >= v[2][0] / 2 + h + clr for v in near_vias)

    def on_pad(c):
        return pad[0] <= c[0] <= pad[2] and pad[1] <= c[1] <= pad[3]
    n = int(reach / step)
    prev = {(0, 0): None}
    q = deque([(0, 0)])
    while q:
        i, j = q.popleft()
        c = (x0 + i * step, y0 + j * step)
        if not on_pad(c) and via_ok(c[0], c[1], GND_VIA, "GND", clr, placed, obstacles, bars):
            cells = [(i, j)]
            while prev[cells[-1]] is not None:
                cells.append(prev[cells[-1]])
            pts = [(x0 + a * step, y0 + b * step) for a, b in reversed(cells)]
            out, k = [pts[0]], 0
            while k < len(pts) - 1:
                m = len(pts) - 1
                while m > k + 1 and not free(pts[k], pts[m]):
                    m -= 1
                out.append(pts[m])
                k = m
            return out
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            v = (i + di, j + dj)
            if v in prev or abs(v[0]) > n or abs(v[1]) > n:
                continue
            e = (x0 + v[0] * step, y0 + v[1] * step)
            if on_pad(e) or free(c, e):
                prev[v] = (i, j)
                q.append(v)
    return None


def pours(board, routes, dry=False):
    """GND solid on In1 (L2), with vias in the GND power pads. Each routed
    power net: its runs as class-width pours, a via array where it changes
    layer, and vias in its SMD power pads where a pour off F.Cu reaches
    them. Every via joins two layers and clears every other net."""
    W, H = pr.OUTLINE
    obstacles = geometry(board)["obstacles"]
    pp = power_pads(board)
    if dry:
        board = None
    else:
        zone(board, "GND", pcbnew.In1_Cu, [[(0.5, 0.5), (W - 0.5, 0.5),
                                            (W - 0.5, H - 0.5), (0.5, H - 0.5)]])
    bars = [(net, L, tuple(a), tuple(b), w, pr.CLASSES[pr.ASSIGN[net]]["clearance"])
            for net, r in routes.items() for L, a, b, w in r["segs"] if a != b]
    # each layer hop: a round via pad on the two layers it joins, as a
    # zero-length bar its corner radius wide (two MST edges can hop at one spot)
    pads16 = []
    for net, r in routes.items():
        cls = pr.CLASSES[pr.ASSIGN[net]]
        hr = hop_radius(cls["track_width"], cls["amps"])
        for x, y, la, lb in sorted(set(map(tuple, r["hops"]))):
            for L in (la, lb):
                bars.append((net, L, (x, y), (x, y), 2 * hr / math.cos(math.pi / 16),
                             cls["clearance"]))
                pads16.append((net, L, hop_pad(x, y, hr)))
    # a net's runs overlap where they meet, and KiCad wants overlapping
    # zones at distinct priorities: so one zone per net and layer, the
    # union of its runs. Every net at 1, above GND's floods: where two
    # nets meet at their pads, both give way by the clearance
    runs = {}
    for net, L, a, b, w, _ in bars:
        if a != b:
            runs.setdefault((net, L), []).append(bar(a, b, w))
    for net, L, poly in pads16:
        runs.setdefault((net, L), []).append(poly)
    for (net, L), polys in sorted(runs.items()):
        if board is not None:
            zone(board, net, board.GetLayerID(L), polys, prio=1)
    placed, short = [], {}
    gclr = pr.CLASSES["RTN"]["clearance"]
    for p in pp.pop("GND", []):
        pour_vias(board, "GND", pr.CLASSES["RTN"]["amps"], gclr, pad_spots(p),
                  lambda ls: True, placed, obstacles, bars)
    for net, r in sorted(routes.items()):
        cls = pr.CLASSES[pr.ASSIGN[net]]
        for x, y, _, _ in sorted(set(map(tuple, r["hops"]))):
            n = pour_vias(board, net, cls["amps"], cls["clearance"],
                          hop_spots(x, y, 2 * hop_radius(cls["track_width"], cls["amps"])),
                          lambda ls: len(ls) >= 2, placed, obstacles, bars)
            if n:
                short["hop", x, y] = (net, n)
        for p, met in zip(pp[net], r["pad_layers"]):
            # vias where the router met an SMD pad off F.Cu: they take the
            # current (a through-hole pad is on every layer already)
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and set(met) - {"F.Cu"}:
                n = pour_vias(board, net, cls["amps"], cls["clearance"], pad_spots(p),
                              lambda ls: bool(ls - {"F.Cu"}), placed, obstacles, bars)
                if n:
                    short["pad", p.GetParentFootprint().GetReference(), p.GetNumber()] = (net, n)
    if not dry:
        stubs, missed = gnd_fanout(board, placed, obstacles, bars)
        print(f"power pours: {len(routes)} nets, {len(bars)} runs, {len(placed)} vias; "
              f"ground: {len(stubs)} stubs", flush=True)
        if missed:
            raise SystemExit(f"no room for a ground via at {missed}")
    return short


def necks(board, routes=None):
    """{net: layer} for every run that keeps less than NECK_MIN of 5 points
    across its width filled anywhere, outside one bar-width (plus the pad)
    of the net's own power pads, where necking into the part is allowed.
    The runs are the power router's (build/power.json)."""
    import json
    if routes is None:
        routes = json.load(open(os.path.join(HERE, "build", "power.json")))["routes"]
    pads = power_pads(board)
    o = gen_pcb.ORIGIN
    out = {}
    for net, r in sorted(routes.items()):
        boxes = [_box(q) for q in pads.get(net, [])]
        for L, a, b, w in r["segs"]:
            keep = [(q[0] - w, q[1] - w, q[2] + w, q[3] + w) for q in boxes]
            layer = board.GetLayerID(L)
            same = [q.GetFilledPolysList(layer) for q in board.Zones()
                    if q.GetNetname() == net and q.GetLayer() == layer]
            n = max(1, int(math.dist(a, b) / 0.5))
            L_ = math.dist(a, b)
            ux, uy = ((b[0] - a[0]) / L_, (b[1] - a[1]) / L_) if L_ else (0, 0)
            for k in range(n + 1):
                cx, cy = a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n
                if any(q[0] <= cx <= q[2] and q[1] <= cy <= q[3] for q in keep):
                    continue
                hits = sum(any(f.Contains(pcbnew.VECTOR2I(
                    int((o[0] + cx - uy * w * k_) * 1e6), int((o[1] + cy + ux * w * k_) * 1e6)))
                    for f in same) for k_ in (-0.4, -0.2, 0, 0.2, 0.4))
                if hits < pr.NECK_MIN:
                    out[net] = L
                    break
    return out


def write_rules():
    """Production's classes and rules, the prototype's additions, and the
    board setup minimum track lowered to the pin-neck width."""
    import json
    gen_pcb.write_rules(pr.PRO)
    d = json.load(open(pr.PRO))
    d.setdefault("board", {}).setdefault("design_settings", {}) \
        .setdefault("rules", {})["min_track_width"] = pr.MIN_TRACK_MM
    with open(pr.PRO, "w") as f:
        json.dump(d, f, indent=2)
        f.write("\n")


def widen(path, rounds=3):
    """Every track under 0.2 mm (the router narrows into tight pins) goes
    to 0.2 mm; one that then breaks clearance goes back, but to no less
    than the 0.15 mm pin-neck minimum. Returns how many stay narrow."""
    import json
    import subprocess
    lo, hi = pcbnew.FromMM(0.15), pcbnew.FromMM(0.2)
    for _ in range(rounds):
        board = pcbnew.LoadBoard(path)
        was = {}
        for t in board.GetTracks():
            if t.Type() == pcbnew.PCB_TRACE_T and t.GetWidth() < hi:
                was[(t.GetLayer(), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y)] = \
                    t.GetWidth()
                t.SetWidth(hi)
        pcbnew.SaveBoard(path, board, True)
        refill(path)                     # the floods must give way first
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "-o",
                            os.path.join(d, "r.json"), path], capture_output=True)
            rep = json.load(open(os.path.join(d, "r.json")))
        hit = {i["uuid"] for v in rep["violations"] if v["type"] == "clearance"
               for i in v["items"]}
        board = pcbnew.LoadBoard(path)
        back = 0
        for t in board.GetTracks():
            k = (t.GetLayer(), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y)
            if k in was and t.m_Uuid.AsString() in hit:
                t.SetWidth(max(was[k], lo))
                back += 1
        pcbnew.SaveBoard(path, board, True)
        refill(path)
        if not back:
            break
    return back


def refill(path):
    """Fill zones with kicad-cli: pcbnew's ZONE_FILLER needs a GUI app."""
    import subprocess
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run([KICAD_CLI, "pcb", "drc", "--refill-zones",
                            "--save-board", "-o", os.path.join(d, "r.rpt"),
                            path], capture_output=True, text=True)
    if "Saved board" not in r.stdout + r.stderr:
        raise SystemExit(f"refill failed:\n{r.stdout}\n{r.stderr}")


def router_dsn(text):
    """Power nets ride their pours, so in the ROUTER'S input their class
    width drops to ROUTER_WIDTH_UM: the router only reaches the small
    parts on them. The project's classes are unchanged (owner, 16 Oct);
    test_power_pours_connect proves no track carries load current."""
    import re

    def narrow(m):
        names = m.group(1).split(",")
        if names[0] in pr.POUR_CLASSES:
            return re.sub(r"\(width \d+\)", f"(width {pr.ROUTER_WIDTH_UM})",
                          m.group(0))
        return m.group(0)
    text = re.sub(r"\(class (\S+).*?\(rule.*?\)\s*\)", narrow, text, flags=re.S)
    # L2 is the ground plane, never cut. Freerouting routes on a signal
    # layer even under a plane; as a power layer, or a layer switched off,
    # it blocks the vias through it too (623 pins could not fan out), and
    # it overrides per-layer costs. So the router sees no L2 at all: its
    # vias still come back through all four layers (KiCad names them
    # Via[0-3]). Ground reaches L2 through its own vias (gnd_fanout), so
    # it goes in as a one-pin net: its copper stays, nothing to route
    text = re.sub(r"\n\s*\(layer In1\.Cu\b.*?\n    \)", "", text, count=1, flags=re.S)
    text = re.sub(r"\n\s*\(plane GND \(polygon In1\.Cu[^()]*\)\)", "", text)
    text = re.sub(r"\((?:shape|keepout \"\") \((?:circle|rect|path|polygon) In1\.Cu[^()]*\)\)",
                  "", text)
    text = re.sub(r"(\(net GND\s*\(pins\s+)(\S+)[^()]*\)", r"\1\2)", text)
    # Freerouting fills one clearance matrix from the classes in order, so
    # a later class's clearance overwrites an earlier one's against it
    # (run 6: PWR at 0.15 mm, HV100_SIG at 0.34). KiCad keeps the larger
    # of the two: say so for every pair, and 0.2 mm against ground, the
    # L2 plane rule
    cls = dict(re.findall(r"\(class (\S+) .*?\(clearance (\d+)\)", text, flags=re.S))
    gnd = next((c for c in cls if re.search(r"\(class " + re.escape(c) + r"\b[^()]*\sGND\s",
                                                 text)), None)
    names = sorted(cls)
    pairs = "".join(
        f"\n    (class_class (classes {a} {b}) (rule (clearance "
        f"{max(int(cls[a]), int(cls[b]), 200 if gnd in (a, b) else 0)})))"
        for i, a in enumerate(names) for b in names[i:])
    return re.sub(r"\n  \)\n  \(wiring", pairs + "\n  )\n  (wiring", text, count=1)


def pour(path=pr.BOARD):
    """Place afresh, lay the pours and their vias, fill. Starts from
    place() rather than deleting copper: removing zones through pcbnew
    leaves SWIG's type table broken for the zones created after."""
    import json
    import subprocess
    board = place(path)
    work = os.path.join(HERE, "build")
    os.makedirs(work, exist_ok=True)
    gj, rj = os.path.join(work, "geom.json"), os.path.join(work, "power.json")
    venv = os.path.join(HERE, "..", ".venv", "bin", "python")
    # where a pad or a layer hop has no room for the vias its current
    # needs, meet that pad on F.Cu, or hop elsewhere, and route again
    f_only, no_hop = set(), set()
    for attempt in range(6):
        with open(gj, "w") as f:
            json.dump(geometry(board, f_only, no_hop), f)
        subprocess.run([venv, os.path.join(HERE, "power_router.py"), gj, rj])
        res = json.load(open(rj))
        if res["failed"]:
            raise SystemExit(f"power router could not route: {res['failed']}")
        short = pours(board, res["routes"], dry=True)
        print(f"  vias short of 2 A each: {sorted(short.items())}", flush=True)
        if not short:
            break
        f_only |= {k[1:] for k in short if k[0] == "pad"}
        no_hop |= {k[1:] for k in short if k[0] == "hop"}
    else:
        raise SystemExit(f"no room for the vias: {short}")
    pours(board, res["routes"])
    pcbnew.SaveBoard(path, board, True)
    refill(path)
    bad = necks(pcbnew.LoadBoard(path))
    if bad:
        raise SystemExit(f"power pours neck: {bad}")
    return len(res["routes"])


def pour_wires(board, routes):
    """The pours as copper Freerouting must respect: it loads a DSN plane
    as a conduction area that is NO obstacle to other nets. Each run goes
    in as a locked track, which exports as a fixed wire: a 0.4 mm
    centreline the whole way (the power router kept every centreline
    NECK_HALF + clearance clear), and full width outside the necks at the
    net's own pads, where the bar may sit over a neighbour's pad that the
    fill carves around. Returns the tracks, to take out again after."""
    pp = power_pads(board)
    o = gen_pcb.ORIGIN
    out = []

    def add(layer, a, b, w, net):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I_MM(o[0] + a[0], o[1] + a[1]))
        t.SetEnd(pcbnew.VECTOR2I_MM(o[0] + b[0], o[1] + b[1]))
        t.SetWidth(pcbnew.FromMM(w))
        t.SetLayer(board.GetLayerID(layer))
        t.SetNet(board.FindNet(net))
        t.SetLocked(True)
        board.Add(t)
        out.append((layer, round(o[0] + a[0], 4), round(o[1] + a[1], 4),
                    round(o[0] + b[0], 4), round(o[1] + b[1], 4)))
    for net, r in routes.items():
        boxes = [_box(p) for p in pp[net]]
        for layer, a, b, w in r["segs"]:
            L = math.dist(a, b)
            if L == 0:
                continue
            add(layer, a, b, 0.4, net)       # 2 x power_router.NECK_HALF

            def at(t):
                return (a[0] + (b[0] - a[0]) * t / L, a[1] + (b[1] - a[1]) * t / L)

            def neck(t):
                x, y = at(t)
                return any(k[0] - w <= x <= k[2] + w and k[1] - w <= y <= k[3] + w
                           for k in boxes)
            ts = [min(L, i * 0.25) for i in range(int(L / 0.25) + 2)]
            run = None
            for t in ts + [None]:
                if t is not None and not neck(t):
                    run = run or [t, t]
                    run[1] = t
                    continue
                if run:
                    # a round end cap reaches w/2: keep it out of the neck
                    s = run[0] + (w / 2 if run[0] > 0 else 0)
                    e = run[1] - (w / 2 if run[1] < L else 0)
                    if e > s:
                        add(layer, at(s), at(e), w, net)
                run = None
        cls = pr.CLASSES[pr.ASSIGN[net]]
        hr = hop_radius(cls["track_width"], cls["amps"]) / math.cos(math.pi / 16)
        for x, y, la, lb in sorted(set(map(tuple, r["hops"]))):
            for layer in (la, lb):                 # the hop's via pad
                add(layer, (x - 0.01, y), (x + 0.01, y), 2 * hr, net)
    return out


def route(path=pr.BOARD, passes=30, fanout_passes=6):
    """Pour, then Freerouting for everything the pours leave, then refill.
    Fanout stops at fanout_passes: the last run's stuck at 7 or 8 pins
    from pass 4 to its 20th, 15 minutes for nothing."""
    import json
    import subprocess
    n = pour(path)
    board = pcbnew.LoadBoard(path)
    work = os.path.join(HERE, "build")
    os.makedirs(work, exist_ok=True)
    routes = json.load(open(os.path.join(work, "power.json")))["routes"]
    stubs = {(t.GetLayer(), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y):
             (t.GetNetCode(), t.GetWidth()) for t in board.GetTracks()
             if t.Type() == pcbnew.PCB_TRACE_T and t.IsLocked()}      # ground stubs
    wires = set(pour_wires(board, routes))
    vias = {}
    for v in board.GetTracks():
        if v.Type() == pcbnew.PCB_VIA_T:
            v.SetLocked(True)                 # fixed: not the router's to rip up
            vias[(v.GetPosition().x, v.GetPosition().y)] = (
                v.GetNetCode(), v.GetWidth(pcbnew.F_Cu), v.GetDrill())
    dsn, ses = os.path.join(work, "prototype.dsn"), os.path.join(work, "prototype.ses")
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        raise SystemExit("DSN export failed")
    with open(dsn) as f:
        text = router_dsn(f.read())
    with open(dsn, "w") as f:
        f.write(text)
    print(f"{n} pours; routing {dsn}", flush=True)
    # caffeinate: the first attempt took 9 h of wall clock for 12 min of
    # CPU because the machine slept
    subprocess.run(["caffeinate", "-i", "java", "-jar", FREEROUTING,
                    "-de", dsn, "-do", ses, "-mp", str(passes),
                    f"--router.fanout.max_passes={fanout_passes}",
                    # it narrows tracks at pins below 0.2 mm, the 2 oz minimum
                    "--router.automatic_neckdown=false",
                    "--router.neck_width_um=200",
                    # its multi-threaded optimiser "is known to generate
                    # clearance violations" (its own warning), and it starts
                    # from the last pass's board, not the best
                    "--router.optimizer.enabled=false"], check=True)
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise SystemExit("SES import failed")
    # the pour wires were the router's obstacles, not copper: the zones
    # are the copper. Whatever the import kept of them goes, and each pour
    # via is there exactly once
    seen = set()
    for t in list(board.GetTracks()):
        if t.Type() == pcbnew.PCB_VIA_T:
            k = (t.GetPosition().x, t.GetPosition().y)
            if k in vias:
                if k in seen:
                    board.Remove(t)
                seen.add(k)
            continue
        s, e = t.GetStart(), t.GetEnd()
        key = (board.GetLayerName(t.GetLayer()), round(s.x / 1e6, 4), round(s.y / 1e6, 4),
               round(e.x / 1e6, 4), round(e.y / 1e6, 4))
        rev = (key[0], key[3], key[4], key[1], key[2])
        k = (t.GetLayer(), s.x, s.y, e.x, e.y)
        if key in wires or rev in wires or (k in stubs and k in seen):
            board.Remove(t)
        seen.add(k)
    have = {(t.GetLayer(), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y)
            for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T}
    for (L, x0, y0, x1, y1), (net, w) in stubs.items():
        if (L, x0, y0, x1, y1) not in have:
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(x0, y0))
            t.SetEnd(pcbnew.VECTOR2I(x1, y1))
            t.SetWidth(w)
            t.SetLayer(L)
            t.SetNetCode(net)
            t.SetLocked(True)
            board.Add(t)
    # the router saw three layers: a via it made comes back "blind" from
    # F.Cu to B.Cu. It is drilled through all four
    for v in board.GetTracks():
        if v.Type() == pcbnew.PCB_VIA_T and v.GetViaType() != pcbnew.VIATYPE_THROUGH:
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    for (x, y), (net, dia, drill) in vias.items():
        if (x, y) not in seen:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(x, y))
            v.SetWidth(dia)
            v.SetDrill(drill)
            v.SetNetCode(net)
            v.SetLocked(True)
            board.Add(v)
    # ground floods both outer layers once the signals are in, lowest
    # priority, so they take only what is left
    W, H = pr.OUTLINE
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone(board, "GND", layer, [[(0.5, 0.5), (W - 0.5, 0.5),
                                    (W - 0.5, H - 0.5), (0.5, H - 0.5)]], prio=0,
             islands=pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    pcbnew.SaveBoard(path, board, True)
    refill(path)
    write_rules()
    print(f"routed; necks after the signals: {necks(pcbnew.LoadBoard(path)) or 'none'}; "
          f"pin necks kept narrow: {widen(path)}", flush=True)


FAB_LAYERS = ("F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,"
              "B.Silkscreen,F.Paste,B.Paste,Edge.Cuts")


def fab(path=pr.BOARD):
    """Fab-neutral files in prototype/fab/: Gerbers (Protel extensions),
    Excellon drill, a placement CSV and a BOM grouped by part."""
    import subprocess
    out = os.path.join(HERE, "fab")
    gbr = os.path.join(out, "gerbers")
    os.makedirs(gbr, exist_ok=True)
    for cmd in (
            ["pcb", "export", "gerbers", "--layers", FAB_LAYERS,
             "--check-zones", "-o", gbr + os.sep, path],
            ["pcb", "export", "drill", "--format", "excellon",
             "-o", gbr + os.sep, path],
            ["pcb", "export", "pos", "--format", "csv", "--units", "mm",
             "--side", "both", "-o", os.path.join(out, "positions.csv"), path],
            ["sch", "export", "bom", "--fields",
             "Reference,Value,Footprint,MPN,${QUANTITY}",
             "--labels", "Refs,Value,Footprint,MPN,Qty",
             "--group-by", "Value,Footprint,MPN", "--ref-range-delimiter", "",
             "-o", os.path.join(out, "bom.csv"), pr.ROOT_SCH]):
        r = subprocess.run([KICAD_CLI] + cmd, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"kicad-cli {' '.join(cmd[:3])} failed:\n"
                             f"{r.stdout}\n{r.stderr}")
    print(f"fab files in {out}")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "place"
    {"place": place, "pour": pour, "route": route, "setup": setup,
     "fab": fab,
     "necks": lambda: print(necks(pcbnew.LoadBoard(pr.BOARD)) or "no necks"),
     "widen": lambda: (write_rules(),
                       print(f"pin necks kept narrow: {widen(pr.BOARD)}"))}[stage]()
