# Design decisions put to the owner

Every decision here was a fork the evidence could not settle on its own:
either it changed the architecture, or it traded cost against reliability.
Each entry gives the question as it was asked, the options offered, what
was chosen, and why the question existed at all.

Dates are 2026. The standing rule from 22 September — **safety and
reliability before cost, size and convenience** — is what several of
these answers turn on.

---

## 1. The harness connector

**Asked:** the specification (§7, deviation 1) called for the OEM 94-way
connector to be replaced by functionally-split sealed connectors plus an
adapter harness. The physical part had since been identified from
photographs of the machine. Keep the deviation, or put the OEM connector
on the board?

**Chosen: the OEM Bosch 94-way on the board, no adapter.** Spec deviation
1 is recorded as reversed.

**Consequence:** the board-side land pattern is now load-bearing and has
to come from a Bosch distributor. Neither part number returns a public
catalogue hit.

---

## 2. Four part-selection findings, approved together

These four were presented as recommendations and approved with one "ok"
on 22 September. Each one came out of choosing a part and discovering the
drawn circuit could not accept it.

### 2a. Where the injector and EGR current comes from — POWER-PATH

**The problem:** every high-current load (injector hold ≈10 A, EGR up to
6.4 A stall, relay coils) draws through connector pin 21, a 20 A fuse,
the EMI filter and a reverse-battery FET. The reverse-battery block sized
that FET for **5 A**, and the EMI filter block never stated a DC current
at all. A 22 µH inductor that does not saturate at 15–20 A is a large
part. Meanwhile pins 04 and 06 are separate battery feeds, fused 10 A
each in the loom, that this board uses only to measure voltage.

**Options:** move the injector and EGR supply onto pins 04/06 with their
own protection, leaving pin 21 for the electronics; or keep everything on
pin 21 and resize the fuse, filter and reverse FET for the full load,
with one contact carrying it.

**Chosen: move the high-current loads to pins 04/06.**
**Status: not yet implemented.**

### 2b. Boost converter stability while cranking — BOOST-SLOPE

**The problem:** the injector boost controller (TPS40210-Q1) adds a fixed
internal slope-compensation ramp. Its Equation 9 caps the current-sense
resistor at `VDD·L·fSW / (60·(VOUT + VD − VIN))`, and 80% of that is the
recommended value. The drawn 82 mΩ passes at 13.5 V (ceiling 99.7 mΩ) and
**fails at the 6 V cranking corner** (ceiling 44.9 mΩ, so 1.83× over):
the converter goes subharmonic exactly when the engine is being started.
Worse, a 330 µH inductor that saturates above the 2.2 A current limit is
not a part that exists in surface mount — the search found 330 µH parts
rated 0.2–0.4 A — and the buildable direction, a smaller inductor, lowers
the ceiling further (100 µH allows 30 mΩ).

**Options:** feed the controller's supply pin from the output side, which
is TI's own remedy and steepens the ramp, and use 100 µH; or accept
subharmonic operation while cranking.

**Chosen: feed VDD from the clamped output side, 100 µH.**
**Status: not yet implemented.** The finding is pinned as a check.

### 2c. Sensor-supply protection — SENSOR-PTC

**The problem:** the requirement asked for a resettable fuse of "R25 =
3.0 Ω nominal, −30% spread". Real PTCs are not specified that way: Bourns
MF-USMF020 gives a **range, 0.40–5.00 Ω**, and at its 0.40 Ω minimum it
contributes 14% of the series resistance the fault-current ceiling
assumed. Its hold current also halves from 0.20 A at 23 °C to 0.10 A at
85 °C, against a ≥200 mA requirement.

**Chosen (first pass): a fixed series resistor sets the fault ceiling and
the fuse only trips.** This was later superseded — see decision 4.

### 2d. The 3.0 V and 3.3 V input clamps — LOWV-CLAMP

**The problem:** fifteen zeners clamp the analog, speed and discrete
inputs. They were specified at 5 mA but sit at tens of microamps, where a
sub-5 V zener's knee is soft. The datasheet allows **10 µA of leakage at
only 1 V**. On a discrete input, 10 µA through the ~28 kΩ source is
0.28 V against a logic-high margin of 0.36–0.41 V while cranking; on an
analog input it is a signal-dependent error on the ADC. The simulation's
idealised sharp-knee zener hid all of it.

**Chosen: replace them with a low-leakage clamp to the 3.3 V rail
(BAV199).**
**Status: done for the analog and cam inputs; the discrete inputs needed
a different answer — see decision 3.**

---

## 3. The discrete switch inputs

