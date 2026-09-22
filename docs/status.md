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
| Phase | **2** — schematic capture **complete**: 10 sheets, root wired, project netlist checked |

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
| **2** | **KiCad hierarchical schematic capture** | **Complete — 196 components, 113 multi-pin nets, 18 named open ends** |
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
| `injector` | **Drawn, netlist-checked** | `boost_converter`, `injector_boost`, `injector_turnoff` |
| `metering_egr` | **Half drawn** — metering unit done; EGR blocked on a rail rating | `metering_unit_pwm`, `egr_hbridge` |
| `sensors_analog` | **Drawn, netlist-checked** | `sensor_ratiometric`, `sensor_differential`, `ntc_frontend`, `battery_sense` |
| `speed_inputs` | **Drawn, netlist-checked** | `vr_conditioner`, `cam_frontend` |
| `discrete_io` | **Drawn, netlist-checked** | `discrete_input`, `trip_module_sense`, `relay_driver` |
| `can` | **Drawn, netlist-checked** | `can_termination` |
| `connector` | **Drawn, netlist-checked** | — (not a circuit: the harness boundary) |

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
Six so far, all of the same shape — a document and an executable file
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
- **The cam front-end put 5 V on a 3.3 V pin.** Spec §4 and pinmap §1.3
  both gave pin 46's front-end as "pull-up to `5V_SENSOR` → timer
  capture", and no `sim/blocks/*.cir` file simulated a cam front-end at
  all — `vr_conditioner.cir` covers the crank and there was no cam
  equivalent, so the swing was never checked. `cam_frontend.cir` was
  written, and one 16 kΩ resistor turns the pull-up into the same
  10 k/16 k divider the ratiometric channels already use.

- **A ground-referenced kill clamp cannot service a high-side gate.**
  Spec §4's fail-safe list names pins 03/05 alongside the four low-side
  gates, and `supervisor.cir` sized a ground-referenced clamp; pinmap §2
  confirmed the reset state of all six pins against NXP's own table. All
  three agree, and all three are silent on the fact that the source of a
  high-side N-FET swings to the boost rail. The injector sheet puts the
  470 Ω across gate and *source*, and moves the kill path into the
  driver's shutdown input.

- **The power ground has no connector pin.** `GP3.8703.C4.pdf` shows
  pin 21 as the battery positive feed and no battery negative anywhere,
  because it is a field troubleshooting diagram and says so: it omits
  "power grounds, unused pins and internal-only pins". Every other sheet
  returns to `GND` — the injector low sides put 18 A into it — and at
  the harness boundary that net has nowhere to go. It cannot be solved
  by choosing one of the 50 unknown pins: a wrong ground pin is a
  harness that has to be remade, not a rework.

**A seventh finding came out of the parts, not the pins.** Every clamp
earlier in this project was chosen by forward drop. The crank input's
four clamp diodes have to be chosen by *reverse leakage* instead:
Schottky leakage at 125 °C puts ~0.90 V of offset across the comparator
input's 4.489 kΩ Thévenin, which is 4.5× the whole ±198 mV hysteresis
window — the comparator latches and a running engine has no speed
signal. `vr_conditioner.cir` cannot see this: its comparator is an ideal
switch with no input network, so no clamp, no leakage and no offset
exist in it. Tagged `VR-CLAMP` in `docs/bom_requirements.md`.

**The battery rail's rating is now enforced, not narrated.** VBAT_PROT
reaches 40.0 V for 400 ms on a load dump and 73.3 V for ~50 µs on pulse
2a, and `transient_clamp.cir` checks what that excludes: a 40 V-abs-max
integrated driver by 1.8×, with the dump alone leaving it no margin. The
practical consequence is that integrated automotive H-bridges and smart
switches — a 40–45 V class — are excluded from everything
battery-connected here, which is what blocked the EGR half of
`metering_egr`.

