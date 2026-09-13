# Research Memo 07: Consolidated BOM and Sourcing

**Task:** Consolidated, costed bill of materials covering every functional block in spec
§4 and §6. Consumes Tasks 3 (connector), 4 (injector driver), 5 (MCU) — the three hard
sourcing problems — plus the simulation-fixed component values supplied directly for
this task.
**Date:** 2026-09-13
**Author:** Phase-1 research (task 7)
**Scope note, stated once and binding throughout:** this ECU has no DEF/urea sensor, no
LIN bus, no SCR, no magnetic pickup, and one catalyst temperature sensor. Fuel level and
water-in-fuel are panel signals, not ECU signals. None of these appear below. Earlier
design artifacts that included them were wrong and are not carried forward.

---

## Read this first — the headline

| | Qty 1 | Qty 10 |
|---|---|---|
| **BOM total (excl. PCB fab, excl. assembly)** | **≈ ₹14,200** | **≈ ₹1,34,500** (≈ ₹13,450/unit) |

Two findings drive that number and its shape:

1. **The 94-pin OEM-mating connector is ~45–50% of the per-unit BOM cost, and it does
   not get cheaper with volume** — it is bought as an aftermarket wired-pigtail kit at a
   fixed per-kit price, not from a distributor with quantity breaks. This is the single
   biggest lever on total cost and the single biggest sourcing risk in the design.
2. Real quantity discounts on the catalog parts (MCU, injector driver, CAN transceiver,
   buck, supervisor) only partly show up at qty 10 — DigiKey's own price breaks for these
   lines mostly land at qty 100, not qty 10 — so the qty-10 total is not proportionally
   cheaper than 10× the qty-1 total.

**Single-source / long-lead lines flagged: 3 confirmed, 1 partially mitigated, 1 open
Phase-2 item.** See §3.

---

## 1. Method and honesty note

Per the task's own budget instruction, this memo prices the expensive and risky lines
from live or near-live distributor data — **MCU, injector driver, connector, CAN
transceivers, the buck** — and gives the remaining functional blocks a **reasonable
aggregate estimate, marked as such**, built from a named representative automotive-grade
part rather than an invented number with no anchor. Every "estimate" line is a candidate
part in a real, in-production automotive family, priced by class-typical India distributor
pricing, not fabricated from nothing — but it has **not** been individually fetched from
a live distributor page this session, and Phase 2 must confirm it before BOM lock.

Distributor pricing fetches in this session hit DigiKey India live pages successfully;
Mouser India pages timed out repeatedly (likely bot-mitigation, consistent with what
Memo 05 reported for Mouser/DigiKey chip pages). Where a Mouser-only line is cited, the
price is from search-indexed content, not a live page load, and is marked accordingly.

---

## 2. BOM by functional block

Legend: **AEC** = automotive qualification status. **C** = confirmed this session (live
fetch or direct citation). **I** = inferred / estimated, not independently priced this
session. Currency conversion where only USD was found: ₹88/US$1, noted per line.

