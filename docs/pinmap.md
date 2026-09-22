# MCU Pin Assignment — S32K148 to the 94-way Bosch Connector

**Date:** 2026-09-19
**Status:** Phase 2, first artifact. Unblocks the per-pin fail-safe detail spec §4 deferred
and the two Phase-2 items memo 05 §7 left open (how many ADC/FTM channels the 144-pin
package actually breaks out; per-pin reset defaults for the six gate pins).

---

## 0. Preamble — package, sources, method

**Package assumed: 144-pin LQFP, orderable part `FS32K148HAT0MLQT`.** This is the package
already selected in spec §5 and confirmed in `docs/research/05-mcu-selection.md` — chosen
as headroom against the 50 still-unresolved OEM connector pins (U1's register), not
because the *confirmed* 44-pin budget needs it. This document does not revisit that
choice; it uses the `S32K148_144lqfp` column of NXP's own pin table throughout.

**Documents retrieved this session, fresh, not from memory:**

- **NXP, *S32K1xx Data Sheet*, Rev. 15, 5 March 2026** — `nxp.com/docs/en/data-sheet/S32K1xx.pdf`,
  the same revision `docs/research/05-mcu-selection.md` cites. Used for the LVR/LVD
  electrical thresholds (§3 below) and to confirm the datasheet itself defers the pinout
  table to the Reference Manual (§10.1, "For package pinouts and signal descriptions,
  refer to the Reference Manual" — this is a direct quote, not a paraphrase, and it is
  why memo 05 could not close its own two Phase-2 items from the datasheet alone).
- **NXP, *S32K1xx Series Reference Manual*, Rev. 13, 04/2020** — retrieved from
  `community.nxp.com` (the same mirror memo 05 found but did not open). **This PDF has
  eleven Excel workbooks embedded as file attachments**, including
  `S32K148_IO_Signal_Description_Input_Multiplexing.xlsx` — the actual chip-specific
  pin-mux table the Reference Manual's own Chapter 4 says exists but does not inline
  ("IO Signal Description Input Multiplexing sheet(s) attached to the Reference Manual").
  Extracted with `pdfdetach` and read directly (893 rows, `IO Signal Table` tab). **This
  is the primary source for every `PTxx` ↔ peripheral ↔ package-pin-number claim in this
  document, all tagged CONFIRMED below**, and it is the single fact this whole exercise
  turned on: the manual's *narrative* text was retrievable by search all along, but the
  actual per-pin table was not, because it lives in an attachment nobody had opened.
- Sensor front-end topology and signal counts: `docs/superpowers/specs/2026-09-13-ecu-reconciled-spec-design.md`
  §4/§5, `refs/ecu-pinout-extracted.md`, `sim/blocks/*.cir` (read, not modified),
  `docs/research/05-mcu-selection.md`, `docs/research/12-driver-architecture.md`.

**One revision gap, disclosed rather than smoothed over.** The Reference Manual pulled
this session is Rev. 13 (04/2020); the datasheet memo 05 cites is Rev. 15 (2026). No
higher-revision Reference Manual was located or checked. Pin multiplexing is a silicon
mask property, not a document-editing one, and no revision-history entry in either
document (datasheet's own changelog was searched) mentions a pinout or signal-mux change
for the S32K148 specifically — but this is **INFERRED**, not independently confirmed
against a Rev.-15-class Reference Manual, because none was found. If a newer RM surfaces
before schematic capture, diff its `S32K148_IO_Signal_Description_Input_Multiplexing.xlsx`
against the one this document used before trusting a pin unchanged.

**Package pin budget, checked rather than assumed:** the embedded table lists 157 `PTxx`
port pins across the whole S32K1xx family tree; **128 of them are bonded out on the
144-pin LQFP package** (the rest exist only on the 176-pin part or the BGA). This document
commits **39** of those 128 to a signal (37 as first written, plus the two watchdog pins
§1.8 adds). That leaves 89 GPIO-capable pins unused — enough
margin that the 50 still-unknown OEM connector pins (spec §8) will not run the package out
of pins once their function is known, which was an open question memo 05 flagged and this
answers: **the 144-pin package was the right headroom call.**

**Reserved and excluded from this map, deliberately:** `PTA4`/`PTC4`/`PTC5` (JTAG
TMS/TCK/TDI) and `PTA5` (dedicated `RESET_b`) are the only four pins on the whole part
with a reset default other than high-impedance-disabled (Reference Manual §4.4,
Table 4‑3 — see §2 below). None of the 94 connector signals are placed on them. `PTB6`/
`PTB7` (`XTAL`/`EXTAL`) are not used by any signal here either, but whether this design
needs an external crystal at all is not decided anywhere in the repo — flagged in §5.

---

## 1. The mapping table

Columns: **ECU pin** (Bosch 94-way, per spec §4 / `refs/ecu-pinout-extracted.md`),
**Signal**, **Front-end** (from spec §4 / `sim/blocks/`, not re-derived here),
**`PTxx`**, **Peripheral**, **Reset pull** (CONFIRMED from the embedded IO Signal Table —
every non-JTAG/RESET pin reads `PE=0, PS=0`, i.e. **disabled, high-impedance, no
pull**, matching RM §4.4 Table 4-3's blanket "Others: Disabled, High impedance" row), and
a **Note** giving the one-line reason for anything not a free choice.

A pin bearing "—" in the `PTxx` column is not an MCU signal at all — it is a power,
ground, or excitation-supply net that terminates at the power tree or the sensor-ground
plane, not at a GPIO. Those are listed so that every one of spec §4's 44 confirmed
connector pins is accounted for, not silently dropped.

### 1.1 Power

| ECU pin | Signal | Front-end | `PTxx` | Peripheral | Reset pull | Note |
|---|---|---|---|---|---|---|
| 21 | Battery + | Reverse-battery FET → buck | — | — | — | Power input net, not an MCU signal |
| 04 | `V_BAT_1R` sense | 120k/10k divider (spec §4) | `PTA0` | ADC0_SE0 | Hi-Z, no pull | Free choice; paired with pin 06 on the *other* ADC instance (below) so both battery rails sample simultaneously |
| 06 | `V_BAT_2R` sense | 120k/10k divider | `PTA2` | ADC1_SE0 | Hi-Z, no pull | Paired with 04 for simultaneity — a real S32K148 property (two independent SAR ADCs), not decorative |
| 09 | `SYNCHRONIZATION GROUND` | — | — | — | — | **U6 open.** Function unconfirmed; likely a ground per its own name despite being drawn red. No MCU pin assigned — assigning one would be guessing a signal that may not exist |

### 1.2 Analog sensors

| ECU pin | Signal | Front-end | `PTxx` | Peripheral | Reset pull | Note |
|---|---|---|---|---|---|---|
| 11 | Boost sensor 5V excitation | `5V_SENSOR` distribution | — | — | — | Power net, not an MCU input |
| 41 | Boost pressure | Differential (shared gnd 34) | `PTA1` | ADC0_SE1 | Hi-Z, no pull | |
| 79 | Boost temperature | Differential or NTC — **U2 open, topology TBD** | `PTA3` | ADC1_SE1 | Hi-Z, no pull | One ADC pin serves either candidate front-end in `ntc_frontend.cir`; the pin choice does not depend on U2's answer |
| 34 | Sensor ground (boost+coolant) | Instrumentation-amp reference | — | — | — | Analog ground-plane net, not a GPIO |
| 33 | Coolant temperature | Differential (shared gnd 34) | `PTA6` | ADC0_SE2 | Hi-Z, no pull | |
| 15 | EGR 5V excitation | `5V_SENSOR` distribution | — | — | — | Power net |
| 37 | EGR position | Differential (shared gnd 36) | `PTA15` | ADC1_SE12 | Hi-Z, no pull | |
| 36 | Sensor ground (EGR+oil) | Instrumentation-amp reference | — | — | — | Analog ground-plane net |
| 39 | Oil pressure 5V excitation | `5V_SENSOR` distribution | — | — | — | Power net |
| 80 | Oil pressure | Differential (shared gnd 36) | `PTA7` | ADC0_SE3 | Hi-Z, no pull | |
| 32 | Rail pressure 5V excitation | `5V_SENSOR` distribution | — | — | — | Power net |
| 35 | Rail pressure | Single-ended (dedicated gnd 08) | `PTA16` | ADC1_SE13 | Hi-Z, no pull | |
| 08 | Sensor ground (rail, dedicated) | — | — | — | — | Analog ground-plane net |
| — | `5V_SENSOR` rail monitor | Divider → ADC (spec §4's ratiometric-correction channel) | `PTC14` | ADC0_SE12 | Hi-Z, no pull | No connector pin — internal PCB net, required by the firmware ratiometric-correction scheme spec §4 already specifies |
| — | Onboard barometric sensor | New, per spec §7 deviation #2 | `PTD18` | ADC1_SE16 | Hi-Z, no pull | No connector pin — this is the 8th "sensor input" in memo 05's 14-channel ADC budget |

### 1.3 Speed

| ECU pin | Signal | Front-end | `PTxx` | Peripheral | Reset pull | Note |
|---|---|---|---|---|---|---|
| 52 / 74 | Crank VR High/Low | Differential adaptive-threshold conditioner (`vr_conditioner.cir`) | *(conditioner input, no direct MCU pin)* | — | — | The conditioner's zero-cross comparator already collapses this to one digital edge stream — see next row |
| — | Crank conditioner output | Zero-cross comparator output, ±198 mV hysteresis (`hw/speed_inputs.kicad_sch`) | `PTB2` | FTM1_CH0 (input capture) | Hi-Z, no pull | **Forced in kind, not in pin**: whatever pin is chosen must be FTM/capture-capable; `PTB2` is a free choice among many valid options. FTM configured for both-edge capture, per RM's `CnSC[ELSA:ELSB]` |
| 30 | Crank sensor ground | Shield termination, ECU end | — | — | — | Ground/shield net |
| 45 | Cam Hall 5V excitation | `5V_SENSOR` distribution | — | — | — | Power net |
| 46 | Cam frequency I/P | 10 k pull-up to `5V_SENSOR` **+ 16 k to ground**, 22 nF, 3.3 V zener (`cam_frontend.cir`) | `PTB3` | FTM1_CH1 (input capture) | Hi-Z, no pull | **CORRECTED 20 Sep 2026** — spec §4's literal "pull-up to `5V_SENSOR`" overvoltages the pad. See §4 |
| 44 | Cam sensor ground | — | — | — | — | Ground net |

### 1.4 Discrete inputs

| ECU pin | Signal | Front-end | `PTxx` | Peripheral | Reset pull | Note |
|---|---|---|---|---|---|---|
| 43 | Coolant switch | Pull-up + RC debounce | `PTD5` | GPIO input | Hi-Z, no pull | |
| 23 | Droop switch | Pull-up + RC debounce | `PTD7` | GPIO input | Hi-Z, no pull | |
| 01 | `G_G_B AT1` | — | — | — | — | **Unresolved per spec §4's own note** — memo 03 suspects this is a power ground, not a switch-return leg. No MCU pin assigned either way: if it's a ground it needs none, and if it is a signal, guessing which one would violate this project's own "nothing guessed into copper" rule |
| 02 | `G_G_B AT2` | — | — | — | — | Same as 01 |
| 20 | Audio abort (active-high) | 47k/68k bias + 3.0V zener clamp | `PTD11` | GPIO input | Hi-Z, no pull | |
| 24 | Override SS (active-high) | Same clamp front-end | `PTD12` | GPIO input | Hi-Z, no pull | |
| 71 | Ignition (active-high) | Same clamp front-end | `PTD16` | GPIO input | Hi-Z, no pull | |
| — | Trip-module sense (new) | `trip_module_sense.cir` — 47k/68k/220nF/3.0 V, same chain as the rows above | `PTB0` | **ADC0_SE4** | Hi-Z, no pull | **CORRECTED 20 Sep 2026, during schematic capture — was `PTD6` GPIO.** See below |

**CORRECTION, 20 September 2026 — the trip sense needs an ADC, not a GPIO.**

This row originally read `PTD6`, GPIO input, "placeholder pin only — front-end is
undesigned". The front-end has since been designed, and designing it invalidated the pin
class. `sim/blocks/trip_module_sense.cir` builds a **three-state supervised loop** and
checks all three bands with real margin:

| State | Node voltage, swept 6–40 V |
|---|---|
| healthy — contact closed, bleed resistor shorted | 2.863 – 2.954 V |
| tripped — contact open, 1.2 MΩ bleed in circuit | 0.310 – 2.068 V |
| wire fault — nothing reaches the divider | 0.000 V |

**A GPIO reads two states.** It separates healthy from not-healthy and nothing else,
which throws away exactly the distinction the bleed resistor exists to create. A
supervised loop that cannot tell a trip from a cut wire is an unsupervised loop with
extra parts in it.

`PTD6` is not ADC-capable — checked against `refs/s32k148-144lqfp-altfn.csv`, and neither
is any other pin in §1.4, which is correct for the channels there and wrong for this one.
The channel moves to **`PTB0` (ADC0_SE4 / ADC1_SE14)**: free, bonded out on the 144-LQFP
at pin 78, `PE=0 / PS=0` at reset. `PTD6` returns to the spare pool.

Committed count is unchanged at 39; the spare GPIO count is unchanged at 89.

**Updated 21 September 2026:** committed count is now **41** and the spare GPIO count
**87**, after `PTB5` and `PTA17` were added for the battery-side high switches (§1.5).
**Updated 22 September 2026:** **42** committed, **86** spare, after `PTB10` was added
for the EGR bridge's shared shutdown (§1.5).

---

### 1.5 Outputs — the six gate pins are in §2

| ECU pin | Signal | Front-end | `PTxx` | Peripheral | Reset pull | Note |
|---|---|---|---|---|---|---|
| 03 | Injector HS bank A (cyl 1+3) | **Boost-rail** high-side switch, peak phase | `PTC0` | FTM0_CH0 | Hi-Z, no pull | See §2 |
| 05 | Injector HS bank B (cyl 2) | **Boost-rail** high-side switch, peak phase | `PTC1` | FTM0_CH1 | Hi-Z, no pull | See §2 |
| 03 | Injector HS bank A — **battery side** | **Battery** high-side switch, hold chopping | `PTB5` | FTM0_CH5 | Hi-Z, no pull | **ADDED 21 Sep 2026** — see below |
| 05 | Injector HS bank B — **battery side** | **Battery** high-side switch, hold chopping | `PTA17` | FTM0_CH6 | Hi-Z, no pull | **ADDED 21 Sep 2026** — see below |
| 73 | Injector LS cyl 1 | Current-controlled low-side | `PTC2` | FTM0_CH2 | Hi-Z, no pull | See §2 |
| 07 | Injector LS cyl 3 | Current-controlled low-side | `PTC3` | FTM0_CH3 | Hi-Z, no pull | See §2 |
| 29 | Injector LS cyl 2 | Current-controlled low-side | `PTB4` | FTM0_CH4 | Hi-Z, no pull | See §2 |
| 88 | Fuel metering PWM | High-current low-side + current sense | `PTD10` | FTM2_CH0 | Hi-Z, no pull | See §2 |
| 59 | EGR High (bridge IN1) | H-bridge | `PTB8` | FTM3_CH0 | Hi-Z, no pull | Not one of the six — see §2's scope note |
| 81 | EGR Low (bridge IN2) | H-bridge | `PTB9` | FTM3_CH1 | Hi-Z, no pull | Not one of the six |
| — | EGR bridge enable (shared SD̄) | Pulled LOW on the sheet — **coast** at reset | `PTB10` | FTM3_CH2 | Hi-Z, no pull | **ADDED 22 Sep 2026.** The bridge is two AUIRS2184S, one input per leg; coast needs both shutdowns asserted, and they default asserted by copper. Same timer as IN1/IN2 |
| 50 | Main relay | Low-side FET + flyback | `PTD13` | GPIO output | Hi-Z, no pull | |
| 69 | Buzzer relay | Low-side FET + flyback | `PTD14` | GPIO output | Hi-Z, no pull | |

**ADDED 21 September 2026 — a peak-and-hold stage needs two high-side switches per bank,
and this map had allocated one.**

The row above originally read "Boosted high-side switch," one pin per bank, with hold
current arriving from the battery through a diode-OR. Drawing the sheet accepted that;
**choosing a gate driver for it did not.** Three things are wrong with a diode:

1. **It cannot regulate hold.** With the battery on a diode the only switch in the loop
   is the low side, and when the low side opens the coil's current goes to the
   recirculation diode and into the 100 V boost rail — a *fast* decay against −87 V,
   which is turn-off, not chopping. Hold needs a slow freewheel around the coil.
2. **It leaves connector pins 03 and 05 permanently live.** A diode from the battery to
   a connector pin means a harness short to ground draws current whenever the battery is
   connected, with no switch anywhere to stop it.
3. **The gate driver cannot be bootstrapped.** A bootstrap capacitor charges when the
   switch node goes low. A battery diode holds that node at 12.8 V, so it never does.

What replaces it is what `injector_turnoff.cir` already models: two high-side switches
onto a common bank node, plus `D_fw` from **ground** to that node — the freewheel path
whose necessity that block's header spends a paragraph on. Hold chopping then happens on
the high side, the node swings to −0.7 V every off-time, and the bootstrap charges.

**Both new pins are FTM0 channels**, like the five injector pins already allocated, so
the whole stage stays on one timer and its edges stay phase-locked to each other.
`PTB5` is a GPIO-HD (high-drive) pad; both are `PE = 0, PS = 0` at reset, confirmed
against the same IO Signal Table §2 uses — so they inherit §2's finding exactly.

### 1.6 Current-sense channels (internal, no connector pin)

Memo 05's ADC budget names "4 current-sense returns from the injector, metering and EGR
drivers." These are shunts on the driver stage, not connector signals, so they have no
ECU pin — but they need an MCU `PTxx` and are placed here for completeness.

| Associated signal | `PTxx` | Peripheral | Reset pull | Note |
|---|---|---|---|---|
| Injector bank A current sense (pins 03/73) | `PTC15` | ADC0_SE13 | Hi-Z, no pull | **INFERRED split**: assumes one shunt per high-side bank, not per low-side cylinder. Memo 12 says "per channel or per bank" without deciding; this map picks per-bank because that is what makes the 4-channel figure in memo 05/§5 add up (2 banks + metering + EGR = 4). Three-channel per-cylinder sensing would need a 5th ADC pin — trivially available, but not what the existing budget assumes. **SETTLED 21 Sep 2026, when the injector sheet was drawn** — `hw/injector.kicad_sch` puts the shunts **low-side and ground-referenced**, one per bank, in the shared source return. Cylinders 1 and 3 fire 240 crank degrees apart and never overlap, so one shunt reads whichever is conducting — the same fact that lets the high side be bank-shared. A high-side shunt would read the same current and need an amplifier whose common-mode range reaches 100 V. Per-bank confirmed, 5 mΩ. |
| Injector bank B current sense (pin 05, low side 29) | `PTD19` | ADC1_SE17 | Hi-Z, no pull | Paired with bank A on the other ADC instance for simultaneous sampling |
| Metering unit current sense (pin 88) | `PTC16` | ADC0_SE14 | Hi-Z, no pull | |
| EGR bridge current sense (pins 59/81) | `PTD22` | ADC1_SE18 | Hi-Z, no pull | |

### 1.7 CAN

Both channels are real (spec §2.5). The S32K148 has three FlexCAN instances; this design
needs two, exactly as memo 05 notes ("1 spare instance"). CAN0/CAN1 are used, CAN2 is
left spare — a free choice among three equally-valid instances, not a forced one.

| ECU pin | Signal | `PTxx` | Peripheral | Reset pull | Note |
|---|---|---|---|---|---|
| 55 | CAN channel 1, H | *(via transceiver)* | — | — | Bus-side signal; transceiver CANH pin, not an MCU pin |
| 77 | CAN channel 1, L | *(via transceiver)* | — | — | Transceiver CANL pin |
| — | CAN channel 1, MCU side | `PTE5` | FlexCAN0_TX | Hi-Z, no pull | To transceiver 1 TXD |
| — | CAN channel 1, MCU side | `PTE4` | FlexCAN0_RX | Hi-Z, no pull | From transceiver 1 RXD |
| 87 | CAN channel 2, H | *(via transceiver)* | — | — | Transceiver 2 CANH |
| 86 | CAN channel 2, L | *(via transceiver)* | — | — | Transceiver 2 CANL |
| — | CAN channel 2, MCU side | `PTC7` | FlexCAN1_TX | Hi-Z, no pull | To transceiver 2 TXD |
| — | CAN channel 2, MCU side | `PTC6` | FlexCAN1_RX | Hi-Z, no pull | From transceiver 2 RXD |
| — | CAN channel 3 (spare) | *(unassigned)* | FlexCAN2 | — | Instance exists, no pins committed |

### 1.8 SPI / supervisor interface

**No SPI-dependent part is currently decided anywhere in the repo.** The handbook's
speculative peripheral table (`docs/handbook/sensors.html`) once counted "1 SPI channel
for the injector driver," but memo 12 (19 Sep 2026) decided discrete FETs with a
conventional gate-driver IC for the injectors and a smart low-side switch for the
metering unit — neither is a microcode/SPI-programmed part in memo 12's recommendation.
So: **no SPI pin is committed in this map.** `LPSPI1` (`PTB14` SCK / `PTB15` SIN /
`PTB16` SOUT / `PTB17` PCS3) is entirely free and is the natural reservation if a future
EEPROM, external diagnostic port, or SPI-configured driver IC is added — but forcing a
pin assignment ahead of a part choice would be exactly the kind of guess this project's
own discipline rules out.

**The supervisor interface is not a data bus at all — that is the point of it.**
`sim/blocks/supervisor.cir` and `docs/research/11-supervisor-and-fail-safe-outputs.md`
specify a TPS3850-class windowed supervisor whose `RESET` output drives the S32K148's
own `RESET_b` pin **and**, through one inverting stage, a dedicated kill transistor at
each of the six gate nodes — entirely in analog/discrete hardware, with no MCU
involvement in that path by design (that is what lets it protect against a *hung* MCU).

**CORRECTED 20 Sep 2026, during schematic capture.** This section previously said "the
only MCU pin in this interface is `RESET_b`", and that was wrong in a way that mattered:
the *kill* path needs no MCU pin, but the **watchdog** does. A window watchdog is not a
passive monitor — the MCU has to present a falling edge on `WDI` inside the window, every
window, or the part asserts and resets the board on a timer. A supervisor topology with
no pin to kick it is a supervisor that guarantees a reset loop.

Two pins are therefore added here, both taken from the 91 spare GPIO the map leaves free,
both `GPIO-HD`, both `PE=0 / PS=0` at reset (confirmed from the same embedded IO Signal
Table as every other row in this document):

| Signal | `PTxx` | Package pin | Peripheral | Reset pull | Note |
|---|---|---|---|---|---|
| `RESET_b` | `PTA5` | 141 | dedicated | **weak pull-up** | **Forced — this is the only `RESET_b` pin on the part.** Dedicated function, not muxed. Reset default per RM Table 4-3: weak pull-up enabled (the one deliberate exception among the pins this document touches) |
| `WDT_KICK` | `PTE0` | 138 | GPIO output | Hi-Z, no pull | MCU → TPS3850 `WDI`. Free choice of pin; what is *not* free is that some pin must do this |
| `WDT_FAULT` | `PTE1` | 137 | GPIO input | Hi-Z, no pull | TPS3850 `WDO` → MCU, so firmware can tell a watchdog timeout from a rail excursion. `WDO` asserts only while `RESET` is high, which is what makes the two distinguishable |

That takes the committed count from 37 signals to **39**, and the spare GPIO from 91 to
**89**.

**The supervisor part is also now chosen**, which §1.8 previously left as a class:
**TPS3850G33** (`TPS3850G33DRCT`, VSON-10). The variant matters and the reasoning is in
`hw/gen_symbols.py` beside the symbol — briefly, the datasheet's own nomenclature table
gives `G` = thresholds at ±4 % of nominal and `H` = ±7 %, and with the part's ±0.8 %
accuracy that puts G33's worst-case undervoltage trip at **3.143 V** against H33's
**3.044 V**. The supervisor has to assert *before* the S32K148's own LVD (3.0 V maximum),
so G33 clears it by 143 mV and H33 by 44 mV — close enough that the two could fire in
either order, and a supervisor that might lose the race to the thing it supervises is not
doing its job. The cost is a tighter window the 3V3 rail has to live inside
(3.143–3.459 V), which is a constraint this map now places on the rails design.

---

## 2. The gate pins and their reset behaviour — six, now eight

Spec §4's binding requirement (added 18 Sep 2026) says every driver gate on pins **88,
73/07/29, 03/05** must be held off by hardware during reset, because S32K148 GPIOs are
high-impedance out of reset. The requirement explicitly left its own per-pin detail open:

> "the physical `PTxx` assignment for pins 88, 73/07/29 and 03/05 is a phase-2 task
> (§5), so the per-pin reset pull defaults cannot yet be looked up."

**That is now answered, pin by pin, from the manufacturer's own IO Signal Table (not
inferred):**

| ECU pin | `PTxx` | `PE` (pull enable) | `PS` (pull select) | Reset state |
|---|---|---|---|---|
| 88 | `PTD10` | 0 | 0 | Disabled, high-impedance |
| 73 | `PTC2` | 0 | 0 | Disabled, high-impedance |
| 07 | `PTC3` | 0 | 0 | Disabled, high-impedance |
| 29 | `PTB4` | 0 | 0 | Disabled, high-impedance |
| 03 | `PTC0` | 0 | 0 | Disabled, high-impedance |
| 05 | `PTC1` | 0 | 0 | Disabled, high-impedance |
| 03 (battery side) | `PTB5` | 0 | 0 | Disabled, high-impedance — **added 21 Sep 2026** |
| 05 (battery side) | `PTA17` | 0 | 0 | Disabled, high-impedance — **added 21 Sep 2026** |

**CONFIRMED** against both the Reference Manual's own prose (§4.4, Table 4-3: "Others:
Disabled — High impedance — `ibe=0, obe=0, pue=0, pus=0`") and the per-pin `PE`/`PS`/
`Reset` fields in the embedded `S32K148_IO_Signal_Description_Input_Multiplexing.xlsx`,
read directly for each of these six pins.

**The two added on 21 September 2026 read the same way**, from the same table — and
they matter differently, because they are *high-side* gates. `hw/injector.kicad_sch`
found that a ground-referenced kill clamp cannot service a high-side gate at all: the
source swings to the boost rail, so a pulldown to ground would hold `Vgs` at minus the
bank voltage and a kill FET referenced to ground cannot short a gate floating 100 V up.
Those four gates get 470 Ω across **gate and source**, and the kill path moves into the
driver's own shutdown input. Their reset state is still worth recording, and it is still
high-impedance.

**None of the six defaults to a pull that works against the fail-safe requirement —
and none defaults to a pull that helps it either. There is no pull at all.** The only
four pins on the entire part with any reset-time pull are `PTA4`/`PTC4`/`PTC5` (JTAG)
and `PTA5` (`RESET_b`) — none of which are used for gate duty. So the exposure spec §4
and memo 11 already reasoned about from first principles (a floating gate, brought up
by leakage or Miller coupling, with nothing internal to the MCU resisting it) is **exactly
the confirmed condition for all six pins**, not a worst-case assumption that turned out
pessimistic or optimistic. This closes the open item cleanly: the hardware kill-clamp
`supervisor.cir` already validated does not change, because it was designed to not
depend on this answer, and the answer it did not depend on turned out to match the
design's own worst case precisely.

**Scope note on EGR (pins 59/81).** Spec §4's fail-safe list names only the six pins
above — not the EGR bridge. A concurrently-updated file, `sim/blocks/egr_hbridge.cir`,
argues EGR's own safe state is different in kind (coast, not off, so a spring return can
close the valve) and is drafting its own gate-kill treatment. That file is outside this
task's scope and was not modified here; it is noted so the two documents are not read as
disagreeing by omission.

---

## 3. Datasheet numbers reconfirmed, not just cited

Spec §4 and memo 11 state the S32K148's brownout thresholds as VLVR 2.50–2.7 V, VLVD
2.8–3.0 V, and a 2.97 V PLL-engaged correctness-guarantee floor. Re-read directly from
the Rev. 15 datasheet's own electrical characteristics tables this session (not taken on
trust from the earlier memo):

- `VLVR` (LVR falling threshold, RUN/HSRUN/STOP): **2.50 / 2.58 / 2.7 V** (min/typ/max)
- `VLVD` (falling low-voltage detect threshold): **2.8 / 2.875 / 3.0 V**
- "S32K148 will operate from 2.7 V when executing from internal FIRC. When the PLL is
  engaged S32K148 is guaranteed to operate from **2.97 V**." — quoted directly, twice, at
  different points in the datasheet (electrical characteristics footnote and I/O
  operating-voltage table, both consistent).

**CONFIRMED, exact match to spec/memo 11's figures.** No arithmetic correction needed
here — recorded because the task asked for datasheet numbers to be checked, not carried
forward on trust a second time.

---

## 4. What did not fit, and what is INFERRED

**Cam signal front-end (pin 46) — a finding, not a fix.** Spec §4 describes pin 46's
front-end as "Pull-up to `5V_SENSOR` → timer capture," i.e. the Hall sensor's open-drain
output pulled directly to the 5 V sensor rail, into an MCU timer-capture pin. Read
literally, that puts a 5 V logic swing on a 3.3 V-rail MCU pin — over the S32K148's
absolute maximum (`VDD + 0.3 V`, roughly 3.6 V at `VDD = 3.3 V`, per the datasheet's own
operating-voltage figures in §3 above). **No `sim/blocks/*.cir` file simulates a cam
front-end at all** (the built-block list in `docs/status.md` §1.3 has `vr_conditioner.cir`
for crank; there is no cam equivalent) — so this was never checked, and the pin map
surfaces it rather than papering over it with a pin choice. `PTB3` is assigned as the
*capture pin*, but the front-end feeding it needs a level clamp or divider before the
pad, matching the discipline already applied to pins 04/06 (battery sense) and 20/24/71
(discrete inputs). **This should become a `sim/blocks/cam_frontend.cir`-class check
before the cam sheet is drawn**, not solved here.

**RESOLVED 20 September 2026 — the check was written and the sheet now carries the fix.**
`sim/blocks/cam_frontend.cir` exists and runs in the suite, and
`hw/speed_inputs.kicad_sch` draws the front-end it validates: the 10 k pull-up to
`5V_SENSOR` stays (the open-collector sensor needs it), and a 16 k to ground turns it
into the same 10 k/16 k divider the ratiometric sensor channels already use — 5.00 V
becomes 3.077 V, and 4.50 V (`sensor_rail.cir`'s own fault floor for a healthy group)
becomes 2.769 V, both inside `[2.31 V logic-high floor, 3.6 V Vih abs-max]`. It costs one
resistor. The §1.3 row for pin 46 is updated accordingly.

**Injector current-sense split (§1.6) is INFERRED, not confirmed.** Memo 12 leaves
"per channel or per bank" open; this map assumes per-bank (2 channels) because that is
the only split consistent with memo 05's stated "4 current-sense returns" total once
metering (1) and EGR (1) are subtracted. A per-cylinder scheme (3 channels) is equally
buildable and would just need one more free ADC1 pin — **settle when the injector driver
sheet's shunt placement is actually drawn.**

**RM revision currency (§0) is INFERRED.** Rev. 13 (04/2020) was the newest S32K148 IO
signal table located; the datasheet elsewhere cited is Rev. 15 (2026). No pin-mux errata
were found in either document's revision history, but a newer Reference Manual was not
checked because none was found. Low risk (pinout is a silicon property), not zero.

**Crystal reservation (`PTB6`/`PTB7`) is an open question, not a finding.** Nothing in
the repo states whether this design runs off the internal FIRC or an external crystal.
Neither pin is used by any signal in this map, so there is no conflict either way — but
if CAN bit-timing accuracy (a real automotive concern, not evaluated here) ends up
requiring a crystal reference, those two pins should be reserved before anything else
claims them.

**SPI (§1.8)**: no pin committed, for the reason stated there — no SPI-dependent part is
decided. `LPSPI1` is free and is the natural landing spot.

---

## 5. Open questions

1. ~~**Cam front-end overvoltage (§4)**~~ — **CLOSED 20 September 2026.**
   `cam_frontend.cir` was written, the divider it validates is drawn on
   `hw/speed_inputs.kicad_sch`, and the §1.3 row now states the real front-end rather
   than spec §4's literal one.
2. ~~**Injector current-sense placement (§1.6)**~~ — **CLOSED 21 September 2026.**
   Per-bank, low-side, ground-referenced, 5 mΩ. Drawn on `hw/injector.kicad_sch`.
3. **Crystal vs FIRC (§4)** — decides whether `PTB6`/`PTB7` are reserved.
4. **U6 (pin 09) and pins 01/02** — still open per spec §8/§4; no MCU pin assigned,
   consistent with "nothing guessed into copper."
5. **The 50 unconfirmed OEM connector pins (spec §8)** — cannot be placed on `PTxx`
   without a function to place. 91 of the 128 GPIO-capable pins on the 144-pin package
   remain uncommitted, which is comfortable headroom once they are known.
   **Sharpened 21 September 2026, by drawing the connector sheet: two of those 50 are
   not headroom, they are blockers.** The wiring diagram shows pin 21 as the battery
   positive feed and shows *no battery negative anywhere* — its own scope note says it
   omits "power grounds, unused pins and internal-only pins" — so `GND`, the net every
   other sheet returns to and the one the injector low sides put 18 A into, has no pin.
   And `TRIP_LOOP`, the supervised trip-module loop `trip_module_sense.cir` designs, is
   a **new** signal that is not on the OEM diagram at all, so it needs one of the 50 as
   well. Neither can be chosen: a wrong ground pin is not a rework, it is a harness that
   has to be remade. Both wait on the connector part number and the OEM pin list, or on
   continuity measurement at the machine.
6. **RM revision currency (§0)** — worth a diff against a newer Reference Manual if one
   surfaces before layout.
