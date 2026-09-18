# Research Memo 02: KG640C Genset Controller (GCU) — J1939 Contract and the MPU Safety Gate

**Task:** U3 (safety gate), U4. **Task 2, phase-1 research — highest priority in the phase.**
**Date:** 2026-09-13
**Author:** Phase-1 research (task 2)

---

## SUPERSEDED IN PART, 18 Sep 2026 — the controller may not be a KG640C

A Kirloskar-issued configuration document has been supplied:
`GP3.314.01.0.PR — DSE 4522 CONTROLLER PROGRAM FOR 3R550.25KVA, 3PHASE (GK
PROJECT)`, 30 pages. It is a **Deep Sea Electronics DSE4522** configuration, and
it names this engine and this rating.

**This memo analyses a KG640C.** The OEM wiring diagram in this repo shows a
KG640C, and both documents carry `GP3.` numbering, so which controller is
actually fitted is now an open question rather than a settled one. Spec section 3's
safety position is built on this memo.

Two specific contradictions, neither yet resolved:

- **Output mapping.** This memo assigns output A to the start relay and output B
  to the ignition relay. The DSE4522 configuration assigns **A = Fuel Relay,
  B = Start Relay**. A separate reading of the wiring diagram gives `-13RB1` =
  ignition on B and `-13RB2` = start on A. Three sources, three mappings.
- **Speed source.** This memo's central finding is that the controller senses
  speed from alternator frequency independently of the ECU. The DSE4522
  configuration carries `Module To Use Engine Speed = No`, whose meaning in DSE's
  own semantics must be established from their documentation before anything is
  concluded from it.

**What the new document adds rather than contradicts:** an Emergency Stop input
wired fail-safe, `ECU Data Fail → Shutdown`, CAN source addresses 234 and 44,
and the protection thresholds the controller applies to values our ECU supplies.
Those partly answer U4.

**The thing that settles it is a photograph of the controller's front panel and
rear terminal strip.** Until then, treat this memo's device identification as
unconfirmed.

Evidence: [`refs/field-evidence-2026-09-18.md`](../../refs/field-evidence-2026-09-18.md).

---

## Verdict (U3 — read this first)

**The KG640C genset controller has no dedicated magnetic pickup (MPU) input terminal. Verdict: No.**

**Status: inferred, high confidence** (not "confirmed" outright — see caveat below) — from two Kirloskar Oil Engines Limited (KOEL) primary documents, not from the wiring diagram's silence:

1. **The OEM wiring diagram itself** (`/home/mohan/workws/ecu25kva/refs/GP3.8703.C4.pdf`, page 1, "GENSET CONTROL UNIT KG640C" block) shows the controller's terminal groups **J1 through J8 in full** — every terminal on the block is labelled: J1 (terminals 1–2, `12/24` battery-sense), J2 (terminals 3–6, digital outputs A–D: Start Relay, Ignition Relay, MC Connect Relay, Common Fault), J3 (terminals 7–10: `D+CHG ALT`, digital outputs/inputs), J4 (terminals 11–16: digital input, **CAN L/H**, RS485 A/B), J5 (terminals 17–26: reserved, digital inputs D/E, analog inputs), J6 (terminals 27–30: genset alternator voltage/frequency sense, fed from the DG alternator's 415 VAC 3-phase output), J7 (mains voltage sense N/B/Y/R), J8 (terminals 35–42: CT current-sense inputs, SCP). **No terminal in J1–J8 is labelled MPU, speed pickup, or magnetic pickup.** Every terminal on the block is accounted for, so this is a complete negative, not silence about an unused pin. *(Confirmed — read directly from the diagram at 400 DPI.)*
2. **A genuine KOEL controller manual for the same product family, "KG640 CONTROLLER MANUAL"** (KOEL letterhead, Laxmanrao Kirloskar Road, Khadki, Pune; internal document number `SED-MAN-KG640-002`), found hosted on Scribd (uploaded by an account named `rajinder.kirloskar`) at https://www.scribd.com/document/878092942/SED-MAN-KG640-002-Koel-Manual-for-KG640-Genset-Controller and retrieved in full (92 pages). This is the **base "KG640" variant** (no CAN bus at all — see §2 below), but its terminal architecture matches the KG640C block on the wiring diagram almost exactly: terminals 1–2 battery, 3–6 digital outputs, 7 `D+ CHARGE ALT`, 27–30 `GEN_V IN` (N,B,Y,R), 35–40 `GEN_CT_IN`, 41 `SCP` — the same terminal numbers doing the same jobs as the KG640C block in the wiring diagram. The manual's **complete 42-terminal table (its Table 15, "Terminal Description")** enumerates every terminal from 1 to 42 with a name; there is no MPU/speed-pickup terminal anywhere in it. Its glossary lists "MPU" as an abbreviation (page iii) but the term is **never used again anywhere in the 92-page body** — consistent with a shared glossary template across KOEL controller documents rather than evidence this unit has one. **Its own configuration parameter for engine speed, "Engine Speed Sense Source," offers only one value: `Alternator frequency`** (§16.8.2, "Speed monitoring engine screen": *"Allows to select electrical signal to be use for measurement of engine speed. Alternator frequency: Engine speed will be sensed from alternator frequency."*). No magnetic-pickup or CAN option is listed for that parameter anywhere in the document. *(Inferred, high confidence, from a primary KOEL manufacturer document — see caveat below on why this isn't "confirmed" outright.)*

