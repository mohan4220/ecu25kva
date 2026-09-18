# Research Memo 03: ECU Connector Identification

> ### U1 CLOSED, 18 Sep 2026 — this memo's leading candidate is confirmed
>
> The connector has been photographed with its markings legible. It carries the
> **Bosch** name and armature logo, part numbers **`1 928 405 192`** and
> **`1 928 405 194`**, **`code C`**, and `2.7`. The face-on photograph shows 94
> cavities in two chambers: 8 large power contacts (1–8) plus four fine rows
> numbered 9–28, 29–50, 51–72, 73–94.
>
> **This memo ranked "Bosch EDC17-style 94-pin" as the leading candidate on
> inference. Confirmed, with part numbers read off the physical part.**
>
> One detail this memo did not anticipate: `code C` is a **mechanical coding
> variant**. Bosch supplies these housings in coded versions that will not mate
> across codes, so any replacement or adapter housing must be code C.
>
> A search for the two part numbers returned no direct catalogue hit, so sourcing
> should go through a Bosch distributor quoting the numbers rather than a search
> engine. The shortlist and sourcing analysis below remain useful for that
> conversation.
>
> Evidence: [`refs/field-evidence-2026-09-18.md`](../../refs/field-evidence-2026-09-18.md).


**Task:** U1 (ECU connector part number / mating-half sourcing), partial closure — full closure needs a photograph. Consumes Task 1 (engine identity). Feeds the adapter-harness deliverable (spec §7.1).
**Date:** 2026-09-13
**Author:** Phase-1 research (task 3)
**Engine/genset:** Kirloskar 3R550ETA 4G1 / KG4-25WS1, per `docs/research/01-engine-identity.md` (inferred, high confidence).

---

## Verdict (read this first)

The OEM ECU part number **could not be established** — same negative result already recorded in `01-engine-identity.md`, Step 2, and not re-openable with the sources available here. What this memo adds is a **physical characterisation of the 94-pin ECU connector** from the wiring diagram, and a **ranked shortlist of connector families** that plausibly match it, each with a buyability verdict for India. No part number is asserted with confidence — per the task's own framing, a line drawing cannot support that, and a confident wrong connector is worse than an honest shortlist.

| Rank | Family | Visual match | Buyable in India | Verdict |
|---|---|---|---|---|
| 1 | **Bosch EDC17/EDC15/EDC16-style 94-pin ECU connector** (TE-Connectivity-built, Bosch-proprietary tooling) | Strong — pin count exact, mixed large/small contact pattern plausible, widely used on Bosch common-rail diesel ECUs of this class | **Yes, but only through the automotive ECU-repair/chiptuning aftermarket, not mainstream component distributors** — order via specialty ECU-connector shops (international, ships to India) | **Leading candidate — photograph required to confirm** |
| 2 | **Aptiv/Delphi GT-series (150-position family) rectangular multi-row connector** | Moderate — rectangular, multi-row, mixed contact sizes are a documented feature of this family; exact 94-position variant not confirmed | **Yes** — stocked by Mouser (mainstream distributor with an India storefront) | Plausible alternate |
| 3 | **TE Connectivity AMPSEAL (16/23/35/direct-descendant 90-series)** | Weak — AMPSEAL housings are characteristically oval/rounded single-lever shells; the PDF drawing shows a rectangular, sharp-cornered, multi-row grid that fits this family less well | **Yes** — mainstream Mouser/DigiKey stock | Weakest visual fit of the three buyable candidates |
| — | Molex CMC / high-density cylindrical automotive headers | Ruled out — CMC-family connectors are round/cylindrical pin-and-socket bundles, not a flat rectangular multi-row grid | N/A | **Ruled out on shape alone** |

**None of these is asserted as "the" connector.** All three buyable candidates are plausible; the photograph brief (final section) is designed to distinguish them in a single site visit.

---

## Step 1: What the wiring diagram actually shows

Source: `refs/GP3.8703.C4.pdf`, page 4, "Engine Control Unit Connector" panel (one of six connector-detail panels on that page), re-rendered at 400 dpi with `pdftoppm` and cropped with PIL for close reading.

