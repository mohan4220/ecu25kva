# BOM requirements

What the schematic has to buy, and the simulation that says so.

Every row here exists because a block in `sim/blocks/` failed without it.
The rule this file follows is the same one the netlists follow: **a figure
nobody has read in a datasheet does not become a design number.** So these
are requirements stated as specifiable, purchasable properties — tempco
bands, ESR bands, on-resistance ceilings — not manufacturer part numbers.
Naming a part is a separate step, and it needs a retrieved datasheet.

Where a part number *does* appear below, it is because it was checked.

---

## Input protection

### `TVS` — transient suppressor, battery input

**SMCJ43CA.** Bidirectional, 43 V standoff, 1500 W package.

Both halves of that were forced by simulation, not chosen:

- **43 V standoff** is the smallest standard bin above the 40 V clamped
  load dump. Below it the part conducts during a *normal* ISO 7637-2
  pulse 5b event rather than a fault — which is what `load_dump.cir` was
  failing on, not "the TVS is too small."
- **1500 W (SMC) package, not 600 W (SMB).** At the SMB size, pulse 2a
  clamps at 88.6 V against the buck's 100 V absolute maximum — 11% margin.
  The SMC part has roughly half the dynamic resistance at the same
  standoff and clamps at 73.3 V, 1.37×.

Checked by `load_dump.cir` (0.000 A, 0.000 J through the TVS) and
`transient_clamp.cir`.

### `NEG-CLAMP` — negative active clamp, buck VIN

N-channel MOSFET, **Vds ≥ 80 V (100 V class), Rds(on) ≤ 10 mΩ at
Vgs = 4.5 V**, source to ground, drain to VIN, driven by a comparator
sensing VIN against a −0.1 V threshold. **In parallel with** the
100 V / 20 A clamp Schottky, which stays as the instant passive backstop.

> **CORRECTED 22 September 2026 — both parts were under-rated for the
> rail they sit on.** This tag originally read **Vds ≥ 40 V** and the
> backstop Schottky was **60 V**. Both have a terminal on `VBAT_PROT`,
> and both were sized for the *negative* pulses they exist to catch — but
> pulse 2a drives the **same node to +73.3 V**, where a 40 V FET is
> 0.55× rated and a 60 V Schottky 0.82×. The 40 V FET had zero margin
> on the 40 V load dump alone. `transient_clamp.cir` already carried the
> rule "every part on VBAT_PROT must clear 73.3 V" — as a principle, not
> a list, so nothing compared these two against it. It is now a table in
> `run_sim.py`: every part with a terminal on this rail, its rating, and
> the margin, and a part below the line fails.

The requirement is really an *effective clamp impedance*, and it is worth
stating as one: the LM5164's VIN absolute maximum is −0.3 V, pulse 1
delivers 150 V through 10 Ω, so

    Rclamp ≤ 0.3 V / 15 A = 20 mΩ, junction drop included

**No junction device meets that**, and the reason is structural rather
than a sizing miss. Decomposing the Schottky's own drop at 15 A:

| term | value |
|---|---|
| junction, `N·Vt·ln(I/Is)` | 0.367 V |
| bulk, `I·Rs` | 0.180 V |
| **total** | **0.547 V** |

Only the bulk term falls when parts are paralleled; the junction term is
logarithmic in current and barely moves. Four Schottkys in parallel still
leave 0.375 V. A FET in its ohmic region has no junction offset at all —
15 A through 5 mΩ is 75 mV.

Checked by `negative_pulses.cir`: buck VIN reaches −0.068 V on pulse 1
(4.4× inside the rating) and −0.027 V on pulse 3a (11×), against −0.528 V
and −0.393 V with the Schottky alone.

**Open, and bounded:** the comparator's propagation delay is not modelled.
VIN sits at the Schottky's −0.53 V for exactly that long before the clamp
engages. What changed is the size of the question — it was "is a 2 ms
excursion acceptable," and it is now "is a sub-microsecond one," which a
comparator datasheet answers.

### Clamp Schottky

**100 V / 20 A class** — it was 60 V; see the correction above. It
carries what the TVS used to: **13.58 A peak, 14.5 mJ** on pulse 1,
measured at its own ammeter in `negative_pulses.cir` rather than inferred
from 150 V / 10 Ω.

A 100 V Schottky has a higher forward drop than the 60 V part
`negative_pulses.cir` models (`SCHN`, BV = 60 V). That drop only matters
for the comparator's propagation delay — the window before the active
clamp engages — and is re-measured when the comparator is chosen.

