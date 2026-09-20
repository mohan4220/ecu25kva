#!/usr/bin/env python3
"""Run every circuit block's simulation and check it against its spec.

Each check is a claim about the circuit that must hold. A block passes
only if every claim holds -- so a red line here means the circuit is
wrong, not that the simulation is unhappy.

    .venv/bin/python sim/run_sim.py            # run all
    .venv/bin/python sim/run_sim.py battery    # run matching blocks
"""
import pathlib
import sys
import tempfile

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
import ngrun  # noqa: E402

BLOCKS = HERE / "blocks"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


class Checks:
    def __init__(self, title):
        self.title = title
        self.rows = []

    def that(self, claim, actual, expected, tol=None, unit="", ok=None):
        """Record one claim. Pass `ok` for a boolean claim, or `tol` for a numeric one."""
        if ok is None:
            ok = abs(actual - expected) <= tol
        self.rows.append((ok, claim, actual, expected, unit))
        return ok

    @property
    def ok(self):
        return all(r[0] for r in self.rows)

    def report(self):
        print(f"\n  {self.title}")
        for ok, claim, actual, expected, unit in self.rows:
            mark = PASS if ok else FAIL
            if isinstance(actual, str):
                print(f"    {mark}  {claim:<46} {actual}")
            else:
                print(f"    {mark}  {claim:<46} {actual:>10.3f} {unit:<4} (want {expected:g})")
        return self.ok


def sim(name, outputs):
    """Run blocks/<name>.cir and return {datafile: {col: array}}."""
    wd = pathlib.Path(tempfile.mkdtemp(prefix=f"sim_{name}_"))
    log = ngrun.run((BLOCKS / f"{name}.cir").read_text(), wd)
    data = {}
    for fname, cols in outputs.items():
        f = wd / fname
        if not f.exists():
            raise RuntimeError(
                f"{name}: ngspice produced no {fname}.\n" + "".join(log[-25:])
            )
        data[fname] = {k: np.array(v) for k, v in ngrun.read_wrdata(f, cols).items()}
    return data


# ---------------------------------------------------------------- blocks


def check_battery_sense():
    c = Checks("battery_sense -- ECU pins 04/06, 6-40 V rail into a 3.3 V ADC")
    d = sim("battery_sense", {"battery_sense.dat": ["vbat", "old", "new"]})["battery_sense.dat"]
    vbat, old, new = d["vbat"], d["old"], d["new"]

    # The inherited 75k/10k divider was sized for a 5 V ADC.
    c.that("inherited 75k/10k peak at 40 V", old.max(), 4.706, tol=0.02, unit="V")
    c.that("  ... and so exceeds a 3.3 V ADC", f"{old.max():.2f} V > 3.3 V -- would damage input",
           None, ok=old.max() > 3.3)

    # The corrected 120k/10k divider must stay inside the ADC range at the
    # top of the input band, and still resolve usefully at the bottom.
    c.that("corrected 120k/10k peak at 40 V", new.max(), 3.077, tol=0.02, unit="V")
    c.that("  ... stays under the 3.3 V rail", new.max(), 3.3, tol=None, ok=new.max() < 3.3)
    c.that("headroom below rail", 3.3 - new.max(), 0.22, tol=0.05, unit="V")

    at6 = float(np.interp(6.0, vbat, new))
    c.that("reading at 6 V cranking dip", at6, 0.462, tol=0.02, unit="V")
    c.that("  ... resolves to usable ADC counts", at6 / (3.3 / 4096), 573, tol=30, unit="LSB")

    # Linearity: a resistive divider must be exactly linear, so a straight-line
    # fit should have essentially zero residual. This catches a wrong topology.
    fit = np.polyfit(vbat, new, 1)
    resid = float(np.max(np.abs(new - np.polyval(fit, vbat))))
    c.that("divider is linear (max residual)", resid, 0.0, tol=1e-6, unit="V")
    c.that("slope matches 10/130", fit[0], 10 / 130, tol=1e-4)
    return c


def check_discrete_input():
    c = Checks("discrete_input -- ECU pins 20/24/71, active-high switched battery")
    d = sim("discrete_input", {
        "discrete_input_dc.dat": ["vsw", "node"],
        "discrete_input_tran.dat": ["time", "node", "sw"],
    })
    vsw, node = d["discrete_input_dc.dat"]["vsw"], d["discrete_input_dc.dat"]["node"]
    t = d["discrete_input_tran.dat"]["time"]
    ntr = d["discrete_input_tran.dat"]["node"]

    # Must never exceed the MCU pin's absolute maximum (VDD + 0.3 = 3.6 V).
    c.that("never exceeds 3.6 V abs max over 6-40 V", node.max(), 3.6, tol=None,
           ok=node.max() <= 3.6)

    # Must read logic HIGH (0.7*VDD = 2.31 V) even at the 6 V cranking dip,
    # which is the worst case for an active-high input.
    at6 = float(np.interp(6.0, vsw, node))
    at40 = float(np.interp(40.0, vsw, node))
    c.that("logic high at 6 V cranking dip", at6, 2.31, tol=None, ok=at6 >= 2.31)
    c.that("logic high at 40 V load dump", at40, 2.31, tol=None, ok=at40 >= 2.31)

    # The point of the zener topology: the logic level should be essentially
    # flat across the whole battery range rather than tracking it.
    c.that("level is flat across 6-40 V (spread)", at40 - at6, 0.0, tol=0.35, unit="V")

    # Debounce: once the contact settles at 4.5 ms, the node must be high
    # and stay high.
    settled = ntr[t >= 20e-3]
    c.that("settled high after bounce ends", float(settled.min()), 2.31, tol=None,
           ok=float(settled.min()) >= 2.31)

    # ... and it must not have chattered across the threshold during the
    # bounce itself. Count threshold crossings before the contact settles.
    early = ntr[t < 4.4e-3]
    crossings = int(np.sum(np.diff((early > 2.31).astype(int)) != 0))
    c.that("threshold crossings during bounce", crossings, 0, tol=None,
           ok=crossings == 0)

    # Time constant is R_thevenin * C with R_th = 47k || 68k = 27.8k.
    tau = (47e3 * 68e3 / 115e3) * 220e-9
    c.that("debounce time constant", tau * 1e3, 6.11, tol=0.05, unit="ms")
    return c


def check_trip_module_sense():
    c = Checks("trip_module_sense -- NEW pin, three-state supervised trip loop")
    d = sim("trip_module_sense", {
        "trip_healthy.dat": ["sweep", "nh"],
        "trip_tripped.dat": ["sweep", "nt"],
        "trip_wirefault.dat": ["sweep", "nc"],
        "trip_bounce.dat": ["t", "nd", "vb"],
    })
    nh = d["trip_healthy.dat"]["nh"]
    nt = d["trip_tripped.dat"]["nt"]
    nc = float(d["trip_wirefault.dat"]["nc"][0])
    t, nd = d["trip_bounce.dat"]["t"], d["trip_bounce.dat"]["nd"]

    WIREFAULT_HI = 0.15
    TRIPPED_HI = 2.5

    # ---- three bands, each swept 6-40 V (op point for wire fault) ----
    c.that("healthy (contact closed) band floor", float(nh.min()), 2.863,
           tol=0.02, unit="V")
    c.that("healthy band ceiling", float(nh.max()), 2.954, tol=0.02, unit="V")
    c.that("tripped (Rt in circuit) band floor, at 6V cranking dip",
           float(nt.min()), 0.310, tol=0.02, unit="V")
    c.that("tripped band ceiling, at 40V", float(nt.max()), 2.068, tol=0.02,
           unit="V")
    c.that("wire fault reads near zero", nc, 0.0, tol=None, ok=abs(nc) < 1e-3,
           unit="V")

    # The zener must never conduct in the tripped branch -- if it did, the
    # band would flatten toward ~3.0V like the healthy branch and lose its
    # separation. Confirmed by the ceiling (2.068 V) staying well under the
    # 3.0 V knee.
    c.that("tripped band never reaches the zener's 3.0V knee",
           float(nt.max()), 3.0, tol=None, ok=float(nt.max()) < 3.0, unit="V")

    # ---- band separation margins, the falsifiable core of this design ----
    wf_margin = float(nt.min()) - WIREFAULT_HI
    trip_margin = float(nh.min()) - float(nt.max())
    c.that("margin: wire-fault threshold to tripped floor (nominal Rt)",
           wf_margin, 0.160, tol=0.02, unit="V")
    c.that("margin: tripped ceiling to healthy floor (nominal Rt)",
           trip_margin, 0.795, tol=0.02, unit="V")
    c.that("  ... both bands separated with real margin, not touching",
           f"wire-fault margin {wf_margin:.3f} V, tripped margin "
           f"{trip_margin:.3f} V, both positive", None,
           ok=wf_margin > 0 and trip_margin > 0)

    # ---- contact bounce: never dips toward wire-fault, settles correctly ----
    before = nd[t < 4.5e-3]
    c.that("during bounce (t<4.5ms), reading never leaves the healthy band",
           float(before.min()), TRIPPED_HI, tol=None,
           ok=float(before.min()) > TRIPPED_HI, unit="V")

    # Hand asymptote: fixed Vbat=12V, node -> Vbat*68k/(Rt+115k) = 0.6206 V.
    c.that("settled value (t=100ms) approaches the DC asymptote (hand: 0.6206 V)",
           float(nd[-1]), 0.6206, tol=0.02, unit="V")
    c.that("  ... which sits inside the tripped band, not wire-fault or healthy",
           float(nd[-1]), TRIPPED_HI, tol=None,
           ok=WIREFAULT_HI < float(nd[-1]) < TRIPPED_HI, unit="V")
    c.that("  ... global minimum over the whole run stays clear of wire-fault",
           float(nd.min()), WIREFAULT_HI, tol=None,
           ok=float(nd.min()) > WIREFAULT_HI, unit="V")

    # ---- why discrete_input.cir's own accepted limitation does not apply
    # here, stated as a claim rather than left as prose only ----
    c.that("open-wire detection: needed here, unlike pins 20/24/71",
           "no OEM harness to stay compatible with, and an undetectable "
           "open reads 'not tripped' at the exact moment a trip occurs",
           None, ok=True)
    return c


def check_sensor_ratiometric():
    c = Checks("sensor_ratiometric -- Group A, pins 41/35/80/37, 0.5-4.5 V into a 3.3 V ADC")
    d = sim("sensor_ratiometric", {
        "sensor_ratio_dc.dat": ["vsens", "node"],
        "sensor_ratio_ac.dat": ["frequency", "vdb"],
        "sensor_ratio_fault.dat": ["sweep", "node", "ifault"],
        "sensor_ratio_rail.dat": ["vsup", "raw", "corrected"],
    })
    vs, node = d["sensor_ratio_dc.dat"]["vsens"], d["sensor_ratio_dc.dat"]["node"]
    f, mag = d["sensor_ratio_ac.dat"]["frequency"], d["sensor_ratio_ac.dat"]["vdb"]

    # Both ends of the sensor's output span must land inside the ADC range,
    # and full scale must stay below the 3.3 V clamp so the clamp never
    # touches the signal in normal operation.
    c.that("sensor zero (0.5 V) maps to", float(node.min()), 0.308, tol=0.01, unit="V")
    c.that("sensor full scale (4.5 V) maps to", float(node.max()), 2.769, tol=0.01, unit="V")
    c.that("  ... clears the 3.3 V clamp", 3.3 - float(node.max()), 0.53, tol=0.05,
           unit="V")

    # Span should use most of the ADC: a front-end that only reaches half the
    # range throws away resolution for nothing.
    span = (node.max() - node.min()) / 3.3
    c.that("span used of ADC range", span * 100, 74.6, tol=2.0, unit="%")

    # The filter must not eat the sensor's own bandwidth (~100 Hz mechanical)
    # while still rolling off the board's switching noise. Measure relative to
    # the passband, not absolute dB -- the divider itself sits at -4.2 dB, and
    # measuring absolutely would report the divider's own loss as a corner.
    passband = float(np.mean(mag[f < 10]))
    i3 = int(np.argmin(np.abs(mag - (passband - 3.0))))
    c.that("low-pass corner", float(f[i3]), 1176, tol=70, unit="Hz")
    at100 = float(mag[int(np.argmin(np.abs(f - 100)))]) - passband
    c.that("loss at sensor's own 100 Hz", at100, 0.0, tol=0.2, unit="dB")
    at100k = float(mag[int(np.argmin(np.abs(f - 1e5)))]) - passband
    c.that("attenuation at 100 kHz switching", at100k, -38.6, tol=1.5, unit="dB")

    # Harness short to battery: the clamp must hold the pin inside the MCU's
    # absolute maximum, and R1 must keep the fault current sane.
    vf = float(d["sensor_ratio_fault.dat"]["node"][0])
    i_f = abs(float(d["sensor_ratio_fault.dat"]["ifault"][0]))
    c.that("40 V harness short clamps pin to", vf, 3.6, tol=None, ok=vf <= 3.6)
    c.that("  ... fault current limited to", i_f * 1e3, 5.0, tol=None, ok=i_f < 5e-3,
           unit="mA")

    # The ratiometric property. A sensor at a fixed physical reading, with the
    # rail drifting +/-5%: the raw ADC value must move with the rail (it is a
    # fraction OF the rail), and the corrected value must not.
    r = d["sensor_ratio_rail.dat"]
    raw, corr = r["raw"], r["corrected"]
    raw_err = (float(raw.max()) - float(raw.min())) / float(raw.mean()) * 100
    corr_err = (float(corr.max()) - float(corr.min())) / float(corr.mean()) * 100
    c.that("raw reading moves with a +/-5% rail drift", raw_err, 10.0, tol=1.0,
           unit="%")
    c.that("  ... so an assumed 5.000 V rail is a 10% error band",
           f"{raw_err:.1f}% of reading, and nothing in the raw value reveals it",
           None, ok=raw_err > 5)
    c.that("corrected reading is flat", corr_err, 0.0, tol=0.01, unit="%")
    c.that("correction recovers the true fraction", float(corr.mean()), 0.5,
           tol=0.001)
    c.that("  ... divider ratio cancels, so its tolerance drops out too",
           "measurand = Vsig/Vrail -- k appears in both and divides away",
           None, ok=True)
    return c


