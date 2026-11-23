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
**Status: built 8 October 2026** (`power_path.cir`, power_input sheet).

How it was built took three more questions, recorded in §5.

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
**Revised 8 October: 150 µH (Würth 7447709151), see §8.**
**Status: built 8 October 2026.**

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

**Status: built 8 October 2026.** The cut-off controller is the
**TPS48110-Q1** (see §7). `sensor_rail.cir` was rewritten around it.

## 5. How the POWER-PATH feeds are built (8 October)

§2a decided that the loads move to pins 04/06. These three questions
decided how. Each was asked with a recommended option, and each was
answered with it.

### 5a. Which loads go on which pin

**Asked:** how should the high-current loads be split across pins 04
and 06?

**Options:**
- **04 injector, 06 EGR** (recommended). Pin 04 feeds the injector hold
  switches and the boost converter input; pin 06 feeds the EGR
  H-bridge. Separate rails, separate protection: an EGR short blows
  only its own fuse, and no two fuses are paralleled. The injector
  averages well under its fuse rating (10 A only during holds of about
  1–3 ms), and the EGR's 6.4 A stall is inside its 10 A fuse.
- **04 + 06 paralleled** onto one high-current rail. Two fuses in
  parallel never share evenly: one blows first and dumps the whole
  load on the other.

**Chosen: 04 injector (`VBAT_INJ`), 06 EGR (`VBAT_EGR`).**

**Why it was a question:** U7, whether the OEM uses pins 04/06 as load
feeds at all, is still open. What makes them usable is the harness
itself: each pin has its own 10 A loom fuse, and a fuse is sized to
protect its wire.

### 5b. Reverse-battery protection on the new rails

**Asked:** what should provide reverse-battery protection on the two
new rails?

**Options:**
- **A P-FET per rail** (recommended). Same passive topology as Q1 on
  pin 21: a gate resistor to ground plus a zener, and no controller IC,
  so nothing has to be rated for the +73 / −48 V swing. It needs a
  lower-RDS(on) part, chosen from a retrieved datasheet, for 6.4 A
  continuous at a 105 °C board. The reversed-battery fault is removed
  rather than managed.
- **Fuse only.** No series element: a reversed battery drives current
  through the bridge FETs' body diodes until the 10 A loom fuse blows.
  No drop or heat in normal running, but it relies on the FETs
  surviving the fuse's clearing time — a managed failure, which the
  standing rule argues against.

**Chosen: a P-FET per rail — SQM120P10-10m1L** (Vishay doc 76943,
retrieved 8 October).

**Why it was a question:** pin 21's SQD50P08-25L could not simply be
copied. At the EGR's 6.4 A stall it would dissipate 1.3–1.8 W, which
takes a DPAK on a 105 °C board past its junction limit. The chosen
part runs at 139 °C (155 °C while cranking), checked in
`power_path.cir`.

### 5c. What stays on pin 21

**Asked:** which loads stay on pin 21, the filtered electronics feed?

