#!/usr/bin/env python3
"""Route the connections Freerouting leaves open, one at a time.

gen_board.finish() hands over, per open connection, the two ends and every
other net's copper near them, already grown by the clearance plus half the
track (or via) width, so a free grid cell is a legal centreline. This
rasterises that on a fine grid over F.Cu, In2.Cu and B.Cu and finds a path
with power_router's A*, a via where all three layers are free. KiCad's DRC
on the result is the arbiter; gen_board drops anything it rejects.

    .venv/bin/python prototype/finish_router.py jobs.json paths.json
"""
import json
import math
import sys

import numpy as np
from matplotlib.path import Path

import power_router as pw

LAYERS = ("F.Cu", "In2.Cu", "B.Cu")
VIA_COST = 12.0                 # a via, in grid steps of track
VIA_SOFT_COST = 400.0           # one that bites a pour: 20 mm of detour at 0.05


def raster(polys, x0, y0, step, shape):
    """Cells whose centre lies inside any polygon (each a point list)."""
    ny, nx = shape
    xs = x0 + step * np.arange(nx)
    ys = y0 + step * np.arange(ny)
    gx, gy = np.meshgrid(xs, ys)
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    out = np.zeros(ny * nx, bool)
    for poly in polys:
        p = np.asarray(poly)
        lo, hi = p.min(axis=0), p.max(axis=0)
        near = (pts[:, 0] >= lo[0]) & (pts[:, 0] <= hi[0]) & \
               (pts[:, 1] >= lo[1]) & (pts[:, 1] <= hi[1])
        if near.any():
            out[near] |= Path(p).contains_points(pts[near])
    return out.reshape(shape)


def disc(c, r, n=16):
    return [(c[0] + r * math.cos(k * 2 * math.pi / n), c[1] + r * math.sin(k * 2 * math.pi / n))
            for k in range(n)]


def capsule(a, b, r):
    """A segment grown by r: its rectangle and a disc at each end."""
    L = math.dist(a, b) or 1e-9
    nx, ny = -(b[1] - a[1]) / L * r, (b[0] - a[0]) / L * r
    return [[(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny),
             (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)], disc(a, r), disc(b, r)]


