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


CHECKS = {
    "battery_sense": check_battery_sense,
    "discrete_input": check_discrete_input,
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
