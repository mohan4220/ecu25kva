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

### Where the chain terminates — U12 CLOSED 18 Sep 2026, and it closed badly

> **The measurement came back: the fuel relay cuts a signal. It does not remove power.**
>
> Reported from the machine alongside two other findings — the intake throttle and the
> pre-heat/post-heat heaters are all fed **from the battery**, not from the ECU.
>
> This is the outcome the inspection brief told the reader to flag immediately rather
> than save for a writeup, and the reasoning below was written before the answer was
> known. It stands as written; what follows is what it now means.
>
> **Both independent lines of defence are gone, for two separate reasons.**
>
> The controller has no independent speed path — it takes engine speed from this ECU
> over CAN (U13, closed 18 Sep). And its every protective action terminates in a relay
> that only signals. So a hung ECU keeps the fuel metering unit energised, and the
> device that is supposed to catch that is asking the hung ECU how fast the engine is
> turning.
>
> What survives: generator over-frequency at 56 Hz, measured from the alternator, which
> does not depend on this ECU for its *measurement* — but which acts through the same
> signalling relay. It can detect the runaway. It cannot stop it.
>
> **Confidence, stated honestly.** Brief task 1.4 exists because a normally-closed relay
> produces the same voltage reading with the opposite meaning, and it is not confirmed
> that 1.4 was performed before this result. The wording reported ("cuts signal") is a
> statement about function rather than a raw voltage, which suggests tracing rather than
> a single measurement — but that is an inference about how the work was done, not
> evidence. Adopting the unsafe reading costs nothing if it is wrong; adopting the safe
> one and being wrong costs the machine. Confirmation is still wanted, and it does not
> gate anything, because nothing below changes if it comes back the other way.

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
4. ~~**The gate: U12 must be closed by measurement before any build takes injection
   authority.**~~ **Closed 18 Sep 2026, in the failing direction.** The gate was written
   to admit the possibility that U12 came back clean. It did not. The relay signals, so
   line 2 detects a runaway without being able to act on it, and item 3's "mandatory" is
   no longer a precaution against an unverified relay — it is the only shutdown path on
   this machine that does not run through the ECU being protected against.

5. **The trip module must break the fuel metering unit's supply directly.** This follows
   from U12 and is now a requirement, not a preference. A trip module that signals the
   same GCU relay chain inherits exactly the defect U12 just exposed. Its contacts have
   to sit in series with the metering unit's own battery feed — the one through fuse
   `8F1` — so that tripping removes fuel authority regardless of what the ECU, the
   controller, or the GCU relay board is doing. Both costed candidates in memo 02 are
   contact-output devices and can be wired this way; the costing survives, the wiring
   assumption behind it does not.

The owners may of course revisit item 3 with evidence. What they should not do is
inherit the previous revision's conclusion, because the fact it was built on turned out
to describe a controller that is not on this machine.

### What this ECU must do about the trip module

Item 5 puts the trip module's contacts in series with the fuel metering unit's battery
feed. That interface is the module's, not ours — but it constrains this design in three
ways, and none of them has been designed against yet.

**We must not be able to defeat it.** The trip module removes the metering unit's
supply. Our low-side driver on pin 88 sinks current from that supply, so when the module
trips, our output has nothing to switch. That is the property that makes the arrangement
work, and it must survive the detail: no path from any ECU output may re-energise the
metering unit around an open trip contact. Any such path would be a wiring error that
silently restores the failure mode the module exists to remove.

**We should sense its state, and treat it as an input rather than a surprise.** A trip
that removes fuel while the ECU is still commanding injection produces a fault the ECU
should recognise and report over CAN, rather than reading it as a fuelling anomaly and
compensating. The cheapest form is one discrete input sensing whether the module's
contacts are closed. That is a new connector position and a new front-end, and it does
not exist in the OEM harness — a deliberate addition, listed under §7.

**We must fail safe into it, not against it.** The module acts on overspeed sensed by
its own magnetic pickup. The ECU's own overspeed shutdown (item 1) acts on the crank
sensor. These are independent measurements of the same quantity, and they will disagree
near the threshold. The ECU must not treat its own reading as authoritative to the point
of trying to keep running through a trip.

