#!/usr/bin/env python3
"""Software-in-the-loop: the firmware core against the engine model.

Each scenario is a claim from the spec (section 7) that must hold.

    .venv/bin/python firmware/sim/run_sil.py           # run all
    .venv/bin/python firmware/sim/run_sil.py runaway   # run matching scenarios
"""
import pathlib
import statistics
import struct
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "sim"))
subprocess.run(["make", "-s", "-C", str(HERE)], check=True)

from ecu import Ecu, RUN, SHUTDOWN, NCYL, eol_record  # noqa: E402
from engine import Engine  # noqa: E402
from run_sim import Checks, PASS, FAIL  # noqa: E402

EOL = eol_record(b"SIL", passed=1)

S = 1_000_000                        # us per second
EEC1, ET1, EFLP1, DM1 = 0xF004, 0xFEEE, 0xFEEF, 0xFECA


IMAGE_LEN = 3036                     # sizeof(nvm_image); decode() checks it
TRIP_OVERSPEED, TRIP_SYNC = 1, 2
EV_SHUTDOWN = 6


def decode(img):
    """The persistent image (firmware/core/nvm.h) as a dict."""
    assert len(img) == IMAGE_LEN, f"image is {len(img)} bytes: nvm.h and decode() disagree"
    magic, version, seq, length, crc = struct.unpack_from("<HHIII", img, 0)
    c = struct.unpack_from("<III4H5I", img, 16)
    counters = dict(ecu_s=c[0], engine_s=c[1], starts=c[2], trips_overspeed=c[3],
                    trips_sync=c[4], wdg_resets=c[6])
    dtcs = []
    for i in range(16):
        spn, fmi, status, oc, vbat, first, last, rpm, rail, load, fuel, clt, oil = \
            struct.unpack_from("<IBBBBIIHHBBBB", img, 64 + 24 * i)
        if status & 2:
            dtcs.append(dict(spn=spn, fmi=fmi, active=bool(status & 1), oc=oc, rpm=rpm))
    ev_head, ev_n, rec_next = struct.unpack_from("<BBB", img, 64 + 384 + 768)
    events = []
    for k in range(ev_n):                      # newest first
        t, code, _, arg, rpm, _ = struct.unpack_from("<IBBHHH", img, 448 + 12 * ((ev_head - 1 - k) % 64))
        events.append(dict(t=t, code=code, arg=arg, rpm=rpm))
    recs = []
    for r in range(2):
        base = 64 + 384 + 768 + 4 + 908 * r
        t, reason, n_pre, n_post = struct.unpack_from("<IBBB", img, base)
        samples = [struct.unpack_from("<HBBH", img, base + 8 + 6 * i) for i in range(n_pre + n_post)]
        recs.append(dict(t=t, reason=reason, n_pre=n_pre, n_post=n_post, rpm=[x[0] for x in samples],
                         state=[x[2] for x in samples]))
    return dict(seq=seq, counters=counters, dtcs=dtcs, events=events, recs=recs)


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
        self.slots = [b"", b""]      # the two NVM slots, as the host's flash
        self.saves = 0
        self.tear_next = False       # the next save is cut by a power loss halfway
        self.torn = False
        self.ecu.nvm_load(*self.slots)
        self.ecu.eol_load(EOL, EOL)      # a unit that passed the end-of-line test
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
                self.ecu.background()
                if self.io.nvm_save:
                    img = self.ecu.nvm_image()
                    if self.tear_next:
                        # the rest of the slot stays erased flash (0xFF)
                        img = img[:len(img) // 2] + b"\xff" * (len(img) - len(img) // 2)
                        self.tear_next, self.torn = False, True
                    self.slots[self.io.nvm_slot] = img
                    self.io.nvm_save = 0
                    self.saves += 1
                for cid, data in self.ecu.drain_can():
                    self.can.append((self.next_ms, pgn(cid), data))
                self._after(self.next_ms)
                self.trace.append((self.next_ms, self.eng.rpm, self.io.state,
                                   self.eng.rail_bar, self.io.meter_duty,
                                   self.ecu.rail_set_bar(self.io.fuel_mg), self.io.wdg))
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

    def power_cycle(self):
        """Power off and on: a fresh ECU that reloads the two slots."""
        self.ecu.init()
        self.io.ignition = 1
        self.io.droop_sw = 0
        self.io.reset_cause = 0
        self._volts()
        self.ecu.nvm_load(*self.slots)
        self.ecu.eol_load(EOL, EOL)
        self._sent = [0] * NCYL
        self.eng.seq = [0] * NCYL
        self.eng.cmd = [None] * NCYL
        self._state = self.io.state
        return decode(self.ecu.nvm_image())

    def request(self, pgn_):
        """A global J1939 request from a tool at address 3."""
        self.ecu.can_rx(0x18EAFF03, pgn_.to_bytes(3, "little"))

    def newest_slot(self):
        imgs = [decode(x) for x in self.slots if len(x) == IMAGE_LEN]
        return max(imgs, key=lambda d: d["seq"])

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
    under = [t for t, d in sim.dm1_after(0) if (190, 18) in d]
    c.that("no underspeed warning (SPN 190 FMI 18)", "none" if not under else "raised", 0,
           ok=not under)
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
    # against the firmware's own setpoint, which follows fuel
    lo0 = [(p, ps) for t, r, st, p, d, ps, w in sim.trace if 6 * S <= t < 8 * S]
    sim.eng.load_kw = 20
    sim.run(16.0)
    lo20 = [(p, ps) for t, r, st, p, d, ps, w in sim.trace if 14 * S <= t < 16 * S]
    for name, xs in (("0 kW", lo0), ("20 kW", lo20)):
        worst = max(abs(p / ps - 1) for p, ps in xs)
        c.that(f"{name}: worst deviation, fraction", worst, 0.05, ok=worst <= 0.05)
    return c


def watchdog():
    c = Checks("11 watchdog kick inside the 5-20 ms window")
    sim = Sim().start(8.0)
    sim.eng.load_kw = 20
    sim.run(13.0)
    falls = [t for (t, *_, w), (t0, *_, w0) in zip(sim.trace[1:], sim.trace) if w0 and not w]
    per = [(b - a) / 1000 for a, b in zip(falls, falls[1:])]
    tail = (sim.trace[-1][0] - falls[-1]) / 1000      # kicks that stop are a failure too
    c.that("time since the last WDI fall at the end, ms", tail, 20, ok=tail <= 20, unit="ms")
    c.that("shortest WDI period, ms", min(per), 5, ok=min(per) >= 5, unit="ms")
    c.that("longest WDI period, ms", max(per), 20, ok=max(per) <= 20, unit="ms")
    return c


def history_after_power_cycle():
    c = Checks("12 runaway, then power cycle: the history survives")
    sim = Sim().start(6.0)
    sim.eng.stuck_fuel_mg = 80
    sim.run(9.0)
    img = sim.power_cycle()
    d = next((x for x in img["dtcs"] if (x["spn"], x["fmi"]) == (190, 0)), None)
    c.that("DTC 190/0 stored", "yes" if d else "no", 0, ok=d is not None)
    if d:
        c.that("  previously active after power-up", "yes" if not d["active"] else "active", 0,
               ok=not d["active"])
        c.that("  occurrence count", d["oc"], 1, tol=0)
        c.that("  freeze-frame rpm", d["rpm"], 1650, ok=d["rpm"] >= 1650, unit="rpm")
    shut = [e for e in img["events"] if e["code"] == EV_SHUTDOWN and e["arg"] == TRIP_OVERSPEED]
    c.that("event log has SHUTDOWN (overspeed)", "yes" if shut else "no", 0, ok=bool(shut))
    rec = next((r for r in img["recs"] if r["reason"] == TRIP_OVERSPEED), None)
    c.that("trip recording kept", "yes" if rec else "no", 0, ok=rec is not None)
    if rec:
        last = rec["rpm"][rec["n_pre"] - 1]
        c.that("  last sample before the trip, rpm", last, 1650, ok=last >= 1620, unit="rpm")
        c.that("  after-trip samples", rec["n_post"], 50, tol=0)
    c.that("starts counted", img["counters"]["starts"], 1, ok=img["counters"]["starts"] >= 1)
    return c


def torn_save():
    c = Checks("13 power lost halfway through a save")
    sim = Sim().start(3.0)
    before = sim.newest_slot()
    sim.tear_next = True
    sim.io.ignition = 0                       # stopping asks for a save, 10 s after the start's
    sim.run(16.0)
    c.that("a save was torn", "yes" if sim.torn else "no", 0, ok=sim.torn)
    img = sim.power_cycle()
    c.that("reload took the previous image, seq", img["seq"], before["seq"], tol=0)
    c.that("starts as in that image", img["counters"]["starts"], before["counters"]["starts"], tol=0)
    return c


def dm2_dm3_over_can():
    c = Checks("14 stored faults read and cleared over CAN")
    sim = Sim().start(6.0)
    sim.eng.clt_open = True                   # 110/3: raised, then cleared -> stored
    sim.run(7.5)
    sim.eng.clt_open = False
    sim.run(8.0)
    sim.request(0xFECB)
    sim.run(8.1)
    dm2 = [dtcs(d) for t, p, d in sim.can if p == 0xFECB and t > 8 * S]
    c.that("DM2 returns 110/3", str(dm2[:1]), 0, ok=bool(dm2) and (110, 3) in dm2[0])
    sim.eng.v_override["v_oil"] = 0.1         # 100/4: active through the clear
    sim.run(9.0)
    sim.request(0xFECC)
    sim.run(9.1)
    sim.request(0xFECB)
    sim.run(11.2)
    dm2 = [dtcs(d) for t, p, d in sim.can if p == 0xFECB and t > 9.1 * S]
    dm1 = [d for t, d in sim.dm1_after(10 * S)]
    c.that("DM2 after DM3 is empty", str(dm2[:1]), 0, ok=bool(dm2) and dm2[0] == [])
    c.that("active fault 100/4 still on DM1", str(dm1[-1:]), 0, ok=bool(dm1) and (100, 4) in dm1[-1])
    return c


def lost_tooth():
    c = Checks("15 one lost crank tooth at 1500 rpm")
    sim = Sim().start(6.0)
    sim.eng.drop_edge_once = True
    sim.run(8.0)
    tr = sim.trip(6.0)
    c.that("SHUTDOWN", "yes" if tr else "no", 0, ok=tr is not None)
    stored = {(d["spn"], d["fmi"]) for d in sim.newest_slot()["dtcs"]}
    c.that("stored as crank sensor (636)", "yes" if (636, 2) in stored else "no", 0, ok=(636, 2) in stored)
    c.that("not stored as overspeed (190)", "no" if (190, 0) not in stored else "yes", 0,
           ok=(190, 0) not in stored)
    return c

def overload():
    c = Checks("16 overload 30 kW: underspeed warning, engine keeps running")
    sim = Sim().start(8.0)
    sim.eng.load_kw = 30                # beyond the 45 mg fuel limit at 1350 rpm
    sim.run(20.0)
    sag = next((t for t, r, *_ in sim.trace if t >= 8 * S and r < 1350), None)
    c.that("speed sags below 1350 rpm", "yes" if sag else "no", 0, ok=sag is not None)
    if sag:
        got = next((t for t, d in sim.dm1_after(sag) if (190, 18) in d), None)
        c.that("DM1 carries SPN 190 FMI 18 within 5 s of the sag, s",
               (got - sag) / S if got else 99, 5, ok=got is not None and got - sag <= 5 * S, unit="s")
        if got:
            lamp = next(d for t, p, d in sim.can if p == DM1 and t == got)[0]
            c.that("amber lamp only, not Protect", hex(lamp), 0, ok=lamp == 0x04)
    c.that("never shut down", "ok" if sim.trip() is None else "tripped", 0,
           ok=sim.trip() is None and sim.io.state == RUN)
    return c


SCENARIOS = {f.__name__: f for f in (start, load_step, load_reject, droop, runaway,
                                     crank_loss, ignition_off, sensor_open,
                                     can_content, rail, watchdog,
                                     history_after_power_cycle, torn_save,
                                     dm2_dm3_over_can, lost_tooth, overload)}


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
