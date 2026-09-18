# Field evidence received 18 Sep 2026

Photographs and one document supplied by the project's second engineer, from the
actual machine and from Kirloskar's own PLM system. This file is **raw extracted
evidence**, in the same role as `ecu-pinout-extracted.md`: what the sources say,
with reading confidence marked. Conclusions belong in the memos and the spec.

**Sources, all now committed alongside this file:**

| File | What it is |
|---|---|
| `engine-plate-2026-09-18.jpeg` | Engine rating plate, photographed on the block |
| `ecu-connector-2026-09-18.jpeg` | ECU mating connector, unplugged, face-on |
| `ecu-connector-bosch-marks-2026-09-18.jpeg` | Same connector, angled to the light — Bosch marks and part numbers |
| `koel-plm-project-2026-09-18.jpeg` | Kirloskar Windchill PLM project slide |
| `controller-front-2026-09-18.jpeg` | Genset controller, front — DSE badge and keypad |
| `controller-rear-2026-09-18.jpeg` | Genset controller, rear — label, ratings, terminal numbering |
| `GP3.314.01.0.PR-DSE4522-config.pdf` | 30-page DSE Configuration Suite printout |

Every reading below was taken from these files directly and can be re-checked
against them. The load-bearing markings — the Bosch part numbers, `code C`, and
the controller's model and serial — were each re-read at 4–5× magnification on
the original files after first being transcribed from a smaller preview. All
matched; none needed correction.

---

## 1. Engine rating plate — U11 CLOSED, and against our inference

Photographed directly off the engine block.

| Field | Value |
|---|---|
| ENGINE TYPE | **3GK550ETA 4SR1** |
| RATING kW/hp | **26.5 / 36** |
| rpm | **1500** |
| RATING STD | ISO 3046 |
| DATE OF MFG | **12/09/2025** |
| Sr No | **GK3.8703 / 2528881** (last digits partly legible) |
| TYPE APPROVAL CERTIFICATE No | **ARAI/MoEF/DGTA/IGES4/KOEL- P25/2825/24** |
| Maker | Kirloskar Oil Engines Ltd, Kagal, India |
| Conformity | Environment (Protection) Rules 1986 |

Cast into the block beside the plate: **`GP3.0107`** (vertical, partly obscured).

A second photograph, of Kirloskar's PLM system (`koelplm.kirloskar.com`,
Windchill), shows a project slide:

| Field | Value |
|---|---|
| Model | **3GK550ETA 4SR1** |
| Application Code | **GK3.8703** |
| Rating | **36 HP @ 1500 RPM** |
| Application | **GENSET** |
| Project start / end | 21-11-2025 / 25-11-2025 |

### What this overturns

**Research memo 01 identified this engine as `3R550ETA 4G1` and explicitly
rejected "GK550" as a garbled recollection.** Its exact words were that GK550
"should not be used as a search term or part-lookup key going forward". The
rating plate says **3GK550ETA 4SR1**. The original designation given to this
project was correct and the memo's inference was wrong.

The memo's *supporting* findings survive — 3 cylinders, common rail, 1500 rpm,
CPCB IV+, 26.5 kW — every one of those matches the plate. What failed was the
model-number reasoning built on top of them, which reached a real Kirloskar
engine designation that is not this engine's.

Note also that Kirloskar's own filename for the controller program (below) says
**"3R550"**, so both strings are in circulation inside KOEL. The plate is
authoritative for this machine.

### The application code resolves the wiring diagram's filename

The OEM wiring diagram in this repo is `GP3.8703.C4.pdf`. The engine's
application code is **GK3.8703** and its serial number begins `GK3.8703/`.
The **8703** matches exactly.

Memo 01 recorded as a negative result that "GP3 cannot be resolved to a specific
engine model or family from public sources", with a speculative guess that it
denoted a shared platform generation. **The number is a project/application
code, and it is this engine's.**

### Emissions tier — now certificate-specific

`IGES4` in the type-approval string is India Genset Emission Standard IV, i.e.
the CPCB IV+ tier. This confirms the tier **and** gives the specific certificate
that memo 06's regulatory analysis is about: `P25/2825/24`, issued under
ARAI/MoEF/DGTA. That is no longer an abstract concern — it is a numbered
certificate attached to this serial number.

