# Research Memo: Injector Turn-Off / Recirculation Circuit

**Task:** Close the gap `injector_boost.cir`'s RESULT NOTE names — turn-off is not
modelled, no clamp/recirculation path is drawn anywhere in the design, and
interrupting 18 A in 200 µH releases ~32 mJ per event with nowhere defined for
it to go. This memo establishes what real automotive injector drivers do about
that, before a SPICE block gets built.
**Date:** 2026-09-18
**Scope:** Read-only research. No repo files modified, nothing committed.

---

## Verdict (read this first)

Production peak-and-hold injector drivers do **not** use a plain freewheel
diode for turn-off — that topology is real (it's the textbook baseline and
the cheapest option) but it is also the slowest, and slow turn-off is exactly
what this project's boost rail was built to avoid on the *opening* side. The
turn-off side has the same problem in reverse. Two topologies dominate
production practice for this injector class: **active/Zener clamping** (fast,
dissipative, tunable voltage) and **recirculation of the coil's turn-off
energy back into the boost reservoir capacitor** (fast, largely
non-dissipative, and confirmed as real automotive practice going back to at
least a 1988 Magneti Marelli diesel-injector patent, not a textbook
idealization). For this design, **recirculation to the existing 100 V / 47 µF
boost rail is the recommended topology**, clamped by a diode rated for the
boost-rail voltage: it collapses 18 A in 200 µH in about **36 µs** (physics
below), and the ~32 mJ recovered per event is the same order of magnitude as
the ~7.3 V peak-phase droop `boost_converter.cir` already calculated — this
is not a rounding error, it changes that block's charge balance.

**Sourcing note, stated as plainly as memo 09 states its own:** this pass
retrieved one strong, directly on-topic primary source in full (Nexperia
AN50003, an application note that surveys exactly the four candidate
topologies the task asked about, with a quantified loss/performance
comparison table) and one confirming patent (Marelli Autronica, 1988,
Google Patents full text) that is diesel-injector-specific and explicitly
diesel-electro-injector. Several other leads that looked promising by title
(ST L9781, NXP AN4849, the ISO 7637-2 standard text itself) **could not be
retrieved** — repeated 403s, timeouts, or a 404 — and are recorded as
negative results below rather than filled in from memory or a search
snippet dressed up as a document. TI DRV8701 was checked and ruled out: it
is a brushed-DC-motor H-bridge driver, not an injector-class part, despite
surface-level keyword overlap ("solenoid control" appears in its marketing
copy).

---

## 1. What actually absorbs the coil energy at turn-off

### 1.1 Nexperia AN50003, "Driving solenoids in automotive applications" — **CONFIRMED**, retrieved and read in full
https://www.digikey.com/Site/Global/Layouts/DownloadPdf.ashx?pdfUrl=7547AD78C870436881732FA36D2AAAFA
(Nexperia B.V., Rev 1.0, 4 December 2020 — an automotive-solenoid-driver
application note, explicitly citing "peak-and-hold" fuel injection current
profiles as its motivating example, §3, Fig. 3)

This is the single best-matched source found in this pass: it surveys
**exactly** the four candidate topologies named in the task, with SPICE-based
loss and performance numbers (their reference case: 12 V battery, 5 mH
inductor, 3 A peak, 1.2 A hold — a much smaller solenoid than this injector,
but the physics and the relative comparison transfer directly). Quoting
Table 1 and Table 2 (§5) in full:

| Topology | Total energy loss (mJ) | Cost | Speed | Efficiency | Reliability |
|---|---|---|---|---|---|
| Free-wheeling diode | 17.0 | Low | Low | High | Long term |
| MOSFET avalanche | 20.7 | Low | Medium | Low | Long term |
| Active clamp (Zener, drain-to-gate) | 20.7 | Low | Medium | Low | **Questionable** |
| Boost converter (energy recovery) | 26.0 | High | High | High | Long term |

Their own text on the "Questionable" reliability rating for active clamp
(§4.3), quoted directly: *"During active clamp there are high energy charge
carriers generated in proximity of the MOSFET's gate oxide. These carriers
might be injected into the oxide and cause damage. Over many active clamp
cycles the gate oxide can wear out and cause parametric shift and ultimately
device failure. Currently it is not recommended to use MOSFETs in repetitive
active clamp."**This directly rules out the naive Zener-across-the-FET
version of "active clamp" for a component that will do this thousands of
times a minute for the life of the genset.**