**Not yet decided:** whether the module's pickup shares the flywheel target with our
crank sensor or gets its own. Sharing is cheaper and physically simpler; separate
targets preserve the independence that is the entire point of fitting the module. This
is a mounting question for whoever fits it, and it should be answered before the module
is ordered rather than after.

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
| 45 / 46 | Cam Hall: 5 V / Frequency I/P | **This row was wrong — see the correction below** |
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

#### Cam front-end (pin 46) — this row was wrong, CORRECTED 19 Sep 2026

The outputs table said "pull-up to `5V_SENSOR` → timer capture" for the cam frequency
input. A Hall sensor pulled up to the 5 V sensor rail swings to 5 V, and the S32K148 is a
3.3 V part. Taken literally, that drives an MCU pin above its absolute maximum.

It survived because **nothing simulated it.** There is a `vr_conditioner` block for the
crank sensor and no cam equivalent, so the mechanism that catches this class of error
never looked. Found by the pin-map work, on the way to something else.

This is the second front-end here specified in a way that would have destroyed a pin. The
first was a divider on the battery sense — caught by `battery_sense.cir`, precisely
because a block existed.

**Now built:** `sim/blocks/cam_frontend.cir` divides the 5 V swing into the 3.3 V domain
and verifies it across the rail's own range — 3.072 V nominal, 3.147 V at 5.25 V high
line, 2.769 V at the 4.5 V fault floor `sensor_rail.cir` established, where it still
reads a valid logic high. All clear the 3.6 V absolute maximum. It also checks a 40 V
harness short, which clamps the pad to 3.308 V with fault current held to 3.7 mA.

#### Nothing on this board protects the buck against a NEGATIVE input — GAP, found 19 Sep 2026

`sim/blocks/negative_pulses.cir` simulated ISO 7637-2's negative transients for the first
time, which became possible only once the TVS stopped being modelled as a single diode.

**The LM5164's VIN pin is rated −0.3 V to 100 V.** The negative limit is not a mirror of
the positive one, and nothing in this design was ever sized against it. Read from TI's own
absolute-maximum table.

With the reverse-battery FET assumed still conducting — the honest assumption, since no
turn-off delay is sourced anywhere and pulse 3a is only 0.1 ms wide:

| Pulse | Buck VIN | Past the −0.3 V rating by |
|---|---|---|
| 1 (−150 V / 10 Ω / 2 ms) | **−40.7 V** | 135× |
| 3a (−220 V / 50 Ω / 0.1 ms) | **−27.8 V** | 93× |

The bidirectional TVS clamps correctly. It clamps to its own breakdown, and −38 V is a
perfectly good clamp that is still two orders of magnitude outside what the buck
tolerates. **This is a missing component, not a mis-sized one** — the chain has no series
element or shunt diode addressing a negative excursion.

**And the reverse-battery stage cannot be assumed to cover it.** If its controller opens
fast enough the buck is isolated almost perfectly; if not, the FET conducts and the buck
sees the full clamped negative voltage. `reverse_battery.cir` models instant turn-off and
its own RESULT NOTE warns it "will always look perfect in reverse". **No controller part
is chosen and no turn-off delay is sourced**, so both bookends are simulated and neither
is claimed. That delay is now a load-bearing number, and this decision should be taken
with the controller selection rather than separately.

#### Every driver gate is held off by hardware, not by firmware — REQUIRED 18 Sep 2026

Research memo 11 establishes the hazard with the MCU's own datasheet numbers rather
than by argument. Two facts combine badly:

- **S32K148 GPIOs are high-impedance out of reset**, until firmware configures them.
  High-impedance on a gate driver is not "off" — it is undefined, and the gate can be
  brought up by leakage or by capacitive coupling from a switching node.
- **There is a band where nothing internal resets the part.** Low Voltage Reset always
  forces a reset at 2.50–2.7 V, but Low Voltage Detect at 2.8–3.0 V only does so if
  firmware has set `LVDRE`. Below the datasheet's own 2.97 V correctness guarantee and
  above LVR, the core may execute wrong instructions **with its outputs still driven**.

The pin that makes this concrete is **88**. The fuel metering unit is fed from battery
through fuse `8F1` and switched low-side by this ECU (§2.2). A gate floating high during
reset energises the metering unit with no firmware in control of it — and, since U12,
with nothing downstream able to remove its power either.

**Therefore, as a binding requirement on every driver gate in the table above:**

