#!/usr/bin/env python3
"""Golden traces from the Python engine model, for the Rust port's tests.

Run once from the repo root, with the repo's .venv:
    .venv/bin/python simulator/tools/golden.py
Writes simulator/crates/plant/tests/golden/*.csv (committed).
"""
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "firmware" / "sim"))
from engine import Engine, RPM  # noqa: E402

OUT = ROOT / "simulator" / "crates" / "plant" / "tests" / "golden"


def run(name, eng, secs, before=None):
    rows, edges, t = [], [], 0
    while t < secs * 1_000_000:
        if before:
            before(eng, t)
        crank, cam = eng.step(t)
        edges += [(x, 0) for x in crank] + [(x, 1) for x in cam]
        t += 20
        if t % 1000 == 0:
            rows.append((t, eng.rpm, eng.rail_bar, eng.theta))
    with open(OUT / f"{name}.csv", "w") as f:
        f.write("t_us,rpm,rail_bar,theta\n")
        f.writelines(f"{a},{b!r},{c!r},{d!r}\n" for a, b, c, d in rows)
    with open(OUT / f"{name}_edges.csv", "w") as f:
        f.write("t_us,is_cam\n")
        f.writelines(f"{a},{b}\n" for a, b in edges)


def held(rpm):
    def f(eng, t):
        eng.omega = rpm * RPM
    return f


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    e = Engine()
    e.starter = True
    run("starter", e, 2.0)

    e = Engine()
    e.load_kw, e.stuck_fuel_mg = 20, 34
    run("held", e, 0.16, held(1500))

    e = Engine()
    e.duty = 0.0
    run("rail_fill", e, 1.0, held(150))

    # free running from 1500 rpm with a fixed injection schedule:
    # cylinder k, occurrence n starts at k*26667 + n*80000 us, 1500 us long,
    # commanded at the first step 10 ms before its start
    e = Engine()
    e.omega, e.duty, e.load_kw = 1500 * RPM, 0.3, 10
    nxt = [0] * 3

    def schedule(eng, t):
        for k in range(3):
            start = k * 26667 + nxt[k] * 80000
            if t >= start - 10000:
                eng.command(k, start, 1500, nxt[k] + 1)
                nxt[k] += 1
    run("free", e, 2.0, schedule)

    # closed loop: the firmware against the model, as run_sil's start scenario
    from run_sil import Sim
    sim = Sim().start(5.0)
    with open(OUT / "closed_start.csv", "w") as f:
        f.write("t_ms,rpm,state,rail_bar\n")
        f.writelines(f"{t // 1000},{r!r},{st},{p!r}\n" for t, r, st, p, *_ in sim.trace)
    print("golden ok")


if __name__ == "__main__":
    main()
