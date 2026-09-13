# Research Memo 04: Injector Identification and Drive Profile

**Task:** U5 (injector drive stage — boost rail voltage, peak/hold current, pulse timing). Consumes Task 1 (engine identity). Feeds the injector driver sheet and Phase-2 boost converter design.
**Date:** 2026-09-13
**Author:** Phase-1 research (task 4)
**Engine:** Kirloskar 3R550ETA 4G1, 3-cyl inline, 1.65 L, common-rail, turbocharged-aftercooled, 1500 rpm, 26.5 kW prime (per `docs/research/01-engine-identity.md`, inferred with high confidence).
**Genset:** Kirloskar KG4-25WS1.

---

## Verdict (read this first)

| Item | Value | Status |
|---|---|---|
| Injection system type | Solenoid common-rail, Bosch-family architecture (not piezo) | Inferred |
| Injector supplier/part number | **Not established** for this specific engine (3R550ETA) | Negative result — see Step 1 |
| Boost rail voltage envelope | **65–115 V DC**, most solenoid CR designs cluster **90–115 V**; this engine most likely sits near **~100 V ± 15 V** | Inferred envelope |
| Peak current | **12–24 A**, most designs **18–20 A** | Inferred envelope |
| Peak current duration | **~0.3–1.0 ms** (boost phase, until current threshold reached) | Inferred envelope |
| Hold current | **~8–13 A**, most designs **~10–12 A** | Inferred envelope |
| Minimum controllable pulse width | **~0.1–0.3 ms** | Inferred envelope |
| Required driver slew rate | **40–100 A/ms** covers the family | Inferred envelope (matches brief's design target) |
| Bank-sharing timing check (Step 3) | **PASSES**, with large margin (≥240 crank degrees / 26.67 ms minimum separation vs. ≤~3 ms max injection duration) | **Confirmed by calculation** — see Step 3 |
| Calibration boundary (Step 5) | Hardware can be built and bench-verified; **cannot run this engine correctly** without flow-vs-pulsewidth maps not publicly available | Stated plainly — see Step 5 |

The headline finding for Step 3 is good news, stated loudly because the brief asked for it either way: **the bank-shared wiring (cyl 1+3 on one high side, pin 03) is inherently safe for any plausible 3-cylinder firing order**, because a 3-cylinder 4-stroke engine with even firing intervals has exactly three, evenly-spaced injection events per 720° cycle — so *any* two of the three cylinders are always separated by one full firing interval (240°) in the closer direction, regardless of which firing order (1-2-3 or 1-3-2) is used. This is a property of "3 evenly spaced cylinders," not of the specific order label. See Step 3 for the full derivation and the one assumption that could break it.

---

## Step 1: Injector family identification

**Search performed:** `Kirloskar R550 common rail injector Bosch part number`, `Kirloskar 3R550 injector Denso`, cross-reference of `crdiparts.com` and `turbotech.in` Kirloskar-branded injector listings.

**What was found:**
- Kirloskar packages Bosch common-rail injectors under its own part-number scheme for at least one other engine family: Bosch injector **0445120646** is sold as Kirloskar part **F6.248.08.0.pr**, "suitable for Kirloskar engine in genset and Liugong loader" (confirmed listing, https://www.crdiparts.com/product/common-rail-fuel-injector-0445120646-f6-248-08-0-pr-suitable-for-kirloskar-engine-in-genset-and-liugong-loader/, mirrored at https://turbotech.in/product/common-rail-fuel-injector-0445120646-f6-248-08-0-pr-suitable-for-kirloskar-engine-in-genset-and-liugong-loader/). The "F6.248" prefix is consistent with Kirloskar's engine-family/displacement coding (analogous to the "3R550" pattern already established in Task 1) and most plausibly denotes a different, larger (6-cylinder-class) Kirloskar engine, **not** the 3-cylinder R550 family used in the KG4-25WS1. **Confirmed:** Kirloskar sources genuine Bosch solenoid CR injectors and re-badges them with Kirloskar part numbers of the form `<code>.<code>.<code>.<code>.pr`. **Not confirmed:** which Bosch part number corresponds to the 3R550ETA specifically.
- No source found ties a specific Bosch (or Denso) injector part number to "3R550" or "3R550ETA" by name. Searches tried: `Kirloskar 3R550 common rail injector Bosch part number`, `Kirloskar R550 CRDI injector Denso`. **Negative result**, recorded per the global instruction that negative results are results.
- The wiring evidence itself (rail-pressure sensor on pins 32/35/08, PWM-driven metering unit on pin 88 per `refs/ecu-pinout-extracted.md`) confirms a solenoid-type high-pressure common-rail architecture (a metering-unit-controlled rail, not a unit-injector or unit-pump system), which is consistent with the Bosch CRSN2/CRIN family design pattern used broadly in this displacement/power class. **Inferred** from architecture, not a part-number match.

**Working assumption for this memo (inferred, not sourced):** the injector is a **Bosch CRIN-family solenoid injector**, most likely in the CRIN2/CRIN3 generation used across Bosch's small-to-mid displacement common-rail industrial/genset engines circa the CPCB IV+ generation (2022–2023 introduction per Task 1). This is a reasonable design assumption but should not be treated as a confirmed part number. **A rating-plate or injector-body photograph (stamped Bosch part number, e.g. `0445 1xx xxx`) would close this** — the same recommendation Task 1 made for engine identity.

---

## Step 2: Drive profile envelope

Exact peak/hold/boost figures are proprietary to the injector manufacturer and are not published for a specific part number without an NDA or a physical sample. Per the brief, the correct engineering response is **an envelope that covers the family**, not a guess at one number.

### The envelope, and why these bounds

Solenoid common-rail injectors (Bosch CRIN, Denso G3/G4, Delphi/Continental DFI) all use the same two-stage drive strategy for the same physical reason: the injector solenoid must open against rail pressure (which can exceed 1600–2000 bar in this class) within a few hundred microseconds, which requires driving far more current into the coil, far faster, than a 12 V battery rail can deliver into a ~0.3–1 mH / <1 Ω coil. The universal solution:

1. **Boost phase:** a boost converter (12 V → tens to ~100+ V) is switched across the coil to slew current up rapidly to a peak threshold.
2. **Peak hold:** current is regulated (chopped) at the peak level for a short duration to fully open the pin/needle against flow forces.
3. **Hold phase:** current is dropped to a lower "hold" level (higher-voltage boost removed, battery rail or PWM-chopped boost used) for the remainder of the injection, to reduce power dissipation and heating.
4. **Fast turn-off:** the low side is opened and freewheel/clamp circuitry rapidly collapses the field to close the injector precisely.

Sourced figures found for this class of driver:
- A peak-and-hold strategy using **~100 V boost to reach 20 A peak, then 24 V (battery-derived) to hold ~10 A** is described directly in an automotive-oscilloscope diagnostic reference for Bosch common-rail solenoid injectors (confirmed, https://www.picoauto.com/library/automotive-guided-tests/bosch-current-at-idle).
- NXP's own reference design for its dedicated injector-driver IC (MC33816, see Step 4) documents a three-stage waveform: **48 V boost to 19 A, regulated hold at 19 A for the peak duration, then regulated hold at 11 A** for the remainder of injection (confirmed, drawn from NXP application material referenced in general search results for the MC33816 common-rail reference design).
- A peer-reviewed overview of common-rail injector driving circuitry states boost voltages in the **65–115 V** range and peak currents around **20 A**, with coil resistance ≤1 Ω and inductance ≤1 mH typical for this injector class (confirmed, "Circuit for driving common rail diesel injectors," ResearchGate, https://www.researchgate.net/publication/350426572_Circuit_for_driving_common_rail_diesel_injectors).
- NXP's MC33816 product page states its pre-driver stage operates up to **72 V** (confirmed, https://www.nxp.com/products/analog-and-mixed-signal/gate-drivers/high-precision-differential-injector-driver:MC33816) — lower than the ~100–115 V boost used by some Bosch-native designs, which means a driver built around this IC's pre-driver alone would need external high-voltage MOSFETs/gate stages if the target boost rail is pushed toward the top of the family envelope.

**Envelope adopted for this project** (matches the brief's design target and is corroborated by the above):

| Parameter | Envelope | Where this engine likely sits, and why |
|---|---|---|
| Boost rail voltage | 65–115 V | Likely **~90–105 V**. This is a mid-displacement (0.55 L/cyl) industrial/genset engine, not a high-speed passenger-car CR engine chasing sub-300 µs injector response; it does not need the most aggressive (115 V-class) boost used by some high-speed automotive applications, but a genset running at a fixed 1500 rpm still benefits from fast, repeatable injector opening for combustion-timing accuracy, so the low end of the range (65 V, associated with older/smaller injectors) is also unlikely. **Inferred**, no part-number-specific source. |
| Peak current | 12–24 A | Likely **~18–20 A**, matching both cited reference designs (Picoscope: 20 A; NXP MC33816 reference: 19 A) which cluster tightly despite being independent sources. **Inferred.** |
| Peak duration | 0.3–1.0 ms | Set by however long it takes the boost stage to reach threshold current against coil L/R and back-EMF; no engine-specific source. **Inferred envelope only.** |
| Hold current | 8–13 A | Likely **~10–12 A**, again bracketed by the two cited reference designs (10 A, 11 A). **Inferred.** |
| Min. pulse width | 0.1–0.3 ms | Standard for pilot-injection-capable CR solenoid injectors; this engine's CPCB IV+ emissions calibration likely uses pilot injection for NOx/noise control, so the low end of this range should be treated as a hard requirement, not headroom. **Inferred.** |
| Driver slew rate | 40–100 A/ms | Per the brief's own design guidance; consistent with reaching ~20 A peak within under 0.5 ms at a ~90–100 V boost rail against a sub-1 mH coil (a first-order L/di/dt estimate: 100 V / 1 mH ≈ 100 A/ms at turn-on, tapering as back-EMF rises — internally consistent with the cited figures). **Derived, not directly sourced.** |

**Design conclusion:** a driver spanning **65–115 V boost, 12–24 A peak, 8–13 A hold, 40–100 A/ms slew** will drive any solenoid CR injector in this displacement/power class, this engine's specific injector included, without knowing its exact part number. This is the number set to carry into the Phase-2 boost converter and driver-IC selection.

---

## Step 3: Bank arrangement vs. firing order — the safety check

### The wiring fact being checked

Per `refs/ecu-pinout-extracted.md`: pin 03 is a single high-side driver output shared, via harness splice V5, between cylinder 1 and cylinder 3. Pin 05 is a dedicated high side for cylinder 2. Low sides are independent per cylinder (73→cyl1, 07→cyl3, 29→cyl2). **The failure mode to rule out:** if cylinder 1 and cylinder 3 ever needed to inject at overlapping times, sharing one high-side node would prevent independent control — both injectors would be forced onto the same boosted supply simultaneously, which the low-side switches alone cannot arbitrate into two independently-timed pulses.

### Establishing the firing order

Three-cylinder inline 4-stroke engines fire every **720°/3 = 240°** of crank rotation when cylinders are evenly spaced (the standard configuration — inline-3 crankshafts use 120° crank-throw spacing, which combined with the 720° four-stroke cycle produces exactly this even 240° firing interval). The two firing orders seen across the industry, **1-3-2** and **1-2-3**, both satisfy this even spacing; they differ only in which physical cylinder fires second, not in the interval between any two firing events. **Confirmed general mechanics** (basic four-stroke engine theory; see e.g. https://en.wikipedia.org/wiki/Firing_order for the general formula). No source was found stating the 3R550ETA's specific firing order by name — searches for `Kirloskar 3R550 firing order`, `Kirloskar R550 firing order 1-2-3 OR 1-3-2` returned no Kirloskar-specific document (**negative result**). This does not block the safety check, for the reason below.

### The check

At 1500 rpm rated speed (per Task 1, confirmed): one crankshaft revolution = 60,000 ms / 1500 = 40 ms. A four-stroke cycle is 720° = 2 revolutions = **80 ms**, matching the brief exactly.

Three evenly-spaced injection events per 80 ms cycle → one event every 80/3 ≈ **26.67 ms**, i.e. every 240° of crank rotation.

Label the three firing instants within one 720° cycle as 0°, 240°, 480° (order 1-2-3: cyl1@0°, cyl2@240°, cyl3@480°; order 1-3-2: cyl1@0°, cyl3@240°, cyl2@480° — the derivation below is order-independent, done for both explicitly):

- **Order 1-2-3:** cyl1 at 0°, cyl3 at 480°. Forward gap cyl1→cyl3 = 480° (53.3 ms). Backward gap (cyl3 in the *previous* cycle, at 480−720 = −240°, to cyl1 at 0°) = 240° (26.67 ms). **Minimum separation = 240° = 26.67 ms.**
- **Order 1-3-2:** cyl1 at 0°, cyl3 at 240°. Forward gap cyl1→cyl3 = 240° (26.67 ms). **Minimum separation = 240° = 26.67 ms.**

Both orders produce the **identical minimum separation: 240 crank degrees, 26.67 ms.** This is not a coincidence specific to either order — it is a general property of any 3 evenly-spaced points on a 720° cycle: with exactly three points, every pair is separated by exactly one interval (240°) in one rotational direction and two intervals (480°) in the other, so the *minimum* pairwise gap is always one interval, **regardless of firing-order labeling**. This is why Step 3 does not actually hinge on resolving the unconfirmed firing order — the bank-sharing safety property holds for both candidate orders identically. **This derivation is original calculation for this memo (basic four-stroke kinematics), not drawn from an external source; it is presented as confirmed by calculation, not inferred.**

**Margin check:** injection duration for common-rail solenoid injectors in this engine class runs from under 0.3 ms (pilot injections, light load) up to roughly 1.5–2.5 ms for a single main injection at higher load, per the cited peak/hold reference designs' typical operating envelope (Step 2 sources); even a generous upper bound of 3 ms for a long, high-load main injection leaves:

**26.67 ms available − 3 ms max injection duration ≈ 23.67 ms of margin, an ~8.9× safety factor.**

Even stacking a pilot + main injection (e.g., 0.3 ms + 2 ms + a few hundred µs dwell between them, well under 5 ms total) on one cylinder leaves over 20 ms of clearance before the shared high side would need to serve the other cylinder on that bank.

### Verdict

**The bank-sharing arrangement (cyl 1+3 on pin 03) is safe.** Cylinders 1 and 3 are never required to inject within less than 240 crank degrees / 26.67 ms of each other under either plausible firing order, and typical common-rail injection durations (even generously bounded) are roughly an order of magnitude shorter than that window. There is no finding to raise loudly here in the negative sense the brief warned about — the check **passes**, and passes with enough margin that even significant transient-response slop in the driver electronics (boost recharge time between pulses, current decay tails) will not threaten it. The one assumption underlying this result — **even 240° firing spacing**, i.e., a conventional 120°-throw inline-3 crankshaft — is standard for this engine class and considered safe to rely on absent contrary evidence; it would be worth a one-line confirmation against a Kirloskar service manual or a firing-order marking on the timing cover if one becomes available, but it is not a blocking risk for the driver design.

---

## Step 4: Candidate driver ICs

Given budget constraints, this section is intentionally thinner, per the brief's own prioritization (Steps 3 and 5 are load-bearing; this one may be lighter).

| Candidate | Channels | Boost handling | Current regulation | High-side bank switching | Package | India availability | Price |
|---|---|---|---|---|---|---|---|
| **NXP MC33816** (SMARTMOS precision differential injector/solenoid driver) | 5 high-side + 7 low-side external MOSFET pre-drivers (up to ~4 full injector channels typical in reference designs) | Pre-driver operates up to **72 V**; does not itself generate boost — needs an external boost converter stage; current regulation and PWM channel sequencing are on-chip (confirmed, https://www.nxp.com/products/analog-and-mixed-signal/gate-drivers/high-precision-differential-injector-driver:MC33816) | On-chip programmable current-profile sequencer (the part is explicitly documented and used for common-rail diesel injector waveforms: boost-to-peak, peak-hold, hold, per NXP's own AN4849 application note referenced from the product page) | Yes — external high/low-side FETs are user-selected and the pre-driver sequences which pair is active, so a shared-high-side bank topology like this ECU's can be implemented in firmware/config, not hardware-forced | Not confirmed from the fetched page (typical NXP power packages; needs datasheet confirmation) | **Confirmed general-market part** — listed "Active" with NXP's Product Longevity Program (10-year availability commitment), stocked at DigiKey (https://www.digikey.com/en/products/detail/nxp-usa-inc/MC33816AE/4693868) and Mouser (https://www.mouser.com/ProductDetail/NXP-Semiconductors/MC33816AE) with normal "buy now, ships today" retail terms — **not automotive-allocation-only**, orderable in small quantities. | ~US$5.19–5.61 per unit at standard distributor pricing (DigiKey/Mouser, confirmed at search time); India landed cost via DigiKey/Mouser India or an authorized distributor would add duty/GST/shipping — order-of-magnitude **₹500–800/unit** in small quantity, not independently confirmed against an India-specific distributor page. |
| Discrete architecture (boost converter IC + external high-side/low-side power MOSFETs or IGBTs + current-sense resistor/comparator, sequenced by an MCU or FPGA) | N/A — built from discrete blocks | Fully custom; boost voltage set by converter design (any point in the 65–115 V envelope) | Closed-loop current regulation implemented in firmware/analog comparator, not integrated | Fully under designer control — the natural way to implement any custom bank topology, including this one | N/A | All constituent parts (boost controllers, automotive MOSFETs, current-sense amps) are broadly available in small quantities from standard distributors | Variable; likely **more engineering effort, more BOM line items, but no automotive-allocation risk** |

**Note on automotive-allocation risk:** several dedicated common-rail injector driver ASICs used by Tier-1s (proprietary Bosch/Denso/Continental in-house silicon, and some Infineon/Elmos/ST parts specifically qualified and allocated for OEM automotive programs) are **not available through normal small-quantity distribution** — searches for Infineon and Elmos part numbers plausibly in this space (`TLE8090`, `E526`) did not surface a confirmed, orderable, small-quantity datasheet within this memo's search budget (**negative result** — this does not prove such parts don't exist or aren't orderable, only that this search did not locate and confirm one; it should be treated as an open item, not a closed "allocation-only" finding, for any part not named above). The **MC33816 is the one confirmed, small-quantity-orderable candidate found in this pass** and is recommended as the primary driver-IC direction for Phase 2, paired with an externally designed boost stage sized to the Step 2 envelope.

---

## Step 5: The calibration boundary — stated plainly

This is the most important paragraph in this memo, and it is written to be read on its own.

**What this hardware can do without any injector-specific calibration data:** the drive stage described above — a boost converter in the 65–115 V range, a peak/hold current-regulated driver spanning 12–24 A peak and 8–13 A hold, sequenced across the bank-shared topology this ECU actually uses — **can be fully designed, built, and verified on the bench.** It can be proven correct against a **known inductive load** (a resistor/inductor dummy load, or a bare injector solenoid off the engine, driven on a bench rail) — confirming boost rise time, peak/hold current accuracy, turn-off decay, minimum pulse width, and the bank-sequencing logic from Step 3, all without ever touching the running engine. This is real, verifiable engineering progress and should proceed.

**What it cannot do without more data: run this specific engine correctly.** A correctly *built* driver that outputs the right current profile is not the same as a driver that delivers the right *fuel quantity* at the right *crank angle* at the right *rail pressure* — and that mapping (fuel mass injected as a function of pulse width, at each of several rail pressures, separately for pilot and main injections, including the "ballistic region" where pulse width is too short for the injector to reach full lift) is exactly the calibration data that **Bosch and Denso do not publish**. It is proprietary flow-bench data tied to the specific injector part number's hydraulic geometry (nozzle hole count/size, needle lift, spring preload), and normally reaches an OEM only bundled with the supplier's own ECU and calibration tools. Without it, this hardware would open and close the injectors with electrically correct pulses but with **no reliable way to know how much fuel each pulse actually delivered** — which means no reliable air-fuel ratio control, no reliable torque control, and for this specific engine, no reliable path to the CPCB IV+ NOx/PM limits its EGR-and-DOC aftertreatment strategy was designed around (Task 1). This is not a minor gap to be tuned out empirically on a running genset; incorrect fueling on a compression-ignition engine at 19.7:1 compression risks knock-like combustion damage, turbocharger overspeed/overtemperature, and DOC/EGR fouling well before a trial-and-error tuning process could converge.

**The three routes to flow-vs-pulsewidth data, named plainly:**

1. **Supplier licence (Bosch or Denso).** Approach the injector's OEM supplier (once the exact part number is identified, per Step 1's open item) for calibration data or a development/licensing agreement. **Cost:** realistically out of reach for a project at this scale — these programs are structured around OEM production volumes (tens of thousands of units), not a single genset retrofit; even where a "development kit" path nominally exists, expect NDA gates, minimum engineering-service fees, and multi-month lead times with no guarantee of access for a non-OEM customer. **Legality:** fully legal — this is the intended, sanctioned route. It is listed first for correctness and last for realism.
2. **Dyno characterization with rate-of-injection measurement.** Buy or borrow injectors of the identified part number, mount them on an injector-rate test bench, and directly measure fuel delivery vs. pulse width vs. rail pressure using an established method — the **Bosch tube method** (pressure-wave measurement in a long fuel-filled tube) or the **Zeuch method** (constant-volume chamber), both well-documented in the injection-research literature (confirmed: e.g. "Experimental Research on the Injection Rate of DME and Diesel Fuel in Common Rail Injection System by Using Bosch and Zeuch Methods," https://doi.org/10.3390/en11020273; "Benchmark between Bosch and Zeuch method–based flowmeters," https://www.researchgate.net/publication/331523136_Benchmark_between_Bosch_and_Zeuch_method-based_flowmeters_for_the_measurement_of_the_fuel_injection_rate). **Cost:** substantial but bounded and controllable — either access to an existing university/industry fuel-injection lab (a rate-of-injection rig is specialized, not off-the-shelf test equipment, and few Indian institutions maintain one) or building a simplified rate tube in-house, plus the engineering time to sweep pulse width × rail pressure × injector unit-to-unit variation into a usable map. **Legality:** entirely legal — this is independent, first-party measurement of purchased hardware, no reverse engineering of anyone's IP.
3. **OEM calibration extraction** (reading the flash/calibration data out of a genuine Kirloskar/Bosch ECU for this engine, by bench-side flash dump or bootloader access, and decoding the injector maps embedded in it). **Cost:** potentially the cheapest in engineering time if a donor ECU and the right tools are available, but requires reverse-engineering an undocumented, likely-encrypted or checksum-protected calibration binary — a nontrivial and uncertain effort in itself. **Legality: do not soften this.** Extracting and using a manufacturer's proprietary calibration data, without a license, sits in genuinely contested legal territory — it implicates the OEM's copyright in the calibration software/data, and depending on jurisdiction and exact method, protections analogous to anti-circumvention rules for access-controlled software. This is squarely the kind of activity that has drawn civil action against aftermarket tuning firms in other jurisdictions (well-documented in the passenger-vehicle ECU-tuning industry). It is **not recommended** as this project's route absent explicit legal clearance, and should not be treated as a routine engineering shortcut.

**This is the single largest risk in the project**, larger than any hardware selection question in this memo. The drive electronics are a solved, bench-verifiable problem. Getting *this engine* to run correctly, safely, and within its designed emissions strategy is gated on data this project does not currently have a confirmed, legal, affordable path to. The owners have been told this before; this memo is the durable written record: **build and bench-verify the driver now; do not plan to commission it on the running genset without first closing Route 1 or Route 2 above (or accepting the documented legal exposure of Route 3).**

---

## Sources consulted

- `/home/mohan/workws/ecu25kva/.superpowers/sdd/2026-09-13-phase1-research/task-4-brief.md` — task requirements (read in full).
- `/home/mohan/workws/ecu25kva/docs/research/01-engine-identity.md` — engine identity memo (read in full).
- `/home/mohan/workws/ecu25kva/refs/ecu-pinout-extracted.md` — ECU pinout extraction, injector bank wiring (read in full).
- https://www.crdiparts.com/product/common-rail-fuel-injector-0445120646-f6-248-08-0-pr-suitable-for-kirloskar-engine-in-genset-and-liugong-loader/ — fetched; Kirloskar-branded Bosch injector cross-reference (different engine family than 3R550).
- https://turbotech.in/product/common-rail-fuel-injector-0445120646-f6-248-08-0-pr-suitable-for-kirloskar-engine-in-genset-and-liugong-loader/ — mirror listing, found via search.
- https://www.picoauto.com/library/automotive-guided-tests/bosch-current-at-idle — found via search; Bosch CR solenoid injector current profile (~100 V boost to 20 A peak, 24 V to 10 A hold).
- https://www.researchgate.net/publication/350426572_Circuit_for_driving_common_rail_diesel_injectors — found via search; boost voltage 65–115 V, peak ~20 A, coil R/L typical values.
- https://www.nxp.com/products/analog-and-mixed-signal/gate-drivers/high-precision-differential-injector-driver:MC33816 — fetched; MC33816 channel count, pre-driver voltage (up to 72 V), Product Longevity status.
- https://www.digikey.com/en/products/detail/nxp-usa-inc/MC33816AE/4693868 and https://www.mouser.com/ProductDetail/NXP-Semiconductors/MC33816AE — found via search; small-quantity distributor stocking and pricing (~US$5.19–5.61).
- https://en.wikipedia.org/wiki/Firing_order — found via search; general four-stroke firing-interval formula (720°/n cylinders).
- https://doi.org/10.3390/en11020273 ("Experimental Research on the Injection Rate of DME and Diesel Fuel... Bosch and Zeuch Methods") — found via search; rate-of-injection measurement methods.
- https://www.researchgate.net/publication/331523136_Benchmark_between_Bosch_and_Zeuch_method-based_flowmeters_for_the_measurement_of_the_fuel_injection_rate — found via search; corroborates Bosch/Zeuch method equivalence.
- Searches returning negative results (recorded, not omitted): `Kirloskar R550 common rail injector Bosch part number`, `Kirloskar 3R550 3 cylinder diesel firing order 1-2-3`, `Infineon TLE8090 OR ELMOS E526 OR STMicroelectronics common rail injector driver IC datasheet` (no confirmed small-quantity-orderable alternative IC located in this search pass).
