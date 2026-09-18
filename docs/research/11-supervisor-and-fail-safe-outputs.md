# Research Memo: Supervisor Circuit — Watchdog, Brownout, and Output State During Reset

**Task:** Spec §3's chain of protection collapsed on 18 Sep 2026 (U12, U13): the DSE4522
reads engine speed from this ECU over CAN, and the only relay in the path signals rather
than removes power. Nothing external to this ECU currently interrupts fuelling without
the ECU's cooperation, and a standalone trip module is specified but not fitted. This
memo asks the question that gap exposes: what does this board do when its own MCU stops
executing correctly? There is no supervisor circuit anywhere in the current design —
no external watchdog, no brownout/reset supervisor, and nothing defining output state
during MCU reset.
**Date:** 2026-09-18
**Scope:** Read-only research. No repo files modified, nothing committed, no subagents
dispatched.

---

## Verdict (read this first)

The S32K148 datasheet and reference manual, retrieved and read directly, confirm the
hazard is real and quantify it: **Low Voltage Reset (VLVR, 2.50–2.7 V) is always
active and forces a reset in every mode, but Low Voltage Detect (VLVD, 2.8–3.0 V) only
forces a reset if firmware sets `LVDRE`**, and the part's own datasheet states the
S32K148 is not guaranteed to execute correctly below 2.97 V with the PLL engaged. That
leaves a **sourced, non-trivial band — roughly 2.97 V down to 2.58 V typ, ~390 mV wide
— where the MCU is out of its own guaranteed operating envelope but nothing internal
has reset it yet**, unless `LVDRE` is set (which narrows but does not close the band).
Reset-and-boot text in the same manual confirms **non-analog GPIO pins are configured
disabled on reset** — high-impedance is the documented behaviour, not a guess. Separately,
NXP's own MC33814 automotive injector/ignition driver datasheet documents production
practice for exactly this exposure: **the driver IC's own POR forces every output off,
independent of what the host MCU's pins are doing** — the fix lives partly in the driver
stage, not only in pull-down resistors.

For the watchdog question, four parts were retrieved and read in enough depth to compare
architectures, not just marketing copy: **TI TPS3850/TPS3813** are cheap, small,
standalone windowed-watchdog supervisors (10-pin VSON / 6-pin SOT-23) that monitor a
rail directly and drive an open-drain RESET; **NXP FS26** and **Infineon TLF35584** are
full safety SBCs/PMICs that additionally offer **true question/answer (challenge-response)
watchdogs** and **dedicated safe-state output pins (FS0B/FS1B, SS1/SS2)** that the
device's own fail-safe state machine can assert independent of any live MCU
communication — but adopting either means replacing this design's existing buck
pre-regulator and LDO architecture (spec §6), not adding one part beside it.

