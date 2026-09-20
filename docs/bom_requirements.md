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

N-channel MOSFET, **Vds ≥ 40 V, Rds(on) ≤ 10 mΩ at Vgs = 4.5 V**, source
to ground, drain to VIN, driven by a comparator sensing VIN against a
−0.1 V threshold. **In parallel with** the 60 V / 20 A clamp Schottky,
which stays as the instant passive backstop.

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

60 V / 20 A class. It carries what the TVS used to: **13.58 A peak,
14.5 mJ** on pulse 1, measured at its own ammeter in `negative_pulses.cir`
rather than inferred from 150 V / 10 Ω.

### Reverse-battery FET

**100 V class** — its third revision, raised each time the clamp moved.
`transient_clamp.cir` now carries an explicit check stating this
downstream requirement, so the next move does not depend on someone
reading three files and noticing.

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