**Confirmed directly from the drawing:**
- The connector is drawn as **one single housing outline** (one continuous molded shell in the 2D projection) — not two or three physically separate ganged blocks side by side. Pins 1–94 are called out on this one outline.
- The pin field is arranged as **four rows** of small, evenly pitched square contacts, split top/bottom: an upper pair of rows (running from a low pin number near "7" up to "28" at the top-right corner) and a lower pair of rows (running from "73" at bottom-left to "94" at bottom-right corner). This matches `refs/ecu-pinout-extracted.md`'s statement that the connector is 94-pin.
- At the **top-left and bottom-left corners**, outside the dense small-pin grid, sit two separate 2-contact clusters, individually labelled "PIN NO.1" (top) and "PIN NO.5" (bottom). These two clusters are drawn with the **identical stepped-rectangle pin symbol** used elsewhere on the *same PDF page* for the standalone 2-pin **Fuel Pump Connector** and **Charging Alternator Connector** panels — both of which are physically large, single-current-path power/current connectors in this harness. **Inferred** (by direct comparison of drawing conventions within one source document, not an explicit label): pins 1, 2, 5, 6 are drawn as large/keyed contacts, distinct in kind from the ~88 small pins in the main grid. This is consistent with the brief's expectation that a 94-pin automotive ECU header of this class mixes large power/injector contacts with small signal contacts in one shell.
- Between the upper and lower row-pairs, **four elongated rectangular features** run across the housing's mid-band. None of them carries a pin number anywhere in the source (every actual contact in this diagram set is numbered). **Inferred:** these are molded polarization/alignment ribs in the plastic shroud (a standard feature on wide, high-pin-count automotive headers to prevent pin damage on blind mating), not additional large contacts.
- On the **right-hand (mating/cable) side** of the housing, the outline shows a curved, bowed wall plus two small rectangular tabs protruding further right than the main shell, near the top-right and bottom-right corners. **Inferred, not confirmed:** this is most consistent with pivot bosses and body of a **lever-actuated latch** (used on high pin-count automotive connectors to provide the large mating force ~94 contacts require) — but a cable-entry strain-relief boot is a plausible alternative reading of the same 2D outline, and the drawing does not disambiguate. This is the single largest open question the photograph needs to resolve.
- Small rectangular tabs are also present at even intervals along the top and bottom edges of the housing (visible in the full-page crop) — consistent with either mounting/latch-catch features or additional polarization ribs; not resolvable further from a line drawing.
- **Not a housing marking:** the "Kirloskar / Oil Engines" watermark visible across the page image is the ikonnect web portal's page watermark (confirmed present on every page of this browser-printed PDF, per `01-engine-identity.md` Step 2), not a molded marking on the physical connector. This is flagged explicitly so it is not mistaken for a part marking later.

**What the drawing does not show and cannot be inferred:** exact housing dimensions, contact pitch, wire-seal type (individual seals vs. a single mat seal), material/color, or any molded part number/logo. `refs/ecu-pinout-extracted.md` already records that only 44 of the 94 pins are traceable to a signal in the wiring diagram; the connector-detail panel on page 4 is a generic "how to count pins" reference (it exists to let a technician find pin 1/5/28/73/94 as anchor points), not a manufacturer datasheet.

---

## Step 2: Candidate families, ranked, with reasoning

### 1. Bosch EDC15/EDC16/EDC17-style 94-pin ECU connector (leading candidate)