**Recommendation: TPS3850-class windowed supervisor, threshold set above VLVD's 3.0 V
max, RESET output gating a discrete "kill" pulldown on every injector and metering-unit
gate node, backed by 10 kΩ gate-source pulldowns (Infineon's own stated typical value)
as the passive baseline.** This is buildable now, without restructuring the power tree,
and is independently justified regardless of the mandatory trip module — they protect
different failure points (Q6).

---

## 1. Internal vs external watchdog — what the on-die peripherals cannot cover

**CONFIRMED**, from the S32K1xx Series Reference Manual (Rev. 13, 04/2020), retrieved
in full (14 MB PDF, `community.nxp.com` mirror) and the S32K1xx Data Sheet (Rev. 6,
01/2018, via `www1.futureelectronics.com/doc/NXP/FS32K146HAT0VLQT.pdf`):

- The S32K1xx has **two separate on-die watchdog-class peripherals**, and they are not
  redundant with each other: the **WDOG** (internal watchdog, resets the MCU's own core
  and peripherals) and the **EWM** (External Watchdog Monitor). Quoting the reference
  manual directly on EWM: *"The EWM differs from the internal watchdog in that it does
  not reset the MCU's CPU and peripherals. The EWM provides an independent EWM_OUT_b
  signal that when asserted resets or places an external circuit into a safe mode."*
  This means the S32K148 already has an on-die mechanism whose *output* is meant to
  drive external hardware into a safe state — but it shares the same die, the same
  power rail, and (absent specific clock-source configuration) can share failure modes
  with the core it is meant to backstop.
- **WDOG supports windowed mode** (`CS[WIN]`, `WIN` register) and **can be clocked from
  a source other than the bus clock**: *"The options allow software to select a clock
  source independent of the bus clock for applications that need to meet more robust
  safety requirements. Using a clock source other than the bus clock ensures that the
  watchdog counter continues to run if the bus clock is somehow halted."* There is even
  a **"backup reset"**: *"a safeguard feature that independently generates a reset in
  case the main WDOG logic loses its clock... If the watchdog counter overflows twice in
  succession (without an intervening reset), the backup reset function takes effect."*
  This is a materially more capable on-die watchdog architecture than "just a timeout
  counter" — NXP has already engineered around the plain clock-failure case.
- **What none of this covers, and the reference manual does not claim to cover:** a
  core that is executing the *wrong* application code but whose scheduler or a
  low-priority ISR still reaches the watchdog-service call on schedule. Both WDOG and
  EWM are serviced by writing a value from *somewhere* in the code the core is
  executing; neither peripheral can distinguish "correct control flow reached this
  service call" from "any code path reached this service call," because both live on
  the silicon being monitored and have no visibility into which code path issued the
  refresh. This is exactly the case a **question/answer watchdog closes** (§2) and
  windowing alone does not (§2) — INFERRED from combining the confirmed WDOG/EWM
  mechanics above with the TLF35584 functional-watchdog mechanism read in §2, not
  stated explicitly as a limitation in NXP's own text.
- **Every one of these peripherals is configured by firmware after reset.** A firmware
  bug that fails to enable `LVDRE`, fails to configure WDOG windowing, or fails to route
  EWM_OUT_b usefully leaves the corresponding protection silently absent — and there is
  no external check on whether that configuration happened correctly. An external
  supervisor's threshold and window are set by resistors/capacitors or SPI-from-a-second-
  die, not by the same firmware whose failure it exists to catch.

**Why automotive practice still fits an external part, stated plainly:** it is not that
the on-die peripherals are poorly engineered — the WDOG/EWM/backup-reset chain above is
genuinely thorough. It is that **every one of them is the same silicon, the same power
domain, and (for WDOG/EWM specifically) configured by the same firmware being
protected against.** An external supervisor is a second, physically independent part:
different die, different supply-monitoring analog front end, and — for the
question/answer class — a challenge the monitored firmware must *compute*, not just
schedule a call to.

---

## 2. Windowed watchdogs and question/answer supervisors — what four real parts provide

### 2.1 TI TPS3850 — **CONFIRMED**, full datasheet retrieved (`ti.com/lit/ds/symlink/tps3850.pdf`, SBVS301B, Oct 2016 rev. Sep 2021)

Precision voltage supervisor **plus** programmable window watchdog in one 10-pin VSON
part. Directly confirmed electrical table (§6.5, at 1.6 V ≤ VDD ≤ 6.5 V,
−40 °C to 125 °C):

| Parameter | Min | Typ | Max | Unit |
|---|---|---|---|---|
| VDD supply range | 1.6 | — | 6.5 | V |
| VPOR (power-on reset voltage) | — | — | 0.8 | V |
| VUVLO | — | — | 1.35 | V |
| Overvoltage/undervoltage SENSE threshold accuracy | — | — | ±0.8 % | — |

Timing table (§6.6) confirms **factory-selectable window ratios of 1/8, 1/2, and 3/4**
(lower boundary : upper boundary), and — with the `CWD` pin left unconnected —
**t_WDL spans ~1.85 ms to ~800 ms and t_WDU spans ~2.5 ms to ~1840 ms** depending on the
`SET0`/`SET1` pins; an external capacitor on `CWD` (0.1 nF to 1000 nF) extends this
further, with the footnote giving 62.74 ms (0.1 nF) to 77.45 s (1000 nF) for t_WDU(typ).
`RESET` and `WDO` are both open-drain, pulled up externally. Footnote directly states:
*"When VDD falls below VPOR, RESET and WDO are undefined."* — i.e. even this supervisor
has its own undefined band below its own POR threshold (0.8 V max), which is far below
anything relevant to a 3.3 V rail, but is worth carrying as a general principle: **every
supervisor has its own minimum operating voltage below which it, too, is undefined.**

### 2.2 TI TPS3813 — **CONFIRMED**, full datasheet retrieved (`ti.com/lit/ds/symlink/tps3813.pdf`)

Same family concept, smaller (6-pin SOT-23), simpler configuration: `WDT` sets the
upper timeout limit (GND/VDD/external cap), `WDR` sets the window ratio (GND/VDD only,
two ratio classes rather than three). Confirmed electrical table: negative-going input
threshold `VIT` for the L30 variant is **2.58 V min / 2.64 V typ / 2.7 V max**
(directly usable as an off-the-shelf threshold sitting almost exactly on the S32K148's
own VLVR typ of 2.58 V — see §3 on why that is *not* actually the right threshold to
pick). Timing table gives watchdog window ratios up to **1:127.7** and a base delay
`td` of 20/25/30 ms after VDD exceeds VIT+0.2 V. Both this and TPS3850 are genuinely
low-part-count, low-cost additions: a handful of passives plus one SOT-23/VSON IC.

### 2.3 NXP FS26 — **CONFIRMED**, short data sheet retrieved and read as images (`nxp.com/docs/en/data-sheet/FS26_SDS.pdf`, Rev 6.1, 30 Jul 2026; full data sheet requires NDA per the document's own cover page — noted, not obtained)

FS26 is a **safety system basis chip (SBC)**, not a standalone supervisor: it integrates
a wide-input (VBST 5–18 V, VPRE HVBUCK buck configurable 3.7–6.35 V/1.5 A) pre-regulator,
a VCORE regulator (0.8–3.35 V), two LDOs, two trackers, and a voltage reference —
i.e. it **replaces**, not supplements, this design's existing buck pre-regulator and LDO
(spec §6). Its watchdog block is explicitly dual-mode — the device's own part table
distinguishes **"Simple"** vs **"Challenger"** watchdog variants by part suffix, and the
block diagram labels it directly: *"WINDOW WATCHDOG (SIMPLE/CHALLENGER)."* Confirmed
via a companion NXP search summary that ASIL D applications require the challenger
variant. FS26 also has **two dedicated fail-safe output pins, FS0B and FS1B (plus
RSTB)**, driven by an independent "FAIL SAFE OUTPUT DRIVER" block inside the chip's own
fail-safe logic domain, explicitly drawn in the block diagram feeding an external
**"ACTUATORS"** block — this is the "hard-disable independent of MCU" mechanism the
task asks about, built into a full SBC rather than a standalone add-on. Package:
LQFP48 with exposed pad.

### 2.4 Infineon TLF35584 — **CONFIRMED**, full 4-page-summarized (actually multi-hundred-page) datasheet retrieved and read (`infineon.com/assets/row/public/documents/10/49/infineon-tlf35584-datasheet-en.pdf`, Rev 2.0, 2017-03-16)

Also a full PMIC (step-up/step-down pre-regulator 3–40 V input, multiple LDOs/trackers),
**not** a standalone supervisor — same caveat as FS26. But its watchdog architecture is
the clearest confirmed answer to "what does question/answer actually mean, mechanically."
Quoting §15.1 directly: *"Two independent types of watchdogs are implemented in the
TLF35584: A standalone window watchdog (WWD)... A standalone functional or
question/answer watchdog (FWD)... The watchdogs have independent timers and error
counters, which allows to run both watchdogs in parallel."* And §15.3, quoted directly
on the FWD mechanism: *"A question is generated (taken out of table)... The question
consists of 4 bits, the expected answer consists of 4 responses of 8 bits each. The
four responses shall be sent before the heartbeat period has ended... If the complete
answer (all four responses – 32 bits) is correct... it is regarded as 'Valid FWD
triggering.'"* **This is the concrete mechanical answer to why question/answer defeats
a stuck-loop-that-still-kicks-the-dog: the correct 32-bit answer must be looked up from
a table and assembled into four SPI writes in the right sequence — a code path that
happens to call a single `WDOG_Refresh()` function cannot produce this by accident.**
TLF35584 also has **SS1/SS2 ("Secondary Safety Shutdown") pins**, driven directly by
the window-watchdog and functional-watchdog failure counters through dedicated safety
logic (Figure 59, §12.5): *"ΣWWO = Number of 'Invalid WWD triggering', after safe state
control shall activate the safe state signal SS1 and SS2."* Packages: PG-VQFN-48 or
PG-LQFP-64.

### 2.5 Maxim MAX16997/MAX16998 — **SNIPPET only, not retrieved in full**

Two full-text fetch attempts (`analog.com` direct, `datasheet4u.com` mirror) both
failed — one timed out twice (60 s and 140 s), the other returned non-PDF content
mislabeled as a PDF. What search-result snippets state (unverified against the document
itself): four independent inputs for reset/watchdog, `SWT`/`SRT` pins set watchdog and
reset timeout via external capacitors, active-low `RESET` and active-low `ENABLE`
outputs, 8-pin µMAX, −40 °C to 125 °C automotive-rated. **Not elevated to CONFIRMED.**
The `ENABLE` output is notable if true — a dedicated enable-gating pin distinct from
`RESET` is exactly the mechanism §4/§6 need — but this project's own discipline (memo
09, memo 10) is explicit that snippet-level claims are not design inputs, so this is
recorded as a lead, not a basis for the recommendation.