### Reverse-battery FET

**P-channel, |Vds| ≥ 80 V, Rds(on) ≤ 40 mΩ at Vgs = −4.5 V**, drain to
the battery side, source to the load, with a **passive gate network**:
47 kΩ gate-to-ground and a 12 V zener gate-to-source.

> **CORRECTED 22 September 2026 — the sheet had drawn an N-FET, and
> `reverse_battery.cir` has always modelled a P-FET.** Its header says
> "a P-FET held on by a controller that watches the polarity", and its
> switch model closes on positive polarity. Found while choosing the
> controller the N-FET would have needed.

**No controller IC checked can sit on this node.** It swings from
**+73.3 V** (pulse 2a, after the TVS) to **−47.8 V** (pulse 1, the
bidirectional TVS's negative clamp — bidirectional precisely so a
reversed battery does not forward-bias it). That is a 121 V span:

| Controller | Rated | Fails by |
|---|---|---|
| LM74700-Q1 | ANODE −65 V to **+65 V** | 8.3 V on the positive side |
| LM5050-1-Q1 | IN **−0.3 V** to +100 V | 47.5 V on the negative side — and IN draws 320 µA, so a series resistor to protect it corrupts its 20 mV sense |

A P-FET needs no controller: `Vgs = −V(load)`, so it is on whenever the
load side is positive and off when it is pulled to zero. That **is** the
block's switch model, with no IC ratings on a 121 V swing to violate.

**What it gives up, recorded rather than hidden.** An ideal-diode
controller blocks reverse *current*; this blocks reverse *polarity*. On
a dropout that *shorts* the input, bulk capacitance discharges backward
through the FET. The spec carries no hold-up requirement, and the
negative clamp is already sized for this FET staying on through a whole
pulse — its turn-off via 47 kΩ and `Ciss` takes tens of microseconds.

The 40 mΩ ceiling gives 0.2 V at 5 A against the block's 0.3 V
requirement. The model's 8 mΩ is its header's own "mid-range for a 100 V
P-channel" and is optimistic; the ceiling is what `run_sim.py` checks.

---

## Power

### `PDN-BULK` — 3V3_MCU bulk capacitor

**Polymer** aluminium electrolytic or polymer tantalum, 150 µF, specified
by an **ESR band of 20–50 mΩ across −40…+125 °C** — not by a 25 °C
typical figure.

Three things about that are load-bearing:

- **The part class changes, not the value.** A wet aluminium or tantalum
  electrolyte loses conductivity as it freezes, roughly 4× ESR at −40 °C,
  which puts the PDN peak at 197 mΩ against a 100 mΩ target. A solid
  polymer electrolyte has no such mechanism.
- **The cold number is what gets specified.** A supplier's 25 °C ESR does
  not answer this block's question, and asking for it is how the original
  corner got in.
- **A band, not a ceiling.** Bulk ESR is also what damps the
  regulator-against-bulk resonance. At 20 mΩ the peak climbs back to
  92 mΩ, 8 mΩ under target. "ESR ≤ 50 mΩ" would be satisfied by a 5 mΩ
  part that fails this block.

The 100 mΩ target is derived — 50 mV allowed ripple over a 0.5 A
transient step — not a round convention. Checked by `mcu_pdn.cir`.

### `SENSOR-PTC` — 5 V sensor rail, one per sensor group

Resettable PTC, hold current ≥ 200 mA, **R25 = 3.0 Ω nominal**.

Sized against the ceiling rather than guessed. The polyfuse has to be
what clears a shorted harness, not the 5 V regulator's own current limit,
so fault current must stay under 3.0 A:

    I < 3.0 A  ⟹  Rsrc + Rptc > 5/3 = 1.667 Ω
    corner = R25 × 0.8 (cold) × 0.7 (−30% spread) = 0.56 × R25
    ⟹  R25 > 2.78 Ω

At the same stacked −40 °C + −30% corner the specified part draws 2.88 A,
0.12 A under the ceiling. The larger series resistance was re-checked
against the rest of the block rather than assumed harmless: healthy-group
voltage holds at 4.69 V against a 4.5 V floor, and nominal fault current
stays inside the 0.3–3.0 A window the polyfuse needs to trip on.

Checked by `sensor_rail.cir`.

---

## Drivers

### `MU-ISENSE` — metering unit current sense, ECU pin 88 return

