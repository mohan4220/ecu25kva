# Research Memo 12: Driver Architecture — Integrated IC vs Discrete FETs, and the Coupled Gate-Kill Question

**Task:** Two schematic sheets (injector driver, metering-unit driver) are blocked on one
decision each, and the two decisions are coupled: **integrated injector-driver IC vs
discrete FETs with custom gate drive**, and **passive gate pulldown vs active clamp**
for holding every driver gate off during reset/brownout (spec §4's "Every driver gate is
held off by hardware" requirement; status.md §6). This memo answers both, together,
because `supervisor.cir`'s claim 3/claim 6 result and the spec's own correction already
established that the second question cannot be closed without the first.
**Date:** 2026-09-19
**Scope:** Read-only research. No repo files modified except this one, nothing
committed, no subagents dispatched.

---

## Verdict (read this first)

**Discrete FETs with a custom pre-driver/gate-drive stage, keeping the already-simulated
100 V boost rail, for the injector banks (pins 03/05, 73/07/29). An integrated smart
low-side switch (already memo 07's direction) for the metering unit (pin 88). An active
kill-clamp at every gate — not a passive pulldown alone — built discretely, exactly as
`supervisor.cir` already validated it, for both output classes.**

The two purpose-built integrated injector-driver ICs close enough to fit this design's
channel count and current class — **NXP MC33816** and **ST L9781** — both cap their
boost-rail voltage **below** the 100 V this project already chose and already built three
passing simulation blocks around: MC33816's `VBOOST` absolute maximum is **72 V**
(CONFIRMED, NXP datasheet Rev 10.0), L9781's `VTank` is reported at **up to 80 V**
(SNIPPET only — its datasheet could not be retrieved in two independent sourcing passes,
this one and memo 10's). Neither integrated part eliminates the external power MOSFETs,
the external boost inductor/diode, or the external current-sense shunt — both are
**pre-drivers**, not integrated power stages, so choosing either does not remove the
discrete-FET selection and thermal-design work this decision is nominally about; it only
relocates the gate-drive sequencing, current-comparator logic, and (for MC33816
specifically) a real microcode toolchain into a part. **MC33814** and (per memo 10,
not re-derived here) **TLE8242-2** are confirmed wrong current/voltage class outright —
MC33814's injector output is rated 1.3 A continuous against an 18 A/8-13 A requirement,
and it has no boost stage at all (CONFIRMED, NXP/Freescale datasheet Rev 5.0).

**On the coupled question:** the integrated route does not remove the passive-vs-active
problem — it relocates it, in a form worth copying. MC33816's own datasheet states
(§6.3.4, CONFIRMED) that its high-side pre-driver output is **actively forced low** —
not merely released to a resistor — whenever reset is asserted or `DrvEn` is low, so long
as the driver's bootstrap capacitor still holds charge above 1.1 V; only when that
bootstrap charge is exhausted does it fall back to a genuinely weak 500 kΩ–2 MΩ
gate-source resistor (CONFIRMED, Table 31). That is the same two-tier structure this
project's own `supervisor.cir` already built and validated for a discrete design: an
active kill path that dominates (claim 1, claim 4: tens of nanoseconds, wins against an
adversarial driver with margin) backed by a passive pulldown that is not, on its own,
strong enough against Miller coupling at this design's own edge rate (claim 3's FAIL,
claim 6's 470 Ω fix). **Buying the IC does not buy exemption from this problem; it buys
someone else's already-shipped version of the same fix**, on a rail voltage this project
did not choose.

---

## 1. What the design actually needs from a driver — established from the repo

Read from spec §2.1, §2.2, §4; `injector_boost.cir`; `injector_turnoff.cir`;
`boost_converter.cir`; `metering_unit_pwm.cir`; memo 04; memo 07. CONFIRMED (repo's own
simulation results and spec text, not re-derived):

| Requirement | Value | Source |
|---|---|---|
| Injector bank high sides | 2 channels (pins 03, 05), bank-shared | spec §2.1, memo 04 §3 |
| Injector low-side selects | 3 channels (73, 07, 29), independent, current-controlled peak-and-hold | spec §2.1 |
| Injector peak current | ~18 A from the boost rail | `injector_boost.cir`, memo 04 envelope 12–24 A |
| Injector hold current | 8–13 A family envelope, ~10 A used in sim | `boost_converter.cir`, memo 04 |
| Boost rail voltage | **100 V**, chosen mid-envelope (memo 04: 65–115 V) and matched to memo 10's turn-off clamp recommendation | `boost_converter.cir`, `injector_turnoff.cir` |
| Turn-off topology | Recirculation into the same 100 V/47 µF boost reservoir, not freewheel-to-battery, not Zener active clamp | memo 10 (settled, not reopened here) |
| Metering unit | 1 low-side PWM channel, current sense, battery-fed through fuse `8F1`, ~0.6–1.35 A class current, no boost, no bank-sharing | spec §2.2, `metering_unit_pwm.cir` |
| EGR | H-bridge, pins 59/81, not yet designed | status.md §2 — explicitly out of this decision's scope; none of the candidates evaluated below are H-bridge parts |
| Fail-safe | Every driver gate (88, 73/07/29, 03/05) held off by hardware during reset/brownout, independent of GPIO state | spec §4, memo 11, `supervisor.cir` |

**The number that actually decides this memo is the 100 V boost rail**, not the 18 A
peak current — every candidate below has enough current-handling margin once external
FETs are sized for it (the ICs are pre-drivers; the FETs carry the current, not the
silicon). Voltage is where the candidates actually fail.

---

## 2. Candidate ICs, evaluated against these numbers

### 2.1 NXP MC33816 — **CONFIRMED**, full datasheet retrieved and read directly (NXP, "SD6 programmable solenoid controller," Rev 10.0, 2/2023, `nxp.com/docs/en/data-sheet/MC33816.pdf`)

**Architecture, read from the block diagram and pin table (p.5–8):** a **pre-driver
only**. Five external high-side MOSFET gate drivers (with integrated bootstrap and
charge pump per channel) and seven external low-side MOSFET gate drivers (one dedicated
to a boost-converter switch), four independent current-measurement comparator/ADC
blocks, and four digital microcores running encrypted, user-written microcode (two
1024×16 code RAM banks, two 64×16 data RAM banks) that sequence the pre-drivers and
implement the peak-and-hold control law using the current-measurement blocks as
feedback. **It does not integrate the power FETs, the boost inductor, the boost diode,
or the current-sense shunt** — all of that remains external and identical in kind to
what a discrete design would need.

**Voltage — the disqualifying number, CONFIRMED (Table 3, Maximum Ratings, p.9):**

| Parameter | Value |
|---|---|
| `VBOOSTMAX` (steady-state and unpowered) | **0–72 V** |
| `VBATT` absolute max | –0.3 to 72 V |
| `VBATT` normal operating (internal VCCP reg.) | 9–16 V typ, up to 36 V (broken-alternator, ≤1 h), up to 48 V (jump start, external VCCP) |

**This is an absolute maximum rating, not a recommendation.** This project's boost rail
is already built, simulated, and passing at **100 V** (`boost_converter.cir`,
`injector_turnoff.cir`). Running MC33816's `VBOOST` pin at 100 V would exceed its
absolute maximum by 28 V — real risk of permanent device damage, not a derating
question. This is independently corroborated at SNIPPET level by hobbyist common-rail
ECU builders working with this exact part: *"The MC33816 only boosts to 72V, and the
[MC33816]/PT2000 can't drive high side transistors over 72v"* (rusefi.com forum,
`www.rusefi.com/forum/viewtopic.php?p=28212`, community project notes — not a
datasheet, cited only because it independently confirms the same number this memo
already read from the datasheet's own table).

**Current:** channel count and current-measurement architecture are not the limiting
factor — 5 HS + 7 LS pre-driver outputs comfortably cover 2 banks + 3 selects + 1 boost
switch, with two channels to spare. The actual current the design draws is set by the
external FETs and the current-sense shunt, which this IC does not supply.

**Peak-and-hold "in hardware":** partially true, and the qualification matters. The
current-measurement comparators and PWM gate outputs are hardware; the sequencing,
thresholds, and boost/peak/hold state machine are **user-written microcode** running on
the part's own microcores, protected by encryption and loaded via SPI (p.14–16,
CONFIRMED). This is a real toolchain and a real skill the spec's own §5 already flagged
as a hiring risk in a different context (rejecting the MPC5744P's eTPU2 microcode for
exactly this reason: *"No eTPU2 microcode, which is a specialist skill and a hiring risk
on a small team"*). The same argument applies here, on a different part.

**Power-on-reset / fail-safe behaviour — CONFIRMED, §6.3.4 and §6.4.1, and this is the
part of the datasheet most directly relevant to spec §4's requirement:**

> *"In order to guarantee a safe condition while the device is not operating, the G_HSX
> output is immediately forced to the low level, switching the external MOSFET off when
> reset (RSTB) is asserted, or DrvEn is low. This behavior is effective as long as the
> bootstrap capacitor voltage is greater than a typical voltage of 1.1 V. When the
> bootstrap capacitor voltage is lower than or equal to 1.1 V, the pre-driver output
> state is undefined, but the pre-driver is not in a high state. In addition, an
> integrated pull-down resistor R_PD_HSX between G_HSX and S_HSX keeps the external
> MOSFET in an OFF state."*

Table 31 gives `R_PD_HSX` = **500 kΩ min, 2000 kΩ (2 MΩ) max** — this is the fallback
path, and it is markedly weaker than the 470 Ω this project's own `supervisor.cir` claim
6 found necessary against Miller coupling at this design's own edge rate. The low-side
pre-driver description (§6.4.1, CONFIRMED) states the identical structure: *"a gate to
source pull-down resistor R_PD_LSX holds the external MOSFETs in the off state, while
the device is in a power on reset state (RSTB low)"*, with the truth table (Table 38,
footnote 48) confirming the driver **actively** drives the gate low (not just releases
it to the resistor) whenever `lsx_command` is commanded low — including the off/reset
condition, as long as the digital core and `VCCP` supply are alive. The numeric off-state
drive impedance for the low-side output specifically was not located in the pages read
this session (the high-side equivalent, Table 33, gives 5.9–138 Ω across slew-rate
settings) — **INFERRED by architectural symmetry with Figure 13/16's matching push-pull
output structure, not itself read from a table**, that the low-side off-state impedance
is in the same class.

**What this means, stated plainly:** MC33816 does not remove the exposure spec §4 and
memo 11 identified — it has the **same** two-tier structure (active clamp dominant,
weak resistor as last resort when the local bias rail is gone) this project's own
supervisor block already designed and proved. The corner case that breaks the resistor
alone in this project's own design (a fully depleted local bias) is analogous to the
corner case that breaks MC33816's own resistor alone (a fully depleted bootstrap cap).
Buying the part buys a working instance of this structure already built and
characterized by NXP; it does not buy a different, exemption-granting mechanism.

**Sourcing — CONFIRMED, reused from memo 07, not re-fetched this session:** MC33816AE,
DigiKey India, 868 units in stock, ₹1,040.54 qty 1 / ₹693.12 qty 100
(`digikey.in/en/products/detail/nxp-usa-inc/MC33816AE/4693868`). **Flagged and still
unresolved:** the live page shows a "Last Time Buy Date: 06/08/2027" field that memo 07
could not reconcile against NXP's own Product Longevity Program listing. This memo does
not resolve it either — it is restated here because it bears directly on whether
MC33816 is even a live option, not just on its cost.

### 2.2 NXP MC33814 — **CONFIRMED**, full datasheet retrieved and read directly (Freescale/NXP, "Two Cylinder Small Engine Control IC," Rev 5.0, 6/2013, mirrored at `datasheet.octopart.com/MC33814AER2-NXP-Semiconductors-datasheet-32860591.pdf`)

**Wrong current and voltage class outright, confirmed from the datasheet's own Maximum
Ratings table (Table 3, p.8), not inferred from its marketing copy:**

| Parameter | Value | Against this design's requirement |
|---|---|---|
| `VPWR` supply voltage, absolute max | –0.3 to **45 V** | No margin for a 100 V boost rail — and there is no boost rail at all in this part's architecture |
| Injector driver output continuous current (`IOC_INJX`) | **1.3 A** max | **~14× under** this design's 18 A peak requirement |

MC33814's own application diagram (p.1) drives injectors **directly off `VPWR`**, with
no boost stage anywhere in the part — consistent with its stated market (lawn mowers,
motor scooters, small motorcycles, snow blowers, chain saws, outboard motors,
gasoline-driven generators, per its own datasheet's Applications list) being low-pressure
port injection or carbureted-class solenoids, not common-rail diesel. This is the same
shape of mismatch memo 10 already found for TLE8242-2 (a variable-force-solenoid
pre-driver rated for 0–1.2 A / 50 V, an order of magnitude below this injector), not
repeated here per the task's own instruction, and confirmed independently for a second
part rather than assumed to generalize. **MC33814 does not fit and should not be
considered further for the injector banks.**

### 2.3 Infineon TLE8242-2 — **not re-evaluated, per instruction.** Memo 10 §1.2 already
found this is a variable-force-solenoid pre-driver (0–1.2 A, 50 V absolute max), an
order of magnitude below this injector's current/voltage class. That finding stands and
is not repeated here.

### 2.4 ST L9781 (and L9782) — **SNIPPET only, not retrieved in full.** Consistent
negative result across two independent sourcing passes.

Two direct-fetch attempts this session — `st.com/resource/en/data_brief/l9781.pdf` and
an `alldatasheet.com` mirror — both failed (60-second timeout on the ST data brief;
HTTP 403 on the alldatasheet page). A third attempt at the full datasheet
(`st.com/resource/en/datasheet/l9781.pdf`) also timed out. This matches memo 10's own
negative result for the same part (§1.2: *"Two direct fetch attempts (st.com PDF,
alldatasheet mirror) both failed"*) — **the same document has now failed retrieval on
two separate research passes**, which is itself a data point about how usable this part
is for a small team without a distributor account or an ST FAE relationship.

**What search-result snippets state (unverified against the document itself, SNIPPET
level only, not elevated further this session):**
- Drives **11 external N-channel logic-level MOSFETs**, controlling up to **5 inductive
  loads** through peak-and-hold current control plus one DC/DC step-up converter
  (ST data brief, indexed search summary).
- The DC/DC converter's `VTank` output is reported as **"up to 80 V"** — like MC33816,
  this is **below** this design's chosen 100 V boost rail, and by a wider margin.
- Peak/hold sequencing is handled by **internal configurable Finite State Machines
  (FSMs)**, described as needing only start-of-actuation commands from the host MCU —
  if accurate, this is architecturally **simpler and less of a toolchain commitment**
  than MC33816's user-programmed microcode, because an FSM configured by registers is
  not the same engineering surface as a part with its own encrypted instruction set.
  **This is exactly the kind of claim this project's own discipline says should not be
  designed against without the datasheet**, so it is recorded as a reason to keep
  pursuing the document, not as a basis for a decision.
- Orderable: DigiKey lists **L9781** at **US$10.92** (cut tape, MOQ 1), 64-pin package,
  found via search index (`digikey.com/en/products/detail/stmicroelectronics/L9781/...`)
  — **SNIPPET**, the live page itself returned HTTP 403 to this session's fetch, the
  same bot-mitigation behaviour memo 07 already reported for Mouser/DigiKey chip pages
  in general.

**No power-on-reset behaviour, no absolute maximum ratings table, and no per-channel
current rating for L9781 could be confirmed this session.** It cannot be recommended as
a primary path on SNIPPET-level numbers — not because the part looks unsuitable
(the reported architecture is a closer conceptual match to this design than MC33816's
microcode approach), but because this project's own sourcing discipline (stated in the
task, and already the subject of two "caught only after they became requirements"
failures) rules out designing a schematic sheet around numbers nobody has actually read.

### Summary table

| Candidate | Channels | Voltage vs 100 V rail | Current vs 18 A/8-13 A | Peak-hold | External FETs needed | POR/fail-safe | Fit |
|---|---|---|---|---|---|---|---|
| MC33816 | 5 HS + 7 LS | **72 V abs max — under, CONFIRMED** | Set by external FETs, no IC limit | Hardware comparators + user microcode | Yes, always | Active-forced-low, backed by weak 500 kΩ–2 MΩ resistor when bootstrap depleted | **Voltage mismatch; everything else fits** |
| MC33814 | 2 injector + misc | 45 V abs max, no boost stage | **1.3 A max — 14× under, CONFIRMED** | N/A — no boost/peak-hold architecture | Integrated (wrong class) | Not evaluated — moot | **Does not fit at all** |
| TLE8242-2 | — | 50 V abs max (memo 10) | 0–1.2 A (memo 10) | — | Yes | — | **Does not fit at all (memo 10)** |
| L9781/2 | 11 gate outputs / 5 loads | **~80 V reported — under, SNIPPET** | Set by external FETs, no IC limit reported | FSM-based, less toolchain than MC33816 (SNIPPET) | Yes, always | Not confirmed | **Voltage mismatch (if the snippet holds); unconfirmed otherwise** |

---

## 3. What the integrated route actually saves — Q2

Reading MC33816's own architecture against this design's needs, what moves into the
part and what does not:

**Moves into the part, CONFIRMED:**
- Gate-drive timing and slew-rate control for the power FETs (four selectable slew
  rates, bootstrap/charge-pump management) — this is real engineering the discrete route
  has to build (a gate-driver IC or discrete driver stage, still needed either way, but
  the sequencing-across-channels logic is a bespoke firmware/FPGA job in the discrete
  case).
- Current-sense comparison against programmable thresholds — the analog front end for
  closed-loop peak/hold, which a discrete design would otherwise build from an
  op-amp/comparator plus MCU ADC/comparator peripherals.
- VDS monitoring and open/short diagnostics per channel (five HS + six LS, independently)
  — a genuinely useful diagnostic capability neither `injector_boost.cir` nor
  `injector_turnoff.cir` currently model or require, but real value if the design wants
  it.
- Part of spec §4's fail-safe requirement — the active-forced-low behaviour at RSTB/DrvEn
  (§2.1 above) — **but only conditionally**, and with the same bootstrap-dependent
  fallback this project's own discrete kill-FET design already had to solve for a
  different bias rail.

**Does not move into the part, confirmed by the same datasheet:**
- The power MOSFETs themselves (all five HS and seven LS pre-driver outputs are
  external-gate-only).
- The boost converter's inductor, diode, switching FET (only the switching FET's *gate*
  is driven by the IC; the power components are external, same as
  `boost_converter.cir`'s model).
- The current-sense shunt resistor.
- The turn-off recirculation topology memo 10 and `injector_turnoff.cir` already chose
  and validated — this is a board-level wiring decision the pre-driver is agnostic to,
  regardless of which pre-driver IC (or discrete gate driver) drives the FETs.
- The peak-and-hold **control law's own numeric thresholds and timing** — those are
  written as microcode (MC33816) or firmware (discrete), either way a real design
  artifact this project has not yet written for either route.

**Net assessment:** the integrated route buys a pre-built gate-drive/diagnostics/
current-comparator front end and a partial answer to the fail-safe requirement, in
exchange for a hard voltage ceiling below this project's chosen rail and a real
microcode toolchain commitment. It does not touch the power stage, the boost stage, or
the turn-off topology, all of which are unaffected by this decision either way.

---

## 4. What it costs — Q3

| Factor | MC33816 | Discrete |
|---|---|---|
| India availability | CONFIRMED in stock at DigiKey India (memo 07), but with an unresolved EOL-date flag | Broadly available — automotive gate-driver ICs and power MOSFETs in this voltage/current class are mainstream-distributor stock (memo 07's own aggregate-estimate lines for comparable parts) |
| Price | ₹1,040.54 qty 1 / ₹693.12 qty 100 (CONFIRMED, memo 07) | Estimated ~₹800 aggregate for the whole discrete boost/driver stage (memo 07 line 14b, **I**-class estimate, not yet itemized) — comparable order of magnitude, not a clear win either way |
| Package/thermal | 64-pin LQFP-EP, R_θJA 24.3–29.7 °C/W (CONFIRMED, Table 4) — the IC itself dissipates little; the external FETs carry the thermal load in both routes | Same external-FET thermal burden, plus a separate gate-driver package (typically SOIC/SOT, lower pin count, simpler layout) |
| Toolchain | **A real one.** Encrypted microcode, two microcores, SPI-loaded configuration, a 93-instruction ISA (datasheet TOC runs to p.312) — this is not a footnote, it is a second embedded-systems skill set beyond the S32K148 firmware this project is already building | None beyond the firmware current-loop this project would write regardless, using peripherals (FlexTimer, dual ADC, PDB) spec §5 already justified as adequate headroom |
| End-of-life exposure | **Real and specific.** A single NXP part, single product line, with an unresolved "Last Time Buy Date" flag (memo 07 §3.2) — if genuine EOL, the injector driver sheet would need a second redesign, not a substitution, because the microcode and the pin-out are both part-specific | A discrete stage is rebuildable around a different FET/gate-driver family without redesigning the current-control architecture, because the control law lives in this project's own firmware, not in a vendor's encrypted microcode |
| Rail-voltage cost, if adopted | **Forces the boost rail down from 100 V to ≤72 V** — re-derives three already-passing simulation blocks (`boost_converter.cir`, `injector_turnoff.cir`, and this file's own claim inputs) and measurably erodes pilot-injection turn-on margin (§5 below) | None — the existing 100 V rail and its three passing sim blocks are unaffected |

---

## 5. Re-derived arithmetic: what a 72 V or 80 V rail actually costs, if MC33816 or L9781 were adopted

**Turn-on ramp time**, using the exact RL step-response formula `injector_boost.cir`'s
own RESULT NOTE cites: `t = (L/R)·ln(V/(V − I_th·R))`, with this project's own L = 200 µH,
R = 0.5 Ω, I_th = 18 A (re-derived here, not assumed):

| Boost voltage | t (turn-on to 18 A) | vs 100 µs minimum pilot pulse (memo 04) |
|---|---|---|
| 100 V (as built) | L/R·ln(100/91) = 400 µs × 0.0943 = **37.7 µs** (matches `injector_boost.cir`'s simulated 38 µs) | consumes **37.7 %** of the shortest pilot pulse |
| 80 V (L9781's reported ceiling) | 400 µs × ln(80/71) = 400 µs × 0.1194 = **47.8 µs** | consumes **47.8 %** |
| 72 V (MC33816's confirmed ceiling) | 400 µs × ln(72/63) = 400 µs × 0.1335 = **53.4 µs** | consumes **53.4 %** |

**Turn-off clamp time**, using memo 10's own relation `Δt = L·ΔI/V_clamp` (re-derived,
not assumed):

| Clamp voltage | Δt (18 A → 0) |
|---|---|
| 100 V (as built, `injector_turnoff.cir` measured ~34 µs) | 200 µH×18/100 = **36 µs** (hand figure; sim measured 34 µs, memo 10 §2.2) |
| 80 V | 200 µH×18/80 = **45 µs** |
| 72 V | 200 µH×18/72 = **50 µs** |

**Reading this plainly:** none of these numbers are disqualifying on their own — even at
72 V, 53.4 µs is still comfortably inside a 100–300 µs minimum pulse and vastly inside a
1–3 ms main injection. But the margin **more than doubles its consumption of the
shortest pilot pulse** (37.7 % → 53.4 %) at the exact operating point (short pilot
injections, the class memo 04 flagged as "a hard requirement, not headroom" for this
engine's CPCB IV+ calibration) where turn-on dead time matters most. This is a real,
quantified cost of adopting either integrated part — not a hand-wave "it's probably
fine" — and it stacks on top of re-deriving `boost_converter.cir`'s droop/recovery
numbers and `injector_turnoff.cir`'s recirculation-bump numbers, both of which are
computed at the 100 V rail those two blocks currently pass at.

---

## 6. The coupled question, answered directly — Q4

**Does an integrated driver remove the passive/active clamp problem, or relocate it?**
**Relocate it.** MC33816's own confirmed behaviour (§2.1 above) is structurally
identical to what this project's own `supervisor.cir` already built for a discrete
design: an active, low-impedance forced-off path that dominates whenever the relevant
local supply (MC33816's bootstrap cap; this design's kill-FET drive, sourced
independently from `3V3_MCU`/supervisor logic) is alive, backed by a passive resistor
that is, on its own, weak relative to this design's own established Miller-coupling
requirement (470 Ω at Crss = 500 pF, claim 6) — MC33816's fallback resistor is
500 kΩ–2 MΩ, three to four orders of magnitude weaker again. **The IC does not grant
exemption from the physics `supervisor.cir` claim 3 found; it ships a version of the
same fix, on a rail voltage this project did not choose, with a corner case (bootstrap
depletion) this project has no visibility into or control over.**

**Does a discrete design with a proper active clamp beat both?** For this project's
specific fail-safe requirement, **yes, and this project has already built and verified
it**: `supervisor.cir` claim 4 proves the discrete kill path (an active kill FET, backed
by a properly-sized passive pulldown per claim 6) beats the S32K148's own 2.97 V
correctness-guarantee floor with margins from 18 µs (fastest brownout ramp modelled) up
to 61 ms (slowest), **using a kill-drive path this project chose to be independent of
the boost rail's own state** — the adversarial-driver stimulus in claims 1b/4 is
explicitly modelled as running off a rail separate from the one that's failing, per
memo 11's own "Phase-2 detail" note. MC33816's equivalent mechanism is tied to its own
bootstrap capacitor, which is charged from `VBOOST`/`VBATT` — the same rails this
design's brownout scenario is about. **No source in this pass (NXP's datasheet included)
makes a timed claim about how fast MC33816's own bootstrap cap decays relative to a
brownout event**, the way this project's `supervisor.cir` makes a timed claim about its
own kill path relative to the 150 µF `mcu_pdn.cir` bulk-cap decay. That is a real,
specific advantage of building the active clamp discretely, on a bias this project
controls, rather than trusting a bootstrap cap of unstated decay behaviour under exactly
the fault condition being protected against.

**Answer to the coupled question, stated once, plainly:** neither integrated candidate
removes the need for an active clamp — both already use one, internally, for the same
reason `supervisor.cir` does. **Build the active clamp discretely, as already designed
and validated** (kill FET, Ron-class ≤5 Ω model, backed by an Rgs pulldown sized per
claim 6's `Rpd < Vgs(th)/(Crss·dV/dt)` relation once a real FET is chosen), for every
gate this decision touches — pins 88, 73/07/29, 03/05 — regardless of which driver
architecture wins for the power stage. This part of spec §4's requirement does not
change with this decision; it was never actually in question.

---

## 7. Does the answer differ between injectors and the metering unit? — Q5

**Yes, and the split is real, not a hedge.**

**Injectors (03/05, 73/07/29):** the requirement is peak-and-hold at 18 A from a shared
100 V boost rail across five channels with bank-sharing logic — the class of problem
MC33816 and L9781 exist for. The recommendation above (discrete, keep the 100 V rail) is
driven by the voltage mismatch, not by the current or channel count, which both
candidates handle comfortably via external FETs.

**Metering unit (88):** a single low-side PWM channel, ~0.6–1.35 A, no boost, no
bank-sharing, current sense against a rail-pressure control loop
(`metering_unit_pwm.cir`). **None of the four evaluated candidates are a sensible fit
for this channel at all** — MC33816 and L9781 are five-to-eleven-channel high-voltage
peak-and-hold parts, absurdly over-specified for one low-current low-side switch; MC33814
and TLE8242-2 are wrong-class outright per §2.2 and memo 10. Memo 07 already recommends
the correct class for this channel — **an integrated automotive smart low-side switch**
(BTS443P-class, memo 07 line 13), which is itself an "integrated driver," just in a
completely different, better-matched product category (single-channel, current-sensing,
typically with its own thermal/short-circuit shutdown), not one of the four candidates
this task named. This memo does not re-evaluate that choice — it is not in question here
— but it confirms the same fail-safe gate-kill requirement (spec §4, `supervisor.cir`)
still has to be built at pin 88's gate node regardless of which smart low-side switch is
chosen, because a generic smart low-side switch's own internal safe-state behaviour on
power loss should not be assumed, without checking that specific part's datasheet, to
satisfy this project's own 2.97–3.10 V reset-band requirement (memo 11 §3). **That check
is a Phase-2 item for whichever BTS443P-class part memo 07's Phase-2 sourcing pass
selects, not resolved here.**

---

## What transfers to this design

1. **The injector driver sheet is drawn discrete**, keeping the 100 V boost rail exactly
   as `boost_converter.cir` and `injector_turnoff.cir` already built and passed. Neither
   MC33816 nor L9781 removes enough engineering work to justify re-deriving those two
   blocks and eroding pilot-injection turn-on margin by roughly 16 percentage points
   (§5's 37.7 %→53.4 % figure).
2. **The current-regulation loop for peak-and-hold is firmware, using the ADC/FlexTimer/
   PDB headroom spec §5 already justified** (2× 12-bit ADC against ~14 channels of
   demand, FlexTimer well beyond the ~10 timing channels needed, 2× PDB for jitter
   isolation) — this project already argued it does not need a dedicated timing
   co-processor for injection scheduling; the same argument extends to not needing a
   dedicated current-regulation ASIC for the same reason (fixed 1500 rpm, no eTPU2-class
   real-time pressure).
3. **The active-clamp requirement is unchanged by this decision** — it was never a
   question this decision could resolve differently. `supervisor.cir`'s kill-FET +
   sized-Rgs structure (§6 above) is what gets drawn, at every one of pins 88, 73/07/29,
   03/05, regardless of which power-stage architecture was chosen.
4. **The metering unit stays on memo 07's existing track** (smart low-side switch), with
   one new Phase-2 checkbox: confirm that specific part's own datasheet against the
   2.97–3.10 V reset-band requirement before assuming its internal safe-state behaviour
   covers what `supervisor.cir` was built to guarantee.
5. **MC33816's "Last Time Buy Date" ambiguity (memo 07 §3.2) is now doubly relevant** —
   it was already a BOM risk; it is now also the fallback path's own risk if this
   decision is ever revisited under the "what would change your mind" conditions below.
6. **L9781/L9782 remain undesigned-against.** Two independent sourcing passes (memo 10,
   this memo) have both failed to retrieve its datasheet. It should not appear in a BOM
   or a schematic net until someone actually reads it.

---

## Recommendation: the circuit to build

**Injector driver sheet (pins 03, 05, 73, 07, 29):** discrete N-channel power MOSFETs
(two high-side bank switches, three low-side selects), rated with margin above 100 V and
18 A peak — exact part TBD, gated on U5 (injector part number) the same way memo 04 and
`boost_converter.cir` already flag — driven by a conventional automotive high-side/
low-side gate-driver IC (general-purpose class, not an injector-specific part; broadly
sourced, e.g. the same class of part memo 07 line 12 already prices for the EGR
H-bridge). Current sense via a shunt per channel or per bank into the MCU's own ADC,
closed-loop peak-and-hold implemented in firmware using PDB-triggered sampling. Turn-off
recirculation exactly as memo 10 and `injector_turnoff.cir` already specify — this sheet
does not reopen that decision.

**At every one of pins 88, 73, 07, 29, 03, 05:** the kill-FET + sized-Rgs active clamp
from `supervisor.cir`'s Recommendation and claim 6 — an N-channel kill transistor from
gate to source, driven (through one inverting stage) by the supervisor's `RESET`, in
parallel with a standing Rgs pulldown sized per `Rpd < Vgs(th)/(Crss·dV/dt)` once the
actual FET is chosen (claim 6's own worked example: 470 Ω at Crss = 500 pF, this
design's 2.8 V/µs edge, Vgs(th) = 1.0 V — re-derive once a real part is picked, per
`supervisor.cir`'s own header caveat that this scales with 1/Crss).

**Metering-unit sheet (pin 88):** unchanged from memo 07's direction — an integrated
smart automotive low-side switch (BTS443P-class), plus the same kill-FET/pulldown at its
gate node, plus the Phase-2 datasheet check named in §7.

**Part class named for the injector power stage's gate-driver IC:** not a specific part
number — this is deliberately left as a Phase-2 sourcing item (the same status memo 04's
Step 4 already gave the discrete route: "all constituent parts... are broadly available
in small quantities from standard distributors"), because the point of this
recommendation is that no single-source, voltage-capped, microcode-dependent part is
needed to close this sheet.

**What would change this recommendation:**

1. **If U5 closes and shows this engine's injector actually wants a clamp/boost voltage
   at or below ~72 V** (the low end of memo 04's 65–115 V envelope, not the ~90–105 V
   midpoint this project chose), the MC33816 voltage mismatch disappears and its
   pre-built current-regulation/diagnostics stage becomes a straightforwardly good trade
   — revisit this memo's §2.1 and §5 arithmetic at the actual chosen voltage.
2. **If the firmware effort for a real-time peak-and-hold current loop turns out to be
   materially harder than spec §5's ADC/FlexTimer/PDB headroom argument assumed** —
   discovered only once firmware development starts — the calculus shifts toward
   MC33816 despite the rail-voltage cost, because buying a working current-loop
   implementation may be cheaper than debugging one under real injector loads.
3. **If MC33816's DigiKey "Last Time Buy Date" is confirmed as a genuine EOL notice**
   (memo 07 §3.2, still open), MC33816 is removed from consideration entirely, leaving
   only L9781/L9782 as an integrated fallback — which cannot be adopted until its
   datasheet is actually retrieved and read, not before.
4. **If a full L9781/L9782 datasheet is obtained** and shows either (a) a `VTank`
   capability compatible with a 90–100 V rail, or (b) an FSM-based control architecture
   confirmed to need materially less firmware/toolchain investment than MC33816's
   microcode, it should be re-evaluated as the primary integrated candidate rather than
   dismissed alongside MC33816.

**Specific, falsifiable claims a Phase-2 SPICE block should check**, once an actual FET
and gate-driver IC are chosen for the discrete route:

1. The chosen gate-driver IC's output impedance, combined with the claim-6-sized Rpd,
   should reproduce `supervisor.cir` claim 2's finding (turn-on edge slowed by ≤3 %, not
   the "moved destination" effect claim 6's RESULT NOTE found at 470 Ω against a 100 Ω
   driver) — i.e. confirm `Rdrv ≤ 24.7 Ω`-class headroom against the real driver chosen,
   not the illustrative 100 Ω `supervisor.cir` used.
2. The actual chosen injector-bank FET's `Crss`/`Ciss`/`Vgs(th)` should be re-run through
   `supervisor.cir` claim 3's sweep to confirm the 470 Ω figure (or its recalculation)
   still clears Miller coupling at this design's own 2.8 V/µs edge, per claim 6's own
   stated caveat that the result scales as 1/Crss.
3. If a firmware current-loop prototype is built before this decision is finalized, its
   achieved loop bandwidth/jitter against the 1–3 ms injection window and the ~38 µs
   boost-ramp time should be measured and compared against what MC33816's hardware
   comparators would have guaranteed — this is the concrete evidence that would either
   confirm or overturn recommendation §item 2 above.

---

## Negative results, recorded

- **ST L9781/L9782 full datasheet** — not retrieved. Three fetch attempts this session
  (`st.com/resource/en/data_brief/l9781.pdf` — 60 s timeout; `alldatasheet.com` mirror —
  HTTP 403; `st.com/resource/en/datasheet/l9781.pdf` — 60 s timeout), on top of memo 10's
  own two prior failed attempts against the same document. Every claim about this part
  in §2.4 is explicitly SNIPPET-level and must not be used as a schematic input without
  the actual datasheet — recommended action for whoever owns Phase 2: request the
  document directly from an ST distributor or FAE contact rather than another automated
  fetch, since the pattern across two independent sessions is a consistent block, not a
  transient failure.
- **ST L9781 DigiKey live product page** — HTTP 403 on direct fetch, consistent with
  memo 07's own documented DigiKey/Mouser bot-mitigation behaviour. Price and package
  are SNIPPET-level (search-index only).
- **MC33816's low-side pre-driver off-state drive impedance** (the LS equivalent of
  Table 33's HS numbers) — not located in the pages read this session. The claim that it
  is in the same tens-of-ohms class as the high-side table is INFERRED from the matching
  push-pull output topology shown in Figure 16, not read from a numbered table.
- **MC33816's bootstrap-capacitor decay time under a brownout/VBATT-loss condition** —
  not stated anywhere in the retrieved datasheet. This is the specific gap that prevents
  treating MC33816's fail-safe behaviour as equivalent to `supervisor.cir`'s claim-4
  guarantee rather than merely analogous to it (§6 above).
- **A confirmed resolution of MC33816AE's "Last Time Buy Date: 06/08/2027" field**
  (memo 07 §3.2) — still open. Not re-attempted this session; flagged again because this
  memo's recommendation depends on it remaining a live part if the fallback conditions
  in the Recommendation section are ever triggered.
- **A quantitative per-channel current rating for L9781/L9782** — not found in any
  source retrieved this session (SNIPPET only: "5 inductive loads," no amperage figure).
