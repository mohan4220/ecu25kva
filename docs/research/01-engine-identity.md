# Research Memo 01: Engine Identity

**Task:** U11 (engine make/model/displacement/cylinder count/rated speed/emissions tier). Informs U8, U9.
**Date:** 2026-09-13
**Author:** Phase-1 research (task 1)

## Verdict

> ### SUPERSEDED 18 Sep 2026 — READ THIS FIRST
>
> The engine's rating plate has been photographed. It reads **`3GK550ETA 4SR1`**,
> application code **`GK3.8703`**, 26.5 kW / 36 hp at 1500 rpm, type approval
> `ARAI/MoEF/DGTA/IGES4/KOEL-P25/2825/24`, manufactured 12 Sep 2025.
>
> **This memo's model-number conclusion below is wrong.** It identified the
> engine as `3R550ETA 4G1` and explicitly rejected "GK550" as a garbled
> recollection of "KG4" + "550", advising that GK550 "should not be used as a
> search term or part-lookup key going forward". The original designation given
> to this project was right; this memo's inference was not.
>
> **What survives:** every hardware constraint in the Step 3 cross-check — three
> cylinders, common rail, turbocharged-aftercooled, cooled EGR with DOC and no
> SCR, 1500 rpm, CPCB IV+, 26.5 kW — matches the plate exactly. The reasoning
> from the wiring diagram was sound. What failed was the model-number
> identification built on top of it, which converged on a real Kirloskar engine
> that is not this one.
>
> **Also resolved:** this memo recorded as a negative result that "GP3 cannot be
> resolved to a specific engine model or family". It is a project/application
> code — the wiring diagram is `GP3.8703.C4.pdf` and the engine's serial number
> begins `GK3.8703/`. The 8703 matches.
>
> Evidence: [`refs/field-evidence-2026-09-18.md`](../../refs/field-evidence-2026-09-18.md).
> **U11 is closed**, by plate rather than by inference.

## Verdict (as originally written, superseded above)

The engine is almost certainly the **Kirloskar 3R550ETA 4G1** (Kirloskar "R550" family, 3-cylinder, 1.65 L, turbocharged-aftercooled, common-rail, cooled-EGR + DOC), as fitted to the **Kirloskar KG4-25WS1** 25 kVA CPCB IV+ genset. Every hardware constraint from the wiring-diagram cross-check (Step 3) is satisfied, and the genset controller named in the OEM brochure (KG640C) is the exact same controller named in the OEM wiring-diagram extraction. This is treated as **inferred with high confidence** rather than **confirmed**, because no single primary source explicitly states "manual 08-GP3-60-001 / file GP3.8703.C4.pdf belongs to engine 3R550ETA 4G1" — the identification is a convergence of independent documents, not a direct statement. A rating-plate photograph (see "What would close this," below) would upgrade this to confirmed.

"GK550" as reported by the user does not match any Kirloskar Oil Engines (KOEL) designation found in searching. It is most plausibly the user's own conflation of the genset model prefix **KG4** and the engine family number **550** — but this is speculation on my part, not a sourced fact, and is flagged as such.

---

## Step 1: What does "GK550" designate?

Searched: `Kirloskar GK550`, `Kirloskar Green GK 550 25 kVA genset`, `KOEL GK550 25 kVA diesel genset specification`, `"GK550" Kirloskar engine OR genset OR generator`, `Kirloskar "GK" series genset air-cooled OR water-cooled kVA range`.

**Result: no primary source uses the string "GK550."** No Kirloskar Oil Engines product page, brochure, distributor listing, or spare-parts catalogue found in this search returned that exact designation. *(Negative result — searched via general web search, no domain restriction, September 2026.)*