---

## 2. ECU connector — U1 substantially advanced

Photograph of the ECU's mating connector, unplugged, face-on.

**Markings legible:**
- **`>PA66-GF50<`** — housing material, polyamide 66 with 50% glass fill.
  Standard automotive ECU housing material; not by itself a maker identification.
- **`BDK`** — moulded at lower left of the grey insert. Significance unknown.
- **Two circular moulded logos**, one between cavities `1` and `2` in the power
  chamber, one at the upper right of the main chamber. Examined at 6× on the
  original file: both are clearly circular badges with internal detail, and
  **neither is legible**. The right-hand one is the better of the two and shows a
  rounded form inside the circle. It is not identifiable with confidence, and
  guessing a manufacturer from a blurred outline would be worse than leaving it
  open. **These are the marks to re-photograph under raking light** — a torch held
  almost flat to the surface, several angles. A maker's mark here closes U1.

**Structure, read at full resolution from the cavity numbering.**

The housing has two chambers. Cavity numbers are moulded down both edges of each.

| Chamber | Pins | Arrangement | Contact size |
|---|---|---|---|
| Left, separate | **1–8** | 2 columns × 4 rows | Large — power |
| Main, row 1 | **9–28** | 20 | Fine |
| Main, row 2 | **29–50** | 22 | Fine |
| Main, row 3 | **51–72** | 22 | Fine |
| Main, row 4 | **73–94** | 22 | Fine |

8 + 20 + 22 + 22 + 22 = **94**, exactly.

*Numbers read:* left chamber shows `1`, `2` at the top, `4` at mid-height and
`6`, `8` at the bottom — the even column on the right, odd on the left. The main
chamber's left edge reads `29`, `51`, `73` clearly, with the row-1 label legible
only as a single digit. Its right edge reads `28`, `50`, `72`, `94`.

*One ambiguity, resolved by arithmetic.* The row-1 left label could be read as
`7` or `9` at this image quality. It must be **9**: `7` would make row 1 twenty-two
pins and the total 96, and the connector is 94. A `4` also appears on the left
edge at mid-height, which initially looked like a fifth row label — it sits
measurably further left than `29`/`51`/`73` and belongs to the power chamber, not
the main one.

*(Confirmed from the photograph for the row boundaries and the 94 total;
the single inference is row 1 starting at 9 rather than 7. Counting cavities on
the physical part would settle even that.)*

**This confirms memo 03's inference** that the low-numbered pins are large power
contacts — they are, and they sit in their own chamber. Memo 03 guessed pins
1/2/5/6; the photograph shows the whole 1–8 group is the power chamber.

---

## 2b. ECU CONNECTOR IDENTIFIED — U1 CLOSED

A second connector photograph, taken with the housing angled to the light, carries
the maker's mark and part numbers that the face-on shot could not resolve.

| Marking | Where |
|---|---|
| **BOSCH** + the Bosch armature-in-circle logo | Moulded on the side body |
| **`1 928 405 194`** | Same face, under the BOSCH text |
| **`2.7`** | Beside the logo on that face |
| **`1 928 405 192`** | On the strip along the lower body |
| **`code C`** | Beside `1 928 405 192` — mechanical coding variant |
| `>PA66-GF…<` | On the locking lever |

The `1 928 4xx xxx` series is Bosch's connector part-number range. Taken with the
face-on photograph's 94 cavities, the `>PA66-GF50<` housing and the single-lever
actuation visible here, this is a **Bosch 94-way ECU connector of the EDC17
family**.

**Memo 03 ranked "Bosch EDC17-style 94-pin" as its leading candidate on
inference. It is confirmed, and with part numbers off the physical part** — which
is better evidence than a catalogue match, since it cannot be a mis-identification.

*Note on `code C`:* Bosch supplies these housings in mechanically coded variants
so that differently-coded plugs cannot be mated. **Any replacement or adapter
housing must match code C**, or it will not engage. This is the kind of detail
that is invisible until a part arrives and will not fit.