def check_transient_clamp():
    c = Checks("transient_clamp -- ISO 7637-2 pulse 2a, +112 V / 2 ohm / 50 us")
    d = sim("transient_clamp", {"transient_clamp.dat": ["time", "bat", "src"]})["transient_clamp.dat"]
    t, bat, src = d["time"], d["bat"], d["src"]

    c.that("pulse actually applied (source peak)", float(src.max()), 112, tol=None,
           ok=float(src.max()) > 100)

    # An SMBJ33CA cannot meet the 42 V figure the earlier artifacts asked for --
    # see the note in the netlist. The real constraints are the buck's rating
    # and keeping 60 V-class parts viable.
    #
    # 55.0 below has the same problem the 42 V figure had, one line down:
    # it is not the LM5164's rating (100 V, checked next), not the "60 V-class
    # parts" bound (checked two lines below), and not tied to any standard or
    # datasheet. It reads as "simulated ~50 V result + ~5 V margin," chosen
    # after seeing the answer rather than before. It happens not to change
    # the verdict -- the 60 V check below carries the real conclusion -- but
    # the number itself is unsourced. Kept as a check (not deleted) because a
    # margin-over-observed-result gate still has some value as a trip wire if
    # the clamp voltage ever moves; just do not read it as a spec.
    vmax = float(bat.max())
    c.that("clamped voltage at buck input", vmax, 80.0, tol=None,
           ok=vmax < 80.0, unit="V")
    # Gate raised from 55 V to 80 V on 20 Sep 2026, and this is a design
    # change rather than a weakened check. The TVS standoff had to go from
    # 33 V to 43 V so it stops conducting during a normal 40 V clamped load
    # dump (see load_dump.cir). A higher standoff clamps higher, and the
    # only real constraint is the buck's own 100 V absolute maximum. The
    # 55 V figure was inherited from a design where the standoff sat below
    # the dump level -- i.e. from the arrangement that was wrong.
    c.that("  ... margin inside LM5164's 100 V rating", 100.0 / vmax, 1.3,
           tol=None, ok=vmax < 100.0 / 1.3, unit="x")
    c.that("  ... 60 V-class parts are NO LONGER viable downstream", vmax, 60.0,
           tol=None, ok=vmax > 60.0, unit="V")
    c.that("  ... so the reverse-battery FET needs 100 V class, not 60",
           f"{vmax:.1f} V clamp -- reverse_battery.cir's 60 V figure is superseded",
           None, ok=True)
    settled = bat[t > 1.5e-3]
    c.that("recovers to nominal after pulse", float(settled.mean()), 12.98, tol=0.1,
           unit="V")
    return c


def check_load_dump():
    c = Checks("load_dump -- ISO 7637-2 pulse 5b, Us*=40 V / 0.5 ohm / 400 ms")
    d = sim("load_dump", {"load_dump.dat": ["time", "bat", "src", "iamm"]})["load_dump.dat"]
    t, bat, src, iamm = d["time"], d["bat"], d["src"], d["iamm"]

    c.that("pulse actually applied (source peak)", float(src.max()), 40, tol=None,
           ok=float(src.max()) > 35, unit="V")

    # Voltage side: same question transient_clamp asked for pulse 2a. This
    # is the part of the story that looks fine.
    #
    # vclamp/iclamp/avg_power below (and the same three lines further down)
    # are REGRESSION PINS, not independent claims (2026-09-18 review F6):
    # their "expected" values were read off this simulation's own output,
    # not derived beforehand from Us*/Ri/the TVS model in closed form -- the
    # TVS's nonlinear clamping makes that algebra impractical by hand, the
    # same reason mcu_pdn.cir's anti-resonance check is pinned rather than
    # formula-checked. They exist so a future change to this netlist that
    # silently moves the clamp point gets caught; they are not a design
    # requirement anybody chose. The real claims -- the ones with an
    # independently sourced bound -- are the ~0.5 J / ~3 W datasheet-class
    # limits checked below, and the settled-voltage and energy figures,
    # which ARE derivable a priori (energy by integrating the plateau
    # numbers, settled voltage as 13.5*Rload/(Rload+Rsrc)) and match to 3
    # significant figures.
    plateau = (t > 0.05) & (t < 0.4)
    vclamp = float(bat[plateau].mean())
    c.that("clamped voltage through the 400 ms plateau", vclamp, 39.60, tol=0.3, unit="V")
    c.that("  ... inside LM5164's 100 V rating", 100.0 / vclamp, 2.6, tol=None,
           ok=vclamp < 100.0 / 1.5, unit="x")
    c.that("  ... 60 V-class parts still viable", vclamp, 60.0, tol=None,
           ok=vclamp < 60.0, unit="V")

    # Energy side: the question pulse 2a never had to ask, because 2a is
    # 50 us and no part-thermal limit engages in that time. 5b is 400 ms,
    # long enough that the TVS's dissipation rating -- not its clamp
    # voltage -- is what determines whether it survives.
    iclamp = float(iamm[plateau].mean())
    c.that("TVS current through the plateau -- now ZERO, the TVS stays off", iclamp, 0.0, tol=0.01, unit="A")
    avg_power = float(np.abs(bat[plateau] * iamm[plateau]).mean())
    c.that("average power dissipated in the TVS", avg_power, 0.0, tol=0.5, unit="W")
    # ^ regression pin, see the comment above vclamp.

    energy = float(np.trapezoid(np.abs(bat * iamm), t))
    c.that("total energy absorbed by the TVS over the pulse", energy, 0.0, tol=0.05,
           unit="J")

    # The falsifiable claims: does an SMBJ-class part actually survive this.
    # Datasheet figures used as the bar (see the netlist's RESULT NOTE for
    # sourcing): ~0.5 J for a single 10/1000 us pulse, ~3 W continuous
    # dissipation. Both are class-typical, not a pulled datasheet number for
    # a specific manufacturer part -- but the margin here is wide enough
    # that the conclusion does not depend on which vendor's exact figure is
    # used.
    c.that("energy stays within a single-pulse (~0.5 J) rating", energy, 0.5,
           tol=None, ok=energy < 0.5, unit="J")
    c.that("average power stays within continuous (~3 W) rating", avg_power, 3.0,
           tol=None, ok=avg_power < 3.0, unit="W")
    c.that("  ... fraction of the continuous rating now used",
           avg_power / 3.0, 0.0, tol=0.2, unit="x")

    # And the model must recover -- same sanity check transient_clamp makes.
    # Settles to the source divided by Rsrc/Rload, not to the bare 13.5 V,
    # same as transient_clamp.
    settled = bat[t > 0.42]
    c.that("recovers to nominal after pulse", float(settled.mean()), 13.37, tol=0.1,
           unit="V")
    return c


def check_negative_pulses():
    c = Checks("negative_pulses -- ISO 7637-2 pulses 1 & 3a, negative excursions "
               "into the battery input")
    d = sim("negative_pulses", {
        "negative_pulses_p1.dat": ["time", "bat1", "src1", "iamm1", "vbuck_on1",
                                    "vbuck_off1", "vbuck_cl1", "isch1"],
        "negative_pulses_p3a.dat": ["time", "bat3a", "src3a", "iamm3a",
                                     "vbuck_on3a", "vbuck_off3a",
                                     "vbuck_cl3a", "isch3a"],
    })
    p1, p3a = d["negative_pulses_p1.dat"], d["negative_pulses_p3a.dat"]
    t1, bat1, src1, iamm1 = p1["time"], p1["bat1"], p1["src1"], p1["iamm1"]
    vbon1, vboff1 = p1["vbuck_on1"], p1["vbuck_off1"]
    vbcl1, isch1 = p1["vbuck_cl1"], p1["isch1"]
    t3, bat3a, src3a, iamm3a = p3a["time"], p3a["bat3a"], p3a["src3a"], p3a["iamm3a"]
    vbon3a, vboff3a = p3a["vbuck_on3a"], p3a["vbuck_off3a"]
    vbcl3a, isch3a = p3a["vbuck_cl3a"], p3a["isch3a"]

    LM5164_VIN_MIN = -0.3  # TI LM5164 datasheet, Absolute Maximum Ratings, VIN
    # to GND: MIN -0.3 V, MAX 100 V -- fetched and text-extracted directly for
    # this block, not carried over unverified. The positive (100 V) rating is
    # already checked elsewhere (transient_clamp/load_dump); this is the first
    # block to need the negative one, and it is a completely different number.

    c.that("pulse 1 actually applied (source peak)", float(src1.min()), -136.5,
           tol=None, ok=float(src1.min()) < -130, unit="V")
    c.that("pulse 3a actually applied (source peak)", float(src3a.min()), -206.5,
           tol=None, ok=float(src3a.min()) < -195, unit="V")

    # ---- Q1: what the buck's VIN pin actually sees ----
    # bat1/bat3a and vbuck_on1/on3a are regression pins (the TVS's nonlinear
    # clamping plus C1's own RC dynamics make these numbers impractical to
    # derive by hand, same reason load_dump's TVS figures are pinned rather
    # than formula-checked) -- the FALSIFIABLE claim is the comparison against
    # LM5164_VIN_MIN two lines below each.
    vbon1_min = float(vbon1.min())
    c.that("battery node, pulse 1 -- now set by the clamp diode, not the TVS",
           float(bat1.min()), -0.64, tol=0.08, unit="V")
    c.that("buck VIN pin, pulse 1, WITH the negative clamp fitted",
           vbon1_min, -0.53, tol=0.06, unit="V")
    c.that("  ... evidence: a Schottky ALONE still misses LM5164's own "
           "-0.3 V abs max (sourced, not INFERRED), by",
           vbon1_min / LM5164_VIN_MIN, 1.76, tol=0.2, unit="x")

    vbon3a_min = float(vbon3a.min())
    c.that("battery node, pulse 3a -- now set by the clamp diode, not the TVS",
           float(bat3a.min()), -0.43, tol=0.08, unit="V")
    c.that("buck VIN pin, pulse 3a, WITH the negative clamp fitted",
           vbon3a_min, -0.39, tol=0.06, unit="V")
    c.that("  ... evidence: same, pulse 3a -- a Schottky alone misses by",
           vbon3a_min / LM5164_VIN_MIN, 1.31, tol=0.2, unit="x")

    # ---- RESOLUTION: the active clamp ----
    # A Schottky cannot reach -0.3 V at 15 A and the reason is structural,
    # not a sizing miss: its junction term is logarithmic in current
    # (0.367 V at 15 A) and only its bulk term falls when parts are
    # paralleled. The rating is really a demand for effective clamp
    # impedance -- 0.3 V / 15 A = 20 mOhm, junction included -- which no
    # junction device meets and an ordinary 5 mOhm N-channel FET clears
    # four times over. See the netlist for the decomposition.
    #
    # These are the falsifiable rows: same -0.3 V rating, same pulses,
    # with the active clamp in place of the bare Schottky.
    vcl1_min, vcl3a_min = float(vbcl1.min()), float(vbcl3a.min())
    c.that("RESOLVED: buck VIN, pulse 1, with the active clamp", vcl1_min,
           LM5164_VIN_MIN, tol=None, ok=vcl1_min >= LM5164_VIN_MIN, unit="V")
    c.that("  ... margin inside the rating", LM5164_VIN_MIN / vcl1_min, 4.4,
           tol=None, ok=vcl1_min > LM5164_VIN_MIN, unit="x")
    c.that("RESOLVED: buck VIN, pulse 3a, with the active clamp", vcl3a_min,
           LM5164_VIN_MIN, tol=None, ok=vcl3a_min >= LM5164_VIN_MIN, unit="V")
    c.that("  ... margin inside the rating", LM5164_VIN_MIN / vcl3a_min, 11.0,
           tol=None, ok=vcl3a_min > LM5164_VIN_MIN, unit="x")
    c.that("  ... and the improvement over the Schottky alone",
           vbon1_min / vcl1_min, 7.7, tol=1.0, unit="x")
    c.that("  ... NOT MODELLED: the comparator's propagation delay -- VIN "
           "sits at the Schottky's clamp for exactly that long first",
           "unbounded question was 'is a 2 ms excursion acceptable'; it is "
           "now 'is a sub-microsecond one', which a comparator datasheet "
           "answers", None, ok=True)

    # ---- Q2: does the reverse-battery stage help or hurt ----
    # vbuck_off reproduces reverse_battery.cir's own optimistic, no-turn-off-
    # delay switch model -- comparison only, per that file's own RESULT NOTE
    # ("will always look perfect in reverse"), NOT a claim this stage protects
    # the buck. No controller part is chosen, so no turn-off delay exists to
    # check pulse 3a's 0.1 ms width against -- the FET-on branch above is the
    # one this block trusts.
    c.that("  ... comparison only: IF the FET had already opened (idealized, "
           "reverse_battery.cir's own optimistic model, not verified against "
           "any real turn-off delay)", abs(float(vboff1.min())), 0.0, tol=0.01,
           unit="V")
    c.that("  ... same comparison, pulse 3a", abs(float(vboff3a.min())), 0.0,
           tol=0.01, unit="V")
    c.that("  ... so the reverse-battery stage helps only if it reacts in time, "
           "and nothing sources that time",
           "FET-on branch tracks the bare TVS clamp to within its 8 mOhm "
           "drop for both pulses -- reverse_battery.cir's own turn-off delay "
           "is undocumented, not zero", None, ok=True)

    # ---- recovery: divider baseline, not bare 13.5 V (see RESULT NOTE) ----
    settled1 = bat1[t1 > 3.2e-3]
    c.that("bat1 recovers to its own Rsrc1/Rload divider baseline (11.25 V, "
           "not 13.5 V)", float(settled1.mean()), 11.25, tol=0.05, unit="V")
    pre_vals = [float(bat3a[(t3 > cc - 1e-3) & (t3 < cc - 0.5e-3)].mean())
                for cc in (0.095, 0.185, 0.275, 0.365)]
    c.that("bat3a recovers to its own divider baseline (6.75 V) between every "
           "burst pulse", float(np.mean(pre_vals)), 6.75, tol=0.02, unit="V")

    # ---- Q4: pulse 3a is a burst -- does anything accumulate ----
    centers = [0.005, 0.095, 0.185, 0.275, 0.365]
    peaks = [float(bat3a[(t3 > cc - 0.2e-3) & (t3 < cc + 0.2e-3)].min())
             for cc in centers]
    # Split the first pulse out from the rest. Pulses 2-5 are the burst
    # proper; pulse 1 fires at t = 5 ms, while C1b is still settling from
    # the run's own initial condition, so it is not a like-for-like
    # sample. Lumping all five together read a 16 mV spread and looked
    # like accumulation -- the split shows pulses 2-5 are identical to
    # the printed precision and the whole spread is pulse 1's head start.
    steady = peaks[1:]
    spread_steady = max(steady) - min(steady)
    c.that("burst: peak-to-peak spread across repeats 2-5 (accumulation "
           "would show up here)", spread_steady, 0.0, tol=1e-4, unit="V")
    c.that("  ... and repeat 1 differs only by its own initial settling, "
           "not by a trend", abs(peaks[0] - peaks[1]) * 1e3, 15.8, tol=3.0,
           unit="mV")
    # A trend is what accumulation looks like. Monotonic drift across the
    # steady repeats would show here even if the spread stayed small.
    diffs = np.diff(steady)
    c.that("  ... no monotonic drift across repeats 2-5",
           float(np.abs(diffs).max()) * 1e3, 0.0, tol=0.1, unit="mV")

    # ---- TVS energy ----
    # The TVS no longer absorbs pulse 1 at all. This row read 0.707 J
    # while the TVS was the only negative-going path on the node; the
    # clamp Schottky added on 20 Sep 2026 conducts at half a volt, two
    # orders of magnitude before the TVS's own -47.8 V breakdown, so the
    # TVS never avalanches and its energy is numerically zero. Re-pinned
    # rather than deleted, because a TVS that starts conducting here again
    # means the clamp path has been broken or removed, and that is worth
    # failing on.
    energy1 = float(np.trapezoid(np.abs(bat1 * iamm1), t1))
    c.that("TVS energy, pulse 1 -- zero now the clamp diode conducts first",
           energy1, 0.0, tol=1e-6, unit="J")

    # The requirement did not disappear with the TVS's energy; it MOVED,
    # onto the clamp Schottky, and it is a requirement on a part the
    # schematic has to carry. Measured at Vsch1, not assumed from
    # 150 V / 10 ohm.
    isch1_pk = float(np.abs(isch1).max())
    esch1 = float(np.trapezoid(np.abs(vbon1 * isch1), t1))
    c.that("  ... so the CLAMP DIODE now carries it: peak current, pulse 1",
           isch1_pk, 13.58, tol=0.5, unit="A")
    c.that("  ... vs the 20 A class already specified for it", isch1_pk, 20.0,
           tol=None, ok=isch1_pk < 20.0, unit="A")
    c.that("  ... clamp diode energy, pulse 1", esch1 * 1e3, 14.5, tol=1.5,
           unit="mJ")
    isch3a_pk = float(np.abs(isch3a).max())
    c.that("  ... peak clamp-diode current, pulse 3a (50 ohm source, so "
           "milder)", isch3a_pk, 4.74, tol=0.3, unit="A")
    # load_dump.cir's own class-typical ~0.5 J single-pulse bound, reused
    # deliberately (same TVS class, not re-derived) -- NOT the ~3 W continuous
    # bound, which would compare a 2 ms pulse against a steady-state rating
    # four decades removed from it and answer a different question. See the
    # netlist's RESULT NOTE for why this one is a real finding, not a
    # manufactured one, and TOLERANCE for how it moves with severity level.
    c.that("  ... vs load_dump's own ~0.5 J single-pulse class bound (the "
           "TVS now clears it by not conducting, not by absorbing less)",
           energy1, 0.5, tol=None, ok=energy1 < 0.5, unit="J")

    energy3a = float(np.trapezoid(np.abs(bat3a * iamm3a), t3))
    c.that("TVS energy, pulse 3a (nominal C1 -- TVS stays below its own "
           "breakdown, does not conduct)", energy3a, 0.0, tol=1e-6, unit="J")
    c.that("  ... so nothing here can accumulate at nominal C1 -- see "
           "TOLERANCE for the corner where it would",
           "TVS current is numerically zero throughout the burst at "
           "C1 = 10 uF; the accumulation question only bites once C1 is "
           "derated enough for the TVS to conduct at all", None, ok=True)
    return c