1. A **gate–source pulldown** at each gate node, sized by the FET actually chosen rather
   than fixed here:

   > `Rpd < Vgs(th) / (Crss · dV/dt)`

   **The dV/dt in that formula is the weakest number in this requirement, and this
   document previously overstated its standing.** It read "2.8 V/µs from
   `injector_turnoff.cir`", which is a citation that file explicitly refuses: its own
   comments say reporting a dV/dt from that model "would be exactly the kind of
   promotion-to-sourced the project's own discipline rules out." The figure is memo 10's
   **inferred** estimate — 100 V in ~36 µs — and `supervisor.cir` imports it as an
   assumed input waveform, labelled INFERRED there too. Every file closer to the number
   than this one hedges it; only the spec stated it flatly, beside genuinely simulated
   figures, where it read as one of them.

   **It is also an average, not a peak, and the error runs in the unsafe direction.**
   100 V over 36 µs is the mean slope of the whole turn-off. Miller coupling happens
   during the plateau, where a real FET slews far faster. The requirement's sensitivity
   to that, at Crss = 500 pF:

   | dV/dt | gate through 470 Ω | Rpd actually needed |
   |---|---|---|
   | 2.8 V/µs (the assumed average) | 0.66 V — ok | < 714 Ω |
   | 10 V/µs | 2.35 V — over threshold | < 200 Ω |
   | 28 V/µs | 6.58 V — over threshold | < 71 Ω |

   At 200 Ω the gate driver would need an output impedance near 10 Ω; at 71 Ω a passive
   pulldown cannot be driven at all. **So the 470 Ω answer survives only at the assumed
   average**, and a modest factor on the real slew rate removes the passive-pulldown
   topology entirely rather than merely resizing it.

   **A second assumption pulls the other way.** The 470 Ω also assumes Vgs(th) = 1.0 V,
   the conservative end of a 1.0–2.5 V class range with no part chosen. Read at 2.5 V the
   same sweep gives **1000 Ω and a ≤52.6 Ω driver**. So:

   | Assumption | Direction | Effect on 470 Ω |
   |---|---|---|
   | Vgs(th) 1.0 V vs 2.5 V | permissive if wrong | 470 Ω is **pessimistic** — costs drive current, not safety |
   | dV/dt 2.8 V/µs (an average, not a plateau slew) | **unsafe if wrong** | 470 Ω is **optimistic** — a real slew of 10 V/µs demands 200 Ω |

   The slew-rate assumption is the larger lever and the dangerous direction. **Treat
   470 Ω as a demonstration, not a value to build to:** what it actually shows is that a
   passive pulldown alone lives in a narrow window bounded by two numbers nobody has
   measured. That conclusion holds whichever way either assumption lands, and it is the
   argument for the active clamp — which `sim/blocks/supervisor.cir` has already
   validated, and which research memo 12 recommends building discretely regardless of
   the driver-architecture decision.

   At a 1.0 V threshold that is **under 1.79 kΩ for Crss = 200 pF, 714 Ω at 500 pF,
   357 Ω at 1000 pF**. `sim/blocks/supervisor.cir` claim 6 sweeps this directly and
   lands on **470 Ω** at Crss = 500 pF — twenty times smaller than the figure this
   requirement first carried.

   **That value constrains the gate driver, and the two cannot be specified apart.**
   At 10 kΩ the pulldown was a perturbation on the driver. At 470 Ω it is the bottom
   half of a divider with the driver's own output impedance:

   > `Vgs = Vdrv · Rpd/(Rpd + Rdrv)` — holding 9.5 V across 470 Ω needs **Rdrv ≤ 24.7 Ω**

   It also costs **21.3 mA per gate and 1.28 W across all six**, continuously, whenever
   the FETs conduct. Stating the pulldown as a single number hid both the coupling and
   the power.

   **This reopens a topology question memo 11 closed on the bad arithmetic.** The memo
   considered an active clamp and dismissed it. A passive pulldown strong enough to
   reject Miller coupling at 500 pF is strong enough to fight its own driver and burn
   over a watt doing it — which is the trade an active clamp exists to avoid, and which
   an integrated driver in the MC33814 class handles internally. That decision is now
   coupled to the driver-architecture decision below and should be taken with it.

   **This requirement said "10 kΩ" when first written on 18 Sep 2026, and that was
   wrong.** Memo 11 §4 computed the Miller-coupled current correctly at 140–560 µA and
   then mis-multiplied, reporting 5.6 mV across 10 kΩ where the answer is 5.6 V.
   `sim/blocks/supervisor.cir` was built to check that paragraph and fails it at 50 pF,
   the low end of the memo's own range. The memo now carries the correction inline. The
   error is recorded rather than quietly patched because it survived a review, a spec
   commit, and was caught only by simulating the claim.
