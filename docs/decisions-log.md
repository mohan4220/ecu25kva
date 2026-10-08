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

## Where these came from

Nothing here was found by reading the schematic. Each one surfaced when a
part number was chosen and its datasheet was checked against what the
drawing assumed — which is the same shape as every earlier finding in
this project: a document and an executable check disagreeing, with
nothing comparing them until someone did.