**50 mΩ shunt** on the low side, into **either** a current-sense amplifier
feeding an ADC channel **or** a gate driver with an integrated
current-regulation comparator.

The amplifier is not optional: 50 mΩ at the 0.675 A setpoint is 33.75 mV,
too small to take straight to the S32K148's ADC at useful resolution.

This one is not a part-selection fix at all — it is an architecture
change, and it is the only failing corner in the suite that no component
choice could have answered. The coil is copper, copper moves 0.39%/°C,
and over −40…+125 °C its resistance goes 7.39 → 13.82 Ω. At a fixed 50%
duty the mean current follows it: **0.862 A cold against 0.462 A hot**,
+27% and −32% around the setpoint. There is no better resistor to buy.

A hysteretic current regulator holds 0.679 / 0.679 / 0.683 A at
−40 / 25 / +125 °C. **Closed loop only works while the regulator has duty
left** — at the hot corner the coil can draw at most 13.5/13.82 = 0.977 A
at 100% duty, so the setpoint sits at 69% of the ceiling. That bound is
checked, because a regulator out of headroom degrades silently back to
open-loop behaviour rather than reporting anything.

Checked by `metering_unit_pwm.cir`.

### `EGR-DRIVER` — EGR H-bridge

A bridge driver with **internal DIR/PWM decode** — one logic input pair
that cannot express both legs of a diagonal conducting at once.

Two logic lines wired straight to two diagonal switch pairs short the
bridge: with both inputs asserted it draws **270 A**. Under a decoded
interface the same input combination draws **4.35 A**, the motor's own
stall current. The fault state stops existing rather than being avoided
by firmware convention.

Current capability: headroom over a 2.6–6.4 A stall.

No part is named. None has been checked against a retrieved datasheet.
What the schematic needs from the BOM is the interface type, the current
limiting, and that headroom.

Checked by `egr_hbridge.cir`, which keeps the naive wiring as pinned
evidence of why the requirement exists.

### `GATE-PULLDOWN` — fail-safe gate pulldowns, six driver gates

**470 Ω**, gate to source, on every driver gate.

The largest standard value that still holds a gate below Vgs(th) = 1.0 V
against Miller coupling at Crss = 500 pF. The commonly-reached-for 10 kΩ
fails even at the *low* end of the memo's own Crss envelope — 1.155 V at
50 pF already exceeds the threshold.

Cost, stated because it is real: 21.3 mA per gate held at 10 V, 1.28 W
across all six.

Checked by `supervisor.cir`.

---

## Signal

### `CAN-TERM` — CAN split termination, Rah / Ral

60.0 Ω **thin-film**, initial tolerance **±0.1%** or better, tempco
**±50 ppm/°C** or better.

Ordinary standard-grade thick-film runs 100–200 ppm/°C. At 200 ppm/°C
over the full −40/+125 °C span, both resistors shifting together, the
differential impedance reaches 123.95 Ω against J1939's own 120 Ω — and
120 Ω here is what the standard specifies, not a round convention, so
missing it is a real finding.

The contrast is a part class, with no meaningful cost or availability
penalty at this quantity. With both mechanisms stacked the adverse way
(60 × 1.00825 × 1.001 = 60.5555 Ω) the specified part lands at 121.10 Ω,
inside the ±2 Ω window with 0.90 Ω to spare. Checked at the **worst
case**, not the nominal — so passing means the requirement is sufficient,
not merely that it helps.

Checked by `can_termination.cir`.

### `VR-CLAMP` — crank input clamp diodes, four off

Reverse leakage **≤1 µA at 125 °C**. Forward drop is explicitly *not* a
requirement.

This inverts the rule every earlier clamp on this board was chosen by.
The negative-clamp Schottky's 0.547 V at 15 A decomposes into a junction
term and a bulk term, and that decomposition is what ruled out
paralleling junction devices for the power path. These four diodes
conduct only on a fault, into a 4.7 kΩ series resistor that is already
doing the limiting — what matters is what they do when they are **off**.

A reverse-biased diode's leakage flows out of the 4.489 kΩ Thévenin at
the comparator input and appears there as an offset voltage, against a
hysteresis window of ±198 mV:

| Class | Leakage at 125 °C | Offset | Against the window |
|---|---|---|---|
| BAT54S-class Schottky | ~200 µA (≈2 µA at 25 °C, ~100× hotter) | 0.90 V | **4.5× the whole window** — latches |
| BAV199-class low-leakage silicon | <1 µA (5 nA max at 25 °C) | <4.5 mV | 2% of the window |