2. A **windowed supervisor** monitoring `3V3_MCU`, tripping at **~3.05–3.10 V**, above
   LVD's 3.0 V maximum, so the trip does not depend on whether firmware ever configured
   `LVDRE`. Its watchdog window must close well inside one cylinder interval (26.67 ms
   at 1500 rpm).
3. The supervisor's reset, inverted, driving a **kill transistor at each protected
   gate**, so the safe state is enforced independently of GPIO configuration. A plain
   timeout watchdog is defeated by a stuck loop that still kicks it; the window is what
   closes that.

This is the ECU's own fail-safe and it is **separate from the standalone trip module**
of §3. The trip module removes fuel authority from outside the board; this keeps the
board's own outputs defined while it still has power. Neither substitutes for the other,
and since U12 neither is optional.

**Open, and blocking the detail rather than the requirement:** the physical `PTxx`
assignment for pins 88, 73/07/29 and 03/05 is a phase-2 task (§5), so the per-pin reset
pull defaults cannot yet be looked up. The requirement above does not depend on them —
it exists precisely so that the answer does not matter — but the analysis cannot be
finished until the pin map is fixed.

#### The EGR driver must decode IN1/IN2 internally — REQUIRED 19 Sep 2026

`sim/blocks/egr_hbridge.cir` argued that no IN1/IN2 combination could short a leg,
because each input line drives a *diagonal* pair. A review falsified it against the
block's own wiring: IN1 commands leg-A-high and leg-B-low, IN2 commands leg-B-high and
leg-A-low, so asserting **both** turns all four switches on and shorts **both legs**
rail-to-ground at once. Simulated at **270 A**, matching the hand figure of two legs of
2 × 50 mΩ across 13.5 V.

The reasoning failed by checking each input line alone and never asking what the two do
together.

**Nothing on this board currently prevents that state.** The gate pulldowns hold both
lines low at reset, which is correct and not the issue — the exposure is any fault or
firmware error that drives both high.

**The requirement:** the EGR driver must decode IN1/IN2 so that the 11 state means brake
or coast and never shoot-through. Integrated H-bridge drivers do this internally, and
that now counts as a reason to prefer one here — note that memo 12's driver decision
covered the *injectors* and explicitly did not address EGR. If the driver is discrete,
the interlock has to be built, and **a per-leg dead time is not sufficient on its own**:
this fault is a logic state, not a timing overlap.

The block fails this check until a driver with that decode is specified.

#### Driver architecture — DECIDED 19 Sep 2026, research memo 12

**Discrete power MOSFETs with a gate-driver IC for the injector banks, keeping the
100 V boost rail. An integrated smart low-side switch for the metering unit. An active
kill-clamp at every gate of both, built discretely.**

The decision was forced by one confirmed number. The two integrated injector-driver ICs
that fit this design's channel count and current class both cap their boost rail **below
the 100 V already chosen**: MC33816's `VBOOST` absolute maximum is **72 V** (NXP
datasheet Rev 10.0), and L9781's tank voltage is reported at 80 V — snippet only, its
datasheet having failed retrieval across two independent sourcing passes.

Adopting either would force the boost rail down and re-derive three already-passing
blocks. Memo 12 re-did that arithmetic: at 72 V the peak-phase ramp stretches from
38 µs to **53 µs**, which still fits a pilot injection but consumes half of it.

**And neither part removes the work.** Both are pre-drivers, not integrated power
stages — external MOSFETs, external boost inductor and diode, and external sense shunt
are required either way. MC33816 additionally brings its own microcode toolchain.
MC33814 is the wrong class outright: 1.3 A continuous against an 18 A requirement, and
no boost stage at all.

**On the coupled clamp question, the integrated route relocates the problem rather than
removing it** — and does so in a form worth copying. MC33816's high-side pre-driver is
*actively forced low* on reset, falling back to a weak 500 kΩ–2 MΩ resistor only once
its bootstrap capacitor is exhausted. That is the same two-tier structure
`supervisor.cir` already validated, on a different bias rail, and with no datasheet
statement about how fast that bootstrap decays under brownout — where `supervisor.cir`
claim 4 gives a timed guarantee. **So build the active clamp discretely regardless.**
This was never a question the IC-versus-discrete decision could have answered
differently.

