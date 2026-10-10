#!/usr/bin/env python3
"""Software-in-the-loop: the firmware core against the engine model.

Each scenario is a claim from the spec (section 7) that must hold.

    .venv/bin/python firmware/sim/run_sil.py           # run all
    .venv/bin/python firmware/sim/run_sil.py runaway   # run matching scenarios
"""
import pathlib
import statistics
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "sim"))
subprocess.run(["make", "-s", "-C", str(HERE)], check=True)

from ecu import Ecu, RUN, SHUTDOWN, NCYL  # noqa: E402
from engine import Engine  # noqa: E402
from run_sim import Checks, PASS, FAIL  # noqa: E402

S = 1_000_000                        # us per second
EEC1, ET1, EFLP1, DM1 = 0xF004, 0xFEEE, 0xFEEF, 0xFECA


def pgn(can_id):
    return can_id >> 8 & 0xFFFF


def dtcs(data):
    """(spn, fmi) pairs in a single-frame DM1; the all-zero DTC means none."""
    out = []
    for i in range(2, len(data) - 3, 4):
        spn = data[i] | data[i + 1] << 8 | (data[i + 2] & 0xE0) << 11
        if spn:
            out.append((spn, data[i + 2] & 0x1F))
    return out


class Sim:
    def __init__(self, droop=False):
        self.eng = Engine()
        self.ecu = Ecu()
        self.ecu.init()
        self.io = self.ecu.io
        self.io.ignition = 1
        self.io.droop_sw = int(droop)
        self.t = 0
        self.next_ms = 1000
        self.can = []                # (t_us, pgn, data)
        self.trace = []              # (t_us, engine rpm, state, rail bar, duty, wdg)
        self.states = []             # (t_us, new state, ecu rpm)
        self.edges = 0
        self.sync_edge = None
        self.over_edge = None        # (t_us, state) at the first edge the ECU read > 1650 rpm
        self.seq_log = []            # (t_us, cyl, seq)
        self._sent = [0] * NCYL
        self._state = self.io.state
        self._volts()

    def _volts(self):
        for k, v in self.eng.volts().items():
            setattr(self.io, k, v)

    def _after(self, t):
        io = self.io
        for k in range(NCYL):
            inj = io.inj[k]
            if inj.seq != self._sent[k]:            # seq alone, as a timer driver would
                if inj.dur_us:
                    self.seq_log.append((t, k, inj.seq))
                self._sent[k] = inj.seq
                self.eng.command(k, inj.start_us, inj.dur_us, inj.seq)
        if io.state != self._state:
            self._state = io.state
            self.states.append((t, io.state, io.rpm))

    def run(self, until_s, each_ms=None):
        until = int(until_s * S)
        while self.t < until:
            crank, cam = self.eng.step(self.t)
            for te, is_cam in sorted([(x, 0) for x in crank] + [(x, 1) for x in cam]):
                if is_cam:
                    self.ecu.cam_edge(te)
                else:
                    self.ecu.crank_edge(te)
                    self.edges += 1
                    if self.sync_edge is None and self.io.synced:
                        self.sync_edge = self.edges
                    if self.over_edge is None and self.io.rpm > 1650:
                        self.over_edge = (te, self.io.state)
                self._after(te)
            self.eng.duty = self.io.meter_duty
            self.t += 20
            if self.t >= self.next_ms:
                self._volts()
                self.ecu.tick(self.next_ms)
                for cid, data in self.ecu.drain_can():
                    self.can.append((self.next_ms, pgn(cid), data))
                self._after(self.next_ms)
                self.trace.append((self.next_ms, self.eng.rpm, self.io.state,
                                   self.eng.rail_bar, self.io.meter_duty, self.io.wdg))
                if each_ms:
                    each_ms(self)
                self.next_ms += 1000
        return self

    def start(self, settle_s=8.0):
        """Crank until RUN, then run on to settle_s."""
        self.eng.starter = True

        def release(sim):
            if sim.io.state == RUN:
                sim.eng.starter = False
        return self.run(settle_s, release)

    def mean_rpm(self, t0_s, t1_s):
        return statistics.mean(r for t, r, *_ in self.trace if t0_s * S <= t < t1_s * S)

    def trip(self, after_s=0.0):
        """(t_us, ecu rpm) of the first SHUTDOWN after after_s, else None."""
        return next(((t, r) for t, st, r in self.states
                     if st == SHUTDOWN and t >= after_s * S), None)

    def dm1_after(self, t_us):
        return [(t, dtcs(d)) for t, p, d in self.can if p == DM1 and t >= t_us]


