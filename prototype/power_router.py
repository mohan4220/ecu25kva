#!/usr/bin/env python3
"""Route the power pours: a wide-track maze router for the power nets only.

Owner, 16 Oct: pours carry the current. Each power net's power pads are
joined along its shortest tree by bars at the class width. A path keeps a
corridor of (class width + clearance) clear all the way, narrowing only
within one bar-width of the net's own pads, where every layout necks into
a part's leads anyway.

Nets compete for corridors, so routing is negotiated (PathFinder, as FPGA
and PCB routers do it): every net routes allowing overlap at a price,
cells where nets collide grow dearer each round, and it stops when no two
nets share copper.

Input and output are JSON, so it runs in .venv with numpy while
gen_board.py (KiCad's Python, no numpy) reads and writes the board:
    .venv/bin/python prototype/power_router.py geom.json paths.json
"""
import heapq
import json
import math
import sys

import numpy as np

G = 0.5                      # grid, mm
NECK_HALF = 0.2              # half-width of the neck allowed at own pads
LAYERS = ("B.Cu", "F.Cu", "In2.Cu")
ROUNDS = 40
VIA_COST = 4.0                # a layer hop, in grid steps of track
HOP_ROUND = 1 / math.cos(math.pi / 16)   # a 16-gon's corner over its inradius


def grid_shape(W, H):
    return int(H / G) + 1, int(W / G) + 1


def stamp(a, x0, y0, x1, y1, v=True):
    ny, nx = a.shape
    i0, i1 = max(0, math.floor(y0 / G)), min(ny - 1, math.ceil(y1 / G))
    j0, j1 = max(0, math.floor(x0 / G)), min(nx - 1, math.ceil(x1 / G))
    if i0 <= i1 and j0 <= j1:
        a[i0:i1 + 1, j0:j1 + 1] = v


def stamp_seg(a, p, q, half):
    n = max(1, int(math.dist(p, q) / (G / 2)))
    for k in range(n + 1):
        x = p[0] + (q[0] - p[0]) * k / n
        y = p[1] + (q[1] - p[1]) * k / n
        stamp(a, x - half, y - half, x + half, y + half)


def dilate(a, r):
    """Square max-filter of radius r cells, separable."""
    out = a.copy()
    for axis in (0, 1):
        src = out.copy()
        for s in range(1, r + 1):
            for sh in (s, -s):
                rolled = np.roll(src, sh, axis=axis)
                if axis == 0:
                    if sh > 0:
                        rolled[:sh, :] = 0
                    else:
                        rolled[sh:, :] = 0
                else:
                    if sh > 0:
                        rolled[:, :sh] = 0
                    else:
                        rolled[:, sh:] = 0
                np.maximum(out, rolled, out=out)
    return out


def static_free(geom, n, layer, w):
    """Where net n's centreline may go on layer, ignoring other power nets."""
    W, H = geom["outline"]

    def blocked(half):
        a = np.zeros(grid_shape(W, H), bool)
        for o in geom["obstacles"]:
            if o["net"] == n["net"] or (layer not in o["layers"]
                                        and "*" not in o["layers"]):
                continue
            m = half + max(n["clr"], o["clr"]) + G / 2
            stamp(a, o["box"][0] - m, o["box"][1] - m,
                  o["box"][2] + m, o["box"][3] + m)
        e = half + 0.5
        for box in ((-1, -1, W + 1, e), (-1, H - e, W + 1, H + 1),
                    (-1, -1, e, H + 1), (W - e, -1, W + 1, H + 1)):
            stamp(a, *box)
        return a
    neck = np.zeros(grid_shape(W, H), bool)
    for p in n["pads"]:
        b = p["box"]
        stamp(neck, b[0] - w, b[1] - w, b[2] + w, b[3] + w)
    free = ~blocked(w / 2) | (neck & ~blocked(NECK_HALF))
    for p in n["pads"]:
        free[round(p["xy"][1] / G), round(p["xy"][0] / G)] = True
    # a layer hop's via pad, radius hop_r, needs its whole width clear,
    # and not where a hop found no room for its vias last time
    hop = ~blocked(n["hop_r"] * HOP_ROUND)
    for x, y in geom.get("no_hop", []):
        stamp(hop, x - n["hop_r"], y - n["hop_r"], x + n["hop_r"], y + n["hop_r"], False)
    return free, neck, hop