**What would change this:** a retrieved L9781 datasheet showing a tank voltage at or
above 100 V, or a decision to accept a ≤72 V rail on other grounds.

**Two sourcing items escalated and unresolved:** MC33816AE carries a distributor
last-time-buy date of 06/08/2027, and the L9781 datasheet has now failed retrieval five
times across two sessions. Both need a human with distributor or FAE access rather than
another automated fetch.

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
> binding constraint in either case — at 6000 rpm a 60-tooth wheel produces an edge
> every **83 µs**, which is about **6,700 CPU cycles** at 80 MHz against an NVIC latency
> of roughly 12. The comparison was never close, so constant speed cannot be what makes
> it comfortable. The reasoning below replaces it.
>
> **Re-corrected 18 Sep 2026.** This box said "an edge every 28 µs, which is over 2000
> CPU cycles". 28 µs is the **one-degree-of-crank** period at 6000 rpm (10,000 µs ÷ 360),
> not a tooth-edge period — a unit conflation, off by a factor of six, sitting inside a
> box that was itself written to fix an earlier reasoning error. A 60-tooth wheel at
> 6000 rpm gives 166.7 µs per tooth and 83.3 µs per edge counting both polarities.
>
> The conclusion is unaffected and in fact strengthened: the correct figure gives *more*
> margin, not less. It is corrected because a wrong number that happens to support the
> right answer is still a wrong number, and this one would have been inherited by anyone
> reasoning forward from it.

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

**Pin map done, 19 Sep 2026 — see [`docs/pinmap.md`](../../pinmap.md).** The first of
the two deferred items above is closed: the Reference Manual's own embedded
`S32K148_IO_Signal_Description_Input_Multiplexing.xlsx` (not the datasheet) gives 128
GPIO-capable pins on the 144-pin package, of which this design commits 37, including all
94-way connector signals with a confirmed identity (spec §4). It also settles §4's
own deferred fail-safe detail: all six gate pins (88, 73/07/29, 03/05) are confirmed
high-impedance with no pull at reset, exactly the condition §4's hardware kill-clamp was
already designed against. One new finding surfaced in the process: pin 46's cam
front-end, as specified above, would put a 5 V swing on a 3.3 V MCU pin — flagged there,
not fixed here. Package pad-pitch verification remains open.

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
| U8 | 6-pin intake throttle — on the ECU at all? | **Partially answered 18 Sep 2026** — reported **battery-fed**, so the ECU does not supply it | Whether a throttle *driver* is in scope. Supply and control are separate questions and only supply is answered | Still needs brief task 3.11: follow the cable and see whether it terminates at the 94-way connector. A battery-fed actuator can still be ECU-commanded |
| U9 | Catalyst temp sensor — connected where? | Open | Whether an EGT front-end is in scope | Trace on the engine |
| U10 | `SENT` in the colour legend — which signal? | Open | Possible digital sensor front-end | Inspect harness; SENT is SAE J2716 |
| U11 | Engine identity | **CLOSED 18 Sep 2026** — rating plate reads **3GK550ETA 4SR1**, app code **GK3.8703**, 26.5 kW at 1500 rpm, type approval `ARAI/MoEF/DGTA/IGES4/KOEL-P25/2825/24`. Memo 01's inferred `3R550ETA 4G1` was **wrong**; the original "GK550" was right | — | Closed by plate |
| U13 | Which controller is fitted | **CLOSED 18 Sep 2026** — **DSE4522 MKII AMF (India SP)**, part `4522-001-01`, serial 11021794. Photographed front and rear. **Not a KG640C.** Memo 02 superseded; spec §3 rewritten | — | Closed by photograph |
| U14 | Pre-heat / post-heat: driven by the controller or by the ECU? | **Partially answered 18 Sep 2026** — reported **battery-fed** | Whether a heater *output* is in scope. As with U8, supply is not control | Who switches that battery feed is still open. The DSE4522 config enables both at 50 °C, so the controller is the likely switch — photograph the heater relay and trace its coil |
| U15 | What does `CRS-878` denote in the controller's engine profile? | **NEW 18 Sep 2026** | Possibly bears on U5 — "CRS" plausibly identifies the common-rail system | Ask KOEL, or find DSE's engine-profile list |
| U16 | **Is the battery-charging alternator's rectifier suppressed (avalanche/clamping), or unsuppressed?** | **NEW 18 Sep 2026** | **The input-protection topology.** Suppressed ⇒ ISO 7637-2 pulse 5b, ~40 V clamped, and the fix is a TVS standoff above the dump level — a part number. Unsuppressed ⇒ pulse 5a at 65–87 V unclamped, tens of joules that nothing downstream can ride out, and a different circuit | The alternator's rectifier part number (look for a suppression/avalanche bin), or a scope on the battery terminal during a live disconnect under load. The scope test needs the set running — a supervised activity, not a solo checklist item |
| U12 | **Does the 70 A ignition relay `-13RB1` remove power from the ECU and fuel metering unit, or only signal the ECU?** | **CLOSED 18 Sep 2026 — it only signals.** Reported from the machine. The relay does not remove power; a hung ECU keeps the fuel metering unit energised | **§3's safety gate, resolved against us.** The trip module is mandatory, and §3 item 5 now requires its contacts to break the metering unit's own battery feed rather than signal the same relay chain | Closed. Task 1.4's normally-closed check is still wanted as confirmation, but nothing depends on it — the unsafe reading is already adopted |

