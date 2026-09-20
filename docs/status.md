# Build Status — What Is Done and What Is Not

**As of 20 September 2026, end of session.** Counts in this document are generated from the repository,
not maintained by hand: the block results come from `sim/run_sim.py`, the unknowns from
the specification's own register.

---

## At a glance

| | Count |
|---|---|
| Circuit blocks simulated | **24** |
| Blocks passing every check | **24** |
| Blocks failing a check | **0** |
| Research memos | **12** |
| Documents in the bible | **18** |
| Unknowns closed | **4** |
| Unknowns partly answered | **4** |
| Unknowns still open | **9** |
| Phase | **2** — schematic capture, 6 of 10 sheets drawn |

**All 24 blocks pass.** On 19 September it was 16, after a temperature-corner pass found
six blocks that fail cold or hot and turned prose caveats into enforced checks. All six
are now answered, and the answers are part specifications rather than widened checks —
every one of them is written up in `docs/bom_requirements.md` with the block that demands
it, and every failing corner is kept as pinned evidence of *why* the requirement exists.

**One of the six was not a part-selection problem at all.** The metering unit's coil is
copper, copper moves 0.39 %/°C, and no better resistor exists to buy. It needed closed-loop
current control, which put a 50 mΩ shunt and a sense amplifier on ECU pin 88's return —
new schematic content, not a BOM line. See §1.7.

**Schematic capture has started; no PCB exists and no firmware has been written.** The
KiCad project is in `hw/`, with all ten hierarchical sheets created and the first —
`power_input` — drawn and netlist-checked. See §7.

---

## 1. Circuit blocks — simulated and passing

Each block is a SPICE netlist plus a set of falsifiable checks. A block "passes" when
every claim it makes about itself holds. These are design verification, not layout.

### 1.1 Power chain — 9 blocks

| Block | What it covers | Status |
|---|---|---|
| `emi_filter` | Two-stage LC, CISPR 25 conducted, differential mode | Passing |
| `reverse_battery` | Ideal-diode P-FET vs series Schottky | Passing |
| `transient_clamp` | ISO 7637-2 pulse 2a, +112 V / 2 Ω / 50 µs | Passing |
| `load_dump` | ISO 7637-2 pulse 5b, 40 V / 0.5 Ω / 400 ms | **FAILS — deliberately** |
| `buck_preregulator` | 6–40 V to 5 V at 400 kHz | Passing |
| `sensor_rail` | 5 V sensor distribution, one PTC per group | **FAILS — cold corner** |
| `mcu_pdn` | 3V3 decoupling impedance, 100 mΩ target | **FAILS — cold corner** |
| `supervisor` | Watchdog, brownout, fail-safe gate kill path | Passing |
| `negative_pulses` | ISO 7637-2 pulses 1 and 3a, negative excursions | **FAILS — real gap** |

**Why `load_dump` fails, and why that is correct.** The TVS chosen against pulse 2a
absorbs 46 J at 116 W under pulse 5b — roughly 100× both its single-pulse energy rating
and its continuous dissipation rating. The failure is the deliverable: it says the part
selection is wrong, not that the simulation is. The fix is a higher standoff voltage so
the TVS stays off during a normal clamped load dump, rather than a larger part to absorb
it. **Blocked on U16** — whether the alternator is suppressed at all decides which pulse
applies.

### 1.2 Sensor front-ends — 7 blocks

| Block | What it covers | Status |
|---|---|---|
| `sensor_ratiometric` | Pins 41/35/80/37, 0.5–4.5 V into a 3.3 V ADC | Passing |
| `sensor_differential` | Shared sensor ground on pin 34, single-ended vs differential | Passing |
| `ntc_frontend` | Pin 79 charge-air temperature, divider vs current source | Passing |
| `battery_sense` | Pins 04/06, 6–40 V rail into a 3.3 V ADC | Passing |
| `discrete_input` | Pins 20/24/71, active-high switched battery | Passing |
| `trip_module_sense` | Trip-module state, supervised three-state loop | Passing |
| `cam_frontend` | Pin 46 cam Hall, 5 V swing divided into the 3.3 V domain | Passing |

