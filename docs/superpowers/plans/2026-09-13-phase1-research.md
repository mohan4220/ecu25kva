# Phase 1 — Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the unknowns that block schematic capture, and produce the sourcing and standards groundwork the later phases depend on.

**Architecture:** Seven independent research memos, one per question, each written to `docs/research/`. Every memo ends with a verdict that either closes a numbered unknown from the spec's §8 register or states precisely why it cannot be closed from desk research and what physical access would close it. Memos are evidence documents: every factual claim carries a citation, and an uncited claim is a defect.

**Tech Stack:** WebSearch and WebFetch for primary sources; manufacturer datasheets and distributor stock APIs; Markdown output under version control.

**Spec:** [`docs/superpowers/specs/2026-09-13-ecu-reconciled-spec-design.md`](../specs/2026-09-13-ecu-reconciled-spec-design.md)

## Global Constraints

- **Every factual claim carries a citation** — a URL, a document number, or an explicit "measured on the engine by <name> on <date>". No claim from memory.
- **Distinguish confirmed from inferred.** Confirmed means a primary source says it. Inferred means we reasoned to it. Memos mark every non-obvious claim as one or the other.
- **A closed unknown states what closed it.** "U5 closed — injector is Bosch 0445110xxx per photograph refs/injector-body.jpg" is a close. "U5 probably Bosch" is not.
- **Negative results are results.** A memo that establishes the KG640C manual is not publicly available has done its job, provided it records where it looked.
- **No safety-relevant conclusion from a secondary source.** Anything feeding the §3 overspeed gate needs a manufacturer document or a measurement, not a forum post.
- Currency for sourcing: **INR**, with availability assessed for **India** (Mouser/DigiKey India, Element14, Robu, local distributors).
- Memos live at `docs/research/<NN>-<topic>.md`, numbered to match task order.

---

### Task 1: Engine identity

**Files:**
- Create: `docs/research/01-engine-identity.md`

**Interfaces:**
- Consumes: nothing.
- Produces: engine make/model/displacement/cylinder count/rated speed/emissions tier, used by Tasks 4 and 6 and by the injector and aftertreatment scope decisions.

**Closes:** U11. Informs U8, U9.

- [ ] **Step 1: Establish what "GK550" designates**

The user reports the engine as "GK550". This does not match a Kirloskar engine designation. Determine whether it is a genset model, an engine model, a Kirloskar Green product code, or a distributor SKU.

Search: `Kirloskar GK550`, `Kirloskar Green GK 550 genset`, `KOEL GK550 25 kVA`.

- [ ] **Step 2: Work backwards from the manual number**

The wiring diagram is `08-GP3-60-001`, file `GP3.8703.C4.pdf`, hosted at `ikonnect.kirloskar.com/KOEL/Services/TroubleShootingWiringDiagram`. Determine what the `GP3` family designates. Try fetching the parent index of that URL path for a manual list that maps families to engine models.

- [ ] **Step 3: Cross-check against the hardware evidence**

The wiring diagram independently constrains the engine. Any candidate must match **all** of: 3 cylinders (three injectors, cylinders 1/2/3); common-rail (rail pressure sensor plus fuel metering unit); EGR fitted; a catalyst temperature sensor present but no SCR or DEF; 12 V electrical system. Reject any candidate that fails one.

- [ ] **Step 4: Determine the emissions tier**

A 25 kVA genset in India with common-rail, EGR and a DOC but no SCR points to CPCB IV+. Confirm against CPCB IV+ requirements for the 19–56 kW band and record what that implies for aftertreatment scope.

- [ ] **Step 5: Write the memo**

Record: engine make, model, displacement, bore/stroke if available, cylinder count, aspiration, rated speed (expected 1500 rpm for 50 Hz), rated output, emissions tier, and the OEM ECU part number if discoverable. Mark each confirmed or inferred. If identity cannot be established, state exactly what photograph of the engine rating plate would close it.

- [ ] **Step 6: Commit**

```bash
git add docs/research/01-engine-identity.md
git commit -m "research: engine identity and emissions tier"
```