One lead was run down and ruled out:
- ManualsLib lists a document titled "KIRLOSKAR GK SERIES INSTRUCTION ON INSTALLATION, OPERATION AND MAINTENANCE" (https://www.manualslib.com/manual/1698613/Kirloskar-Gk-Series.html). Search-result snippets describe this as covering Kirloskar pump type **GK(P)** — a **Kirloskar Brothers Limited** (pumps) product, not a Kirloskar Oil Engines (engines/gensets) product. These are different companies under the Kirloskar Group umbrella. **Ruled out** — different Kirloskar Group entity, wrong product category. *(Confirmed via search-result description; the page itself returned HTTP 403 to direct fetch and could not be read in full.)*

What KOEL genset/engine naming actually looks like, established from primary sources fetched directly:
- Genset models use a **`KG<n>-<kVA><suffix>`** pattern, e.g. **KG4-25WS1** (25 kVA), KG4-30WS1, KG4-40WS1, KG4-58.5WS (all from the same brochure) — source: Kirloskar Oil Engines, "CPCBIV+ COMPLIANT — INDIA'S LARGEST FLEET OF GENSETS 25-58.5 kVA," https://www.kirloskaroilengines.com/documents/541738/2079942/2_A4_CPCB+IV+25-58.5+kVA.pdf (downloaded and text-extracted directly; doc ref `20240610/REV01/A4 CPCB IV+25-82.5 kVA`, footer code `IBG.V.045 Rev0`). **Confirmed.**
- Engine models use an **`<cyl>R<displacement-code><aspiration><generation>`** pattern, e.g. **3R550ETA 4G1** (3-cylinder, "550" family, Electronic-governed, Turbocharged-Aftercooled, generation suffix "4G1") for the 25 kVA genset in the same brochure. Source: same PDF, table row "ENGINE / Engine Model." **Confirmed.**
- A related, non-genset-specific brochure from Kirloskar Americas (https://www.kirloskaramericas.com/documents/5928996/5929154/Kirloskar+R550+G+Drive+Brochure+25052022+Rev0.pdf — downloaded directly) lists the bare engine-platform naming: **2R550NA, 3R550NA, 3R550TC, 3R550TA** — i.e., "R550" is the engine *platform* name, and the suffix encodes cylinder count and aspiration. **Confirmed.**

**Working hypothesis (inferred, not sourced):** the user's "GK550" is most likely a garbled or telescoped memory of **"KG4"** (the genset-model prefix) and **"550"** (the engine-family number that actually appears in the engine model string, 3R**550**ETA), possibly by transposing K/G. I found no evidence this is an official SKU, a genset model, or a Kirloskar Green product code in its own right. It should not be used as a search term or part-lookup key going forward — use **KG4-25WS1** (genset) and **3R550ETA 4G1** (engine) instead.

---

## Step 2: Working backwards from the manual number

Manual number `08-GP3-60-001`, file `GP3.8703.C4.pdf`, served from `https://ikonnect.kirloskar.com/KOEL/Services/TroubleShootingWiringDiagram?manualName=08-GP3-60-001` (confirmed present in the PDF's own footer on every page, verified via `pdftotext` extraction of the source file).

Attempts made:
- Fetched `https://ikonnect.kirloskar.com/KOEL/Services/TroubleShootingWiringDiagram` (no query string) directly — connection failed (no response body; the endpoint requires the `manualName` parameter and/or an authenticated session).
- Fetched `https://ikonnect.kirloskar.com/KOEL` (portal home) — retrieved (22 KB), but it is a login/marketing shell with no manual index; no list of manual-family codes is exposed to an unauthenticated fetch.
- Searched `Kirloskar "GP3" engine family diesel`, `Kirloskar "GP3" ECU OR "engine control unit" wiring diagram manual`, `"08-GP3-60-001" Kirloskar`, `Kirloskar "GP3" platform OR series diesel engine common rail EGR CPCB` — **no result anywhere maps "GP3" to a specific engine model or family.** *(Negative result.)*
- Read the wiring diagram itself in full (`pdftotext -layout` extraction of `/home/mohan/workws/ecu25kva/refs/GP3.8703.C4.pdf`, all 5 pages) — it does not state an engine model number anywhere in its body text. It is a browser print-to-PDF of the ikonnect portal page (page metadata shows a print timestamp), consistent with the note already recorded in `ecu-pinout-extracted.md` that the diagram is troubleshooting-oriented and does not carry a full connector/engine cross-reference.

**Conclusion: "GP3" cannot be resolved to a specific engine model or family from public sources.** *(Negative result — this closes off Step 2 as originally scoped.)* A plausible but **unconfirmed and unsourced** guess: KOEL's CPCB IV+ genset range (7.5–800 kW) uses the same control architecture (common rail, cooled EGR, DOC, KG640C controller) across several engine displacements (R550, R1040/R1190, R810, per the CPCB IV+ 25-58.5 kVA brochure), so "GP3" may denote a shared ECU/wiring *platform generation* spanning multiple engine sizes rather than one engine. This would explain why the diagram itself carries no engine-specific model text — it may be reused, with only the pin count and sensor complement varying by engine. This is **speculation, explicitly not a finding**, and should not be treated as established.

---

## Step 3: Cross-check against the hardware evidence

Per the brief, a valid candidate must match **all five** of: 3 cylinders; common-rail; EGR fitted; catalyst temp sensor present but no SCR/DEF; 12 V electrical system. Evidence for each column below is drawn directly from `/home/mohan/workws/ecu25kva/refs/ecu-pinout-extracted.md` (hardware) and the KOEL CPCB IV+ 25-58.5 kVA brochure (candidate engine spec, downloaded and extracted directly from `https://www.kirloskaroilengines.com/documents/541738/2079942/2_A4_CPCB+IV+25-58.5+kVA.pdf`).

| Constraint | Wiring-diagram evidence | 3R550ETA 4G1 (candidate) | Match |
|---|---|---|---|
| 3 cylinders | Injector bank wiring: cyl 1/2/3, pins 03/05/73/07/29 (pinout doc, "Injectors" section) | "No. of cylinder: 3" (brochure table) | **Match — confirmed** |
| Common-rail | Rail pressure sensor (pins 32/35/08) + PWM-driven fuel metering unit (pin 88) (pinout doc, "Analog sensors" and "Outputs") | CRDi (Common Rail Direct Injection); brochure narrative: "High pressure common rail system employed on Kirloskar CPCB IV+ Gensets" | **Match — confirmed** |
| EGR fitted | Dedicated EGR position sensor (pins 15/37/36) and EGR H/L bridge-driven actuator output (pins 59/81) (pinout doc, "Analog sensors" and "Outputs") | "EGR System used to reduce the level of NOx emitted by Engine" (brochure feature callout) | **Match — confirmed** |
| Catalyst temp sensor present, no SCR/DEF | Catalyst Temperature Sensor connector present in connector appendix (2-pin, one only); pinout doc's "Absent from the entire system" section: "No DEF/urea sensor... No SCR" | Brochure lists **DOC** ("DOC system sets off the reaction to meet the CPCB norms") for this kVA family; **no SCR or DEF mentioned anywhere** in the 25–58.5 kVA brochure | **Match — confirmed** |
| 12 V electrical system | Battery+ feed pins 04/06/21, all via fused red supply; no 24 V evidence anywhere in diagram | "Electrical Battery Start in R Voltage: 12 Volts-DC" (brochure); user-reported 12 V/75 Ah battery | **Match — confirmed** |

All five constraints are satisfied simultaneously by only one engine in the brochure's four-model 25–58.5 kVA lineup (the other three — 3R1190ENA, 3R1190ETA, 4R810ETA — are 30/40/58.5 kVA respectively, not 25 kVA, and one is naturally aspirated, so they fail on rated output alone even before considering hardware detail). **This is the strongest evidence in the memo** and is why the identity is called "inferred with high confidence" rather than a bare guess.

**Independent corroboration found during this cross-check (not requested by the task, but material):** the pinout extraction names the genset control unit as **Kirloskar KG640C** (`ecu-pinout-extracted.md`, "Other system components named"). The CPCB IV+ 25-58.5 kVA brochure independently names its standard controller as the **KG640C Controller** (same PDF, "State of the art Genset Controller" section, pictured with a photo captioned "KG640C Controller"). Two independently-obtained documents (a scraped OEM troubleshooting diagram, and a public marketing brochure) naming the identical, fairly specific controller part number is strong circumstantial confirmation that the wiring diagram belongs to this genset family. **Confirmed** (both documents state the KG640C designation directly; the *inference* is that they describe the same unit).

---

## Step 4: Emissions tier

**CPCB IV+** is confirmed as the applicable tier for this class of genset:

- Regulatory basis: **GSR 804(E), dated 3 November 2022**, Ministry of Environment, Forest and Climate Change — "Emission limits for new internal combustion engine up to 800 kW gross power used for power generating set (Genset) application," commonly referred to as the CPCB IV+ regulation. *(Confirmed via independent secondary source: https://www.ricago.com/blog/revised-emission-standards-for-gensets-a-step-towards-cleaner-air, which states the GSR number and date; corroborated by a second secondary source in the same search. Primary source page https://cpcb.gov.in/genset-notifications/ (redirected from `cpcb.nic.in`) confirms the base notification chain "GSR 771(E) dated 11 Dec 2013" and its amendments exist at CPCB, but its listing text as fetched did not expose the GSR 804(E) reference by name — flagged as a fetch limitation, not a contradiction.)*
- Effective/compliance date: 1 July 2023 (secondary sources; not independently verified against gazette text).
- Power-band limits (19–56 kW band, which contains this engine's 26.5 kW prime rating): PM ≤ 0.03 g/kWh, combined NOx+HC ≤ 4.7 g/kWh, CO ≤ 3.5 g/kWh, smoke ≤ 0.7 — per dieselnet.com's published summary table of the 2022/2023 Indian genset standard (https://dieselnet.com/standards/in/genset.php). **Inferred/secondary-sourced** — dieselnet is a respected industry standards clearinghouse but this is not the gazette text itself.
- The genset manufacturer's own literature states this engine/genset combination is CPCB IV+ certified and uses cooled EGR + DOC (no SCR, no DPF mentioned) to meet it — consistent with the 19–56 kW band not requiring the separate, stricter NOx-only limit (0.40 g/kWh) that appears at the 56–560 kW band, where SCR is more commonly needed to hit the tighter NOx number. This is **inferred**: no source states "this band never needs SCR," but the absence of SCR/DEF hardware, plus the combined NOx+HC limit form used below 56 kW, is internally consistent with why KOEL doesn't fit SCR to this genset size.

**Implication for aftertreatment scope (informs U8):** design should assume a **DOC-only aftertreatment path with cooled EGR** — no SCR, no DEF/urea system, no DPF regeneration logic. This matches the hardware evidence exactly (single catalyst-temperature-sensor connector, no urea pump/quality sensor anywhere in the harness).

---

## Step 5: Summary — engine identity record

| Field | Value | Status | Source |
|---|---|---|---|
| Engine make | Kirloskar (Kirloskar Oil Engines Ltd, KOEL) | Confirmed | KG4-25WS1 brochure (below) |
| Engine model | 3R550ETA 4G1 (OCR'd in one source as "3R55OETA 4G1" — "O"/"0" artifact) | Inferred, high confidence (see Step 3) | Kirloskar Oil Engines CPCB IV+ 25-58.5 kVA brochure, https://www.kirloskaroilengines.com/documents/541738/2079942/2_A4_CPCB+IV+25-58.5+kVA.pdf ; corroborated by https://www.indiamart.com/proddetail/kirloskar-kg4-25ws1-diesel-generator-2854043860488.html |
| Engine platform/family | "R550" (Kirloskar's own naming) | Confirmed | Kirloskar Americas R550 G-Drive brochure, https://www.kirloskaramericas.com/documents/5928996/5929154/Kirloskar+R550+G+Drive+Brochure+25052022+Rev0.pdf |
| Genset model | KG4-25WS1 | Confirmed | Kirloskar Oil Engines CPCB IV+ 25-58.5 kVA brochure (above); indiamart listing (above) |
| Displacement | 1.65 L (1,650 cc, 3-cylinder) | Confirmed | Kirloskar Oil Engines CPCB IV+ 25-58.5 kVA brochure (above); cross-checked arithmetically: 86 mm bore × 94 mm stroke × 3 cyl ≈ 1,638 cc, consistent with rounded 1.65 L spec |
| Bore × stroke | 86 mm × 94 mm | Confirmed | Kirloskar Americas R550 G-Drive brochure (above) |
| Cylinder count | 3 (inline) | Confirmed | Kirloskar Oil Engines CPCB IV+ 25-58.5 kVA brochure (above); matches wiring-diagram injector wiring (cyl 1/2/3) |
| Compression ratio | 19.7:1 | Confirmed | Kirloskar Americas R550 G-Drive brochure (above) |
| Aspiration | Turbocharged, aftercooled (TA) | Confirmed | Both Kirloskar brochures (above) |
| Rated speed | 1500 rpm | Confirmed | Kirloskar Oil Engines CPCB IV+ 25-58.5 kVA brochure (above) — matches 50 Hz expectation from the brief |
| Rated output | 26.5 kW / 36 HP prime, per ISO 8528-1 | Confirmed | Kirloskar Oil Engines CPCB IV+ 25-58.5 kVA brochure (above) |
| Genset rated output | 25 kVA prime, 20 kW, 0.8 PF, 50 Hz, 230 V(1φ)/415 V(3φ) | Confirmed | Same brochure |
| Fuel injection | Common rail direct injection (CRDi), electronic governor | Confirmed | Same brochure; hardware corroboration via rail pressure sensor + PWM fuel metering unit in pinout doc |
| EGR | Cooled EGR fitted | Confirmed | Same brochure; hardware corroboration via EGR position sensor + EGR actuator pins in pinout doc |
| Aftertreatment | DOC only; no SCR, no DEF, no DPF mentioned | Confirmed (absence) | Same brochure narrative; hardware corroboration via single catalyst-temp-sensor connector and complete absence of urea/SCR hardware in pinout doc |
| Emissions tier | CPCB IV+ (GSR 804(E), 3-Nov-2022; effective 1-Jul-2023) | Confirmed regulation exists; inferred that this specific unit is certified to it (brochure says so but I have not seen a type-approval certificate) | Brochure states CPCB IV+ compliance; GSR number/date per https://www.ricago.com/blog/revised-emission-standards-for-gensets-a-step-towards-cleaner-air ; band limits per https://dieselnet.com/standards/in/genset.php |
| Genset controller | Kirloskar KG640C | Confirmed | Both the wiring-diagram pinout extraction and the CPCB IV+ brochure name this controller independently |
| Battery | 12 V DC starting | Confirmed | Brochure ("Electrical Battery Start in R Voltage: 12 Volts-DC"); matches user-reported 12 V system |
| Battery Ah | User reports 75 Ah; generic Kirloskar Americas R550 brochure lists 65 Ah for the bare-engine starter spec; a KOEL-Green-branded 12 V/75 Ah battery (part 02.709.24.0.Pr, model 75D31R-A) is sold as a genuine Kirloskar spare | Inferred (discrepancy noted, not resolved) | Kirloskar Americas R550 G-Drive brochure (65 Ah, generic/global engine-only spec); https://www.safesparesonline.com/product/kirloskar-genuine-02-709-24-0-pr-12v-dc-75ah-lead-acid-koel-green-battery-model-75d31r-a/ (75 Ah, India-market genuine part) |
| OEM ECU part number | Not found | Not established | See Step 2 — no source ties a Bosch/Continental/etc. ECU part number to this engine or to manual `08-GP3-60-001` |
| ECU manual/family code | `08-GP3-60-001` / "GP3" — meaning of "GP3" not established | Not established | See Step 2 (negative result) |

---

## What would close this — the one photograph that settles it

The engine's own **rating plate** (usually riveted to the rocker cover, flywheel housing, or side of the cylinder block) would resolve every remaining "inferred" item above in one shot. Specifically, photograph it so the following are legible:

1. **Engine model string** — should read something matching `3R550ETA` (or a close variant) if this identification is correct. If it instead reads e.g. `3R1040...` or a different family entirely, this whole identification is wrong and should be discarded rather than patched.
2. **Serial number** — allows a direct KOEL/dealer parts-catalogue or warranty lookup, independent of any web search.
3. **Rated output, rated speed, and frequency** stamped on the plate — cross-check against the 26.5 kW / 1500 rpm / 50 Hz figures above.
4. **Emission certification marking** if present (CPCB IV+ or equivalent BEE/ARAI type-approval sticker) — would directly confirm Step 4 rather than relying on brochure-level marketing claims.
5. **The genset's own nameplate** (usually on the canopy or control panel, separate from the engine plate) — should read `KG4-25WS1` or a close variant if this identification is correct, and will separately carry the genset serial number, which is the cleanest path to an authoritative KOEL parts/spec lookup via an authorized dealer or KOEL Care.

Absent that photograph, treat every "inferred" row above as provisional. The hardware cross-check in Step 3 is strong (five independent constraints all satisfied by exactly one candidate in the only public document that lists 25 kVA CPCB IV+ engines), but it is still an inference from convergence, not a direct statement of identity from a primary source that names manual `08-GP3-60-001` and engine `3R550ETA 4G1` in the same document.

---

## Sources consulted (full list)

- `/home/mohan/workws/ecu25kva/refs/GP3.8703.C4.pdf` — OEM wiring diagram, manual `08-GP3-60-001`, read in full via `pdftotext -layout`.
- `/home/mohan/workws/ecu25kva/refs/ecu-pinout-extracted.md` — pin-level extraction of the above, read in full.
- Kirloskar Oil Engines, "CPCBIV+ COMPLIANT — INDIA'S LARGEST FLEET OF GENSETS 25-58.5 kVA": https://www.kirloskaroilengines.com/documents/541738/2079942/2_A4_CPCB+IV+25-58.5+kVA.pdf — downloaded directly and text-extracted in full (283 lines).
- Kirloskar Americas, "R550 G-Drive" brochure: https://www.kirloskaramericas.com/documents/5928996/5929154/Kirloskar+R550+G+Drive+Brochure+25052022+Rev0.pdf — downloaded directly and text-extracted in full (blocked to the WebFetch tool with HTTP 403; retrieved successfully via direct HTTP GET).
- https://www.kirloskaroilengines.com/products/power-gen/genset/lhp/diesel-generators/25-kva-diesel-genset — fetched, gives KG4-25WS1 and engine model 3R550ETA 4G1.
- https://www.indiamart.com/proddetail/kirloskar-kg4-25ws1-diesel-generator-2854043860488.html — fetched, corroborates engine model, rated speed 1500 rpm, CRDi, EGR+DOC/CPCB IV+.
- https://www.indiamart.com/proddetail/kirloskar-3r550-engine-2850959578848.html — fetched, US-market bare-engine listing corroborating 3-cylinder, ~1.64 L (100 cu in), NA/TC/TA variants.
- https://www.safesparesonline.com/product/kirloskar-genuine-02-709-24-0-pr-12v-dc-75ah-lead-acid-koel-green-battery-model-75d31r-a/ — found via search, corroborates a 12 V/75 Ah Kirloskar Green genuine battery part exists in the India market.
- https://www.manualslib.com/manual/1698613/Kirloskar-Gk-Series.html — found via search, used to rule out "GK Series" as a Kirloskar Brothers pump line unrelated to this engine (page itself returned HTTP 403 on direct fetch; ruled out based on search-result description only — flagged as weaker evidence).
- https://ikonnect.kirloskar.com/KOEL/Services/TroubleShootingWiringDiagram (no query) and https://ikonnect.kirloskar.com/KOEL — fetched directly; no manual-family index exposed without authentication.
- https://dieselnet.com/standards/in/genset.php — fetched, CPCB IV+ power-band emission limits table.
- https://cpcb.gov.in/genset-notifications/ (redirected from https://cpcb.nic.in/genset-notifications/) — fetched, confirms existence of the GSR 771(E)/2013 notification chain and its amendments; did not by itself surface the GSR 804(E)/2022 CPCB IV+ reference.
- https://www.ricago.com/blog/revised-emission-standards-for-gensets-a-step-towards-cleaner-air — fetched, states GSR 804(E) dated 3 November 2022 as the CPCB IV+ notification.
- General web searches (not individually cited above where they returned only negative results or were superseded by direct fetches): `Kirloskar GK550`, `Kirloskar Green GK 550 25 kVA genset`, `KOEL GK550 25 kVA diesel genset specification`, `Kirloskar "GP3" engine family diesel`, `ikonnect.kirloskar.com TroubleShootingWiringDiagram manualName`, `Kirloskar "3R550ETA" engine specifications`, `Kirloskar "R550" OR "3R550" displacement bore stroke cc`, `site:kirloskaramericas.com R550`, `Kirloskar R550 engine "1500 rpm" OR "1800 rpm" kW genset industrial`, `Kirloskar "GP3" ECU OR "engine control unit" wiring diagram manual`, `"08-GP3-60-001" Kirloskar`, `CPCB IV+ norms diesel genset 19-56 kW NOx PM DOC EGR SCR requirement notification date`, `CPCB IV+ GSR notification number "3rd November 2022" gensets gazette`.