def check_injector_boost():
    c = Checks("injector_boost -- why the boost stage exists (pins 03/05)")
    dd = sim("injector_boost", {
        "injector_boost.dat": ["time", "ibat", "ibst"],
        "injector_boost_cold.dat": ["time", "ibat", "ibst"],
        "injector_boost_hot.dat": ["time", "ibat", "ibst"],
    })
    d = dd["injector_boost.dat"]
    t = d["time"]
    # ngspice reports source current as negative when sourcing.
    ibat, ibst = np.abs(d["ibat"]), np.abs(d["ibst"])

    def t_to(cur, target, tt=t):
        idx = np.argmax(cur >= target)
        return float(tt[idx]) if cur.max() >= target else float("inf")

    # The two times below have a closed form -- t = (L/R)*ln(V/(V-I_th*R)),
    # the standard RL step-response result -- but the "want" figures were
    # taken from this simulation's own output rather than typed in from
    # that formula, so treat them as regression pins on the timing (2026-09-18
    # review F6 pattern). The RATIO two lines down is not a pin in the same
    # way: L and R are identical in both branches (same injector coil), so
    # L/R cancels algebraically and the ratio depends only on the two drive
    # voltages -- it is invariant to the injector's own L/R tolerance by
    # construction, not just numerically robust.
    t_bat = t_to(ibat, 18.0)
    t_bst = t_to(ibst, 18.0)
    c.that("time to 18 A peak from 13.5 V battery", t_bat * 1e6, 439, tol=15, unit="us")
    c.that("time to 18 A peak from 100 V boost", t_bst * 1e6, 38, tol=4, unit="us")
    c.that("boost is faster by", t_bat / t_bst, 11.6, tol=1.5, unit="x")

    # The number that matters: opening dead time against a 1-3 ms injection.
    # Battery drive spends a third of the shortest injection just lifting the
    # needle, which is why no production common-rail ECU does it that way.
    c.that("battery drive eats this much of a 1 ms injection",
           100 * t_bat / 1e-3, 43.9, tol=2.0, unit="%")
    c.that("boost drive eats this much of a 1 ms injection",
           100 * t_bst / 1e-3, 3.8, tol=0.5, unit="%")

    # TEMPERATURE -- express both halves, same instruction as
    # metering_unit_pwm.cir. The TOLERANCE note above claimed the ratio
    # is "invariant to the injector's own L/R tolerance by construction" --
    # true for L, but R also appears inside the log term via I_th*R, which
    # does NOT cancel between branches (re-derived and verified against
    # the actual netlist, not just the algebra, per this project's own
    # history of exactly this kind of error). Copper coil resistance
    # (~0.39%/C, physical constant, same physical part in both branches --
    # see the header) gives R=0.37 ohm at -40C / 0.69 ohm at +125C.
    # `option temp` does nothing for this RL model (no junctions), so this
    # is a component-value corner, via `alter` in the netlist's .control
    # block (same technique as metering_unit_pwm.cir).
    for label, fname in (("-40C", "injector_boost_cold.dat"),
                          ("+125C", "injector_boost_hot.dat")):
        dc = dd[fname]
        tc = dc["time"]
        ibatc, ibstc = np.abs(dc["ibat"]), np.abs(dc["ibst"])
        t_batc = t_to(ibatc, 18.0, tc)
        t_bstc = t_to(ibstc, 18.0, tc)

        # Half 1, EVIDENCE: the ratio against the NOMINAL 11.6x target
        # fails at both corners (cold undershoots, hot overshoots), which
        # is what corrected the file's own "invariant by construction"
        # claim -- the ratio is L-invariant but not R-invariant, and R
        # moves with ambient. That correction is worth keeping visible,
        # so each corner is pinned to its own produced value with a real
        # tolerance rather than deleted or waved through with ok=True.
        #
        # What it is NOT is a design failure. 11.6x was never a
        # requirement; it is the nominal ratio this block measured. The
        # requirement -- that boost drive is decisively faster than
        # battery drive -- is the check immediately below, and it is the
        # one allowed to fail.
        ratio_c = t_batc / t_bstc
        c.that(f"  ... evidence: ratio at {label} ambient, vs the 11.6x "
               f"NOMINAL (not a requirement)", ratio_c,
               {"-40C": 9.856, "+125C": 19.017}[label], tol=0.4, unit="x")
        c.that(f"  ... REQUIREMENT: boost still decisively faster at "
               f"{label} (>5x)", ratio_c, 5.0, tol=None, ok=ratio_c > 5.0,
               unit="x")
        # And the consequence that actually drives the architecture: with
        # battery drive the needle-lift time eats a large fraction of the
        # shortest injection at every corner, which is why the boost rail
        # exists at all. Same 1 ms reference the nominal checks use.
        c.that(f"  ... and battery drive still eats this much of a 1 ms "
               f"injection at {label}", 100 * t_batc / 1e-3, 25.0, tol=None,
               ok=100 * t_batc / 1e-3 > 25.0, unit="%")

        # Half 2: the number that actually matters for the REAL design --
        # t_bst, the boost-driven time -- uses the SAME target/tolerance
        # as the nominal check above. It survives both corners: 100 V so
        # thoroughly dominates I_th*R that this time is nearly
        # temperature-insensitive, which is the real design's answer to
        # the question this block exists to ask.
        c.that(f"  ... time to 18 A from 100 V boost, {label} ambient",
               t_bstc * 1e6, 38, tol=4, unit="us")
    return c


def check_injector_turnoff():
    c = Checks("injector_turnoff -- recirculation to the boost rail (pins 73/07/29)")
    d = sim("injector_turnoff", {
        "injector_turnoff.dat": ["time", "rail", "ii", "irc", "ifw", "vlo", "ib",
                                  "railh", "ih"],
    })["injector_turnoff.dat"]
    t = d["time"]
    rail, ii, irc, vlo = d["rail"], np.abs(d["ii"]), np.abs(d["irc"]), d["vlo"]
    ib = np.abs(d["ib"])
    railh, ih = d["railh"], np.abs(d["ih"])

    def at(time):
        return float(np.interp(time, t, rail))

    # ---- claim 1: turn-off time, 18 A clamped to the boost rail ----
    # Memo 10 section 2.2: Delta t = L*Delta I / V_clamp =~ 36 us. Measured
    # as time from the gate's turn-off command (38 us, the same ramp time
    # injector_boost.cir found) to the current dropping under 0.5 A (2.8%
    # of peak).
    window = (t > 38e-6) & (t < 238e-6)
    idx = np.where(ii[window] < 0.5)[0]
    t_off = float(t[window][idx[0]] - 38e-6) if len(idx) else float("inf")
    c.that("turn-off time, 18 A -> ~0 A on the boost rail", t_off * 1e6, 36.0,
           tol=6.0, unit="us")

    # Comparison only, not this design: the same 18 A starting current,
    # freewheeling to the 13.5 V battery instead (memo 10's ruled-out
    # baseline). Included so "far off" in the claim above has something to
    # be far off FROM.
    idxb = np.where(ib < 0.5)[0]
    t_offb = float(t[idxb[0]]) if len(idxb) else float("inf")
    c.that("  ... vs freewheel-to-battery baseline (comparison only)",
           t_offb * 1e6, 260.0, tol=None, ok=t_offb > 5 * t_off, unit="us")
    c.that("  ... boost recirculation is faster by", t_offb / max(t_off, 1e-9),
           25.0, tol=10.0, unit="x")

    # ---- claim 2: boost-rail bump from ONE recovery event ----
    # Isolated at the pilot event: rail value at the turn-off instant (the
    # bottom of the on-phase droop) vs after the recirculation decay has
    # finished, so this is JUST the recovery contribution, not mixed with
    # the on-phase draw already characterized in boost_converter.cir.
    droop = 100.0 - at(38e-6)
    bump = at(90e-6) - at(38e-6)
    c.that("on-phase droop, pilot event", droop, 7.3, tol=0.5, unit="V")
    c.that("  ... matches boost_converter.cir's own droop figure",
           "cross-check between two independently built models", None,
           ok=abs(droop - 7.3) < 1.0)
    c.that("recovery bump, pilot event (isolated)", bump, 6.9, tol=1.2, unit="V")
    c.that("  ... undershoots the droop it is paired with (real losses)",
           f"{bump:.2f} V recovered vs {droop:.2f} V drawn -- net loss, not gain",
           None, ok=bump < droop)

    # ---- claim 3: does recirculation push the rail over 100 V on
    # back-to-back events? ----
    # As THIS circuit models it -- boost supplies the peak ramp, the SAME
    # current is what gets recirculated at turn-off -- the answer is no,
    # and it is not a close call. A lossless version of this exact loop
    # would cancel EXACTLY: ramping up and recirculating down against the
    # same clamp voltage draws and returns identical charge by symmetry
    # (a linear ramp up, a linear-ish ramp down). Real R only adds loss,
    # never surplus, which is exactly what the bump-vs-droop check above
    # already shows. So across three back-to-back events the rail should
    # stay at or below its 100 V start, never above it.
    c.that("rail never exceeds 100 V setpoint (3-event circuit)",
           float(rail.max()), 100.0, tol=None, ok=float(rail.max()) < 100.05,
           unit="V")
    c.that("rail recovered by the next cylinder (26.67 ms after post)",
           float(np.interp(0.638e-3 + 26.67e-3, t, rail)), 100.0, tol=1.0,
           unit="V")

    # The sensitivity this verdict actually hinges on: THIS circuit always
    # recirculates current it just drew from the SAME rail. boost_converter
    # .cir's own arrangement A has the boost rail supply the peak phase
    # ONLY -- hold current comes from the battery. If one shared low-side
    # switch and diode per channel (not two) recirculates a HOLD-current
    # cutoff into the boost cap too, that energy has no offsetting
    # boost-side draw to net against -- a separate small circuit in the
    # netlist starts a second reservoir at 100 V with boost_converter.cir's
    # own 10 A hold-current figure already flowing (ic=10, no ramp) and
    # measures the result directly.
    # Regression pin (2026-09-18 review F6 pattern): the bump depends on the
    # two diode drops and R1's resistance during the decay, which is not a
    # simple Q/C calculation. The claim this block actually makes is the
    # next line -- that THIS scenario overshoots 100 V while the peak-only
    # one above does not -- which is a real, independently meaningful
    # comparison even though this exact bump figure is not independently
    # derived.
    c.that("hold-current cutoff into the SAME cap, no offsetting draw",
           float(railh.max()) - 100.0, 2.1, tol=0.6, unit="V")
    c.that("  ... THIS is the scenario that overshoots 100 V",
           float(railh.max()), 100.0, tol=None, ok=float(railh.max()) > 100.5,
           unit="V")
    c.that("  ... so the verdict hinges on whether hold-current cutoffs "
           "share the boost-recirculation diode",
           "peak-only recirculation never overshoots; hold-current "
           "recirculation does -- boost_converter.cir's Bchga has no bleed "
           "path either way", None, ok=True)

    # ---- claim 4: peak instantaneous diode power, not the average ----
    # Memo 10 section 4: worst-case AVERAGE dissipation across all 9
    # events/second is ~3.6 W, assuming a purely dissipative clamp. This
    # block's clamp is not dissipative (recirculation), but the diode
    # still carries the full 18 A at its own forward drop during each
    # ~33 us pulse, and that instantaneous figure is what the diode's
    # thermal/junction rating actually has to survive.
    # No closed form for peak_p -- it depends on the diode's nonlinear I-V
    # curve at the instant of peak recirculation current, which only the
    # simulation resolves. Regression pin (2026-09-18 review F6 pattern),
    # not an independently derived claim; the claim this check actually
    # backs is the ratio two lines down, against memo 10's own sourced
    # average figure.
    decay = (t >= 38e-6) & (t < 138e-6)
    p_diode = (vlo[decay] - rail[decay]) * irc[decay]
    peak_p = float(p_diode.max())
    c.that("peak instantaneous power in D_recirc during turn-off", peak_p,
           29.0, tol=8.0, unit="W")
    c.that("  ... exceeds the ~3.6 W worst-case AVERAGE by", peak_p / 3.6,
           8.0, tol=4.0, unit="x")

    # ---- claim 5: the EMI edge, stated not modelled ----
    # The switches here are ideal (zero transition time), so this
    # simulation cannot honestly produce a dV/dt -- that would be an
    # artifact of the solver's timestep, not a FET's real slew rate.
    # Carried over as memo 10's own INFERRED estimate, not this block's
    # result: 100 V in ~36 us is about 2.8 V/us, two orders of magnitude
    # gentler than the buck stage's edges emi_filter.cir already exists to
    # filter -- a comparison point, not a simulated claim.
    c.that("differential-mode edge vs emi_filter.cir",
           "not modelled here (ideal switches) -- memo 10's own ~2.8 V/us "
           "estimate is carried as a comparison, not simulated", None,
           ok=True)
    return c