# ---- scenarios ------------------------------------------------------------

def start():
    c = Checks("1  start: sync, then 1500 rpm")
    sim = Sim().start(5.0)
    c.that("crank edges to sync (2 revs + 2)", sim.sync_edge or 999, 118,
           ok=(sim.sync_edge or 999) <= 118)
    c.that("speed at 5 s, rpm", sim.mean_rpm(4.9, 5.0), 1500, tol=15, unit="rpm")
    peak = max(r for t, r, *_ in sim.trace)
    c.that("start overshoot, rpm (50 below the trip)", peak, 1600, ok=peak < 1600, unit="rpm")
    c.that("never shut down", "ok" if sim.trip() is None else "tripped", 0,
           ok=sim.trip() is None)
    return c


def load_step():
    c = Checks("2  load step 0 -> 20 kW")
    sim = Sim().start(8.0)
    sim.eng.load_kw = 20
    sim.run(13.0)
    c.that("lowest speed, rpm", min(r for t, r, *_ in sim.trace if t >= 8 * S), 1350,
           ok=min(r for t, r, *_ in sim.trace if t >= 8 * S) > 1350, unit="rpm")
    c.that("speed 5 s after, rpm", sim.mean_rpm(12.9, 13.0), 1500, tol=15, unit="rpm")
    return c


def load_reject():
    c = Checks("3  load rejection 20 -> 0 kW")
    sim = Sim().start(5.0)
    sim.eng.load_kw = 20
    sim.run(12.0)
    sim.eng.load_kw = 0
    sim.run(17.0)
    peak = max(r for t, r, *_ in sim.trace if t >= 12 * S)
    c.that("highest speed, rpm (trip 1650)", peak, 1650, ok=peak < 1650, unit="rpm")
    c.that("never shut down", "ok" if sim.trip() is None else "tripped", 0,
           ok=sim.trip() is None)
    return c


def droop():
    c = Checks("4  droop switch: 4 % from no load to full load")
    sim = Sim(droop=True).start(10.0)
    n0 = sim.mean_rpm(9.0, 10.0)
    sim.eng.load_kw = 20
    sim.run(18.0)
    n20 = sim.mean_rpm(17.0, 18.0)
    c.that("speed fall, fraction of 1500", (n0 - n20) / 1500, 0.04, tol=0.01)
    return c


def runaway():
    c = Checks("5  runaway (stuck fuel): trip at 1650 rpm")
    sim = Sim().start(6.0)
    sim.eng.stuck_fuel_mg = 80
    sim.run(7.0)
    tr, over = sim.trip(6.0), sim.over_edge
    c.that("tripped", "yes" if tr else "no", 0, ok=tr is not None)
    c.that("ECU read > 1650 rpm on some edge", "yes" if over else "no", 0, ok=over is not None)
    if tr and over:
        # on that very edge, not at the next 1 ms tick
        c.that("SHUTDOWN on the first edge above 1650", over[1], SHUTDOWN, ok=over[1] == SHUTDOWN)
        late = [s for s in sim.seq_log if s[0] >= over[0]]
        c.that("injection commands from that edge on", len(late), 0, ok=not late)
        c.that("pending commands cancelled", sum(i.dur_us for i in sim.io.inj), 0,
               ok=all(i.dur_us == 0 for i in sim.io.inj))
        at = [p for t, r, st, p, *_ in sim.trace if t >= tr[0]]
        c.that("rail after trip never above rail at trip, bar", max(at) - at[0], 0,
               ok=max(at) <= at[0], unit="bar")
        got = [d for t, d in sim.dm1_after(tr[0]) if (190, 0) in d]
        c.that("DM1 carries SPN 190 FMI 0", "yes" if got else "no", 0, ok=bool(got))
    return c


def crank_loss():
    c = Checks("6  crank signal lost while running")
    sim = Sim().start(6.0)
    sim.eng.crank_lost = True
    sim.run(7.5)
    tr = sim.trip(6.0)
    c.that("tripped", "yes" if tr else "no", 0, ok=tr is not None)
    if tr:
        c.that("time to SHUTDOWN, ms", (tr[0] - 6 * S) / 1000, 100,
               ok=tr[0] - 6 * S <= 100_000, unit="ms")
        got = [d for t, d in sim.dm1_after(tr[0]) if any(s == 636 for s, f in d)]
        c.that("DM1 carries SPN 636", "yes" if got else "no", 0, ok=bool(got))
    return c


