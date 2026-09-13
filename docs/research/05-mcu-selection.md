# Research Memo 05: MCU Selection — S32K148 Confirmation

**Verdict: CONFIRMED.** NXP S32K148, Arm Cortex-M4F, recommended in the **144-pin LQFP
package** (orderable P/N **FS32K148HAT0MLQT** — 80 MHz clock grade, −40…+125 °C, CAN‑FD
feature set, tape-and-reel), is retained as the MCU for this design. It clears the
channel budget in spec §5 with large margin, is in stock at an India-serving distributor
today (not a 40-week part), has a workable — if not ideal — KiCad footprint path, and a
free toolchain. **One part of the spec's reasoning is weaker than it looks and is
replaced below (§6): the "constant speed relaxes timing" argument checks crank-edge
rate, which was never the binding constraint. The binding constraint is injector
pulse-width/output-compare resolution, and that also clears with large margin — so the
conclusion holds, but for a different reason than §5 states.**

---

## 1. Channel budget vs. the S32K148 datasheet

Source: NXP, *S32K1XX — S32K1xx Data Sheet*, **Rev. 15, 5 March 2026**,
<https://www.nxp.com/docs/en/data-sheet/S32K1xx.pdf> (cached copy inspected locally;
page numbers below refer to this PDF's own footer pagination, "N / 108").

| Budget item (spec §5) | Need | S32K148 datasheet | Cite | Status |
|---|---|---|---|---|
| CAN | 2× | **3× FlexCAN**, all 3 with CAN‑FD (ISO/CD 11898‑1) | p.6, Fig. 3 | Confirmed — 1 spare instance |
| ADC | ~14 ch (8 sensor + 2 batt-rail + 4 current-sense) | **2× 12‑bit SAR ADC, 1 Msps each, up to 32 ch/module** = up to 64 analog-capable pins at full-chip level | p.2 (Key Features), p.6 Fig. 3 | Confirmed at instance/full-chip level. **Inferred, not yet confirmed:** how many of those 64 channels are actually broken out on the 144-pin package specifically requires the pin-mux table in the *S32K1xx Reference Manual* — the datasheet itself says pinouts/signal descriptions live there, not in this document (p.10, §10.1). Flagged for Phase 2. |
| Timer | ~10 ch (crank, cam, 3 inj-lo, 2 inj-hi, metering PWM, 2 EGR PWM) | **8× independent 16‑bit FlexTimer (FTM) modules, up to 64 standard IC/OC/PWM channels total** (8 ch/instance) | p.3, p.6 Fig. 3 | Confirmed — >6× the required channel count |
| I2C (baro sensor) | 1× | **2× LPI2C** | p.6 Fig. 3 | Confirmed |
| Flash | — | up to **2 MB** program flash (up to 1,984 KB when EEPROM emulation/data flash in use) | p.2, p.6 Fig. 3 footnote 2 | Confirmed, generous for this application's code size |
| RAM | — | up to **256 KB** SRAM (incl. FlexRAM) | p.2, p.6 Fig. 3 | Confirmed, generous |
| Core / clock | — | Arm Cortex‑M4F, **80 MHz (RUN)** or **112 MHz (HSRUN)** | p.2, p.6 Fig. 3 | Confirmed |

The spec's own summary of the datasheet (§5: "3× FlexCAN... dual 12-bit ADC... FlexTimer
instances well beyond the ~10 timing channels required") is accurate and is now backed
by a primary-source page reference rather than recollection.

---

## 2. Package selection

**Recommendation: 144-pin LQFP** (NXP case outline **SOT486‑2**, drawing **98ASS23177W**
— confirmed document numbers, per datasheet §9.1 "Obtaining package dimensions," p.108
of the PDF; the dimensional drawing itself was **not** independently fetched in this
session — **inferred, not confirmed:** SOT486 is the standard 20×20 mm / 0.5 mm-pitch
LQFP144 outline used across NXP's automotive MCU lines, but this specific drawing should
be pulled from nxp.com and checked pad-by-pad before footprint lock, per the PCB
Roadmap's warning that a hand-sourced footprint is the most likely place to introduce a
silent error).

Why 144-pin over the smaller options, and why LQFP over BGA:

- Package options that exist for S32K148: 100-pin LQFP (QuadSPI *not* supported in this
  package per datasheet footnote 6, p.6), 100-pin MAPBGA, 144-pin LQFP, 176-pin LQFP.
- The confirmed pin map (spec §4) resolves only 44 of 94 OEM ECU pins; U1 in the
  unknowns register carries the other 50. The MCU-side signal budget from §5 alone
  (2 CAN ×2 pins + 14 ADC + 10 timer + 1 I2C ×2 pins ≈ 30 dedicated pins) plus SWD debug,
  oscillator, and power/ground pins for a part this size (typically another 30–40 pins on
  a 144-pin LQFP) is comfortably inside even the 100-pin package. The 144-pin package is
  chosen as headroom against U1, not because the confirmed budget requires it.
- LQFP over MAPBGA: a 100-pin MAPBGA buys nothing the 144-pin LQFP doesn't already have
  (same instance counts — CAN/ADC/FTM/I2C counts are silicon-level, not package-level,
  per Fig. 3), while a BGA package requires X-ray or destructive inspection to verify
  solder joints — a real cost for a small team doing early hand/low-volume assembly.
  144-pin LQFP is 0.5 mm pitch, which is reflow-soldering-standard and inspectable by eye
  or AOI.

**Recommended orderable part number: FS32K148HAT0MLQT** — decoded against the datasheet's
own ordering-information key (p.8, Fig. 5):
- `H` = 80 MHz speed grade (RUN mode)
- `A`/`A1` = CAN‑FD + FlexIO (+ Security) feature option
- `M` = **−40 °C to +125 °C** temperature grade
- `LQ` = 144-pin LQFP package code
- `T` = trays/tubes (an `R` suffix variant, e.g. FS32K148HFT0VLQR, exists for tape-and-reel
  production quantities)

**Confirmed** the `U` (112 MHz HSRUN) speed-grade parts are explicitly **not valid at the
125 °C (`M`) temperature grade** (datasheet footnote 1 under the ordering-option table,
p.8: "Not valid with M temperature/125C"). This matters directly for the recommendation:
an engine-bay-adjacent ECU should be specified to the 125 °C grade, and §6 below shows
the extra 32 MHz of HSRUN clock isn't needed to close the timing budget — so there is no
reason to trade thermal margin for clock headroom the design doesn't use. **This is a
concrete correction to the spec's framing in §5**, which cites "a Cortex-M4F at 112 MHz"
as the relevant number; the part that should actually go on the BOM runs at 80 MHz and
gets the better temperature rating in exchange.

---

## 3. Availability and pricing — India

Distributor pages for the specific chip part numbers (as opposed to the eval board) are
behind bot-detection on live fetch (Mouser: DataDome 403; DigiKey: 403) in this session,
so the figures below come from each distributor's own indexed page content returned via
search, dated **2026‑09‑13**. This is flagged so a live re-check before BOM lock is
understood as still worthwhile — component pricing/stock is volatile — but the figures
are not fabricated; they are quoted from the cited distributor URL's own content as
indexed.

**S32K148, 144-pin LQFP family (FS32K148UJT0VLQT / FS32K148HFT0VLQR / FS32K148HAT0MLQT):**

