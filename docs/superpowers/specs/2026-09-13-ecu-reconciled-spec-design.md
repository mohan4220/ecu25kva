# Genset ECU — Reconciled Specification

**Date:** 2026-09-13
**Status:** Phase 0 — supersedes all four prior artifacts
**Target:** Functional replacement for the `ENGINE CONTROL UNIT` block of Kirloskar
wiring diagram `08-GP3-60-001`, on a 25 kVA diesel genset with a 12 V / 75 Ah battery.

---

## 1. Why this document exists

Four artifacts precede this one:

| Artifact | Rev | Role |
|---|---|---|
| Genset ECU Design Brief | J | Spec |
| ECU Circuit Guide | H | Per-block why/how/prove |
| ECU Circuit Schematics | H | 15 topology sheets |
| PCB Design Roadmap | A | Brief → fab sequence |

They were written by reverse-engineering the Kirloskar wiring diagram from memory
of it, not from the document itself. Now that `GP3.8703.C4.pdf` is in hand, roughly
a third of their content is wrong — not stylistically, but in ways that change the
BOM, the driver topology and the pin count.

**This document is the single source of truth from here.** Where it contradicts an
artifact, this document wins. The artifacts remain useful for the reasoning behind
blocks that survived unchanged, and the Circuit Guide's "prove it" bench procedures
remain valid for those blocks.

Raw extracted evidence: [`refs/ecu-pinout-extracted.md`](../../../refs/ecu-pinout-extracted.md).

---

## 2. What changed, and why it matters

### 2.1 Injector drive is bank-shared

The diagram traces injector high-side pin `03` to **both** cylinder 1 and cylinder 3,
joined at splice V5. Pin `05` serves cylinder 2 alone. Low-side selects are individual:
`73` (cyl 1), `07` (cyl 3), `29` (cyl 2).

Five pins, two banks. The artifacts specify an independent high/low pair per cylinder —
six pins, three banks — which would put three boost stages on a board that needs two.

This is the conventional arrangement: the boost converter and high-side switch are the
expensive, thermally-significant parts, so they are shared across cylinders that never
fire simultaneously. Cylinder selection happens on the low side, which is cheap.

**Consequence:** two high-side bank switches, one shared boost rail, three low-side
current-controlled selects.

### 2.2 Fuel metering unit is low-side PWM, not an H-bridge

Metering unit pin 2 sits on fused battery (20 A, `8F1`). Pin 1 goes to ECU pin `88`
on a black wire — the low-side class per the page-2 legend. The ECU sinks current;
it does not source it, and it never reverses polarity.

The Design Brief specifies a TLE9201SG H-bridge with one leg tied off. That works
electrically but buys a reversing bridge for a solenoid that only pulls one way.

**Consequence:** one high-current low-side driver with current sense, closed-loop in
firmware. One fewer part family to source.

### 2.3 Fuel level and water-in-fuel are not ECU signals

Both route through the XC11/XC1 36-pin harness to the panel — fuel level to XC pin 22
(wire `1C2`), water-in-fuel to XC pin 16/1 (wire `4B`). Neither reaches an ECU pin
anywhere in the diagram. They belong to the GCU.

**Consequence:** two analog front-ends and two connector positions removed.

### 2.4 Discrete inputs are active-high, not active-low

`AUDIO ABORT` (20), `OVERSIDE SWITCH` (24) and `IGNITION` (71) are all **red** wires —
switched battery. The switch connects the pin *to battery*, not to ground.

The artifacts specify pull-up to 5 V with the switch closing to ground. That is the
opposite sense, and the front-end is wrong for it: these pins see battery voltage,
not 5 V, so they need a divider rated for the full 6–40 V input range plus a clamp.

The fail-safe reasoning also inverts. Circuit Guide Group D argues that normally-closed
wiring makes an open harness read as a fault. With switched-battery inputs an open wire
reads "not asserted" — indistinguishable from a switch that simply isn't pressed. That
argument does not hold here and should not be repeated in the new design. Detecting an
open wire on these inputs requires either a pull-down and a diagnostic current source,
or accepting that it is not detectable. **We accept it is not detectable** and note it
in the FMEA, because changing the sense would break harness compatibility.

Pins `01` (`G_G_B AT1`) and `02` (`G_G_B AT2`) are ECU-provided return/ground legs for
the switch circuits. The coolant switch (`43`) and droop switch (`23`) are cyan —
digital-input class — and are conventional switch-to-return inputs.

### 2.5 Both CAN channels are real