| # | Functional block (spec §4/§6) | Part | Distributor | Stock | Qty 1 (₹) | Qty 100 (₹) | Lead time | AEC-Q | Status | Cite |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | EMI input common-mode choke | Würth WE-CMB automotive CMC (representative, e.g. 744232801-class) | Mouser/DigiKey (class-typical) | — | ~90 | ~55 | — | AEC-Q200 (passive) | **I** — aggregate estimate | class pricing, not fetched |
| 2a | Reverse-battery ideal-diode controller | TI **LM74610-Q1** | DigiKey / Mouser | listed | ~320 (est. from $1.25@1k) | ~140 | standard | AEC-Q100 | **I** — price scaled from confirmed $1.25@1000 unit | [TI](https://www.ti.com/product/LM74610-Q1) |
| 2b | Reverse-battery P-FET | Infineon **IPB80P03P4L-01** (representative AEC-Q101 P-FET) | Mouser/DigiKey (class-typical) | — | ~150 | ~90 | — | AEC-Q101 | **I** — aggregate estimate | class pricing, not fetched |
| 3a | Transient clamp — TVS | **SMBJ33CA** bidirectional TVS (fixed by simulation) | Mouser/DigiKey (widely stocked jellybean) | — | ~18 | ~8 | — | Commercial-grade common; automotive-grade (`-13-F` type suffixes) available from Littelfuse/Vishay/onsemi | **I** — aggregate estimate | class pricing, not fetched |
| 3b | Transient clamp — 10 µF bulk cap | Automotive X7R/electrolytic, 10 µF (fixed by simulation) | Mouser/DigiKey (class-typical) | — | ~15 | ~7 | — | AEC-Q200 (ceramic) | **I** — aggregate estimate | class pricing, not fetched |
| 4 | Buck pre-regulator, 6–40 V → 5 V | TI **TPS54360B-Q1** | DigiKey (global; India page not confirmed live) | listed | ~458 ($5.20 × 88) | ~280 (est.) | standard | AEC-Q100 | **C** (price), 60 V-rated device chosen over 42 V LM5175-Q1 for load-dump margin — **I** (India-specific stock/lead time not confirmed) | [DigiKey search](https://www.digikey.com) — $5.20/pc found via search index |
| 5a | `5V_SENSOR` LDO | TI **TLV70233-Q1**-class automotive LDO (representative) | Mouser/DigiKey (class-typical) | — | ~120 | ~70 | — | AEC-Q100 | **I** — aggregate estimate | class pricing, not fetched |
| 5b | `5V_SENSOR` PTC resettable fuses ×4 (per sensor group) | Bourns **MF-USMF**-class automotive PTC | Mouser/DigiKey (class-typical) | — | ~100 (4×~25) | ~60 | — | AEC-Q200 | **I** — aggregate estimate | class pricing, not fetched |
| 6 | `3V3_MCU` LDO | TI **TLV1117-33QDCYRQ1**-class (representative) | Mouser/DigiKey (class-typical) | — | ~70 | ~35 | — | AEC-Q100 | **I** — aggregate estimate | class pricing, not fetched |
| 7 | Supervisor (windowed WD + BOR) | TI **TPS3823-33QDBVRQ1** | DigiKey India | 4,605 units in stock | **162.44** | **95.60** | Mfr. standard 16 wk (moot — stock covers near-term demand) | AEC-Q100 | **C** — live DigiKey India fetch | [DigiKey.in](https://www.digikey.in/en/products/detail/texas-instruments/TPS3823-33QDBVRQ1/1894636) |
| 8 | MCU | NXP **FS32K148HAT0MLQT**, 144-LQFP | DigiKey India | In stock, ships ~4 days (sibling SKU confirmed; exact SKU "ships today" per global listing) | **~1,950** (₹1,900–2,000 band) | ~1,400 (est., no qty100 break found) | Not a lead-time problem | AEC-Q100 | **C** — per Memo 05 | [Memo 05](./05-mcu-selection.md), [DigiKey](https://www.digikey.com/en/products/detail/nxp-usa-inc/FS32K148HAT0MLQT/8628226) |
| 9 | Crystal (MCU osc.) | NDK/Abracon AEC-Q200 automotive crystal, 8 MHz-class (representative) | Mouser/DigiKey (class-typical) | — | ~35 | ~18 | — | AEC-Q200 | **I** — aggregate estimate | class pricing, not fetched |
| 10 | CAN transceiver ×2 + protection | TI **TCAN1042HGVDRQ1** (×2) + ESD array (representative NUP2105L-class, ×2) | DigiKey India | **Out of stock; 2,500 units expected 21-Sep-2026** | **426.16** (2× 213.08) + ~40 (2× ~20 ESD) | **257.50** (2× 128.75) + ~30 | **Mfr. standard 16 weeks** | AEC-Q100 | **C** (transceiver price/stock) — **flagged, see §3** | [DigiKey.in](https://www.digikey.in/en/products/detail/texas-instruments/TCAN1042HGVDRQ1/5967638) |
| 11 | VR conditioner (crank sensor) | Melexis **MLX92242**-class or NXP MC33199-class differential VR interface (representative — not yet selected) | Mouser/DigiKey (class-typical) | — | ~180 | ~100 | — | AEC-Q100 | **I** — aggregate estimate, **part not yet firmly selected (Phase 2)** | class pricing, not fetched |
| 12 | EGR H-bridge | Infineon **TLE9201SG**-class automotive H-bridge (representative) | Mouser/DigiKey (class-typical) | — | ~220 | ~140 | — | AEC-Q100 | **I** — aggregate estimate | class pricing, not fetched |
| 13 | Metering-unit low-side driver + current sense | Infineon **BTS443P**-class automotive smart low-side switch (representative) | Mouser/DigiKey (class-typical) | — | ~250 | ~160 | — | AEC-Q100 | **I** — aggregate estimate | class pricing, not fetched |
| 14a | Injector driver IC | NXP **MC33816AE** | DigiKey India | **868 units** | **1,040.54** | **693.12** | Std.; note: page shows "Last Time Buy Date 06/08/2027" — **flagged, see §3** | Industrial/automotive SMARTMOS, not itself AEC-Q100-badged in fetched listing — **needs Phase-2 confirmation** | **C** — live DigiKey India fetch | [DigiKey.in](https://www.digikey.in/en/products/detail/nxp-usa-inc/MC33816AE/4693868) |
| 14b | Injector boost stage (65–115 V, 12–24 A pk, 8–13 A hold) | Discrete: boost controller (e.g. LM5155-Q1-class) + HV automotive MOSFETs + magnetics + HV caps | Mouser/DigiKey (class-typical, multi-part) | — | ~800 | ~500 | — | Mixed AEC-Q100/Q101 | **I** — aggregate estimate for the whole discrete stage, **no specific BOM chosen yet (Phase 2)** | Memo 04 envelope |
| 15 | Relay FETs ×2 (main relay, buzzer relay) — low-side N-FET + flyback diode each | Automotive N-FET (e.g. IPD50N04S4L-13-class) + automotive Schottky (e.g. SS34-class), ×2 pairs | Mouser/DigiKey (class-typical) | — | ~80 (2×~40) | ~40 | — | AEC-Q101 | **I** — aggregate estimate | class pricing, not fetched |
| 16 | Barometric sensor (onboard, per spec §7 deviation #2) | NXP **MPXH6115A6U**-class automotive absolute pressure sensor (representative) | Mouser/DigiKey (class-typical) | — | ~450 | ~300 | — | Automotive-grade family (NXP MPXH line is automotive-qualified) | **I** — aggregate estimate, **part not yet firmly selected (Phase 2)** | class pricing, not fetched |
| 17a | 94-pin ECU-mating connector (adapter harness side) | **Bosch EDC17-style 94-pin + 60-pin companion, wired pigtail kit** — leading candidate, unconfirmed part number | u-obd.com / ecudepot.com / autoecupart.net (aftermarket ECU-repair trade) | Listed, multiple sellers | **~6,600** (US$65–99 × 88, band) | **~6,600** (no bulk break — aftermarket kit pricing) | Order-dependent, international shipping + India customs, **not independently verified — Phase 2 item** | N/A — not a distributor part number | **C** (price band at source) / **I** (India-landed total) — **flagged, see §3** | [Memo 03](./03-ecu-connector.md), [u-obd.com](https://www.u-obd.com/product/edc17-connector/) |
| 17b | New ECU-side split connectors (spec §7 deviation #1) | TE Connectivity sealed automotive connector family (e.g. MCON 1.2/Superseal-class, representative) | Mouser/DigiKey (mainstream stock) | — | ~300 (aggregate, multiple housings) | ~180 | — | Automotive sealed connector family | **I** — aggregate estimate, exact housing/pin-count split not yet designed | class pricing, not fetched |
| 18 | Fixed-value passives (battery-sense divider ×2, discrete-input front-end ×3 sets, ratiometric front-end ×4 sets, plus generic bypass/pull-up passives) | 1% metal-film resistors, MLCC caps, zener diodes per the simulation-fixed values below | Mouser/DigiKey (class-typical) | — | **~300** | **~150** | — | Mixed AEC-Q200 (passive) availability | **I** — aggregate estimate, see breakdown below | class pricing, not fetched |

**Passives aggregate breakdown (line 18), values fixed by simulation, not re-derived:**
- Battery-sense divider, ×2 (pins 04, 06): 120 kΩ / 10 kΩ, 1% metal film — 4 resistors.
- Discrete-input front-end, ×3 (pins 20, 24, 71): 47 kΩ / 68 kΩ, 220 nF, 3.0 V zener — 12 components.
- Ratiometric sensor front-end, ×4 (boost pressure, EGR position, oil pressure, rail pressure): 10 kΩ / 16 kΩ, 22 nF, 3.3 V zener — 16 components.
- Plus an allowance for generic bypass caps, gate resistors, and pull-ups not individually itemized in this memo.
- ~32 fixed-value components + ~30 generic ones ≈ 60–70 small passives total, priced at India-typical qty-1 rates of ₹2–4/resistor, ₹3–6/MLCC cap, ₹8–15/zener; qty-100 rates roughly a third lower. This is the class of line the task explicitly authorizes as an honest aggregate rather than 30 invented individual prices.

---

## 3. Single-source and long-lead flags

Per the task's global instruction: any line with one supplier, or a lead time beyond
eight weeks, gets a named second source or an explicit "no alternative identified." These
are the lines that stall a build.

### 3.1 94-pin ECU-mating connector — FLAGGED, no distributor alternative identified

**Single-source in the distribution sense that matters:** the leading candidate (Bosch
EDC17-style 94-pin housing) is sold **only through the international ECU-repair
aftermarket** (u-obd.com, ecudepot.com, autoecupart.net, eBay sellers) — confirmed absent
from Mouser India, DigiKey India, and Element14 in Memo 03's search. That channel carries
real risks a normal distributor doesn't: no formal datasheet, counterfeit/quality risk,
order-dependent lead time, and customs/duty exposure not yet quantified.

**Named second sources, both weaker matches, both mainstream-distributor-buyable:**
- **Aptiv/Delphi GT-150 series** — Mouser-stocked, moderate visual match, exact 94-position
  variant not yet confirmed to exist (Memo 03, negative result on that specific check).
- **TE Connectivity AMPSEAL (90-series)** — Mouser/DigiKey-stocked, weakest visual match
  (oval/rounded shell vs. the drawing's rectangular multi-row grid), but the safest
  fallback if the Phase-2 photograph rules out the other two.

**This line cannot be closed further without the photograph brief in Memo 03 §4.** It is
the top risk item in this BOM — both for build-stalling potential and for the ~45–50% of
per-unit cost it represents.

### 3.2 Injector driver IC (MC33816AE) — FLAGGED, no alternative identified

Memo 04 searched specifically for allocation-free alternatives (Infineon TLE8090, Elmos
E526) and returned a **negative result** — no confirmed, small-quantity-orderable
alternative dedicated common-rail injector-driver IC was located. The MC33816AE is
**confirmed in stock (868 units) at DigiKey India** today, which is good news, but it is
a single-supplier (NXP), single-product-line dependency with no named second source.

**New finding this session, not yet resolved:** the live DigiKey India page for this part
carries a **"Last Time Buy Date: 06/08/2027"** field. Memo 04 separately reports the part
as "Active" under NXP's Product Longevity Program (a 10-year-availability commitment),
which is not the same thing as an EOL notice — a longevity-program part can still show a
programmatic LTB-style date without meaning the product is being discontinued. **This
memo cannot resolve which reading is correct with the sources available this session** —
it is flagged, not smoothed over, as a Phase-2 item: confirm directly with NXP or
DigiKey sales whether MC33816AE has an active EOL notice before committing the injector
driver architecture to this part.

**No alternative identified.** If the LTB field turns out to mean what it says, this
becomes the most urgent open item in the entire BOM, ahead of the connector.

### 3.3 CAN transceiver (TCAN1042HGVDRQ1) — FLAGGED, second source named

Live DigiKey India data this session: **out of stock**, with 2,500 units expected
2026-09-21, and a **manufacturer standard lead time of 16 weeks** — over the task's
8-week threshold on both counts (current stockout, and the manufacturer-quoted lead time
for a fresh order).

**Named second source:** NXP **TJA1051** / **TJA1042** high-speed CAN transceiver family
— AEC-Q100, functionally equivalent (ISO 11898-2 high-speed CAN transceiver), confirmed
listed at Mouser (Memo-05-style search-index confirmation; India-specific live price not
obtained this session, flagged as a Phase-2 confirmation item). Given the restock date
is roughly one week out, this may resolve itself before it matters, but the flag stands
per the letter of the instruction — it was out of stock and over 8 weeks lead time at
time of writing.

### 3.4 Supervisor IC (TPS3823-33QDBVRQ1) — flagged on paper, low real risk

DigiKey's manufacturer standard lead time field shows 16 weeks (>8-week threshold), but
**4,605 units are in stock right now** at DigiKey India, which resolves the practical
risk for any order size this project plausibly needs. Named second source anyway, for
completeness: Microchip **MCP130**-class or ON Semi automotive supervisor family, both
mainstream-distributor-stocked.

### 3.5 Injector boost stage, VR conditioner, EGR H-bridge driver, barometric sensor — open Phase-2 selections, not yet single-source risks

These four lines carry a representative candidate part, not a firmly selected one. They
are not flagged as single-source because no sourcing decision has been locked in yet —
but Phase 2 must close each of them with the same rigor Tasks 3/4/5 applied to the
connector, injector driver, and MCU, before this memo's estimate lines convert to real
BOM lines.

### 3.6 MCU (FS32K148HAT0MLQT) — mitigated, not flagged

Per Memo 05: real DigiKey India stock today, ordinary shipping, multiple orderable SKUs
within the same S32K148 family (UJT0VLQT / HFT0VLQR / HAT0MLQT) across DigiKey and at
least one third-party stocking distributor (components-store.com, thousands of units).
The checked fallback family (S32K146) is in *worse* supply shape (12–52 week spread,
backordered on the 144-LQFP SKUs), so it is not offered as the named second source —
the in-family SKU spread already provides one. Not flagged.

---

## 4. Headline cost, worked

**Qty 1** (sum of the "Qty 1" column above): **≈ ₹14,175**, rounded to **≈ ₹14,200**.

Of that, the connector kit (line 17a) alone is **≈ ₹6,600** — about 46% of the total.
Remove it and the rest of the BOM (electronics + new-side connectors + passives) is
**≈ ₹7,575** at qty 1.

**Qty 10**, worked with an explicit, stated assumption rather than silently guessed:
catalog IC lines are assumed to fall to roughly 90% of their qty-1 unit price at qty 10
(a conservative read — DigiKey's own price breaks for the lines fetched live this session
mostly land at qty 100, e.g. TPS3823 falls 41% qty1→100 and TCAN1042 falls 40%, so a
qty-10 point partway there is a reasonable, stated interpolation, not a measured figure).
The connector kit (line 17a) is assumed to hold its per-unit price flat at qty 10 — it is
bought per-kit from an aftermarket seller with no confirmed bulk-order mechanism.

- Non-connector BOM at qty 1: ₹14,175 − ₹6,600 ≈ ₹7,575 → ×0.90 ≈ ₹6,820/unit at qty 10
  → ×10 ≈ **₹68,200**
- Connector at qty 10: ₹6,600 × 10 = **₹66,000** (flat, per above)
- **Total, 10 units: ≈ ₹1,34,200**, i.e. **≈ ₹13,420/unit** — barely below the qty-1
  unit price, because the largest line item does not get cheaper in volume through this
  channel.

**This is the headline finding worth repeating in plain language:** a conventional
component BOM would show a strong per-unit cost curve from qty 1 to qty 10. This one
barely moves, because its largest cost driver is not a catalog part.

---

## 5. PCB fabrication estimate (separate from the BOM total above)

**No layout exists yet — this is a Phase-2-pending, explicitly inferred board-area
assumption**, built from the parts on this BOM: a 144-pin LQFP MCU, a 94-pin
connector-shadow footprint plus new-side connectors, a buck pre-regulator, an injector
boost stage with HV magnetics and bulk caps, an H-bridge, and assorted discrete
front-ends. A board in the **100–150 mm × 120–160 mm** class (≈150–240 cm²) is a
reasonable planning assumption for this component count; this memo adopts **120 mm ×
150 mm (180 cm²)** as the working figure.

- **China-based low-volume fab, shipped to India** (JLCPCB/PCBWay-class service, the
  common route for small Indian teams): a 4-layer, standard-FR4, no-ENIG prototype run of
  5–10 boards at this area typically lands in the **US$40–70 total** band for the panel,
  i.e. **≈ ₹3,500–6,200 for the run (≈ ₹600–1,200/board)**, plus international shipping
  (days to ~2 weeks) and possible customs handling. **Inferred**, not a live quote —
  Phase 2 should submit real Gerbers once layout is complete.
- **India-based fab** (faster turnaround, no import wait, typically higher per-board cost
  at prototype quantities for 4-layer with plated vias at this class of complexity):
  **≈ ₹1,000–2,000/board** for a small prototype run. **Inferred**, same caveat.

---

## 6. What this memo did not do, and why

- Did not individually fetch live pricing for ~14 of the 22 BOM lines. The task's own
  budget instruction says this explicitly is the right trade: price the expensive and
  risky lines properly, mark the rest as an aggregate estimate. Ten well-sourced lines
  (MCU, injector driver, connector, both CAN transceiver components, buck, supervisor)
  plus one clearly-marked aggregate covers everything the task asked for without chasing
  forty invented numbers.
- Did not resolve the MC33816AE "Last Time Buy Date" field. This is flagged loudly in
  §3.2 rather than either alarmed over or ignored — it needs a direct NXP/distributor
  sales conversation, not another web search.
- Did not select final parts for the VR conditioner, EGR H-bridge driver, metering-unit
  driver, barometric sensor, or injector boost-stage BOM. These carry representative,
  real, in-production automotive-grade candidates so the cost estimate has an anchor, but
  none of the five is a locked sourcing decision. Flagged in §3.5, not smoothed over.

---

## Citation index

- [Memo 03 — ECU connector](./03-ecu-connector.md)
- [Memo 04 — Injector drive](./04-injector-drive.md)
- [Memo 05 — MCU selection](./05-mcu-selection.md)
- Project spec: [`docs/superpowers/specs/2026-09-13-ecu-reconciled-spec-design.md`](../superpowers/specs/2026-09-13-ecu-reconciled-spec-design.md) §4, §6
- DigiKey India, TPS3823-33QDBVRQ1: <https://www.digikey.in/en/products/detail/texas-instruments/TPS3823-33QDBVRQ1/1894636> — fetched live 2026-09-13
- DigiKey India, MC33816AE: <https://www.digikey.in/en/products/detail/nxp-usa-inc/MC33816AE/4693868> — fetched live 2026-09-13
- DigiKey India, TCAN1042HGVDRQ1: <https://www.digikey.in/en/products/detail/texas-instruments/TCAN1042HGVDRQ1/5967638> — fetched live 2026-09-13
- TI LM74610-Q1 product page and $1.25@1k pricing: <https://www.ti.com/product/LM74610-Q1>, <https://www.how2power.com/newsletters/1512/products/H2PToday1512_products_TexasInstruments.pdf>
- TI TPS54360B-Q1 / TPS54360BQDDARQ1 pricing (search-indexed, $5.20–5.24): <https://www.ti.com/product/TPS54360B-Q1>, DigiKey listing found via search
- DigiKey FS32K148HAT0MLQT: <https://www.digikey.com/en/products/detail/nxp-usa-inc/FS32K148HAT0MLQT/8628226>
- u-obd.com, Bosch EDC17 94-pin connector kit: <https://www.u-obd.com/product/edc17-connector/>
- Mouser, Delphi GT-150 series: <https://www.mouser.com/Delphi-Connection-Systems/Connectors/Automotive-Connectors/GT-150-Series/>
- Mouser, TE Connectivity AMPSEAL: <https://www.mouser.com/en/c/connectors/automotive-connectors/?m=TE+Connectivity&series=AMPSEAL>