On the boost/recovery topology (§4.4), quoted: *"During the Peak and Hold
Phases the nominal battery voltage is switched, as in the previous cases.
This allows for fast actuation of the solenoid, but also the energy from the
solenoid is regenerated into the DC link capacitor of the boost converter...
Although the losses appear to be higher in the Boost topology, the
recuperation of the energy means that its efficiency is on par with the
free-wheeling topology, despite using higher R_DSon components."*
(§5) — i.e. the boost/recovery topology has the **highest absolute component
losses in their table but the best net efficiency**, because most of the
32 mJ-scale energy is returned to the rail rather than burned.

On the free-wheeling diode being the slowest (§4.1), quoted: *"Compared to
the other driver topologies, the free-wheeling driver is simple, has a low
component count, but it is the slowest due to the inductor voltage being
approximately equal to the battery voltage."*

### 1.2 The industry-standard schematic vocabulary — **CONFIRMED** across two independent IC datasheets

- **Infineon TLE8242-2** datasheet, retrieved in full (rev 1.0, Feb 2010):
  https://www.infineon.com/dgdl/Infineon-TLE8242_2-DS-v01_00-en.pdf — this is
  a **low-side constant-current pre-driver IC**, explicitly stated to be for
  "Variable Force Solenoids (e.g. automotive transmission solenoids)" and
  other constant-current solenoids (EGR, idle air control), not a diesel
  common-rail injector driver — **important scale mismatch**: its current
  range is 0–1.2 A and its absolute max POSx/NEGx rating is 50 V, roughly an
  order of magnitude below this injector's 18 A / 100 V. It is cited here
  only for what it confirms about topology convention, not for numbers.
  §1.3.1 and §1.3.2, quoted directly: *"Note: An external flyback clamp is
  required in [Direct PWM] configuration otherwise the IC may be damaged"*
  and *"Note: An external recirculation diode is required in [constant
  current mode] configuration otherwise the IC may be damaged."* **The IC
  itself never integrates the clamp/recirculation element — it is always an
  external, designer-chosen part**, which matches what this project needs to
  design rather than buy.
- **ST L9781** — **SNIPPET only, not retrieved**. Two direct fetch attempts
  (st.com PDF, alldatasheet mirror) both failed — one timed out, one
  returned HTTP 403. What search-result snippets say (unverified against the
  document itself): the L9781 is a multi-valve pre-driver with an integrated
  boost step-up converter reported as "V-boost up to 80 V," and its
  recirculation/clamp behaviour is described in a snippet as *"Fast
  recirculation happens through clamp activation, with S2 open and clamp on
  S1 activated"* — language consistent with recirculation back toward the
  boost-side switch/rail rather than a simple flyback-to-ground diode. This
  is recorded as a data point corroborating the recirculation-to-boost
  topology, but it is explicitly **not** elevated to CONFIRMED status because
  the datasheet itself was never read.

### 1.3 Energy recovery in real diesel-injector drive circuits — **CONFIRMED** via patent full text (Google Patents), not a datasheet
US Patent 4,862,866, "Circuit for the piloting of inductive loads,
particularly for operating the electro-injectors of a diesel-cycle internal
combustion engine," assignee **Marelli Autronica S.p.A.** (Magneti
Marelli's electronics arm — a genuine Tier-1 diesel-ECU supplier, a Bosch
competitor), filed 22 August 1988.
https://patents.google.com/patent/US4862866A/en

Quoted directly from the retrieved claims/description text: the circuit
includes *"energy-recovery circuit means controlled by the unit and adapted
to enable part of the reactive energy stored in the load to be recycled
towards the supply VB each time a load is deactivated."* This is explicit,
diesel-electro-injector-specific, decades-old confirmation that **energy
recovery at injector turn-off is real production-line thinking, not a
textbook flourish invented for this memo.** No numeric clamp voltage or
recovered-energy figure is given in the retrieved text — the patent
describes the mechanism (an OR-diode network into a junction with a
recovery switch SW4 back to the supply), not performance numbers.