**Options:**
- **Buck, relays, metering** (recommended). Pin 21 keeps the buck (all
  the electronics), the relay coils (~84 mA) and the metering valve's
  freewheel diode (0.86 A max; the valve itself is powered by the
  OEM's 20 A fuse 8F1). The boost controller's VDD stays on VBAT_PROT
  until BOOST-SLOPE moves it. Pin 21 then carries a couple of amps.
- **Buck only.** Move the relay coils and the metering freewheel onto
  the new rails as well. Pin 21 becomes electronics-only, but the
  relays and the metering valve then depend on the 04/06 fuses too.

**Chosen: buck, relays and metering stay on pin 21.**

**Consequence:** L101, L102 and F101 are unblocked and are now sized
for pin 21's reduced load, which still has to be stated as a number.

---

## 6. The toolchain on a new machine (7–8 October)

Setting the project up on macOS raised three questions. They are about
tools, not the circuit, but two of them decide which simulator and
which libraries the circuits are checked against.

### 6a. Which KiCad

**Asked:** the project was generated and verified with kicad-cli
7.0.11, but Homebrew offers only KiCad 10. Install 7.0.11 from
kicad.org, KiCad 10 from Homebrew, or skip KiCad for now?

**Options:** 7.0.11, which matches the verified netlists (recommended
at the time); KiCad 10, which is easier to keep updated, but its
netlist export and libraries may differ; or no KiCad.

**Chosen: KiCad 10** (10.0.7, installed by the owner).

**Consequence:** two things had to change for KiCad 10. `kicad-cli` 10
writes its netlist one token per line, so the parsers in
`check_netlist.py` and `assign_passives.py` were changed to accept
either layout. The results were identical to KiCad 7's, and
`passive_fp.json` came out byte for byte the same. The generators copy
library symbols into each sheet, so they are pointed at **KiCad
7.0.11's symbol library**, downloaded separately. With it, an
unchanged sheet regenerates identically apart from UUIDs. KiCad 10's
library would have changed every symbol on every regenerated sheet.
That library choice was not put to the owner; it follows from this
answer.

### 6b. Which ngspice

**What happened:** Homebrew's ngspice 47 failed three blocks that pass
on the original machine. `injector_turnoff` and `boost_converter`
never finished, and `metering_unit_pwm` missed by 3 %. The suite also
stalled at random. Fixes for all three were found: a ramp on an on/off
charger model, a step-size cap and a time-weighted average. But the
random stall remained.

**The owner's position:** first, that the circuits must work on the
latest version too. Then, after the random stall: build ngspice 42
from source rather than spend more time on 47.

**Chosen: ngspice 42, built from source** into `~/opt/ngspice-42`. The
committed suite passes 24/24 on it unchanged (25/25 with
`power_path`).

**Still open:** the suite does not pass on ngspice 47 for the three
causes above. Upgrading the simulator is a change that needs the whole
suite re-run (`docs/HANDOFF.md` §2 and §5).

### 6c. Keep the ngspice 47 fixes or not

**Asked:** with 42 passing the committed code, revert the 47-specific
edits to the netlists, `run_sim.py` and `ngrun.py`, and commit only the
setup changes?

**Chosen: revert.** The 47 fixes are not in the repository; §6b
records what they were.

## 7. The overvoltage cut-off in front of the sensor trackers (8 October)

§4 chose a tracking regulator per sensor group "behind a 100 V-class
overvoltage cut-off", and named an LTC4368-class controller as the
candidate. Its datasheet had never been retrieved. Retrieving it, and
looking for an alternative, turned the candidate into a choice.

### What the part is for

The three sensor regulators (TPS7B4253-Q1, one per group) survive at
most **45 V** on their input. This board's battery rail reaches
**73.3 V** for about 50 µs on ISO 7637-2 pulse 2a, a standard automotive
surge test. So the regulators need a fast automatic switch in front of
them:

- normally **on**, passing battery power through;
- above about 45 V it switches **off** within a few microseconds, and a
  47 µF capacitor after it keeps the sensors powered meanwhile;
- when the surge has passed, it switches back **on**.

It is a small controller chip driving one power transistor. It must
stay **on** through the 40 V load dump, which lasts 400 ms, far longer
than the capacitor could bridge.

### The question

**Asked:** which overvoltage cut-off controller should feed the three
sensor trackers?

The first time it was asked, the options were given only as datasheet
figures, and the owner replied that they could not decide between two
part numbers. The question was then explained as above, with this
comparison:

| | **TPS48110-Q1** (Texas Instruments) | **LTC4368** (Analog Devices) |
|---|---|---|
| Survives | 100 V | 100 V |
| Switches off in | 2.6–4 µs after the threshold | under 8 µs |
| Automotive-qualified (AEC-Q100) | **yes**, Grade 1 | **no**: C, I and H grades only (H = −40 to +125 °C) |
| Around it | a few more parts: charge-pump capacitor, unused current-sense pins tied off | simpler, 10 pins |
| Datasheet | SLUSEE5E (April 2026), from ti.com | Rev A, read through a mirror because analog.com timed out |
| Extra check needed | a 60 V/µs limit on how fast its input may rise | — |

**Recommended: TPS48110-Q1.** Electrically, either would do the job.
The deciding point is qualification. AEC-Q100 means the chip has passed
the automotive industry's stress tests for temperature cycling,
vibration and lifetime. Every other IC on this board has it, and the
LTC4368 would have been the one exception, on the part that protects
the sensor supply. The standing rule puts reliability before cost and
convenience.

**Chosen: TPS48110-Q1** ("ok use the recommended one").

**Consequences:**

- **Slew limit:** the input slew rate on pulse 2a's edge has to be
  checked against the 60 V/µs limit. The `sensor_rail` rewrite does
  that.
- **Threshold window:** the OV threshold must sit above the 40 V load
  dump at its lowest tolerance, and trip early enough that the
  regulators' input stays under 45 V. That includes the rise during the
  controller's 2.6–4 µs reaction time. The window is narrow, and the
  `sensor_rail` rewrite pins it.
- **The switch transistor** is the board's existing 100 V N-FET,
  IPD90N10S4-06, so there is one part number fewer to buy.

**What the simulation then showed.** Pulse 2a was applied through the
real pin-21 filter. The trackers' input peaks at about **22 V**, nowhere
near 45 V, at every corner. TI's own inrush network does most of that:
the 22 nF from gate to ground holds the FET's gate, so the FET can only
follow the surge up to its gate voltage. The OV comparator then opens
it fully once the rail passes 40.5–42.1 V, and that timing turned out
not to be critical. The 60 V/µs slew limit is met by feeding the
controller's supply pins through 100 Ω and 22 nF, which gives 4.9 V/µs.
The 47 µF hold-up is enough even aged to 33 µF with all three trackers
at their limit. One thing it showed about the rest of the board: with
the filter inductor not saturated, the clamp node reaches **76.6 V**,
not the 73.3 V `transient_clamp.cir` reports. Every part there is
100 V class, and the figure is now a check.

### A limit this design does not remove

The trackers' outputs survive −1 V to +45 V, so a sensor supply wire
shorted to battery is survived at 24 V (jump start) and at 40 V (load
dump). A short to battery **at the same time as** a pulse 2a surge
(73.3 V) would exceed it. That is a double fault, and it is recorded
rather than designed out.

## 8. The boost inductor, revisited (8 October)

§2b approved two changes to the injector boost converter: feed the
controller's supply (VDD) from the clamped output side, and use a
100 µH inductor (Würth 7447709101). Building it showed the 100 µH part
does not fit every rule.

### What the inductor and its sense resistor have to do

The TPS40210-Q1 measures inductor current through a small sense
resistor, and that one resistor sets two things:

- **Stability.** TI's Equation 9 caps the resistor at 80 % of
  VDD × L × fSW / (60 × (VOUT + VD − VIN)). Below it the converter is
  stable; above it, it goes "subharmonic" and oscillates at half its
  switching frequency. The worst corner is the 6 V cranking dip.
  Feeding VDD from the boost output raises VDD from about 5 V to about
  32 V while cranking, which is the whole remedy.
- **The current limit.** The controller cuts each cycle when the
  resistor's voltage reaches 120–180 mV, a 1.5 : 1 spread over
  tolerance and temperature. The limit has to sit high enough never to
  trip in normal running (TI's Equation 49), and low enough that in a
  fault the inductor does not saturate badly.

### The first question

**Asked:** with the approved 100 µH inductor, all three rules cannot be
met strictly. Allow the fault current limit to reach the inductor's
softer 30 % saturation point, or find a bigger inductor?

**The owner's answer:** "150 µH inductor comes in size 10x10x4 SMD
package."

**Checked against Würth's own datasheets:**

- **7447714151, 10 × 10 × 4 mm:** 150 µH, Isat 1.4 A typ. It cannot
  work. Normal cranking peaks at about 1.14 A, so TI's rule puts the
  current limit's minimum near 1.8 A and its maximum near 2.7 A. The
  part would saturate in normal running, not just in a fault.
- **7447709151, 12 × 12 mm:** 150 µH, Isat 2.7 A (10 %) and 3.3 A
  (30 %) typ, in the **same footprint** as the approved 100 µH part.

### The second question

**Asked:** which boost inductor?

| | 100 µH 7447709101 (as approved) | **150 µH 7447709151** |
|---|---|---|
| Sense resistor | 50 mΩ | 62 mΩ |
| Current limit, min–max | 2.4–3.6 A | 1.9–2.9 A |
| Limit max vs 10 % saturation | 16 % over | 7 % over |
| Limit max vs 30 % saturation | 5 % under | 14 % under |
| Stability margin (Eq. 9, 80 % rule) | 1.07× | 1.30× |
| No false trip while cranking (Eq. 49) | 1.27× | 1.07× |

**Recommended and chosen: 150 µH, Würth 7447709151, with a 62 mΩ sense
resistor.** It has more stability margin and less fault-current
saturation, in the same footprint. This revises the 100 µH in §2b; the
VDD-from-output remedy stands.

**Why neither choice is strict:** the 1.5 : 1 spread of the current-
limit threshold means the limit's maximum is always 1.5 × its minimum.
The minimum has to clear normal cranking current, so the maximum lands
above the first softening point of any inductor this size. Partial
saturation during a fault is not damaging: the controller still cuts
the current every cycle.

### How it was built

- **VDD from the output.** A follower off the 100 V rail gives VDD
  34.3–45.0 V. It is 12V_GATE's circuit with a 39 V zener (BZG03C39,
  same Vishay family as the 36 V clamp): a PZTA42-Q pass transistor,
  2 × 3.3 kΩ collector resistors, and a PMBT3904-Q limiting at
  11.6 mA. A follower off a 100 V rail needs that protection whatever
  it feeds. If VDD shorted, the follower would otherwise burn.
- **Start-up from the battery.** The old 220 Ω feed became a 180 Ω
  start-up path, with its 36 V clamp, into a Schottky (SS20PH102,
  already on the board). The Schottky stops the follower pushing about
  0.1 A back into the battery rail. 180 Ω, not 220 Ω, buys back the
  Schottky's drop: VDD is 4.77 V at the 6 V cranking dip, against the
  4.5 V start threshold.
- **Found while building it:** the oscillator's timing resistor
  returns to VDD, and TI specifies the frequency −20 % / +7 % across
  VDD. Equation 9 scales with frequency, so the stability check has to
  use −20 %. At that corner the 150 µH design keeps 1.12×. The 100 µH
  design would have failed outright (42.9 mΩ against its 50 mΩ). The
  choice in this section was the right one for a reason nobody had
  seen yet.
- **Stated, not hidden:** the switch FET's datasheet gives only a
  typical gate charge. At twice that, start-up margin falls to 17 mV.
  Until the output passes about 36 V, the controller runs from the
  battery feed with a shallow ramp, so subharmonic operation is
  possible for the first milliseconds of a cranking start, not in
  running.

---

## 9. The three capacitors that are not ceramic (8 October)

Every chip capacitor on the board is a multilayer ceramic, packaged
automatically by `assign_passives.py`. Three are not, because each needs
something a ceramic cannot give: a lot of capacitance at high voltage, or
a controlled internal resistance. They were left open until now.

| Ref | Job | Chosen |
|---|---|---|
| C313 | bulk on the MCU's 3.3 V supply | KEMET T599D157M006ATE025, 150 µF polymer tantalum, **plus R306, 22 mΩ 1 %** in series |
| C211 | holds the sensor supply up while the cut-off is open | Chemi-Con HHXC630ARA470MHA0G, 47 µF 63 V hybrid polymer, 8 × 10 mm |
| C401 + C420 | the injector's 100 V energy tank | **two** Chemi-Con HHXC800ARA820MJC5G, 82 µF 80 V hybrid polymer, 10 × 12.5 mm, in series = 41 µF, 160 V |

All three are AEC-Q200, surface-mount, and rated to 125 °C or higher.
Chemi-Con figures are from its 2026 catalogue (CAT. No. E1001A); KEMET's
from the part's own specification sheet.

### The idea behind all three: ESR

Every real capacitor has a small resistance in series with it, its
**ESR**. In wet aluminium electrolytics it rises steeply in the cold,
because the liquid inside thickens: typically 4–10× at −40 °C. A
**polymer** or **hybrid polymer** capacitor replaces most or all of that
liquid with a conductive solid, so its ESR barely moves. Chemi-Con
guarantees the HXC series' impedance at −55 °C is **at most twice** its
20 °C value. That one property is why all three choices are polymer
types.

### C313 — the bulk capacitor needs a *minimum* resistance

`mcu_pdn.cir` showed the bulk capacitor's ESR is not just a loss but
the damping for a resonance between the regulator and the capacitor. Too
little ESR and the supply rings; too much and it stops filtering. The
requirement (`PDN-BULK`) was therefore a band: 20–50 mΩ.

Two findings changed how it was met:

- **A capacitor datasheet gives a maximum ESR, never a minimum.** No
  part can be bought "at least 20 mΩ". So the floor is a separate
  resistor: 22 mΩ, 1 %, in series with a capacitor whose own ESR is
  25 mΩ at most. Even if the capacitor's ESR were zero, the pair is
  21.8 mΩ.
- **The ceiling was conservative.** A sweep of the same model shows the
  100 mΩ target holds from about 17 mΩ up to about 95 mΩ. The pair's
  worst high end is 72.2 mΩ: resistor +1 % plus the capacitor at
  KEMET's 2× end-of-life limit. Both ends pass at the smallest
  capacitance the datasheet allows (96 µF): 71.9 and 86.9 mΩ.

No question was put to the owner: the resistor is the only way to meet
a requirement both ends of which are needed.

### C211 — the sensor hold-up

When the TPS48110-Q1 opens for a voltage spike (§7), this capacitor
keeps the three sensor regulators running. The only new demands are a
voltage rating above the 40 V load dump the switch lets through, and a
capacitance that survives aging. The HXC part gives 63 V (1.58× over
40 V). At −20 % tolerance and −30 % end of life it is 26.3 µF.
`sensor_rail.cir` now runs its two worst corners at 26.3 µF, not the
33 µF it used before, and still passes: the rail's lowest point
is 9.2 V. Its ESR drop at −55 °C, aged, with all three regulators at
their limit, is 0.25 V. No question was needed.

### C401 — the injector tank, and the question

**What it does.** The boost converter can only trickle-charge this
capacitor. The capacitor alone delivers the injector's opening pulse:
18 A within about 40 µs, every injection. Its ESR is in series with the
injector. At 18 A, every ohm of ESR costs 18 V of push and slows the
opening.

**What the search found.** The tank sits at 100 V and reaches 104 V,
so it needs a part rated above 100 V. In the catalogues searched,
**no capacitor rated above 100 V publishes its ESR at all**, cold or
warm. Chemi-Con's 160 V parts give only a 120 Hz loss figure. Vishay's
specified-cold series stops at 80 V. Parts rated up to 80 V do publish
it, including HXC.

**Asked:** "C401 is the injector's 100 V energy tank … No single
capacitor rated above 100 V publishes its cold ESR. Which way?"

| | **2 × 80 V hybrid in series (recommended)** | 1 × 160 V wet electrolytic |
|---|---|---|
| Part | 2 × Chemi-Con HXC 82 µF 80 V, SMD | 1 × Chemi-Con GXF 51 µF 160 V, radial |
| ESR at −55 °C, aged | 224 mΩ, from the datasheet | not specified; estimated ~8 Ω |
| Time to 18 A at −40 °C, lowest rail | 45 µs (38 µs nominal) | never reaches 18 A at the estimate: 10.2 A at most |
| Cost and space | one extra can, 10 × 12.5 mm | cheapest, one part |

**The owner's answer:** "2× 80 V in series (Recommended)."

**Why it matters:** the injector controller ends the opening phase when
the current reaches its peak threshold. A tank that cannot push 18 A
through its own resistance never ends that phase, and the engine
misfires. That would happen on a cold start, late in the part's life,
which is the hardest fault to find in the field.

**How two in series work:**

- **Capacitance halves, voltage rating doubles.** 41 µF, 160 V. The
  sims now run at 41 µF. The droop per injection is 8.3 V (it was
  7.3 V). On the smallest stack the datasheet allows (−20 %, then
  −30 % aged) it is 14.9 V, so the rail never falls below 85.1 V.
  Every check that used the old 92.7 V low point now uses that figure.
  The gate-driver bank node rises to 104.1 V, since each hold-cutoff
  bump is 2.45 V on 41 µF. Recovery time does not change; it depends
  on charge, not capacitance.
- **The bleed balances the stack.** Two capacitors in series only share
  the voltage evenly if something forces them to. The 22 kΩ bleed that
  `BOOST-BLEED` already required is now 2 × 11 kΩ, one across each can
  (R401, R435). With the worst leakage mismatch the datasheet allows,
  each can settles at 52.4 V on an 80 V part. The first charge from
  0 V is the worst moment: it splits by capacitance alone, so 71.0 V
  can land on one can. That is 1.13× under its rating. Total bleed
  current and power are unchanged.
- **Ripple:** the injection pulses plus the charger's switching current,
  counted as if it never stopped, are 1.06 A rms against 2.1 A rated at
  125 °C.

All of it is executable arithmetic in `run_sim.py` under
`boost_converter`, beside the converter's own datasheet checks.

---

## 10. A filter on each new supply feed (8 October)

POWER-PATH (§2a, §5) moved the injector and EGR currents onto connector
pins 04 and 06. That was right for current and heat, but it took the
board's two noisiest loads away from pin 21's EMI filter. Each new feed
had only its reverse FET and 4.4–8.8 µF of ceramic capacitors. The
question was whether that is enough to meet the radio-interference
limit this project designs to. The limit is CISPR 25 Class 5, the
strictest automotive class (research memo 06), the same target pin 21's
filter is held to.

### What makes the noise

Both loads switch large currents on and off many thousands of times a
second, straight from the battery wire:

- **Injector hold.** After the 100 V opening pulse, each injector is held
  open at about 10 A by switching the battery on and off ("chopping").
- **EGR valve motor.** Driven by PWM: full battery on and off, up to 6.4 A
  at stall.
- **Boost converter input.** A smaller, smoother 150 kHz ripple.

Each on-off edge sends a spray of harmonics down the harness. A radio
receiver near the wiring would hear it, and the standard limits how
much is allowed.

### What the model found

New block `feed_emi.cir` reproduces CISPR 25's measurement: the
standard 5 µH / 50 Ω test network (LISN), 200 mm of harness, then the
board. `run_sim.py` adds up each load's harmonics against the Class 5
limits, band by band, with the peak and average detectors.

| | Worst point against Class 5 |
|---|---|
| VBAT_INJ as drawn | **33 dB over** |
| VBAT_EGR as drawn | **48 dB over** |
| VBAT_INJ with the filter | 17.7 dB under (12.2 dB under with aged capacitors) |
| VBAT_EGR with the filter | 9.3 dB under |

48 dB is about 250 times too much voltage. No layout trick closes a
gap that size; it needs a filter.

### The filter, per feed

- **Coilcraft XAL1510-103**, 10 µH, rated 16 A for a 20 °C rise.
  Between the reverse FET and the loads.
- **Two 82 µF / 80 V hybrid capacitors** (the same Chemi-Con HXC part as
  C401) on the load side. These supply the chopping current, so the
  inductor only carries the average.
- **Two dampers:** another HXC each, in series with a 0.68 Ω resistor.
- The existing 2 × 2.2 µF ceramics now sit on the connector side, which
  makes it a two-capacitor filter.

Both feeds get the identical circuit: one parts list, one layout block.

**Why the dampers.** An inductor and capacitor together form a resonant
circuit, here near 3 kHz. Two of the loads on the injector feed, the
boost converter and the hold-current loop, try to draw *constant power*.
To the filter that looks like a negative resistance: about 0.94 Ω at a
9 V cranking dip with a hot injector coil. If the filter's own impedance
peak is higher than that, the supply can oscillate. Undamped it peaks at
1.24 Ω. With the dampers it peaks at 0.64 Ω, even with end-of-life
capacitors, a margin of 1.47×. The damping is a plain resistor, not a
wet capacitor's internal resistance, because that rises about 8× at
−40 °C (§9), exactly when cranking makes it matter.

**Why this inductor.** The Würth 10 µH alternative saturates at 8.8 A
typical and is rated only to 75 °C ambient. The Coilcraft part saturates
at 26 A and is rated to 165 °C. Its one limit is 55 V across the
winding. The model puts ISO pulse 2a through the filter: at most 48.7 V
across it, 1.12× inside. In return the filter swallows most of pulse 2a,
so the feed's loads see at most 28.7 V, where VBAT_PROT sees 73.3 V.

### A requirement this puts on the firmware

The hold chopping and the EGR PWM frequencies have not been chosen; they
are firmware. Harmonic strength in the radio bands grows with switching
frequency, so the filter was sized at **25 kHz**. At 50 kHz the EGR feed
would be 1 dB over. **Both must stay at or below 25 kHz.** That is
above hearing, which is the usual reason for choosing about 20 kHz
anyway.

### What it costs, and what would change it

Two inductors (15 × 16 mm), eight hybrid capacitors (10 × 12.5 mm) and
four resistors: 14 parts, roughly US$15–20 a board. No question was put
to the owner. Without the filter the board fails Class 5 by 33–48 dB,
and the only alternative is a looser emissions class. That is the
owner's call. A stationary genset has no car radio, so a lower class may
be defensible, but it is not this log's decision to make. If the owner
relaxes the class, these filters can shrink.

**Decided 12 October 2026: the owner keeps CISPR 25 Class 5.** The
filters stay as designed. The PCB layout is held to Class 5 practice
too: tight switching loops, an unbroken ground plane, and filters
placed at the connector. The layout guide carries this.

**Limits of the model.** Like `emi_filter.cir`, it covers differential
mode only. Common-mode noise, both wires moving together against the
chassis, needs a layout to model. The 100 ns switching edges and the
in-phase sum of harmonics are deliberate worst cases.

---

## 11. Firmware on the PC first (10–11 October)

The hardware was complete to schematic, but no firmware existed. A
competing team already runs firmware on their board, with an Arduino
faking the engine signals. The question was how to catch up without
waiting for our own PCB.

### The choice

The control software is written as **plain C that touches no hardware**
(`firmware/core/`). It runs on the PC against a **simulated engine**
(`firmware/sim/engine.py`). The same C files later run unchanged on an NXP
S32K148 evaluation board, and after that on our own board. Every control
and safety function is proven first on the PC, where a mistake costs
nothing.

All the firmware sees is one table of numbers (`ecu_io` in `ecu.h`). The
inputs are sensor voltages and switch states. The outputs are injection
commands, the metering-valve duty, the watchdog pin and the CAN messages.
The firmware has four entry points: start up, a crank tooth arrived, a
cam pulse arrived, and one millisecond passed. The simulator fills the
table and reads it back, and the S32K148 port will do the same from its
pins. Injection is given as **"start at time T, for D microseconds"** per
cylinder, which is what the chip's timer executes. That keeps the
simulator's time step coarse without making the fuel amounts coarse.

### What the firmware does

- **Reads the crank wheel.** A 60-2 wheel has 58 teeth and a gap where
  two are missing. The gap shows up as a tooth period more than 1.5×
  the one before. Two gaps 58 teeth apart mean "synchronised". The cam
  pulse, once per two revolutions, says which revolution has cylinder 1
  firing.
- **Injects** once per cylinder per cycle, 5° before top dead centre. It
  schedules at least 1° ahead, so the start time is never already past.
- **Governs speed.** It holds 1500 rpm, or falls 4 % from no load to
  full load when the droop switch is closed. On reaching 400 rpm the
  setpoint **ramps up at 500 rpm/s** rather than jumping, explained below.
- **Holds rail pressure** at 1000 bar by driving the metering valve,
  treated as normally closed: more duty, more fuel flow. See the final
  review below.
- **Checks every sensor.** One that stays out of range for 100 ms raises
  a fault code. From the first moment it goes out of range, its last good
  value is held.
- **Shuts down and latches.** Above 1650 rpm (checked on every tooth),
  on loss of the crank signal, or on ignition off. It stays shut down
  until the ignition is cycled. The trip cancels any injection not yet
  started.
- **Talks J1939 to the DSE4522:**
  - engine speed every 20 ms
  - coolant temperature every 1 s
  - oil pressure every 500 ms
  - active fault codes every 1 s

### What the simulator proved

Eleven scenarios, run with one command
(`.venv/bin/python firmware/sim/run_sil.py`), all pass in 36 s:

| # | Scenario | Result |
|---|---|---|
| 1 | Start | synchronised in 116 teeth; 1500 rpm by 5 s; peak 1534 rpm |
| 2 | 0 → 20 kW load step | dips to 1449 rpm, back within ±15 rpm |
| 3 | 20 → 0 kW load rejection | peaks at 1547 rpm, well under the 1650 trip |
| 4 | Droop switch | speed falls 3.8 % (want 4 ± 1 %) |
| 5 | Runaway (stuck injector) | trips at 1650.6 rpm; no new injection after |
| 6 | Crank signal lost | shuts down 50 ms later, fault SPN 636 |
| 7 | Ignition off | shuts down with no fault code |
| 8 | Coolant sensor unplugged | fault SPN 110 FMI 3 after 1.0 s; engine keeps running |
| 9 | CAN timing and content | every message on time to the ms; speed within 0.1 % |
| 10 | Rail pressure | within 1.6 % of 1000 bar at full load |
| 11 | Watchdog | WDI falls every 10 ms |

There are also 46 unit tests on the separate pieces (`make -C
firmware/sim test`).

### What an expert review caught

Halfway through, a separate reviewer acting as a diesel-ECU firmware
specialist read the code. Every finding was reproduced as a failing test
before it was fixed. The ones worth knowing:

- **The start nearly tripped overspeed.** On reaching 400 rpm the speed
  loop asked for 1500 at once, fuel hit its limit, and the engine peaked
  at 1647 rpm, 3 rpm short of the trip. The ramping setpoint brought the
  peak down to 1534.
- **A crank-sensor noise spike read as overspeed.** One extra edge in
  mid-tooth made the speed read 1700 rpm. An edge arriving in less than
  half a tooth's time is now ignored, because no engine accelerates that
  fast.
- **A cancelled injection could still fire.** The cancel did not change
  the sequence number a timer driver watches. Now it does.
- **A hot engine looked like a shorted sensor.** With the placeholder
  coolant sensor, 0.2 V is a real 129 °C. That would have been flagged
  as a short and replaced by a harmless 90 °C. The coolant short
  threshold is now 0.1 V.
- **A stray cam pulse shifted everything by a revolution.** The engine
  would have injected on the wrong stroke. A cam pulse in the wrong
  revolution now stops injection until the next one agrees.
- Smaller fixes:
  - a timestamp 1 µs out of order read as signal loss
  - an out-of-range sensor's raw value was used during the 100 ms debounce

### What the final review caught

After all ten steps, a second reviewer read the whole branch. Again,
each finding became a failing test before it was fixed.

- **The metering valve's polarity contradicted the safety design.** This
  firmware spec had assumed a normally-open valve. The parent spec's trip
  module stops fuel by *cutting the valve's supply*, and that only works
  if the valve is **normally closed**: unpowered, no fuel. With a
  normally-open valve, cutting its supply opens it fully. The runaway
  run showed the rail climbing to 1695 bar after the trip. The firmware
  now assumes normally closed, to agree with the parent spec. Polarity is
  a single constant (`METER_NC`), and shutdown always commands the closed
  position. **The real valve still has to be identified.** If it is
  normally open, the constant flips *and* the trip module's contacts must
  move to the injector supply.
- **A stray edge before cranking blinded the decoder for 30 s.** The
  noise filter compared every tooth with a stale 30-second "period". After
  any pause longer than 50 ms, the decoder now starts afresh.
- **A 1 ms ignition flicker cleared a latched trip** while the engine was
  still turning, and the ECU restarted it. The latch now clears only after
  the ignition has been off for 500 ms with the engine stopped.
- **The speed reading could drop to 0 for one tick** if a tooth arrived
  just after the tick read the clock. That doubled the fuel demand for a
  moment. The time comparison is now signed, as it already was in the
  decoder.
- **Scenario 5 could not tell an edge-checked trip from a late one.**
  With the per-edge overspeed check deleted, it still passed. It now
  checks that the ECU is shut down on the very edge it first reads above
  1650 rpm, and that rail pressure falls after the trip. With the check
  deleted, the scenario now fails.

### Choices made while building

- **Signal-loss timeout of 50 ms, not 100.** The scenario requires
  shutdown within 100 ms. At 400 rpm the longest normal gap between
  edges is 7.5 ms.
- **Watchdog kicked every 10 ms.** This settles the open item on the MCU
  sheet. The TPS3850's window (its SET0/SET1 straps and CWD capacitor) has
  to accept a 5–20 ms kick period. That is well inside the 26.67 ms
  cylinder interval the spec requires.
- **Tuned gains.** These are placeholders until real engine tests:
  - speed: 0.5 mg/rpm proportional, 2.0 mg/(rpm·s) integral
  - rail: 0.002 duty/bar proportional, 0.01 duty/(bar·s) integral

  The gentler of the two passing sets was kept. A real engine has delays
  this model lacks.
- **A stray cam pulse or a noise edge** does not stop the engine. A
  single spike should not shut down a genset.

### What is assumed, and how to change it

Each assumption is a single named constant in a header, marked
`assumed` or `calibration`:
- the 60-2 wheel and cylinder 1 TDC at 90° after the gap
  (`CRANK_TDC1_DEG`)
- firing order 1-2-3
- start of injection, 5° before TDC
- the injector flow law
- fuel at full load, 34 mg (sets the droop)
- every sensor's volts-to-units table (`sensors.c`)

The engine model's constants are guesses for a 3-cylinder genset diesel,
also marked. When the real engine's figures arrive, each is a one-line
change, and the scenarios say at once whether the control still holds.

### Out of scope, and next

Not done yet:
- injector current regulation (that lives in the driver chip)
- pilot and post injections
- real calibration maps
- EGR control

The next step is the S32K148 evaluation board with an Arduino generating
the engine signals: the competitor's setup, but with control logic that
is already proven.

---

## 12. Logs a production ECU keeps (11 October)

This ECU goes into a production genset that runs for months at a time.
Until now, everything the firmware knew disappeared at power-off. A
technician arriving at a stopped set would have found nothing.

### Four records

All four live in one **persistent image** of about 3 KB. That fits the
S32K148's 4 KB emulated EEPROM.

- **Fault memory.** Up to 16 faults, kept after they clear. Each has an
  occurrence count, the first and last time it was seen, and a
  **snapshot taken the first time**:
  - speed
  - load
  - fuel
  - rail pressure
  - coolant
  - oil
  - battery
  - state

  It answers "what was the engine doing when this happened?"
- **Event log.** The last 64 of:
  - power-ups and their cause (a watchdog reset is a firmware hang
    caught in the field)
  - ignition on and off
  - crank, run and shutdown, with the reason
  - faults set and cleared
  - stored-fault clears
- **Counters.**
  - ECU powered time and engine hours
  - starts
  - trips by cause
  - watchdog resets
  - time at each quarter of rated load
- **Trip recorder.** For the last two overspeed or crank-signal trips:
  speed, fuel, rail pressure and state every 20 ms, from 2 s before to
  1 s after. Normal ignition-off stops are not recorded, or the daily
  stop would overwrite the last real trip.

### Surviving power loss and flash wear

- **Two copies.** The host keeps two copies of the image and writes them
  alternately. Each copy carries a sequence number and a CRC-32, and at
  power-up the newest good copy wins. A power cut in the middle of a
  write loses that one save, never the history.
- **Sealed copy for the host.** The image the host writes is a sealed
  copy, so the 1 ms tick can keep updating the live one during the write.
- **Saves only from the main loop.** A save happens on:
  - a fault's first occurrence
  - every trip (1 s after it, once the recording is complete)
  - entering shutdown
  - each start
  - every hour of running

  The rate is capped at one save per 10 s, except a trip.
- **Wear.** That is about 30 saves a day, roughly 110 000 per copy over 20
  years. The S32K148's storage has to be chosen for that, in the
  dev-kit spec.

### Reading it

Over J1939, which the DSE4522 and standard service tools understand:
- **stored faults (DM2)**
- **clear stored faults (DM3)**
- **fault snapshots (DM4)**
- **engine hours**: on request, and broadcast every 10 s until we know
  whether the DSE asks for them (U4)

The event log and trip recorder need a laptop service tool over CAN
(UDS), which belongs in the dev-kit spec. Until then, the simulator reads
them straight from the image.

### The watchdog needs the main loop now

Until now the 1 ms tick pulsed the watchdog on every pass. A main loop
hung while interrupts still ran would have kept the watchdog happy
forever, which is exactly the failure a window watchdog exists to catch.
The tick now pulses only if the main loop has checked in within 50 ms.
If the loop hangs, the pulses stop, the TPS3850 resets the processor, and
the next power-up logs a watchdog reset.

### Three more fixes for long running

- **The millisecond counter wraps every hour by design.** It used to wrap
  after 49.7 days, which would have broken message timing once in the
  field.
- **A lost crank tooth is logged as a crank-sensor fault.** It used to be
  logged as overspeed, because the missing tooth makes that edge's speed
  read high. The decoder also drops its speed history on any fault, so
  one bad edge can't raise a second, false overspeed.
- **A fault message too long for one CAN frame is sent whole or not at
  all.** It is never half-sent.

### What the tests caught while building

- **Faults read "active" after power-up.** A fault saved while active
  still read "active" after a power cycle. Load now marks every stored
  fault as previously active, because nothing is active until it is seen
  again.
- **Scenario 11 couldn't see the watchdog stop.** With the watchdog newly
  tied to the main loop, the simulator, which didn't run the main loop
  yet, stopped pulsing after 50 ms, and scenario 11 still passed. It now
  also checks that the pulses continue to the end.

### What the final review caught

A fresh reviewer, acting as an off-highway ECU firmware specialist, found
no critical defects. It did find four that would hurt in months of field
running. Each now has a test that failed first:
- **A loose sensor connector flooded the event log.** Every flicker logged
  "fault set" and "fault cleared", and in 10 s that pushed the overspeed
  record out. Each fault's set and clear is now logged once per ignition
  cycle, and ignition-off only after 500 ms off, so a bouncing contact
  logs nothing.
- **A service tool reading fault snapshots could silence the DSE's fault
  list.** Long multi-frame messages queue one at a time, and the tool's
  requests always won. The active fault list (DM1) now goes first.
- **A watchdog reset was never saved on its own.** If the operator
  power-cycled before anything else triggered a save, the evidence of the
  hang was lost. A watchdog-reset boot now requests a save, still under
  the 10 s limit, so a boot loop can't wear the flash.
- **A packet of a long message could be dropped** if the CAN queue was
  full at that moment. It is now retried 1 ms later.

### Proof

- **78 unit tests.**
- **15 scenarios.** The four new ones:

| # | Scenario | Result |
|---|---|---|
| 12 | Runaway, then power cycle | overspeed fault stored with its snapshot (1650 rpm), shutdown event logged, trip recording kept (last sample before the trip 1633 rpm, 50 after) |
| 13 | Power cut halfway through a save | reload takes the previous save; nothing else lost |
| 14 | Stored faults over CAN | DM2 returns the stored fault; DM3 clears it and leaves an active one alone |
| 15 | One lost crank tooth at 1500 rpm | shutdown, stored as crank sensor (636), not overspeed |

### Still open (dev-kit spec)

- **Storage choice.** Pick storage for about 110 000 writes per copy.
- **Laptop service tool.** It reads the event log and trip recorder over
  UDS.
- **DM3 acknowledgement.** Whether the DSE expects one (U4).
- **Interrupt masking.** Mask the tick during the sealed-copy step on the
  real chip.

### Addendum, 14 October: the Protect lamp

**The problem:** the DSE4522's configuration (`field-evidence-2026-09-18.md`)
treats the DM1 **red stop** lamp as a *warning* and shuts down only on the
**ECU Protect** lamp. Our firmware set red on its shutdown faults but never
Protect. So after our ECU cut the fuel for overspeed, the DSE would have
seen only the speed falling and shut down on *under-speed* (1310 rpm),
logging the wrong reason.

**Chosen:** a shutdown fault (overspeed, SPN 190; crank signal lost,
SPN 636) now sets **red and Protect** (DM1 byte 1 = 0x11). A sensor fault
sets amber only (0x04), so a bad sensor never stops the set through the
DSE.

**Proof:** three unit tests (79 in all): overspeed and crank loss each send
0x11; an open coolant sensor sends 0x04. All 15 scenarios still pass.

**Still to confirm on the machine:** that the DSE logs "ECU Protect"
rather than under-speed when our ECU trips. That's a commissioning check.

---

## 13. The board, prepared for hand routing (11–14 October)

**The question:** should the PCB be laid out here, or by a person? And
since the new ECU must fit somewhere on the engine, where does it go?

**Chosen (owner, 11 October):**
- **I prepare, a person routes.** The board file arrives with every part
  placed by block and every rule set. A layout engineer routes it by
  hand in KiCad 10.
- **The board goes in the old ECU's die-cast housing.** The housing is
  also the heat sink. So the outline, the screw holes, the cooling contact
  areas and the J1001 header all copy the old unit.

### What exists now

| Item | Where |
|---|---|
| The board, 379 parts, 373 nets, placed by block | `hw/ecu25kva.kicad_pcb` (KiCad 10) |
| Stack-up, computed widths, net classes, housing placeholders | `hw/pcb_rules.py` (tested by `hw/test_pcb_rules.py`) |
| The generator | `hw/gen_pcb.py`. On a routed board it updates only the rules |
| The check | `hw/check_pcb.py`. Footprints, nets, classes, widths, DRC: all pass, 499 connections unrouted (expected) |
| Guide for the person routing | `docs/layout-guide.md` (the bible's PCB Layout Guide) |
| What to measure on the old ECU | inspection brief, Group 6 |

### The decisions inside it

| Item | Choice | Why |
|---|---|---|
| Stack-up | 4 layers, 1.6 mm, Tg ≥ 170 °C; 2 oz outer, 1 oz inner; L2 a solid ground plane | Engine bay; high current on the outer layers; the plane is never cut |
| Track widths | Computed from current by IPC-2221, for a 20 °C rise. Never typed | The spec named IPC-2152; IPC-2221 has a formula and comes out wider, so it errs safe. 18 A → 5.35 mm, 6.4 A → 1.3 mm on 2 oz |
| Clearances | IPC-2221B, external, uncoated: 0.6 mm for anything from 31 V up (boost voltage; the EGR gates, which reach 52 V on a load dump); 0.2 mm for CAN and analogue; 0.15 mm for logic and low-voltage power on fine-pitch pins. Battery power at 0.3 mm is a **judgement**, not a table row: the table gives 0.1 mm up to 30 V | Safe even before conformal coating |
| Net classes | Ten: PWR_HI, RTN, PWR_LOOM, PWR, PWR_LV, HV100, HV100_SIG, CAN, ANALOG, Default | See below for the ones that differ from the plan |
| The EGR feed (pin 6) | Sized for its 10 A loom fuse, not the 6.4 A load: 135 % of rating (a blade fuse may carry that for up to 30 minutes, ISO 8820-3) = 13.5 A → 3.6 mm | Nothing on the board limits that feed below the loom fuse |
| Unclassified power nets | The check fails if any net touching a power part (power FET, power diode, inductor, fuse, milliohm shunt) has no class | A new power net can't silently get a thin trace |
| Pads inside one part | Exempt from class clearance (a custom rule) | A 0.5 mm-pitch chip can't meet a 0.3 mm class rule; that spacing is the maker's. The classes govern the copper the router adds |
| Single ground join | All high-current returns meet the board ground at J1001's battery-ground pins, and only there | Keeps injector and switching current out of the sensor ground (layout guide §4) |

**Three changes from the plan, found while doing it:**
- **The injector's 100 V nets carry 18 A, not 1 A.** The plan sized the 100 V class for 1 A. But the injector's peak current flows through the boost rail, the bank nodes and the low-side drains. So that class takes the 18 A width. A new class, **HV100_SIG**, gives the small nets that sit at boost voltage (gates, bootstraps, divider midpoints) the 0.6 mm clearance without a 5 mm default width.
- **Ground has its own class (RTN).** Ground was planned under the 18 A class, with its 0.6 mm clearance. That put 0.6 mm between every ground pin and its neighbour, which no fine-pitch chip meets. Ground, with the injector shunt tops, keeps the 18 A width at the default clearance. Anything at 100 V still gets 0.6 mm from its own class. The same reasoning gives 3V3, 5 V and the boost controller's pins the PWR_LV class at 0.15 mm.
- **The fused pin-21 path is 6.4 A class, not 18 A.** It sits behind the 5 A fuse F101. The injector's power comes in on pin 4.

### Placeholders, and what the measurements change

| Item | Placeholder | Settled by |
|---|---|---|
| Board outline | 180 × 130 mm | Group 6.1–6.2 |
| Mounting holes | 4 × M3, corners | 6.1–6.2 |
| Housing contact band | top 25 mm | 6.1–6.2 |
| J1001 footprint | 6 large + 4 × 22 at an assumed 2.5 mm pitch, through-hole, marked "DO NOT FABRICATE" | **6.3** |
| Battery-ground pins | 1 and 2, assumed. The schematic leaves them unconnected | 5.1, 6.4 |
| D806 footprint | SMA | the trip-loop pin, 5.2 |

When the measurements arrive, `HOUSING` and `REGIONS` in `pcb_rules.py`
change. Before routing, re-run the generator. After routing starts, move
the outline and J1001 by hand.

**One finding the owner should know.** The spec's placeholder outline was
160 × 120 mm, and **the parts don't fit on one side of it**. Packed, they
need about 15,300 mm². At 160 × 120, the power-input block alone had no
room beside the connector. The placeholder is therefore 180 × 130. If the
old housing's board is smaller, our parts go on **both sides**. That is
normal for an ECU, but it needs the housing's inside depth on both faces
(Group 6.1 asks for it).

**Two things the schematic doesn't have yet, which the layout guide reserves room for:**
- a common-mode choke at the power input and on each CAN pair (spec §6, needed for CISPR 25 Class 5)
- test points

**One KiCad trap.** kicad-cli 10 silently ignores a custom-rules file it
can't parse; KiCad 10 needs units on every number (`0mm`, not `0`). So
`check_pcb.py` confirms the rules file is the generated one before it
trusts the DRC.

---

## 14. Calibrate from the old ECU's own recording (14 October)

**The evidence:** a 35-minute XCP recording of the original Bosch ECU on a running 3-cylinder engine at 1500 rpm (`refs/field-evidence-2026-10-14.md`).

**Asked:** should the firmware take its numbers from it? **Owner:** yes, "we need it to work right."

**What changed:**

| Item | Before | Now | From |
|---|---|---|---|
| Metering valve | normally closed (`METER_NC 1`) | **normally open** (`METER_NC 0`): full duty stops flow | current falls as pressure rises; it rises to stop the engine |
| Injector law | 300 µs + q / (0.0009 √p) | **323 µs + q / (0.00191 √p)** | fitted to 20,473 samples, within ±6 µs |
| Start of injection | 5° BTDC fixed | **table on fuel**: 11.5° at 6.5 mg → 15.9° at 17 mg → 14.2° from 26.5 mg | the old ECU's own values, median per mg |
| Rail pressure | 1000 bar fixed | **table on fuel**: 827 → 1171 bar | the same |
| Droop | 4 % only with the droop switch closed | unchanged | the old ECU runs isochronous, and so does ours with the switch open |

**What it costs, and what is still open:**
- **The trip module must move.** With a normally-open valve, cutting the valve's supply gives *full* flow, so the trip removes no fuel. The trip has to cut the injector and boost supply instead. This is an **external wiring change, not the PCB**: the trip goes in series with the injector feed, pin 04. It is written up in spec §3 item 6 (14 Oct), with the field survey in inspection brief Group 7. If the module's own contact can't carry the 10 A feed, it switches a run relay that is energised to run. Not yet wired.
- **The valve's part number** is the last confirmation. If it turned out normally closed, `METER_NC` goes back to 1; both polarities are tested.
- **The tables cover 6.5–26.5 mg at 1500 rpm.** Above that, and at other speeds (cranking, the run-up), they hold their end values. Those parts need the real engine.
- **The old ECU dips 9.8 % on a load step,** at G2's limit. Our model shows 3.4 % on a bigger step, so it is probably optimistic. Commissioning has to measure it.

**Proof:** 80 unit tests, and 15/15 scenarios. The engine model now uses the measured injector and valve too. Scenario 10 checks rail pressure against the firmware's live setpoint (worst 2.3 % at no load, 1.3 % at full load).

---

## 15. A prototype board, buildable now (15–17 October)

**The question:** the production board waits on the Bosch connector and the old ECU's housing. Nothing has shown the design working. Can a board that sets both aside be built now?

**Chosen (owner, 15 October):** yes. Everything for it is in `prototype/` (spec `prototype/docs/spec.md`, plan `prototype/docs/plan.md`, bring-up guide `prototype/docs/bring-up.md`).

| Question | Owner's answer |
|---|---|
| What goes on it | **The full production circuit.** Its eight sheets are built by the production generators, unchanged |
| MCU | **STM32G474VET6**, cheaper and easier to get than the S32K148. The production MCU choice is revisited once the prototype works |
| Dev board or one board | **One board,** MCU soldered on. A WeAct STM32G474 module is bought separately, for early firmware only |
| Assembly | **Fab-assembled.** The files are fab-neutral; the fab is chosen at quoting |
| Routing | **Done here,** by script. The owner does not route |
| Connector and housing | **Set aside.** Pluggable 5.08 mm screw terminals, labelled with the production pin numbers |
| High-current copper (16 Oct) | **Pours carry the current.** 585 of the 640 power pads are narrower than their class width, so no track can meet the class at the pad. Each power net's power parts are joined by class-width pours; tracks to small parts on a power net may be pad-width |
| Board size (16 Oct) | **300 × 200 mm** ("you can use bigger board dimensions"). 220 × 160 and 240 × 180 were too congested to route the injector stage at full width |
| Pin necks (16 Oct) | **0.15 mm, inside a part's courtyard only.** 0.2 mm (the 2 oz minimum) does not clear between 0.5 mm-pitch pins; 0.2 mm everywhere else |
| Layers (16 Oct) | **Stay at 4.** L2 stays a solid ground plane, never cut; signals use F.Cu, In2 and B.Cu |

### What it adds to production, and only to the prototype

- **Test points** on every rail, the boost rail (marked HV), CAN, the crank and cam edges and the four current senses: TP1–TP24.
- **A boost-rail monitor** `BOOST_MON`: 2 × 499 k + 24.9 k, so 116 V reads 2.82 V.
- **A battery monitor** `VBAT_MON` on the MCU sheet: 120 k / 10 k.
- **A 2 × 10 bridge header** for the future simulator board.
- **USB-C, data only.** It does not power the board, so the MCU rail has one source.

### How the board is routed

- **`prototype/power_router.py`** routes the 29 power nets as class-width bars. It is a maze router on a 0.5 mm grid over B.Cu, F.Cu and In2. Nets negotiate for space (the PathFinder method) until no two overlap. Where a bar changes layer it gets a via array at 2 A per via. On In2, which is 1 oz copper, bars are twice as wide.
- **Freerouting 2.4.1** routes everything else. **It treats a KiCad pour as no obstacle** (in its own code, a DSN plane loads with `isObstacle=false`). So a first run routed signals straight across the power bars, which the refill would have cut. In its input each bar is now a fixed wire and each pour via a fixed via; they come out again after import. `test_router_sees_pours` guards this.
- **Ground reaches L2 through its own vias** (`gnd_fanout`), one per ground pad, so Freerouting never sees L2. It routes three layers; its vias come back through all four.
- **Freerouting leaves about 45 connections open** (run 12, 29 passes, 1 h 50 min). **`prototype/finish_router.py`** routes them, one at a time, with KiCad's DRC as the judge: anything DRC rejects comes out whole. What it needed, each found on a connection that would not route:
  - **A start anywhere on the end's copper island**, not only its centre point. Off a 0.5 mm-pitch pin's centre is the only legal start beside a 0.3 mm clearance net.
  - **Vias through a pour's interior**, with 1 mm of pour kept round the hole. A deeper bite into a pour's edge is allowed but priced as a 20 mm detour, and `necks()` judges it afterwards.
  - **A last pass 50 mm round the ends on a 0.1 mm grid**, for HSB_BAT_GATE: 115 mm across the injector pours.
  - **Rip-up**: other nets' tracks round the open ends, then along the line between them, are taken out; the open connection routes first, the rest after. Rounds that leave more open are undone.
  - **`tidy`** removes the vias and stubs rip-up leaves dangling.
- **Result (17 October): nothing unconnected, 0 DRC errors, schematic parity clean** but for D806's placeholder footprint. Freerouting started from 625 nets.
- **Proofs:**
  - `test_power_pours_connect`: with every track removed, every power part's pads are still joined, so no track carries load current.
  - `gen_board.necks()`: every bar keeps at least 3 of 5 sample points across its width filled, outside its own pads.

### Rules the routing needed (17 October)

| Rule | Why | Cost if wrong |
|---|---|---|
| **Pin escape:** inside a fine-pitch chip's courtyard, a PWR or PWR_LOOM track keeps the chip's own 0.2 mm pin gap to that chip's pads, not 0.3 mm. The 100 V classes and PWR_HI keep theirs | U203 pin 13 (VSNS) lies between OVC_BST and OVC_GATE on a 0.5 mm pitch: even a 0.15 mm track dead centre is 0.275 mm from them. The chip itself holds those voltages across 0.2 mm. **Production has the same pin** | A creepage review of the 7 chips (U101, U202, U203, U301, U302, U401, U701) |
| **Fine-pitch chips keep 1 mm clear** round their courtyard in placement | Run 9 left U401, U203 and U504 walled in by their own satellites | A placement rerun |
| **R503 is turned 180°** after packing | U504's gate-source resistor faced gate-down, source-up, against the driver's pin order: EGR_AH_G and EGR_HIGH_59 had to cross at 0.6 mm clearance, and EGR_A_VB was walled in | None: the same box |
| **Finishing tracks on power nets are 0.2 mm** | They reach small parts; the current rides the pours | None measurable |
| **A power net with no pour carries its own current on tracks** (`TRACK_AMPS`: 1 A on the 5 V buck's switch node and output, 0.05–0.3 A on the rest). Each track is IPC-2221 wide for that current on its layer. A net that would need more than 0.2 mm on In2 stays on the outer layers | Eight power-class nets have at most one power part, so the pour router gives them no bars. The 5 V buck's output ran 0.2 mm on 1 oz In2: 65 °C rise at the buck's 1 A, which a chafed sensor lead can hold (each sensor tracker limits at 301–520 mA). `test_track_power_widths` | A rerun if a load grows: the table is the budget |

### Found on the way

- **A production defect, fixed in `hw/`.** In the supervisor, the `~RESET` and `~WDO` pull-ups overlapped on the schematic. That shorted the TPS3850's reset and watchdog-fault outputs into one net. Fixed in commit 491f37e. `check_netlist.MUST_SEPARATE` now guards it.
- **That fix broke the watchdog kill (found in review, 19 October).** The TPS3850 asserts `WDO` on a watchdog timeout and never `RESET` (SBVS301B §7.3.6.3). Once the short was gone, a hung MCU no longer reset or killed the gates. **D302, a BAT54Q-7-F Schottky** (anode `~RESET`, cathode `WDT_FAULT`), puts the path back: `WDO` low pulls `RESET` to about 0.3 V. That is below Q301's 1.1 V minimum threshold, so `GATE_KILL` rises. `RESET` low leaves `WDO` alone. In production and on the prototype; `check_netlist` WDO_KILL guards it. **The cost:** the MCU is held in reset for as long as `WDO` is low, so `WDT_FAULT` no longer tells firmware which trip it was. No firmware reads it.
- **U606's library footprint** (Freescale 98ARH99066A) has a malformed courtyard. The prototype redraws it as a rectangle. **Production uses the same footprint** and passes the design-rule check only because of where it sits. Check it before production layout.
- **ST's datasheet DS12288 could not be downloaded** (st.com refused). The power-distribution check keeps production's 0.5 A load step: 70.3 mΩ cold and 78.5 mΩ warm against the 100 mΩ target. The STM32's real step is smaller.

### The cost to know before quoting

- **The stack-up is production's:** 4 layers, 2 oz outer copper, 1 oz inner. The pour widths are computed for 2 oz.
- **A 1 oz quote is not a drop-in.** The bars would carry about half the current.
- **300 × 200 mm with 2 oz outer copper** is outside most fabs' cheapest prototype tier. Expect to pay for size and copper weight, not part count.
- **95 pin necks are 0.15 mm on 2 oz outer copper.** Some fabs' 2 oz minimum is 0.15–0.2 mm: ask at quoting.
- **20 small islands of pour fill** are left floating (current-sense pours on In2, three on the ground plane). They carry nothing; a fab may ask about them.


## 16. A service link: bootloader, end-of-line record, underspeed warning (17–20 October)

**Prompted by** a friend's screenshot of a comparable production ECU's
firmware, a TargetLink model. It has a bootloader, an end-of-line write
and an underspeed fix. Ours had none of the three.

### The owner's answers (17 October)

| Question | Answer |
|---|---|
| Underspeed action | **Warn; the DSE decides.** The DSE has its own under-frequency shutdown; the ECU does not stop the engine for underspeed |
| Link | **Both.** USB on the prototype for quick iterations; CAN channel 2 in production |
| End-of-line scope | **The unit record**, locked once written. A factory output-test mode is later work |
| Protection | **Seed-key**, and the engine must be stopped |

### What was built

All portable C, tested on the PC (firmware guide §16). Spec
`docs/superpowers/specs/2026-10-17-service-link-design.md`.

| Part | Decision | Why |
|---|---|---|
| Protocol | A subset of **UDS (ISO 14229)**, the same on both links | A technician's UDS tester can read the IDs; `python-udsoncan` could replace our tool |
| Underspeed | Below 1350 rpm for 3 s: SPN 190 FMI 18, **amber lamp only**; above 1400 rpm for 1 s clears it | The DSE shuts down on the Protect lamp, which every SPN 190 used to light. A warning must not stop the set |
| End-of-line record | 84 bytes, two copies apart from the logs, trims applied to every input; none good means SPN 628 FMI 13 | A unit that skipped the line says so on the DSE's screen |
| Bootloader | Image header written **last**, magic last of all; never touches its own 32 KiB | A power cut anywhere leaves no valid header: the update is just run again. Tested by cutting the power at every write |
| Hardware check | The bootloader runs an image only if the record's hardware revision is in the image's range | A good image for another board revision stays in the bootloader |
| Engine stopped | OFF, WAIT or SHUTDOWN and no tooth for 1 s; an open session ends at the first tooth; an ECU reset is refused while it turns | A laptop left connected, or a generic tester's reset button, must never stop a running set |
| End-of-line "passed" | SPN 628 stays on until the record carries the passed stamp | A station that writes the serial and then aborts must not ship a unit running silently on default trims |

### Found on the way

- **The SIL engine's load was constant power**, so any overload stalled
  it in under 3 s, faster than the warning. A real alternator's regulator
  rolls the voltage off below about 47 Hz, so a resistive load's power
  falls with speed. The model now has that roll-off (`AVR_KNEE_RPM`, an
  assumption); scenario 16 settles near 1190 rpm at 30 kW.
- The spec's record size (88 bytes) was wrong: its own fields pack to 84.
- **The final review (20 October)** found an ECU reset accepted on a
  running set, a lost CAN flow-control frame that silenced channel 2
  until power-off, "stopped" reading "turning" after 36 minutes at rest,
  a partial record clearing SPN 628, USB served from the preemptible
  background, a save handshake that could lose a write, and the affine
  CRC-32 key. All seven fixed, each with a test that failed first.

### Risks

| Risk | What it costs | Answer |
|---|---|---|
| The seed-key secret is in every unit's flash | Anyone who reads one unit can compute keys for all | Acceptable for stopping casual writes. Signed images are the answer to tampering. (The first design's CRC-32 key was worse: it is affine, so one sniffed unlock gave keys for every seed. The final review caught it; the key is now SipHash-2-4) |
| A CAN update at 500 kbit/s | About 30 KiB/s: a 256 KiB image takes about 10 s plus the erase | USB on the prototype |
| The DSE's under-frequency settings are unknown (U4) | If the DSE ignores DM1 and has no under-frequency trip, nothing stops a set that sits overloaded | In the U4 questions |
| No rollback | A bad image that passes its CRC needs the previous one flashed | One application slot, by choice |
| **Still to write:** the chip layers | Flash, CAN, USB and reset drivers on the STM32G474 and S32K148 | The port contract, firmware guide §14 items 10–13 |

---

## 17. A simulator anyone can run (20 October)

**Asked for:** three simulators. (1) The firmware alone. (2) The prototype
board fed sensor values and faults over USB, its firmware using them in
place of its inputs. (3) The board on a bench rig that plays the engine.
Each runs live or from a script, and everything is traced in a browser.
This entry is mode 1. The owner's friend uses Windows: "it should be an
easy setup for him too".

| Question | Answer | Why |
|---|---|---|
| Language | **All Rust**: engine model, loop, server | One `.exe`, nothing to install. About 100 times faster than real time, against about 3 times for the Python model, so scripts run in seconds. The same model can later run on the mode 3 bench's microcontroller |
| The firmware | **Unchanged C**, built in, and loadable from the UI as a `.dll`/`.dylib`/`.so` | The simulator tests the code that ships. A loaded build is refused unless `ecu_abi_version()` and `ecu_io_size()` match |
| The UI | A web page served by the program itself, on 127.0.0.1 only | Works the same on every OS. `--share` lets a second PC watch, and then refuses firmware uploads, which run code |
| Scripts | `.seq` text: timed actions, `end`, and `expect` checks | Readable by someone who has never seen the code. A live session is saved in the same syntax, so it replays |
| The Python SIL | **Kept** as the firmware's gate | It checks what the script language cannot say: the sync edge count, watchdog periods, CAN intervals, the NVM image byte by byte |

### How it is checked

- The Rust engine model gives the Python model's crank edge times
  exactly, and speed and rail within 1e-6, over four open-loop profiles.
- The whole loop gives the Python SIL's 5 s start with identical states
  and speed within 1 rpm.
- All 16 SIL scenarios run as scripts and pass. CI runs them on Windows,
  macOS and Linux once the branch is pushed.

### Found on the way

- The droop scenario claims a 4 % drop, not a speed. Scripts gained one
  check, `mean change`, for it.
- A DM1 with two faults is sent as a multi-frame BAM. The Python SIL
  reads only single frames, so a second fault would have gone unseen
  there. The simulator reassembles them.
- Operating systems hand back an already-loaded library for the same path,
  so a rebuilt firmware uploaded under the old name would have run the
  old code. Every load is a fresh copy.

### Risks

| Risk | Answer |
|---|---|
| Loaded firmware runs with the user's rights | The UI says so; uploads are refused under `--share`. Only the simulator's own page may send it anything: the final review found that any web site the user visits could POST a library to 127.0.0.1 (no preflight for a plain body), so the Host and Origin headers are checked |
| The Windows `.exe` needing the VC++ runtime | The C runtime is linked in (`+crt-static`, `/MT`), so nothing is installed |
| The binary is unsigned | SmartScreen and Gatekeeper warn once; the guide says how to proceed |
| A live session keeps its whole trace in memory | About 300 MB per simulated hour; streaming to disk is the upgrade if long sessions matter |
| `sin` and `exp` differ in the last bit between OSes | Traces can differ slightly across machines; the checks' bands absorb it |

Guide: `simulator/README.md`. Spec and plan: `simulator/docs/`.

## 18. The Bosch pinout becomes the master (7–8 November)

**Asked for:** the board had been designed from KOEL's harness diagram
(GP3.8703.C4). The owner sent Bosch's terminal diagram for the ECU itself
(`T4.435.04.0.PR`, Bosch drawing 0 462 YU4 15D, "MD1CS162 KOEL CPCB4+ 3 cyl"),
and the two disagree on power. The owner's answers (7 November): this
project replicates the MD1CS162. The Bosch drawing applies to our
3GK550ETA4SR1, because the models it lists share the same sensors and
ratings. The "0 281 …" number on the old ECU is an access code and does
not matter. Then: **"use only Bosch pins"**, and **"go with Bosch"**.
The pin list is `refs/bosch-pinout-md1cs162.md`, read off a 400 dpi
render.

| Pin | KOEL diagram (what the board did) | Bosch (what it does now) |
|---|---|---|
| 21 | Permanent battery feed for the electronics | `I_S_WFLS`, the **water-in-fuel** switch, active high |
| 04 / 06 | Injector and EGR feeds, plus voltage sense | `V_V_BAT_1R/2R`, the main relay's contact, the board's **only supply**. 04 now also feeds the electronics chain |
| 50 | Main relay output, no special role | Closes the board's **own supply** relay |
| 71 | Ignition input | Ignition, and the **wake**: it closes the relay in hardware |
| 01 / 02 | Unknown, no power ground anywhere | `G_G_BAT1/2`, the **power ground** |
| 09 | "Synchronization ground", unassigned | `I_A_SYNC`, an analog input from the GCU |
| 14, 25 | Not shown | Diagnosis request; **stop / emergency switch** |
| CAN | 55/77 "channel 1" | 87/86 is Bosch's CAN 1 (1000 kbit/s, flashing and UDS); 55/77 is CAN 2 (250 kbit/s, J1939) |

| Question | Answer | Why |
|---|---|---|
| How the board comes up | **Pin 71 turns on a second FET on pin 50** (10k / 22k, 12 V zener): the relay closes in hardware, 04/06 come up, the MCU boots and holds the relay itself | With no permanent feed nothing else can close the relay before the MCU has power. Vgs 5.5 V at 8 V in, 12.0 V on pulse 2a, -0.7 V reversed (`main_relay.cir` A) |
| Where the electronics feed comes from | **Pin 04**, ahead of its own protection, beside the injector feed | 2.95 A of electronics plus 3.8 A RMS of injector stays under the 10 A loom fuse. A blown 04 fuse also stops injection, so losing the ECU with it costs nothing extra |
| Pin 50's turn-off clamp | **A TVS to ground** (SMAJ48CA), not a diode to VBAT_PROT | See "Found on the way" |
| The after-run | Ignition off: the firmware stops the engine, asks for a save, and **releases the relay only once the engine has stopped and the save is written**, at most 60 s | The board drops its own supply. Releasing early would lose the stop's record. The save goes through the 10 s rate limit, and the relay waits for it, so a flapping ignition costs no extra flash writes |
| The trip loop | **Removed.** The overspeed trip module opens the main relay's coil feed | It had no Bosch pin. Opening the coil drops the ECU, the injectors and the metering unit together, and the GCU sees the CAN go quiet |
| Pin 25 | An operator stop: SHUTDOWN, no DTC, no red lamp, latched until an ignition cycle. **Also in hardware since 10 Nov** (below) | Like the ignition. **Polarity as Bosch draws it** (contact to terminal 31 = stop), the owner's decision on 10 Nov; seen once at first power-up (bring-up step 6) |
| Pin 21 | Amber DTC, SPN 97 FMI 31, after 2 s; clears after 2 s dry | A warning, never a stop. 2 s each way so fuel sloshing past the probe does nothing |
| Pins 09 and 14 | Read and passed to the firmware; **no function yet** | Bosch's drawing names them but does not say what the GCU sends. 09 reads 0–10 V |
| CAN | Net names kept; the service link moves to **1000 kbit/s** | Renaming nets churns three sheets for nothing. The mapping is written on the connector sheet |

### Found on the way

- **A sneak path that would have held the relay in forever.** The relay
  driver had a flyback diode from the drain to VBAT_PROT. That was safe
  while the coil was fed from the board's own battery feed. Under Bosch's
  wiring the coil sits on Term. 30, always live. With the relay open, the
  coil and diode fed the "unpowered" board: 22.8 mA through the coil, 2.7
  times its release current, with the board at 9.1 V (`main_relay.cir` B).
  The relay could never drop out. Bosch marks pin 50 "not equipped with
  freewheeling diode": the diode belongs in the relay. The netlist check
  now fails on any diode from pin 50 to a supply.
- **The decoupling check had been passing on nothing.** KiCad 10's
  `kicad-cli` writes the netlist one element per line. The check's pattern
  expected KiCad 7's inline form, found no parts, and passed on "0 supply
  pins". It now parses either form, and fails if it finds none. It checks
  50 pins, all decoupled.
- **Two open items closed.** The power ground (since 19 September) and
  the trip loop's missing pin. The netlist check reports none open.

### Proof

- `run_sim.py`: 26/26 blocks. `main_relay` is new; `trip_module_sense`
  is retired with the loop.
- `check_netlist.py`: connectivity OK, 0 open items. Five new checks:
  GND on pins 01/02, the 5 A fuse on pin 04, pin 21 an input, no diode
  from pin 50 to a supply, and two drivers on pin 50 with one woken from
  pin 71.
- Firmware: the unit tests pass (seven new), as do the boot tests,
  16/16 SIL scenarios and the service tool. Scenario 7 now checks that the
  relay opens 22.6 s after ignition off: after the engine has stopped,
  and after the stop is saved. `ECU_ABI_VERSION` is 2.
- `check_pcb.py`: footprints, links, nets, classes, widths and DRC pass
  after `gen_pcb.py`. Schematic parity fails on the Windows machine this
  was done on, 198 entries, almost all pins with no net. It fails the
  same on the unchanged board (199), so it is the KiCad build, not this
  change. It passed on the macOS setup. **Found 9 Nov:** KiCad 10.0.6
  drops every pin on an auto-named net (`Net-(...)`, `unconnected-(...)`)
  from parity, and only those. `check_pcb.py` now checks exactly those
  pins against KiCad's exported netlist, and parity passes. A pad on the
  wrong net still fails.

### The prototype, brought up to it (8–9 November)

The routed prototype board was updated in place, not placed and routed
again (`prototype/gen_board.py`):

- **`migrate`** records what `sync` cannot decide on its own (`BOSCH_MIGRATE`):
  - `/VBAT_IN` becomes `/V_BAT_1R` with its copper. The same rename goes into the committed router inputs `build/power.json` and `build/prototype.dsn`, which the board tests read.
  - The trip loop's parts go.
  - U301, J1001, J1007 and F101 take the new pad nets. J1007 grows from 6 to 9 positions, with pin 1 kept in place.
  - **J1001-1 and -2 are joined by a 2.5 mm F.Cu link.** Both positions are pin 04 now, but their pours had belonged to two nets and did not meet.
  - It is safe to run again.
- **`sync` places the 30 new parts.** Grown from the MCU end, the first try put three inputs' front ends 90–150 mm from J1007. Placement now:
  - starts from the connector and works inward
  - ignores GND and the supply rails when choosing a neighbour
  - on a tie, prefers a part placed in the same run

  Every input's protection and divider now sits at J1007.
- **The three new inputs moved on the MCU:** water in fuel, diagnosis request and the stop switch went from PE7–PE9 to **PD8–PD10** (`stm32_pins.py`). PE7–PE9 are three neighbours mid-way along the bottom row, in the CAN lines' corridor. Routed there, PE8 was walled in, and so were three CAN lines and SENSOR_5V_MON. PD8–PD10 are free pins on the side facing J1007. The firmware reads them through `ecu_io`, so it does not change.
- **`gnd_stitch`** gives each new F.Cu ground pad that reached no via a via to the L2 plane. `pour()` does this for every part, but `sync` did not, so 5 pads lacked one (Q807, Q808, C808, D807, C616).
- **D806 is no longer a placeholder** (`proto_rules.PLACEHOLDER` and `PARITY_OK` are empty). The reference now names the water-in-fuel clamp, a BAV199.
- Routing: `finish` and `finish_pass` routed all 42 new connections. A `rip` stage clears a net's tracks before its pins move.

  The result: **0 DRC errors, 0 unconnected items, schematic parity clean** (KiCad 10, this machine).

### Pin 25 kills the gates in hardware (10 November)

**The owner:** pin 25 is the operator's force shutdown, pressed when the generator is not behaving properly. So it has to work when the firmware is what is misbehaving. Until now it reached only the firmware.

**The change** (`hw/gen_sheet_mcu.py`, `stop_kill()`, on both boards):
- Q301, the inverter that raises `GATE_KILL`, now takes its gate from `~RESET` through a 100k (R307; R314 on the prototype).
- A 2N7002BK (Q302) with its gate on `SW_STOP` pulls that gate low while the button is pressed. `GATE_KILL` rises and every injector, metering and EGR gate drops, with no firmware in the path.
- `~RESET` stays at 3.0 V, above the MCU's 2.31 V threshold, so the MCU runs on, sees the stop and latches SHUTDOWN. Releasing the button does not restart injection.

**Proven by:**
- `sim/blocks/stop_kill.cir`, at the worst-high FET threshold:
  - pressed: 11.9 V on `GATE_KILL`
  - a 1 kΩ contact still kills; 47 kΩ of harness leakage does not; it trips at 10.8 kΩ
  - 0.9 ms from press to kill
- `check_netlist` STOP_KILL, on both boards.

**Polarity:** the drawing's (contact to terminal 31 when pressed), chosen by the owner on 10 Nov. If the machine shows a normally-closed contact, this path and the firmware both invert.

### Still open

- **The Rust simulator** mirrors `ecu_io`. Its fields and ABI are
  updated, but there was no Rust toolchain on this machine to build it.
  CI will build it, and so will a `cargo` on any of the three OSes. The
  committed Windows `.exe` is the old build until then.
- ~~At the machine: whether the fitted main relay carries its own
  suppressor.~~ Closed 10 Nov. Pin 50 drives the main relay and 69 the
  buzzer relay (owner). Neither needs to know about suppressors:
  - Pin 50's TVS works with one in the relay or without.
  - Pin 69's flyback diode (D811) goes to the board's supply. That is
    safe because the buzzer coil is fed from the same main-relay line,
    as Bosch draws it, so there is no sneak path when the relay opens.
- **Pin 25's polarity: as Bosch draws it** (owner, 10 Nov 2026). The
  switch is the external stop/emergency button, and pressing it
  connects pin 25 to terminal 31. It is no longer a question for the
  machine; first power-up shows it (bring-up step 6).
- **Pins 09 and 14 (owner, 10 Nov):** they stay as an analog input
  (09, 0–10 V into the ADC) and a digital switch input (14, contact to
  ground), at their current ratings. What they do is configured in
  firmware later. Until then the firmware reads both and acts on
  neither, so neither can change how the engine runs.

## 19. The boost cannot run away; heat and coating (12 November)

**Asked for:** the owner asked what still bothered us, then for fixes
for the 100 V boost and for heat: **"fix this"**.

**Found: nothing stopped the boost in hardware.** The TPS40210 holds
99.7 V through 2 × 499 k into FB. If either resistor opens (a cracked
1206, a lifted joint), FB reads 0 V and the controller runs at maximum
duty. Its DIS/EN pin was tied to "on" through 10 k, and nothing else
stopped the rail before a 150 V part failed (FET, diode or the 160 V
capacitor stack). The production board doesn't measure the rail at all.

| Question | Answer | Why |
|---|---|---|
| The cutoff | **A 110 V zener (BZG03C110-HM3) from BOOST_100V, through 470 Ω, into DIS/EN**; the pulldown goes from 10 k to 470 Ω | DIS/EN is an active-high shutdown, 0.7–1.3 V, rated 10 V (TI SLVS861F §6.1, §6.5, §7.3.7). 470/470 puts the zener at 1.5–2.8 mA at the trip, near its 5 mA test current, so its 104–116 V range applies. **Trip 105.0–119.3 V** over both corners; with feedback open the rail is held at 119.3 V, dissipating 0.66 W in the zener (`run_sim.py boost_ovp`) |
| Above the trip | **A 5.1 V zener (BZX84-C5V1-Q) on DIS/EN** | Holds the pin at 6.2 V with the rail at 160 V, under its 10 V rating |
| The MCU's stop | **`BOOST_DIS`: PTD15 (production), PD14 (prototype), through 100 Ω and a BAT54Q into DIS/EN** | 2.1 V on EN at the MCU's 2.9 V minimum high, 4.5 mA. The Schottky keeps a low or Hi-Z pin from loading the zener's divider. Hi-Z at reset leaves the boost running, as before |
| Firmware | **Above 106 V for 20 ms: `boost_dis`, SHUTDOWN, red DTC SPN 520192 FMI 0**, latched to the next ignition cycle. The boost is also off in SHUTDOWN | With the boost off, 12V_GATE collapses and nothing can inject, so the stop is made explicit. 520192 is the first proprietary SPN: J1939 has none for an injector boost rail. Production has no rail channel (`v_boost_rail` 0), so there only the zener guards it |
| Passives at the fault peak | **BOOST peak 104 → 120 V** in `assign_passives.py` | Nothing changes size: the 0805s on the rail are rated 150 V |

**Heat.** The hot parts were sized against a housing the prototype
doesn't have: Q104 at 139 °C junction with the EGR valve stalled at
6.4 A, on a 105 °C board. The firmware had no EGR control loop, so it
had no stall limit either. **Now it has a stall guard.** Over 5 A for
1.5 s, the bridge coasts (`egr_off`: the valve springs shut) for 5 s
and an amber DTC is raised: SPN 2791 (EGR valve control), FMI 6. The
third stall holds it off until the next ignition cycle. EGR is never a
reason to stop the engine. Bring-up step 7 adds a 10-minute full-load
heat check with a 100 °C limit.

**Spacing.** Every 100 V net keeps 0.6 mm. That is IPC-2221B's B2 row
for an uncoated external layer up to 150 V, so it's fine on a bench.
Raising it to 1.0 mm would fail hundreds of places, and many of them are
inside the FET packages themselves, where layout can't help. So **the
board is conformal-coated before it goes on the engine** (acrylic or
silicone, connectors and test points masked). The bring-up guide says
so, and so does the layout guide for production.

**The prototype, brought up to it.** `migrate boost_ovp` refits R403
(10 k → 470 Ω) and U301 (PD14 now drives `BOOST_DIS`); `sync` places
the five new parts beside U401. Sync dropped R437 inside the
ISNS_BOOST pour (Q401's source to the 62 mΩ sense resistor), and its
first routing cut that pour in two (`test_power_pours_connect`). R437
was moved to the nearest clear spot, left of the pour, and the four
nets were re-routed in one pass. 26/26 prototype tests pass, with 0
DRC errors, nothing unconnected, and the fab files regenerated.

**ABI 3.** `ecu_io` gains `v_boost_rail`, `i_egr`, `boost_dis` and
`egr_off`. The Python SIL and the Rust simulator's copies are updated.
The simulator wasn't rebuilt (owner: "no simulator").

## 20. The application in Simulink and Stateflow, with generated code (13 November)

**Asked for:** "a complete state flow model in MATLAB Simulink that is
able to generate code, and the new generated code we should be able to
flash in our ECU". The owner left the how to us ("do the best you can").
Design: `docs/superpowers/specs/2026-11-13-simulink-model-design.md`.

| Question | Answer | Why |
|---|---|---|
| What the models own | **The application layer**: the engine state machine, governor, rail control, the two calibration tables, the injector law, the trip decision and the five timed guards. Twelve models | That is the logic engineers tune and review. Tooth decoding, J1939, UDS, storage and the bootloader are event- and byte-driven platform code, already tested, and stay C |
| How they plug in | **Drop-in components** behind today's functions (`gov_step`, `mode_cmd` ...), selected by `ECU_MODEL` | One model for the whole tick would either slow the per-tooth trips (overspeed, sync) to the tick or split one state machine between C and model |
| The state machine | **A Stateflow chart driven by commands** (IGN_ON, TOOTH, RUN_OK, TRIP, RESET) | The tooth interrupt and the tick both change the state. `ecu.c` had five places that wrote it; all five now ask the chart |
| The guards | **Five small charts**, each its own model (`mode.c` holds the hand-written reference, moved out of `ecu.c` unchanged) | They reset at different times (water in fuel only at power-up) and run at different points in the tick |
| Where constants come from | **The C headers and tables**, read by `model/ecu_params.m` | A calibration typed in two places drifts. The `.slx` files are built by scripts, like the schematics |
| Code settings | ERT, reusable functions, inlined parameters, single precision, ARM Cortex-M, shared utilities | Runs on the STM32G474 and the S32K148 alike; no `double` on a single-precision FPU |
| Which is the reference | **Both builds, for now** | The hand-written modules stay until the generated build has run on the engine |

**The proof.** Every unit test and all 16 SIL scenarios pass on the
generated build. A back-to-back test (`model/test/run_b2b.sh`) runs each
generated model against its hand-written original on millions of
random inputs; the six charts are run 3 million random ticks each,
reaching every outcome (84 boost trips, 143 EGR stalls, 46 after-runs,
every engine state). They agree exactly, apart from one or two units in
the last place in the two tables, where Simulink orders its
interpolation arithmetic differently. The closed-loop model
(`ecu_app`: the real component models with a mean-value engine) starts,
holds 1500 rpm, takes 20 kW with a 1444 rpm low and stops on pin 25 in
Simulink (`model/test/sim_ecu_app.m`).

**Found on the way:**
- The governor first came out one unit in the last place off. The
  compiler, not the model, did it: it fused `set + RAMP*dt` into one
  multiply-add in the hand-written C. With `-ffp-contract=off` both
  agree to the bit.
- Simulating the charts in Simulink caught locals read before they were
  first written, which the C tests could not see. They start at zero in
  the generated C either way, but every chart now says so.
- `python -m ziglang cc` swallows the compiler's error messages on this
  machine. Two silent failures (a duplicated helper across two models,
  a missing source file) came from that; `zig.exe` called directly
  prints them.

**What it does not do yet: run on the board.** The generated code is
part of the firmware image and is flashed with it, over SWD or the UDS
bootloader. But the STM32 chip layer (ADC, timers, CAN, USB, flash) is
still unwritten, for either build.

**14 November, closing what still bothered us** (the owner: "can we fix
any of these"):
- **The boost's silent clamp, and a dead boost.** The hardware zener can
  hold the rail at 105 V, below the firmware's 106 V trip, and nothing
  said so. A dead boost showed only as "won't start". Now: held over
  104 V for 2 s raises amber SPN 520192 FMI 16; under 80 V for 0.5 s
  while cranking or running raises amber FMI 18. Neither stops the
  engine. Both are in the C and in a new chart, `ecu_boostm`; the
  back-to-back test agrees on every tick.
- **The state machine owns its conditions.** `ecu.c` used to decide
  when the ignition counted and when an ignition cycle had finished; it
  now sends TICK every millisecond and the chart decides both. The
  Simulink closed loop lost the copy of that logic it carried.
- **One command checks everything:** `./verify.sh`.
- **A test that passed by luck.** The hour-counter test depended on the
  edge generator's leftover fraction of a microsecond from earlier
  tests: that bias decided whether the governor's integral drifted up
  or down over a simulated hour. Adding a test before it flipped it.
  Each test now starts the edge clock clean.

## 21. The prototype's chip layer (14 November)

The owner, after the 4-layer board was confirmed: "do the best you can".
So the STM32G474 side of firmware guide §14, in `firmware/stm32/`.

**Choices made, each the simplest that is correct:**
- **Toolchain: the project's zig**, already in `.venv`, compiling against
  musl's headers and linking freestanding (zig's runtime supplies
  `memcpy`, `logf`, `fmodf`). Nothing new to install. The Arm GNU
  toolchain was downloaded and its checksum matched, but running a
  downloaded compiler was refused on this machine; zig made it
  unnecessary.
- **Registers, not ST's HAL.** ST's device header and Arm's CMSIS core,
  pinned and vendored with their licences. ST's HAL sources were read
  for the message-RAM layout, the DMA request numbers and the clock
  sequence, not copied. USB is TinyUSB 0.20.0 (MIT), vendored.
- **Peak and hold by the ADC's own watchdog.** ADC1 converts the active
  bank's shunt about every 0.45 µs; its watchdog interrupt is the
  crossing. The comparators were the other way, but bank A's shunt pin
  (PA2) is not a comparator input. A pure-C sequencer decides, so the PC
  checks it against a coil model: the peak arrives in 37 µs (the circuit
  simulation says 38), the hold stays within 9–11 A. It also carries
  rules of its own: no peak in 60 µs, over 26 A, longer than 5 ms, or
  started late, and the injection ends.
- **Two timers for one clock.** TIM2 captures the crank and cam at the
  core's priority; TIM5, started on the same edge, holds the injection
  compares at the top priority. One timer has one interrupt priority.
- **Stored data in bank 2,** so writes never stall code in bank 1, and
  the end-of-line record's copies in separate pages, so b survives a's
  erase. Firmware guide §14 item 11 said "the last page": it is now the
  last two.
- **The bootloader erases lazily**, because the tool waits 2 s and a
  full erase takes 5. Bank-1 erases run from RAM, feeding the
  watchdog, because a 22–40 ms stall is longer than its window.
- **Transmit by back-pressure.** The chip layer takes from the front of
  `can[]`/`can2[]` what the 3-deep hardware FIFO accepts and leaves the
  rest, so a long ISO-TP reply is paced by the bus, never dropped.

**Found on the way:**
- PB6, CAN2's transmit pin, comes out of reset with the USB-C
  dead-battery pull-down on it. The firmware releases it first thing.
- The core gives the EGR bridge no position command (`ecu_io` carries
  only `egr_off`), so the bridge stays coasting.

**Checked on the PC (`verify.sh`):** 11 sequencing cases on the coil
model; every pin, AF number and ADC channel against ST's data; the
images (vectors, bank-1 code, RAM, no double-precision code); and the
real bootloader core accepts `app_signed.hex` and refuses it with one
bit changed.

**Not checked: anything on a board.** Placeholders to settle at
bring-up are in `firmware/stm32/README.md`: the peak and hold currents
(U5), the metering PWM frequency, the crank and cam edge, and the tick's
real duration (`tick_max_cycles`).

## 22. The whole ECU as one model, with buttons (16 November)

The owner sent two photographs of a production model-based ECU (dSPACE
TargetLink): a TRIGGERS block firing the tasks and interrupts into a
MODEL block, a "Set PGNs / SEND all PGNs" J1939 area, and Build, Clean,
Bootloader and J-Link buttons. They asked for the same for this ECU: "do
what is the best for the ECU".

**Decided: the model owns everything signal-level, C keeps what is event-
or byte-driven.** Two more component models, each proven bit-exact
against the C it replaces on 3 million random steps:
- **`ecu_sensors`:** the 5 V correction, the end-of-line trims, the NTC
  and linear transfer functions, and the debounced range faults
  (`sensors.c`).
- **`ecu_j1939`:** the data bytes of EEC1, ET1, EFL/P1 and HOURS
  (`j1939.c`). Sending them, the transport protocol, DM1/2/4 and the
  requests stay in C.

**`ecu25kva.slx`** replaces `ecu_app`:
- **TRIGGERS:** a Stateflow scheduler firing initialisation, a
  per-cylinder event and the 1 ms, 20 ms, 500 ms, 1 s and 10 s tasks.
- **MODEL:** function-call subsystems holding the 15 component models.
- **PLANT:** the engine, the rail and the sensor voltages.
- **Buttons:** `ecu_project.m` generates, builds, flashes (ST-LINK or
  J-Link), cleans, checks and simulates, with a PCB selector. Errors are
  shown in MATLAB.

Simulated closed loop with 16 checks: the SIL limits, the sensor chain,
the injection and the J1939 frames.

**To make this possible, the components lost their own rate.** Their
charts were fixed at 1 ms. Now every component is sample-time
independent and takes its task's rate. The regenerated C differs only
in its timestamps.

**From now on the `.slx` files are what you edit.** The `mdl_*.m`
scripts lay a model out from scratch and overwrite edits, so they are
for starting over. The back-to-back test is how a deliberate change is
caught and then carried into the C reference.

**Found on the way:** the generated `initialize` functions zero every
array they are given. Passing the live end-of-line trims to it would
have wiped them on every sensor reset. The glue gives it scratch arrays.

**The MATLAB here is an academic licence**, and every generated file
says so. The owner: education and testing first; the code is
regenerated under a commercial licence before any commercial use.

## 23. The 20 kVA set's cascade PID, carried over (16-17 November)

The owner sent the control diagram of the AG48 ECU, tested on a 20 kVA
genset: engine states → RPM setpoint → outer PID (speed) → position
command → inner PID (position) → PWM → solenoid valve → crankshaft. They
asked for it to be carried over, and for any mistakes to be corrected:
"use it all because the logic would be same".

**It does not map one-to-one, and that is the first correction.** That
engine has a fuel actuator with a position sensor; this one is common
rail (Bosch MD1CS162). Our governor's output is fuel mass, which the
injector law turns into a time, and there is no position to control. The
cascade's idea fits in three places, and all three are now in:
- **Metering valve: rail pressure → valve current → PWM.** The rail PI's
  output is now a current command, and a new inner loop
  (`actuate.c mu_step`, model `ecu_mucur`) feeds the battery voltage
  forward and closes on the coil current. This is what Bosch does: the
  old ECU's recording runs on a current setpoint, `MeUn_iSet`. Before
  this, a hot coil or a low battery moved the valve: the metering
  block's "fails both corners".
- **EGR valve: target position → position PID → bridge PWM**
  (`egrp_step`, model `ecu_egrpos`), on the valve's own position
  sensor, pin 37. The bridge was never driven before. The target table
  is zeros until the emissions calibration exists, so today the loop
  coasts, as before. The structure is ready.
- **Engine states → speed setpoint:** OFF, IDLE, OPERATING, STEADY
  (`spdst_step`, chart `ecu_spdst`). The governor gains an idle input.
  Warm-up idle is a calibration, `SPD_IDLE_MS`, and it is 0, so the set
  goes straight to rated speed. A genset whose DSE expects rated speed
  should not idle on its own; set it if your sets do.

**Corrections to the diagram as drawn, applied here:**
- **Derivative on the measurement, not the error,** and filtered. A D
  term on the error kicks the actuator every time the target steps.
- **Anti-windup.** The integral stops while the output is pushed into
  a limit. The diagram has none, and a wound-up integral overshoots
  when the limit releases.
- **The inner loop must be much faster than the outer.** The coil's 3 ms
  against a rail loop of tens of ms holds that; so does a position loop
  of tens of ms against a speed loop of seconds.
- **The comparators are differences, with the sign the actuator needs.**
  For a normally-open metering valve, more current means LESS fuel. The
  rail PI already has that sign; the diagram's "=" hides it.
- **Coast, don't brake, at a closed EGR target.** Driving into the
  closed stop stalls the motor and trips the stall guard; the spring
  closes the valve.

**The chip side.** The metering shunt carries current only while its
FET is on, so a free-running scan reads the coil current or zero at
random. TIM20's spare compare channel sits at half the on-time, and its
compare pulse triggers one ADC2 injected sample per PWM period. The EGR
bridge is TIM1 PWM, sign-magnitude, with EGR_EN high only while driving.

**Mistakes of mine, found by the checks:**
- **The SIL plant had no coil:** the valve shut the instant it was told.
  With a real 3 ms coil, scenario 5's "rail never above its value at the
  trip" was not physical. It now allows a fraction of a bar; a real
  build-up would be tens.
- **The hot-coil scenario's expected duty ratio was wrong:** 1.29 where
  Ohm's law gives 1.41. The check now computes it from the plant.
- **A Stateflow chart writes its outputs only in entry actions,** and
  holds them in the caller's storage the rest of the time. The new
  chart's glue passed fresh local variables, so between transitions the
  governor read an uninitialised "idle". Seven unit tests and five
  scenarios caught it on the model build. The back-to-back test did
  not, because it reuses its variables. The glue now owns that storage,
  as every other chart's does.
- **The Simulink plant fed the coil current straight back in the same
  step** (an algebraic loop). The ADC reads the current already flowing,
  so the measurement now comes from the coil's previous step.

**Proven:** all three models bit-exact with their C on 3 million random
steps; the governor too, with idle switching. A 17th scenario, a coil
25 % hot on a 12 V battery, holds the rail within 1.3 %. Unit tests
cover each loop and the states.

**ABI 4.** `ecu_io` gained `i_mu`, `i_mu_valid`, `egr_duty` and
`spd_state`. The Rust simulator's binding (`simulator/crates/sim/src/fw.rs`)
needs the same four fields and `ABI_VERSION = 4`. Until then it refuses
this firmware, saying so. It was left alone as asked.

---

## 24. The 20 kVA set's fault diagnoses, adapted (18 November)

The owner sent the 20 kVA genset's DSM sheet: a fault-diagnosis table with
SPN and FMI, detection conditions, debounce and healing times, and lamp
actions. They asked whether it helps, then said to continue. Transcribed,
mapped row by row and flagged in `docs/research/13-dsm-20kva.md`.

**It is the same kind of correction as §23.** The 20 kVA engine has a fuel
rack; this one is common rail. So its rack faults become the metering valve's
and the rail's, and the EGR rows carry over almost as written, because the
EGR hardware is the same kind of thing.

**What went in:** `firmware/core/diag.c` holds 11 conditions, every one
**amber**:
- **EGR (SPN 2791):** open load (/5), stuck open (/0) and stuck shut (/7),
  diagnosed only from 10 to 15 V.
- **Metering valve (SPN 1347):** open load (/5) and over current (/6).
- **Rail pressure:** not following its target (157/7).
- **Speed:** a high-speed warning at 1590 rpm (190/16), and turning on oil
  pressure with no crank teeth (190/8).
- **Oil pressure with the engine stopped** (100/2).
- **Battery:** high (168/16), and low while running (168/18).

Each condition has its own debounce and healing time (`diag_def`), stepped by
one Stateflow chart, `ecu_deb`, with an instance per diagnosis. It is the
19th component model, and back-to-back it is exact over four instances at
once.

**What did not go in, on purpose:**
- **The DSE keeps** oil and coolant shutdowns, fuel level, charging, crank
  attempts and the maintenance timers. The MD1CS162 has no pins for them, and
  "follow only Bosch".
- **No battery shutdowns.** A battery is no reason to stop a genset.
- **Only standard J1939 codes,** so the DSE4522 shows the right text. The
  sheet uses FMI 22 (which J1939 doesn't define) and the maker's own SPNs.

**The sheet's mistakes, not copied:**
- Speed sensor erratic as written fires at standstill.
- The battery and alternator shutdowns aren't limited to running, so they
  would trip during cranking.
- The battery warnings use the shutdown enables.
- Three EGR codes share one condition.
- Two resistance bands look like normal readings.
- A filter row has no variable.

**Found on the way:**
- **The lamp rule called every speed fault red except underspeed.** A
  high-speed warning would have lit red and set Protect, and the DSE stops on
  Protect. Red is now overspeed only (FMI 0).
- **The unit tests powered the ECU from 24 V,** stale from before the field
  evidence settled a 12 V system. They also held every sensor at mid-scale,
  which is a stopped engine with 500 kPa of oil and a coasting EGR valve half
  open. Both are real faults now, so the test rig reads 13.5 V, 0 kPa and the
  valve shut.
- **The metering valve runs out of authority at no load on a hot coil or a
  low battery.** The rail deviation diagnosis caught it in scenario 17: a
  12.5 Ω coil on 12.0 V reaches 0.96 A of the 1.35 A that closes the
  normally-open valve. From 4.2 to 8.8 s, at no load, the rail sits on the
  relief valve at 1800 bar against 827. The scenario only checked 14–16 s
  at 20 kW, so this was never seen. At 11 V a cold coil (1.1 A) does the
  same. **It rests on the 10 Ω coil, which is an assumption.** Bosch
  metering units are nearer 3 Ω, and then the authority is ample. The real
  metering unit's coil resistance settles it, so read it off the part or
  measure it. Scenario 17 now keeps it as evidence, and scenario 18 runs
  loaded.
- **The fault table held 8 active faults.** It now holds 16; DM1 sends
  more than one as a BAM.

**Proven:**
- Unit tests for the debounce, every condition and its gating, and four
  end-to-end cases, all on both builds.
- Back-to-back exact.
- Scenario 18: EGR stuck open, then a battery that stops charging. Both
  amber, nothing else stored, the engine never stops.
- 18/18 scenarios on both builds.

**ABI unchanged (4).** `diag` reads only fields that already existed.

---

## 25. The metering valve's coil, measured: 2.5–5 Ω (18 November)

The owner measured the set's metering unit (pin 88): **2.5–5 Ω**. Everything
had assumed 10 Ω, a class guess from before any part was known. Bosch
metering units are about 3 Ω, so this fits.

**What it settled.** §24 found the valve out of authority: a hot 10 Ω coil on
a low battery could not reach the 1.35 A that closes it, so at no load the
rail sat on the relief valve. With the measured coil the worst corner (5 Ω at
+125 °C is 6.91 Ω) on 11 V still reaches 1.6 A. Scenario 17 now runs that
corner and holds the rail within 3 % at no load and 1.3 % at 20 kW, with no
rail-deviation fault.

**What it changed:**
- **The current loop** (`actuate.h`). Nominal is 3.75 Ω. The current that
  closes the valve, 1.35 A (`MU_I_FULL`), stays an assumption and is now
  separate from the coil: it is the metering unit's own data, from its part
  number. Feedforward is command × 5.0625 V ÷ battery. The gains are scaled
  by 3.75/10 so the loop keeps its dynamics (KP 0.075, KI 7.5). The
  integral range is widened to 0.4 to cover 1.85–6.91 Ω. `ecu_mucur` is
  regenerated; back-to-back exact.
- **"Valve closed" is a current now, not a duty.** The trip and the reset
  set a raw duty of 1.0. That was 1.35 A in a 10 Ω coil, but in a cold
  1.85 Ω coil it is 7.3 A, or 8.6 A at 16 V. They now set the feedforward
  duty for the closing current (`mu_ff`).
- **The measurement is trusted only while it reads sane.** With 1347/5 or
  1347/6 active the loop runs on feedforward alone, so a sense chain that
  reads low cannot wind the duty up. Feedforward alone puts at most 2.74 A
  into the coldest, lowest coil. So the over-current line moves from 2.5 A
  to 3.0 A, above anything legitimate and inside ISNS_MU's 3.3 A range.
- **R501 must be rated at least 0.5 W** (`bom_requirements.md` MU-ISENSE):
  2.74 A is 0.37 W in 50 mΩ.
- **The circuit block** (`metering_unit_pwm.cir`) runs 3.75 Ω, 11.25 mH
  (keeping the 3 ms time constant, since the inductance is still
  unmeasured), 18.75 % duty, and corners at 1.85 Ω and 6.91 Ω. Two new
  facts came out of it:
  - Open loop gives 0.52 A, not Ohm's 0.675 A. The freewheel diode's
    0.7 V matters against only 2.5 V across the coil.
  - At 100 Hz the current touches zero every period and no longer averages
    like 1 and 10 kHz. 100 Hz is out; the firmware drives 1 kHz.
- **The electronics feed's current bound (pin 04; the check still said "pin 21" until §26) no longer adds the coil's freewheel current.**
  D501 returns it into VBAT_PROT and back to the battery, so it runs
  against the feed's draw. Adding it was the safe direction at 0.86 A; at
  2.5 A it would have failed the L101 heating check for a current flowing
  the other way. The reverse current is bounded separately (2.48 A, under
  F101).
- **The SIL engine** uses a 3.75 Ω coil and the 1.35 A closing current.
- **The Simulink whole-ECU plant** (`mdl_ecu25kva.m`) uses the same coil. Its check "current = duty × 1.35" only held for 10 Ω (where full duty was 1.35 A); it now checks current = duty × 13.5 V ÷ 3.75 Ω. 20/20.

**Still open:**
- The closing current (part number on the pump).
- The coil's inductance.
- **There is no fast hardware current trip on pin 88.** A stuck-on FET puts
  8.6 A through R501, and only the 20 A fuse ends it.

**Proven:** the metering block at all corners, the power block, unit tests on
both builds (the loop at both corners, half and full command), back-to-back
exact, and 18/18 scenarios on both builds.

---

## 26. The water-in-fuel sensor's load, and the main relay's contacts (21–22 November)

The owner sent two more values: the water-in-fuel sensor (pin 21),
**20–50 mA and 1–4.7 kΩ**, and the main relay, **5–10 A at 250 VAC / 30 VDC**.

**Water in fuel.** The two numbers can't describe one thing: 1–4.7 kΩ at
12 V passes 2.6–12 mA, not 20–50 mA. So they're read as the sensor's
**supply current** (drawn from the main-relay line, not the ECU) and the
**load its output wants** at pin 21. If the sensor's label says otherwise,
this reading is the one to revisit (`bom_requirements.md` WIF-LOAD).
The owner confirmed the part on 22 November, **Bosch F 002 H23 583**. Its
public listings give no electrical data, so the count of wires on its
connector (3 = active, as read; 2 = a probe to ground) is what settles it.

The standard input channel is about 10 kΩ once its transistor conducts: too
light. Pin 21 alone changes:
- **R818 goes 10k → 3.3k.** It is now a 1210: `assign_passives.py` sizes it
  for 24 V continuous across it, which is 0.16 W.
- **R819 goes 4.7k → 1.5k,** so the threshold stays where the other
  channels have it.

The sensor sees 3.4–3.6 kΩ from 9 to 16 V at −40 and +125 °C. An open
output reads dry, and 6 V reads water. `discrete_input.cir` has a new
branch, W21, that checks all of it. The routed prototype took the change
through a migration (`WIF_MIGRATE`, refit R818/R819), then `sync`,
`finish` and `fab`: 26/26 tests pass, 0 design-rule errors, 0 unrouted.
The production board was rebuilt; 16 parts of the discrete block repacked.
The firmware doesn't change: active high, 2 s debounce.

**The main relay is off-board, but what flows through its contacts is
ours.** Terminal 87 feeds pins 04 and 06 (10 A fuse each) and the
main-relay line. The block bounds, added:
- **8.83 A running.**
- **13.8 A with the EGR stalled,** for up to 1.5 s per try.
- The fuses behind it allow 20 A.

**A 5 A relay is undersized. A 10 A relay has 13 % margin running, is
1.38× over in a stall, and would weld before a fuse blew.** Requirement: a
12 V automotive relay of **30 A or more** (`bom_requirements.md`
MAIN-RELAY), checked in `check_main_relay`. The relay's coil resistance is
still needed; 160 Ω is assumed.
**22 November: the requirement is reversed.** The owner gave the part
number of both the buzzer relay and the main relay, **4H.865.27.0.00**. It
is a KOEL "2½-relay board, 12 V DC", with both as PCB relays. It is the
set's own part and the Bosch ECU runs with it, so it stays; the ECU is
what gets replaced. The 30 A relay becomes the fallback. What decides it
is a clamp-meter reading of terminal 87 on the running set; the ECU must
not draw more than the Bosch one did. If the margin is thin, the fix is
on the ECU's side: the EGR stall limit and time, and the inrush into the
bulk capacitors (`bom_requirements.md` MAIN-RELAY).

**Found on the way: the electronics feed's checks still said "pin 21".**
That was the KOEL harness reading. Since the Bosch pinout (§18) it has been
pin 04 (F101 sits on V_BAT_1R), and the labels now say so. The numbers were
always pin 04's.


## 27. The metering valve's closing current: 1.8 A, from Bosch's data (22 November)

The owner gave the metering valve's part number, **Bosch 0 928 400 820**
(it was already confirmed against the drawing on 10 November). There is
no public datasheet for that number. Published Bosch metering-unit data
(third-party service pages, the same family) gives:

| | Bosch family data | This firmware before |
|---|---|---|
| Coil resistance, 20 °C | 2.3–3.15 Ω | measured on the set: 2.5–5 Ω (§25) |
| Idle current | **1.38–1.43 A** | the valve closed at 1.35 A |
| Maximum working current | **1.8 A** | — |

**The 1.35 A assumed since §23 is below the published idle current,** so the
rail loop could not have reached idle current. `MU_I_FULL`, command 1.0
("closed"), is now **1.8 A**:
- `MU_V_FULL` becomes 6.75 V (1.8 × 3.75).
- The loop gains are scaled by 1.8/1.35, to keep the loop's dynamics in amps: `MU_KP` 0.1, `MU_KI` 10.
- `MU_INTEG_MAX` goes to 0.5. The hot 5 Ω coil at 13.5 V needs +0.42 of duty over the feedforward.

**What it costs:**
- **A hot 5 Ω coil (6.91 Ω) cannot reach 1.8 A below about 12.4 V.** The set
  charges at 14.5 V, so it only matters with charging lost. Then the loop
  saturates at full duty: 1.59 A on 11 V. That is tested in `test_core.c`
  and pinned in `check_metering_unit_pwm`. **The engine scenario found what
  it means:** at no load on 11 V the valve can't shut far enough, so the rail
  runs 95 % over its target. That leaves it to the pump's pressure-limiting
  valve, and 157/7 (amber) is stored; the engine keeps running. Scenario 17
  now checks that the rail holds on 13.5 V (within 3 %) and pins the 11 V
  case as evidence. Before, it ran only at 11 V. If the bench shows the real
  closing current is nearer idle than 1.8 A, the 11 V case goes away.
- **Feedforward alone** (once the measurement is distrusted, 1347/5 or /6)
  gives the cold 2.5 Ω coil up to 3.65 A at command 1.0. That is over the
  3.0 A line, and was 2.74 A before. Up to idle current it stays under the
  line.
- **The main relay's running load** goes from 8.83 A to **9.28 A**, and to
  14.2 A with the EGR stalled. A 10 A relay now has 8 % margin. The 30 A+
  requirement stands.
- **The SIL engine and the Simulink plant** close the valve at 1.8 A.
  `ecu_mucur` is regenerated.

**Still to confirm on the bench:** the closing current itself, and the
coil inductance, with the real unit on a current-controlled supply.


## 28. The crank speed sensor: Bosch DG-6-K, 0 281 002 214 (22 November)

The owner gave the crank sensor's part number. Bosch's sensor catalogue
gives the DG-6-K family's data:
- winding resistance 860 Ω ±10 % at 20 °C, rising 0.4 %/°C;
- inductance 370 ± 60 mH at 1 kHz;
- 20–7000 rpm on a 60-2 wheel, the same as this engine's;
- output 210 V peak at a 0.3 mm gap and 7000 rpm, and 170 mV at 1.5 mm
  and 50 rpm.

The design had assumed 20 V at 1500 rpm and 2 V at cranking. Scaled by
speed, the real sensor gives:

| | Real sensor | Design |
|---|---|---|
| 1500 rpm, tightest gap | **45 V** | 20 V assumed |
| 1650 rpm (the trip), tightest gap | 49.5 V | under the SMAJ48CA's 53.3 V minimum breakdown |
| Where the TVS starts to clip | 1777 rpm | clipping keeps the zero crossing, so no teeth are lost |
| Clamp current per leg at 1650 rpm | 4.6 mA | 4.7k per leg |
| 150 rpm cranking, widest gap | **0.51 V** | 2.6× the ±198 mV hysteresis |
| Slowest speed still seen at 1.5 mm | 58 rpm | |
| Coil at 1500 Hz | 3.6 kΩ | 1.7 % lost into the 100k bias |

**No circuit change.** The front end was sized for a signal 2.25× smaller
at speed, but its zero-crossing design doesn't depend on amplitude, and
every corner above passes. These are now checks in
`check_vr_conditioner`. The TVS note on the schematic still says "about
20 V at 1500 rpm"; its conclusion (48 V clears the trip) holds.

**Still worth doing on the machine:** the crank sensor's voltage while
cranking, cold. It confirms the real gap.


## 29. The cam (segment) sensor: Bosch Hall, 0 281 002 667 (22 November)

The owner gave the camshaft segment sensor's part number. Bosch's
aftermarket catalogue (2013/2014, "Hall speed sensor without cable") has
this exact number:
- supply: 5 V rated, range 4.7–18 V, 5.6 mA typical;
- output: open collector, sinks 0–20 mA, saturation ≤ 0.5 V, switching ≤ 1 µs / 15 µs;
- air gap 0.2–1.8 mm, speed 0–4500 rpm, −40 to +150 °C.

It is what `cam_frontend.cir` assumed from the pinout: a 3-pin, open
collector Hall sensor on 5V_SENSOR (pin 45). New checks in
`check_cam_frontend`:
- the 10k pull-up sinks 0.53 mA, 38× inside the rating;
- the saturated low (≤ 0.5 V) is under the pad's 0.99 V;
- the 22 nF filter delays the edge 93 µs, 0.84° of crank at 1500 rpm,
  which is irrelevant for a sensor that only picks the cycle;
- the cam turns at 825 rpm at the trip.

**One near miss, kept as evidence:** in `sensor_rail.cir`, a healthy
sensor group holds 4.69 V during a short on another group, at the
stacked cold corner. That is 10 mV under this sensor's 4.7 V minimum,
during a fault only. The nominal rail is 5.0 V.

**Open: how many segments the cam wheel has.** The firmware's decoder
(`crank.h`) expects one cam pulse per cycle. "Segment sensor" may mean a
wheel with several segments, typically one per cylinder plus a marker.
That changes the decoder, not the circuit.

**23 Nov (owner's crop of the drawing):** pins 3/2/1 to ECU 45/46/44,
the three wires twisted, as the circuit assumed. The crop doesn't give
the segment count, so the question stays open. It matters at the first
start: with several segments per cycle the decoder sees a cam pulse in
every revolution: `crank.c` resets the revolution count at every gap and
its phase flag flips on and off each turn, so it never holds a phase it can
inject on reliably. Bring-up: count pin 46's pulses over two crank revolutions
(scope, or the service tool) before the first start.


## 30. The rail pressure sensor: Bosch 0 281 006 425 (22 November)

The owner gave the rail pressure sensor's part number. Listings give it
as an **1800 bar** Bosch rail sensor, M18 × 1.5, cross-referenced to
Cummins 5.9 L parts (0 281 002 851, 5093112AA). That is the RDS4 family.
The firmware already scales the rail at 0.5–4.5 V = 0–1800 bar
(`sensors.c`), so the range now comes from the part; the 0.5–4.5 V curve
is still the common Bosch one, not this part's own data sheet. No change
in code, only the comment.

What it means in volts, on a 5 V supply:
- 0 bar (engine stopped) is 0.50 V;
- the rail table's 827 bar at no load is 2.34 V;
- its 1171 bar at full load is 3.10 V.

**A check on the set confirms the curve.** Ignition on, engine stopped:
pin 35 (signal) to pin 08 (its ground) should read about 0.5 V. Below 0.2 V or
above 4.8 V the firmware calls the sensor faulty (SPN 157 FMI 4 / 3).


## 31. The oil pressure sensor: Honeywell PX3AN2BF010BSDAX (22 November)

The owner gave the oil pressure sensor's part number, a **Honeywell PX3**
heavy-duty transducer. Honeywell's PX3 data sheet decodes it as:

| Code | Means |
|---|---|
| A | Metri-Pack 150 connector |
| N2 | 1/8-27 NPT port |
| B, F | brass housing, F-code O-ring |
| 010B | **0–10 bar** |
| S | sealed gauge |
| DA | **ratiometric 5 V, 10–90 % of supply (0.5–4.5 V), diagnostics on** |

Its other figures:
- 5 V ±0.25 V supply, 3.0 mA max, protected to ±16 V;
- total error band ±1.0 % FSS (±10 kPa) from −20 to 85 °C;
- response under 2 ms.

**This is what the firmware assumed:** oil at 0.5–4.5 V = 0–1000 kPa
(`sensors.c`), now from the part's own data sheet. **Its diagnostics mode
fits the fault checks.** An internal fault (EEPROM, bridge, low supply)
rails the output at 2.5 % (0.125 V) or 97.5 % (4.875 V), and so does a
lost ground. The firmware's limits, 0.2 V (oil) and 4.8 V, catch both, as
SPN 100 FMI 4 / 3. The new unit test `test_sens_oil_px3` checks the two
rails and full scale. No code change, only the comment.

On the set: oil is pin 80, with its own return on 36. Engine stopped, it
should read 0.5 V; the oil-at-rest diagnosis (100/2) uses 100 kPa
(0.9 V).


## 32. The coolant sensor: Bosch 0 281 002 209, and Bosch's NTC table (22 November)

The owner gave the coolant sensor's part number. Bosch lists it as an
NTC, **2.5 kΩ ±6 % at 20 °C**, which is the firmware's assumed 20 °C point.
Bosch Motorsport publishes the characteristic of its 2.5 kΩ NTC (NTC
M12-H), −40 to 150 °C, ±1.4 °C at 25 °C and ±0.8 °C at 100 °C.

**The firmware's beta law (β 3450) did not follow it at the hot end:**

| Real | 60 °C | 80 °C | 100 °C | 110 °C | 130 °C |
|---|---|---|---|---|---|
| Read with β 3450 | 60.7 | 81.7 | **102.8** | **113.9** | 135.9 |

This matters because the ECU sends the temperature to the DSE in ET1. With
the 20 kVA sheet's limits, 100 °C warning and 104 °C stop, **a real 101 °C
coolant would have stopped the set.** *Corrected in §35:* those are the
20 kVA set's limits. The 25 kVA set's DSE is set at 150 / 200 °C, so on this
set the ECU's own reading is what protects the engine. That makes an
accurate hot end matter more, not less.

**Fixed:**
- Bosch's 20-point table is in `sensors.c` (`ntc_t`, `ntc_r`), interpolated in ln(R).
- The Simulink `ecu_sensors` model reads it through `ecu_params`. Wrapped C tables are now read as one row.
- The model is regenerated and checked bit-exact against the C (b2b).
- The PC engine model and the Simulink plant use the same table.
- `test_sens_convert` checks the table's own points (−40, 0, 80, 100, 150 °C) and 104 °C to 0.1 °C, and both ends.

Below −40 °C the reading holds −40 until the open-circuit fault (above 4.8 V).
Above 150 °C it holds 150 until the short fault (below 0.1 V).

**The table is the family's, from Bosch Motorsport,** and matches this part's
20 °C value and tolerance. A check on the set: unplugged, the sensor's
resistance at a known coolant temperature, e.g. 323 Ω at 80 °C.


## 33. The boost sensor's NTC answers U2, and two faults on the sensor inputs (22 November)

The owner gave the boost sensor's part number, **Bosch 0 281 006 102**.
Bosch's catalogue lists it as a **DS-S3-TF**:
- 50–400 kPa absolute;
- 4.75–5.25 V supply, output load −1 to +0.5 mA, 1 ms response;
- −40 to 130 °C;
- **pin 2 an NTC**, pin 1 ground, pin 3 +5 V, pin 4 output.

Bosch's pinout wires pin 2 to ECU pin 79 (`I_A_BTS`) and pin 1 to pin 34.
**That answers U2:** the charge-air element is a bare thermistor. The
boost pressure scaling (50–400 kPa at 0.5–4.5 V) was already right.

Following it through the boards found two faults, both there since the
schematic was first drawn:

1. **The sensor grounds went nowhere.** SGND_34 and SGND_36 reached only
   the INA592s' −IN. Pin 34 (`G_R_BPS`) is the ground of the boost and
   coolant sensors, and pin 36 of the oil and EGR position sensors. Their
   supply current had no return, so those four sensors could not have
   worked. `sensor_differential.cir` modelled a grounded return the
   schematic did not have. Fixed: **R633 and R634, 0 Ω, tie them to GND.**
2. **The coolant NTC (pin 33) had no pull-up**, and nor would pin 79. Both
   were drawn as INA592 channels, which suit a sensor that drives its
   output. The firmware assumed a 2.49k pull-up the board did not have.
   - The INA592's +IN is 18k to ground, ±20 % absolute. Adding a pull-up in
     front of it would put an open sensor at 4.3–4.5 V, on top of a −40 °C
     one.
   - Fixed: **a 2.49k 0.1 % pull-up to 5V_SENSOR_A, then 100k/160k**. That
     is a 260k load the firmware takes out exactly (`NTC_LOAD`). An open
     sensor reads 4.95 V and −40 °C reads 4.71 V, so the common 4.8 V open
     limit separates them.
   - Two INA592s go (×5 → ×3). The ADC scaling for those pins goes from
     G = ½ to 16/26.

**Charge-air temperature in the firmware:**
- It is read from pin 79 with the same table (`sens_aux_step_1ms`).
- Its faults are SPN 105 FMI 3/4.
- It is sent to the DSE as J1939 IC1, SPN 105, every second.
- The channel sits outside the five-sensor arrays, so the end-of-line
  record keeps its format.
- **ABI 5** adds `v_bts` and `bts_c`. The Rust simulator lags, as before.
- In Simulink since §34 (`ecu_sensaux`).
- The table is the coolant's, Bosch's 2.5 kΩ NTC. It is the same Bosch
  family, but not confirmed for this part.

**Boards:**
- **Prototype:** migration `ntc` drops U602, U605 and their tails, and
  `sync` places the new parts. The old channels keep their reference
  numbers as "ghosts", so no other part renumbers.
- **Production:** rebuilt.

**Self-heating:** 2.5 mW in the NTC at 20 °C. That is about 1.4 °C in
still air, much less in coolant or moving charge air.


## 34. Fixes without new data: the metering valve when its reading fails, and the netlist gate (23 November)

The owner asked for everything fixable without new data to be fixed.

**The netlist gate now asks the questions §33's faults escaped** (`hw/check_netlist.py`, both boards):
- pins 34 and 36 must reach GND through 10 Ω or less;
- pins 33 and 79 need one pull-up to 5V_SENSOR, and no INA592.

Run against the design as it was before §33 (9ee3025), all four fail and
name the parts. **Pin audit:** every one of Bosch's 46 pins was checked (the other 48 are unconnected, as on the drawing)
against the netlist. The sensor returns 08, 30 and 44 go straight to GND,
the CAN channels match Bosch (55/77 J1939 at 250k, 87/86 service at 1000k),
and nothing else was found. **Open:** the EGR position sensor's type
(Padmini, pin 37). If it is a bare potentiometer, the INA592's 18k load
bends it by up to 6 %.

**The metering valve when its current reading fails** (prototype only:
production has no ISNS_MU). A new scenario, 19, cut the reading at 20 kW
on the cold 2.5 Ω coil. That found three things:

1. **The loop trusted an impossible reading for 500 ms**, the DTC's
   debounce, and wound its integral up. **The coil drew 3.7 A.** Now a
   reading that cannot be right stops being trusted after
   `MU_DISTRUST_MS`, 10 ms or three coil time constants. "Cannot be right"
   means driven with no current, or over 3 A. The DTC keeps its 500 ms.
2. **Open load was judged by duty above 20 %.** A cold 1.85 Ω coil runs a
   loaded set at 15 % on 14.5 V, so a dead reading there was never
   flagged. Now it is judged by the current the highest coil (6.91 Ω)
   would draw at that duty and battery: over 0.25 A, the coil must show
   current (`DG_MU_DRIVEN`).
3. **The fallback assumed a nominal 3.75 Ω coil**, so a cold one got up to
   twice its current.
   - Now, while the reading is trusted and above 0.9 A, the coil's
     resistance as the loop sees it (duty × battery ÷ current) is learned,
     with τ 1 s. Above 0.9 A the freewheel diode's drop is under 8 %.
   - The fallback scales its command by learned ÷ nominal.
   - With nothing learned (production, or a reading bad from power-up)
     it stays nominal. Assuming the lowest coil there would leave a
     nominal one unable ever to close the valve.

**Scenario 19 now:** 1347/5 is raised, the coil peaks at 1.43 A (never
over 1.8 A), the rail holds within 8.5 % at 20 kW, and the engine keeps
running. **19/19 scenarios** on both builds.

**Charge-air temperature in Simulink:** a new component model,
`ecu_sensaux` (20 models now), matches `sens_aux_step_1ms` bit for bit in
b2b, both FMIs included.

**Left for data, not design:**
- the EGR position sensor's type;
- the cam wheel's segment count;
- the main relay's measured current, which sets whether the EGR stall
  limit or the bulk-capacitor inrush needs to come down;
- the metering valve's bench closing current and inductance;
- the injector's coil resistance.

The INA592's AEC-Q100 status is a production question, deferred with the
production board (owner, 23 Nov: the prototype first).


## 35. The 25 kVA set's own settings replace the 20 kVA sheet's (23 November)

The owner: "everything we build now is for 25 kVA, but some data was given
for 20 kVA; make changes according to that."

**What came from the 20 kVA set:**
- **§23:** the cascade's structure only. Every gain, limit and coil value
  was derived for this engine, so nothing there changes.
- **§24:** the DSM sheet's thresholds. The 25 kVA set's own figures are in
  its DSE4522 configuration (`refs/GP3.314.01.0.PR-DSE4522-config.pdf`,
  20 kW rating). Compared:

| | 20 kVA sheet | 25 kVA set's DSE | Now |
|---|---|---|---|
| Battery high | 14.8 V, 5 s | 15.0 V, back 14.5 V, 10 s | **the 25 kVA's**, with the return |
| Battery low | 11.9 V running, 5 s | 9.5 V, back 10.0 V, 10 s | **the 25 kVA's**, running only |
| Underspeed | 1300 rpm stop | 1310 rpm stop; 45 Hz pre-alarm | 190/18 at 1350 rpm (= 45 Hz) already matched |
| Overspeed | 1650 rpm | 1710 rpm; 55/56 Hz | 1650 rpm trip (55 Hz), already under both |
| Speed high warning | 1590 rpm | none | 190/16 at 1590 kept: no 25 kVA figure, harmless |
| Low oil | 200 kPa, the DSE's | 99 kPa, the DSE's | the DSE's job, unchanged. 190/8's "oil above 200 kPa = turning" stays conservative |
| Coolant | 100 °C warn, 104 °C stop | **150 °C / 200 °C**: never acts | **the ECU protects**, see below |
| ECU lamps | | Protect → shutdown; red, amber → warning | as before |

**Coolant is the one that matters.** On this set the DSE's coolant alarms
never act, so the engine relies on the ECU's Protect lamp. The firmware had
no coolant protection. The §24 note "the DSE keeps coolant" was true of the
20 kVA set, not this one. The owner chose:
- **110/16 above 100 °C** (amber), back below 98 °C;
- **110/0 above 104 °C** (red + Protect, so the DSE shuts down), back below 102 °C;
- 2 s each, and only from a good sensor.

These are KOEL's limits from the 20 kVA sheet, kept until the 25 kVA's own
are known. §32's Bosch table makes the hot end accurate to 0.1 °C. **§32
was corrected:** it had called 100/104 °C "the DSE's".

**Pin 43, coolant level** (Bosch `I_S_CLS`; the owner: closed = level OK).
The input was built but never read.
- ABI 6 adds `clt_low`.
- An open switch for 5 s raises 111/18 (amber).
- EFL/P1 now carries SPN 111 (100 % or 0 %), which the 25 kVA DSE is set
  to read from the ECU. Its level alarm is configured with action "None".

**Tests:**
- battery levels with their returns (`test_diag_cond`, `test_diag_battery_low`);
- coolant warn, stop and returns, and the level switch (`test_diag_coolant`).
  The red + Protect lamp is checked in the multi-frame DM1, which the test
  rig now reads.
- Scenario 18 loses charging at 9.3 V instead of 11.0 V.


## 36. The metering valve's and the EGR actuator's wiring, from Bosch's drawing (23 November)

The owner sent two crops of Bosch's terminal diagram. Each was read again on
the drawing itself, rendered at 6×.

**Metering valve (0 928 400 820):**
- its pin 1 goes to ECU 88 and its pin 2 to the main-relay line, as a
  twisted pair;
- it is a proportional solenoid with no diode inside, so D501, the board's
  freewheel diode, is required. It is there.

No change, beyond the pinout reference, the BOM note and bring-up step 4b.

**EGR actuator (Padmini):**
- pins 1 and 2 (the motor) go to 59 and 81, twisted;
- pin 3 goes to 15 (5 V), **pin 5, the wiper of a potentiometer, to 37**,
  and pin 4 to 36 (ground, via V4).

That answers §34's open question: the position sensor is a bare
potentiometer. On the INA592 its wiper saw 18k to ground, ±20 % absolute.
For a 5 kΩ track that is up to 4 % of full scale at mid travel, with a
±1.3 % spread from board to board that no calibration could take out.

**Pin 37 now gets the NTC pins' light divider, 100k/160k, with no
pull-up:**
- under 0.3 % of full scale for a 5 kΩ track (`check_ntc_frontend`);
- an open wiper reads 0 V, which is FMI 4.

U603 and its tail go (INA592 ×3 → ×2). R635, R636, R637, C619 and D612 are
placed last, so nothing renumbers. The prototype took migration `egr_pot`.
The chip layer reads pin 37 at 16/26. The netlist gate now fails if pin 37
meets an INA592 or a pull-up.

**Still to calibrate on the bench:** the pot's voltage at the valve's two
stops. The firmware assumes 0.5–4.5 V for 0–100 %.

---

## 37. The main relay's own drawing: a resistor across the coil (23 November)

The owner sent the relay's symbol (4H.865.27.0.00, main and buzzer
relay): **contact 30–87 normally open, coil 85–86, a resistor in parallel
with the coil.** No diode.

What it means for pins 50 and 69:
- **Wiring is unchanged and polarity-free.** Bosch's drawing (86 to
  Term. 30, 85 to pin 50) fits it; with no diode inside, swapping 85/86
  would also work.
- **Turn-off is softer, not harder.** The resistor carries the coil's
  current at release, so the drain sees 14.4 V + I × R. Pin 50's
  SMAJ48CA caps the rest (§18 already said the TVS works with or without
  a suppressor in the relay). Simulated corners: 330 Ω peaks at 43.8 V
  and the TVS never conducts; 2.2 kΩ peaks at 53.7 V in the TVS.
- **The driver carries a little more.** Coil plus resistor: 133 mA
  at 14.4 V with a 160 Ω coil and 330 Ω resistor. PMV280ENEA is rated
  1 A. That is 8 mW in the FET.
- **No sneak path.** Relay off, the TVS blocks; the resistor doesn't feed
  the board.

`main_relay.cir` part D and `check_main_relay` now check both corners.
No change to either board.

---


## 38. The injector's own drawing (23 November)

The owner's crop of Bosch's drawing shows each injector as **a bare
solenoid on two pins, no diode, with its two wires twisted.** That is
what the injector stage assumes:
- the stage takes the coil's turn-off energy itself (boost recovery and
  the clamp); a diode in the injector would have slowed the closing;
- the coil has no polarity, so which injector pin takes the high side
  changes nothing electrically. The ECU side is fixed by Bosch: high
  sides 03 (cyl 1 + 3) and 05 (cyl 2), low sides 73, 07, 29.

No change to either board. **Still needed: the coil's resistance** (a
meter across the two pins, injector disconnected), which sets the hold
current the stage is checked against.

---



Nothing here was found by reading the schematic. Each one surfaced when a
part number was chosen and its datasheet was checked against what the
drawing assumed — which is the same shape as every earlier finding in
this project: a document and an executable check disagreeing, with
nothing comparing them until someone did.
