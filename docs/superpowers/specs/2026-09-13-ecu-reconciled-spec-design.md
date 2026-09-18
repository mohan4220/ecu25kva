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

> **Revised 18 Sep 2026 — second revision, and it moves in the pessimistic direction.**
> The genset controller has been photographed and identified. It is a **Deep Sea
> Electronics DSE4522 MKII AMF (India SP)**, part `4522-001-01`, serial 11021794 —
> **not the KG640C** that the OEM wiring diagram shows and that research memo 02
> analysed. This section was built on memo 02. Its central claim is now known to be
> false for the device actually fitted, and the relaxation that claim bought is
> withdrawn.

### What changed

The previous revision rested on this: *the controller senses speed from alternator
frequency, not from CAN, so its overspeed trip cannot be defeated by a hung ECU.*

That is true of the KG640C. **It is not true of the DSE4522.** From DSE's own operator
manual for the DSE4510/4520 MKII (document `057-260`, the 4522's siblings):

> "If the unit has been configured for CAN, compatible ECU's receive the start command
> via CAN and **transmit the engine speed to the DSE controller**."

and, in the engine-at-rest detection logic:

> "Engine speed is zero **as detected by the CAN ECU**"

**Engine speed reaches this controller from our ECU, over CAN.** The configured
overspeed shutdown at 1710 rpm therefore reads a number we send. An ECU that hangs
while transmitting a stale, plausible speed defeats it completely — which is precisely
the failure mode this section exists to guard against.

### What is confirmed, and what replaces it

**No magnetic pickup — now confirmed rather than inferred.** The DSE4522's full
terminal list runs 1–35 and contains no speed-pickup input of any kind: 1–2 DC supply,
3–4 outputs A (FUEL) and B (START), 5 charge fail/excite, 6–9 outputs C–F, 10 sensor
common, 11–13 analogue sensors, 14–17 digital inputs, 18–20 CAN, 21–24 generator
voltage sensing, 25–28 mains, 29–35 CTs, charge alternator and comms. Read from the
manufacturer's own terminal table, not from a diagram's silence.

**An independent path does still exist — but it is a different mechanism, and a more
conditional one.** The module measures **generator frequency directly** at terminals
21–24, straight off the alternator's three phases. It does not use CAN to do this. The
configuration sets:

| Protection | Trip | Source | Equivalent speed (4 poles) |
|---|---|---|---|
| Generator **over-frequency** shutdown | **56.0 Hz** (112 %) | Alternator terminals 21–24 — **independent of CAN** | **1680 rpm** |
| Engine **over-speed** shutdown | 1710 rpm | **CAN, from our ECU** | 1710 rpm |

On a 4-pole alternator at no slip, speed and output frequency are rigidly linked. The
over-frequency trip fires at **1680 rpm, before** the CAN-dependent overspeed trip at
1710 rpm, and it cannot be defeated by anything our ECU does or fails to do.

**Its conditions, stated plainly.** It is a *generator* protection being relied on as an
*engine* protection, and it inherits that mechanism's dependencies: the alternator must
be excited and producing measurable output, and the AVR must be working. An excitation
failure removes the protection. That is a narrower guarantee than a magnetic pickup
watching the flywheel, and it should not be described as equivalent to one.

### Where the chain terminates — and why U12 is now the whole question

Every protective action this controller can take ends at the same place: it
de-energises **DC Output A, terminal 3, the FUEL relay** (rated 10 A for 10 s, 5 A
continuous — a relay coil driver, consistent with it operating the 70 A `-13RB1`
contactor in the OEM diagram).

So the independent over-frequency path is only as good as what that relay's contacts
carry. If they remove supply from the ECU and the fuel metering unit, the path works. If
they merely signal a hung ECU, **the path terminates in the failure it was meant to
catch**, and there is no independent protection at all.

That is U12, unchanged in substance and now the single load-bearing measurement in this
section.

### The position for this design

1. The ECU implements overspeed shutdown in firmware as a **primary** function, with the
   crank sensor as its input, at the highest scheduling priority. First line, and it is
   ours.
2. The controller's **generator over-frequency shutdown at 56 Hz**, measured directly
   from the alternator, is the **second line**. It is independent of this ECU but
   conditional on alternator excitation. We must not weaken it: the ECU must not latch
   the fuel metering unit on in a way that survives its supply being removed, and must
   fail safe when the ignition input at pin 71 drops.
3. A standalone MPU-driven overspeed trip module is **mandatory again**, not
   recommended. The relaxation in the previous revision was bought entirely by the claim
   that the controller had an independent *speed* path; that claim is false for the
   fitted device. What remains is a generator-frequency protection with an excitation
   dependency, terminating in a relay whose function is unverified. That is not enough
   to carry a 25 kVA set on its own. Two candidates are costed in memo 02
   (GAC SSW675, Murphy HD9063) — that costing survives even though the memo's device
   analysis does not.
4. **The gate: U12 must be closed by measurement before any build takes injection
   authority.** A clean U12 result strengthens line 2 but does not by itself restore the
   relaxation, because line 2's excitation dependency is separate from U12.

The owners may of course revisit item 3 with evidence. What they should not do is
inherit the previous revision's conclusion, because the fact it was built on turned out
to describe a controller that is not on this machine.

### What this section still does not address

A diesel that begins burning its own lubricating oil — through a failed turbocharger
seal or crankcase fumes drawn into the intake — has a fuel supply that **none of the
three lines above can interrupt**. Every one of them cuts diesel or electrical power.
The standard countermeasure is a mechanical or pneumatic **air-intake shutoff valve**,
and no such device appears anywhere in this design, this register, or §9's out-of-scope
list. It was never considered rather than considered and rejected.

This is recorded here, unresolved, because it is a decision for the machine's owners:
the part is mechanical, not electronic, and fitting it is not within this PCB's scope.
It should not be allowed to stay invisible.

---

## 4. ECU pin map

Confirmed pins from the wiring diagram. **44 of 94.** See §8 for the remaining 50.

### Power

| Pin | Signal | Front-end |
|---|---|---|
| 21 | Battery + feed | Main input: EMI filter → fuse → TVS → reverse-battery FET |
| 04 | `V_V_BAT_1R` (10 A fused) | **120 k / 10 k** divider → ADC; feeds high-current loads `[?]` |
| 06 | `V_V_BAT_2R` (10 A fused) | **120 k / 10 k** divider → ADC; feeds high-current loads `[?]` |
| 09 | `SYNCHRONIZATION GROUND` | Function unresolved — see §8 |

The battery-sense divider is **120 k / 10 k, not the 75 k / 10 k** inherited from
the earlier artifacts. That value was sized for a 5 V ADC and delivers 4.69 V at
a 40 V input — above the S32K148's 3.3 V analog supply. The corrected divider
peaks at 3.07 V and still resolves 573 ADC counts at the 6 V cranking dip.
Verified in [`sim/blocks/battery_sense.cir`](../../../sim/blocks/battery_sense.cir).

### Ratiometric analog — 10 k / 16 k divider, 22 nF shunt, 3.3 V clamp, rail measured and corrected in firmware

**Revised 14 Sep 2026.** This section previously specified *1 kΩ series, 100 nF
shunt, ADC ref tracks `5V_SENSOR`*, which contradicted the simulated front-end and
cannot be built on this MCU. Both halves were wrong, and for the same reason the
75 k / 10 k battery divider was wrong — they were written for a 5 V part:

- **`VREFH` cannot track `5V_SENSOR`.** The S32K148's ADC reference may not exceed
  its 3.3 V analog supply. A reference at 5 V is not an option on any 3.3 V device.
- **1 kΩ in series scales nothing.** With no division, a sensor at 4.5 V arrives at
  a 3.3 V pin. The series resistor is a fault-current limiter, not an attenuator.

So the signal must be divided, and the question becomes how to keep the
*ratiometric* property after dividing it.

**Decision: divide, then measure the rail and correct in firmware.**
`5V_SENSOR` gets its own ADC channel. Every ratiometric reading is computed as a
fraction of the measured rail rather than of an assumed 5.000 V, which is what the
sensor's output actually represents. Cost: one ADC channel, zero analog parts. The
channel budget has room — see the sensor reference.

*Rejected alternative:* dividing `5V_SENSOR` into `VREFH` by the same 16/26 ratio.
It fits numerically (5 V × 16/26 = 3.08 V, inside the 3.3 V limit) and gives true
ratiometric conversion with no firmware arithmetic. It is rejected because `VREFH`
is shared by every channel on that ADC, so it would silently make **battery sense
and the NTC channels ratiometric to the sensor rail as well** — both of which need
an absolute reference. It would also need a buffer, since a resistive divider is
too noisy and too high-impedance to drive a reference input.

**Single-ended or differential is decided by the ground, not by the channel.**
Where the sensor's return is shared, the other sensor's current develops an offset
across the harness resistance that a single-ended input reads as signal:
[`sim/blocks/sensor_differential.cir`](../../../sim/blocks/sensor_differential.cir)
measures 12 mV of bias at 1 Ω of return resistance against 0.13 mV differential.
Research memo 09 found both Deep Sea Electronics and SEDEMAC treat this as a
first-class problem. So:

- **Shared ground (pins 34, 36) → differential front-end.**
- **Dedicated ground (pin 08) → single-ended is sufficient**, because there is no
  other sensor's current in that return. This mirrors the OEM's own ranking: they
  gave rail pressure a dedicated return precisely so it would not need one.

| Pin | Signal | Group ground | Front-end |
|---|---|---|---|
| 11 / 41 | Boost: 5 V excitation / pressure signal | 34 | Differential |
| 79 | Boost: temperature signal — **topology unresolved, see §8** | 34 | Differential |
| 34 | Sensor ground — boost + coolant | — | — |
| 33 | Coolant temperature (NTC, pull-up divider) | 34 (spliced) | Differential |
| 15 / 37 | EGR position: 5 V / wiper | 36 | Differential |
| 36 | Sensor ground — EGR + oil pressure | — | — |
| 39 / 80 | Oil pressure: 5 V / signal | 36 (spliced) | Differential |
| 32 / 35 | Rail pressure: 5 V / signal | 08 | Single-ended |
| 08 | Sensor ground — rail pressure, dedicated | — | — |
| — | `5V_SENSOR` rail monitor | — | Divider → ADC, for the correction above |

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
| 01 / 02 | `G_G_B AT1` / `AT2` | — | Switch return legs — but see note below, these may be power grounds |
| 20 | Audio abort | **Active-high** | 47 k / 68 k bias + 3.0 V zener clamp + 220 nF |
| 24 | Override SS | **Active-high** | same |
| 71 | Ignition | **Active-high** | same |

**The active-high front-end is not a divider, and cannot be.** Reading logic
high at a 6 V cranking dip needs a divider ratio above 2.31/6 = 0.385; staying
under 3.3 V at 40 V needs it below 3.3/40 = 0.0825. Those constraints do not
overlap, so no fixed ratio works at both ends. The zener sets the clamp level
and the divider only biases into it, which makes the logic level flat to within
92 mV across the whole range instead of tracking the battery. Verified in
[`sim/blocks/discrete_input.cir`](../../../sim/blocks/discrete_input.cir).

**Pins 01/02 need checking.** Memo 03 infers from the connector drawing that
pins 1, 2, 5 and 6 are large power contacts. Pins 05 and 06 fit that — injector
high side and a battery rail. Switch return legs would not. The likelier reading
is that `G_G_B` denotes battery ground and these are the ECU's main power
grounds, which would also explain why no power-ground pin appears anywhere in
the extraction. Queued as a continuity measurement.

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

Status updated at phase 1 exit, 14 Sep 2026. Three states, and the middle one
carries weight: **Open** means no answer yet; **Answered** means phase-1 research
produced an answer that is good enough to design against but is *inferred*, not
confirmed, and still carries the upgrade path in its memo; **Closed** means
confirmed outright. Nothing here is Closed yet — every confirmation on this list
needs the machine.

| # | Unknown | Status | Blocks | How to close |
|---|---|---|---|---|
| U1 | ECU connector identity | **CLOSED 18 Sep 2026** — **Bosch**, part numbers `1 928 405 192` and `1 928 405 194`, **`code C`** mechanical keying. 94 cavities: power pins 1–8 in their own chamber, then rows 9–28, 29–50, 51–72, 73–94 | — | Closed by markings on the part. Note: an adapter housing **must be code C** or it will not mate |
| U2 | Boost air-temp (pin 79): NTC or ratiometric? | Open | Sheet 3b front-end | One resistance reading, sensor cold — brief task 1.3, closes it outright. **Mitigation: a front-end that works either way** |
| U3 | Controller MPU input — does it exist? | **CLOSED 18 Sep 2026 — No.** The fitted controller is a **DSE4522 MKII**; DSE manual `057-260`'s terminal table runs 1–35 with no speed-pickup terminal | §3 | Closed from the manufacturer's own terminal list |
| U4 | Controller J1939 expectations | **Largely answered** — CAN source addresses **234** (engine) / **44** (instrumentation); J1939-75 instrumentation on, alarms off; the controller takes **oil pressure, coolant temperature, coolant level and ENGINE SPEED** from our ECU over CAN; `ECU Data Fail → Shutdown` | Firmware, CAN sheet | Remaining: the exact PGN set. Log the live bus, or read DSE publication 057-004 |
| U5 | Injector part number and drive profile | **Partly answered** — memo 04 gives a family envelope (65–115 V, 12–24 A peak, 8–13 A hold, 40–100 A/ms) sufficient to design the driver | Boost rail *target* voltage, not the driver sheet itself | Photograph the injector body for a Bosch `0445 1xx xxx` or Kirloskar `F6.xxx.xx.x.pr`. **Separately: the calibration data is a different problem — see §9 and memo 04** |
| U6 | Pin 09 `SYNCHRONIZATION GROUND` function | Open | Power/ground plan | OEM pin list; drawn red despite the name |
| U7 | Pins 04/06 — sense only, or load feeds? | Open | Power sheet current rating | Measure on the live engine, or OEM pin list |
| U8 | 6-pin intake throttle — on the ECU at all? | Open | Whether a throttle driver is in scope | Trace the cable by hand — brief task 3.11; not in this diagram |
| U9 | Catalyst temp sensor — connected where? | Open | Whether an EGT front-end is in scope | Trace on the engine |
| U10 | `SENT` in the colour legend — which signal? | Open | Possible digital sensor front-end | Inspect harness; SENT is SAE J2716 |
| U11 | Engine identity | **CLOSED 18 Sep 2026** — rating plate reads **3GK550ETA 4SR1**, app code **GK3.8703**, 26.5 kW at 1500 rpm, type approval `ARAI/MoEF/DGTA/IGES4/KOEL-P25/2825/24`. Memo 01's inferred `3R550ETA 4G1` was **wrong**; the original "GK550" was right | — | Closed by plate |
| U13 | Which controller is fitted | **CLOSED 18 Sep 2026** — **DSE4522 MKII AMF (India SP)**, part `4522-001-01`, serial 11021794. Photographed front and rear. **Not a KG640C.** Memo 02 superseded; spec §3 rewritten | — | Closed by photograph |
| U14 | Pre-heat / post-heat: driven by the controller or by the ECU? | **NEW 18 Sep 2026** | Whether a heater output is in scope. The design currently has none | The DSE4522 config enables both at 50 °C. Trace the heater's supply at the machine |
| U15 | What does `CRS-878` denote in the controller's engine profile? | **NEW 18 Sep 2026** | Possibly bears on U5 — "CRS" plausibly identifies the common-rail system | Ask KOEL, or find DSE's engine-profile list |
| U12 | **Does the 70 A ignition relay `-13RB1` remove power from the ECU and fuel metering unit, or only signal the ECU?** | Open | **The §3 safety gate.** The entire relaxation from "mandatory trip module" to "recommended" rests on this | Measure at the machine: with the ignition relay de-energised, check for battery voltage at ECU pins 21, 04, 06 and at the fuel metering unit's supply pin. Voltage present ⇒ signal only ⇒ §3 reverts. **Do brief task 1.4 first** — a normally-closed relay gives the same reading with the opposite meaning |

**U12 now stands alone as the load-bearing unknown.** U13 is closed and it cost this
project its safety argument: the fitted DSE4522 takes engine speed from our ECU over
CAN, so the controller's overspeed trip is not independent of the thing it is meant to
protect against. What independence remains is the generator over-frequency shutdown at
56 Hz — and every protective action the controller can take terminates in the same
fuel relay on terminal 3. **U12 asks what that relay's contacts actually carry, and the
entire second line of defence rests on the answer.**

U1, U3, U11 and U13 all closed on 18 September from photographs and one manufacturer's
manual. Three of the four closed *against* an inference this project had made, which is
the honest measure of how much desk research was carrying.

U3 and U11 were the other two on that list and are now answered, both by inference
from primary documents rather than by confirmation. Neither answer is fragile — but
both are the kind of finding that a single photograph at the machine would settle
permanently, which is why they stay on the register rather than leaving it.

U5 has moved off the critical list for a reason worth stating plainly: memo 04's
family envelope means the **injector driver can be designed now, without the part
number**. What the part number buys is a boost-rail target instead of a range. The
thing that genuinely gates running this engine is not on this register at all — it
is the injector calibration data, recorded in §9 and memo 04.

---

## 9. Out of scope

- Injection calibration: timing maps, quantity maps, rail pressure setpoint schedules.
  The hardware will be capable; the maps are a dyno programme, not a PCB deliverable.
- Emissions certification. **But read this before planning deployment** — research memo
  06 found, in primary sources, that the regulatory position is worse than "we simply
  won't certify it." CPCB's RECD System & Procedure states that ECU characteristics
  governing injection timing, air-mass metering and emission-reduction strategy must not
  be altered even under CPCB's own sanctioned retrofit scheme, and excludes changes
  limited to engine control from that scheme entirely. General Condition 3 of GSR 804(E)
  states that no person shall use a genset lacking a valid Type Approval and CoP
  certificate. No approval pathway for a third-party ECU replacement was found.

  This does not block the engineering: designing the board, building it, and bench-testing
  it against simulated signals are unaffected. It bears on **putting it into service on a
  genset that is in use**, and it compounds the calibration risk in memo 04 — this engine
  meets its limits partly through calibration, so a replacement ECU can move it out of
  compliance without any hardware changing at all.

  This is the project owners' decision to take to qualified counsel or to CPCB/ARAI
  directly. It is recorded here because it is material and was not previously examined,
  not to make the decision for them.
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
