# Genset ECU

Replacement engine control unit for a **Kirloskar KG4-25WS1** 25 kVA diesel
genset (engine 3R550ETA 4G1, 12 V system).

## Start here

**[`docs/pdf/ECU-Bible.pdf`](docs/pdf/ECU-Bible.pdf)** — everything, in reading
order, in one 163-page file. Cover, field handbook, sensor reference, circuit
reference, the specification, all nine research memos, the plan. Bookmarked, so
the PDF reader's outline pane is the table of contents.

Prefer the browser? Three of those are live HTML:
[the handbook](docs/handbook/index.html),
[the circuit reference](docs/handbook/circuits.html) and
[the sensor reference](docs/handbook/sensors.html).

## What's in here

| Path | What it is |
|---|---|
| `docs/pdf/` | Every document as PDF — one file each, plus the combined bible |
| `docs/handbook/index.html` | The handbook: machine, 94-pin interface, the circuits in narrative, how a runaway gets stopped |
| `docs/handbook/circuits.html` | Circuit reference — all 17 blocks, each with schematic, reasoning, simulated result and model limits |
| `docs/handbook/sensors.html` | Sensor reference — every sensor, what it measures, how it's read, what the data drives |
| `docs/superpowers/specs/` | The reconciled specification — the binding source of truth |
| `docs/research/` | Nine research memos: engine ID, GCU, connector, injector, MCU, standards, BOM, inspection brief, sensor front-ends |
| `sim/` | Seventeen SPICE circuits that run and check themselves, plus the schematic and page generators |
| `refs/` | The OEM wiring diagram and its extracted pinout |

## Rebuilding the PDFs

```bash
.venv/bin/python docs/build_pdf.py
```

Markdown documents are converted and printed; the handbook pages are printed as
they stand, from a temporary copy with the print rules injected — the source
HTML is never edited, so a PDF cannot drift from the page it came from.

Needs Chrome or Chromium on `PATH` (it is the renderer — the only engine here
that handles the handbook's inline SVG schematics and CSS custom properties),
plus `markdown` and `pypdf`:

```bash
.venv/bin/pip install markdown pypdf
```

Page rules live in [`docs/print.css`](docs/print.css).

## Running the circuit simulations

```bash
.venv/bin/python sim/run_sim.py              # every block
.venv/bin/python sim/run_sim.py injector     # blocks matching "injector"
```

Each check is a claim about the circuit, so a red line means the **design** is
wrong, not the simulator. All seventeen blocks currently pass.

The netlists are plain SPICE — they also open directly in KiCad's built-in
simulator (Tools → Simulator), LTspice, or standalone ngspice. See
[`sim/README.md`](sim/README.md).

If `.venv` is missing, rebuild it:

```bash
python3 -m venv .venv && .venv/bin/pip install PySpice numpy schemdraw markdown pypdf
```

## Where the project stands

Phase 1 is complete: nine research memos, **seventeen verified circuit blocks**
covering the whole power chain, both sensor front-end topologies, the speed
input, the injector boost rail and its reservoir, both actuator drivers and the
CAN termination — and a specification carrying the corrections that simulation
forced, including one front-end that could not have worked as originally
specified.

Simulation has now caught a design error in roughly a third of the blocks
written. The ones worth knowing about: the discrete input was impossible as a
divider rather than merely mis-valued; the battery divider would have destroyed
an ADC pin; the MCU decoupling peaked thirty times over target against the
regulator's own output inductance; and the EMI filter handed back 12 dB at the
exact frequency it most needed to hold.

What gates the next phase is not desk research. Twelve unknowns remain open, and
most need a multimeter and a camera at the machine rather than more reading, so
one visit closes nearly all of them —
[Memo 08](docs/research/08-engine-inspection-brief.md) is the printed checklist
for that visit, and Handbook §06 lists what each unknown blocks.

Two findings deserve reading before anything gets built: **Memo 06** on the CPCB
IV+ certification position, which is a decision for the machine's owners rather
than an engineering call, and the single-source flag on the **MC33816** injector
driver in Memo 07, which has no alternative identified.
