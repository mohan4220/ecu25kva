# Field evidence received 18 Sep 2026

Photographs and one document supplied by the project's second engineer, from the
actual machine and from Kirloskar's own PLM system. This file is **raw extracted
evidence**, in the same role as `ecu-pinout-extracted.md`: what the sources say,
with reading confidence marked. Conclusions belong in the memos and the spec.

**The original files are not yet in this repo.** They arrived through
conversation, not the filesystem. They should be committed to `refs/` — the
three photographs and the 30-page DSE configuration PDF — so this extract can be
checked against them.

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
- Two small circular logos, upper left and upper right of the grey insert, not
  resolvable at this image size. **These are the marks worth re-photographing
  under raking light** — see the inspection brief.

**Structure, read from the visible cavity numbering.** Numbers legible at the
edges: `1`, `2` at the top of a separate left-hand chamber; `7` lower in that
same chamber; and on the main chamber `29`, `51`, `73` down the left edge with
`21`, `50`, `72`, `94` down the right.

That is consistent with, and only with, this arrangement:

| Chamber | Pins | Contact size |
|---|---|---|
| Left, separate | **1–8** | Large — power |
| Main, row 1 | **9–28** (20) | Fine |
| Main, row 2 | **29–50** (22) | Fine |
| Main, row 3 | **51–72** (22) | Fine |
| Main, row 4 | **73–94** (22) | Fine |

8 + 20 + 22 + 22 + 22 = **94**. *(Inferred from the photograph, high confidence —
the arithmetic closes exactly and every legible number falls where this
arrangement puts it. Should still be confirmed by counting cavities on the
physical part.)*

**This confirms memo 03's inference** that the low-numbered pins are large power
contacts — they are, and they sit in their own chamber. Memo 03 guessed pins
1/2/5/6; the photograph shows the whole 1–8 group is the power chamber.

---

## 3. THE GENSET CONTROLLER IS A DEEP SEA DSE4522, NOT A KG640C

Document supplied: **`GP3.314.01.0.PR — DSE 4522 CONTROLLER PROGRAM FOR
3R550.25KVA, 3PHASE (GK PROJECT)`**, 30 pages, dated 10-07-2026. It is a full
DSE Configuration Suite printout.

`GP3.314.01.0.PR` follows the same `GP3.` document-numbering as the wiring
diagram, and the title names this engine and this rating.

**Research memo 02 is an analysis of the KG640C.** The whole of spec §3's safety
position is built on it: that the controller senses speed from alternator
frequency, that its digital output B drives a 70 A ignition relay, and that this
gives an overspeed path bypassing the ECU. **If the fitted controller is a
DSE4522, that analysis is about the wrong device.**

This is not yet settled — see "What this does not tell us" below.

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