The two diodes on a leg are reverse-biased symmetrically by `VR_BIAS`,
and the legs are matched, so leakages partly cancel and what survives is
partly common-mode. That is not a thing to defend a speed input on, so
the requirement is stated instead.

`vr_conditioner.cir` does **not** model this — its comparator is an ideal
switch with no input network, so no clamp, no leakage and no offset exist
in it. Found while drawing `hw/speed_inputs.kicad_sch`.

The same tag covers the **differential TVS across the pair**: bidirectional,
standoff ≥48 V. The standoff has to clear the *signal*, not just the rail
— VR amplitude is proportional to speed, about 20 V peak at 1500 rpm, so
a 24 V part would clip a runaway engine's own crank signal at the one
moment the ECU most needs to keep counting teeth. 48 V clears 3600 rpm.

### `VR-COMP` — crank zero-cross comparator

Single **3.3 V** supply, **push-pull** rail-to-rail output, propagation
delay **≤1 µs**. Input common-mode range: **mid-rail only**.

Drawn as `COMPARATOR_GENERIC` — placeholder pins, no footprint — because
no part is chosen. Three of those four are unusually easy, deliberately:

- The output swing *is* the hysteresis window (3.3 V × 4489/(4489+33000)
  = 0.395 V), so an open-drain part would make the window depend on its
  pull-up value and its V<sub>OL</sub>.
- Biasing the floating VR coil to `VR_BIAS` means the inputs never leave
  mid-rail, so **no common-mode range including ground is needed** — the
  usual hard constraint on a zero-cross detector, avoided by biasing the
  sensor rather than level-shifting it.
- 1 µs is 0.009 crank degrees at 1500 rpm on a 60-tooth wheel.
- Input offset voltage and its tempco are non-issues: 10 mV is 5% of the
  window.

Checked by `vr_conditioner.cir`, which establishes the topology (a fixed
5 V threshold produces edges at 1500 rpm and **none** at cranking speed)
and the ±0.2 V window the E24 network above lands on.

### `BOOST-BLEED` — injector boost reservoir bleed

**22 kΩ, 1 W**, across the 47 µF / 100 V reservoir.

The charger regulates from **one side only**: `boost_converter.cir`'s
`Bchg` adds 50 mA while the rail is below setpoint and adds nothing
above it. Nothing else in the circuit can remove charge, so any
excursion above 100 V is permanent. `injector_turnoff.cir` measured the
mechanism that produces one — a hold-current cutoff, whose energy came
from the **battery** through the high side's diode-OR and so has no
boost-side draw to net against — and its RESULT NOTE asked for this
resistor by name.

Sizing is not a duty-cycle argument; it is "one event is gone before the
next cylinder fires":

| | |
|---|---|
| event charge | 10 A decaying to 0 over 20 µs = 100 µC |
| on 47 µF | 2.14 V of rail rise |
| above setpoint | charger is **off**, so the whole 100 V / 22 kΩ = 4.55 mA discharges it |
| time to clear | **21.4 ms**, against **26.67 ms** between cylinders at 1500 rpm |
| cost | **455 mW**, burned continuously whenever the rail is up |

Checked by `boost_converter.cir` arrangement C, which runs two identical
reservoirs — one bare, one bled — through three such events at the real
cylinder spacing. Bare, the rail stacks to 106.4 V and stays there.

A comparator-gated shunt costs nothing at idle and is the alternative.
It is more parts, and it is a part nobody has chosen.

**Over a complete injection event there is no pumping at all** — the
peak phase draws 342 µC from the reservoir and end-of-injection
recirculation returns roughly 100 µC of it. This resistor is not there
for normal running. It is there because one-sided regulation has no
answer for an excursion from *any* cause.

### `INJ-RECIRC` — injector recirculation diodes, five off

**150 V, 20 A, ultrafast.** Three on the low sides (one per cylinder,
into the boost reservoir) and two on the high sides (the battery
diode-OR).

Research memo 10 names the class. Not a Zener active clamp across the
FET — Nexperia AN50003 rates repetitive active clamp
reliability-"Questionable" for gate-oxide wear-out. Not a bare freewheel
to battery, which is too slow: the same problem the boost rail exists to
fix on the opening side.

**Sized by the pulse, not the average.** `injector_turnoff.cir` measures
28.7 W instantaneous during turn-off against roughly 3.6 W averaged over
all nine events per second — a factor of eight. The average would never
have sized this part.

---

## Chosen parts