Pins `55`/`77` and `87`/`86` are both drawn as twisted pairs with bidirectional markers.
The artifacts treat CAN1 as a spare, DNP on the harness. In the OEM system both are wired.

**Consequence:** populate both transceivers and both connector positions.

### 2.6 Scope reductions confirmed

None of the following exist anywhere in this system: magnetic pickup unit, DEF/urea
sensor, LIN bus, SCR, separate overspeed switch, barometric sensor in the harness.
There is **one** catalyst temperature sensor connector (2-pin), not three EGT channels.

`OVERSIDE SWITCH` (pin 24) and `Override SS SW -S7` are one component. The Design Brief
lists them as two.

---

## 3. Safety position

**Engine speed reaches the GCU over CAN only.** There is no independent overspeed path
in this architecture.

The Circuit Guide argued — correctly, as a matter of engineering — that overspeed
protection should not depend on the same MCU and the same bus that could be the thing
that failed. The OEM system does not honour that. We are replacing the OEM ECU, so we
inherit its interface, and adding an MPU requires a GCU input we have not confirmed exists.

The position for this design:

1. The ECU implements overspeed shutdown in firmware as a **primary** function, with the
   crank sensor as its input, at the highest scheduling priority.
2. An independent hardware overspeed trip is treated as a **required addition**, not an
   optional one, and is tracked in the unknowns register (§8) pending the KG640C manual.
   If the KG640C has an MPU input, we wire one. If it does not, a standalone trip module
   is added to the panel.
3. **No build of this ECU takes injection authority over a running engine until item 2
   is closed.** This is a gate, not a preference.

A 25 kVA set in runaway is a mechanical hazard to anyone near it. The failure mode that
matters is the controller hanging with the fuel valve open, and a controller cannot be
its own protection against that.

---

## 4. ECU pin map

Confirmed pins from the wiring diagram. **44 of 94.** See §8 for the remaining 50.

### Power

| Pin | Signal | Front-end |
|---|---|---|
| 21 | Battery + feed | Main input: EMI filter → fuse → TVS → reverse-battery FET |
| 04 | `V_V_BAT_1R` (10 A fused) | Divider + ADC sense; feeds high-current loads `[?]` |
| 06 | `V_V_BAT_2R` (10 A fused) | Divider + ADC sense; feeds high-current loads `[?]` |
| 09 | `SYNCHRONIZATION GROUND` | Function unresolved — see §8 |

### Ratiometric analog — 1 kΩ series, 100 nF shunt, clamp, ADC ref tracks `5V_SENSOR`

| Pin | Signal | Group ground |
|---|---|---|
| 11 / 41 | Boost: 5 V excitation / pressure signal | 34 |
| 79 | Boost: temperature signal — **topology unresolved, see §8** | 34 |
| 34 | Sensor ground — boost + coolant | — |
| 33 | Coolant temperature (NTC, pull-up divider) | 34 (spliced) |
| 15 / 37 | EGR position: 5 V / wiper | 36 |
| 36 | Sensor ground — EGR + oil pressure | — |
| 39 / 80 | Oil pressure: 5 V / signal | 36 (spliced) |
| 32 / 35 | Rail pressure: 5 V / signal | 08 |
| 08 | Sensor ground — rail pressure, dedicated | — |

Sensor-ground grouping mirrors the OEM harness exactly: `34` boost+coolant,
`36` EGR+oil, `08` rail alone, `30` crank alone, `44` cam alone. Rail pressure gets
a dedicated return because it is the most accuracy-critical analog channel on the engine.

### Speed

| Pin | Signal | Front-end |
|---|---|---|
| 52 / 74 | Crank VR: Frequency I/P High / Low | Differential adaptive-threshold conditioner → timer capture |
| 30 | Crank sensor ground | Shield terminates here, ECU end only |
| 45 / 46 | Cam Hall: 5 V / Frequency I/P | Pull-up to `5V_SENSOR` → timer capture |
| 44 | Cam sensor ground | — |

### Discrete inputs

| Pin | Signal | Sense | Front-end |
|---|---|---|---|
| 43 | Coolant switch | Switch-to-return | Pull-up + RC debounce |
| 23 | Droop switch | Switch-to-return | Pull-up + RC debounce |
| 01 / 02 | `G_G_B AT1` / `AT2` | — | Switch return legs |
| 20 | Audio abort | **Active-high** | Battery-rated divider + clamp + RC |
| 24 | Override SS | **Active-high** | Battery-rated divider + clamp + RC |
| 71 | Ignition | **Active-high** | Battery-rated divider + clamp + RC |

### Outputs