**Two open items were closed by drawing, not by deciding.** The injector
current-sense placement (`pinmap` §1.6, INFERRED per-bank, "settle when
the sheet is drawn") is settled: low-side, ground-referenced, one per
bank, because cylinders 1 and 3 fire 240 crank degrees apart and never
overlap. And the boost reservoir's missing bleed path — which
`injector_turnoff.cir` asked for by name — is now modelled in
`boost_converter.cir` as arrangement C and drawn as a 22 kΩ resistor:
one hold-cutoff event clears in 21.4 ms against the 26.67 ms between
cylinders, for 455 mW burned continuously.

**The root sheet is wired and the project has a netlist for the first
time.** Until 21 September 2026 `hw/ecu25kva.kicad_sch`'s ten sheet
symbols carried **no hierarchical pins**, which meant every sheet's own
netlist was correct and the project had none: a name on two sheets was
two nets and nothing compared them. Each symbol now carries one pin per
net its child exports — 162 pins — with a stub and a label, and two
labels with the same name are one net.

Exporting it immediately found the second half of the same problem:
**`kicad-cli` reported annotation errors**, because each sheet generator
allocated `R1`, `C1`, `U1` from its own counter. Ten sheets, ten parts
called `R1`. `schlib.REF_BASE` now gives each sheet its own hundred —
KiCad's own sheet-number × 100 convention, applied at generation time
rather than by a hand pass in Eeschema.

| | |
|---|---|
| components | **201**, every reference unique |
| named nets with ≥2 pins | **108** (the four `5V_MAIN` islands merged into one) |
| named nets with 1 pin | **18**, each a recorded open item |
| sheet paths | 10 |
| `GND` / `3V3_MCU` / `5V_MAIN` / `VBAT_PROT` | 139 / 36 / 28 / 12 pins, all spanning the project |

**Exporting it for the first time found three real defects that ten
clean per-sheet netlists could not.**

1. **`5V_MAIN` was four nets.** The buck's 5 V output is a board rail —
   the CAN transceivers' VCC, the five difference amplifiers and the
   discrete inputs' pull-ups all run off it — and it was a *local* label
   on every one of those sheets. A local label stops at its sheet's
   edge, so three of the four copies had no regulator on them, and each
   sheet's own netlist was perfectly correct. `rails` now exports it.
2. **`3V3_MCU` was three.** Same mechanism, on `can` (both transceivers'
   VIO) and `speed_inputs` (the comparator's supply, both upper clamp
   diodes and the bias divider — five pins and no rail).
3. **Five supply pins had no decoupling capacitor.** The difference
   amplifiers on `sensors_analog` were the only undecoupled supply pins
   on the board. No simulation block was ever going to say so:
   `sensor_differential.cir` models an ideal amplifier with no supply
   pin at all.

All three are now permanent checks rather than one-off observations: one
walks every `power_in` pin and asks whether a capacitor sits on its net,
and one fails any sheet-local net whose name shadows a project-wide one
— the exact shape of defects 1 and 2.

`hw/check_netlist.py` is the gate, and it is the counterpart to
`sim/run_sim.py`: that one guards the component *values*, this one
guards the *connectivity*. It enforces the same rule — **an exemption is
not a pass**. Every single-pin net must be listed with its reason, and a
net that stops being single-pin must be removed from the list or the
check fails. An open item that quietly closes is as much a drift as one
that quietly opens.

The full schematic set plots to `docs/pdf/ECU-Schematics.pdf`, 11 pages.

**Phase 2 is done.** What remains under these sheets is not schematic
work — it is eighteen named open ends, and every one waits on a
datasheet, a part number, or the machine:

- **nine** driver / current-sense-amplifier interfaces (requirements
  drawn, parts not chosen)
- **two** controller gates on `power_input`
- **five** for the EGR bridge, blocked on a gate driver above 73.3 V
- **two** with no part and no pin: `BARO`, and `TRIP_LOOP` — which
  needs one of the 50 unconfirmed connector pins, as does `GND`

**Correction, 21 September 2026 — the connector's part number was in
the repo and the sheet said it was not.** `hw/connector.kicad_sch` was
drawn from `refs/ecu-pinout-extracted.md`, which predates the field
visit and still says "a complete pinout requires the connector part
number and the OEM pin list". `refs/field-evidence-2026-09-18.md` §2b
closed U1 three days earlier, off a photograph of the housing angled to
the light: **Bosch `1 928 405 192` / `1 928 405 194`, code C**,
`>PA66-GF50<`, EDC17 family — read off the physical part, which beats a
catalogue match because it cannot be a mis-identification. **Code C is
load-bearing**: Bosch codes these housings mechanically so
differently-coded plugs cannot mate. What is still missing is the OEM
*pin list*, a different document, and the board-side land pattern —
neither number returns a catalogue hit, so the footprint has to come
through a Bosch distributor. Same shape as the six findings above, and
this one was mine: reading the older reference and not the newer one.

**The negative clamp latched, and a passing check hid it — 22 September
2026, 8 → 7 open ends.** Choosing its comparator meant setting real
thresholds, and the model's were wrong: engage near +0.08 V, release above
+0.12 V. At the end of every negative pulse the returning source drove
1.35 A back through the still-on clamp — 6.7 mV across 5 mΩ, never
reaching release — so it **latched on and shorted the source**. The check
measured only the clamp's minimum and said RESOLVED; a recovery check
failed on both pulses. It is a low-side ideal diode and now releases above
−6.8 mV, below zero even with the comparator's full offset.

Two more numbers on that block were artifacts. With the ~100 ns
comparator-and-driver delay in, the default timestep let ngspice commit
the hysteretic switch on a rejected trial step: the "−0.068 V" minimum was
really **−0.177 V** — still inside the −0.3 V rating by 1.70×, which
answers the question this block had carried since 20 September. And the
pinned 4.74 A clamp-diode peak and a 15.8 mV "settling" difference on
pulse 3a were coarse-step overshoot, confirmed on the unchanged original
netlist: 4.114 A fine, equal to the flat top and to (206.5 − 0.4) / 50 Ω.

**Choosing the clamp comparator found two under-rated parts and a
drawn FET of the wrong polarity, 22 September 2026.** `NEG-CLAMP`
specified its FET at **40 V** and the backstop Schottky was **60 V** —
both with a terminal on `VBAT_PROT`, both sized for the negative pulses
they catch, neither checked against pulse 2a driving the *same* node to
**+73.3 V**. `transient_clamp.cir` carried "every part on VBAT_PROT must
clear 73.3 V" as a principle, not a list; it is now a **table**, every
part on the rail with its rating and margin, and a part below the line
fails. Both are 100 V class now.

And the reverse-battery FET: the sheet drew an **N-FET** with an
undriven controller gate, while `reverse_battery.cir` has always
modelled a **P-FET**. The node swings +73.3 V to −47.8 V and no
controller IC checked spans it — LM74700-Q1 stops at +65 V, LM5050-1-Q1
at −0.3 V. A P-FET with a passive gate network *is* the block's switch
model and has no IC ratings to violate. It gives up ideal-diode hold-up
on a *shorted*-input dropout, which the spec does not require; that is
on the page.

**Current sense chosen, 22 September 2026: INA181A1-Q1 on all three
channels, 12 → 9 open ends.** One part and one gain — 20 — set for the
injector, so the 18 A peak reads 1.80 V and a fault to 32.8 A is still
measured rather than clipped. Supplied from 3V3_MCU, which makes its
output ADC-safe by construction and removes the need for a clamp. The
metering FET was also redrawn: it had been placed at `rot=270` since
20 September, which gives diagonal drain and source wires — the same
drawing bug the injector sheet had, fixed there first.

**Gate drivers chosen, 21 September 2026: AUIRS2181S on all eight
gates, and the open-end count fell from 20 to 12.** Its first listed
application is common-rail injection, and the deciding property is one a
parametric search would never filter for: it has **no cross-conduction
interlock**. In a half bridge that is the less safe choice; here the high
and low switches are in *series* with the coil and must both be on, so
UCC27282-Q1 and UCC27712-Q1 — which have interlock — could not fire an
injector at all. It also clears the two ratings the obvious 120 V part
(UCC27211A-Q1) fails: 4.1 V of headroom on its HB absolute maximum, and a
−1 V HS DC minimum that the freewheel diode violates on every hold
off-time. The kill path moves to `HIN`, the one ground-referenced point
in the high-side path.

The drivers needed a rail the board did not have — 10–20 V — and **it is
made from the boost rail** so it survives cranking. The LM5164 already on
the board was the obvious candidate and is ruled out by its own VIN
absolute maximum of 100 V against a ~102 V rail. A discrete follower with
a current limit carries the ~3 mA; if the boost stops, every driver drops
into UVLO and every gate turns off.

**Choosing the second part found an error in the first sheet it touched.**
The injector high side was drawn on 21 September with the battery
feeding the bank node through a plain **diode-OR**, on the argument that
it needed no extra MCU pin. Looking for a gate driver for it showed that
it is wrong three ways, and only the third is visible from a datasheet:

1. **It cannot regulate hold.** With the battery on a diode the only
   switch in the loop is the low side, and opening it sends the coil's
   current into the 100 V rail — a fast decay against −87 V, which is
   turn-off, not chopping.
2. **It leaves connector pins 03 and 05 permanently live**, so a harness
   short to ground draws current whenever the battery is connected.
3. **The gate driver cannot be bootstrapped.** A bootstrap capacitor
   charges when the switch node goes low; a battery diode holds it at
   12.8 V, so it never does.

The replacement is what `injector_turnoff.cir` already modelled and
spends a paragraph of its header justifying: **two high-side switches
per bank** onto a common node, plus `D_fw` from **ground**. Hold chopping
moves to the high side, the node swings to −0.7 V each off-time, and the
bootstrap charges. It costs two MCU pins — `PTB5` and `PTA17`, both FTM0
channels, so the whole injector stage stays on one timer and its edges
stay phase-locked. The pin map's "six gate pins" section is now eight.

**Phase 3 started 21 September 2026 — the first part is chosen.**
`TPS40210QDGQRQ1`, the injector boost controller, and it was chosen on
**one spec that runs backwards from the usual**: tOFF(min) = 200 ns max.
A boost needs 94.1% duty at the 6 V cranking corner; at 150 kHz that
off-time floor allows 97.0%, and at the 2.2 MHz most wide-input boost
controllers in this class use, the same 200 ns caps duty at 56% — below
even the 86.6% the rail needs at a *nominal* battery. Switching slower
is the requirement, and the part that looks less modern is the one that
works.

**And it hit the 73.3 V rail rating for the third time.** VDD absolute
maximum is 52 V. Same shape as DRV8873-Q1's 40 V `VM`, which took that
part off the EGR bridge — solvable here only because this pin draws
2.5 mA plus gate charge rather than a motor's current, so 47 Ω and a
43 V zener hold it inside the rating. 43 V rather than 39 V so the clamp
stays *out* of conduction during the 400 ms load dump and only works
during the 50 µs pulse. All of it is checked as executable arithmetic
under `boost_converter`, not as prose.

The converter stage is drawn — `injector` moved to A1 to hold it — and
the loop compensation is the one thing on it marked as a starting point
rather than a result, because a current-mode boost's loop depends on the
inductor's real DCR and the capacitor's real ESR and is a bench
measurement.

**Footprints are the phase-3 input, not a phase-2 gate:** 7 of 201
components carry one, and they are exactly the parts with a retrieved
datasheet behind them.

---

## 8. Work at the machine

Ordered by what it unblocks.

**Re-ordered 21 September 2026, after the schematics were drawn.** Two
items moved to the top that were not on this list before, because they
came out of capture rather than out of a document. The full tasks are
`docs/research/08-engine-inspection-brief.md` **Group 5**, written for
whoever is at the machine.

| Task | Closes | Unblocks |
|---|---|---|
| **Continuity from every populated cavity to chassis — where is the power ground?** | — | **The board, outright.** 94 pins and no identified battery negative; the injector low sides put 18 A into a net with nowhere to land |
| Cavity census: populated, contact-only, empty | — | A pin **and a wire** for `TRIP_LOOP`, which is not on the OEM diagram at all |
| Trace who switches the heater feed | **U14** | Whether a heater output is in scope — **can make the board bigger** |
| Follow the throttle's 6-pin cable to where it ends | **U8** | Whether a throttle driver exists at all — **can make the board bigger** |
| Injector part number from the body | **U5** | The boost rail's 100 V target and the 18 A threshold, both currently a family envelope |
| Alternator rectifier part number, or a scope during a live disconnect under load | **U16** | The whole input-protection topology, and `load_dump`'s failure |
| Resistance across the charge-air element, cold | **U2** | The `ntc_frontend` populate choice |
| Crank VR output while cranking, cold *(supervised)* | — | Confirms the ±198 mV hysteresis window against the real sensor, not a 2 V estimate |
| Contact pitch and row spacing, with calipers | — | Confirms which Bosch family drawing is the right one for the board-side footprint |
| Relay contact-type check | U12 confirmation | Nothing — recorded for completeness |

**The two that can grow the board — U14 and U8 — should be answered
before layout starts, not after.** Everything else on this list changes a
value or closes a register entry; those two change the output count.

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
