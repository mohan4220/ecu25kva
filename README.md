# Genset ECU

Replacement engine control unit for a **Kirloskar KG4-25WS1** 25 kVA diesel
genset (engine 3R550ETA 4G1, 12 V system).

## Start here

**[`docs/handbook/index.html`](docs/handbook/index.html)** — the field handbook.
Open it in a browser. Everything below is summarised there in readable form: the
machine, the 94-pin interface, every circuit with its simulated result, how a
runaway gets stopped, and the two risks that decide whether this ever runs.

## What's in here

| Path | What it is |
|---|---|
| `docs/handbook/index.html` | The handbook. Read this first. |
| `docs/superpowers/specs/` | The reconciled specification — the binding source of truth |
| `docs/research/` | Six research memos: engine ID, GCU, connector, injector, MCU, standards |
| `sim/` | Six SPICE circuits that run and check themselves |
| `refs/` | The OEM wiring diagram and its extracted pinout |

## Running the circuit simulations

```bash
.venv/bin/python sim/run_sim.py              # every block
.venv/bin/python sim/run_sim.py injector     # blocks matching "injector"
```

Each check is a claim about the circuit, so a red line means the **design** is
wrong, not the simulator. All six blocks currently pass.

The netlists are plain SPICE — they also open directly in KiCad's built-in
simulator (Tools → Simulator), LTspice, or standalone ngspice. See
[`sim/README.md`](sim/README.md).

If `.venv` is missing, rebuild it:

```bash
python3 -m venv .venv && .venv/bin/pip install PySpice numpy
```

## Where the project stands

Six of eight research memos are done. Six circuits are verified. The
specification carries three corrections that simulation forced, including one
front-end that could not have worked as originally specified.

Not yet done: the BOM memo, and the engine inspection brief. That brief matters
most — most of the twelve open unknowns need a multimeter and a camera at the
machine rather than more desk research, so one visit closes nearly all of them.
Handbook §06 lists them.