~~**U12 now stands alone as the load-bearing unknown.**~~ **U12 closed 18 Sep 2026, and
the answer was the bad one.** U13 cost this project its safety argument: the fitted
DSE4522 takes engine speed from our ECU over CAN, so the controller's overspeed trip is
not independent of the thing it is meant to protect against. What independence remained
was the generator over-frequency shutdown at 56 Hz — and every protective action the
controller can take terminates in the same fuel relay on terminal 3.

**That relay signals. It does not remove power.** So the second line of defence can
detect a runaway and cannot stop one. The two findings compound: the controller either
cannot see the fault (overspeed, read from our CAN) or cannot act on it (over-frequency,
acting through a signalling relay).

Nothing on this machine currently interrupts fuelling without the cooperation of the ECU
being protected against. The trip module in §3 item 3 is what closes that, and §3 item 5
now specifies where its contacts have to sit — in series with the metering unit's own
battery feed, not in the GCU relay chain that just failed this test.

Worth stating plainly, because it is the pattern of this whole phase: **four of the five
unknowns closed by field evidence closed against what this project had reasoned.** U11
(engine identity), U13 (which controller), U1 (connector — this one closed *for* us),
and now U12. Desk inference has a measured track record here, and it is poor.

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
- The panel controller. We talk to the **DSE4522 MKII AMF**; we do not replace it. (Earlier
  revisions of this line said KG640C, which is what the OEM wiring diagram shows and not what
  is fitted — see §3.)
- Panel wiring, ATS, alternator metering.

---

## 10. Phase sequence

| Phase | Output | Status |
|---|---|---|
| 0 | This document | Done |
| 1 | Research memos: engine ID, controller, MCU confirmation, injector and connector sourcing | **Done** — nine memos |
| **1.5** | **Block-level simulation: topology and component values verified before capture** | **In progress — 17 blocks, all passing** |
| 2 | KiCad hierarchical schematic capture | Not started |
| 3 | 4-layer PCB layout, DRC, fab outputs | Not started |
| 4 | Firmware skeleton: HAL, J1939, crank sequencing, fault manager | Not started |

**Phase 1.5 was added on 18 Sep 2026 to name work that was already happening.** The
simulated blocks are neither research memos nor schematic capture, and leaving them
unnamed meant the roadmap did not describe the most productive activity on the project —
the one that caught a divider that would have destroyed an ADC pin, a discrete input that
was impossible as specified, and a decoupling network thirty times over its impedance
target. It also gives the two gaps the circuit review found — load dump, and injector
turn-off energy — a phase to belong to instead of floating as review findings.

Phase 2's blocked sheets are now fewer: **U1 is closed** (Bosch `1 928 405 192` / `194`,
code C), so the connector and adapter-harness sheets are unblocked. U2 blocks one sensor
front-end, U8 blocks whether a throttle driver exists at all, and U5 sets the boost rail's
target voltage but not the driver itself. Power, CAN, MCU support, speed inputs, the
relay outputs and the analog front-ends are all fully specified above.