`ntc_frontend` simulates **both** candidate topologies because **U2** is unresolved. One
resistance measurement at the machine picks between them; the front-end is designed so
that measurement selects a populate option rather than unblocking a redesign.

### 1.3 Speed and position — 1 block

| Block | What it covers | Status |
|---|---|---|
| `vr_conditioner` | Crank VR sensor, pins 52/74/30 | Passing |

### 1.4 Injection — 3 blocks

| Block | What it covers | Status |
|---|---|---|
| `injector_boost` | Why the boost stage exists, pins 03/05 | **FAILS — both corners** |
| `injector_turnoff` | Turn-off recirculation into the boost rail | Passing |
| `boost_converter` | Injector rail reservoir sizing | Passing |

`boost_converter` passes but carries a recorded gap: it has **no bleed path**. Its charge
source regulates the rail from below only. Harmless while current flowed outward;
`injector_turnoff` now pushes energy back in, and a hold-current cutoff would climb the
rail about 2 V per event with no way down.

### 1.5 Actuators — 3 blocks

| Block | What it covers | Status |
|---|---|---|
| `metering_unit_pwm` | Pin 88, low-side PWM into the fuel metering solenoid | **FAILS — both corners** |
| `relay_driver` | Pins 50/69, low-side FET with flyback | Passing |
| `egr_hbridge` | Pins 59/81, positional actuator, feedback on 37 | **FAILS — shoot-through** |

### 1.6 Communications — 1 block

| Block | What it covers | Status |
|---|---|---|
| `can_termination` | Split vs single termination, J1939 250 kbit/s | **FAILS — tempco** |

---

### 1.7 The six corners that were failing, and what each one bought

All six are closed. None was closed by widening a check: each is answered by specifying a
part, with the failing corner kept as pinned evidence. The requirements live in
`docs/bom_requirements.md` under the tags below.

| Block | Was | Answer | Tag |
|---|---|---|---|
| `can_termination` | 123.95 Ω at 200 ppm/°C vs J1939's own 120 Ω | thin-film, 0.1 %, 50 ppm/°C → 121.10 Ω at stacked worst case | `CAN-TERM` |
| `sensor_rail` | 4.15 A at cold + −30 % vs a 3.0 A polyfuse ceiling | PTC R25 2.0 → 3.0 Ω, solved against the ceiling → 2.88 A | `SENSOR-PTC` |
| `mcu_pdn` | 197 mΩ at a wet electrolytic's cold ESR vs 100 mΩ | polymer bulk, ESR **band** 20–50 mΩ → 60 / 92 mΩ | `PDN-BULK` |
| `metering_unit_pwm` | 0.862 A cold / 0.462 A hot vs a 0.675 A setpoint | closed-loop current control → 0.679 / 0.683 A | `MU-ISENSE` |
| `negative_pulses` | VIN −0.528 V vs the LM5164's −0.3 V | active clamp → −0.068 V | `NEG-CLAMP` |
| `injector_boost` | ratio missed 11.6× at both corners | 11.6× was this block's *nominal*, never a requirement | — |

Three of those were more than part swaps, and they are the ones worth reading.

**The metering unit needed an architecture change.** Over −40…+125 °C the coil's
resistance goes 7.39 → 13.82 Ω and at fixed duty the current follows it, ±30 %. A
hysteretic current regulator holds 0.679 / 0.679 / 0.683 A at −40 / 25 / +125 °C. Closed
loop only works while the regulator has duty left: at the hot corner the coil can draw at
most 0.977 A at 100 % duty, so the setpoint sits at 69 % of the ceiling. That bound is
checked, because a regulator out of headroom degrades silently back to open-loop.

**The negative clamp needed a FET, for a structural reason.** A Schottky's drop at the
15 A pulse 1 delivers decomposes as 0.367 V junction + 0.180 V bulk, and only the bulk
term falls when parts are paralleled — four of them still leave 0.375 V. The rating is
really a demand for ≤ 20 mΩ effective clamp impedance *including the junction*, which no
junction device meets and a 5 mΩ FET clears four times over. Still open but now bounded:
the comparator's propagation delay is unmodelled, so the question went from *"is a 2 ms
excursion acceptable"* to *"is a sub-microsecond one"*.