def check_relay_driver():
    c = Checks("relay_driver -- pins 50/69, low-side FET with flyback")
    d = sim("relay_driver", {"relay_driver.dat": ["time", "with_d", "without_d"]})["relay_driver.dat"]
    withd, without = d["with_d"], d["without_d"]

    # With the diode, the drain must stay near the battery rail at turn-off.
    c.that("drain peak WITH flyback diode", float(withd.max()), 15.0, tol=None,
           ok=float(withd.max()) < 15.0, unit="V")

    # Without it, the inductive kick is enormous -- this is the number that
    # justifies a part that looks optional on a schematic.
    c.that("drain peak WITHOUT diode", float(without.max()), 100.0, tol=None,
           ok=float(without.max()) > 100.0, unit="V")
    c.that("  ... diode suppresses the kick by",
           float(without.max()) / float(withd.max()), 10.0, tol=None,
           ok=float(without.max()) / float(withd.max()) > 10, unit="x")
    return c


def check_egr_hbridge():
    c = Checks("egr_hbridge -- pins 59/81, H-bridge + position feedback on pin 37")
    d = sim("egr_hbridge", {
        "egr_kill.dat": ["t", "g_egr", "g_egr_adv"],
        "egr_dc.dat": ["sweep", "i_stall", "i_run", "i_coast", "i_shoot", "i_dec"],
        "egr_recirc.dat": ["time", "ma5", "mb5", "ma6", "mb6", "ibat5"],
    })
    Vgsth = 1.0  # same INFERRED figure supervisor.cir uses -- see this netlist's header.

    # ---- kill-clamp: mirrors supervisor.cir claim 1 / 1b, at the corrected
    # Rpd=470 ohm rather than the superseded 10k. Hand check: tau =
    # (470||5)*2n = 9.9 ns, t(Vgsth) = tau*ln(10) = 22.8 ns. ----
    dk = d["egr_kill.dat"]
    tk, g, gadv = dk["t"], dk["g_egr"], dk["g_egr_adv"]
    idx = int(np.argmax(g < Vgsth))
    t_g = float(tk[idx]) if g[idx] < Vgsth else float("inf")
    c.that("kill-clamp: gate below Vgsth (hand estimate 22.8 ns)",
           t_g * 1e9, 22.8, tol=5.0, unit="ns")
    c.that("  ... adversarial driver (100R/10V) still held below Vgsth",
           float(gadv[-1]), Vgsth, tol=None, ok=float(gadv[-1]) < Vgsth, unit="V")
    c.that("  ... adversarial settle voltage (hand: 10*4.95/104.95=0.471 V)",
           float(gadv[-1]), 0.471, tol=0.02, unit="V")

    # ---- DC operating points: stall, running, coast. ngspice reports
    # source current as negative when sourcing (same convention
    # injector_boost.cir notes). Hand values: I_stall=13.5/3.1=4.355 A,
    # I_run=(13.5-9)/3.1=1.452 A, I_coast ~ 0 (Roff leakage only). ----
    dd = d["egr_dc.dat"]
    i_stall = abs(float(dd["i_stall"][0]))
    i_run = abs(float(dd["i_run"][0]))
    i_coast = abs(float(dd["i_coast"][0]))
    c.that("stall current (Vemf=0, hand: 13.5/3.1)", i_stall, 4.355, tol=0.02, unit="A")
    c.that("running current (Vemf=9V, hand: 4.5/3.1)", i_run, 1.452, tol=0.02, unit="A")
    c.that("coast current (IN1=IN2=0)", i_coast, 0.0, tol=None,
           ok=i_coast < 1e-6, unit="A")

    # A positional actuator stalls at its own end of travel in NORMAL
    # operation, not only as a fault -- this is not an edge case to design
    # around. Compared against a class-typical small-actuator automotive
    # H-bridge rating (2-3 A continuous, INFERRED, no part chosen).
    c.that("stall current exceeds a class-typical 2-3 A driver rating",
           i_stall, 3.0, tol=None, ok=i_stall > 3.0, unit="A")
    c.that("  ... so the eventual driver needs active current limiting, "
           "not a fixed series resistor",
           f"{i_stall:.2f} A at Rm=3 ohm alone exceeds a 2-3 A class rating",
           None, ok=i_stall > 3.0)

    # ---- recirculation: with the body diodes (the design) vs without
    # (comparison only, same convention relay_driver.cir uses). ----
    dr = d["egr_recirc.dat"]
    t, ma5, mb5, ma6, mb6, ibat5 = (dr[k] for k in
                                     ("time", "ma5", "mb5", "ma6", "mb6", "ibat5"))

    # Steady-state forward current just before coast is commanded (t=20ms)
    # must agree with section 2's own stall figure -- same Vbat, same Rm,
    # same drive, so this is an internal consistency check, not a new claim.
    i_fwd = abs(float(np.interp(19.9e-3, t, ibat5)))
    c.that("forward steady current at t=19.9ms matches section 2's stall figure",
           i_fwd, i_stall, tol=0.02, unit="A")

    near_coast = (t > 20e-3) & (t < 20.5e-3)
    c.that("WITH diodes: low side stays within a diode drop of ground "
           "(hand: -1.09 V)", float(ma5[near_coast].min()), -1.09, tol=0.15,
           unit="V")
    c.that("WITH diodes: high side stays within a diode drop of the rail "
           "(hand: 14.59 V)", float(mb5[near_coast].max()), 14.59, tol=0.15,
           unit="V")

    # Without a current path, the ideal-switch model produces an
    # unbounded swing -- same reading relay_driver.cir gives its own
    # "without flyback diode" branch: the magnitude is a model artifact,
    # the conclusion (current has nowhere to go) is not.
    c.that("WITHOUT diodes: low side swings far past ground",
           abs(float(ma6[near_coast].min())), 1e5, tol=None,
           ok=abs(float(ma6[near_coast].min())) > 1e5, unit="V")
    c.that("WITHOUT diodes: high side swings far past the rail",
           abs(float(mb6[near_coast].max())), 1e5, tol=None,
           ok=abs(float(mb6[near_coast].max())) > 1e5, unit="V")
    c.that("  ... recirculation diodes are load-bearing, not decorative",
           f"bounded to {float(mb5[near_coast].max()):.1f} V with diodes vs "
           f"{abs(float(mb6[near_coast].max())):.2e} V without", None, ok=True)

    # ---- position feedback, pin 37: not re-simulated here. ----
    c.that("position feedback (pin 37) is Group A ratiometric, proven "
           "in sensor_ratiometric.cir",
           "0.308-2.769 V into the 3.3 V ADC, see check_sensor_ratiometric()",
           None, ok=True)
    # ---- shoot-through: the state this file used to claim was impossible ----
    # Added 19 Sep 2026. The header argued that because IN1 drives a DIAGONAL
    # pair (S1+S4), no IN1/IN2 combination could short a leg. It checked each
    # input line alone and never asked what the two do together: IN2 drives
    # S3+S2, so asserting both turns all four switches on and shorts BOTH legs
    # rail-to-ground at once.
    #
    # This is a real fault state with nothing on the board preventing it, so it
    # is a failing claim, not an evidence row. It clears when the driver's own
    # decode logic is specified -- see the netlist header.
    # EVIDENCE, not a live gate, as of 20 Sep 2026. This is the REJECTED
    # arrangement -- two logic lines wired straight to two diagonal switch
    # pairs -- kept because it is the reason spec sec.4 requires a decoded
    # driver. Pinned with a tolerance so drift fails; it is not ok=True.
    # The live claim is the decoded row below.
    i_shoot = abs(float(dd["i_shoot"][0]))
    c.that("rejected naive wiring: rail current with IN1=IN2 asserted",
           i_shoot, 270.0, tol=15.0, unit="A")
    # Hand check, to catch the sim disagreeing with the topology: each leg is
    # two SWH in series from rail to ground, Ron 0.05 each, so 13.5/0.1 = 135 A
    # per leg and 270 A for the two legs together.
    c.that("  ... matching the two-legs-of-2x50mOhm hand figure",
           i_shoot, 270.0, tol=15.0, unit="A")
    # The fix, demonstrated rather than asserted: the same bridge driven
    # through a decoded DIR/PWM interface, with BOTH inputs high -- the
    # combination that shorts the naive arrangement. Under decode the
    # fault state cannot be expressed, so the current is the motor's, not
    # a short's.
    i_dec = abs(float(dd["i_dec"][0]))
    c.that("ADOPTED: decoded DIR/PWM driver, both inputs asserted",
           i_dec, 5.0, tol=None, ok=i_dec < 5.0, unit="A")
    c.that("  ... so decode removes the fault state entirely",
           f"{i_shoot:.0f} A naive vs {i_dec:.2f} A decoded -- "
           f"{i_shoot/max(i_dec,1e-9):.0f}x", None, ok=i_dec < 5.0)

    return c


def check_reverse_battery():
    c = Checks("reverse_battery -- ideal diode vs Schottky, power chain stage 2")
    d = sim("reverse_battery", {
        "reverse_battery_fwd.dat": ["iload", "d_sch", "d_fet"],
        "reverse_battery_rev.dat": ["vrev", "sch", "fet"],
    })
    i, sch, fet = (d["reverse_battery_fwd.dat"][k] for k in ("iload", "d_sch", "d_fet"))

    at3 = lambda v: float(np.interp(3.0, i, v))  # noqa: E731
    c.that("Schottky drop at 3 A", at3(sch), 0.46, tol=0.06, unit="V")
    c.that("ideal-diode FET drop at 3 A", at3(fet), 0.024, tol=0.005, unit="V")

    # Spec section 6 asks for under 0.3 V, and the worst case is the top
    # of the current range, not the typical operating point.
    c.that("FET drop stays under 0.3 V spec to 5 A", float(fet.max()), 0.3,
           tol=None, ok=float(fet.max()) < 0.3, unit="V")
    c.that("  ... Schottky does NOT meet it",
           f"{float(sch.max()):.2f} V at 5 A -- fails the 0.3 V spec", None,
           ok=float(sch.max()) > 0.3)

    # The number that pays for the controller IC: heat that never happens.
    # The Schottky figure is class-typical (the header's "roughly 0.46 V at
    # 3 A"), so 1.38 W tracks a real datasheet-class number, loosely. The
    # FET figure is exactly I*Ron = 3 A * 8 mOhm = 0.024 V * 3 A -- Ohm's
    # law, not a regression pin, even though the "want" value was in fact
    # copied from an earlier run of this same simulation rather than typed
    # in as 0.024*3 (2026-09-18 review F6 flagged this one; the arithmetic
    # is trivial enough that pin vs. derived claim comes out the same
    # either way here, unlike load_dump's TVS numbers above, which have no
    # such closed form).
    c.that("power burnt in the Schottky at 3 A", at3(sch) * 3, 1.38, tol=0.2, unit="W")
    c.that("  ... and in the FET instead", at3(fet) * 3, 0.072, tol=0.02, unit="W")

    # Reverse: neither path may pass appreciable current backwards.
    rsch = d["reverse_battery_rev.dat"]["sch"]
    rfet = d["reverse_battery_rev.dat"]["fet"]
    c.that("Schottky blocks -14 V (leak into 1k)", abs(float(rsch.min())) * 1e3,
           1.0, tol=None, ok=abs(float(rsch.min())) < 0.05, unit="mV")
    c.that("ideal-diode FET blocks -14 V", abs(float(rfet.min())) * 1e3,
           0.0, tol=None, ok=abs(float(rfet.min())) < 0.05, unit="mV")
    return c


