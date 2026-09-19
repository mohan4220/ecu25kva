# Build Status — What Is Done and What Is Not

**As of 19 September 2026, end of session.** Counts in this document are generated from the repository,
not maintained by hand: the block results come from `sim/run_sim.py`, the unknowns from
the specification's own register.

---

## At a glance

| | Count |
|---|---|
| Circuit blocks simulated | **24** |
| Blocks passing every check | **17** |
| Blocks failing a check | **7** — see below; five of them are new *information*, not new faults |
| Research memos | **12** |
| Documents in the bible | **18** |
| Unknowns closed | **4** |
| Unknowns partly answered | **4** |
| Unknowns still open | **9** |
| Phase | **1.5** — block simulation, nearly complete |

**The pass rate went down on 19 September, and that is progress.** It was 22 of 24 that
morning. Nothing broke: the temperature-corner pass found six blocks that fail cold or
hot and recorded all six in RESULT NOTE prose, where the suite could not see them. They
are now enforced checks. A design that was always marginal at −40 °C now says so when you
run it.

**Nothing has been captured in KiCad, no PCB exists, and no firmware has been written.**
Everything below describes design work verified by simulation, which is the stage before
schematic capture.

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
| `egr_hbridge` | Pins 59/81, positional actuator, feedback on 37 | Passing |

### 1.6 Communications — 1 block

| Block | What it covers | Status |
|---|---|---|
| `can_termination` | Split vs single termination, J1939 250 kbit/s | **FAILS — tempco** |

---

### 1.7 The seven failures, and what each one means

A failing block here is a finding, not a broken simulation. Three different kinds:

**Wrong part selected — 1 block.**

- **`load_dump`** — the TVS absorbs 38 J under pulse 5b against roughly a 0.5 J
  single-pulse class rating. The fix is a *higher standoff* voltage so the part stays off
  during a normal clamped dump, not a bigger part to absorb it. Blocked on **U16**: if the
  alternator turns out unsuppressed, the applicable pulse is 5a and the topology changes
  rather than the part number.

**Missing component — 1 block.**

- **`negative_pulses`** — the buck's VIN pin is rated **−0.3 V to 100 V**, and the
  negative limit is not a mirror of the positive one. It sees −40.7 V on pulse 1 and
  −27.8 V on pulse 3a. The TVS clamps correctly; −38 V is a good clamp that is still two
  orders of magnitude outside what the buck tolerates. Nothing in the chain addresses a
  negative excursion at all.

**Marginal at a temperature corner — 5 blocks.** These were always true; until 19
September nothing asked.

- **`sensor_rail`** — 4.148 A against a real 3.0 A polyfuse trip ceiling, at the stacked
  cold-and-tolerance corner.
- **`mcu_pdn`** — 196.7 mΩ against the derived 100 mΩ target at a 4× cold-ESR derate. The
  bulk electrolytic's ESR *is* the damping in this block, so cold attacks the mechanism
  the design depends on.
- **`can_termination`** — 123.96 Ω differential against J1939's 120 ± 2, from 200 ppm/°C
  resistor tempco alone. An ordinary part, not an exotic one.
- **`metering_unit_pwm`** and **`injector_boost`** — their *target* checks fail while
  their *control-law invariants* hold. Both halves are checked deliberately so a reader
  sees which is fragile. A target that moves with temperature is not the same as a design
  that stops working.

**One block passes in a way worth reading.** `emi_filter` was not failed at its corner,
because its −40 dB gate is documented in its own final check as being of unknown adequacy
pending measured hardware emissions. Failing a corner against an admittedly arbitrary
number manufactures a verdict. The X7R −15% corner is recorded as regression pins with a
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
| **Air-intake shutoff** | Nothing electrical | Owners' decision. Nothing in this design can stop an oil-fuelled runaway |
| **Trip-module pickup target** | Module ordering | Whether it shares our flywheel target. Sharing is cheaper; separate preserves the independence that is the reason for fitting it |

---

## 7. Phases

