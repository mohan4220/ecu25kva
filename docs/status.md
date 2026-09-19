# Build Status — What Is Done and What Is Not

**As of 19 September 2026.** Counts in this document are generated from the repository,
not maintained by hand: the block results come from `sim/run_sim.py`, the unknowns from
the specification's own register.

---

## At a glance

| | Count |
|---|---|
| Circuit blocks simulated | **20** |
| Blocks passing their checks | **19** |
| Blocks failing deliberately | **1** (`load_dump`) |
| Research memos | **12** |
| Unknowns closed | **4** |
| Unknowns partly answered | **4** |
| Unknowns still open | **8** |
| Phase | **1.5** — block simulation, nearly complete |

**Nothing has been captured in KiCad, no PCB exists, and no firmware has been written.**
Everything below describes design work verified by simulation, which is the stage before
schematic capture.

---

## 1. Circuit blocks — simulated and passing

Each block is a SPICE netlist plus a set of falsifiable checks. A block "passes" when
every claim it makes about itself holds. These are design verification, not layout.

### 1.1 Power chain — 8 blocks

| Block | What it covers | Status |
|---|---|---|
| `emi_filter` | Two-stage LC, CISPR 25 conducted, differential mode | Passing |
| `reverse_battery` | Ideal-diode P-FET vs series Schottky | Passing |
| `transient_clamp` | ISO 7637-2 pulse 2a, +112 V / 2 Ω / 50 µs | Passing |
| `load_dump` | ISO 7637-2 pulse 5b, 40 V / 0.5 Ω / 400 ms | **FAILS — deliberately** |
| `buck_preregulator` | 6–40 V to 5 V at 400 kHz | Passing |
| `sensor_rail` | 5 V sensor distribution, one PTC per group | Passing |
| `mcu_pdn` | 3V3 decoupling impedance, 100 mΩ target | Passing |
| `supervisor` | Watchdog, brownout, fail-safe gate kill path | Passing |

**Why `load_dump` fails, and why that is correct.** The TVS chosen against pulse 2a
absorbs 46 J at 116 W under pulse 5b — roughly 100× both its single-pulse energy rating
and its continuous dissipation rating. The failure is the deliverable: it says the part
selection is wrong, not that the simulation is. The fix is a higher standoff voltage so
the TVS stays off during a normal clamped load dump, rather than a larger part to absorb
it. **Blocked on U16** — whether the alternator is suppressed at all decides which pulse
applies.

### 1.2 Sensor front-ends — 5 blocks

| Block | What it covers | Status |
|---|---|---|
| `sensor_ratiometric` | Pins 41/35/80/37, 0.5–4.5 V into a 3.3 V ADC | Passing |
| `sensor_differential` | Shared sensor ground on pin 34, single-ended vs differential | Passing |
| `ntc_frontend` | Pin 79 charge-air temperature, divider vs current source | Passing |
| `battery_sense` | Pins 04/06, 6–40 V rail into a 3.3 V ADC | Passing |
| `discrete_input` | Pins 20/24/71, active-high switched battery | Passing |

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
| `injector_boost` | Why the boost stage exists, pins 03/05 | Passing |
| `injector_turnoff` | Turn-off recirculation into the boost rail | Passing |
| `boost_converter` | Injector rail reservoir sizing | Passing |

`boost_converter` passes but carries a recorded gap: it has **no bleed path**. Its charge
source regulates the rail from below only. Harmless while current flowed outward;
`injector_turnoff` now pushes energy back in, and a hold-current cutoff would climb the
rail about 2 V per event with no way down.

### 1.5 Actuators — 2 blocks

| Block | What it covers | Status |
|---|---|---|
| `metering_unit_pwm` | Pin 88, low-side PWM into the fuel metering solenoid | Passing |
| `relay_driver` | Pins 50/69, low-side FET with flyback | Passing |

### 1.6 Communications — 1 block

| Block | What it covers | Status |
|---|---|---|
| `can_termination` | Split vs single termination, J1939 250 kbit/s | Passing |

---

## 2. Circuits not yet built at all

These have no netlist, no schematic and no checks. They are the real gaps.

| Missing circuit | Pins | Why it is not built |
|---|---|---|
| **EGR actuator H-bridge** | 59 / 81 drive, 37 position feedback | Not started. In scope, specified in §4, simply not reached |
| **Trip-module sense input** | new — not in the OEM harness | Created by U12 closing badly. The ECU should sense whether the trip module has cut fuel and report it, rather than reading the result as a fuelling anomaly |
| **Intake throttle driver** | 6-pin connector | **Blocked on U8.** Reported battery-fed, which answers who supplies it, not who commands it. May be out of scope entirely |
| **Pre/post-heat output** | unknown | **Blocked on U14.** Same distinction — battery-fed is not the same as ECU-switched. The DSE4522 enables both at 50 °C and this design has no heater output |

---

## 3. Verification not yet done

The blocks above are each simulated in isolation, at one temperature, against the
stimuli named. These are the gaps in the *verification*, not in the circuits.

| Gap | Consequence |
|---|---|
| **No temperature corner anywhere** | Every result is a 27 °C result. An engine bay is not 27 °C |
| **ISO 7637-2 negative pulses unsimulated** | And the TVS model is a single diode, so reusing it for reverse-polarity transients would give a confidently wrong answer rather than failing visibly. The model must be replaced before the test is meaningful |
| **Common-mode EMI unmodelled** | `emi_filter` covers differential mode only. Most real automotive failures are common mode, and modelling it honestly needs a layout to give the return path |
| **Reverse-battery transient** | The switch model turns off instantly, so it always looks perfect. The real number is a controller-datasheet question |
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
| **1.5** | **Block-level simulation** | **In progress — 20 blocks, 19 passing** |
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