*A web search for the two part numbers returned no direct catalogue hit* — the
series and the 94-way EDC17 family are well represented commercially, but these
specific numbers did not surface. Sourcing should go through a Bosch distributor
quoting the numbers, not through a search engine. *(Negative result, recorded.)*

---

## 3. THE GENSET CONTROLLER IS A DEEP SEA DSE4522 — CONFIRMED, NOT A KG640C

**Settled by photograph, 18 Sep 2026.** The controller has been removed and
photographed front and rear.

Front: **DSE — Deep Sea Electronics** badge, LCD, and the Stop / Auto / Start
keypad of the 45xx series.

Rear label:

| Field | Value |
|---|---|
| Model | **4522 MKII AMF (INDIA SP)** |
| Part number | **4522-001-01** |
| Batch | F001022612 |
| Serial number | **11021794** |
| Origin | Made in the UK |
| Housing | 020-1048,5 |

Ratings printed on the rear housing:

| | |
|---|---|
| DC supply | 8 V to 35 V, 0.5 A max |
| DC outputs | 30 V, **5 A (T3–T4)**; **2 A (T6–T9)** |
| DC inputs | 30 V max |
| AC voltage inputs | 600 V AC, 50/60 Hz, 1 ph to 3 ph |
| AC current inputs | 5 A, 50/60 Hz, 1 ph to 3 ph |
| Charge alternator | 30 V DC, 2.5 W max |
| Comms port | 5 V DC max |

Terminals visible: **1–9, 10–20** along the bottom; **21–24, 25–28, 29–35** along
the top. **35 terminals.** A USB-B configuration port sits on the rear face.

Document supplied alongside: **`GP3.314.01.0.PR — DSE 4522 CONTROLLER PROGRAM FOR
3R550.25KVA, 3PHASE (GK PROJECT)`**, 30 pages, dated 10-07-2026. A full DSE
Configuration Suite printout, and now confirmed to be the program for the module
that is actually fitted.

`GP3.314.01.0.PR` follows the same `GP3.` document-numbering as the wiring
diagram, and the title names this engine and this rating.

**Research memo 02 is an analysis of the KG640C, and the KG640C is not on this
machine.** The whole of spec §3's safety position was built on that memo. It has
been rewritten — see §3 of the spec, second revision.

### 3.0 What DSE's own manual says about engine speed — the finding that matters