- **Why it's plausible:** The pin count (94) is an exact match, not just "in the ballpark" — multiple independent listings in the automotive ECU-repair/chiptuning aftermarket specifically describe a "Bosch EDC17 94-pin" (and a companion 60-pin, for two-connector EDC17 variants) ECU connector, sold as bench/pigtail cable kits: e.g. u-obd.com ("BOSCH EDC17 Connector 94 PIN 60 PIN plug cable set full PIN wired," https://www.u-obd.com/product/edc17-connector/, US$99), ecudepot.com (same product, https://ecudepot.com/product/bosch-edc17-connector/), autoecupart.net (multiple listings, e.g. https://www.autoecupart.net/products/original-full-94-pin-connector-for-bosch-edc17-electronic-control-unit-ecu), and eBay listings (e.g. https://www.ebay.com/itm/265128037857 "OEM Full 94 Pin Connector for Bosch ME17.9.11 EDC17"). **Confirmed:** a documented, commercially available "Bosch 94-pin" ECU connector family exists and is actively sold as a discrete product. **Not confirmed:** that this specific family is the one on the Kirloskar genset — no source ties a Bosch part number to manual `08-GP3-60-001` or to this engine.
- **Corroborating context from this project's own prior research (not new evidence, but relevant):** `docs/research/04-injector-drive.md` independently concludes the injector architecture is most likely a Bosch solenoid common-rail family (CRIN2/CRIN3-class), based on wiring-diagram evidence (rail-pressure sensor + PWM metering-unit pattern) and Kirloskar's confirmed practice of re-badging genuine Bosch injectors under Kirloskar part numbers for at least one other engine family (Bosch 0445120646 = Kirloskar F6.248.08.0.pr). If the injectors are Bosch, an ECU built around a Bosch-family connector (rather than a mixed-vendor harness) is the more parsimonious assumption — **inferred, not a separate confirmed fact.**
- **Retention/shape match:** the EDC15/16/17 94-pin housing family is documented in the tuning trade as using a mixed grid of small signal pins with a smaller number of larger power/injector pins in one shell, closely matching the page-4 drawing's large-corner-pair-plus-dense-grid layout described in Step 1. This comparison is based on general familiarity with these connectors in the aftermarket record, not a side-by-side dimensioned drawing — **inferred, moderate confidence.**
- **Buyability (India):** **Yes, but not through a normal electronic-component distributor.** No listing was found on Mouser India, DigiKey India, or Element14 for a "Bosch EDC17 94-pin" connector under any manufacturer part number — searches for a TE Connectivity part number tied to this housing returned no result (**negative result**). It is however readily orderable from the international automotive ECU-repair trade (u-obd.com, ecudepot.com, autoecupart.net, eBay/AliExpress sellers), all of which ship internationally including to India, typically **US$65–99 per full connector-pair kit** (94-pin + companion 60-pin, wired pigtail) plus international shipping and India customs duty/GST on import (landed cost not independently verified — treat the $65–99 base figure as confirmed-at-source, the India-landed total as **unverified, order-of-magnitude estimate only**). This satisfies "a connector we cannot buy is not a candidate" — it is buyable — but the sourcing channel is the aftermarket repair trade, not a component distributor, which has implications for lead time, quality/counterfeit risk, and lack of a formal datasheet.

### 2. Aptiv/Delphi GT-series rectangular multi-row connector (150-position family)

- **Why it's plausible:** The GT150 family is a genuine, rectangular, multi-row automotive ECU/PCM connector platform distributed through mainstream channels (Mouser lists it directly: https://www.mouser.com/Delphi-Connection-Systems/Connectors/Automotive-Connectors/GT-150-Series/, and specialist motorsport/ECU-wiring shops such as Corsa Technic and Waytek Wire stock GT150 housings, terminals, and seals across a range of position counts). Its general silhouette — rectangular shell, dense rows of small pins with provision for larger power contacts in the same housing family — is structurally similar to what the page-4 drawing shows. **Confirmed:** this connector family exists, is rectangular/multi-row, and is mainstream-distributor-stocked.
- **What is not confirmed:** whether a 94-position GT-series variant exists and matches the specific layout (four small-pin rows plus two 2-large-pin corner blocks) seen on page 4. This was not verified in this pass — **negative result, flagged as an open item**, not a ruled-out candidate.
- **Buyability (India):** **Yes** — Mouser operates an India storefront with INR pricing and ships GT-series connectors; DigiKey/Element14 India stock was not separately checked in this pass (**not verified**, time-boxed). Exact INR unit pricing for a 94-position variant was not obtained in this pass — recommend confirming against Mouser India's live catalog once/if this candidate is pursued further.

### 3. TE Connectivity AMPSEAL (90-series descendants)

- **Why it's a weaker fit:** AMPSEAL is a genuinely mainstream, India-buyable automotive sealed-connector family (Mouser lists the series directly: https://www.mouser.com/en/c/connectors/automotive-connectors/?m=TE+Connectivity&series=AMPSEAL) and is used on some diesel ECUs. But the AMPSEAL housing silhouette is characteristically **oval/rounded with a single center or side lever**, single or double staggered pin rows — not the sharp-rectangular, four-row, dense micro-pin grid with two separate large-pin corner clusters that page 4 shows. **Inferred:** shape mismatch downgrades this candidate relative to #1 and #2, even though it is the easiest of the three to actually buy through normal distribution.
- **Buyability (India):** **Yes, straightforwardly** — standard Mouser/DigiKey stock, no aftermarket-only caveat. This is the safest fallback if the photograph rules out #1 and #2.