**Caveat, stated plainly:** this manual documents "KG640," not "KG640C" by name, and it predates or excludes the CAN bus that the wiring diagram's KG640C block clearly has (J4 terminals 13/14, CAN L/H — repurposing what the base manual lists as "Reserved" terminals 13/14). The "C" suffix is therefore read as "CAN-added" variant of the same terminal architecture, not a different product — the terminal-for-terminal match on every other function (genset voltage sense, CT sense, digital I/O, D+ charge alt, RS485) is too exact to be coincidental. But no manual titled specifically "KG640C" was located, so this is an inference from a closely related sibling document, not a direct statement about the exact SKU. This is why the verdict is **"No, inferred with high confidence"** rather than **"No, confirmed."** Per the task's own safety framing, concluding "no MPU" when the true answer might be "yes" is the safe-direction error (it triggers an unnecessary but harmless redundant hardware purchase); concluding "yes" when the answer is "no" is the dangerous-direction error. This memo is deliberately conservative.

**What would upgrade this to "confirmed":** a manual or datasheet with "KG640C" in the title/header (not just the base KG640), a photograph of a physical KG640C rear terminal block, or a call to KOEL technical support quoting manual number `08-GP3-60-001` (the engine wiring diagram's own manual number, from Task 1) and asking directly.

### A materially important side-finding: the GCU already has a speed-sensing path independent of the engine ECU and CAN bus

The base KG640 manual's Table 5 ("Genset Voltages and Frequency") specifies terminals 27–30 sample the **genset's own AC output** at **5 kHz**, deriving frequency over a **3–75 Hz range at 0.1 Hz resolution, 0.25% accuracy**. Because this 4-pole alternator's electrical frequency is rigidly tied to shaft speed (1500 rpm ↔ 50 Hz, no slip), and because the GCU's "Engine Speed Sense Source" defaults to reading this alternator frequency rather than a CAN message from the engine ECU, **the GCU's own over-speed and gross-over-speed shutdown logic (manual §16.8.2, alarms #27/#28 in the base manual's alarm table) does not depend on the engine ECU or the CAN bus between them** — it depends only on the GCU's own AC front-end and its own microcontroller. This is **not** a substitute for a hardware MPU trip (it still shares fate with the GCU's firmware/microcontroller, and a CAN-bus failure alone would not defeat it, but a GCU firmware hang would), and it does **not** change the verdict above. But it is directly relevant to the design decision that follows from the verdict, and should inform how the team weighs the residual risk before deciding how much redundancy the standalone module below needs to add. *(Inferred from the base KG640 manual's specification tables and alarm list; not confirmed for the KG640C variant specifically, since KG640C-specific documentation was not located.)*

### Recommended standalone overspeed trip module candidates (since the answer is "No")

Two candidates, both electronic speed switches driven from a magnetic pickup at the flywheel ring gear, independent of any ECU or GCU microcontroller:

| # | Part | Function | Key specs (manufacturer-stated) | India availability / price found |
|---|---|---|---|---|
| 1 | **Governors America Corp (GAC) SSW675** "2-Element Speed Switch — Overspeed, Crank" | Dedicated dual-setpoint electromechanical-relay trip switch: low setpoint = crank disconnect, high setpoint = overspeed shutdown. Magnetic-pickup input, 5 A relay output, on-board overspeed test circuit. | Manufacturer product page: https://www.governors-america.com/product/ssw675/ (fetch blocked by site, confirmed via search-result excerpt quoting the manufacturer's own description) | **India price not confirmed this session** — GAC/Governors America Corp parts are stocked by Indian industrial resellers (e.g., Spares Bazaar Pvt Ltd, New Delhi, and HT Industrial Automation Ltd, which list other GAC part numbers), but no INR figure for SSW675 specifically was found. A related GAC part family (ESD5100-series analog governors, a **different product — NOT a dedicated overspeed relay**, and GAC's own ESD5500E documentation explicitly states a separate overspeed shutdown device is still required) is listed at **₹9,500/piece** by Spares Bazaar Pvt Ltd, New Delhi (https://www.indiamart.com/proddetail/esd5500e-esd5111-esd5550-esd5221-gac-speed-control-unit-governor-america-corp-21293246791.html) — cited only as a rough order-of-magnitude anchor for this brand/class of device in the Indian market, **not** as pricing for the correct part. |
| 2 | **Murphy by Enovation Controls HD9063** dual-setpoint electronic speed switch | Crank disconnect (250–6,000 Hz) + overspeed (1,100–10,000 Hz) on one module. Magnetic-pickup input, 0.35–60 Vrms signal range, 8–30 VDC supply, SPDT relay output 5 A/30 VDC, built-in overspeed test circuit and trip-point LEDs. Explicitly marketed for "generator sets, pumps, and compressors." | Manufacturer product page: https://www.enovationcontrols.com/products/hd9063-os77d-and-ss300/ (fetched directly, specs quoted above verbatim) | Indian distributor confirmed: **"Murphy By Enovation Controls," Pune, Maharashtra**, IndiaMART storefront lists HD9063/OS77D/SS300 (https://www.indiamart.com/proddetail/hd9063-os77d-and-ss300-electronic-speed-switches-15889251691.html) but the listing is quote-only ("Get Latest Price") — **no published INR figure**. |

**Negative result, recorded honestly:** this session did not obtain a firm INR list price for either correctly-matched dedicated overspeed module (SSW675 or HD9063). Both have confirmed Indian distributors who would need to be contacted directly for a quote. A single-function analog GAC governor (a different, not-directly-comparable product) was found at ₹9,500 in India as the only concrete INR figure this search turned up for the GAC brand; it is reported here only for order-of-magnitude context, flagged explicitly as the wrong product class, and should not be used as a quote basis.

---

## 1. Controller identity and sourcing basis

- **Controller:** Kirloskar KG640C, named independently by the OEM wiring diagram (`GP3.8703.C4.pdf`, page 1) and by KOEL's public CPCB IV+ 25–58.5 kVA brochure (Task 1, `01-engine-identity.md`). *(Confirmed.)*
- **Manual used:** `SED-MAN-KG640-002`, "KG640 CONTROLLER MANUAL," KOEL, found via Scribd (https://www.scribd.com/document/878092942/SED-MAN-KG640-002-Koel-Manual-for-KG640-Genset-Controller), retrieved and read in full (92 pages). This is a genuine KOEL-authored document (KOEL letterhead, internal doc number, copyright notice), located via a document-sharing site rather than kirloskar.com directly — the **content is primary** (manufacturer-authored), but its **hosting is secondary** (Scribd, not KOEL's own domain). Flagged for transparency; the manual's content is treated as manufacturer documentation for the purposes of the "no safety-relevant conclusion from a secondary source" rule, because the document itself is KOEL's own, not a reseller's or forum's description of KOEL's product.
- **Not investigated further as a "rebadge" lead:** the brief flagged Deep Sea Electronics, ComAp, Datakom, SmartGen and Lovato as common Indian-market OEM sources. A SmartGen HGM6100N manual was pulled during this investigation as a comparison candidate, but the KOEL-letterhead KG640 manual's near-exact terminal-for-terminal match to the KG640C block in the OEM wiring diagram is strong enough evidence that **KG640C is Kirloskar's own documented product**, not a rebadge requiring third-party manual substitution. This conclusion is **inferred**, not from a statement anywhere that KG640C is Kirloskar's original design, but from the convergence of two independent KOEL-branded documents describing the identical terminal architecture.
- **No manual titled specifically "KG640C" was located** despite searching `Kirloskar KG640C manual`, `"KG640C" Kirloskar controller manual pdf`, `scribd "KG640C" OR "SED-MAN-KG640C"`, and the `ikonnect.kirloskar.com` portal (which exposes no manual index to an unauthenticated fetch, consistent with Task 1's finding). A sibling document, "KG645 Genset Controller User Manual" (https://www.scribd.com/document/407079798/Kirloskar-KG645-User-manual-for-genset-controller-pdf, 123 pages), was found and may be a closer CAN-capable relative, but its full text could not be retrieved this session (Scribd's preview blocked the fetch tool; only metadata was obtained). **Flagged as an unresolved lead**, not pursued further under this task's budget constraint.

---

## 2. J1939 PGN expectations (Step 3) — mostly unconfirmed; documented honestly

**This section could not be closed with primary-source confirmation.** The only KOEL controller manual obtained in full (the base "KG640," §1 above) has **no CAN bus and no J1939 content whatsoever** — no mention of PGN, SPN, EEC1, ET1, EFL/P1, VEP1, DM1, or TSC1 anywhere in its 92 pages (verified by full-text search of the extracted manual). Its only digital communications are RS485/Modbus (for panel-to-PC configuration, terminals 15/16) and USB (configuration tool). This confirms the base KG640 does not need this section at all — but it also means **the base manual cannot answer Step 3 for the CAN-equipped KG640C variant actually in the field.**

What **is** confirmed directly from the two primary hardware documents:

| Fact | Source | Status |
|---|---|---|
| KG640C has exactly **one** CAN interface on its terminal block: J4, terminal 13 = CAN L, terminal 14 = CAN H | OEM wiring diagram, page 1 (`kg_bot.png` crop) | Confirmed |
| The engine ECU has **two** CAN channels: channel 1 on pins 55 (CAN H)/77 (CAN L), channel 2 on pins 87 (CAN H)/86 (CAN L) | `ecu-pinout-extracted.md`, "CAN — two channels" | Confirmed |
| Which of the ECU's two CAN channels physically connects to the GCU's single CAN port is **not stated** in either document — the wiring diagram's harness connectors (XC1/XC11) were not traced pin-for-pin to this specific link in the pinout extraction | Both documents | **Not established — open item** |
| Baud rate is not stated on either the wiring diagram or in the base KG640 manual | — | **Not established — open item** |
| Engine ECU source address (whether 0x00 per SAE J1939 convention) is not stated anywhere in the available documents | — | **Not established — open item** |

**What is *not* confirmed, and is presented here only as an informed, explicitly-labelled expectation, not a finding:** a J1939 link between a proprietary genset controller and a Tier-4/CPCB-IV+ common-rail ECU of this type would, by nearly universal industry convention (SAE J1939-71), be expected to carry at minimum: **EEC1 (PGN 61444)** for engine speed, **ET1 (PGN 65262)** for coolant temperature, **EFL/P1 (PGN 65263)** for oil pressure, **VEP1 (PGN 65271)** for battery/system voltage, **DM1 (PGN 65226)** for active diagnostic trouble codes, and **TSC1 (PGN 0)** if the GCU (rather than the ECU alone) is meant to command engine speed/torque. Standard J1939 baud rate for this device class is 250 kbit/s, and the engine ECU node would conventionally sit at source address 0x00. **None of this is sourced to a KG640C document — it is a generic industry baseline offered so the design isn't starting from nothing, and it must be treated as inferred/unconfirmed until either a real KG640C CAN specification is found or the bus is logged directly off the existing panel.**

**What would close this:** (a) locating and fully retrieving the KG645 manual noted above, on the chance it documents the CAN link in detail; (b) a KG640C-specific manual or CAN database (DBC) from KOEL; (c) the most direct route — connecting a CAN logger to the existing genset's harness at the XC1/XC11 connectors and recording live traffic, which would settle baud rate, source addresses, and the actual PGN set in one measurement, superseding any manual-based inference.

---

## 3. Digital I/O contract (Step 4)

Confirmed terminal assignments on the KG640C block (wiring diagram page 1, `kg_top.png`/`kg_bot.png` crops), cross-referenced against the base KG640 manual's terminal table and against `ecu-pinout-extracted.md`'s ECU-side digital I/O list:

| KG640C terminal | Group | Function | Direction relative to ECU |
|---|---|---|---|
| J2-3 (terminal 3, "A") | Digital output | Drives **START RELAY** coil | GCU issues the start *request*; see reasoning below on what actually cranks the engine |
| J2-4 (terminal 4, "B") | Digital output | Drives **IGNITION RELAY** coil (`-13RB1`, 70 A) | GCU-issued; **corrected 14 Sep 2026** — this memo originally named this relay `-13RB2`, which is the START relay on output A; the ignition relay is `-13RB1`. The binding spec always had it right, so the error did not propagate. This relay's contact almost certainly switches battery+ onto ECU pin 71 (`IGNITION`, confirmed active-high/switched-battery per `ecu-pinout-extracted.md`), i.e. **the GCU powers the ECU on** |
| J2-5 (terminal 5, "C") | Digital output | Drives **MC CONNECT RELAY** (mains contactor connect) | Not ECU-related — genset/mains transfer logic, panel-side only |
| J2-6 / J3 area | Digital output | **COMMON FAULT** relay, **GC CONTACT RELAY** (genset contactor) | Not ECU-related — panel/contactor logic |
| J3-7 | Combined I/O | **D+ CHARGE ALT** — GCU provides alternator field excitation and reads back charge-alternator voltage for charge-fail detection | **Entirely GCU-and-alternator; the ECU is not involved.** `ecu-pinout-extracted.md`'s connector appendix lists a 2-pin "Charging Alternator" connector present in the harness but never traced to an ECU pin, consistent with this. |
| J4-13/14 | CAN L/H | Single CAN port | Almost certainly the GCU's link to one of the ECU's two CAN channels (see §2) — exact channel not traced |
| J5-21/22 ("D"/"E") | Digital inputs | Wired to **OVERRIDE SS SW `-S7`** | Matches `ecu-pinout-extracted.md`'s note that ECU pin 24 ("OVERSIDE SWITCH") traces via harness connectors XC1/XC11 to the same `-S7 Override SS SW` component — **this is a shared physical switch, not two different switches**, and per the pinout doc it is explicitly **not** a dedicated overspeed switch: *"OVERSIDE SWITCH (pin 24) and Override SS SW -S7 are the same component. There is no separate overspeed switch."* |

**What actually executes cranking — inferred, not fully traceable:** `ecu-pinout-extracted.md` lists ECU pin 50 (`MAIN RELAY`) as a **low-side output from the ECU itself**, and separately names a starter (`8STR1`) with its own solenoid (`-SOL`) among the panel components. The most consistent reading of the two documents together is: the GCU's Ignition Relay output energizes the ECU (powers it up); the ECU then runs its own internal start sequence (preheat, fuel priming, crank-permission logic) and asserts its own `MAIN RELAY` output to engage the starter solenoid — i.e., **the GCU requests a start (by powering the ECU on) and the ECU executes it** (drives the actual crank relay), matching the brief's framing exactly. However, **the GCU's own "START RELAY" terminal (J2-3) has no confirmed downstream connection to any ECU pin in either document** — it may feed a separate/legacy manual-crank path, a crank-permissive input the pinout extraction didn't capture, or something not traceable without the full XC1/XC11 harness cross-reference (which page 1 of the wiring diagram, the page examined in most detail for this memo, does not itself contain — that harness detail lives on later pages not fully re-examined under this task's time budget). **Flagged as an open item**, not asserted as resolved.

---

## 4. What remains unknown

1. **No document titled specifically "KG640C" was found** — the MPU verdict and terminal architecture rest on a sibling "KG640" (non-CAN) manual plus the OEM wiring diagram's own KG640C block, not on a KG640C-specific manual. High confidence, not full confirmation.
2. **J1939 baud rate, engine-node source address, and the exact PGN set are not confirmed** — no KG640C CAN specification or DBC was located. Direct CAN bus logging off the existing panel is the fastest way to close this and should be prioritized over further document search.
3. **Which of the ECU's two CAN channels (55/77 or 87/86) physically connects to the GCU's single CAN port (J4, 13/14) is not established.** If the second channel is used for something else (a dealer diagnostic tool, telematics/remote-monitoring per KOEL's own marketing material mentioning a "remote monitoring system"), that has implications for whether diagnostic tooling can coexist with the GCU link without contention.
4. **The GCU's own "START RELAY" output (terminal J2-3) has no confirmed destination** — whether it reaches the ECU, the starter solenoid directly, or a legacy manual-start path is unresolved from the documents in hand.
5. **INR pricing for the two correctly-matched standalone overspeed modules (GAC SSW675, Murphy/Enovation HD9063) was not obtained** — both have confirmed Indian distributors but require a direct quote request.
6. **The "KG645" manual** (a possible CAN-capable sibling found via search, https://www.scribd.com/document/407079798/) was not retrieved in full this session and may resolve some or all of items 1–3 above if obtained.
7. As with Task 1, **a photograph of the physical KG640C rear terminal block would be the single most valuable piece of evidence** this design phase could still obtain — it would upgrade the MPU verdict from "inferred, high confidence" to "confirmed" in one image, and would likely also show CAN port labelling that clarifies item 3.

---

## Sources consulted (full list)

- `/home/mohan/workws/ecu25kva/refs/GP3.8703.C4.pdf` — OEM wiring diagram, page 1, rendered at 400 DPI and read directly (crops examined: KG640C block terminals J1–J8, in this session's scratchpad).
- `/home/mohan/workws/ecu25kva/refs/ecu-pinout-extracted.md` — ECU-side pin-level extraction of the same diagram, read in full.
- `/home/mohan/workws/ecu25kva/docs/research/01-engine-identity.md` — Task 1 memo, engine and controller identity.
- KOEL, "KG640 CONTROLLER MANUAL" / `SED-MAN-KG640-002`, 92 pages, retrieved via https://www.scribd.com/document/878092942/SED-MAN-KG640-002-Koel-Manual-for-KG640-Genset-Controller — read in full.
- KOEL, "KG645 Genset Controller User Manual," https://www.scribd.com/document/407079798/Kirloskar-KG645-User-manual-for-genset-controller-pdf — located, **not** retrieved in full (fetch returned only page metadata); flagged as an open lead.
- KOEL, "KG934V1 Genset Controller User Manual" (2010), https://5.imimg.com/data5/SELLER/Doc/2021/7/JH/DB/YP/28202182/kirloskar-green-kg934v1-genset-controller.pdf — located as an older/smaller sibling product during search, not used as evidence in this memo (different, smaller controller family).
- SmartGen (Zhengzhou) Technology Co., "HGM6100N Series Genset Controller User Manual" — pulled as a rebadge-comparison candidate; ruled out as the KG640C's underlying product per §1.
- Governors America Corp (GAC), SSW675 product page, https://www.governors-america.com/product/ssw675/ (direct fetch blocked by site; description obtained via search-result excerpt of the manufacturer's own page).
- Governors America Corp (GAC), ESD5500E documentation (via search snippet) — cited only to show GAC's own explicit statement that a separate overspeed shutdown device is required in addition to its analog governors.
- Enovation Controls (Murphy), HD9063/OS77D/SS300 product page, https://www.enovationcontrols.com/products/hd9063-os77d-and-ss300/ — fetched directly, specs quoted verbatim.
- IndiaMART listing, Spares Bazaar Pvt Ltd (New Delhi), GAC ESD5500E/ESD5111/ESD5550/ESD5221 at ₹9,500/piece, https://www.indiamart.com/proddetail/esd5500e-esd5111-esd5550-esd5221-gac-speed-control-unit-governor-america-corp-21293246791.html — cited only as order-of-magnitude brand/market context, not as pricing for the correct part (see caveat in the recommendation table).
- IndiaMART listing, Murphy By Enovation Controls (Pune), HD9063/OS77D/SS300, https://www.indiamart.com/proddetail/hd9063-os77d-and-ss300-electronic-speed-switches-15889251691.html — quote-only, no published price.
- `ikonnect.kirloskar.com` portal — checked for a KG640C-specific manual index; none exposed without authentication (consistent with Task 1's finding).
- General web searches (recorded for completeness, mostly negative or superseded by the direct fetches above): `Kirloskar KG640C manual`, `KG640C genset controller datasheet`, `KOEL KG640C wiring`, `Kirloskar KG640C manual J1939 CAN engine PGN`, `"KG640C" Kirloskar controller manual pdf`, `scribd "KG640C" OR "SED-MAN-KG640C" Kirloskar CAN J1939`, `GAC ESD5500 electronic overspeed shutdown device price India magnetic pickup`, `GAC ESD5111 electronic overspeed shutdown device specification magnetic pickup frequency`, `"Governors America" OR GAC overspeed shutdown device dedicated relay model number`, `GAC SSW675 speed switch price India`, `"SSW675" OR "SSW676" OR "speed switch" GAC indiamart price generator overspeed India`, `Murphy overspeed shutdown module magnetic pickup speed switch price India`, `Murphy OS77D speed switch India IndiaMART price`, `Murphy Enovation OS77D specification frequency input voltage amplitude magnetic pickup`, `Electra Brandt SSW675 price`.