**The PDN requirement had to be a band, not a ceiling.** Bulk ESR is also what damps the
regulator-against-bulk resonance, so at 20 mΩ the peak climbs back to 92 mΩ. "ESR ≤ 50 mΩ"
would have been satisfied by a 5 mΩ part that fails the block.

**A near-miss worth recording.** The active-clamp branch first shared the battery node
with the unprotected one, and at 13 mΩ to ground it shunted the fault for that branch too
— reporting −0.177 V where the true Schottky-only figure is −0.528 V, i.e. reporting the
problem as already solved. Caught because the clamp diode's own ammeter read 13 mA where
15 A was expected.

**Two stale checks were also found.** `negative_pulses` still demanded 0.707 J from the
TVS, from before the clamp Schottky existed — the TVS no longer conducts on negative
pulses at all, and the requirement moved onto the part that now carries it (13.58 A peak,
14.5 mJ). And a burst-accumulation check conflated first-pulse settling with
accumulation; repeats 2–5 are identical to the printed precision.

**One block passes in a way worth reading.** `emi_filter` was not failed at its corner,
because its −40 dB gate is documented in its own final check as being of unknown adequacy
pending measured hardware emissions. Failing a corner against an admittedly arbitrary
number manufactures a verdict. The X7R −15 % corner is recorded as regression pins with a
note that the value sits below the nominal gate.

---

## 2. Circuits not yet built at all

These have no netlist, no schematic and no checks. They are the real gaps.

| Missing circuit | Pins | Why it is not built |
|---|---|---|
| **Negative-input protection for the buck** | pin 21 chain | **Found 19 Sep.** The LM5164's VIN is rated −0.3 V to 100 V; the negative limit is not a mirror of the positive one and nothing was sized against it. The TVS clamps correctly to −38 V, which is still two orders of magnitude outside what the buck tolerates. A missing component, not a mis-sized one |
| **Intake throttle driver** | 6-pin connector | **Blocked on U8.** Reported battery-fed, which answers who supplies it, not who commands it. May be out of scope entirely |
| **Pre/post-heat output** | unknown | **Blocked on U14.** Same distinction — battery-fed is not the same as ECU-switched. The DSE4522 enables both at 50 °C and this design has no heater output |

---

## 3. Verification not yet done

The blocks above are each simulated in isolation, at one temperature, against the
stimuli named. These are the gaps in the *verification*, not in the circuits.

| Gap | Consequence |
|---|---|
| ~~No temperature corner anywhere~~ | **Done 19 Sep**, −40/+125 °C across all blocks. Six fail at a corner — `emi_filter` and `can_termination` from *ordinary specified* component behaviour, not stacked worst cases. Being converted from prose into enforced checks |
| ~~ISO 7637-2 negative pulses unsimulated~~ | **Done 19 Sep.** The TVS is now modelled as the bidirectional part it is, which is what made the question answerable. Result: the buck's VIN sees −40.7 V against a sourced −0.3 V absolute maximum — see the new gap below |
| **Common-mode EMI unmodelled** | `emi_filter` covers differential mode only. Most real automotive failures are common mode, and modelling it honestly needs a layout to give the return path |
| **Reverse-battery transient — now load-bearing** | The switch model turns off instantly, so it always looks perfect. That was a caveat; since `negative_pulses` it is a design dependency. If the controller opens fast enough the buck is isolated; if not it sees the full clamped negative voltage. No controller part is chosen and no turn-off delay is sourced, so both bookends are simulated and neither is claimed |
| **Watchdog fault-detection time** | `supervisor` bounds only what happens *after* reset asserts, not how long detection takes |

---

## 4. Documents

| Document | State |
|---|---|
| Reconciled Specification | **Binding.** Rewritten §3 on the fitted controller, §4 gained a hardware fail-safe requirement, register extended to U16 |
| Field Handbook | Current |
| Sensor Reference | Current |
| Circuit Reference | Generated from the simulations at build time, so it cannot drift |
| Memos 01–12 | Dated records. Superseded conclusions carry banners rather than being rewritten |