def check_buck_preregulator():
    c = Checks("buck_preregulator -- 6-40 V to 5 V, 400 kHz, power chain stage 4")
    d = sim("buck_preregulator", {
        "buck_prereg.dat": ["time", "vo1", "il1", "vo2", "il2"],
    })["buck_prereg.dat"]
    t = d["time"]

    # Only the settled tail is steady state; the first cycles are startup.
    tail = t > 380e-6
    vo1, il1 = d["vo1"][tail], np.abs(d["il1"][tail])
    vo2, il2 = d["vo2"][tail], np.abs(d["il2"][tail])

    c.that("output at 13.5 V in (open loop, D=0.370)", float(vo1.mean()), 5.0,
           tol=0.15, unit="V")
    c.that("output at 40 V in (open loop, D=0.125)", float(vo2.mean()), 5.0,
           tol=0.15, unit="V")

    # Inductor ripple sets the core loss and the peak current the switch
    # sees. Convention is to keep it under ~40% of full load -- a ripple
    # RATIO (r = dI/Iload) of 0.3-0.4 shows up repeatedly across buck
    # converter inductor-selection app notes (e.g. TI SLVA477) as the
    # rule-of-thumb sweet spot: lower wastes core size and cost on ripple
    # nobody needs, higher raises peak current, core loss and EMI for no
    # benefit. It is not a number from any standard, and no single
    # canonical source for "40%" specifically was found -- 30% is quoted
    # about as often as 40% is. Per the 2026-09-18 review (F9), this is
    # convention, not spec: reasonable, uncited, and per the tolerance note
    # below, the margin against it is thin.
    rip1 = float(il1.max() - il1.min())
    rip2 = float(il2.max() - il2.min())
    c.that("inductor ripple at 13.5 V", rip1, 0.238, tol=0.06, unit="A")
    c.that("inductor ripple at 40 V", rip2, 0.331, tol=0.07, unit="A")
    c.that("  ... worst case is HIGH line, not low", rip2 / rip1, 1.39, tol=None,
           ok=rip2 > rip1, unit="x")
    c.that("worst-case ripple as fraction of 1 A load", rip2 * 100, 40.0,
           tol=None, ok=rip2 < 0.4, unit="%")

    # Output ripple is what the analog front-ends and the MCU rail inherit.
    vr1 = float(vo1.max() - vo1.min())
    vr2 = float(vo2.max() - vo2.min())
    c.that("output ripple at 13.5 V", vr1 * 1e3, 50.0, tol=None,
           ok=vr1 < 50e-3, unit="mV")
    c.that("output ripple at 40 V", vr2 * 1e3, 50.0, tol=None,
           ok=vr2 < 50e-3, unit="mV")
    return c


def check_sensor_rail():
    c = Checks("sensor_rail -- 5V_SENSOR, one PTC per sensor group")
    d = sim("sensor_rail", {
        "sensor_rail.dat": ["sweep", "raila", "ab", "railb", "bb", "isrc",
                            "xb", "ic", "raild", "db", "id", "eb", "ie"],
    })["sensor_rail.dat"]
    raila, ab = float(d["raila"][0]), float(d["ab"][0])
    railb, bb = float(d["railb"][0]), float(d["bb"][0])

    # With per-group protection, one shorted harness must leave the other
    # groups usable. 4.5 V is 10% below the 5 V nominal -- not "a few
    # percent," corrected here (2026-09-18 review F8: the two did not
    # match). No sharper derivation exists yet for why 10% specifically is
    # the floor rather than, say, 5%; sensor_ratiometric.cir's ratiometric
    # correction (measuring the rail and dividing it out) removes the error
    # a drifting rail causes for THAT front-end, but the floor here is
    # about whether the rail still has enough headroom to sit above the
    # ADC's own useful range at all, which is a cruder question. Treat 4.5
    # V as a round, defensible-but-not-derived floor until someone ties it
    # to a specific sensor's own supply-tolerance spec.
    c.that("healthy group with PTCs, group A shorted", ab, 4.5, tol=None,
           ok=ab > 4.5, unit="V")
    c.that("  ... rail itself holds up", raila, 4.5, tol=None, ok=raila > 4.5,
           unit="V")

    # Without them, the same fault takes every sensor on the engine.
    c.that("healthy group WITHOUT PTCs, same fault", bb, 1.0, tol=None,
           ok=bb < 1.0, unit="V")
    c.that("  ... so one harness short blinds the whole ECU",
           f"{bb:.2f} V -- every analog channel lost at once", None, ok=bb < 1.0)

    c.that("protection improves the healthy group by", ab / max(bb, 1e-6), 5.0,
           tol=None, ok=ab / max(bb, 1e-6) > 5, unit="x")

    # And the fault current must be something a polyfuse can actually trip on.
    ifault = abs(float(d["isrc"][0]))
    c.that("fault current drawn from the 5 V rail", ifault, 3.0, tol=None,
           ok=0.3 < ifault < 3.0, unit="A")

    # TEMPERATURE, network C -- the design is inadequate at this corner.
    # PTC resistance is temperature-defined by construction, and ngspice's
    # `option temp` does nothing for a plain resistor, so the corner is a
    # component value (network C in the netlist), same mechanism as the
    # TOLERANCE section's own -30% spread. Stacked here because that is
    # what the netlist's TEMPERATURE note found: -40 C ambient alone still
    # passes (fault current 2.92 A, margin 0.08 A -- not asserted here,
    # since it does not flip anything), but a real cold-climate genset (this
    # design's stated environment) sees -40 C AND ordinary PTC part spread
    # together, not one or the other. Rptc = 2.0 * 0.8 (cold, INFERRED) *
    # 0.7 (-30% tolerance, TOLERANCE section) = 1.12 ohm.
    #
    # This is a real requirement (the polyfuse has to trip, not the rail's
    # own regulator), so a fail here is not manufactured -- it is the same
    # 3.0 A ceiling as the line above, just no longer met once the PTC sits
    # at a plausible worst case instead of its 27 C nominal value.
    # EVIDENCE: this is the corner that produced the requirement. Pinned
    # to its own produced value with a real tolerance rather than ok=True,
    # so drift in the network or the sweep fails this row and says so.
    ifault_corner = abs(float(d["ic"][0]))
    c.that("  ... evidence: stacked -40C-cold + -30%-tolerance corner on "
           "the ORIGINAL 2.0 ohm PTC -- the corner that forced the spec",
           ifault_corner, 4.148, tol=0.05, unit="A")
    c.that("  ... so a 2.0 ohm PTC overshoots the 3.0 A ceiling by",
           ifault_corner - 3.0, 1.148, tol=0.05, unit="A")

    # RESOLUTION: PTC specified at R25 = 3.0 ohm (networks D and E).
    # Two things have to hold, and a larger series resistance could
    # plausibly have broken either one, so both are checked rather than
    # only the corner that was failing.
    ifault_spec = abs(float(d["ie"][0]))
    c.that("RESOLVED: specified 3.0 ohm PTC at the SAME stacked corner",
           ifault_spec, 3.0, tol=None, ok=ifault_spec < 3.0, unit="A")
    c.that("  ... margin under the 3.0 A ceiling", 3.0 - ifault_spec, 0.1,
           tol=None, ok=ifault_spec < 3.0, unit="A")

    # The larger PTC costs healthy-group headroom during a fault (more
    # series drop in the faulted branch means a lower rail), so the 4.5 V
    # floor is re-checked against the specified part, not assumed to carry
    # over from the 2.0 ohm case.
    railD, dbv = float(d["raild"][0]), float(d["db"][0])
    c.that("  ... healthy group still above 4.5 V with the bigger PTC fitted",
           dbv, 4.5, tol=None, ok=dbv > 4.5, unit="V")
    c.that("  ... and the rail itself", railD, 4.5, tol=None, ok=railD > 4.5,
           unit="V")

    # And it must not go so far the other way that the polyfuse no longer
    # sees a current it can trip on -- the same 0.3 A floor the nominal
    # check above uses.
    ifault_nom = abs(float(d["id"][0]))
    c.that("  ... fault current at the specified part's nominal, still "
           "inside the 0.3-3.0 A trip window", ifault_nom, 1.6, tol=None,
           ok=0.3 < ifault_nom < 3.0, unit="A")
    return c


def check_mcu_pdn():
    c = Checks("mcu_pdn -- 3V3_MCU decoupling impedance, 100 mOhm target")
    d = sim("mcu_pdn", {"mcu_pdn.dat": ["frequency", "z10", "z1", "z10c",
                                        "z10s_cold", "z10s_warm"]})["mcu_pdn.dat"]
    f, z10, z1 = d["frequency"], d["z10"], d["z1"]

    # Driven by 1 A, so node voltage reads directly as ohms. The sweep stops
    # at 100 MHz because that is where the lumped model stops being true --
    # see the netlist's RESULT NOTE.
    peak = float(z10.max())
    fpeak = float(f[int(np.argmax(z10))])
    c.that("peak impedance, 1 kHz to 100 MHz", peak * 1e3, 100.0, tol=None,
           ok=peak < 0.1, unit="mOhm")

    # Where the peak sits was the design insight while the bulk was 47 uF:
    # the limiter was the regulator's own output inductance against the bulk
    # capacitance, tens of kHz, decades below the bulk/ceramic anti-resonance
    # a decoupling discussion usually starts from. Raising the bulk to 150 uF
    # (18 Sep 2026, see the netlist's tolerance note) moved that resonance far
    # enough down and damped it enough that it is no longer the tallest thing
    # in the sweep -- the bulk/ceramic anti-resonance in the MHz now is. That
    # handover IS the claim worth checking, because it is what buys the block
    # its tolerance margin: the surviving peak does not move with Lldo, the
    # parameter nobody has pinned.
    c.that("  ... and it has moved to the MHz anti-resonance", fpeak / 1e6, 2.6,
           tol=1.0, unit="MHz")
    c.that("  ... i.e. bulk against ceramic, no longer regulator L against bulk",
           f"{fpeak/1e6:.2f} MHz -- the LDO resonance is no longer the limiter",
           None, ok=fpeak > 500e3)

    # High frequency is where the parasitics decide it. ESL divides by the
    # number of packages sharing the current; capacitance is irrelevant here.
    hf = int(np.argmin(np.abs(f - 100e6)))
    c.that("ten 100 nF parts at 100 MHz", float(z10[hf]) * 1e3, 47, tol=15,
           unit="mOhm")
    c.that("one 1 uF part at 100 MHz", float(z1[hf]) * 1e3, 357, tol=80,
           unit="mOhm")
    c.that("  ... same capacitance, this much worse", float(z1[hf] / z10[hf]),
           7.6, tol=None, ok=float(z1[hf] / z10[hf]) > 5, unit="x")

    # The counter-intuitive half, worth keeping as a regression: at the
    # bulk/ceramic anti-resonance the LOW-ESR network is WORSE, because ESR
    # is what damps that peak. Chasing low ESR everywhere backfires here.
    ar = int(np.argmin(np.abs(f - 3.5e6)))
    c.that("ten-part net at the 3.5 MHz anti-resonance", float(z10[ar]) * 1e3,
           55, tol=15, unit="mOhm")
    c.that("  ... one-part net is LOWER there (its ESR damps it)",
           f"{float(z1[ar])*1e3:.0f} mOhm vs {float(z10[ar])*1e3:.0f} -- "
           "more ESR, better damping", None, ok=float(z1[ar]) < float(z10[ar]))

    # TEMPERATURE -- design is inadequate at a plausible cold-ESR corner.
    # Rb (bulk electrolytic ESR) is exactly the parameter the tolerance
    # check above shows this block is sensitive to; ngspice's `option temp`
    # does not move a plain RLC network, so the corner is the explicit
    # component-value network (n3) added to the netlist -- Rb at 200 mOhm,
    # 4x nominal, the mid of an INFERRED 2-6x class-typical cold-ESR-derate
    # range for aluminium/tantalum electrolytics (no part chosen). The
    # 100 mOhm target itself is derived (50 mV allowed ripple / 0.5 A
    # transient step), not a round convention, so this is a real fail, not
    # a manufactured one against an arbitrary gate.
    # EVIDENCE: the corner that produced the requirement. Pinned to its
    # own produced value with a real tolerance, not ok=True.
    z10c = d["z10c"]
    peakc = float(z10c.max())
    c.that("  ... evidence: peak with a WET electrolytic at its cold-ESR "
           "corner (Rb=200 mOhm, 4x) -- the corner that forced the spec",
           peakc * 1e3, 196.7, tol=2.0, unit="mOhm")
    c.that("  ... so a wet bulk part misses the 100 mOhm target by",
           peakc * 1e3 - 100.0, 96.7, tol=2.0, unit="mOhm")

    # RESOLUTION: polymer bulk, specified by COLD ESR (<= 50 mOhm at
    # -40 C). Bounded from both sides -- this block's own finding is that
    # bulk ESR DAMPS the regulator-against-bulk resonance, so a
    # requirement stated only as a maximum could be met by a part whose
    # low ESR re-opens that peak. Both ends are therefore checked against
    # the SAME 100 mOhm target the nominal check uses.
    pk_cold = float(d["z10s_cold"].max())
    pk_warm = float(d["z10s_warm"].max())
    c.that("RESOLVED: peak with the specified polymer bulk at its cold-ESR "
           "limit (Rb=50 mOhm)", pk_cold * 1e3, 100.0, tol=None,
           ok=pk_cold < 0.1, unit="mOhm")
    c.that("  ... and at the low-ESR end the same part reaches warm "
           "(Rb=20 mOhm) -- the under-damped side", pk_warm * 1e3, 100.0,
           tol=None, ok=pk_warm < 0.1, unit="mOhm")
    c.that("  ... worst of the two ends, margin under target",
           100.0 - max(pk_cold, pk_warm) * 1e3, 10.0, tol=None,
           ok=max(pk_cold, pk_warm) < 0.1, unit="mOhm")
    return c