| Pin | Signal | Driver |
|---|---|---|
| 03 | Injector high side — bank A (cyl 1 + 3) | Boosted high-side switch |
| 05 | Injector high side — bank B (cyl 2) | Boosted high-side switch |
| 73 / 07 / 29 | Injector low side — cyl 1 / 3 / 2 | Current-controlled low-side, peak-and-hold |
| 88 | Fuel metering unit PWM | High-current low-side + current sense |
| 59 / 81 | EGR High / EGR Low | H-bridge + position feedback on pin 37 |
| 50 | Main relay | Low-side FET + flyback |
| 69 | Buzzer relay | Low-side FET + flyback |

### CAN

| Pin | Signal |
|---|---|
| 55 / 77 | CAN channel 1 — H / L |
| 87 / 86 | CAN channel 2 — H / L |

---

## 5. MCU selection

**Recommendation: NXP S32K148.** This resolves the contradiction in the artifacts —
Design Brief §03 specifies MPC5744P while its own §02 block diagram and §06 sensor table
still say S32K148 and FTM.

The argument for MPC5744P was angle-synchronous injection timing needing the eTPU2.

> **Corrected 2026-09-13** after research memo 05 challenged the original reasoning and
> was right to. This section first argued that constant 1500 rpm operation relaxes the
> timing problem because a crank degree is 111 µs and a 60-tooth wheel gives an edge
> every 667 µs. That checks the wrong variable. Crank-edge *capture* rate was never the
> binding constraint in either case — at 6000 rpm a 60-tooth wheel still only produces
> an edge every 28 µs, which is over 2000 CPU cycles at 80 MHz against an NVIC latency
> of roughly 12. The comparison was never close, so constant speed cannot be what makes
> it comfortable. The reasoning below replaces it.

**What the eTPU2 actually buys.** It is a co-processor that autonomously schedules and
re-schedules many angle-domain output-compare events across a wide and *rapidly changing*
speed range, without consuming the main CPU's interrupt budget and without the core's
scheduling jitter — cache effects, higher-priority ISRs, RTOS latency — reaching the
injection timing chain. That matters when rpm sweeps 800–6000 with tight transient
response and pilot/main/post multi-pulse strategies all landing within microseconds of a
moving target angle.

**Why we don't need it.** This set governs to a fixed 1500 rpm, and the pin map in §4
shows a single main injection pulse per cylinder per cycle — one bank high-side plus one
low-side select, with no multi-pulse rate shaping in scope. The constraint that does bind
is **injector pulse-width resolution**, which sets fuel-quantity metering accuracy and is
independent of crank speed. FlexTimer output-compare runs off the bus clock: one tick is
12.5 ns at 80 MHz, 8.9 ns at 112 MHz HSRUN. Against a single-pulse metering requirement
on the order of 1–4 µs, that is roughly 100–450× headroom.

The S32K148 also carries 2× Programmable Delay Blocks, which trigger ADC conversions or
timer events at a defined delay from a capture event in hardware. That recovers part of
what the eTPU2 offers — jitter isolation on the timing chain — without the eTPU2.

**Caveat carried forward:** the 1–4 µs resolution figure is a general diesel-injector
engineering figure, not this injector's datasheet. Revisit if U5 closes with a part
demanding materially finer control, or if multi-pulse injection ever enters scope.

What the S32K148 buys in exchange:

- Free S32 Design Studio; GCC ARM toolchain; cheap CMSIS-DAP/J-Link probes instead of
  a Power Architecture Nexus pod
- Stock KiCad symbol availability, or trivially built from NXP's own EVB files
- Real availability in small quantities in India
- 3× FlexCAN (we need 2); dual 12-bit ADC against a demand of ~14 channels — 8 sensor
  inputs, 2 battery-rail senses, and 4 current-sense returns from the injector, metering
  and EGR drivers; FlexTimer instances well beyond the ~10 timing channels required
  (crank capture, cam capture, 3 injector low-side, 2 injector high-side, metering PWM,
  2 EGR bridge PWM)
- No eTPU2 microcode, which is a specialist skill and a hiring risk on a small team

**Confirmed in Phase 1** — see [`docs/research/05-mcu-selection.md`](../../research/05-mcu-selection.md).
Orderable part **FS32K148HAT0MLQT**, 144-pin LQFP, 80 MHz RUN / 112 MHz HSRUN grade,
−40…+125 °C. In stock at DigiKey India at roughly ₹1,900–2,000/unit. The S32K146
fallback was checked and is in worse supply shape (backordered, 12–52 week spread), so
it is not needed.