def ignition_off():
    c = Checks("7  ignition off: stop, no fault")
    sim = Sim().start(6.0)
    sim.io.ignition = 0
    sim.run(36.0)
    tr = sim.trip(6.0)
    c.that("SHUTDOWN", "yes" if tr else "no", 0, ok=tr is not None)
    dm = sim.dm1_after(6 * S + 1)
    c.that("DM1 after stop shows no DTC", str(dm[:1]), 0, ok=bool(dm) and all(not d for t, d in dm))
    stop = next((t for t, r, *_ in sim.trace if t > 6 * S and r < 50), None)
    c.that("engine below 50 rpm, s after stop", ((stop or 99 * S) - 6 * S) / S, 30,
           ok=stop is not None, unit="s")
    return c


def sensor_open():
    c = Checks("8  coolant sensor open circuit")
    sim = Sim().start(6.0)
    sim.eng.clt_open = True
    sim.run(9.0)
    got = next((t for t, d in sim.dm1_after(6 * S) if (110, 3) in d), None)
    c.that("DM1 SPN 110 FMI 3 within, s", ((got or 99 * S) - 6 * S) / S, 1.2,
           ok=got is not None and got - 6 * S <= 1.2 * S, unit="s")
    c.that("engine still running", sim.io.state, RUN, ok=sim.io.state == RUN)
    return c


def can_content():
    c = Checks("9  CAN content and rates")
    sim = Sim().start(6.0)
    sim.run(8.0)
    log = [(t, p, d) for t, p, d in sim.can if t >= 6 * S]
    rpm_at = {t: r for t, r, *_ in sim.trace}

    def gaps(p):
        ts = [t for t, q, d in log if q == p]
        return [(b - a) / 1000 for a, b in zip(ts, ts[1:])]
    for p, name, ms in ((EEC1, "EEC1", 20), (ET1, "ET1", 1000), (EFLP1, "EFL/P1", 500), (DM1, "DM1", 1000)):
        g = gaps(p)
        worst = max((abs(x - ms) for x in g), default=99)
        c.that(f"{name} interval error, worst, ms", worst, 0, ok=bool(g) and worst <= 2, unit="ms")
    err = max(abs((d[3] | d[4] << 8) * 0.125 / rpm_at[t] - 1) for t, p, d in log if p == EEC1)
    c.that("EEC1 speed vs engine, worst fraction", err, 0, ok=err <= 0.005)
    return c


def rail():
    c = Checks("10 rail pressure within 5 % in steady running")
    sim = Sim().start(8.0)
    lo0 = [p for t, r, st, p, *_ in sim.trace if 6 * S <= t < 8 * S]
    sim.eng.load_kw = 20
    sim.run(16.0)
    lo20 = [p for t, r, st, p, *_ in sim.trace if 14 * S <= t < 16 * S]
    for name, xs in (("0 kW", lo0), ("20 kW", lo20)):
        worst = max(abs(x / 1000 - 1) for x in xs)
        c.that(f"{name}: worst deviation, fraction", worst, 0.05, ok=worst <= 0.05)
    return c


def watchdog():
    c = Checks("11 watchdog kick inside the 5-20 ms window")
    sim = Sim().start(8.0)
    sim.eng.load_kw = 20
    sim.run(13.0)
    falls = [t for (t, *_, w), (t0, *_, w0) in zip(sim.trace[1:], sim.trace) if w0 and not w]
    per = [(b - a) / 1000 for a, b in zip(falls, falls[1:])]
    c.that("shortest WDI period, ms", min(per), 5, ok=min(per) >= 5, unit="ms")
    c.that("longest WDI period, ms", max(per), 20, ok=max(per) <= 20, unit="ms")
    return c


SCENARIOS = {f.__name__: f for f in (start, load_step, load_reject, droop, runaway,
                                     crank_loss, ignition_off, sensor_open,
                                     can_content, rail, watchdog)}


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else ""
    selected = {k: v for k, v in SCENARIOS.items() if want in k}
    if not selected:
        print(f"no scenarios match {want!r}. known: {', '.join(SCENARIOS)}")
        return 2
    print("=" * 74)
    print("  Genset ECU -- firmware against the engine model")
    print("=" * 74)
    results = {}
    for name, fn in selected.items():
        try:
            results[name] = fn().report()
        except Exception as exc:
            print(f"\n  {name}\n    {FAIL}  error: {exc!r}")
            results[name] = False
    npass = sum(results.values())
    print("\n" + "=" * 74)
    print(f"  {npass}/{len(results)} scenarios pass")
    print("=" * 74)
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