---

### Task 2: KG640C genset controller

**Files:**
- Create: `docs/research/02-kg640c-gcu.md`

**Interfaces:**
- Consumes: Task 1's engine identity (the GCU is sold against engine families).
- Produces: the J1939 PGN set the ECU must transmit and receive, and a yes/no on the MPU input that the spec's §3 safety gate turns on.

**Closes:** U3, U4. **U3 is the safety gate — treat this task as the highest priority in the phase.**

- [ ] **Step 1: Locate the KG640C manual**

Search: `Kirloskar KG640C manual`, `KG640C genset controller datasheet`, `KOEL KG640C wiring`. Also try the `ikonnect.kirloskar.com` path that served the wiring diagram, substituting the controller's manual number if a list is discoverable.

The KG640C may be a rebadged third-party controller — Deep Sea, ComAp, Datakom and SmartGen all OEM for Indian genset makers. If the manual is unavailable under the Kirloskar name, identify the underlying product and use its documentation, recording the identification basis.

- [ ] **Step 2: Answer the MPU question explicitly**

Determine whether the KG640C has a magnetic pickup input terminal. The spec's §3 gate depends on this and nothing else.

Three possible verdicts, all acceptable outputs:
- **Yes** — record the terminal designation and the input's electrical spec. The design wires an MPU to it.
- **No** — the design needs a standalone overspeed trip module in the panel. Identify two candidate modules with part numbers and prices.
- **Cannot determine** — state what would: a photograph of the KG640C terminal strip, or the physical unit.

Do not infer from the wiring diagram's silence. The diagram shows terminals J1–J8 in use; an unused MPU terminal would not appear.

- [ ] **Step 3: Extract the J1939 expectations**

Determine which PGNs the controller expects from an engine node, and which it transmits. At minimum establish whether it uses: EEC1 (61444) for speed, ET1 (65262) for coolant temperature, EFL/P1 (65263) for oil pressure, VEP1 (65271) for battery voltage, DM1 (65226) for active faults, and TSC1 (0) for speed commands to the engine.

Record baud rate (expected 250 kbit/s) and whether it expects the engine at source address 0x00.

- [ ] **Step 4: Record the digital I/O contract**

From the wiring diagram, terminals J1/J2 carry `D+CHG ALT`, `DIG I/P`, `DIG O/P`, `IGNITION RELAY`, `START RELAY`. Establish which of these the ECU interacts with and in which direction, since start/stop sequencing is split between the GCU requesting and the ECU executing.

- [ ] **Step 5: Write the memo**

Lead with the U3 verdict — it is the reason this memo exists. Then the PGN tables, the digital I/O contract, and a list of what remains unknown.

- [ ] **Step 6: Commit**

```bash
git add docs/research/02-kg640c-gcu.md
git commit -m "research: KG640C controller, J1939 contract and MPU verdict"
```

---

### Task 3: ECU connector identification

**Files:**
- Create: `docs/research/03-ecu-connector.md`

**Interfaces:**
- Consumes: Task 1's engine identity.
- Produces: candidate connector part numbers and the mating-half sourcing that the adapter-harness deliverable (spec §7.1) depends on.

**Closes:** U1, partially — full closure needs the photograph.

- [ ] **Step 1: Characterise the connector from the PDF**

PDF page 4 shows the ECU connector with pins 1, 5, 28, 73 and 94 called out. Re-render that page region at high DPI and examine the housing: number of pin rows, whether it is a single housing or ganged blocks, the lever or bolt retention style.

```bash
pdftoppm -r 400 -f 4 -l 4 -png refs/GP3.8703.C4.pdf /tmp/p4
```

- [ ] **Step 2: Match against standard 94-pin automotive ECU headers**

94-pin is a common automotive ECU size. Check the usual families: TE Connectivity AMPSEAL, Bosch's own ECU headers (the Bosch EDC17/MD1 series uses 94-pin variants), Molex CMC, Aptiv/Delphi GT. Record which are 94-pin and how their housings compare to the PDF image.