def route(job, done=()):
    """`done`: what this pass already laid for other nets, which this
    connection must clear like any other copper. Inside a courtyard the
    track may neck to job["neck"] (the pin-neck rule): there the cells come
    from the obstacles grown for that width."""
    step = job["grid"]
    x0, y0, x1, y1 = job["window"]
    shape = (int((y1 - y0) / step) + 1, int((x1 - x0) / step) + 1)
    w, wn = job["width"], job["neck"]
    tro = {L: list(job["track_obst"][L]) for L in LAYERS}
    trn = {L: list(job["track_obst_neck"][L]) for L in LAYERS}
    vo = list(job["via_obst"])
    for d in done:
        if d["net"] == job["net"]:
            continue
        c = max(d["clr"], job["clr"]) + 0.01
        for L, a, b, dw in d["segs"]:
            tro[L] += capsule(a, b, dw / 2 + c + w / 2)
            trn[L] += capsule(a, b, dw / 2 + c + wn / 2)
            vo += capsule(a, b, dw / 2 + c + 0.3)
        for v in d["vias"]:
            for L in LAYERS:
                tro[L].append(disc(v, 0.3 + c + w / 2))
                trn[L].append(disc(v, 0.3 + c + wn / 2))
            vo.append(disc(v, 0.3 + c + 0.3))
            vo.append(disc(v, 0.15 + 0.25 + 0.15 + 0.01))      # hole to hole
    court = raster(job["courtyards"], x0, y0, step, shape)
    full = np.stack([raster(tro[L], x0, y0, step, shape) for L in LAYERS])
    nk = np.stack([raster(trn[L], x0, y0, step, shape) for L in LAYERS])
    blocked = np.where(court, nk, full)
    via_bad = raster(vo, x0, y0, step, shape)

    def cell(p):
        return (round((p[1] - y0) / step), round((p[0] - x0) / step))
    # a track may start anywhere on an end's own copper, but clear of the
    # rest: next to a 0.3 mm clearance net on a 0.5 mm pitch, only off the
    # pad's centre. Starting off the end point, it needs no join: the
    # cell is on the pad. Freeing 3 x 3 cells round each end, as run 10
    # did, put 4 stubs too close
    joins = []
    for p, area, layers in ((job["a"], job["a_own"], job["a_layers"]),
                            (job["b"], job["b_own"], job["b_layers"])):
        c = cell(p)
        li = [LAYERS.index(L) for L in layers]
        if any(not blocked[i][c] for i in li):
            joins.append((c, True))
            continue
        on = raster(area, x0, y0, step, shape) if area else np.zeros(shape, bool)
        ok = on & ~np.logical_and.reduce([blocked[i] for i in li])
        if ok.any():
            ys, xs = np.nonzero(ok)
            k = np.argmin((ys - c[0]) ** 2 + (xs - c[1]) ** 2)
            joins.append(((int(ys[k]), int(xs[k])), False))
        else:                      # last resort: KiCad's DRC will judge it
            for i in li:
                blocked[i][c] = False
            joins.append((c, True))
    (s, join_a), (g, join_b) = joins
    free = ~blocked
    cost = np.ones(free.shape)
    # via_bad holds every layer's copper grown for a via: a via needs only
    # that, and its two layers free for the track (A* checks those)
    hop_ok = ~via_bad
    # a via that bites a pour: allowed, at the price of a long detour
    hop_cost = np.where(raster(job["via_soft"], x0, y0, step, shape), VIA_SOFT_COST, VIA_COST)
    path, _ = pw.astar(free, cost, s, g, hop_cost, hop_ok,
                       [LAYERS.index(L) for L in job["a_layers"]],
                       [LAYERS.index(L) for L in job["b_layers"]])
    if path is None:
        return None

    def mm(q):
        return (x0 + q[1] * step, y0 + q[0] * step)
    segs, vias, run = [], [], [path[0]]
    for q in path[1:] + [None]:
        if q is not None and q[0] == run[-1][0]:
            run.append(q)
            continue
        if len(run) > 1:
            L = LAYERS[run[0][0]]
            # pull each stretch in or out of a courtyard on its own: only
            # the stretch inside necks, and the step between two stretches
            chunks = [[run[0]]]
            for r in run[1:]:
                if court[r[1], r[2]] == court[chunks[-1][-1][1], chunks[-1][-1][2]]:
                    chunks[-1].append(r)
                else:
                    chunks.append([r])
            prev = None
            for ch in chunks:
                inside = court[ch[0][1], ch[0][2]]
                # pulled over the cells for its own width: a wide stretch
                # pulled over neck cells cut a courtyard corner (run 10)
                ok = ~(nk if inside else full)[ch[0][0]]
                ok[s] = ok[s] or free[ch[0][0]][s]
                ok[g] = ok[g] or free[ch[0][0]][g]
                pts = pw.pull(ok, [(y, x) for _, y, x in ch])
                if prev is not None:
                    segs.append((L, mm(prev), mm(pts[0]), wn))
                segs += [(L, mm(a), mm(b), wn if inside else w) for a, b in zip(pts, pts[1:])]
                prev = pts[-1]
        if q is not None:
            vias.append(mm(q[1:]))
            run = [q]
    # the path ends at the cell centres; join them to the exact ends
    if segs and join_a:
        segs.insert(0, (segs[0][0], tuple(job["a"]), segs[0][1], wn if court[s] else w))
    if segs and join_b:
        segs.append((segs[-1][0], segs[-1][2], tuple(job["b"]), wn if court[g] else w))
    return {"segs": segs, "vias": vias}


def main(src, dst):
    out, done = {}, []
    for job in json.load(open(src)):
        r = route(job, done)
        out[job["id"]] = r
        if r:
            done.append({"net": job["net"], "clr": job["clr"], "width": job["width"], **r})
        print(f"  {job['net']:34} {'routed' if r else 'no path'}", flush=True)
    json.dump(out, open(dst, "w"))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