**Memo 01 and Memo 02 are substantially wrong** and say so at the top. Memo 01
misidentified the engine and advised discarding the correct search term. Memo 02
analysed a controller that is not fitted. They are kept because the reasoning that
produced them is the record of how the error happened.

---

## 5. Unknowns

### Closed — 4

| # | Question | Answer |
|---|---|---|
| U11 | Engine identity | `3GK550ETA 4SR1`, app code `GK3.8703`, CPCB IV+ under certificate `P25/2825/24` |
| U1 | ECU connector | Bosch `1 928 405 192` / `194`, **code C** keying |
| U13 | Which controller is fitted | **DSE4522 MKII AMF**, not the KG640C the diagram shows |
| U12 | Does the fuel relay remove power? | **No — it only signals** |

**Three of these four closed against what this project had reasoned.** That is the
single most useful thing to know about the desk work: it is productive, and it is not
reliable without the machine.

### Partly answered — 4

**U4** CAN expectations (addresses 234 and 44 confirmed) · **U5** injector drive profile
(family envelope only, no part number) · **U8** throttle (supply known, control not) ·
**U14** pre/post-heat (supply known, control not)

### Open — 8

**U2** charge-air sensor topology · **U6** pin 09 function · **U7** pins 04/06 sense or
feed · **U9** catalyst sensor routing · **U10** SENT signal identity · **U15** what
`CRS-878` denotes · **U16** alternator rectifier suppressed or not · plus U12's
contact-type confirmation, which gates nothing

---

## 6. Decisions open, and blocking

| Decision | Blocks | Why it cannot wait |
|---|---|---|
| ~~Integrated driver IC vs discrete FETs~~ | — | **DECIDED 19 Sep 2026, memo 12.** Discrete FETs, keeping the 100 V rail. MC33816 caps at 72 V, L9781 at a reported 80 V, and both are pre-drivers that need external FETs anyway |
| ~~Passive pulldown vs active clamp~~ | — | **DECIDED 19 Sep 2026, memo 12.** Active clamp, built discretely, at every gate. The integrated route relocates this problem rather than removing it |
| **MC33816 last-time-buy 06/08/2027** | Fallback path only | Needs a distributor conversation, not another search |
| **L9781 datasheet unretrievable** | Confirming the decision's runner-up | Five failed fetches across two sessions. Needs FAE or distributor access |
| **Ideal-diode controller for Q1** | `power_input` sheet, `reverse_battery`, `negative_pulses` | Its turn-off time is load-bearing and unsourced. `VBAT_REV_GATE` is undriven on the sheet until a part is chosen |
| **Negative-clamp comparator for Q2** | `power_input` sheet, `negative_pulses` | Its propagation delay is the last unmodelled term in the negative-pulse chain. `NCLAMP_GATE` is undriven until a part is chosen |
| **Air-intake shutoff** | Nothing electrical | Owners' decision. Nothing in this design can stop an oil-fuelled runaway |
| **Trip-module pickup target** | Module ordering | Whether it shares our flywheel target. Sharing is cheaper; separate preserves the independence that is the reason for fitting it |

---

## 7. Phases

| Phase | Output | State |
|---|---|---|
| 0 | Reconciled specification | Done |
| 1 | Research memos | Done — twelve |
| 1.5 | Block-level simulation | **Done — 24 blocks, 24 passing** |
| **2** | **KiCad hierarchical schematic capture** | **In progress — 6 of 10 sheets drawn** |
| 3 | 4-layer PCB layout, DRC, fab outputs | Not started |
| 4 | Firmware skeleton | Not started |

### Phase 2 — what exists

The project is `hw/ecu25kva.kicad_pro`. Everything in it is generated, and the generators
refuse to overwrite a sheet that has content, so Eeschema edits are safe against a re-run.