### What each actually costs in parts, stated plainly

- **TPS3850 / TPS3813**: one small IC (VSON-10 / SOT23-6) plus a handful of resistors
  and optionally one capacitor. Adds to the existing power architecture without
  changing it. **This is the class that fits a "supervisor bolted onto an otherwise-
  finished power tree," which is this project's situation.**
- **FS26 / TLF35584**: one 48–64-pin IC that **is** the power tree — buck pre-regulator,
  core LDO, sensor LDOs, tracker regulators, reference, and the safety logic all in one
  part. Adopting either means re-deriving spec §6 from scratch, not adding a block
  beside `buck_preregulator.cir` and `mcu_pdn.cir`. Also gates significant parts of the
  FS26 full datasheet behind NDA (confirmed from the short data sheet's own cover page),
  which is a real cost for a small team, separate from silicon price.

---

## 3. Brownout — the threshold, the hazard band, and what the 150 µF cap does to it

**CONFIRMED**, from the S32K1xx Data Sheet (Rev. 6, 01/2018), Table 2 and Table 5,
retrieved and read directly (text-extracted, not paraphrased from a search snippet):

- **Minimum operating voltage, stated in the datasheet's own words** (footnote 3 to
  Table 2): *"S32K148 will operate from 2.7 V when executing from internal FIRC. When
  the PLL is engaged S32K148 is guaranteed to operate from 2.97 V."* Table 2 itself:
  `VDD` min **2.73 V**, and a boxed NOTE above the table: *"Full functionality/
  specifications cannot be guaranteed when voltage drops below 2.7 V."*
- **Table 5, "VDD supply LVR, LVD and POR operating requirements"** — the exact table
  the task asked for:

  | Symbol | Description | Min | Typ | Max | Unit |
  |---|---|---|---|---|---|
  | VPOR | Rising and falling VDD POR detect voltage | 1.1 | 1.6 | 2.0 | V |
  | VLVR | LVR falling threshold (RUN, HSRUN, STOP) | 2.50 | 2.58 | 2.7 | V |
  | VLVR_LP | LVR falling threshold (VLPS/VLPR) | 1.97 | 2.22 | 2.44 | V |
  | VLVD | Falling low-voltage detect threshold | 2.8 | 2.875 | 3 | V |
  | VLVW | Falling low-voltage warning threshold | 4.19 | 4.305 | 4.5 | V |

  (VLVW is stated for completeness; at this design's 3.3 V nominal `3V3_MCU` rail, VLVW's
  4.19 V min floor is above the rail's own nominal voltage and therefore cannot function
  as a meaningful warning here — flagged as an **INFERRED implication**, not stated as
  such in the datasheet, which documents the part across its full 2.7–5.5 V VDD range.)

- **Reference manual, §25.2.2.2, confirms the reset-forcing behaviour directly**:
  *"Besides LVD operation, the device also supports LVR (Low Voltage Reset) operation.
  If the supply voltage falls below the reset trip point (VLVR), a system reset will be
  generated. **LVR system is enabled in all modes.** LVDRE has effect on LVD operation
  only."* I.e. **LVR always resets the part; LVD only resets it if firmware has set
  `PMC_LVDSC1[LVDRE]`.** This is the load-bearing distinction for the "band" question:
  without `LVDRE` set, the *only* automatic reset floor is VLVR at 2.50–2.7 V, not VLVD
  at 2.8–3.0 V.

**The hazard band, quantified from these confirmed numbers, not invented:**

1. **With `LVDRE` unset (a plausible firmware omission, not a hypothetical)**: the MCU's
   own datasheet stops guaranteeing correct operation at 2.97 V (PLL engaged) but the
   first automatic reset does not occur until VLVR's typ 2.58 V / worst-case 2.50 V.
   That is a **~390–470 mV band, executing with outputs still under firmware control,
   in which the part's own datasheet has already withdrawn its correctness guarantee.**