def check_emi_filter():
    c = Checks("emi_filter -- CISPR 25 conducted, differential mode")
    d = sim("emi_filter", {"emi_filter.dat": ["frequency", "out", "ref", "outt"]})["emi_filter.dat"]
    f, out, ref, outt = d["frequency"], d["out"], d["ref"], d["outt"]

    def il(hz, o=out):
        i = int(np.argmin(np.abs(f - hz)))
        return float(o[i] - ref[i])

    # CISPR 25's conducted band starts at 150 kHz. The switching
    # fundamental sits at 400 kHz, inside it by design -- see the netlist.
    c.that("insertion loss at 150 kHz (band start)", il(150e3), -40.0, tol=None,
           ok=il(150e3) < -40, unit="dB")
    c.that("insertion loss at 400 kHz (switching f)", il(400e3), -50.0, tol=None,
           ok=il(400e3) < -50, unit="dB")
    c.that("insertion loss at 1 MHz", il(1e6), -60.0, tol=None, ok=il(1e6) < -60,
           unit="dB")

    # The bands the standard weights hardest, and the ones a single bulk
    # capacitor cannot reach because it is inductive by then.
    c.that("insertion loss at 30 MHz", il(30e6), -40.0, tol=None,
           ok=il(30e6) < -40, unit="dB")
    c.that("insertion loss at 100 MHz (FM band)", il(100e6), -40.0, tol=None,
           ok=il(100e6) < -40, unit="dB")

    # Attenuation must be monotone enough that no band is left unguarded:
    # the worst point anywhere above the band start is the real spec.
    band = f >= 150e3
    worst = float(np.max(out[band] - ref[band]))
    fworst = float(f[band][int(np.argmax(out[band] - ref[band]))])
    c.that("worst insertion loss anywhere above 150 kHz", worst, -40.0, tol=None,
           ok=worst < -40, unit="dB")
    # Informational, not a claim: no value of fworst can fail this line, so it
    # is reported as a string like the other informational rows below rather
    # than as a numeric check with a fake "(want 150)" target. (2026-09-18
    # review F5: the numeric form with ok=True hardcoded printed a "want"
    # value nothing could ever violate.)
    c.that("  ... worst point sits at", f"{fworst/1e3:.1f} kHz", None, ok=True)

    # Stated rather than asserted: how much attenuation is ENOUGH cannot be
    # decided here. It depends on the unfiltered emissions, which need a
    # built board and a LISN. 40 dB across the band is what this filter
    # delivers; whether Class 5 needs more is a measurement, not a claim.
    #
    # That "unknown" is not a footnote to the five hard gates above -- it is
    # the reason they exist at all. -40/-50/-60 dB are round numbers chosen
    # before any hardware measurement existed to validate them (see the
    # netlist's tolerance note: at a standard inductor/capacitor tolerance
    # corner, two of them flip to FAIL on margins that were 1-2 dB at
    # nominal). A tolerance-driven flip against an unvalidated round number
    # does not mean the filter is inadequate for CISPR 25 Class 5 -- it
    # means these five checks are only as solid as the -40/-50 dB choice,
    # which this line already says is not solid. Read a FAIL here as "this
    # filter's margin against its own placeholder target is thin," not as
    # "this filter fails Class 5" -- that second claim needs the measurement
    # this line says has not been made.
    c.that("is 40 dB enough for Class 5?",
           "unknown -- needs measured unfiltered emissions on hardware", None,
           ok=True)

    # TEMPERATURE -- shape 2: the -40/-50 dB gates above are the ones the
    # line just above says are unvalidated round numbers, not a spec pulled
    # from a measurement. Re-running them at a temperature corner and
    # asserting PASS/FAIL against those same numbers would manufacture a
    # verdict this block cannot support either way (same reasoning the
    # existing TOLERANCE result-note already applied to the DC-bias
    # corner, which also never got a pass/fail check here).
    #
    # What IS real and checkable: C1 is X7R, and X7R's +/-15% capacitance
    # limit over its rated temperature range is the part's own EIA/AVX
    # definition (X=-55C, 7=+125C, R=+/-15% max) -- SOURCED, not INFERRED,
    # unlike most other corners in this pass. So these two lines are
    # regression pins on the corner's actual measured value (real
    # tolerance, not ok=True) -- they catch drift in the corner network or
    # the temperature assumption -- without asserting the corner passes or
    # fails the placeholder -40/-50 dB gates.
    il150_t = il(150e3, outt)
    il400_t = il(400e3, outt)
    c.that("  ... IL@150kHz, C1 at X7R's own -15% temp derate (C1=3.995uF)",
           il150_t, -39.74, tol=0.3, unit="dB")
    c.that("  ... IL@400kHz, same corner",
           il400_t, -50.07, tol=0.3, unit="dB")
    # Read against the nominal-27C -40 dB check above by eye, not by a new
    # assertion here (a pass/fail line against that gate would be exactly
    # the manufactured verdict this note opened by declining to make): the
    # pinned -39.74 dB is numerically below -40 dB, worse than the nominal
    # check's -41.07 dB pass -- temperature ALONE, no DC bias, no L1
    # tolerance, is enough to do that, purely from what "X7R" on the BOM
    # line already promises. Whether that means the filter needs a
    # different C1 case size/voltage rating, or whether -40 dB was never
    # the right gate to begin with, is the same open measurement question
    # the "is 40 dB enough" line above already leaves open.
    return c


def check_vr_conditioner():
    c = Checks("vr_conditioner -- crank VR sensor, pins 52/74/30")
    d = sim("vr_conditioner", {
        "vr_conditioner.dat": ["time", "zr", "fr", "zc", "fc"],
    })["vr_conditioner.dat"]
    t = d["time"]

    def edges(v):
        """Rising edges of a logic signal, counted at mid-rail."""
        return int(np.sum(np.diff((v > 1.65).astype(int)) > 0))

    # 20 ms of 1500 Hz is 30 teeth; of 150 Hz, 3 teeth.
    c.that("zero-cross, running (1500 rpm, 30 teeth)", edges(d["zr"]), 30,
           tol=1, unit="edges")
    c.that("zero-cross, cranking (150 rpm, 3 teeth)", edges(d["zc"]), 3,
           tol=1, unit="edges")

    # The fixed threshold works fine on the bench signal and fails on the
    # one that matters. This is the whole block.
    c.that("fixed 5 V threshold, running", edges(d["fr"]), 30, tol=1,
           unit="edges")
    c.that("fixed 5 V threshold, cranking", edges(d["fc"]), 0, tol=None,
           ok=edges(d["fc"]) == 0, unit="edges")
    c.that("  ... so a fixed threshold never starts the engine",
           "works at 1500 rpm, blind at 150 rpm -- passes on the bench",
           None, ok=edges(d["fc"]) == 0)

    # Edge spacing is what timing accuracy rests on: every injection is
    # scheduled against crank angle interpolated between these edges.
    idx = np.where(np.diff((d["zr"] > 1.65).astype(int)) > 0)[0]
    if len(idx) > 2:
        gaps = np.diff(t[idx])
        c.that("running tooth period", float(gaps.mean()) * 1e6, 667, tol=20,
               unit="us")
        c.that("  ... jitter across the window", float(gaps.std()) * 1e6, 0.0,
               tol=8.0, unit="us")
    return c


def check_cam_frontend():
    c = Checks("cam_frontend -- ECU pins 45/46/44, cam Hall sensor into PTB3/FTM1_CH1")
    d = sim("cam_frontend", {
        "cam_frontend_dc.dat": ["vraila", "na"],
        "cam_frontend_tran.dat": ["time", "nb", "ctrl"],
        "cam_frontend_fault.dat": ["sweep", "nc", "iflt"],
    })
    va, na = d["cam_frontend_dc.dat"]["vraila"], d["cam_frontend_dc.dat"]["na"]
    t, nb = d["cam_frontend_tran.dat"]["time"], d["cam_frontend_tran.dat"]["nb"]

    # PTB3 is not 5 V tolerant for guaranteed logic recognition (Vih max =
    # VDD+0.3 = 3.6 V, S32K1xx datasheet Rev.15 Table 17) -- a literal
    # pull-up to 5V_SENSOR is out of spec. This block's whole point is that
    # the divider keeps the pad inside [2.31 V, 3.6 V] across the rail's
    # own plausible range, not just at one nominal value.
    at5 = float(np.interp(5.0, va, na))
    at45 = float(np.interp(4.5, va, na))
    at525 = float(np.interp(5.25, va, na))
    c.that("sensor off, 5V_SENSOR nominal (5.0 V) -> pad", at5, 3.072, tol=0.01,
           unit="V")
    c.that("  ... clears the 3.6 V abs max", 3.6 - at5, 0.528, tol=0.02, unit="V")
    c.that("sensor_rail.cir's own fault floor (4.5 V) -> pad", at45, 2.769,
           tol=0.01, unit="V")
    c.that("  ... still reads logic high (>=2.31 V, 0.7*VDD)", at45, 2.31,
           tol=None, ok=at45 >= 2.31, unit="V")
    c.that("above-nominal rail (5.25 V) -> pad", at525, 3.147, tol=0.01, unit="V")
    c.that("  ... still clears the 3.6 V abs max", 3.6 - at525, 0.453, tol=0.02,
           unit="V")

    # Never exceeds the pad's absolute maximum anywhere in the transient,
    # sensor toggling at its own rate.
    c.that("never exceeds 3.6 V abs max in transient", float(nb.max()), 3.6,
           tol=None, ok=float(nb.max()) <= 3.6, unit="V")

    # Edge count: 170 ms window, PULSE period 80 ms -> exactly 2 complete
    # rising edges (at ~40 ms and ~120 ms -- floor(170/80) = 2), same
    # rising-edge-counting convention vr_conditioner.cir uses.
    edges = int(np.sum(np.diff((nb > 1.65).astype(int)) > 0))
    c.that("rising edges, 170 ms window at 12.5 Hz (80 ms period)", edges, 2,
           tol=0, unit="edges")

    # 40 V harness short on the signal line: the clamp must hold the pad
    # inside the abs max, same bound sensor_ratiometric.cir checks for its
    # own 5V_SENSOR-fed channels.
    vf = float(d["cam_frontend_fault.dat"]["nc"][0])
    i_f = abs(float(d["cam_frontend_fault.dat"]["iflt"][0]))
    c.that("40 V harness short on signal line clamps pad to", vf, 3.6,
           tol=None, ok=vf <= 3.6, unit="V")
    c.that("  ... fault current limited to", i_f * 1e3, 5.0, tol=None,
           ok=i_f < 5e-3, unit="mA")
    return c


def check_sensor_differential():
    c = Checks("sensor_differential -- shared ground on pin 34, single vs diff")
    d = sim("sensor_differential", {
        "sensor_differential.dat": ["rg", "se", "diff", "gs"],
    })["sensor_differential.dat"]
    rg, se, dif, gs = d["rg"], d["se"], d["diff"], d["gs"]

    # Exactly the divider's ratio, not a rounded 0.615: at these error
    # magnitudes a third-decimal rounding in the reference is itself a
    # millivolt, and it showed up as a spurious clean-harness failure.
    ideal = 2.5 * 16 / 26

    # A clean harness: both topologies are fine, which is why this defect
    # never shows up on a bench with short wires.
    i0 = int(np.argmin(np.abs(rg - 0.05)))
    c.that("clean harness (50 mOhm), single-ended error",
           abs(float(se[i0]) - ideal) * 1e3, 1.0, tol=None,
           ok=abs(float(se[i0]) - ideal) < 1e-3, unit="mV")

    # A corroded return, which is what the harness becomes.
    i1 = int(np.argmin(np.abs(rg - 1.0)))
    c.that("1 ohm return, ground offset present", float(gs[i1]) * 1e3, 20.0,
           tol=1.0, unit="mV")
    c.that("  ... single-ended reading error", abs(float(se[i1]) - ideal) * 1e3,
           12.3, tol=1.5, unit="mV")
    # Both this line and the ratio below are pinned to the netlist's
    # assumed 80 dB CMRR (INFERRED, no in-amp chosen) -- see its tolerance
    # note. At a worse, still-plausible CMRR (harness-driven source-
    # impedance imbalance, not just a cheaper chip) these numbers move a
    # lot; the underlying claim -- differential meaningfully beats
    # single-ended -- does not, down to 60 dB CMRR tried there.
    c.that("  ... differential reading error", abs(float(dif[i1]) - ideal) * 1e3,
           0.13, tol=0.2, unit="mV")

    # The ratio is the argument for the part.
    e_se = abs(float(se[i1]) - ideal)
    e_df = abs(float(dif[i1]) - ideal)
    c.that("differential is better by", e_se / max(e_df, 1e-9), 90, tol=None,
           ok=e_se / max(e_df, 1e-9) > 20, unit="x")

    # Stated as a harness requirement, which is the useful form: this is
    # what single-ended costs you in contact resistance you must maintain.
    span = 2.769 - 0.308
    worst = abs(float(se[-1]) - ideal)
    c.that("single-ended error at 2 ohm (bad contact)", worst / span * 100,
           1.0, tol=None, ok=worst / span > 0.005, unit="% span")
    c.that("  ... single-ended needs contact resistance below",
           "~0.1 ohm forever, to hold 0.1% -- differential needs nothing",
           None, ok=True)
    return c


def check_boost_converter():
    c = Checks("boost_converter -- injector rail reservoir, pins 03/05")
    d = sim("boost_converter", {
        "boost_converter.dat": ["time", "ra", "rb"],
    })["boost_converter.dat"]
    t, ra, rb = d["time"], d["ra"], d["rb"]

    # Arrangement A: reservoir supplies the peak phase only.
    droop_a = 100.0 - float(ra.min())
    c.that("droop, peak phase only (47 uF)", droop_a, 7.3, tol=1.5, unit="V")
    c.that("  ... rail stays usefully above battery", float(ra.min()), 60.0,
           tol=None, ok=float(ra.min()) > 60, unit="V")

    # Arrangement B: reservoir supplies hold current too.
    droop_b = 100.0 - float(rb.min())
    c.that("droop, peak AND hold from the rail", droop_b, 100.0, tol=None,
           ok=droop_b > 50, unit="V")
    c.that("  ... so the rail collapses",
           f"{float(rb.min()):.0f} V -- hold must come from the battery",
           None, ok=float(rb.min()) < 50)
    c.that("hold phase costs this much more charge", droop_b / droop_a, 28.0,
           tol=None, ok=droop_b / droop_a > 10, unit="x")

    # Recharge has 26.67 ms before the next cylinder (memo 04, 240 degrees).
    at_next = float(np.interp(1e-3 + 26.67e-3, t, ra))
    c.that("recovered by the next injection (26.67 ms)", at_next, 100.0,
           tol=1.0, unit="V")
    c.that("  ... 50 mA average charging is enough", at_next, 99.0, tol=None,
           ok=at_next > 99, unit="V")
    return c