### Ruled out: Molex CMC and similar high-density cylindrical automotive headers

Molex's CMC (and comparable high-pin-density automotive families built around round/cylindrical pin-and-socket bundles rather than a flat rectangular grid) do not match the page-4 drawing's flat, rectangular, multi-row silhouette at all. **Ruled out on shape alone** — no further sourcing work done on this family. *(Negative result, recorded per the global instruction that negative results are results.)*

---

## Step 3: Sourcing summary table

| Candidate family | Housing/mating-half source | Contacts/seals source | Price (as found) | India availability | Buy verdict |
|---|---|---|---|---|---|
| Bosch EDC15/16/17 94-pin (+60-pin companion) | u-obd.com, ecudepot.com, autoecupart.net, eBay sellers (aftermarket ECU-repair trade) | Bundled with the wired pigtail kits above; loose terminals also listed separately on some of the same sites | US$65–99 per kit (source-confirmed); India-landed cost incl. shipping/duty **not verified, estimate only** | Yes, via international aftermarket shipping — **not stocked by Mouser/DigiKey/Element14 India** (checked, negative result) | **Buyable — proceed if photograph confirms Bosch-style housing** |
| Aptiv/Delphi GT150-series | Mouser (mainstream distributor); Corsa Technic, Waytek Wire (motorsport specialty) | Same distributors, per-position contact/seal kits | Not obtained in this pass for a 94-position variant — **unverified** | Yes — Mouser has an India storefront | **Buyable — needs live-catalog price/position check before ordering** |
| TE Connectivity AMPSEAL (90-series) | Mouser, DigiKey (mainstream, confirmed stocked) | Same distributors | Not itemised in this pass | Yes — mainstream stock | **Buyable — safest fallback, weakest visual match** |
| Molex CMC / cylindrical high-density | — | — | — | — | **Not a candidate — shape mismatch** |

---

## Step 4: The photograph brief that closes this

One site visit, done right, resolves which of the three buyable candidates is correct. Photograph the ECU connector **on the engine harness side (the plug, not the ECU-mounted socket)** and the **ECU case itself**, as follows:

1. **Full-face shot of the connector's mating face**, camera square-on (not at an angle) to the pin field, filling the frame. This is the single most important shot: it will immediately show whether the housing is one rectangular shell with a flat multi-row grid (Bosch/Delphi-style — candidates #1/#2) or an oval/rounded single-lever shell (AMPSEAL-style — candidate #3), settling the ranking's top-level question in one image.
2. **A shot of the retention mechanism actuated/engaged and again disengaged** (if it can be safely operated with the engine off and battery disconnected) — specifically to determine whether it is a pivoting lever, a slide latch, a center bolt, or simple friction/CPA-clip retention. This resolves the Step-1 ambiguity about the bowed feature on the connector's right side.
3. **A raking (low-angle, side-lit) shot of every flat surface of the housing** — top, both sides, and the cable-entry boot — specifically hunting for a **molded (raised or recessed) part number, date code, or manufacturer logo**. These are usually small (2–4 mm character height) and shallow, so: use a raking light held at a low angle roughly parallel to the surface (a phone flashlight held to the side works well) rather than the on-axis camera flash, which washes out shallow embossing. Take multiple shots at different light angles if the first pass doesn't reveal legible text. Manufacturer logos to watch for specifically: the Bosch roundel, a Delphi/Aptiv wordmark or triangle logo, or a TE Connectivity ("te" stylized) mark — presence of any one of these directly resolves the family question.
4. **The ECU's own case label/nameplate**, photographed flat-on and well-lit — looking for a Bosch part number of the pattern `0 281 0xx xxx` (EDC-family) or `F 01R 0xx xxx` (Bosch reseller code, sometimes used by Kirloskar per the injector cross-reference in `04-injector-drive.md`), or any Continental/Delphi/Denso equivalent. Finding this would independently resolve the still-open "OEM ECU part number" question from `01-engine-identity.md` Step 2, which is a bigger win than the connector question alone.
5. **A wide shot showing the connector still mated to the harness**, to capture the harness-side (socket) connector's backshell and cable exit angle/strain relief — useful for the adapter-harness design even if it adds nothing to family identification.
6. **A pin-count check shot**: with the connector unplugged (engine off, battery disconnected), count and photograph the pin rows directly, confirming the "four rows, two 2-pin corner blocks" structure this memo infers from the line drawing, and specifically checking whether the two corner-pin contacts are visibly larger in diameter/blade-width than the grid pins — this is the single check that would upgrade Step 1's "inferred" finding about mixed contact sizes to "confirmed."