2. **With `LVDRE` set** (zero-BOM-cost, firmware-only fix, and this memo recommends it
   regardless of any external supervisor): the automatic floor rises to VLVD's 2.8–3.0 V,
   which **still sits below the 2.97 V PLL-guarantee floor at the typ corner (2.875 V)**
   — a narrower but nonzero ~95 mV gap remains at typical parts, wider at worst-case
   corners (2.97 V guarantee vs. 2.8 V min LVD trip = 170 mV).
3. **Neither of these is zero**, and both exist entirely within NXP's own published
   numbers — this is not a manufactured hazard.

**What the 150 µF bulk cap does to the *duration* of this band — INFERRED, original
arithmetic, not sourced to a load-current measurement:** `mcu_pdn.cir`'s RESULT NOTE
(read in full, §"Power chain stages 6 and 7") records the bulk capacitor on `3V3_MCU`
was raised from 47 µF to 150 µF on 18 Sep 2026 for a PDN-impedance reason unrelated to
brownout (damping the LDO/bulk anti-resonance). That capacitor still governs how long a
*lost* rail takes to sag through the ~390 mV LVR-to-guarantee band once the LDO can no
longer supply it (e.g. on an upstream supply loss, not a cranking dip — the buck stage's
6–40 V input range with 6 V covering the cranking dip means a *normal* crank event should
not reach this rail at all). Using `dt = C·ΔV/I` with the now-confirmed 390 mV band and
an assumed, unsourced load current in the tens-to-low-hundreds-of-mA class typical for
this MCU plus its immediate peripherals:

| Assumed load | dt across the 390 mV band |
|---|---|
| 50 mA | 1.17 ms |
| 100 mA | 585 µs |
| 200 mA | 293 µs |

**These are sub-millisecond to low-millisecond, i.e. shorter than even the fastest
window-watchdog configurations surveyed in §2** — for a *lost-supply* event, the on-die
LVR should reset the part well before any watchdog would have caught it. The scenario
that actually matters is a **slow sag** (not a clean loss): if the buck stage's own
regulation degrades gradually rather than losing input entirely, the rail could linger
in the band far longer than this RC estimate, which assumes no regulation at all during
the sag. No source found quantifies this slower-sag case for this specific buck design;
flagged as an open item for `buck_preregulator.cir`'s own next revision rather than
guessed here.

**What margin a supervisor threshold needs above VLVR/VLVD, stated plainly:** an external
supervisor exists specifically to fire *before* the MCU's own guarantee lapses, and to do
so **regardless of whether firmware ever set `LVDRE`.** Its threshold should sit above
VLVD's stated max (3.0 V) with margin for the supervisor's own accuracy (TPS3850's ±0.8%
threshold accuracy, confirmed in §2.1) and for the fact that VLVD is a *falling* threshold
with separately-specified rising hysteresis — i.e. roughly **3.05–3.10 V** is a reasonable
target for the external supervisor's undervoltage trip, giving clearance above both VLVD's
worst case and VLVR's worst case, and doing so independent of any internal MCU register
configuration. This is a design recommendation for this memo, not a number pulled from a
source.

---

## 4. THE QUESTION I MOST WANT ANSWERED — output state during reset