These are the entries that have moved from "a class" to "a part number",
each against a datasheet that was actually retrieved and read. They are
listed separately from the requirements above because they are answers,
not constraints.

| Function | Part | Why this one |
|---|---|---|
| Buck pre-regulator | **LM5164DDAR** | 100 V input, 1 A, 6–100 V range. See below — it replaces a 60 V part that can no longer survive this input. |
| 3V3 regulator | **TLV76733QWDRBRQ1** | 1% over load *and* temperature. The supervisor makes that load-bearing. |
| Supervisor | **TPS3850G33DRCT** | ±4% window variant, so its undervoltage trip clears the MCU's own LVD by 143 mV rather than 44 mV. |
| Injector boost controller | **TPS40210QDGQRQ1** | Chosen on its **200 ns maximum off-time** — the one spec that makes 94% duty reachable at the 6 V cranking corner. See below. |
| Gate drivers, all eight gates | **AUIRS2181STR** ×5 | **No cross-conduction interlock** — the injector's high and low switches are in series with the coil and must both be on. See below. |
| Current-sense amplifiers | **INA181A1QDBVRQ1** ×3 | VCM reaches −0.2 V, so it sits across a ground-referenced shunt; supplied from 3V3_MCU so its output is ADC-safe by construction. |

### `INA181A1QDBVRQ1` — one part, one gain, three channels

**TI SLYS018F**, April 2018, revised October 2024. Retrieved and
text-extracted.

| | |
|---|---|
| Common mode | **−0.2 V to 26 V** — covers a ground-referenced shunt |
| Gain | 20 V/V (A1), ±1 % max over temperature |
| Offset | **±150 µV max at VCM = 0 V**, 1 µV/°C max drift |
| Bandwidth | 350 kHz (A1) |
| Supply | 2.7–5.5 V; output swings to VS − 0.02 V |
| CMRR | 84 dB min |

| Channel | Shunt | Full scale | Where it sits |
|---|---|---|---|
| Injector bank A → `PTC15` | 5 mΩ | 1.80 V at 18 A peak, 1.00 V at 10 A hold | ADC0 |
| Injector bank B → `PTD19` | 5 mΩ | same | ADC1 — simultaneous with bank A |
| Metering → `PTC16` | 50 mΩ | 675 mV at the 0.675 A setpoint, 844 counts | ADC0 |

**The gain is chosen for the injector.** 1.80 V at the peak leaves
headroom to 3.28 V, so a fault current up to **32.8 A is measured rather
than clipped** — which is what an overcurrent check needs. Offset is
worth 30 mA of injector current (0.17 % of peak) and 3 mA of metering
current (0.44 % of setpoint). Bandwidth resolves the 38 µs ramp to peak
with about 0.45 µs of lag.

**Supplied from 3V3_MCU, which makes the output ADC-safe by
construction.** It cannot swing above VS − 0.02 V, so these three
channels need no 3.3 V zener at the MCU pin — unlike every channel on
`sensors_analog`, which arrives from the harness.

**This closes `MU-ISENSE`'s open half.** That tag specified the 50 mΩ
shunt and said "the amplifier below is not optional"; this is the
amplifier. `IN−` goes to GND, and the tag's layout requirement stands: a
Kelvin tap at the shunt's own ground pad, not a via into the pour.

### `AUIRS2181STR` — chosen because it has *no* interlock

**Infineon (International Rectifier) AUIRS2181(4)S**, datasheet dated
10 January 2014, still hosted by Infineon. Retrieved and text-extracted
this session. **Its first listed typical application is "Piezo / common
rail Injection."** Confirm lifecycle status at sourcing — the datasheet
is old even though the part is still listed.

| | |
|---|---|
| Offset | VB **625 V** absolute maximum; VS operational **−5 V to +600 V** |
| Supply | VCC 10–20 V; UVLO+ 8.0 / 8.9 / **9.8 V** max |
| Logic | VIH 2.5 V min, VIL 0.8 V max — direct from a 3.3 V MCU pin |
| Output | 1.9 A / 2.3 A typ, **1.4 A / 1.8 A min** short-circuit at 15 V |
| Delay | 160 / 200 ns typ, 270 / 330 ns max |
| Interlock | **None** on 2181/21814 (the 2183/2184 have it) |
| Package | SOIC-8, AEC-Q100 |

**Three properties chose it, each against a part that failed on it:**