- [ ] **Step 3: Establish mating-half availability and price in India**

For each candidate, find the harness-side connector, contacts and seals, with distributor stock and INR pricing. A connector we cannot buy is not a candidate.

- [ ] **Step 4: Specify the photograph that closes U1**

Write explicit instructions for what to photograph on the engine: the ECU connector housing from the mating face, any moulded part number or logo on the housing and on the ECU case, and the ECU's own label. Include what lighting and angle make moulded numbers legible.

- [ ] **Step 5: Write the memo**

Ranked candidate list with the evidence for each, sourcing table, and the photograph brief.

- [ ] **Step 6: Commit**

```bash
git add docs/research/03-ecu-connector.md
git commit -m "research: ECU connector candidates and sourcing"
```

---

### Task 4: Injector identification and drive profile

**Files:**
- Create: `docs/research/04-injector-drive.md`

**Interfaces:**
- Consumes: Task 1's engine identity.
- Produces: boost rail voltage, peak and hold current targets, and pulse timing — the inputs to the injector driver sheet and the boost converter design in Phase 2.

**Closes:** U5.

- [ ] **Step 1: Identify the injector family**

From the engine identity, determine the common-rail system supplier. Indian 3-cylinder gensets in this class typically use Bosch CRS or Denso. Record the injector part number if discoverable.

- [ ] **Step 2: Establish the drive profile envelope**

Solenoid common-rail injectors share a characteristic profile: a boosted opening pulse, then a lower hold current. Establish typical values for the identified family — boost rail voltage, peak current and its duration, hold current, and minimum controllable pulse width.

Where exact figures are unavailable, record the **envelope** across the family and design the hardware to cover it. A driver that spans 40–100 A/ms slew and 12–24 A peak will drive any of them; the calibration narrows it later.

- [ ] **Step 3: Confirm the bank arrangement against firing order**

The spec establishes bank A = cylinders 1+3, bank B = cylinder 2. Verify this is consistent with a 3-cylinder firing order (typically 1-3-2 or 1-2-3) — cylinders sharing a high-side bank must never need simultaneous injection. Record the firing order and show the check.

- [ ] **Step 4: Select candidate driver ICs**

Identify integrated common-rail injector drivers with integrated or companion boost control. Record for each: channel count, boost capability, current regulation method, whether it handles the high-side bank switching, package, availability in India, and price. Note explicitly whether each is available in small quantities or is automotive-tier allocation only.

- [ ] **Step 5: State the calibration boundary plainly**

Record what this hardware can and cannot do without injector characterisation data. The memo must say, unambiguously, that the driver can be built and bench-verified against a known load, and that making it run *this* engine correctly needs flow-vs-pulsewidth data that is not publicly available. Name the three routes to that data — supplier licence, dyno with rate-of-injection measurement, or OEM calibration extraction — with an honest note on the cost and legality of each.

- [ ] **Step 6: Write the memo and commit**

```bash
git add docs/research/04-injector-drive.md
git commit -m "research: injector identification, drive envelope and calibration boundary"
```

---

### Task 5: MCU confirmation and availability

**Files:**
- Create: `docs/research/05-mcu-selection.md`

**Interfaces:**
- Consumes: the channel budget in spec §5 — 2 CAN, ~14 ADC, ~10 timer channels.
- Produces: the confirmed MCU part number, package and KiCad symbol source for Phase 2.

**Confirms:** spec §5. Does not close a numbered unknown.

- [ ] **Step 1: Verify the channel budget against the S32K148 datasheet**

Fetch the S32K148 datasheet and confirm: FlexCAN instance count, ADC channel count and resolution, FlexTimer instances and channels per instance, LPI2C for the barometric sensor, flash and RAM. Record the specific package under consideration and its pin count.

- [ ] **Step 2: Check real availability and price in India**

Check Mouser India, DigiKey India and Element14 for S32K148 stock in the chosen package, in single-digit and hundred-unit quantities, with INR pricing and lead time. Repeat for the S32K146 fallback named in the spec.

