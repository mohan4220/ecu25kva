# Genset ECU

Replacement engine control unit for a 25 kVA Kirloskar diesel genset —
engine **3GK550ETA 4SR1**, application code `GK3.8703`, 26.5 kW at 1500 rpm,
12 V system. Panel controller is a **Deep Sea Electronics DSE4522 MKII AMF**.

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
| `refs/` | The OEM wiring diagram, the DSE4522 configuration, machine photographs, and the extracted pinout |
| `docs/research/` | Nine research memos: engine ID, GCU, connector, injector, MCU, standards, BOM, inspection brief, sensor front-ends |
| `sim/` | Seventeen SPICE circuits that run and check themselves, plus the schematic and page generators |

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

**Four unknowns closed on 18 September**, from photographs of the machine and one
manufacturer's manual — and three of the four closed *against* an inference this
project had made. The engine is **3GK550ETA 4SR1**, not the model memo 01 derived.
The panel controller is a **DSE4522**, not the KG640C the OEM diagram shows. The
connector is **Bosch `1 928 405 192` / `194`, code C**. And the controller has no
speed pickup, which memo 02 got right about the wrong device.

That cost the project its safety argument. The DSE4522 takes engine speed from
**our ECU over CAN**, so its overspeed trip is not independent of the thing it
protects against. Spec §3 is rewritten and the standalone overspeed trip module
reverts from *recommended* to **mandatory**.

**U12 now stands alone as the load-bearing unknown.** Every protective action the
controller can take ends by de-energising one fuel relay; whether its contacts
remove supply from the ECU and fuel system, or merely signal a hung ECU, decides
whether any independent protection exists.
[Memo 08](docs/research/08-engine-inspection-brief.md) is the printed checklist
for that measurement.

Three things deserve reading before anything gets built. **Memo 06** on the CPCB
IV+ position — and the machine's type approval is now a specific certificate,
`ARAI/MoEF/DGTA/IGES4/KOEL-P25/2825/24`. The single-source flag on the
**MC33816** injector driver in Memo 07. And §3's closing note: **no air-intake
shutoff exists anywhere in this design**, which means nothing here can stop a
diesel running away on its own lubricating oil.