| Sheet | State | Blocks it realises |
|---|---|---|
| `power_input` | **Drawn, netlist-checked** | `emi_filter`, `transient_clamp`, `load_dump`, `negative_pulses`, `reverse_battery` |
| `rails` | **Drawn, netlist-checked** | `buck_preregulator`, `mcu_pdn`, `sensor_rail` |
| `mcu` | **Drawn, netlist-checked** | `supervisor`, `mcu_pdn` |
| `injector` | Created, empty | `boost_converter`, `injector_boost`, `injector_turnoff` |
| `metering_egr` | **Half drawn** — metering unit done; EGR blocked on a rail rating | `metering_unit_pwm`, `egr_hbridge` |
| `sensors_analog` | Created, empty | `sensor_ratiometric`, `sensor_differential`, `ntc_frontend`, `battery_sense` |
| `speed_inputs` | Created, empty | `vr_conditioner`, `cam_frontend` |
| `discrete_io` | **Drawn, netlist-checked** | `discrete_input`, `trip_module_sense`, `relay_driver` |
| `can` | **Drawn, netlist-checked** | `can_termination` |
| `connector` | Created, empty | — |

**The S32K148 symbol is generated from NXP's own pin table, and no pin number is retyped
anywhere in the chain.** KiCad 7 ships no S32K symbol. The package pin numbers live only
in `S32K148_IO_Signal_Description_Input_Multiplexing.xlsx`, which is not a download but
one of eleven workbooks embedded as attachments inside the Reference Manual PDF. That file
had been extracted once and not kept, so `docs/pinmap.md` cited a source the repo no
longer held. It is now in `refs/`, with checksums, and `hw/extract_pinmux.py` makes the
extraction reproducible. Re-extracting confirmed three of pinmap.md's claims
independently: 128 port + 16 supply = 144 pins with every package pin accounted for; the
six driver-gate pins are all PE=0 PS=0; and exactly four pins on the whole part carry a
reset pull, which are precisely the four JTAG/RESET pins pinmap.md reserved.

**Three parts have moved from a class to a part number**, each against a
retrieved datasheet, and all three are in `docs/bom_requirements.md`:
`LM5164DDAR` (buck), `TLV76733QWDRBRQ1` (3V3), `TPS3850G33DRCT`
(supervisor). Two of them supersede rows in research memo 07, which is
now annotated in place.

**The buck row is worth reading as a process failure, not just a part
change.** Memo 07 chose a 60 V part for load-dump margin, correctly, at
the time. The input-protection work then raised the TVS standoff and put
the pulse 2a clamp at 73.3 V — and `transient_clamp.cir` has carried a
*passing* check reading "60 V-class parts are NO LONGER viable
downstream" ever since. The contradiction sat between an executable file
and a prose table for days, and only the executable one knew. Nothing
compares them. It surfaced when someone had to draw the buck and needed a
pinout.

**Check the netlist, not the plot.** Three bugs on the first sheet were invisible on a
correctly-plotting page and obvious in the exported netlist: a rotation helper with 90 and
270 swapped, which put the clamp Schottky's cathode on ground; custom part fields starting
at property id 2, which KiCad reserves, silently renaming the first one "Footprint"; and
labels offset from their wires for looks, which detaches them silently while the page
still reads as connected.

**A wire endpoint landing mid-span on another wire does not connect** —
not in KiCad 7's netlister, and not even with an explicit junction
element in the file. Interactively, Eeschema *splits* the underlying wire
when you drop a junction on it; a generated file has no such split, so
the two cross without meeting. The page plots exactly as intended and the
netlist reports every tapped part as unconnected. Found on the rails
sheet, where the input capacitor, the UVLO divider and the RON resistor
all tapped the middle of one wire and all three came back unconnected.
`schlib.Rail` now emits one segment per interval and is the only thing
allowed to draw a multi-tap rail.

**Drawing the sheets is finding things nothing else was going to find.**
Three so far, all of the same shape — a document and an executable file
disagreeing, with nothing that compares them:

- **No watchdog pin.** The pin map assigned 37 signals and none serviced
  the external watchdog memo 11's supervisor topology requires. A window
  watchdog nobody feeds resets the board on a timer. `PTE0`/`PTE1` added.