An MCU with a 40-week lead time fails this task regardless of how good the datasheet is. If both S32K parts fail on availability, evaluate alternatives against the same channel budget and recommend one — do not silently proceed with an unobtainable part.

- [ ] **Step 3: Confirm KiCad symbol and footprint provenance**

Determine whether a symbol and footprint exist in KiCad's stock libraries, in NXP's published EVB design files, or on SnapEDA/Ultra Librarian. Record the source and whether pad pitch was verified against the datasheet. Per the PCB Roadmap's warning, a hand-sourced footprint is the single most likely place to introduce a silent error.

- [ ] **Step 4: Confirm the toolchain**

Record: compiler (S32 Design Studio / GCC ARM), debug probe compatible with the chosen part and its price in India, and whether an evaluation board exists that would let firmware work start before the PCB is fabricated.

- [ ] **Step 5: Write the memo and commit**

State the verdict in the first line: confirmed, or changed with reasoning.

```bash
git add docs/research/05-mcu-selection.md
git commit -m "research: MCU confirmation, availability and toolchain"
```

---

### Task 6: Standards and compliance scope

**Files:**
- Create: `docs/research/06-standards.md`

**Interfaces:**
- Consumes: Task 1's emissions tier.
- Produces: the test and design requirements Phase 3 layout must honour, and an honest scope statement on certification.

- [ ] **Step 1: SAE J1939 layers that apply**

Summarise what each relevant part requires of this design: J1939-11 (twisted-pair physical layer, termination, stub lengths), J1939-21 (transport protocol, BAM vs RTS/CTS), J1939-71 (the PGN definitions Task 2 identified), J1939-73 (diagnostics, DM1/DM2), J1939-81 (address claiming).

- [ ] **Step 2: ISO 7637-2 transient immunity**

Record the pulse definitions that apply to a 12 V system — 1, 2a, 2b, 3a, 3b and load dump 5b — with their amplitudes and the severity levels typically specified. This sets the TVS clamp voltage and the buck's input rating.

- [ ] **Step 3: CISPR 25 conducted emissions**

Record the frequency bands and class limits. Note what bench equivalent (LISN plus spectrum analyser) gives useful indication short of a test house, and what it cannot tell you.

- [ ] **Step 4: State the certification position honestly**

This is a replacement controller on an emissions-certified engine. Record plainly what that means: modifying the engine controller on a CPCB-IV+ certified genset affects its certification status, and a replacement ECU is not covered by the original certificate. State the regulatory position for a genset in service in India and flag it as a decision for the project owners, not an engineering detail.

- [ ] **Step 5: Write the memo and commit**

```bash
git add docs/research/06-standards.md
git commit -m "research: J1939, ISO 7637-2, CISPR 25 and certification scope"
```

---

### Task 7: Consolidated BOM and sourcing

**Files:**
- Create: `docs/research/07-bom-sourcing.md`

**Interfaces:**
- Consumes: Tasks 3, 4 and 5 — connector, injector driver and MCU are the three hard sourcing problems.
- Produces: a costed BOM skeleton for Phase 2 capture, with every line either sourced or flagged.

- [ ] **Step 1: Build the BOM skeleton from the spec**

One line per functional block in spec §4 and §6: EMI filter, reverse-battery controller and P-FET, TVS, buck, sensor-rail LDO and PTCs, 3V3 LDO, supervisor, MCU, crystal, 2× CAN transceiver and protection, VR conditioner, EGR H-bridge, metering-unit low-side driver, injector driver and boost stage, relay-drive FETs, barometric sensor, connectors.

- [ ] **Step 2: Price and check stock for every line**

For each: manufacturer part number, distributor, stock quantity, INR unit price at qty 1 and qty 100, lead time. Prefer automotive-qualified (AEC-Q100/Q101) parts and record the qualification status per line.

- [ ] **Step 3: Flag every single-source and long-lead line**

Any line with one supplier, or a lead time beyond eight weeks, gets flagged with a named second source or an explicit "no alternative identified". These are the lines that stall a build.

- [ ] **Step 4: Produce a headline cost**