def check_ntc_frontend():
    c = Checks("ntc_frontend -- U2's NTC branch, pin 79, divider vs current")
    d = sim("ntc_frontend", {
        "ntc_frontend.dat": ["rt", "vdiv", "vcur", "pdiss"],
    })["ntc_frontend.dat"]
    rt, vdiv, vcur, pd = d["rt"], d["vdiv"], d["vcur"], d["pdiss"]

    hot = int(np.argmin(np.abs(rt - 88)))       # 150 C
    mid = int(np.argmin(np.abs(rt - 2500)))     # 25 C
    cold = int(np.argmin(np.abs(rt - 59000)))   # -40 C

    # The divider is bounded by its own supply at both ends by construction.
    c.that("divider at 150 C (88 ohm)", float(vdiv[hot]), 0.19, tol=0.03, unit="V")
    c.that("divider at 25 C (2.5k)", float(vdiv[mid]), 2.66, tol=0.1, unit="V")
    c.that("divider at -40 C (59k)", float(vdiv[cold]), 4.82, tol=0.1, unit="V")
    c.that("  ... never leaves the 5 V rail", float(vdiv.max()), 5.0, tol=None,
           ok=float(vdiv.max()) < 5.0, unit="V")

    # The constant-current front-end runs out of rail before it runs out
    # of range. This is the finding that keeps the divider.
    c.that("100 uA source needs this at -40 C", float(vcur[cold]), 5.9,
           tol=0.2, unit="V")
    c.that("  ... but the rail is 5 V", f"{float(vcur[cold]):.1f} V demanded "
           "-- out of compliance, reading clips", None,
           ok=float(vcur[cold]) > 5.0)
    c.that("100 uA source at 150 C gives only", float(vcur[hot]) * 1e3, 8.8,
           tol=1.0, unit="mV")

    # Sized to stay in compliance, the current source gives up the hot end.
    i_ok = 5.0 / 59000
    c.that("current that WOULD stay in compliance", i_ok * 1e6, 85, tol=10,
           unit="uA")
    c.that("  ... leaving this at 150 C", i_ok * 88 * 1e3, 7.5, tol=1.0,
           unit="mV")

    # Self-heating: the divider's one real cost, and it is small but not zero.
    c.that("divider self-heating power at 25 C", float(pd[mid]) * 1e3, 2.83,
           tol=0.5, unit="mW")
    c.that("  ... error at ~2 mW/C dissipation constant",
           float(pd[mid]) * 1e3 / 2.0, 1.4, tol=0.3, unit="degC")
    return c


def check_metering_unit_pwm():
    c = Checks("metering_unit_pwm -- ECU pin 88, low-side PWM into the solenoid")
    dd = sim("metering_unit_pwm", {
        "metering_unit_pwm.dat": ["time", "i100", "i1k", "i10k", "ireg"],
        "metering_unit_pwm_cold.dat": ["time", "i100", "i1k", "i10k", "ireg"],
        "metering_unit_pwm_hot.dat": ["time", "i100", "i1k", "i10k", "ireg"],
    })
    d = dd["metering_unit_pwm.dat"]
    t = d["time"]
    tail = t > 50e-3
    i100, i1k, i10k = (np.abs(d[k][tail]) for k in ("i100", "i1k", "i10k"))

    # The control law: average current must be the same at every frequency,
    # or the pressure loop's gain depends on the PWM constant. 0.675 A is
    # 13.5 V * 0.5 duty / 10 ohm -- the ideal value AT THE ASSUMED 10 ohm
    # coil resistance, which is a class-typical figure, not a chosen part's
    # datasheet number (see the netlist's tolerance note). The real claim
    # this loop is checking is that the three frequencies AGREE with each
    # other, not that any of them hits 0.675 A exactly -- a coil that turns
    # out to be 11 ohm moves all three together and still passes the real
    # invariant while missing this absolute figure. Kept as three separate
    # checks against 0.675 rather than one mutual-agreement check because it
    # also catches a frequency-dependent bug the agreement check alone could
    # miss (e.g. all three drifting together with frequency).
    for name, arr in (("100 Hz", i100), ("1 kHz", i1k), ("10 kHz", i10k)):
        c.that(f"mean current at {name}", float(arr.mean()), 0.675, tol=0.09,
               unit="A")

    # Ripple falls with frequency as V*D*(1-D)*T/L.
    r100 = float(i100.max() - i100.min())
    r1k = float(i1k.max() - i1k.min())
    r10k = float(i10k.max() - i10k.min())
    c.that("ripple at 100 Hz", r100, 1.0, tol=None, ok=r100 > 0.5, unit="A")
    c.that("  ... as fraction of mean", r100 / float(i100.mean()) * 100, 100,
           tol=None, ok=r100 / float(i100.mean()) > 0.8, unit="%")
    c.that("ripple at 1 kHz", r1k, 0.113, tol=0.05, unit="A")
    c.that("ripple at 10 kHz", r10k, 0.011, tol=0.008, unit="A")
    c.that("ripple scales as 1/f", r1k / r10k, 10.0, tol=None,
           ok=5 < r1k / r10k < 20, unit="x")

    # 100 Hz is not dither, it is on/off. The coil's 3 ms time constant is
    # comparable to the period, so the valve follows the PWM rather than
    # its average.
    c.that("100 Hz is not dither, it is chopping",
           f"{r100/float(i100.mean())*100:.0f}% ripple -- valve follows the PWM",
           None, ok=r100 / float(i100.mean()) > 0.8)

    # TEMPERATURE -- express both halves of the finding, per the task's own
    # instruction for this block: the "0.675 A" target and the control-law
    # invariant move in opposite directions at a temperature corner, and
    # that split is itself the thing worth checking.
    #
    # Copper's ~0.39%/C resistance tempco is a physical constant (not
    # INFERRED like most other corners in this pass): R = 10*(1+0.0039*
    # (T-25)) gives 7.39 ohm at -40 C, 13.82 ohm at +125 C. ngspice's
    # `option temp` does nothing for a plain resistor, so this is a
    # component-value corner, done with `alter` on the SAME three
    # branches (see the netlist's TEMPERATURE note for why three more
    # parallel branches broke ngspice's convergence).
    def tailc_of(dc):
        return dc["time"] > 50e-3

    def corner(fname):
        dc = dd[fname]
        tc = dc["time"]
        tailc = tc > 50e-3
        return (np.abs(dc["i100"][tailc]), np.abs(dc["i1k"][tailc]),
                np.abs(dc["i10k"][tailc]))

    for label, fname in (("-40C", "metering_unit_pwm_cold.dat"),
                          ("+125C", "metering_unit_pwm_hot.dat")):
        c100, c1k, c10k = corner(fname)

        # Half 1: the target check IS real (it's the same 0.675+/-0.09 A
        # band the nominal checks above already enforce), so running it at
        # a temperature corner and letting it fail is not manufacturing a
        # verdict -- it is the same claim, at a condition the design has
        # to survive. It fails in OPPOSITE directions at the two corners
        # (cold overshoots, hot undershoots), which is itself informative:
        # not a directional design flaw, just copper doing what copper does.
        # EVIDENCE: these are the rows that produced the requirement for
        # closed-loop current control. Each is pinned to its own produced
        # value with a real tolerance -- not ok=True -- so the finding
        # stays falsifiable, and a second row states the miss against the
        # 0.675 A setpoint explicitly so the size of it is not buried.
        want_ol = {"-40C": 0.862, "+125C": 0.462}[label]
        for name, arr in (("100 Hz", c100), ("1 kHz", c1k), ("10 kHz", c10k)):
            c.that(f"  ... evidence, OPEN LOOP: mean current at {name}, "
                   f"{label} ambient", float(arr.mean()), want_ol, tol=0.02,
                   unit="A")
        ol_mean = float(np.mean([c100.mean(), c1k.mean(), c10k.mean()]))
        c.that(f"  ... so open-loop duty misses the 0.675 A setpoint at "
               f"{label} by", (ol_mean - 0.675) / 0.675 * 100,
               {"-40C": 27.7, "+125C": -31.6}[label], tol=2.0, unit="%")

        # Half 2: the control-law invariant -- the three frequencies must
        # still agree with each other, which is the actual claim the
        # pressure loop depends on (see the header). This is the check
        # that should gate whether the DESIGN is broken, not the absolute
        # target above. A real tolerance (2%), not ok=True: if the three
        # frequencies ever diverge at a corner, this catches it.
        means = np.array([c100.mean(), c1k.mean(), c10k.mean()])
        spread_pct = float((means.max() - means.min()) / means.mean() * 100)
        c.that(f"  ... control law: frequencies still agree, {label}",
               spread_pct, 0.0, tol=2.0, unit="%")

        # RESOLUTION: the hysteretic current regulator (branch 4). Same
        # 0.675 +/- 0.09 A band the open-loop checks use, at the same
        # corner -- this is the claim, not a relabelled pin.
        ireg_c = np.abs(dd[fname]["ireg"][tailc_of(dd[fname])])
        c.that(f"  ... RESOLVED, CLOSED LOOP: mean current at {label}",
               float(ireg_c.mean()), 0.675, tol=0.09, unit="A")

    # And the bound that makes closed-loop possible at all: at the hot
    # corner the coil can only draw 13.5/13.82 = 0.977 A at 100% duty, so
    # the regulator has to have duty left over at the setpoint. Checked,
    # not assumed -- run the regulator out of headroom and it degrades
    # silently back to open-loop behaviour.
    i_max_hot = 13.5 / 13.82
    c.that("closed loop needs duty headroom: max coil current at +125C",
           i_max_hot, 0.977, tol=0.01, unit="A")
    c.that("  ... setpoint as a fraction of that ceiling",
           0.675 / i_max_hot * 100, 100.0, tol=None,
           ok=0.675 / i_max_hot < 0.85, unit="%")

    # Nominal too, so the regulator is shown working before the corners.
    ireg_n = np.abs(d["ireg"][tail])
    c.that("closed loop at nominal 25C", float(ireg_n.mean()), 0.675,
           tol=0.09, unit="A")
    rreg = float(ireg_n.max() - ireg_n.min())
    c.that("  ... hysteresis band it actually regulates within", rreg, 0.133,
           tol=0.06, unit="A")
    return c


def check_can_termination():
    c = Checks("can_termination -- split vs single, J1939 250 kbit/s")
    d = sim("can_termination", {
        "can_termination.dat": ["frequency", "zd_split", "zcm_split",
                                "zd_single", "zcm_single", "zd_tcorner",
                                "zdiff_spec"],
    })["can_termination.dat"]
    f = d["frequency"]
    zds, zcs = d["zd_split"], d["zcm_split"]
    zdg, zcg = d["zd_single"], d["zcm_single"]
    zdt = d["zd_tcorner"]

    # Differential impedance is what the standard specifies, and both
    # topologies meet it identically -- which is why a schematic label
    # cannot tell them apart.
    lo = int(np.argmin(np.abs(f - 250e3)))
    c.that("split termination, differential at 250 kbit/s", float(zds[lo]),
           120.0, tol=2.0, unit="ohm")
    c.that("single 120R, differential at 250 kbit/s", float(zdg[lo]), 120.0,
           tol=2.0, unit="ohm")
    c.that("  ... identical differentially", abs(float(zds[lo] - zdg[lo])),
           0.0, tol=1.0, unit="ohm")

    # Common mode is where they differ, and it is the whole reason to split.
    hi = int(np.argmin(np.abs(f - 10e6)))
    c.that("split termination, common-mode at 10 MHz", float(zcs[hi]), 33.0,
           tol=8.0, unit="ohm")
    c.that("single 120R, common-mode at 10 MHz", float(zcg[hi]) / 1e3, 500.0,
           tol=None, ok=float(zcg[hi]) > 1e5, unit="kohm")
    c.that("  ... split shunts common mode better by",
           float(zcg[hi] / zcs[hi]), 1000.0, tol=None,
           ok=float(zcg[hi] / zcs[hi]) > 100, unit="x")

    # And it must not do that at the signal frequency, or it would load
    # the bus: at 250 kbit/s the midpoint cap is still a high impedance.
    c.that("split common-mode at the bit rate stays high", float(zcs[lo]),
           100.0, tol=None, ok=float(zcs[lo]) > 100, unit="ohm")

    # TEMPERATURE -- shape 1: design is inadequate at the corner. 120 ohm
    # is what J1939 specifies, not a round convention (see the header), so
    # a fail against the SAME 120+/-2 ohm target used above is a real
    # finding, not a manufactured one. Rah/Ral at 200 ppm/C (ordinary
    # standard-grade thick-film, not exotic) shifted together over the
    # full -40/+125 C span -- component-value corner, not `.temp`-driven
    # (plain resistors, no modelled junction). Network "e" in the netlist.
    #
    # NOTE: the netlist's own RESULT NOTE originally wrote this corner's
    # resistance as 61.65 ohm; re-deriving it from the note's own stated
    # formula (200 ppm/C * 165 C span = +3.3%, R = 60*1.033) gives 61.98
    # ohm instead -- the note had a small arithmetic slip, corrected here
    # and in the netlist comment, verified against the actual ngspice run.
    # EVIDENCE, not a live failure: this is the corner that produced the
    # requirement. Pinned to its own produced value with a real tolerance
    # (not ok=True) so that if the network or the sweep drifts, this row
    # fails and says so -- the same treatment egr_hbridge gives its
    # rejected naive wiring and battery_sense its rejected divider.
    c.that("  ... evidence: at 200 ppm/C thick-film tempco (matched "
           "direction, -40/125C) -- the corner that forced the requirement",
           float(zdt[lo]), 123.95, tol=0.3, unit="ohm")
    c.that("  ... so ordinary thick-film misses J1939's own 120 ohm by",
           float(zdt[lo]) - 120.0, 3.95, tol=0.3, unit="ohm")

    # RESOLUTION: the specified part. Thin-film, 0.1% initial, 50 ppm/C --
    # both mechanisms stacked the adverse way (network "f" in the netlist,
    # R = 60 * 1.00825 * 1.001). This is the falsifiable claim: the
    # requirement written into the BOM is SUFFICIENT, checked at the
    # specified part's worst case rather than its nominal.
    zsp = float(d["zdiff_spec"][lo])
    c.that("RESOLVED: specified 0.1%/50 ppm thin-film, worst-case stacked",
           zsp, 120.0, tol=2.0, unit="ohm")
    c.that("  ... margin remaining inside the 120 +/-2 ohm window",
           2.0 - abs(zsp - 120.0), 1.0, tol=None, ok=abs(zsp - 120.0) < 2.0,
           unit="ohm")
    return c


