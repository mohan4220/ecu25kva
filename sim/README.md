# Circuit simulation

Every circuit block in this ECU has a SPICE netlist here and a set of checks
that must hold. A check is a claim about the circuit — "reads logic high at a
6 V cranking dip", "never exceeds the MCU's absolute maximum" — so a failure
means the **circuit** is wrong, not that the simulator is unhappy.

This is how design errors get caught before copper. Two were caught on the
first run; both are described at the bottom of this file.

## Running

```bash
.venv/bin/python sim/run_sim.py              # every block
.venv/bin/python sim/run_sim.py battery      # blocks matching "battery"
```

Output is a table, one line per claim, green or red.

## What you need

Already present on this machine:

- **KiCad 7.0.11**, which ships `libngspice.so.0` — that shared library *is*
  the simulator, and `sim/lib/ngrun.py` drives it directly.
- **`.venv`** with numpy. Created with `python3 -m venv .venv` and
  `.venv/bin/pip install PySpice numpy`.

If `libngspice.so.0` lives somewhere else on your machine, point `NGSPICE_LIB`
at it.

## Opening these circuits in a GUI

The netlists are plain SPICE and are not tied to this harness:

- **KiCad** — Tools → Simulator, then load the `.cir` file. You already have
  this installed.
- **LTspice** — free from Analog Devices, runs under Wine. Open the `.cir`
  directly. Best waveform viewer of the three.
- **ngspice** on its own — `sudo apt install ngspice`, then
  `ngspice sim/blocks/battery_sense.cir`.

Each netlist carries its own `.control` block, so it runs and writes its data
files without any extra setup.

## Layout

```
sim/
  lib/ngrun.py     driver -- talks to libngspice over ctypes
  blocks/*.cir     one netlist per circuit block, heavily commented
  run_sim.py       the checks
```

The comments inside each `.cir` explain *why* the circuit is shaped the way it
is, not just what the components are. Read those first — they carry the
reasoning that the schematic alone cannot.

## Errors this has already caught

**Battery sense divider fed 4.7 V into a 3.3 V ADC.** The value inherited from
the earlier design documents — 75 kΩ / 10 kΩ — was sized for a 5 V ADC. The
MCU is an S32K148 with a 3.3 V analog supply, so at the top of the 40 V input
range that divider delivers 4.69 V to a pin rated 3.3 V. Corrected to
120 kΩ / 10 kΩ, which peaks at 3.07 V. The simulation keeps both in the
netlist so the difference stays visible.

**The discrete input could not be built as a divider at all.** Pins 20, 24 and
71 are active-high switched battery. Reading logic high at a 6 V cranking dip
needs a divider ratio above 0.385; staying under 3.3 V at 40 V needs it below
0.0825. Those do not overlap — *no* fixed ratio works. The fix is a different
topology: a zener sets the clamp level and the divider only biases into it, so
the logic level is flat to within 92 mV across the entire 6–40 V range instead
of tracking the battery. This one is worth understanding, because it is not
obvious from a schematic that the original was impossible rather than merely
mis-valued.