Two items deferred to Phase 2: confirming how many ADC channels the 144-pin package
actually breaks out (needs the reference manual's pin-mux table, not the datasheet), and
pad-by-pad verification of the SOT486-2 package drawing before the footprint is locked.

---

## 6. Power architecture

Unchanged from the artifacts in topology; the reasoning there is sound.

| Stage | Function |
|---|---|
| EMI input filter | Common-mode choke, CISPR 25 conducted margin |
| Reverse-battery | Ideal-diode controller + P-FET, < 0.3 V drop |
| Transient clamp | Bidirectional TVS, ISO 7637-2 pulses incl. load dump 5b |
| Buck pre-regulator | 6–40 V → 5 V, wide-input synchronous |
| `5V_SENSOR` | PTC-protected per sensor group, isolated from MCU rails |
| `3V3_MCU` | LDO off 5 V |
| Supervisor | Windowed watchdog + brown-out reset |

Input range 6–40 V: 6 V covers the cranking dip on a 12 V system, 40 V bounds the
clamped load-dump transient.

**Injector boost rail** is new relative to the power chain as drawn: a separate boost
stage generating the injector opening voltage, with its own reservoir bank sized for
the pulsed draw of two banks. Target voltage is set by the injector part — see §8.

---

## 7. Deliberate deviations from the OEM design

Recorded so they are choices, not drift:

1. **Connector split.** The OEM uses one 94-pin connector. We use functionally-split
   sealed connectors. This simplifies harness build and field diagnosis, at the cost
   of needing an adapter harness to mate with an unmodified Kirloskar loom. That
   adapter is a deliverable, not an afterthought.
2. **Onboard barometric sensor.** Not present in the OEM harness. Added on-PCB behind
   a vented port; costs nothing in harness terms and improves fuelling correction.
3. **Independent overspeed path.** Added, per §3. The OEM does not have one.

---

## 8. Unknowns register

Nothing in this list may be guessed into copper. Each needs an answer before the
sheet that depends on it is drawn.

| # | Unknown | Blocks | How to close |
|---|---|---|---|
| U1 | Remaining 50 of 94 ECU pins | Connector selection, adapter harness | ECU connector part number — photograph the housing on the engine |
| U2 | Boost air-temp (pin 79): NTC or ratiometric? | Sheet 3b front-end | Sensor part number. **Mitigation: lay out a DNP pull-up so either works** |
| U3 | KG640C MPU input — does it exist? | §3 safety gate | KG640C manual |
| U4 | KG640C J1939 PGN set and expectations | Firmware, CAN sheet | KG640C manual; or log the live bus with the OEM ECU fitted |
| U5 | Injector part number and drive profile | Injector driver sheet, boost rail voltage | Read the injector body; Bosch/Denso datasheet or supplier |
| U6 | Pin 09 `SYNCHRONIZATION GROUND` function | Power/ground plan | OEM pin list; drawn red despite the name |
| U7 | Pins 04/06 — sense only, or load feeds? | Power sheet current rating | Measure on the live engine, or OEM pin list |
| U8 | 6-pin intake throttle — on the ECU at all? | Whether a throttle driver is in scope | Trace on the engine; not in this diagram |
| U9 | Catalyst temp sensor — connected where? | Whether an EGT front-end is in scope | Trace on the engine |
| U10 | `SENT` in the colour legend — which signal? | Possible digital sensor front-end | Inspect harness; SENT is SAE J2716 |
| U11 | Engine identity — "GK550" vs Kirloskar range | Emissions tier, sensor sourcing | Engine rating plate photograph |

**U1, U3 and U5 are the three that matter most.** U1 decides whether the board mates,
U3 is the safety gate, U5 decides whether injection can be commissioned at all.

---

## 9. Out of scope

- Injection calibration: timing maps, quantity maps, rail pressure setpoint schedules.
  The hardware will be capable; the maps are a dyno programme, not a PCB deliverable.
- Emissions certification.
- The GCU. We talk to the KG640C; we do not replace it.
- Panel wiring, ATS, alternator metering.

---

## 10. Phase sequence

| Phase | Output |
|---|---|
| 0 | This document |
| 1 | Research memos: engine ID, KG640C, MCU confirmation, injector and connector sourcing |
| 2 | KiCad hierarchical schematic capture |
| 3 | 4-layer PCB layout, DRC, fab outputs |
| 4 | Firmware skeleton: HAL, J1939, crank sequencing, fault manager |

Phase 2 cannot start on the sheets blocked by U1, U2, U5 and U8. It can start on power,
CAN, MCU support, speed inputs and the relay outputs, which are fully specified above.