A second patent, EP0622536A2 (Chrysler, priority 1993), was also retrieved
via Google Patents and is recorded for completeness but is **not** treated
as strong evidence for this design: it is a **gasoline two-stroke
direct-injection** patent, not diesel common-rail, and its numbers (flyback
clamped to "15–20× battery potential," i.e. ~180–240 V on a 12 V system,
against an 8–10× battery boost voltage of ~96–120 V) describe a
self-boosted clamp stage deliberately driven *above* the boost rail, a
different design choice than recirculating into the existing boost
capacitor. Noted as related prior art, not as a number to adopt.

### 1.4 Bosch EDC17/EDC7 architecture — **negative result**
No public technical description of Bosch's own injector-driver ASIC
internals (clamp topology, voltage, or recirculation) was found. Search
results for EDC17 return tuning/remapping community material (map
structures, torque-based control philosophy) with no circuit-level
disclosure. This is consistent with memo 04's own finding that OEM
injector-driver silicon and calibration data are not publicly documented —
recorded here as a negative result, not filled in by inference from the
adjacent (and more open) NXP/Nexperia/Infineon material.

### 1.5 TI DRV8701-class — **ruled out, not applicable**
The DRV8701 datasheet (https://www.ti.com/lit/ds/symlink/drv8701.pdf) is a
single H-bridge **gate driver for a 5.9–45 V, bidirectional brushed-DC
motor**. It is not a peak-and-hold constant-current injector driver and has
no boost-voltage handling in this part's role. It surfaced in search results
only because "solenoid control" appears in TI's generic marketing
description for the DRV87xx/DRV870x family. **Recorded as a checked-and-
rejected candidate, not a silent omission.**

---

## 2. Clamp voltage vs turn-off time — the actual numbers

### 2.1 The physics, cross-checked against a retrieved source
`di/dt = V_clamp / L` while the coil discharges above zero, so
`Δt ≈ L·ΔI / V_clamp`. This is not a new derivation — it is exactly the
relation Nexperia's AN50003 uses (§4.1, Eq. 1: `Δt = L·ΔI/V`), and their own
worked numbers cross-check cleanly: their free-wheeling case (12 V, 5 mH,
1.2 A hold current) gives `Δt = 5e-3 × 1.2 / 12 = 0.5 ms`, matching their
stated "close to 0.5 ms" (§4.1). Their avalanche case, clamped at a
measured 68 V (Fig. 7, read directly off their MOSFET avalanche plot) against
the same 5 mH/1.2 A step, gives `Δt = 5e-3 × 1.2 / 68 ≈ 88 µs`, and their
text states the reduction is "close to... a five-fold reduction" — 12/68 ≈
0.176, i.e. a 5.7× voltage ratio, consistent with their "five times faster
with five times larger voltage" framing (§4.2). **This cross-check is
original arithmetic done for this memo against Nexperia's own published
numbers, not itself sourced — marked INFERRED, but it validates that the
formula and their reported figures agree with each other.**

### 2.2 Applied to this injector — **INFERRED, derived, not sourced for this specific part**
Using this project's own numbers (18 A, 200 µH, from `injector_boost.cir`):

| Clamp path | Clamp voltage | Turn-off time (18 A → 0) | Note |
|---|---|---|---|
| Freewheel to battery | ~13.5–14 V | **~257–267 µs** | Baseline, slowest |
| Avalanche/Zener active clamp | 68 V (Nexperia's example FET rating) | **~53 µs** | ~5× faster, matches their ratio |
| Recirculate to boost rail | 100 V (this project's existing rail) | **~36 µs** | Recommended path, see §3 |
| Dedicated higher clamp above boost | 150 V (illustrative) | **~24 µs** | Faster still, needs a part rated well above the 100 V rail |

At a 1–3 ms injection duration (memo 04's envelope, corroborated by
`injector_boost.cir`'s own framing), even the slowest option (267 µs,
battery freewheel) is a smaller fraction of the injection window than the
38 µs turn-on ramp is — but turn-off precision matters disproportionately
for **small-quantity pilot injections**, where end-of-delivery timing
directly sets fuel quantity. No source in this pass gave a quantified
"needle closes N µs after current reaches zero" mechanical lag figure for
this injector class — that remains an open item, same as memo 04's Step 5
calibration gap. **This whole table is INFERRED (derived arithmetic), not a
number pulled from a source for this specific injector** — the only
source-backed clamp-voltage figure found in this pass is Nexperia's own
68 V MOSFET avalanche example, which is a generic automotive part rating,
not an injector-specific spec.

### 2.3 Why higher clamp voltage is not free — confirmed qualitatively, not quantitatively
AN50003 states plainly (§4.2, §4.3) that faster (higher-voltage) turn-off
concentrates the *same total energy* into a shorter, hotter pulse, and that
this is the mechanism behind their "Questionable" reliability flag on active
clamp (gate-oxide stress) and their explicit statement that existing MOSFET
datasheets give only "scarce data" on repetitive avalanche ratings (§6).
**No source in this pass gave a quantitative die-temperature-rise-per-volt
figure** — that would require a specific FET's thermal datasheet and is a
detailed-design question, not a topology question. Recorded as an open item
rather than estimated.

---

## 3. Energy recovery — real practice or textbook complication

**Real practice, with a caveat about how much it matters here.**

- Confirmed via the Marelli Autronica 1988 patent (§1.3 above): energy
  recovery at diesel-injector deactivation is documented production-supplier
  engineering, not a modern textbook idea being retrofitted onto this
  project.
- Confirmed via Nexperia AN50003 (§1.1 above): the boost-recovery topology
  has the best net efficiency of the four surveyed, specifically *because*
  turn-off energy is regenerated into the DC-link capacitor rather than
  burned.
- SNIPPET-level (ST L9781, not retrieved in full) is consistent with the
  same idea in a currently-sold automotive injector pre-driver part.

**Does it meaningfully change this project's boost converter load?** This is
where the sourcing runs out and the memo has to say so: **no source found
gives a quantitative "% duty cycle reduction" figure for recovery vs. no
recovery on a diesel common-rail boost stage.** What follows is original
arithmetic against this project's own `boost_converter.cir` numbers, marked
**INFERRED**:

- Coil turn-off energy per event: ~32.4 mJ (`0.5 × 200µH × 18A² = 32.4 mJ`,
  matching `injector_boost.cir`'s RESULT NOTE figure of "about 32 mJ").
- `boost_converter.cir`'s reservoir is 47 µF at a 100 V setpoint, and its
  own RESULT NOTE calculates a **7.3 V droop** from the peak-phase charge
  draw (342 µC / 47 µF).
- If that same 32.4 mJ were returned to the same 47 µF/100 V capacitor
  (energy balance `ΔE = C·V·ΔV`, linearised around 100 V):
  `ΔV = ΔE / (C·V) = 32.4e-3 / (47e-6 × 100) ≈ 6.9 V`.
- **That recovered-voltage bump (≈6.9 V) is essentially the same size as the
  droop the peak-phase draw already causes (7.3 V).** This is not a small
  correction — on this project's own reservoir sizing, full recovery would
  come close to cancelling the very droop `boost_converter.cir` exists to
  characterize. It would change the charger's required average current
  (`Bchga`'s 50 mA figure) and could push the rail *above* its 100 V
  setpoint on back-to-back events if the regulator doesn't shed the excess,
  which is exactly the "climbed past target, reported 122 V" failure mode
  that block's own header describes for an unregulated charger.

**This is the concrete reason recovery is worth building here, not a
default recommendation copied from the literature**: it isn't a minor
efficiency nicety, it is the same order of magnitude as a number this
project has already calculated and cared about.

---

## 4. Thermal — events per second and average dissipation

**Assumptions stated plainly, because the task brief itself contains a
contradiction worth flagging:** the task text refers to "a 4-cylinder at
1500 rpm genset speed" in one clause and then names the actual engine as
"3GK550ETA 4SR1, 3-cylinder" in the same sentence. Per memo 04 (confirmed,
engine identity task), **this engine is a 3-cylinder** (Kirloskar 3GK550ETA
4SR1, 3-cyl inline, KG4-25WS1 genset). This memo uses **3-cylinder**, not 4,
and flags the discrepancy rather than silently picking one.

**Derivation (original calculation, INFERRED, following memo 04's own
Step 3 method exactly):**
- At 1500 rpm: one crank revolution = 40 ms; a 4-stroke cycle (720°) = 2
  revolutions = **80 ms** (matches memo 04 and `boost_converter.cir`'s own
  26.67 ms per-cylinder figure: 80/3 = 26.67 ms).
- Assumption: pilot + main + post injection per cylinder per cycle = **3
  injection events per cylinder per 720° cycle**. This is stated as an
  assumption because no source in this pass (or in memo 04) gives a
  confirmed injection-strategy count for this specific engine/calibration —
  it is a reasonable assumption for a CPCB IV+-class common-rail genset
  (memo 04 already assumes pilot-injection capability is a hard requirement
  for its minimum-pulse-width figure), not a measured fact.
- Total events per cycle: 3 cylinders × 3 injections = **9 events / 80 ms**.
- **Events per second: 9 / 0.080 s = 112.5 Hz.**

**Worst-case average dissipation**, assuming every one of the 9 events
collapses from the full 18 A peak (i.e., assuming a purely dissipative
clamp — freewheel-to-battery or avalanche/Zener, not the recovery topology
recommended in §3):
`P_avg = 32.4 mJ × 112.5 /s ≈ 3.6 W`.

This is a **modest, not alarming, average number** — well within what a
TO-220/DPAK-class clamp FET or Zener can shed continuously, even with a
fairly restrained heatsink. The reason it still matters is not the average,
it's the **peak instantaneous dissipation during each ~30–50 µs clamp
interval** (32.4 mJ delivered in ~36–53 µs is a multi-hundred-watt
*instantaneous* pulse into the clamp element even though the time-averaged
figure is small) — this is precisely the stress mode AN50003 flags as
"Questionable" for active-clamp reliability (§1.1) and the reason its own
avalanche-rated parts are only characterized up to single-digit-mJ
per-event energies (their BUK9K35-60RA example: 4.9 mJ/event, ~2.5 billion
cycle life at that energy, §6) — **an order of magnitude below this
injector's 32.4 mJ per event.** No source in this pass characterizes a
repetitive-avalanche or active-clamp part rated for 32 mJ/event at anything
like injector-relevant cycle counts; this is recorded as an open item for
the eventual FET selection, not answered here. **This is exactly the
argument for recirculating the energy into the boost cap rather than
dissipating it in a clamp device at all** — it sidesteps the question of
whether a suitably-rated dissipative part even exists in this energy class.

If pilot/post events are assumed to turn off from hold current (~10 A) 
rather than full peak (plausible if they are short enough to be within the 
hold phase at cutoff, though memo 04 notes the boost ramp to 18A takes only 
~38 µs, well under the ~100–300 µs minimum pulse width, so even short pilot 
pulses likely do reach peak current before cutoff) — the worst case above 
should be treated as the design figure, not a conservative upper bound to be 
discounted.

---

## 5. ISO 7637-2 / CISPR 25 implications of the turn-off edge

**Partially sourced — the standard's own text could not be retrieved.**

- An attempt to fetch the ISO 7637-2:2011 standard text directly (a
  third-party PDF mirror) returned **HTTP 401 (paywalled/blocked)**. The
  official standard was not retrieved in this pass. What follows is drawn
  from search-result summaries describing the standard's pulse definitions
  — **SNIPPET level**, not confirmed against the standard itself.
- Per those snippets: **ISO 7637-2 pulse 2a** is specifically defined to
  simulate *"transients due to sudden interruption of currents in a device
  connected in parallel with the DUT due to the inductances of the wiring
  harness"* — this is, in general terms, structurally the same event class
  as an injector solenoid turn-off on a shared harness (an inductive load
  on the same supply/return network being suddenly interrupted). **This is
  an inference about applicability, not a confirmed statement from the
  standard that injector turn-off is pulse 2a's origin** — no source found
  states that explicitly for this project's harness.
- Pulses 3a/3b are described (snippet level) as driven by "distributed
  capacitance and inductance of the wiring harness" during switching
  processes — again structurally relevant to a fast clamped turn-off edge
  propagating down a wire that runs the length of the engine, but not
  confirmed against the standard text.
- `emi_filter.cir`'s own RESULT NOTE already establishes this project's
  relevant framing: it models **differential-mode conducted emissions only**
  (150 kHz–108 MHz, CISPR 25 Class 5, 18 dBµV average in the FM band per
  research memo 06), and explicitly defers common-mode analysis (which a
  fast dV/dt edge referenced to chassis would excite more than a
  differential edge) as "a specification, not a simulated result, until
  there is a layout to model it against."

**What transfers, stated as INFERRED, not sourced:** a clamped turn-off at
100 V in 36 µs is a dV/dt of roughly 100 V / 36 µs ≈ **2.8 V/µs** — two
orders of magnitude gentler than the buck stage's ~400 kHz switching edges
that `emi_filter.cir` already exists to filter (a 400 kHz square edge with
even a few-hundred-ns risetime is tens to hundreds of V/µs). This suggests
the turn-off edge is **unlikely to be the dominant conducted-emissions
contributor** compared to the buck converter already being filtered, but
this is a first-order comparison, not a simulated result, and it says
nothing about the common-mode / radiated-emissions picture, which
`emi_filter.cir` itself has not modelled for any source yet. **This is the
one open item from this section worth carrying into the eventual SPICE
block**: once a turn-off netlist exists, its edge should be checked against
`emi_filter.cir`'s existing differential-mode model rather than assumed
benign.

---

## What transfers to this design

1. **Topology choice is a solved, four-way-classified problem** (Nexperia
   AN50003), not something to invent from first principles. Free-wheel is
   cheapest and slowest; avalanche and active-clamp are similar in speed and
   loss to each other but active-clamp carries a documented long-term
   reliability caution this project should not casually inherit; boost/
   recovery is the most complex and highest nominal component cost but the
   best net efficiency *and* is the one option with genuine diesel-injector
   production precedent (Marelli, 1988).
2. **The clamp-voltage-vs-speed trade-off is a straightforward L/V relation**
   that this memo's own arithmetic cross-checks cleanly against Nexperia's
   published numbers — no separate injector-specific figure was found or is
   needed to use the relation correctly.
3. **Recirculation to the boost rail is not a marginal optimization for this
   specific design** — the ~6.9 V recovered bump is the same order of
   magnitude as the ~7.3 V droop `boost_converter.cir` already treats as the
   central sizing question for that block. Building the turn-off circuit
   without considering recovery would leave that block's charge balance
   silently wrong once turn-off events are added to the picture.
4. **32.4 mJ/event is a real thermal design constraint for any dissipative
   clamp part**, even though the *average* power (3.6 W worst case) is
   modest — it is the peak/instantaneous stress during each 30–50 µs clamp
   event that matters, and no source in this pass identifies an
   avalanche-rated or Zener-clamp part characterized anywhere near this
   energy class per event. This is an argument in favor of recovery
   (minimizing energy actually dissipated in a switch/clamp device) rather
   than a solved problem to defer.
5. **The turn-off edge should be checked against, not assumed clear of,**
   the existing `emi_filter.cir` differential-mode model, and eventually
   against a common-mode model neither this memo nor that block has built.

---

## Recommendation: the circuit to build

**Topology:** Low-side switch (per injector channel, matching the existing
bank-shared high-side / independent low-side wiring memo 04 already
verified) with a **recirculation diode from the injector's low side back
into the 100 V boost rail capacitor** — the "boost converter" / energy-
recovery variant from AN50003 §4.4, adapted from its PWM-ripple-recovery
role (used there during the Peak/Hold chop) to also handle full End-of-
Injection turn-off, which is the diesel-electro-injector-specific
architecture the Marelli 1988 patent describes in general terms. This is
**not** a Zener-across-the-FET active clamp (ruled out per §1.1's
reliability finding) and **not** a bare freewheel-to-battery diode (too
slow relative to the boost rail already built for the opposite reason on
turn-on).

**Clamp voltage:** the existing **100 V boost rail itself** — no separate,
higher clamp voltage is recommended. This keeps the clamp element's voltage
rating aligned with parts already being selected for the boost stage,
avoids introducing a fifth voltage domain, and gives a computed ~36 µs
turn-off (§2.2), comfortably fast against the 1–3 ms injection window. A
higher dedicated clamp (§2.2's 150 V illustrative row) would turn off
faster still, but nothing in this pass's sourcing justifies paying for a
second high-voltage rail when the existing one is already close to the
useful range AN50003's own avalanche example (68 V) demonstrates.

**Part class:** a diode (ultrafast recovery, rated for boost-rail voltage
and the 18 A peak current, matching the class TLE8242-2's own datasheet
calls out generically — "recirculation diode (ultrafast)" — even though
that IC itself is the wrong current/voltage class for this injector) in
series with the existing low-side switch topology; no new active clamp
IC is recommended. Should the boost rail's regulator (`Bchga` in
`boost_converter.cir`) need to shed recovered energy that pushes it above
100 V on back-to-back events, that is a boost-converter-block problem to
solve in that block's next revision, not a reason to add a second
dissipative clamp path here.

**Specific claims the next SPICE block should check:**
1. Turn-off time from 18 A to ~0 A when clamped to a 100 V rail: expect
   **~36 µs** (physics-derived, §2.2) — if the simulated result is far off
   this, the model's assumptions (diode drop, rail sag under load) need
   re-examination before trusting it.
2. Boost-rail voltage excursion from one full-energy recovery event on the
   existing 47 µF/100 V reservoir: expect **~+6.9 V** (§3) — compare against
   `boost_converter.cir`'s own ~7.3 V peak-phase droop to see whether
   recovery approximately cancels it, overshoots it, or undershoots it once
   diode/switch losses are included (this memo's number ignores those
   losses; AN50003's own data suggests recovery topologies still have real,
   non-zero losses even though net efficiency is favorable).
3. Whether recovered energy pushes the rail above the 100 V setpoint on
   back-to-back pilot+main+post events at the 26.67 ms per-cylinder spacing,
   and whether the existing `Bchga` charge-regulation logic needs a bleed
   path.
4. The clamp diode's peak instantaneous power/junction stress during the
   ~36 µs turn-off pulse, not just the ~3.6 W time-averaged figure (§4) —
   the average number is not the one that will size the part.
5. The turn-off edge's differential-mode contribution against
   `emi_filter.cir`'s existing model (§5) — first-order comparison here
   suggests it is gentler than the buck stage's edges, but this should be
   checked, not assumed.

---

## Negative results, recorded

- **ST L9781 datasheet** — not retrieved. Two fetch attempts (st.com direct
  PDF, alldatasheet mirror) failed: one timed out (60 s), one returned HTTP
  403. Everything attributed to it in this memo is explicitly marked
  SNIPPET and should not be used as a design number without retrieving the
  document.
- **NXP AN4849** ("Four Injector and Fuel Pump Drive Featuring the
  MC33816") — the PDF URL found via search (nxp.com/docs/en/application-
  note/AN4849.pdf) returned **HTTP 404**. Not retrieved. Search-result
  summaries describing its "boosting"/"holding" high-side driver pairing
  per bank are recorded in this memo's working notes but were not used as
  a cited finding above, since the document itself was never seen.
- **Bosch EDC17/EDC7 injector-driver ASIC architecture** — no public
  technical/circuit-level source found at all (see §1.4). This is a
  negative result about public availability, not evidence that Bosch's
  internal architecture differs from what's described here.
- **ISO 7637-2:2011 standard text** — one direct-PDF fetch attempt
  returned **HTTP 401**. Not retrieved. §5's discussion of pulses 2a/3a/3b
  is search-snippet level throughout and is flagged as such at each claim.
- **A quantitative die-temperature-rise-per-clamp-voltage figure** (task
  item 2's request for "actual numbers real drivers use," beyond the single
  68 V generic-automotive avalanche example found) — not found. No
  injector-specific clamp-voltage number (as opposed to a generic solenoid
  or a 15–20×-battery gasoline-DI figure) was retrieved from any source in
  this pass. The 100 V recommendation in this memo's §"Recommendation" is
  a design choice justified by matching the existing boost rail, not a
  sourced industry-standard clamp voltage for this injector class.
- **A confirmed injection strategy (pilot/main/post count) for this
  specific engine/calibration** — not found; memo 04 does not establish
  this either. §4's "3 events per cylinder per cycle" is stated as an
  assumption, not a sourced fact.
- **TI DRV8701 relevance** — checked and explicitly ruled out (§1.5), not
  silently dropped, since the task named it as a candidate to check.