| Property | This part | Why it matters | Failed it |
|---|---|---|---|
| **No cross-conduction interlock** | none | In a half bridge, HO and LO together is shoot-through and every driver prevents it. Here the "high" and "low" switches are in **series with the coil** and must **both** be on for it to conduct at all | UCC27282-Q1, UCC27712-Q1 — could not fire an injector |
| **Offset rating** | 625 V abs max, **5.4×** margin | Bank node ~103.8 V worst case, VB 12 V above it = 115.9 V | UCC27211A-Q1 — HB 120 V abs max, **4.1 V** of headroom |
| **Negative VS** | operational to −5 V, clears by **3.7 V** | `D_fw` drops the bank node 1.0–1.3 V below ground on **every** hold off-time | UCC27211A-Q1 — HS DC min −1 V, **violated in normal operation** |

The first is the one that is not a rating, and the one nobody searching
a parametric table would filter for: the familiar reflex is that a
half-bridge driver *without* interlock is the less safe choice. In this
circuit interlock is not a safety feature, it is a failure to function.

**Five in use.** Four on `injector` — each package pairs one high side
with one low side, by package and not by circuit; UB2's low side is
spare. One on `metering_egr`, low side only, so the board carries one
gate-driver part number instead of two.

**The kill path moves to `HIN`.** The part has no shutdown pin, and a
ground-referenced FET cannot short a gate floating 100 V up. `HIN` *is*
ground-referenced, so `supervisor.cir`'s kill FET goes there behind a
1 kΩ from the MCU. It is slower than the low-side gate clamp — 330 ns
maximum driver turn-off against 23 ns — and that is acceptable because
it is not the path the fail-safe argument rests on: the low sides are in
**series** with every coil, and killing any one stops that cylinder.

Checked by `boost_converter`'s rating checks in `run_sim.py`.

### `GATE-RAIL` — 12V_GATE, a discrete follower off the boost rail

The board had no rail between 5 V and 40 V, and the drivers need
10–20 V. **Its source is the boost rail, and the reason is cranking:** a
regulator from `VBAT_PROT` cannot make 12 V from a 6–9 V cranking
battery, and a gate rail that collapses during cranking means no
injection exactly when the engine needs it. `BOOST_100V` is the one rail
already designed to hold up from 6 V.

**Not the LM5164 already on the board** — its VIN absolute maximum is
**100 V** (TI datasheet §5.1), and this rail sits at ~102 V.

| Part | Value | Why |
|---|---|---|
| Bias | 2 × 47 kΩ | 87 V split so neither resistor carries all of it; 0.87 mA |
| Reference | 13 V zener | 13 V − Vbe − limit drop = **12.07 V** at 5 mA |
| Pass | NPN, **Vceo ≥ 160 V**, DPAK, AEC-Q101 | 0.44 W at 5 mA; a shorted output puts the whole rail across it |
| Limit | small-signal NPN + **56 Ω** | 0.65 V / 56 Ω = **11.6 mA**, holding a short to **1.16 W** |
| Output | 10 µF 25 V | Holds through each driver's gate-charge pulse |