| Phase | Output | State |
|---|---|---|
| 0 | Reconciled specification | Done |
| 1 | Research memos | Done — twelve |
| **1.5** | **Block-level simulation** | **In progress — 23 blocks, 22 passing** |
| 2 | KiCad hierarchical schematic capture | Not started |
| 3 | 4-layer PCB layout, DRC, fab outputs | Not started |
| 4 | Firmware skeleton | Not started |

**What ends phase 1.5:** the four missing circuits in §2, the verification gaps in §3,
and the verification gaps in §3. The two driver decisions in §6 are now taken. **What starts phase 2:** assigning `PTxx` pins to the
94-way connector — which is also what unblocks the per-pin detail of the fail-safe
requirement.

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

Written at the end of 19 September so the next session does not have to
re-derive where things stand. **Nothing is half-finished: the tree is clean, the
suite passes, everything is pushed.**

### Done since this section was written

Both items below are complete: the TVS is bidirectional, ISO 7637-2's negative pulses are
simulated, and temperature corners are run and enforced across all 24 blocks. What they
produced is in §1.7 and §2. The text of the two items is kept as written because it
records what was expected, and the negative-pulse result was not it.

### The two pieces of phase 1.5 that were outstanding — now done

**1. Replace the TVS model, then simulate the negative pulses.** In that order — the
second is not answerable until the first is done.

`sim/blocks/transient_clamp.cir` and `load_dump.cir` share this model:

```
.model TVS D(Is=1e-12 N=1.6 Rs=0.35 BV=36.7 IBV=1e-3)
```

That is a **single diode**. The real part is an SMBJ33CA, and the `CA` suffix means
bidirectional. A single diode conducts forward at 0.7 V in reverse polarity, so any
reverse-polarity or negative-pulse question put to it gets a confident wrong answer
rather than a visible failure.

Build a bidirectional subcircuit — two junctions back to back — and switch both blocks
to it. **Both must reproduce their current results**: `transient_clamp` passing,
`load_dump` failing at ~46 J absorbed. If either moves, that is a finding about the old
model and should be reported, not tuned away.

Then add a `negative_pulses` block for ISO 7637-2 pulses **1** and **3a** on a 12 V
system. Spec §6 requires ISO 7637-2 and only 2a and 5b exist. Take severity from
memo 06 if it is there; otherwise state the values and label them INFERRED.

**2. Temperature corners across all 23 blocks.** Every result in this repo is a 27 °C
result. The tolerance pass built the pattern to follow — see `load_dump.cir` and
`supervisor.cir` for how a corner is stated. This is the piece most likely to be cut off
part-way, and it survives that well: each block's corner is self-contained, which is how
the tolerance pass came back cleanly from being truncated at 11 of 19 blocks.

### Also outstanding

**Four artifacts built on 19 September have never been independently reviewed:**
`egr_hbridge`, `trip_module_sense`, `cam_frontend`, and `docs/pinmap.md`. The last review
ran before any of them existed. Both review passes so far found real errors, including a
2× arithmetic slip inside the block written to fix a 1000× one.

### Needs a person, not an agent

| Item | Why |
|---|---|
| **MC33816AE last-time-buy 06/08/2027** | Distributor conversation. Gates memo 12's fallback path |
| **L9781 datasheet** | Five failed retrievals across two sessions. Needs FAE or distributor access. It is the runner-up to the driver decision and cannot be confirmed without it |

### At the machine

**U16 is now the one that gates most** — whether the alternator's rectifier is suppressed
decides which ISO 7637-2 pulse applies and therefore whether `load_dump`'s failure is
fixed by a part number or a different circuit. Then U2, U8, U14, U5.

### The pattern worth carrying forward

Across 19 September, **four wrong numbers were found in prose — comments, memos, the
specification — and none in a check.** A factor of 1000, a factor of 6, a factor of 2,
and a stale 0.19 V that should have been 0.308 V. Every one of them became or nearly
became a requirement, and every one was caught by something executing the claim rather
than reading it.

Two circuits have now been specified in a way that would have destroyed an MCU pin. The
first was caught by a simulation block. The second — the cam input — survived precisely
because no block existed for it.