| Distributor | Part | Stock / lead time | Price | Cite |
|---|---|---|---|---|
| DigiKey (India storefront, digikey.in) | FS32K148UJT0VLQT | In stock, ships to India in ~4 days | ₹1,900.22 (qty 1) | [DigiKey](https://www.digikey.in/en) |
| DigiKey | FS32K148UJT0VMHT (100‑BGA variant, for comparison) | In stock | ₹2,016.80 (qty 1) | [DigiKey](https://www.digikey.in/en) |
| DigiKey (global .com listing) | FS32K148HAT0MLQT | "Ships today" per indexed listing | not captured in INR | [DigiKey](https://www.digikey.com/en/products/detail/nxp-usa-inc/FS32K148HAT0MLQT/8628226) |
| Third-party stocking distributor (components-store.com) | FS32K148UJT0VLQT | 7,948 units | $4.28/pc | [components-store.com](https://www.components-store.com/product/NXP-Semiconductors-Freescale/FS32K148HNT0VLUR.html) |
| Third-party stocking distributor | FS32K148HFT0VLQR | 10,530 units | $3.59/pc | (same search) |
| Element14 India | S32K148EVB-Q176 (eval board, not bare chip) | listed, "pricing unavailable, contact customer service" for chip SKUs | ₹17,922.07 (eval board) | [in.element14.com](https://in.element14.com/nxp/s32k148evb-q176/eval-board-32bit-arm-cortex-m4f/dp/2917581) |

**Verdict on S32K148 availability: confirmed pass.** Real stock at DigiKey's
India-facing storefront in single-digit quantities, at low-hundreds-of-rupees-to-few-
thousand-rupee unit pricing, with ordinary shipping — not a lead-time problem. No need to
invoke the S32K146 fallback.

**S32K146 fallback (checked per brief step 2, not needed but recorded):**

| Part | Stock | Cite |
|---|---|---|
| FS32K146HFT0VLQT (144-LQFP) | Out of stock, backorder at DigiKey | [DigiKey](https://www.digikey.com/en/products/detail/nxp-usa-inc/FS32K146HFT0VLQT/10815998) |
| FS32K146HAT0VLQT (144-LQFP) | Out of stock, backorder | [DigiKey](https://www.digikey.co.il/en/products/detail/nxp-usa-inc/FS32K146HAT0VLQT/10816081) |
| FB32K146HAT0VLLT (related SKU, 100-LQFP) | Manufacturer standard lead time **52 weeks** | found via search index |
| FS32K146HAT0MLLT (related SKU, 100-LQFP) | Manufacturer standard lead time **12 weeks** | found via search index |

**Inferred:** the 144-pin LQFP S32K146 SKUs specifically are on backorder with no
confirmed lead time in the indexed snippets; related SKUs in the same family show a wide
12–52 week spread, which would have made S32K146 a materially worse availability bet
than S32K148 if it had been needed. This reinforces, rather than undercuts, the S32K148
recommendation — the fallback is in worse shape right now than the primary choice.

**Element14 India** does not surface public per-unit pricing for the bare MCU chip in
either family (only the eval board); it would need a quote request. Not a blocker given
DigiKey's confirmed stock, but worth noting Element14 is the weakest of the three
distributors for this specific part.

---

## 4. KiCad symbol and footprint provenance

- **KiCad's own stock symbol library does not carry the S32K1xx family.** A direct
  search of the official `KiCad/kicad-symbols` GitHub repository for NXP MCU symbols
  returns only legacy Freescale parts (`MCU_NXP_HC11.lib`, `MCU_NXP_HC12.lib`,
  `MCU_NXP_NTAG.lib`) — confirmed, no `S32K` entry exists.
  Cite: <https://github.com/KiCad/kicad-symbols>
- **NXP's own EVB design files exist but are schematic-level, not a reusable
  KiCad/parametric MCU symbol.** The S32K148EVB-Q176 has a published schematic
  (document SCH-29642, dated 2017-07-12, mirrored via Octopart) but this is a board-level
  PDF schematic, not a native KiCad library part — using it as a footprint source would
  mean hand-deriving pin assignments, exactly the "hand-sourced footprint" risk the PCB
  Roadmap warns about.
  Cite: <https://datasheet.octopart.com/S32K148EVB-Q144-NXP-Semiconductors-datasheet-103093927.pdf>
- **SnapEDA (now SnapMagic Search) is the practical source.** It lists symbol/footprint/
  3D-model downloads, exportable to KiCad, for S32K148 parts including 144-LQFP variants
  (e.g. `FS32K148HAT0MLQT`) — confirmed listing exists.
  Cite: <https://www.snapeda.com/parts/FS32K148HAT0MLLT/NXP%20Semiconductors/view-part/>,
  <https://octopart.com/part/nxp-semiconductors/FS32K148HAT0MLQT> (Octopart surfaces the
  same "trusted partner" symbol/footprint/3D-model set)

**Pad pitch verification: not done in this session — flagged as an open Phase 2 item.**
The datasheet points to case outline SOT486-2 / drawing 98ASS23177W for the exact
mechanical dimensions (§9.1, p.108 of the PDF) but does not inline the pitch value, and
the drawing PDF itself was not fetched here. Per the PCB Roadmap's explicit warning, do
**not** carry a SnapEDA footprint into layout without diffing its pad pitch/pad size
against document 98ASS23177W pulled fresh from nxp.com — this is exactly the class of
silent error the Roadmap calls out, and it has not been closed by this memo.

---

## 5. Toolchain and debug

- **Compiler/IDE: NXP S32 Design Studio for ARM**, free, Eclipse-based, bundles the GNU
  Arm Embedded Toolchain (GCC/GDB) — confirmed, S32DS for ARM 2.2 explicitly lists S32K148
  support. NXP is migrating S32K1 support toward "S32 Design Studio for S32 Platform"
  going forward; both remain usable today.
  Cite: <https://www.nxp.com/design/design-center/software/automotive-software-and-tools/s32-design-studio-ide/s32-design-studio-for-arm:S32DS-ARM>,
  release notes PDF via NXP Community.
  Third-party toolchains (IAR, GHS, Arm/Keil, Lauterbach, iSystems) are also listed as
  supported ecosystem options in the datasheet itself (p.6, Fig. 3, "Ecosystem" row).
- **Evaluation board exists: S32K148EVB-Q176**, Arduino-Uno-pinout-compatible, confirmed
  available from DigiKey India (₹17,487.61) and Element14 India (₹17,922.07) — the two
  prices differ by ~2%, ordinary distributor variance, not a discrepancy worth chasing.
  Cite: <https://www.digikey.in/en/products/detail/nxp-usa-inc/S32K148EVB-Q176/7929314>,
  <https://in.element14.com/nxp/s32k148evb-q176/eval-board-32bit-arm-cortex-m4f/dp/2917581>.
  **Confirmed** this lets firmware bring-up (HAL, crank/cam capture, CAN/J1939 stack
  skeleton, injector timer logic) start well before the custom PCB is fabricated, per
  spec §10 Phase 4 sequencing.
- **Debug probe for the custom board.** The EVB has an onboard OpenSDA debug/serial
  adapter (confirmed via NXP's own EVB documentation, indexed) usable during EVB-based
  bring-up at no extra cost. For the custom PCB (bare SWD header, no onboard debug
  circuit), a standalone probe is needed. **Important gotcha, not called out in the
  brief:** SEGGER's cheapest J-Link variant, the **J-Link EDU Mini, is licensed for
  non-commercial/educational use only** — SEGGER's own product description states it is
  "sold to private persons, colleges, schools, universities and NPOs for educational
  purposes only and is not sold to companies." This project is a commercial product
  development effort, so J-Link EDU Mini is **not** a legally usable option here despite
  being the cheapest one that shows up in a casual search. Commercially-licensed options:
  - **SEGGER J-Link BASE**: $798 (8.08.00) or **J-Link BASE Compact**: $598 (8.19.00) —
    confirmed pricing at DigiKey (USD; India-specific INR not separately captured in this
    session — inferred to land in the ₹50,000–₹67,000 band at typical GST/duty markup,
    needs a live India quote before budgeting).
    Cite: <https://www.digikey.com/en/products/detail/segger-microcontroller-systems/8-08-00-J-LINK-BASE/2175882>,
    <https://www.digikey.com/en/products/detail/segger-microcontroller-systems/8-19-00-J-LINK-BASE-COMPACT/7386652>
  - **PE Micro U-MULTILINK-FX**: $738.27 at DigiKey — comparable price to J-Link BASE, no
    commercial-use restriction, and PEmicro explicitly supports S32 Design Studio.
    Cite: <https://www.digikey.com/en/products/detail/nxp-usa-inc/U-MULTILINK-FX/3247905>
  Recommendation: budget for one J-Link BASE Compact or PEmicro U-MULTILINK-FX for lab/
  production debug; use the EVB's free onboard OpenSDA for early firmware work.

---

## 6. Testing the constant-speed timing argument

The spec's §5 argument, restated: a genset governs at a fixed 1500 rpm; a crank degree is
111 µs at that speed; a 60-tooth wheel gives a tooth edge every 667 µs; the Cortex-M4F/
FlexTimer combination has "several orders of magnitude of headroom" against that, so the
eTPU2's angle-synchronous hardware isn't needed.

**This is checking the wrong variable.** Crank-edge *capture* rate was never the hard
constraint that motivated eTPU2 use in automotive engines. A tooth arriving every
several hundred microseconds to a few milliseconds is trivial for a Cortex-M4F interrupt
or a FlexTimer input-capture channel regardless of whether the engine is a genset or a
car — 667 µs is ~75,000 CPU cycles at 80 MHz, and NVIC latency on a Cortex-M4F is on the
order of 12 cycles (~150 ns at 80 MHz), several thousand times smaller than the interval
being measured. This was true for automotive engines too, even at 6000 rpm (crank edge
every ~28 µs at 6000 rpm / 60 teeth — still >2000 CPU cycles). **So the comparison the
spec makes was never actually close, in either the automotive or the genset case, and
citing constant-speed operation as what makes it comfortable is not quite the right
causal story.**

The eTPU2's real value in automotive engines is different: it is a co-processor that
autonomously schedules and re-schedules many angle-domain output-compare events (start
of injection, duration, sometimes multi-pulse rate-shaping) across a wide, *rapidly
changing* speed range, without loading the main CPU's interrupt budget, and without the
main core's scheduling jitter (cache effects, higher-priority ISRs, RTOS latency)
touching the injection timing chain. That is a real constraint when rpm sweeps
800–6000 rpm with tight closed-loop transient response, many simultaneous channels, and
multi-pulse strategies (pilot/main/post injection) that all need to land within
microseconds of a moving target angle.

**The constraint that should actually be checked is injector pulse-width/output-compare
resolution — how finely the MCU can control injector on-time, independent of crank
speed.** This is what determines fuel-quantity metering accuracy for a given injector's
flow characteristic, and it does not go away just because rpm is constant. Checking it:

- FTM output-compare channels run off the bus/peripheral clock, up to 112 MHz (HSRUN) or
  80 MHz (RUN) per the datasheet (p.2). At 80 MHz, one timer tick = 12.5 ns; at 112 MHz,
  ~8.9 ns.
- Typical diesel solenoid injector pulse-width control for quantity repeatability needs
  on the order of 1–4 µs resolution in demanding automotive multi-pulse (pilot/main/post)
  strategies — this is a widely-cited engineering figure for common-rail injector drive,
  not a datasheet fact, so it is marked **inferred** rather than confirmed by a specific
  citation here; it is not sourced from memory of a specific document, and should be
  checked against the actual injector's datasheet once U5 (injector part number, in the
  spec's unknowns register) is closed.
- The pin map (spec §4) shows a single main injection pulse per cylinder per cycle (one
  high-side bank switch + one low-side select per cylinder, "boosted high-side switch" +
  "current-controlled low-side, peak-and-hold" — no evidence of multi-pulse rate-shaping
  in scope for this genset). A single-pulse-per-cycle strategy is materially less
  demanding on timing resolution than automotive pilot/main/post injection.
- Either way, an 8.9–12.5 ns timer tick against a ~1–4 µs (or looser, for single-pulse
  metering) requirement leaves roughly **100–450× headroom** — comparable in kind to the
  margin the spec claimed for crank-edge capture, but now measured against the
  constraint that actually matters.

**Conclusion: the spec's recommendation survives, but its stated reasoning should be
corrected, not just accepted.** Crank-edge capture rate was never the tight constraint,
in either an automotive or a genset engine. The tight constraint — injector pulse-width
resolution — is also comfortably cleared by the S32K148's FlexTimer output-compare
granularity, with margin that would likely hold even if this design later grew a
multi-pulse injection strategy (not currently in scope; U5 in the spec's unknowns
register should be revisited if it changes). The two PDBs (Programmable Delay Blocks,
2× on K148, confirmed p.6 Fig. 3) are also relevant here and not mentioned in the
spec: they allow triggering ADC conversions or timer events at a defined delay from a
capture event in hardware, without CPU intervention — useful headroom for keeping the
injection-timing chain jitter-free even if firmware complexity grows, and a partial
answer to the "what does the eTPU2 buy that we're giving up" question the spec doesn't
fully address.

**One caveat this memo cannot close:** the flow-rate/resolution figure used above is a
general diesel-injector engineering figure, not a citation to this project's actual
injector. U5 (injector part number and drive profile) is still open per the spec's
unknowns register. If the injector's actual metering-quantity-vs-pulse-width sensitivity
turns out to need sub-microsecond control (unusual for single-pulse metering, but not
impossible for a very small idle-quantity injector), this section's margin claim should
be re-run against the injector's actual datasheet before Phase 2 sign-off. This is the
one place where "confirmed" in this memo rests on an inferred industry figure rather
than a project-specific document, and it is flagged as such rather than smoothed over.

---

## 7. Residual items for Phase 2

1. Pull NXP package drawing **98ASS23177W** (144-pin LQFP, SOT486-2) directly and diff
   its pad pitch/pad geometry against whatever KiCad footprint (SnapEDA-sourced or
   hand-built) is actually used in the schematic sheet — not done in this memo.
2. Pull the **S32K1xx Reference Manual** pinout/IO-signal-description tables to confirm
   which of the 64 ADC channels and 64 FTM channels are actually broken out on the
   144-pin LQFP package specifically (the datasheet defers this to the Reference Manual,
   §10.1) — the instance-level counts are confirmed, the exact pin-level assignment for
   this package is not.
3. Get a live India quote (not indexed-search pricing) for FS32K148HAT0MLQT and one
   commercial debug probe (J-Link BASE Compact or PEmicro U-MULTILINK-FX) before BOM
   lock — Mouser/DigiKey blocked live automated fetch in this session (bot protection);
   the figures above are real but were retrieved via search-index snippets of the
   distributors' own pages, not a live page load.
4. Revisit §6's injector timing margin once U5 (injector part number) is closed.

---

### Citation index

- NXP, *S32K1XX S32K1xx Data Sheet*, Rev. 15, 5 March 2026: <https://www.nxp.com/docs/en/data-sheet/S32K1xx.pdf>
- KiCad stock symbols repo: <https://github.com/KiCad/kicad-symbols>
- SnapEDA / SnapMagic Search, S32K148 parts: <https://www.snapeda.com/parts/FS32K148HAT0MLLT/NXP%20Semiconductors/view-part/>, <https://octopart.com/part/nxp-semiconductors/FS32K148HAT0MLQT>
- S32K148EVB-Q176 schematic (SCH-29642): <https://datasheet.octopart.com/S32K148EVB-Q144-NXP-Semiconductors-datasheet-103093927.pdf>
- NXP S32 Design Studio for ARM: <https://www.nxp.com/design/design-center/software/automotive-software-and-tools/s32-design-studio-ide/s32-design-studio-for-arm:S32DS-ARM>
- DigiKey India: <https://www.digikey.in/en>; DigiKey FS32K148HAT0MLQT: <https://www.digikey.com/en/products/detail/nxp-usa-inc/FS32K148HAT0MLQT/8628226>; S32K148EVB-Q176: <https://www.digikey.in/en/products/detail/nxp-usa-inc/S32K148EVB-Q176/7929314>
- DigiKey S32K146 SKUs: <https://www.digikey.com/en/products/detail/nxp-usa-inc/FS32K146HFT0VLQT/10815998>, <https://www.digikey.co.il/en/products/detail/nxp-usa-inc/FS32K146HAT0VLQT/10816081>
- Element14 India, S32K148EVB-Q176: <https://in.element14.com/nxp/s32k148evb-q176/eval-board-32bit-arm-cortex-m4f/dp/2917581>
- SEGGER J-Link EDU Mini (educational-use-only licensing): <https://www.segger.com/news/segger-introduces-j-link-edu-mini-a-low-cost-j-link-for-education/>
- SEGGER J-Link BASE / BASE Compact pricing: <https://www.digikey.com/en/products/detail/segger-microcontroller-systems/8-08-00-J-LINK-BASE/2175882>, <https://www.digikey.com/en/products/detail/segger-microcontroller-systems/8-19-00-J-LINK-BASE-COMPACT/7386652>
- PEmicro U-MULTILINK-FX: <https://www.digikey.com/en/products/detail/nxp-usa-inc/U-MULTILINK-FX/3247905>
- Project spec: `docs/superpowers/specs/2026-09-13-ecu-reconciled-spec-design.md` §4, §5