From the DSE4510 MKII / DSE4520 MKII operator manual, document **`057-260` issue 6**
(the 4522's direct siblings; downloaded and text-extracted):

> "If the unit has been configured for CAN, compatible ECU's receive the start
> command via CAN and **transmit the engine speed to the DSE controller**."

and in the engine-at-rest detection logic:

> "Engine speed is zero **as detected by the CAN ECU**"

**Engine speed reaches this controller from the ECU, over CAN.** Memo 02's central
claim — that the controller senses speed from alternator frequency independently
of the ECU — is false for the fitted device. The configured 1710 rpm overspeed
shutdown reads a number our ECU sends, and a hung ECU transmitting a stale
plausible speed defeats it.

**No magnetic pickup input exists** on this module. The manual's terminal table
runs 1–35 with no speed-pickup terminal of any kind. That makes U3's answer
*confirmed* rather than *inferred* — arrived at correctly by memo 02, for a
device that turned out not to be fitted.

**The independent path that does survive is generator over-frequency.** The
module measures generator frequency directly at terminals 21–24, off the
alternator's three phases, without touching CAN. The configuration sets an
over-frequency **shutdown at 56.0 Hz**, which on this 4-pole alternator is
**1680 rpm** — below the CAN-dependent 1710 rpm overspeed trip. It is genuinely
independent of our ECU, and it is conditional on the alternator being excited.

### 3.0.1 Terminal assignments, from the manual

| Terminal | Function | Rating |
|---|---|---|
| 1 / 2 | DC plant supply negative / positive | — |
| **3** | **DC Output A — FUEL** | 10 A for 10 s, 5 A continuous |
| **4** | **DC Output B — START** | 10 A for 10 s, 5 A continuous |
| 5 | Charge fail / excite | — |
| 6–9 | DC Outputs C–F | 2 A each |
| **10** | **Sensor common return** | must bond to the **engine block** |
| 11 / 12 / 13 | Analogue sensor inputs A / B / C | oil / coolant / fuel level |
| 14–17 | Configurable digital inputs A–D | switch to negative |
| 18 / 19 / 20 | CAN H / CAN L / screen | 120 Ω cable |
| 21–24 | Generator L1 / L2 / L3 / N voltage sensing | — |
| 25–28 | Mains L1 / L2 / L3 / N | — |
| 29–35 | CTs, charge alternator, comms | — |

This reconciles the configuration printout exactly: six DC outputs A–F, of which
two are the 5 A pair on T3/T4 and four are the 2 A group on T6–T9.

**Terminal 10's instruction is emphatic and worth carrying into our own design.**
DSE's manual: *"It is VERY important that terminal 10 (sensor common) is connected
to an earth point on the ENGINE BLOCK, not within the control panel … This
connection MUST NOT be used to provide an earth connection for other terminals or
devices."* That is the same discipline research memo 09 found in SEDEMAC's sensor
common point, now confirmed as DSE practice on the exact module fitted here.

### 3.1 Digital outputs (page 4) — contradicts memo 02's mapping

| Output | Source | Polarity |
|---|---|---|
| A | **Fuel Relay** | Energise |
| B | **Start Relay** | Energise |
| C | Close Mains Output | Energise |
| D | Close Gen Output | Energise |
| E | Not Used | Energise |
| F | **Common Shutdown** | Energise |

Memo 02 assigned output A to the start relay and output B to the ignition relay.
This configuration assigns **A = Fuel, B = Start**. The domain SME review
separately read the wiring diagram as `-13RB1` = ignition on output B and
`-13RB2` = start on output A.

Three sources, three mappings. **U12's measurement is now more necessary, not
less.**

### 3.2 Speed, and where it comes from (pages 12, 15)

| Setting | Value |
|---|---|
| Module to Record Engine Hours | Yes |
| **Module To Use Engine Speed** | **No** |
| Module To Use Charge Alt Voltage | Yes |
| Disable ECM Speed Control | No |
| Overspeed Overshoot | 10 % |
| Overshoot Delay | 2 s |
| **Under Speed Shutdown** | **Enabled, 1310 rpm** |
| **Over Speed Shutdown** | **Trip 1710 rpm** |

Crank disconnect (page 15):

| Source | Threshold |
|---|---|
| Generator Frequency | 15.0 Hz |
| Engine Speed | 600 rpm |
| Oil Pressure | 3 Bar |
| Charge Alternator | No (6.0 V DC) |
| Crank Disconnect on Oil Pressure | No |
| Check Oil Pressure Prior to Starting | **Yes** |

**`Module To Use Engine Speed = No` needs interpreting against DSE's own
documentation before anything is concluded from it.** Read one way it means the
module takes engine speed from the ECU over CAN rather than measuring it — which
would *remove* the independent speed path that spec §3's relaxation depends on.
Read the other way it means the opposite. This is the single most important thing
to resolve and it must not be guessed. **Generator frequency does appear as a
crank-disconnect source, so alternator-frequency sensing is present in the
module for at least that purpose.**

Overspeed trip is **1710 rpm**, 114 % of 1500.

### 3.3 What the controller expects OUR ECU to send (pages 2, 9, 10, 12, 13)

This is a direct requirements list for the J1939 implementation — it partly
answers **U4**, which memo 02 left open.

| Setting | Value |
|---|---|
| CAN source address — engine messages | **234** |
| CAN source address — instrumentation | **44** |
| J1939-75 Instrumentation Enable | Yes |
| J1939-75 Alarms Enable | No |
| Oil pressure | **read from the ECU (ECM)** |
| Coolant temperature | **read from the ECU (ECM)** |
| Coolant level | **read from the ECU (ECM)** |
| Engine Type profile selected | `[Development] KOEL 4R4K6KSL90 CRS-878` |

The engine-type string is the DSE's decoding profile, not the engine's name. It
is marked `[Development]`. What `CRS-878` denotes is unknown and worth chasing —
"CRS" plausibly means the common-rail system identifier, which would bear on U5.

Protection thresholds the controller applies to values **we** supply:

| Alarm | Threshold | Action |
|---|---|---|
| Low oil pressure | 0.99 Bar (99 kPa) | Shutdown |
| High coolant temp — pre-alarm | 150 °C (return 125 °C) | — |
| High coolant temp — shutdown | **200 °C** | Shutdown |
| Exhaust temperature trip | 650 °C | — |
| Coolant level | 25 % (return 50 %) | None |
| **ECU (ECM) Data Fail** | — | **Shutdown**, armed from Safety On |
| ECU Protect (DM1) | — | **Shutdown** |
| ECU Amber / Red / Malfunction | — | Warning |

**`ECU Data Fail → Shutdown` is significant for the safety case.** If our ECU
stops transmitting on CAN, this controller shuts the set down. That is a real
watchdog on our ECU, held by another device.

### 3.4 An emergency stop exists (page 2)

| Digital Input A | |
|---|---|
| Function | **Emergency Stop** |
| Polarity | **Open to Activate** |
| Activation delay | 0 s |

The domain SME review listed "independent hard-wired E-stop" as absent from the
design. **It exists on the controller**, and it is wired fail-safe — open circuit
activates it, so a cut wire trips rather than disables the stop.

Other digital inputs: B = Remote Start On Load (close to activate), C = user
configured (indication, never armed), D = user configured (warning, always).

### 3.5 Pre-heat and post-heat are enabled (page 12)

| | Enabled | On | Duration |
|---|---|---|---|
| Pre-heat | **Yes** | 50 °C | 0 s |
| Post-heat | **Yes** | 50 °C | 0 s |

**Our design has no glow-plug or heater output anywhere**, and neither the spec
nor the unknowns register mentions cold-start heating. Whether the heater is
driven by the controller or by the ECU is now an open question.

### 3.6 Aftertreatment signals are armed (page 14)

`DPTC Filter`, `HEST Active`, `DEF Level` and `SCR Inducement` are all
**Enabled: Yes**, action Warning, armed from Safety On. Also `DPF Regeneration
Control — Allow Non-Mission Regeneration: No`.

Spec §2.6 records that this system has no SCR and no DEF. These are most likely
DSE defaults left enabled rather than evidence of fitted hardware — but it means
the controller is prepared to act on aftertreatment messages, and a replacement
ECU that never sends them may or may not be noticed. Worth checking against the
machine.

### 3.7 Fuel level and water-in-fuel — spec §2.3 holds

| | |
|---|---|
| Analogue Input C | **Fuel Sensor** |
| Low fuel level alarm | Shutdown at 10 % |
| Low fuel level pre-alarm | Warning at 15 % |
| Fuel Level Switch | **Shutdown**, always armed |
| Water In Fuel | Warning, always armed |

Both are controller-side signals, exactly as spec §2.3 concluded. That finding
survives intact.

### 3.8 Electrical configuration (pages 6, 7, 15)

| | |
|---|---|
| Alternator poles | 4 |
| AC system | 3 phase, 4 wire |
| Nominal | 415 V ph-ph, 50.0 Hz |
| Generator kW rating | 20 kW |
| CT primary / secondary | 50 A / 5 A |
| Full load rating | 34 A |
| Overload trip | 112 %, 22 kW, 4 s delay |
| Over-frequency shutdown | 56.0 Hz (112 %) |
| Plant battery under-volt warning | 9.5 V (return 10.0 V), 10 s |
| Plant battery over-volt warning | 15.0 V (return 14.5 V), 10 s |
| Charge alternator alarm | Shutdown and warning both enabled |

4 poles at 1500 rpm gives exactly 50 Hz, confirming the rigid speed-to-frequency
relationship memo 02 relied on.

Start timers: 3 start attempts, 5.0 s cranking, 10 s cranking rest, 10 s safety-on
delay, 20 s warming, 30 s fail-to-stop delay, 30 s cooling.

---

## What this does NOT tell us

1. **Whether the DSE4522 is the controller actually fitted to this machine.**
   The document is a Kirloskar-issued program for this engine and rating, which
   is strong. But the OEM wiring diagram in this repo shows a KG640C, and both
   documents carry `GP3.` numbering. Possibilities: the panel was changed; there
   are two panel variants; the DSE4522 is for a different market or a later
   revision. **A photograph of the controller's front panel and its rear
   terminal strip settles this in seconds and should be the next thing asked
   for.**
2. **Which relay is which.** Three sources now disagree on the output-to-relay
   mapping. Only measurement settles it.
3. **What `Module To Use Engine Speed = No` means in DSE's semantics.** Needs the
   DSE4522 manual, not inference.
4. **Whether the ECU or the controller drives the pre-heat/post-heat output.**
5. **The connector's maker.** The photograph advances the structure but the two
   circular logos are unresolved.

---

# Second batch, 18 Sep 2026 — verbal report, no photographs

Reported by the on-site engineer. **Verbal, not documented** — no photograph,
meter reading or wiring trace accompanies these, so they are recorded at lower
confidence than the first batch and each is marked with what would raise it.

## 4. U12 CLOSED — the fuel relay signals, it does not remove power

> "fuel relay cuts signal"

This is the outcome the inspection brief instructed be reported immediately
rather than saved for a writeup, and the reason is that it resolves §3's safety
gate against the design.

**What it means.** Every protective action the DSE4522 can take ends by
de-energising the FUEL relay on its terminal 3. If those contacts had carried the
fuel system's supply, the controller could physically stop the engine without the
ECU's cooperation. They do not. A hung ECU keeps the fuel metering unit
energised.

**It compounds with U13** rather than merely adding to it. The controller's
overspeed trip reads engine speed from our CAN, so a hung ECU hides the fault
from it. Its generator over-frequency trip measures the alternator directly and
does see the fault — and then acts through this relay. So:

| Protection | Can it *see* a hung-ECU runaway? | Can it *act* on one? |
|---|---|---|
| Engine overspeed, 1710 rpm | No — reads our CAN | (moot) |
| Generator over-frequency, 56.0 Hz | Yes — reads the alternator | **No — acts through the signalling relay** |

**Nothing on this machine currently interrupts fuelling without the cooperation
of the ECU being protected against.**

**Confidence and what would raise it.** Brief task 1.4 exists precisely because a
normally-closed relay produces the same voltage reading with the opposite
meaning, and it is not confirmed that 1.4 was performed first. The phrasing
reported is a statement about function rather than a raw voltage, which suggests
the circuit was traced rather than measured at one point — but that is an
inference about method, not evidence. **The unsafe reading is adopted regardless**,
because being wrong in that direction costs nothing and being wrong in the other
direction costs the machine. A photograph of the relay's contact arrangement, or
the 1.4 continuity result, would settle it.

## 5. Intake throttle and the pre/post-heaters are battery-fed — U8 and U14 partially answered

> "for intake throttle, preheat and post heat, its battery"

**What this answers:** the ECU does not *supply* any of these three loads. That
removes them from the power budget and from any consideration of high-current
outputs on our side.

**What it does not answer, and the distinction matters:** supply and control are
separate questions. A battery-fed actuator can still be ECU-commanded — the OEM
fuel metering unit is exactly that, fed from battery through fuse `8F1` and
switched by the ECU's low-side PWM on pin 88 (spec §2.2). The same arrangement on
the throttle would put a driver back in scope.

So U8 still needs brief task 3.11 — follow the 6-pin throttle cable by hand and
see whether it terminates at the 94-way ECU connector or joins the XC11/XC1 panel
loom. And U14 still needs to know who switches the heater feed; the DSE4522's
configuration enables pre-heat and post-heat at 50 °C, which makes the controller
the likely switch, but "likely" is the word that has cost this project three
unknowns already.

## The pattern, recorded because it is now a measurement rather than an impression

Five unknowns have been closed by field evidence. **Four closed against what this
project had reasoned:** U11 (engine identity — memo 01 was wrong and had advised
discarding the correct search term), U13 (which controller — memo 02 analysed a
device that is not fitted), U12 (the safety gate), and only U1 (the connector)
closed in favour of an inference.

Desk research on this project has a measured track record, and it is poor. That
is not an argument against doing it — it is an argument for marking its outputs
as provisional and for weighting a single multimeter reading above a chain of
plausible reasoning.