- **The buck was a 60 V part on a 73.3 V rail.** `transient_clamp.cir`
  had carried a *passing* check saying 60 V-class parts were no longer
  viable for days, while memo 07's BOM still named one.
- **The trip sense was a GPIO on a three-state loop.**
  `trip_module_sense.cir` designs and checks three bands with real
  margin; a GPIO reads two, which discards exactly the distinction the
  bleed resistor exists to create. Moved `PTD6` → `PTB0` (ADC0_SE4).

**The battery rail's rating is now enforced, not narrated.** VBAT_PROT
reaches 40.0 V for 400 ms on a load dump and 73.3 V for ~50 µs on pulse
2a, and `transient_clamp.cir` checks what that excludes: a 40 V-abs-max
integrated driver by 1.8×, with the dump alone leaving it no margin. The
practical consequence is that integrated automotive H-bridges and smart
switches — a 40–45 V class — are excluded from everything
battery-connected here, which is what blocked the EGR half of
`metering_egr`.

**What ends phase 2:** the nine remaining sheets, and the two gates currently left
undriven on `power_input` (§6).

---

## 8. Work at the machine

Ordered by what it unblocks.

| Task | Closes | Unblocks |
|---|---|---|
| Alternator rectifier part number, or a scope during a live disconnect under load | **U16** | The whole input-protection topology, and `load_dump`'s failure |
| Resistance across the charge-air element, cold | **U2** | The `ntc_frontend` populate choice |
| Follow the throttle's 6-pin cable to where it ends | **U8** | Whether a throttle driver exists at all |
| Trace who switches the heater feed | **U14** | Whether a heater output is in scope |
| Injector part number from the body | **U5** | The boost rail's target voltage |
| Relay contact-type check | U12 confirmation | Nothing — recorded for completeness |

---

## 9. Resume here — next session

Written at the end of 20 September so the next session does not have to re-derive where
things stand. **Nothing is half-finished: the tree is clean, all 24 blocks pass,
everything is pushed.**

### What closed today

Phase 1.5 is done. All six temperature-corner failures are answered, and the answers are
in `docs/bom_requirements.md` rather than in a widened check — see §1.7 for what each one
cost and which three were more than part swaps.

Phase 2 started. The KiCad project exists with all ten sheets, the S32K148 symbol is
generated from NXP's own pin table, and `power_input` is drawn and netlist-checked.

### Next, in order

**1. Draw the remaining sheets.** The generator and its helper (`hw/schlib.py`) are in
place, so each sheet is now a matter of describing its parts and their provenance. Order
by what unblocks the most:

- `mcu` — the pin map is done and every other sheet references it
- `rails` — `buck_preregulator` plus the two specified parts (`PDN-BULK`, `SENSOR-PTC`)
- `metering_egr` — carries the new current-sense requirement (`MU-ISENSE`)
- `can` — small and fully specified (`CAN-TERM`)
- then `injector`, `sensors_analog`, `speed_inputs`, `discrete_io`, `connector`

**2. Check each sheet's netlist, not its plot.** Every bug found on the first sheet was
invisible on a page that plotted correctly. `kicad-cli sch export netlist` is the check;
KiCad 7's CLI has no ERC subcommand, so this stands in for it.

**3. Two parts still need choosing**, and both show up as undriven gates on `power_input`
(§6): the ideal-diode controller and the negative-clamp comparator. Neither pinout can be
drawn without a datasheet.

### Needs a person, not an agent

- **MC33816AE last-time-buy 06/08/2027** — a distributor conversation, not another search.
- **L9781 datasheet** — five failed retrievals across three sessions. Needs FAE or
  distributor access.

### At the machine

See §8. **U16 (the alternator rectifier) no longer gates the input-protection topology** —
that closed when the TVS standoff and the active clamp were specified — but it still
decides which ISO 7637-2 pulse applies, and it is the first thing to settle.

### The pattern worth carrying forward

Every wrong number found in this project so far has been found in prose, not in a check.
The corner that fails is the one that is written as an enforced check; the corner that is
written as a caveat in a comment is the one that gets believed. The same held today at the
schematic: three real errors, all invisible on the page, all obvious in the netlist.