**Why it came back:** BAV199 works where a clamp only conducts on a
fault. The five switch inputs clamp **continuously**, because a 6–40 V
input cannot be divided into logic range otherwise: reading a logic high
at 6 V needs a divider ratio above 0.385, and staying under 3.3 V at 40 V
needs one below 0.0825. Those do not overlap. Three candidate clamps were
checked and all three fail:

| Candidate | Why it fails |
|---|---|
| 3.0 V zener (BZX84-C3V0-Q) | soft knee at µA; the leakage that started this |
| Rail clamp (BAV199-Q to 3V3) | parks the pad at 3.9 V continuously — beyond the pin's rating, as an operating point rather than a fault |
| Shunt reference (LM4040-Q1 3.0 V) | draws ~35 µA of bias below breakdown (TI SNOS633N, Fig. 5-4); the cranking-dip input can supply only 20 µA, so the node sags to ~2.6 V with no guaranteed bound, and it fails outright on the pull-up channels |

**Options offered:** an NPN buffer per input; a stronger drive plus the
LM4040, with special cases for the two contact-to-ground channels; or a
dedicated automotive switch-detection IC on SPI.

**Chosen: the NPN buffer.** 10 kΩ into the base, 4.7 kΩ and 4.7 µF to
ground, a BAV199-Q diode holding the base against reverse battery, and
the transistor's collector as the MCU pin with a 10 kΩ pull-up to 3.3 V.
The pad now only ever sees 0–3.3 V, and nothing on it has to conduct
continuously.

**What the safety rule changed inside this decision:** the input resistor
was first drawn at 100 kΩ, which draws 0.11 mA through a closed contact
at 12 V. Non-gold switch and relay contacts at that current oxidise into
an intermittent open — a field failure, not a bench one. 10 kΩ gives
1.1 mA. Everything is checked at the worst corner rather than typical:
hFE 30 (datasheet minimum 60, halved for −40 °C) still pulls the pad to
0.03 V from a 6 V input, and a typical part at 125 °C stays off below a
1.3 V input.

**Cost:** the logic is inverted — pad low means input active — which is
recorded in the pin map, and the failure modes (transistor open reads
inactive, collector-emitter short reads active) are handed to the
firmware plausibility spec, because one polarity cannot make every
channel fail safe.

**Status: done.**

---

## 4. The 5 V sensor supply

**Why it came back:** the fix approved in 2c does not survive the real
source impedance. The sensor rail block modelled the 5 V supply as ideal
behind 0.1 Ω, but it comes from a **1 A buck**. So:

- a shorted sensor harness hits the buck's current limit long before any
  fuse trips; 5V_MAIN collapses, 3V3_MCU follows it, and the supervisor
  shuts the engine down. One chafed wire stops the machine.
- a sensor supply wire shorted to **battery** back-feeds 24 V into
  5V_MAIN through the fuse. No series resistor or PTC prevents that.

**Options offered:**

| Option | What it buys | What it costs |
|---|---|---|
| Tracker per group + overvoltage cut-off | each group survives a short to ground *and* to battery; other groups and the MCU are unaffected | about 8 more parts |
| Series resistor + PTC (as approved in 2c) | cheapest | a harness short browns out the MCU; a battery short back-feeds the rail |
| Trackers fed directly, with a lower main TVS | fewer parts | rewrites the whole board's transient design, and needs the alternator question (U16) answered first |

**Chosen: a tracking regulator per sensor group (TPS7B4253-Q1, whose
output survives −1 to +45 V and limits at 301–520 mA, tracking 5V_MAIN to
±4 mV) behind a 100 V-class overvoltage cut-off.**

**Why the cut-off is needed:** the tracker's input pin is rated 45 V and
this board's battery rail reaches 73.3 V for 50 µs on ISO 7637-2 pulse
2a. The cheap alternatives were worked through and discarded: a series
resistor with a TVS must clamp below 45 V, so it would conduct through
the entire 400 ms load dump (about 7 J), and any series resistance breaks
the 0.52 V of dropout headroom at a 6 V cranking input; an emitter or
source follower loses its own Vbe/Vgs at that same corner. A cut-off
instead disconnects for the 50 µs pulse, while a 47 µF capacitor holds
the sensors up (0.16 V of droop), and stays connected through the 40 V
dump.

**Status: not yet implemented.**

---

## Where these came from

Nothing here was found by reading the schematic. Each one surfaced when a
part number was chosen and its datasheet was checked against what the
drawing assumed — which is the same shape as every earlier finding in
this project: a document and an executable check disagreeing, with
nothing comparing them until someone did.