**CONFIRMED, GPIO default state.** S32K1xx Series Reference Manual, §25.2.2 (System
reset sources), quoted directly: *"The on-chip peripheral modules are disabled and the
non-analog I/O pins are initially configured as disabled. The pins with analog functions
assigned to them are configured for their analog functions after reset."* And §12.5.1
(`PORT_PCRn`), MUX field: *"000 Pin disabled (Alternative 0) (analog)."* This confirms
the task's premise directly from the primary source, not from a forum answer: **GPIOs
are high-impedance / disabled out of reset, and stay that way until firmware writes the
PCR MUX field.** The register's `PE` (pull enable) and `PS` (pull select) bit reset
values are explicitly documented as **"Varies by port. See Signal Multiplexing and
Signal Descriptions chapter for reset values per port"** — i.e. **not every pin defaults
to the same pull state.** Some dedicated pins have a stated default (JTAG: *"TDI as
pullup, TCK as pulldown, TMS as pullup"*, confirmed in the same reset-and-boot section);
general-purpose pins do not have a universal default documented at this level. **This is
an open item specific to this design, not resolved by this memo**: the S32K148's
pin-mux/signal-multiplexing table — which physical `PTxx` pin ECU pins 88, 73, 07, 29,
03 and 05 land on — is explicitly deferred to Phase 2 per spec §5 ("confirming how many
ADC channels the 144-pin package actually breaks out (needs the reference manual's
pin-mux table")). **The exact PE/PS reset default for those six specific pins cannot be
stated until that pin-mux assignment exists.** Do not treat "high-impedance, no pull"
as confirmed for those specific pins — treat "high-impedance by default, pull state
pin-specific and not yet mapped" as the confirmed statement.

**CONFIRMED, production practice for the driver stage itself.** NXP MC33814
("Advanced Fuel Injector and Ignition Coil Driver Controller IC," full datasheet
retrieved as a saved PDF via `nxp.com/docs/en/data-sheet/MC33814.pdf` and text-extracted)
is a real Bosch-family-class injector/ignition low-side driver IC — the same device
class this design's own injector and metering-unit drivers occupy. §5.1.2.2, quoted
directly: *"SPI register settings from Power On Reset (POR) are as follows: • All
outputs turned off • Off State open load detection enabled (LSD) • Default values in
the SPI Configuration, Control and Status registers."* This is the production answer to
the task's question, from a real injector-class driver IC: **the driver IC's own POR
(its `VCC(POR)` threshold, separately confirmed in the same datasheet as 3.9–4.9 V
rising) forces every output off, independent of whatever the host MCU's control pins
are doing during the host's own reset.** The driver does not trust the host's GPIO
state; it has its own POR and its own default-off register state.

**One nuance worth flagging rather than glossing over — a genuine gap in what was
retrieved, not filled in:** MC33814 §5.3.2 lists watchdog timeout, VCC undervoltage,
and VPWR overvoltage as sources of a `RESETB` pulse (used to reset the *host MCU*), but
the retrieved text does not state whether a watchdog-timeout-triggered `RESETB` pulse
*also* resets the 33814's own output/control registers to their POR default, the way an
actual POR (sleep→active transition) does per §5.1.2.2. §5.3.3 separately describes an
SPI-commanded "internal reset" that does clear all registers, but that requires the
host to still be capable of issuing SPI commands — not a given during the fault this
memo is about. **This is recorded as an open question about MC33814 specifically, not
resolved by inference, and it is exactly the kind of assumption ("the driver IC handles
it") that should not be adopted without checking, which is the point of flagging it.**

**Pin-specific exposure in this design, reasoned from spec §2.2, §4 and the sim blocks
read for this task (INFERRED synthesis of confirmed facts, not itself sourced):**

- **Metering unit (pin 88, low-side PWM into a fused-battery-fed coil, per spec §2.2)**:
  `metering_unit_pwm.cir`'s own header states the coil's electrical time constant is
  L/R = 3 ms. If the GPIO driving this gate floats high during a reset/brownout window
  (§3's band, or the tens-of-ms class of watchdog timeout surveyed in §2), the coil
  current will visibly ramp toward its fully-on value within a small multiple of that
  3 ms constant — this is not a momentary glitch, it is enough time for the metering
  unit's actual fuel-metering position to move.
- **Injector low-side selects (73/07/29) and bank high-sides (03/05)**: per spec §2.1,
  these switch a shared 100 V boost rail (`injector_boost.cir`/`injector_turnoff.cir`).
  A floating low-side select gate during reset is lower-consequence alone (no boost-rail
  path is complete unless the corresponding high-side is also conducting), but the
  bank-shared high-side switches (03/05) are the ones exposed to the full 100 V rail on
  their drain — if either floats on during a reset window while any low-side is also
  ambiguous, current can flow into whichever injector coil is selected.

**What standard practice actually is, assembled from the confirmed sources above —
be specific, per the task's own instruction:**

1. **Passive gate-source pulldown on every gate node, sized from a real application
   note, not a round number.** Infineon's 2022 application note "Gate drive for power
   MOSFETs in switching applications" (`infineon.com/assets/row/public/documents/24/42/
   infineon-gate-drive-for-power-mosfets-in-switchtin-applications-applicationnotes-
   en.pdf`, retrieved in full), quoted directly: *"A resistor RGS, in the kΩ range
   (typically 10 kΩ), is highly recommended between the gate and source so that the
   MOSFET gate will be discharged if the gate becomes disconnected from the driver
   circuit. Without this a MOSFET may remain on when it should be off..."* **10 kΩ is
   this memo's recommended value, and here is why it clears this design's own numbers,
   not just the AN's round figure:**
   - *Leakage check*: S32K1xx Data Sheet Table 10 (§5.3, CONFIRMED), input leakage per
     pin at VDD = 3.3 V is **0.005 µA typ / 0.5 µA max**. Through 10 kΩ that is at most
     5 mV — utterly negligible against any gate threshold.
   - *Discharge-speed check*: RC = 10 kΩ × Ciss. No specific gate driver FET part number
     is chosen yet for this design (spec §8, U5-adjacent gap), so this uses a
     representative automotive power-MOSFET class Ciss of 1–4 nF — **INFERRED, not
     sourced to a chosen part.** RC ≈ 10–40 µs, three to four orders of magnitude faster
     than the shortest injection event (1 ms) or the fastest watchdog window considered
     in §2/§5. The pulldown does not need to be any stronger than 10 kΩ to be fast
     enough for this application's own timescales.
   - *dV/dt-coupling check, the case the same Infineon AN specifically warns needs a
     "strong" pulldown*: quoted directly, *"A strong pull-down is important in
     hard-switching half-bridge or full-bridge configurations to prevent C.dv/dt-induced
     turn on."* This design's own already-computed turn-off edge
     (`injector_turnoff.cir`'s RESULT NOTE / research memo 10 §5) is **~2.8 V/µs** across
     the 100 V boost rail — the memo's own number, reused here, not re-derived. Using an
     illustrative Crss of 50–200 pF (again a class figure, INFERRED, not a chosen part),
     the coupled current is `I = Crss·dV/dt ≈ 140–560 µA`.

     > **CORRECTION, 18 Sep 2026 — this paragraph was wrong by a factor of 1000, and
     > the conclusion it reached does not survive the fix.**
     >
     > It originally read: *"Through 10 kΩ that is at most ~5.6 mV — again far below any
     > realistic gate threshold,"* and concluded that a plain 10 kΩ weak pulldown is
     > adequate without an active clamp.
     >
     > 560 µA through 10 kΩ is **5.6 V**, not 5.6 mV. `560e-6 × 10e3 = 5.6`.
     >
     > `sim/blocks/supervisor.cir` was built to test this paragraph's conclusion as
     > claim 3, and it **FAILS**. Simulated peak gate voltage, which includes the gate's
     > own Ciss dividing the step down and so reads somewhat below the bare arithmetic:
     >
     > | Crss | V(gate) through 10 kΩ alone |
     > |---|---|
     > | 20 pF | 0.465 V |
     > | 50 pF | **1.155 V** |
     > | 100 pF | 2.289 V |
     > | 200 pF | 4.497 V |
     > | 500 pF | 10.647 V |
     >
     > Against a representative Vgs(th) of 1.0 V it fails at **50 pF — the low end of
     > this memo's own illustrative range**, not at some pessimistic extension of it.
     >
     > The edge-rate argument above is still correct as far as it goes: 2.8 V/µs really
     > is two orders of magnitude gentler than the hard-switched half-bridge case the
     > "strong pulldown" literature addresses. It just does not license 10 kΩ, and the
     > arithmetic slip is what made it look as though it did.
     >
     > **The pulldown cannot be a fixed number in this memo.** It is set by the FET
     > actually chosen, through `Rpd < Vgs(th) / (Crss · dV/dt)`. At this design's
     > 2.8 V/µs and a 1.0 V threshold: Crss 200 pF needs under 1.79 kΩ, 500 pF under
     > 714 Ω, 1000 pF under 357 Ω. Halve for margin. Bounded from below by the gate
     > driver's source current, since the pulldown fights it continuously during
     > conduction — 300 Ω holding a 10 V gate costs 33 mA per gate, and there are six.
     >
     > What survives unchanged is everything the kill transistor does. Claim 4 passes
     > across six brownout ramps with margin. This correction is about the passive
     > resistor beside it, not the supervisor path.
2. **A driver IC whose own POR forces outputs off, independent of host GPIO state** —
   confirmed real practice per MC33814 above. This is the stronger mechanism where
   applicable, because it does not depend on a passive resistor racing an active driver
   trying to turn the gate on; it removes the ambiguity at its source.
3. **A supervisor output that hard-disables the drivers independent of the MCU** — this
   is what FS26's FS0B/FS1B and TLF35584's SS1/SS2 are *for* (§2.3, §2.4), confirmed
   from their own block diagrams and safe-state-control chapters. This project's
   recommended part class (§2's TPS3850/TPS3813) does not have a dedicated safe-state
   pin the way those SBCs do, but its open-drain `RESET` output serves the same role
   when wired through one inverting stage into a dedicated "kill" pulldown transistor
   at each protected gate node — see the Recommendation below.

---

## 5. Reset timing against the injection event

**INFERRED — original arithmetic against this project's own confirmed engine numbers,
not sourced to a watchdog-timeout industry standard, per the task's instruction to state
assumptions plainly.**

Base figures, already established and confirmed elsewhere in this project (memo 04,
memo 10, `boost_converter.cir`): 1500 rpm, 3-cylinder, 4-stroke ⇒ one full engine cycle
(720°, 2 revolutions) = **80 ms**; per-cylinder firing interval (cylinders phased 240°
apart) = **26.67 ms**. Memo 10's own assumption (explicitly flagged there as an
assumption, not a sourced fact) of a pilot+main+post = 3 injection events per cylinder
per cycle gives **9 events / 80 ms ≈ 112.5 Hz**, i.e. an average of one injection event
every ~8.9 ms, though in practice a cylinder's triplet lands in a short burst (memo 10's
own `injector_turnoff.cir` spaces them 300 µs apart, itself unsourced) rather than
evenly across the 26.67 ms gap.

| Watchdog timeout | Cylinder-intervals covered (÷26.67 ms) | What a hung ECU could do inside it |
|---|---|---|
| 1 ms | 0.037 | Shorter than a single injection event (1–3 ms) — could interrupt *one event in progress*, not even complete it |
| 5 ms | 0.19 | Within one cylinder's pilot/main/post triplet only |
| 10 ms | 0.375 | Still within one triplet's worth of time, comfortably |
| 26.67 ms | 1.0 | Exactly one additional cylinder gets a full, possibly wrong or stuck, firing decision |
| 50 ms | 1.87 | ~2 more cylinders fire under the hung condition before recovery |
| 100 ms | 3.75 | Every cylinder gets an extra full engine cycle (all 3 fire again) |

**The metering unit (pin 88) is the more continuously-exposed output, not the
injectors**: it is not event-scoped, it is a continuous PWM duty. `metering_unit_pwm.cir`
gives the coil's electrical time constant as 3 ms; a stuck duty cycle held for any of the
timeouts above except the 1 ms row is long enough for the coil current — and therefore
the actual fuel-metering position — to have **settled** at whatever the stuck command
was, not merely glitched toward it.

**What this implies for choosing a timeout, stated as a design conclusion rather than a
sourced number**: keeping total hung-ECU exposure **under one cylinder-to-cylinder
interval (26.67 ms)** keeps the worst case to "part of one cylinder's injection triplet
affected," rather than "one or more entire extra cylinders fire under an uncommanded
condition." That argues for a **window watchdog with its closed (upper) boundary well
under 26.67 ms** — a closed window in the 15–20 ms class, with an open (lower) boundary
comfortably above the 1–3 ms injection duration (so normal interrupt/scheduling jitter
around a real injection event does not false-trip the window) is the target this memo
recommends qualitatively. **The exact capacitor/register values to hit that window on a
chosen supervisor part are explicitly left open here** — TPS3850's own equations
(referenced in its datasheet's revision history but not extracted in this pass) would
size it precisely once a part and threshold are finalized. Guessing a specific
picofarad value into this memo would be exactly the "confident desk reasoning" failure
mode this project's own sourcing discipline exists to catch; it is left as a Phase-2
hardware/firmware co-design item instead.

---

## 6. Does the supervisor need to be independent of the trip module, or can they be one thing?

**INFERRED — reasoned from spec §3 read in full, not sourced to an external reference,
and stated as this memo's considered position rather than hedged.**

**They are not redundant. They protect different points in the chain, and removing
either weakens the design in a way the other does not cover:**

- **The trip module (spec §3 item 5) is downstream and symptom-facing.** It must break
  the metering unit's own battery feed (through fuse `8F1`) — i.e. it acts on the
  *load side* of the metering unit, after everything upstream (MCU, GPIO state, gate
  driver, FET) has already done whatever it was going to do. It is triggered by an
  engine-level fault signal (most plausibly overspeed, per spec §3's own reasoning
  about the standalone MPU-driven trip module) and its detection latency is bounded by
  how fast the engine can visibly speed up, not by how fast the MCU misbehaves. It is
  also the *only* mechanism in this whole discussion that can stop a **hardware fault
  downstream of the gate** — a low-side FET that has failed shorted, for instance, is
  completely unaffected by anything a supervisor does to that FET's gate, because the
  gate is no longer what is holding the FET on. Only removing supply at the relay
  reaches that failure.
- **A supervisor that hard-disables the drivers is upstream and root-cause-facing.**
  It watches whether the MCU itself is behaving (via watchdog) and whether its supply
  is in-spec (via undervoltage threshold), and it acts at the gate, before current ever
  reaches the injector or metering coil. It catches failure modes that never progress
  to an engine-level symptom the trip module's overspeed logic would notice — a hung
  MCU commanding a *wrong but not obviously runaway* fuelling profile (rough running,
  white smoke, a stall under load, a genset that drops load without ever exceeding
  1680/1710 rpm) is invisible to an overspeed-triggered trip module but is exactly what
  a watchdog-driven gate kill catches, because it does not care what the fuelling
  profile *looks like* downstream — it only cares whether the MCU is still answering
  correctly.
- **They also differ in what they depend on.** The trip module (per spec §3 item 5's
  own requirement) must not depend on the GCU relay chain that U12 just showed fails —
  it has to be its own mechanical/electrical path to the metering unit's supply. A
  supervisor on this board depends on nothing outside this board: it does not care
  whether the DSE4522 is configured correctly, whether the alternator is exciting, or
  whether the trip module itself has been correctly wired — all conditions spec §3
  already flags as real, live uncertainties for the *other* two lines of defence.

**Where they do overlap, and why that overlap is a feature, not waste**: in the specific
scenario of "MCU hangs, metering unit gets stuck on," both mechanisms independently
break the fuelling path — the supervisor at the gate, the trip module at the relay.
That is genuine defence-in-depth precisely because their independence is real (different
physical points, different trigger conditions, different failure dependencies), not
because either one is a weaker copy of the other. **A supervisor is not a substitute for
the trip module** — it has no path to the alternator-side over-frequency signal and no
mechanical contact breaking the battery feed, so it cannot replace what spec §3 item 5
requires. **The trip module is not a substitute for a supervisor** — it does nothing
until the engine has already visibly misbehaved, and does nothing at all for a stuck
FET's gate. Both belong in this design.

---

## What transfers to this design

1. **Enable `PMC_LVDSC1[LVDRE]` in firmware startup.** Zero-BOM-cost, moves the internal
   automatic reset floor from VLVR (2.50–2.7 V) up to VLVD (2.8–3.0 V), narrowing (not
   closing) the band identified in §3. This is a firmware action, not a hardware one,
   but it belongs in the same design review that adds the external supervisor, because
   it is the cheapest partial mitigation available and there is no reason not to take it.
2. **A TPS3850/TPS3813-class supervisor, not an FS26/TLF35584-class SBC.** The latter
   pair would require re-deriving spec §6's entire power architecture; the former adds
   one small part beside `buck_preregulator.cir`/`mcu_pdn.cir` without disturbing either.
3. **10 kΩ gate-source pulldowns on every gate this task named** (pin 88's metering FET;
   the 73/07/29 low-side selects; the 03/05 bank high-sides), justified against this
   design's own confirmed leakage number (S32K1xx datasheet, ≤0.5 µA) and this project's
   own already-computed turn-off edge rate (~2.8 V/µs, memo 10), not against a generic
   round number.
4. **Route the supervisor's RESET through one inverting stage into a dedicated kill
   pulldown at each protected gate**, so that reset/brownout/watchdog-fault conditions
   are enforced at the gate independent of GPIO state, matching what FS0B/FS1B and
   SS1/SS2 do on the parts surveyed in §2, without needing to adopt a full SBC to get it.
5. **The pin-mux table gap (spec §5, deferred to Phase 2) directly blocks finishing this
   analysis.** Until ECU pins 88/73/07/29/03/05 are mapped to physical `PTxx` pins, this
   memo cannot state those specific pins' PE/PS reset defaults from the reference
   manual — only the general GPIO-disabled-on-reset behaviour is confirmed. This should
   be flagged alongside U2/U8 as a dependency for finishing the supervisor/output-safety
   sheet, not silently assumed away.
6. **The trip module and a board-level supervisor are both required — see §6.** Neither
   is optional given the other.

---

## Recommendation: the circuit to build

**Topology:** A TPS3850-class (or TPS3813-class, if the third window-ratio option is
not needed) precision voltage supervisor with programmable window watchdog, monitoring
`3V3_MCU` via its `SENSE` pin (fixed-threshold variant) or, if a threshold other than a
factory-trimmed option is needed, the adjustable `H01` variant with an external divider
per its own `V_MON = V_IT(ADJ) × (1 + R1/R2)` equation (confirmed present in the
datasheet, §7.3.4). Its open-drain `RESET` output, pulled up to `3V3_MCU`, feeds:

- the S32K148's `RESET_B` pin, as conventional; and
- one inverting stage (a single small-signal BJT or logic inverter — not specified
  further here, a Phase-2 detail) whose output drives the gate of a dedicated N-channel
  "kill" transistor placed from each protected gate node (pin 88's metering FET gate;
  73/07/29 low-side select gates; 03/05 bank high-side gates) to ground, in parallel
  with the standing 10 kΩ gate-source pulldown already recommended above. The inversion
  is needed because `RESET` is active-low (asserted during fault) while the kill
  transistor must turn ON — pull the gate down — precisely when `RESET` is asserted.

**Thresholds:**
- Undervoltage trip: **~3.05–3.10 V** on `3V3_MCU`, chosen to sit above VLVD's
  confirmed 3.0 V max with margin for the supervisor's own ±0.8% accuracy — independent
  of whether firmware ever configured `LVDRE`.
- Watchdog window: **closed (upper) boundary well under 26.67 ms** (§5), open (lower)
  boundary comfortably above the 1–3 ms injection duration. Exact CWD/SET0/SET1
  programming left to Phase 2 once a specific part variant is chosen — not guessed here.
- Gate pulldown: **10 kΩ** at every named gate node (§4).

**Part class:** TI TPS3850 (VSON-10) or TPS3813 (SOT23-6) for the supervisor; a
small-signal N-FET (e.g. SOT-23 class, no current-handling requirement beyond
discharging gate capacitance) for each kill transistor; standard 10 kΩ 0603/0805
resistors for the passive pulldowns.

**Specific, falsifiable claims the next SPICE block should check:**

1. With the supervisor's `RESET` asserted and the kill transistor's gate driven high
   (via the inverting stage), every protected gate node should settle below the
   FET class's `Vgs(th)` within the 10–40 µs RC estimate from §4 — not just "eventually,"
   a specific time bound the simulation can assert.
2. With `RESET` deasserted (normal operation) and the MCU actively driving a gate high
   through its normal drive path, the kill transistor and its 10 kΩ pulldown together
   should not measurably slow the intended switching edge — i.e. the pulldown's loading
   effect on turn-on time should be checked against whatever gate-drive current budget
   the eventual driver stage has, not assumed negligible.
3. A simulated Miller/dV/dt coupling event at this design's own ~2.8 V/µs boost-rail
   turn-off edge (memo 10, reused here) should show the gate node staying below
   `Vgs(th)` through the 10 kΩ pulldown alone, across a swept Crss range (the 50–200 pF
   class used in §4's arithmetic) — this directly tests whether the "weak pulldown is
   adequate, no strong/active clamp needed" conclusion in §4 actually holds, or whether
   it was an artifact of the illustrative Crss assumption.
4. A brownout ramp on `3V3_MCU` sagging through the confirmed VLVR/VLVD band (§3) at a
   swept rate (from the sub-millisecond RC estimate up through several orders of
   magnitude slower, to bound the "slow sag" open item from §3) should show the external
   supervisor's own threshold tripping *before* the MCU's outputs could plausibly be
   left in an undefined state by internal LVR/LVD alone — this is the block that would
   either validate or falsify this whole memo's central claim.
5. Total exposure time from watchdog-fault-onset to kill-transistor-conducting should
   be checked against the §5 table's per-timeout-value cylinder-interval count, once an
   actual window value is chosen in Phase 2 — confirming the chosen window keeps worst-
   case exposure under one 26.67 ms cylinder interval as intended.

---

## Negative results, recorded

- **Maxim MAX16997/MAX16998 full datasheet** — not retrieved. Direct fetch from
  `analog.com` timed out twice (60 s, then 140 s in the background); a `datasheet4u.com`
  mirror returned content that was not actually a readable PDF. Everything attributed
  to these parts in §2.5 is explicitly marked SNIPPET and should not be used as a design
  number without retrieving the document.
- **FS26 full data sheet** — the retrieved document is explicitly a "short data sheet"
  whose own cover page states *"For detailed and full information, see the relevant
  FS26 full data sheet... available via the NXP Secure Files content interface to those
  with non-disclosure agreement (NDA) access."* The full watchdog-timing and safe-state
  electrical-characteristics tables were therefore not available in this pass. The
  architectural claims in §2.3 (Simple/Challenger watchdog variants, FS0B/FS1B fail-safe
  output driver) are read directly from the short data sheet's own block diagram and
  part-ordering table, which is CONFIRMED as far as it goes, but does not include timing
  numbers the way TPS3850's public datasheet does.
- **A specific, sourced Crss/Ciss figure for this design's actual injector/metering FET**
  — not found, because no FET part number has been chosen yet (spec §8 does not carry
  this as its own numbered unknown, but it is the same category of gap as U5's injector
  part number). §4's dV/dt-coupling and RC-discharge arithmetic uses illustrative,
  clearly-flagged INFERRED class values (Crss 50–200 pF, Ciss 1–4 nF) rather than a
  sourced number, and the "10 kΩ is adequate" conclusion should be re-checked once a
  specific FET is selected.
- **MC33814's behaviour on a watchdog-triggered (as opposed to POR-triggered) reset,
  specifically whether it also clears the driver's own output/control registers** — not
  resolved from the retrieved text (§4's nuance paragraph). The datasheet is explicit
  about POR behaviour and about SPI-commanded internal reset, but the retrieved §5.3.2
  text does not state whether a watchdog-timeout-triggered `RESETB` pulse has the same
  register-clearing effect. Recorded as open rather than assumed favorably.
- **A quantified "how much longer does the brownout band last under a slow supply sag"
  figure** — not found and not derivable from any source retrieved in this pass; §3's
  RC-decay table explicitly assumes a lost supply with no ongoing regulation, and flags
  the slow-sag case as a `buck_preregulator.cir`-adjacent open item rather than
  estimating it without a basis.
- **TPS3850's exact `t_WDL`/`t_WDU` equations for a custom `CWD` capacitor value** — the
  datasheet's revision history references "Equation 4," "Equation 5," and "Equation 11"
  governing these, but this pass did not extract the equations themselves (only the
  factory-preset timing table, §2.1/§6.6). §5's window-watchdog recommendation is
  therefore qualitative (target ranges) rather than a specific capacitor value, by design
  — filling that in without the equations would be exactly the guessed-into-copper
  failure mode this project's sourcing discipline exists to prevent.
- **Infineon TLF35584 direct datasheet PDF** — the first attempted URL pattern (`dgdl/...
  DataSheet-v01_02-EN.pdf`) returned HTTP 404; the working URL
  (`infineon.com/assets/row/public/documents/10/49/infineon-tlf35584-datasheet-en.pdf`,
  Rev 2.0) was found via a second search and did succeed. Recorded so the failure isn't
  silently absent from the trail — the guess at a version-numbered filename was wrong,
  the actual current document uses a different naming convention.