def astar(free, cost, s, g, hop_cost, hop_ok, s_layers, g_layers):
    """A* over (layer, y, x): eight moves in a layer, or a hop to another
    layer where both are free (a via array, priced hop_cost there). Starts and
    ends on the pads' own layers: a power pad reaches every layer whose
    current its vias carry. A hop's vias pass through EVERY layer, so it
    needs hop_ok there."""
    nl, ny, nx = free.shape
    plane = ny * nx
    fr = free.ravel().tolist()
    hk = hop_ok.ravel().tolist()
    cs = cost.ravel().tolist()
    hc = hop_cost.ravel().tolist()
    gy, gx = g
    goal = {l * plane + gy * nx + gx for l in g_layers}
    dist, prev, h = {}, {}, []
    for l in s_layers:
        u = l * plane + s[0] * nx + s[1]
        if fr[u]:
            dist[u] = 0.0
            heapq.heappush(h, (math.hypot(s[0] - gy, s[1] - gx), u))
    steps = [(-1, -1, 1.414), (-1, 0, 1), (-1, 1, 1.414), (0, -1, 1),
             (0, 1, 1), (1, -1, 1.414), (1, 0, 1), (1, 1, 1.414)]
    while h:
        f, u = heapq.heappop(h)
        l, r = divmod(u, plane)
        uy, ux = divmod(r, nx)
        du = dist[u]
        if f - math.hypot(uy - gy, ux - gx) > du + 1e-9:
            continue
        if u in goal:
            path = [u]
            while u in prev:
                u = prev[u]
                path.append(u)
            out = []
            for v in reversed(path):
                lv, rv = divmod(v, plane)
                out.append((lv, rv // nx, rv % nx))
            return out, du
        moves = [(l, uy + dy, ux + dx, c) for dy, dx, c in steps]
        if hk[r]:
            moves += [(m, uy, ux, hc[r]) for m in range(nl) if m != l]
        for lv, vy, vx, c in moves:
            if 0 <= vy < ny and 0 <= vx < nx:
                v = lv * plane + vy * nx + vx
                if fr[v]:
                    nd = du + c * (cs[v] if lv == l else 1.0)
                    if nd < dist.get(v, 1e18):
                        dist[v] = nd
                        prev[v] = u
                        heapq.heappush(h, (nd + math.hypot(vy - gy, vx - gx), v))
    return None, None


def visible(ok, a, b):
    n = max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 2 + 1
    for k in range(n + 1):
        y = round(a[0] + (b[0] - a[0]) * k / n)
        x = round(a[1] + (b[1] - a[1]) * k / n)
        if not ok[y, x]:
            return False
    return True


def pull(ok, path):
    """String-pull a grid path into the fewest straight runs over `ok`."""
    out, i = [path[0]], 0
    while i < len(path) - 1:
        j = len(path) - 1
        while j > i + 1 and not visible(ok, path[i], path[j]):
            j -= 1
        out.append(path[j])
        i = j
    return out


def mst(points):
    inside, edges = {0}, []
    while len(inside) < len(points):
        i, j = min(((i, j) for i in inside for j in range(len(points))
                    if j not in inside),
                   key=lambda e: math.dist(points[e[0]], points[e[1]]))
        inside.add(j)
        edges.append((i, j))
    return edges


def main(src, dst):
    geom = json.load(open(src))
    W, H = geom["outline"]
    shape = grid_shape(W, H)
    nets = sorted(geom["nets"], key=lambda n: (-n["amps"], n["net"]))
    width = {(n["net"], L): n["width"] * (2.0 if L == "In2.Cu" else 1.0)
             for n in nets for L in LAYERS}
    free, neck, hopfree = {}, {}, {}
    for n in nets:
        for L in LAYERS:
            free[n["net"], L], neck[n["net"], L], hopfree[n["net"], L] = static_free(
                geom, n, L, width[n["net"], L])
    hist = {L: np.zeros(shape) for L in LAYERS}
    foot = {}                       # net -> (layer, footprint map)
    routes = {}
    pres = 1.0
    for rnd in range(ROUNDS):
        for n in nets:
            name = n["net"]
            foot.pop(name, None)
            free3, cost3, over3 = [], [], []
            hop_ok = np.ones(shape, bool)
            hop_over = np.zeros(shape)
            hr = n["hop_r"] * HOP_ROUND
            for L in LAYERS:
                # another net's neck stretch is free to cross only inside
                # this net's own neck: two nets necking into one part
                others = np.zeros(shape, np.int16)
                for o, fl in foot.items():
                    if L in fl:
                        full, nk = fl[L]
                        others += full & ~(nk & neck[name, L])
                over = dilate(others, math.ceil((width[name, L] / 2 + n["clr"] / 2) / G))
                free3.append(free[name, L])
                cost3.append(1.0 + hist[L] + pres * over)
                over3.append(over)
                # a hop's pad is on every layer: it may overlap another
                # net while they negotiate, at a price, like a run
                hop_ok &= hopfree[name, L]
                hop_over = np.maximum(hop_over, hist[L] + pres * dilate(
                    others, math.ceil((hr + n["clr"] / 2) / G)))
            free3, cost3 = np.stack(free3), np.stack(cost3)
            hop_cost = VIA_COST * (1.0 + hop_over)
            cells = [(round(p["xy"][1] / G), round(p["xy"][0] / G)) for p in n["pads"]]
            segs, hops = [], []
            ends = [set() for _ in n["pads"]]       # the layers each pad is met on
            for i, j in mst([p["xy"] for p in n["pads"]]):
                path, c = astar(free3, cost3, cells[i], cells[j], hop_cost, hop_ok,
                                [LAYERS.index(L) for L in n["pads"][i]["layers"]],
                                [LAYERS.index(L) for L in n["pads"][j]["layers"]])
                if path is None:
                    print(f"  {name}: no path on any layer", flush=True)
                    return fail(dst, [name])
                ends[i].add(LAYERS[path[0][0]])
                ends[j].add(LAYERS[path[-1][0]])
                # split into runs per layer; string-pull each run over cells
                # no other net uses, plus the run's own
                runs, cur = [], [path[0]]
                for q in path[1:]:
                    if q[0] != cur[-1][0]:
                        runs.append(cur)
                        hops.append((q[2] * G, q[1] * G, LAYERS[cur[-1][0]], LAYERS[q[0]]))
                        cur = [q]
                    else:
                        cur.append(q)
                runs.append(cur)
                for run in runs:
                    l = run[0][0]
                    if len(run) < 2:
                        continue
                    mask = free3[l] & (over3[l] == 0)
                    for _, y, x in run:
                        mask[y, x] = True
                    pts = [(x * G, y * G) for y, x in pull(mask, [(y, x) for _, y, x in run])]
                    segs += [(LAYERS[l], a, b) for a, b in zip(pts, pts[1:])]
            fl = {}
            for L, a, b in segs:
                m = fl.setdefault(L, np.zeros(shape, bool))
                # one cell under the true half-width: rasterising grows a
                # stamp by up to a cell, and the copper check (necks) after
                # the fill is the real arbiter
                stamp_seg(m, a, b, max(G, width[name, L] / 2 + n["clr"] / 2 - G))
            hopm = np.zeros(shape, bool)
            for x, y, _, _ in hops:                # vias go through every layer
                hw = hr + n["clr"] / 2
                stamp(hopm, x - hw, y - hw, x + hw, y + hw)
            for L in LAYERS:
                fl[L] = fl.get(L, np.zeros(shape, bool)) | hopm
            # each layer's claim, and the part of it that is a neck into
            # the net's own pads (a hop's pad never is)
            foot[name] = {L: (m, m & neck[name, L] & ~hopm) for L, m in fl.items()}
            routes[name] = {"segs": [(L, a, b, width[name, L]) for L, a, b in segs],
                            "hops": hops, "pad_layers": [sorted(e) for e in ends]}
        # who still overlaps whom
        clash = set()
        for L in LAYERS:
            # two claims clash unless every claim there is a neck
            tot = np.zeros(shape, np.int16)
            nks = np.zeros(shape, np.int16)
            for fl in foot.values():
                if L in fl:
                    tot += fl[L][0]
                    nks += fl[L][1]
            hot = (tot > 1) & (nks < tot)
            if hot.any():
                hist[L] += hot * 1.0
                for name, fl in foot.items():
                    if L in fl and (fl[L][0] & hot).any():
                        clash.add(name)
        print(f"  round {rnd + 1}: {len(clash)} nets overlapping", flush=True)
        if not clash:
            break
        pres *= 1.5
    for net, r in sorted(routes.items()):
        layers = sorted({s[0] for s in r["segs"]})
        print(f"  {net:34} {'+'.join(layers):20} {len(r['segs']):3} runs, "
              f"{len(r['hops'])} hops")
    if clash:
        return fail(dst, sorted(clash), routes)
    json.dump({"routes": routes, "failed": []}, open(dst, "w"))
    print(f"power router: {len(routes)} routed")
    return 0


def fail(dst, names, routes=None):
    json.dump({"routes": routes or {}, "failed": names}, open(dst, "w"))
    print(f"power router: failed {names}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