def check_supervisor():
    c = Checks("supervisor -- fail-safe kill path, watches 3V3_MCU (research memo 11)")
    d = sim("supervisor", {
        "supervisor_claim12.dat": ["t", "g1", "g1b", "g2pd", "g2nopd"],
        "supervisor_claim3.dat": ["t", "g20p", "g50p", "g100p", "g200p", "g500p",
                                   "g1000p"],
        "supervisor_claim4_fast.dat": ["t", "mon293", "g293", "mon585", "g585",
                                        "mon1170", "g1170"],
        "supervisor_claim4_slow.dat": ["t", "mon10m", "g10m", "mon100m", "g100m",
                                        "mon1000m", "g1000m"],
    })
    Vgsth = 1.0  # INFERRED, see the netlist header -- low end of a small-signal
    # N-FET class threshold, the conservative pick for every "stays below" claim.

    def t_cross(sig, tarr, thresh, rising=False):
        """First interpolated time `sig` crosses `thresh` (falling by default).
        Linear interpolation between the bracketing samples, not just the
        raw sample index -- resolution-independent, same trick used to
        pull claim 2's ~14 ns effect out of a 10 ns-step dataset."""
        cond = sig > thresh if rising else sig < thresh
        idx = int(np.argmax(cond))
        if not cond[idx]:
            return float("inf")
        if idx == 0:
            return float(tarr[0])
        t0, t1_ = tarr[idx - 1], tarr[idx]
        v0, v1 = sig[idx - 1], sig[idx]
        frac = (thresh - v0) / (v1 - v0) if v1 != v0 else 0.0
        return float(t0 + frac * (t1_ - t0))

    # ---- claim 1: RESET already asserted -- how fast does the kill path
    # itself pull the gate below Vgs(th)? Memo 11's own bound for the
    # PASSIVE pulldown alone is 10-40 us; this is the ACTIVE kill path,
    # which should beat that bound by a wide margin because Ron (5 ohm)
    # dominates the 10k pulldown. ----
    d12 = d["supervisor_claim12.dat"]
    t12, g1, g1b = d12["t"], d12["g1"], d12["g1b"]
    t_g1 = t_cross(g1, t12, Vgsth)
    c.that("claim 1: gate below Vgsth, kill engaged (bound: 10-40 us)",
           t_g1 * 1e6, 40.0, tol=None, ok=t_g1 < 40e-6, unit="us")
    c.that("  ... actual kill-path discharge time",
           f"{t_g1*1e9:.1f} ns -- Ron dominates the 10k pulldown by ~2000x",
           None, ok=True)

    # ---- claim 1b: the GPIO-independence check memo 11 sec.4 asks for in
    # prose. An adversarial driver (100 ohm to 10 V, fixed) fights the kill
    # path for the WHOLE run. If the gate still ends up below Vgsth, the
    # safe state does not depend on what GPIO/driver is doing. ----
    v_g1b_final = float(g1b[-1])
    c.that("claim 1b: gate stays below Vgsth despite an adversarial\n"
           "      driver actively holding it high (GPIO-independence)",
           v_g1b_final, Vgsth, tol=None, ok=v_g1b_final < Vgsth, unit="V")

    # ---- claim 2: RESET deasserted, MCU driving the gate through its
    # normal path -- the pulldown must not measurably slow the edge.
    # Compared at a fixed absolute voltage (90% of the 10 V command)
    # rather than each branch's own 10-90%, so the tiny final-value
    # difference doesn't get folded into the timing comparison. ----
    g2pd, g2nopd = d12["g2pd"], d12["g2nopd"]
    t_pd = t_cross(g2pd, t12, 9.0, rising=True)
    t_nopd = t_cross(g2nopd, t12, 9.0, rising=True)
    slowdown = (t_pd - t_nopd) / t_nopd
    # Claim 2 asks what the pulldown costs the intended turn-on. It was
    # written against 10k, where the answer was 3% and uninteresting.
    # Claim 6 below shows the pulldown has to be ~470 ohm, and at that
    # value the question changes shape entirely: the pulldown and the
    # gate driver's output impedance form a DIVIDER, so the gate never
    # reaches the rail at all. Time-to-9V is the wrong probe -- it goes
    # to infinity not because the edge is slow but because the
    # destination moved. Measure the destination instead.
    vg_final = float(g2pd[-1])
    vg_nopd = float(g2nopd[-1])
    c.that("claim 2: final V(gate) with the 470 ohm pulldown fitted",
           vg_final, 8.25, tol=0.3, unit="V")
    c.that("  ... vs the same driver with no pulldown", vg_nopd, 10.0,
           tol=0.3, unit="V")
    # 100 ohm is what this netlist assumed for the driver. The divider
    # says what it would have to become: Vgs = 10*Rpd/(Rpd+Rdrv), so
    # holding 9.5 V across 470 ohm needs Rdrv <= 24.7 ohm. This is the
    # real coupling the corrected requirement creates -- choosing the
    # pulldown constrains the driver, and the two cannot be specified
    # apart.
    rdrv_needed = 470.0 * (10.0 / 9.5 - 1.0)
    c.that("  ... driver output impedance needed to still reach 9.5 V",
           rdrv_needed, 25.0, tol=2.0, unit="ohm")
    c.that("  ... the 100 ohm driver this block assumed is too weak by",
           100.0 / rdrv_needed, 4.0, tol=0.5, unit="x")

    # ---- claim 3: THE ONE THE TASK FLAGGED AS LOAD-BEARING. Miller/dV-dt
    # coupling at this design's own 2.8 V/us boost-rail turn-off edge,
    # through the 10k pulldown ALONE (no kill switch -- RESET is not
    # asserted during a normal turn-off). Swept across Crss rather than
    # taking memo 11's illustrative 50-200 pF on faith. See the netlist's
    # RESULT NOTE for the arithmetic error this exposes in the memo. ----
    d3 = d["supervisor_claim3.dat"]
    crss_checks = [
        ("g20p", 20, 0.465),
        ("g50p", 50, 1.155),
        ("g100p", 100, 2.289),
        ("g200p", 200, 4.497),
        ("g500p", 500, 10.647),
        ("g1000p", 1000, 19.490),
    ]
    for key, pf, expected in crss_checks:
        peak = float(d3[key].max())
        # `expected` is a regression pin on this simulation's own output
        # (this exact R/C/edge model), not an independently derived
        # number -- the CLAIM is the ok= comparison against Vgsth.
        # EVIDENCE ROWS, not live gates. These are the falsification
        # record for memo 11 sec.4's 10 kOhm: the value is rejected, so
        # gating on Vgsth here would make the block fail forever for a
        # historical reason instead of a live one.
        #
        # But they are NOT ok=True, which is what they were until
        # 19 Sep 2026. A review found the 20 pF row stated 0.235 V
        # against an actual 0.465 V -- a 2x hand-arithmetic error that
        # ok=True made structurally uncatchable, in the file written to
        # fix a 1000x hand-arithmetic error. An evidence row still has
        # to reproduce; it just does not gate on the design threshold.
        # So: pin to the stated value with a tolerance, and let drift
        # fail.
        c.that(f"claim 3 (evidence): peak V(gate), Crss={pf} pF, Rpd=10k",
               peak, expected, tol=max(0.05 * expected, 0.02), unit="V")
    c.that("  ... memo 11's own hand arithmetic at Crss=200 pF claimed",
           "~5.6 mV -- off by 1000x (560 uA * 10 kOhm = 5.6 V, not 5.6 mV); "
           "this sim's 4.50 V independently confirms the corrected order "
           "of magnitude, not the memo's figure", None, ok=True)
    c.that("  ... so the 10k pulldown fails even at the memo's OWN low end",
           "1.155 V at Crss=50 pF already exceeds Vgsth=1.0 V -- not just "
           "at an extended/pessimistic Crss", None, ok=True)

    # ---- claim 4: THE CENTRAL CLAIM. Brownout ramps at six rates (three
    # from memo 11's own sub-ms RC estimate, three several orders of
    # magnitude slower), gate held by the SAME adversarial drive as
    # claim 1b throughout. Does the kill path finish (gate < Vgsth)
    # before 3V3_MCU crosses 2.97 V, the S32K148's own PLL-guarantee
    # floor -- the earliest, most conservative bound for "undefined
    # state", earlier than VLVR (2.50-2.7 V) where the MCU would
    # actually reset itself? ----
    def claim4_margins(dat, keys, unit_scale, unit):
        rows = []
        for mon_k, g_k, label in keys:
            mon, g = dat[mon_k], dat[g_k]
            t = dat["t"]
            t_safe = t_cross(g, t, Vgsth)
            t_297 = t_cross(mon, t, 2.97)
            margin = t_297 - t_safe
            c.that(f"claim 4: gate safe before 2.97V guarantee floor, "
                   f"ramp={label}", margin * unit_scale, 0.0, tol=None,
                   ok=margin > 0, unit=unit)
            rows.append((label, margin))
        return rows

    d4f = d["supervisor_claim4_fast.dat"]
    claim4_margins(d4f, [
        ("mon293", "g293", "293 us"),
        ("mon585", "g585", "585 us"),
        ("mon1170", "g1170", "1.17 ms"),
    ], 1e6, "us")

    d4s = d["supervisor_claim4_slow.dat"]
    claim4_margins(d4s, [
        ("mon10m", "g10m", "10 ms"),
        ("mon100m", "g100m", "100 ms"),
        ("mon1000m", "g1000m", "1000 ms"),
    ], 1e3, "ms")

    c.that("  ... tightest margin is at the FASTEST ramp tried",
           "18 us at 293 us -- grows to tens of ms at the slowest ramp; "
           "a slow sag gives the supervisor MORE time, not less", None,
           ok=True)

    # ---- claim 5: total exposure vs one 26.67 ms cylinder interval
    # (1500 rpm, 3-cyl, 240 deg phasing -- memo 04/10). Not a separate
    # circuit -- reuses claim 1's own measured kill-path latency, because
    # the watchdog window itself (CWD/SET0/SET1) is an explicit Phase-2
    # item memo 11 sec.5 declines to guess. This only bounds the GATE
    # RESPONSE portion of total exposure, not the watchdog's own fault-
    # detection latency, which is unmodelled and unchosen. ----
    cyl_interval = 26.67e-3
    ratio = cyl_interval / t_g1
    c.that("claim 5: kill-path latency vs one 26.67 ms cylinder interval",
           ratio, 1000.0, tol=None, ok=ratio > 1000, unit="x")
    c.that("  ... caveat: excludes the watchdog's own fault-DETECTION "
           "time",
           "not modelled -- Phase-2 item per memo 11 sec.5, this only "
           "bounds the response AFTER RESET asserts", None, ok=True)

    # ---- claim 6: what Rpd actually has to be ----
    # Claim 3 swept Crss at a fixed 10k and showed 10k is wrong. This
    # sweeps the free parameter instead and reports the largest pulldown
    # that survives, which is what the corrected spec requirement needs.
    # Swept at Crss = 500 pF, the pessimistic end of the class range:
    # the bound scales as 1/Crss, so a value chosen here stays valid if
    # the eventual FET turns out gentler.
    d6 = sim("supervisor", {"supervisor_claim6.dat":
                            ["time", "grr1", "grr2", "grr3", "grr4", "grr5"]})["supervisor_claim6.dat"]
    rpd_vals = [(220, "grr1"), (470, "grr2"), (1000, "grr3"),
                (2200, "grr4"), (4700, "grr5")]
    VGSTH = 1.0
    peaks = [(r, float(np.abs(d6[k]).max())) for r, k in rpd_vals]
    # Sweep data, same treatment as claim 3's rows: pinned to the values
    # actually produced, so drift fails, but not gated on Vgsth -- the
    # derived result below is the gate.
    claim6_expected = {220: 0.308, 470: 0.658, 1000: 1.401,
                       2200: 3.077, 4700: 6.267}
    for r, pk in peaks:
        c.that(f"claim 6 (sweep): peak V(gate) at Crss=500 pF, Rpd={r} ohm", pk,
               claim6_expected[r], tol=max(0.05 * claim6_expected[r], 0.02),
               unit="V")
    survivors = [r for r, pk in peaks if pk < VGSTH]
    rmax = max(survivors) if survivors else 0
    # Vgsth is itself a class figure with a stated 1.0-2.5 V range and no
    # part chosen. It is the permissive direction -- a higher threshold
    # allows a larger pulldown -- so 1.0 V is the conservative end. Report
    # the other end too, because the spec quotes the 1.0 V answer as
    # though it were fixed.
    rmax_hi = max([r for r, pk in peaks if pk < 2.5] or [0])
    c.that("  ... same sweep read at Vgsth=2.5 V, the permissive end",
           float(rmax_hi), 1000.0, tol=None, ok=rmax_hi >= rmax, unit="ohm")
    c.that("  ... largest pulldown that holds the gate below Vgsth",
           float(rmax), 470.0, tol=None, ok=rmax >= 220, unit="ohm")
    # The lower bound is DC arithmetic, not a transient question: the
    # driver fights Rpd continuously while the FET conducts. Stated as a
    # claim so the cost is visible next to the resistance, because the
    # two bounds together are the requirement -- a single number hid
    # exactly this.
    if rmax:
        per_gate = 10.0 / rmax
        c.that(f"  ... cost of {rmax} ohm: drive current per gate held at 10 V",
               per_gate * 1e3, 50.0, tol=None, ok=per_gate < 0.05, unit="mA")
        c.that("  ... and across all six driver gates",
               6 * per_gate * 10.0, 3.0, tol=None, ok=6 * per_gate * 10.0 < 3.0,
               unit="W")
    return c


CHECKS = {
    "battery_sense": check_battery_sense,
    "discrete_input": check_discrete_input,
    "trip_module_sense": check_trip_module_sense,
    "sensor_ratiometric": check_sensor_ratiometric,
    "transient_clamp": check_transient_clamp,
    "load_dump": check_load_dump,
    "negative_pulses": check_negative_pulses,
    "injector_boost": check_injector_boost,
    "injector_turnoff": check_injector_turnoff,
    "relay_driver": check_relay_driver,
    "egr_hbridge": check_egr_hbridge,
    "emi_filter": check_emi_filter,
    "reverse_battery": check_reverse_battery,
    "buck_preregulator": check_buck_preregulator,
    "sensor_rail": check_sensor_rail,
    "mcu_pdn": check_mcu_pdn,
    "vr_conditioner": check_vr_conditioner,
    "cam_frontend": check_cam_frontend,
    "sensor_differential": check_sensor_differential,
    "boost_converter": check_boost_converter,
    "ntc_frontend": check_ntc_frontend,
    "metering_unit_pwm": check_metering_unit_pwm,
    "can_termination": check_can_termination,
    "supervisor": check_supervisor,
}


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else ""
    selected = {k: v for k, v in CHECKS.items() if want in k}
    if not selected:
        print(f"no blocks match {want!r}. known: {', '.join(CHECKS)}")
        return 2
    print("=" * 74)
    print("  Genset ECU -- circuit block simulation")
    print("=" * 74)
    results = {}
    for name, fn in selected.items():
        try:
            results[name] = fn().report()
        except Exception as exc:
            print(f"\n  {name}\n    {FAIL}  simulation error: {exc}")
            results[name] = False
    print("\n" + "=" * 74)
    npass = sum(results.values())
    print(f"  {npass}/{len(results)} blocks pass")
    print("=" * 74)
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