**Lighting/angle summary:** natural or diffuse white light for the full-face and pin-count shots (avoid on-axis flash — it flattens the pin field and hides depth); raking side-light specifically for hunting molded text. A macro mode or phone "portrait"/close-focus mode is recommended for the part-number hunt, since the expected character height is small.

---

## Sources consulted

- `/home/mohan/workws/ecu25kva/refs/GP3.8703.C4.pdf` — page 4, "Engine Control Unit Connector" panel, re-rendered at 400 dpi (`pdftoppm -r 400 -f 4 -l 4`) and examined via cropped PIL renders.
- `/home/mohan/workws/ecu25kva/refs/ecu-pinout-extracted.md` — confirms 94-pin count and that only 44/94 pins are traceable in the wiring diagram.
- `/home/mohan/workws/ecu25kva/docs/research/01-engine-identity.md` — engine/genset identity; Step 2 negative result on OEM ECU part number, carried forward unchanged (not re-openable with sources available here).
- `/home/mohan/workws/ecu25kva/docs/research/04-injector-drive.md` — Bosch-injector-family inference used as corroborating (not standalone) context for candidate #1.
- https://www.u-obd.com/product/edc17-connector/ — Bosch EDC17 94-pin+60-pin connector kit, US$99, fetched directly.
- https://ecudepot.com/product/bosch-edc17-connector/ — same product, found via search.
- https://www.autoecupart.net/products/original-new-full-94-pin-connector-for-bosch-edc17-electronic-control-unit-ecu and related autoecupart.net listings — found via search, corroborate the "Bosch 94-pin EDC17" connector as a distinct, repeatedly-listed aftermarket product.
- https://www.ebay.com/itm/265128037857 and https://www.ebay.com/itm/254545773762 — eBay listings, found via search, further corroboration.
- https://www.mouser.com/Delphi-Connection-Systems/Connectors/Automotive-Connectors/GT-150-Series/ — Aptiv/Delphi GT150 series distributor listing, found via search.
- https://www.corsa-technic.com/category.php?category_id=178 and https://www.waytekwire.com/catalog/connectors/aptiv-gt150-connectors — GT150 specialty-distributor listings, found via search.
- https://www.mouser.com/en/c/connectors/automotive-connectors/?m=TE+Connectivity&series=AMPSEAL — TE Connectivity AMPSEAL series distributor listing, found via search.
- https://bosch-connectors.com/ (PS Connectors) — fetched directly; page returned only navigation/legal boilerplate, no usable technical content (**negative result**, recorded rather than omitted).
- Searches returning negative or inconclusive results (recorded per the global instruction): `Bosch EDC17 94 pin connector India price Delhi distributor OR Amazon.in OR IndiaMART` (no India-specific listing found); `Bosch MD1 MDG1 154 pin ECU connector ampseal delphi GT94 comparison` (no direct technical comparison found); `TE Connectivity AMPSEAL 90 way OR Delphi GT150 150 pin connector Mouser India price` (distribution channel confirmed, exact India pricing not obtained).
- Prior-session scratchpad files reviewed for reusable material (`/tmp/claude-1000/.../scratchpad/`): `drivven.txt` (Drivven DI Driver Module manual — relevant to Task 4, not this task), `bpc960.txt` (Bliss Powercom BPC960 genset-controller manual — a different controller, not the KG640C or the engine ECU, not used in this memo), `apalrd.txt` (generic common-rail-diesel-control-system slide deck — not connector-specific, not used). None of these contained ECU-connector-family evidence directly usable here; reviewed to avoid duplicate fetching, not cited as sources for any claim above.