Load is about 3 mA (five drivers' quiescent current plus gate charge),
designed for 5 mA. **12V_GATE clears the drivers' UVLO+ ceiling by
2.27 V.** Standing load on the boost is now 9.65 mA — bleed, gate rail
and divider — of its 50 mA, and the peak-phase draw still recovers in
8.48 ms against 26.67 ms between cylinders.

**Its failure runs the safe way.** If the boost stops, 12V_GATE
collapses, every driver drops into UVLO and holds its outputs low, and
every gate on the board turns off.

### `TPS40210QDGQRQ1` — chosen on an off-time, not on an input range

**TI SLVS861F**, August 2008, revised June 2020. Retrieved and
text-extracted this session.

| | |
|---|---|
| Input | 4.5 V–52 V, **absolute maximum 52 V** (Table 6.1) |
| Reference | 700 mV, 686–714 mV over −40/+125 °C (Table 6.5) |
| Off-time floor | **tOFF(min) = 170 ns typ, 200 ns max** (Table 6.6) |
| UVLO | 4.25 V typ, **4.5 V max** turn-on (Table 6.5) |
| Supply current | 1.5 mA typ, **2.5 mA max**, not switching |
| Internal regulator | BP = 8 V typ (7–9 V), 0–15 mA |
| Gate driver | 400 mA source / sink |
| Package | HVSSOP-10 PowerPAD (DGQ), 3 × 3 mm, AEC-Q100 grade 1 |

**The number that chose it is the off-time, and the reasoning runs
backwards from the usual.** A boost from a 6 V cranking dip to 100 V
needs

```
D = 1 − 6 / (100 + 0.9) = 94.05 %
```

and a controller's minimum off-time is a floor **in time**, not in duty.
At 150 kHz, 200 ns is 3 % of the period, so `Dmax` = 97.0 % and the
cranking corner clears by **2.95 points**. At 2.2 MHz — where most
wide-input boost controllers in this class sit, and where the magnetics
would be far smaller — the same 200 ns is 44 % of the period and `Dmax`
falls to **56 %**, below even the 86.6 % the rail needs at a *nominal*
13.5 V battery.

So "higher switching frequency, smaller inductor" is the wrong
optimisation here, and the part that looks less modern is the one that
works.

**THE RATING THAT DOES NOT FIT — the third time on this board.** VDD's
absolute maximum is **52 V**; `VBAT_PROT` reaches **73.3 V** for about
50 µs on ISO 7637-2 pulse 2a. Over by **1.41×**.

This is the same shape as DRV8873-Q1's 40 V `VM`, which took that part
off the EGR bridge — and it is solvable here for a reason that did not
apply there. A motor bridge's `VM` carries the motor current; this pin
carries 2.5 mA plus gate charge. So it gets its own clamp:

### `BOOST-VDD-CLAMP` — 47 Ω, 1 W, and a 43 V zener, 1 W

| | |
|---|---|
| Pulse 2a, 73.3 V | zener passes (73.3 − 43)/47 = **645 mA**, for 50 µs = **1.39 mJ** |
| Load dump, 40 V for 400 ms | **43 V clamp does not conduct at all** |
| Cranking, 6 V in | 2.5 mA + 25 nC × 150 kHz = 6.25 mA, dropping **0.29 V** → VDD = **5.71 V** |
| against UVLO turn-on max 4.5 V | **1.21 V of margin** |

**43 V rather than 39 V is the whole point of the value.** A 39 V clamp
would sit in conduction for the load dump's entire 400 ms at roughly
0.8 W. A 43 V clamp only works during the 50 µs pulse, where 1.39 mJ is
nothing.

The 47 Ω is squeezed from both ends: small enough that 6.25 mA does not
drop the part below UVLO at the cranking dip, large enough that the
zener sees 645 mA and not more during the pulse.

**The power stage is untouched by any of this** — the inductor and FET
see the rail directly, and are 150 V class for it, the same class the
injector switches already carry.

Checked by `boost_converter.cir`'s rating checks in `run_sim.py` — not
with a switching model, which that block deliberately does not have, but
as executable arithmetic on the datasheet's own numbers. Same treatment
`transient_clamp.cir` gives the 73.3 V rail.

**What is NOT settled by a datasheet:** the loop compensation. `Rcomp`
10 kΩ and `Ccomp` 6.8 nF put the error amplifier's zero at 2.3 kHz,
below the right-half-plane zero a boost puts at
`(1−D)² · Rload / (2π·L)` = 17.3 kHz at 13.5 V in — and that zero
**moves with duty cycle**, so the cranking corner is the hard one. These
are a starting point. A current-mode boost's loop depends on the
inductor's real DCR, the capacitor's real ESR and the FET's real
switching behaviour; it gets measured on the bench.

### `LM5164DDAR` — and the 60 V part it replaces

Research memo 07 §4 selected **TPS54360B-Q1**, reasoning that a 60 V part
beat a 42 V LM5175-Q1 "for load-dump margin". That reasoning was correct
when it was written. It is not correct now, and the change came from the
input-protection work above:

- The TVS standoff had to rise to 43 V so the part stops conducting
  during a *normal* clamped load dump.
- A higher standoff clamps higher. Pulse 2a now clamps at **73.3 V**.
- `transient_clamp.cir` carries a **passing** check that says so in as
  many words: *"60 V-class parts are NO LONGER viable downstream."*

A 60 V buck on this input is a part that fails the first ISO 7637-2
pulse 2a event. The LM5164 was already the part every rating check in the
suite was written against — its −0.3 V / 100 V VIN limits are what
`negative_pulses` and `transient_clamp` check — but nothing had ever
reconciled the BOM table with it. **This is what a contradiction between
two documents looks like when only one of them is executable.**

Operating range 6–100 V covers the spec's own 6–40 V requirement, with
the 6 V end matching the cranking dip the input range was built around.
1 A against an estimated 400–500 mA board load.

Configuration values, all derived from the datasheet rather than picked:

| Part | Value | From |
|---|---|---|
| `RON` | 31.6 kΩ | The tON table in §5.5 is linear in RON/VIN: at 12 V, 25 kΩ gives 830 ns, so K = 398 ns·V/kΩ. For 400 kHz at 5 V out, RON = tON·VIN/K is 31.4 kΩ at **both** 13.5 V and 40 V — the VIN feedforward is what holds the frequency fixed. E96 value 31.6 kΩ. |
| FB divider | 38.3 kΩ / 12.1 kΩ | VREF is 1.2 V (1.181–1.218, ±1.5%), so 5 V needs 1 + R1/R2 = 4.167. |
| EN/UVLO divider | 75 kΩ / 24.9 kΩ | Enable rises at 1.5 V typ; 0.249 ratio puts turn-on at 6.02 V, the spec's cranking-dip floor. The pin is rated to 100 V, so the divider programs the threshold rather than protecting the pin. |
| BST cap | 2.2 nF 50 V X7R | Not a range. The datasheet specifies the part: *"a high-quality 2.2nF 50V X7R ceramic capacitor between BST and SW"*. |
| `L` / `Cout` | 33 µH / 47 µF, 10 mΩ ESR | `buck_preregulator.cir`, sized at the 40 V worst case rather than nominal. The ESR is part of the value — it sets the ripple. |

The RON figure is worth one more line: it independently reproduces
`buck_preregulator.cir`'s own gate timings, 925 ns at 13.5 V and 312.5 ns
at 40 V. The netlist got those from D = Vout/Vin; the datasheet gets them
from RON. They agree.

### `TLV76733QWDRBRQ1` — accuracy as a requirement

Memo 07 §6 named `TLV1117-33QDCYRQ1`, explicitly *"class pricing, not
fetched"*. Choosing the supervisor turned 3V3 accuracy into a hard
constraint: outside **3.143–3.459 V** the board resets itself. TLV767-Q1
is **1% over load and temperature** — 3.267–3.333 V, about 125 mV of
margin at each end. 1 A, 2.5–16 V in, AEC-Q100, VSON-8.

The fixed-output version is the one specified. Its pin 3 is `SNS` where
the adjustable version has `FB`, and they are not interchangeable. `SNS`
must not float; it is tied to `OUT`.

### `TPS3850G33DRCT`

See `docs/pinmap.md` §1.8 and `hw/gen_symbols.py`. The variant letter is
the decision: `G` sets thresholds at ±4% of nominal and `H` at ±7%, and
with the part's ±0.8% accuracy that is a worst-case undervoltage trip of
**3.143 V** against **3.044 V**. The supervisor has to assert before the
S32K148's own LVD (3.0 V max), so G33 clears it by 143 mV and H33 by
44 mV — close enough that the two could fire in either order, and a
supervisor that might lose the race to the thing it supervises is not
doing its job. The cost is the tighter rail window above.

---

## MCU

**NXP S32K148, `FS32K148HAT0MLQT`** — 144-pin LQFP, 80 MHz, −40…+125 °C.

Confirmed in research memo 05 against the S32K1xx data sheet Rev. 15 with
page-level citations. The full reasoning is there; what matters for the
BOM:

- The **144-pin** package is headroom against unknown U1 (50 of the OEM
  ECU's 94 pins are still unresolved), not a requirement of the confirmed
  channel budget, which fits inside a 100-pin part.
- **LQFP over MAPBGA**: identical instance counts — CAN/ADC/FTM/I²C are
  silicon-level, not package-level — and 0.5 mm pitch is inspectable by
  eye or AOI, where a BGA needs X-ray or destructive inspection. A real
  cost for a small team doing early assembly.
- **80 MHz `H` grade, not 112 MHz `U`**: the `U` speed grade is *not
  valid* at the 125 °C `M` temperature grade, per the datasheet's own
  ordering-table footnote. Memo 05 §6 shows the extra clock is not needed
  to close the timing budget, so there is no reason to trade thermal
  margin for headroom the design does not use. This corrects the spec §5
  framing, which cites 112 MHz.
- In stock at DigiKey's India storefront at single-unit quantities. Not a
  lead-time part. The S32K146 fallback was checked and is *not* needed —
  it is the one that is out of stock, with 12–52 week lead times.

**Still to check before footprint lock:** package drawing 98ASS23177W
(SOT486-2) has not been independently fetched. The PCB roadmap's warning
stands — a hand-sourced footprint is the most likely place to introduce a
silent error.