Total BOM cost at quantity 1 and quantity 10, excluding PCB fabrication and assembly. Note separately the estimated 4-layer PCB fab cost for the expected board area.

- [ ] **Step 5: Write the memo and commit**

```bash
git add docs/research/07-bom-sourcing.md
git commit -m "research: consolidated BOM with India sourcing and cost"
```

---

### Task 8: Engine inspection brief

**Files:**
- Create: `docs/research/08-engine-inspection-brief.md`

**Interfaces:**
- Consumes: Tasks 1, 3 and 4 — each contributes an item that only physical access resolves.
- Produces: a single checklist someone takes to the machine, closing six unknowns in one visit.

**Closes:** U2, U6, U7, U8, U9, U10 — none of which desk research can close.

- [ ] **Step 1: Collect every unknown that needs the physical engine**

From spec §8: U2 (boost air-temp topology), U6 (pin 09 synchronisation ground), U7 (whether pins 04/06 are sense-only or load feeds), U8 (6-pin intake throttle — on the ECU at all?), U9 (catalyst temperature sensor routing), U10 (which signal uses SENT). Add U1's connector photograph from Task 3 and U11's rating plate from Task 1.

- [ ] **Step 2: Write the photograph list**

For each: what to photograph, from what angle, and what detail must be legible. Engine rating plate. ECU case label and connector mating face. Boost P&T sensor body — the part number on it settles U2 outright. Injector body. Intake throttle connector and its cable run. Catalyst temperature sensor and where its harness goes. KG640C terminal strip.

- [ ] **Step 3: Write the measurement list**

Measurements need the harness live or disconnected — say which for each, and give the expected reading so an anomaly is recognisable on the spot.

For U2: resistance across boost sensor pins 2 and 1 with the connector unplugged and the engine cold. A few kΩ that falls as it warms means NTC; an open or a fixed high reading suggests a conditioned ratiometric output. This single measurement closes U2.

For U7: voltage on ECU pins 04 and 06 with ignition on, then current draw if it can be measured safely at the fuses. Sense-only pins draw milliamps; load feeds draw amps.

For U6: continuity from pin 09 to battery negative and to sensor ground, engine off, battery disconnected.

- [ ] **Step 4: Write the safety preamble**

The brief is for someone working on a genset. Lead with: battery disconnected before any continuity measurement; no measurement inside the alternator output enclosure; the engine does not run during any of this. State that if the set must run for a measurement, that is a separate supervised activity and not part of this checklist.

- [ ] **Step 5: Write the memo and commit**

Format it as a checklist that works printed and carried, not as a report.

```bash
git add docs/research/08-engine-inspection-brief.md
git commit -m "research: engine inspection brief closing six physical unknowns"
```

---

## Phase exit criteria

Phase 1 is complete when:

- [ ] U3 has a verdict. The safety gate in spec §3 is either satisfiable or has a named trip module.
- [ ] U5 has a drive envelope sufficient to design the injector stage, and the calibration boundary is stated in writing.
- [ ] U11 is closed, or the rating-plate photograph is specified and requested.
- [ ] U1 has a ranked candidate list and a photograph brief.
- [ ] The MCU is confirmed or replaced, with stock verified.
- [ ] The engine inspection brief exists and has been handed to whoever has access to the machine.
- [ ] Every unknown that remains open is recorded in an updated spec §8 with what would close it.

**Final step:** update spec §8 in place so the register reflects reality, and commit that edit with the phase.

## What this plan does not cover

Phases 2, 3 and 4 get their own plans, written once Phase 1 closes the unknowns they depend on:

- **Phase 2 — schematic capture.** Can begin on power, CAN, MCU support, speed inputs and relay outputs before Phase 1 finishes. Blocked on U1 for connectors, U2 for the boost air-temp front-end, U5 for the injector stage, U8 for the throttle.
- **Phase 3 — PCB layout.** Blocked on Phase 2.
- **Phase 4 — firmware skeleton.** Unblocked by Phase 1 except for the J1939 layer, which needs Task 2. Could run in parallel.
