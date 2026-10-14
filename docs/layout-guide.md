# PCB Layout Guide

**Written for:** the layout engineer who routes `hw/ecu25kva.kicad_pcb` by hand.

**Date:** 14 October 2026.

**What you get:**
- a board with all 379 parts placed by block
- every net
- every net class and rule

**What you do:** fine placement and routing. This guide says what matters in each block and why. Where it quotes a number, the source is named beside it. A simulation file is `sim/blocks/<name>.cir`. A sheet is the matching `hw/gen_sheet_<name>.py`.

---

## 1. What is ready, and what is a placeholder

| Item | State |
|---|---|
| 379 footprints, 373 nets | From the schematic, exactly. `hw/check_pcb.py` proves it |
| Net classes, widths, clearances | In `ecu25kva.kicad_pro`. Generated from `hw/pcb_rules.py` |
| Placement | By block (each schematic sheet is a KiCad group), shelf-packed, no overlaps. Fine placement is yours |
| **Board outline** | **PLACEHOLDER:** 180 × 130 mm rectangle |
| **Mounting holes** | **PLACEHOLDER:** 4 × M3 at the corners |
| **Housing contact band** | **PLACEHOLDER:** top 25 mm (User.Comments layer) |
| **J1001, the 94-way header** | **PLACEHOLDER:** pin numbers right, geometry assumed (2.5 mm pitch) |
| **D806** | Footprint assumed (SMA). The part waits on the trip-loop pin |

> **No board is ordered until J1001 and the outline are measured** from the old ECU (inspection brief, Group 6). Both placeholders say "DO NOT FABRICATE" on the silkscreen. When the measurements arrive, `HOUSING` and `REGIONS` in `pcb_rules.py` change. If you have not started routing, re-run the generator. If you have, move the outline and J1001 by hand.

**Why 180 × 130 and not the spec's 160 × 120:** the parts need about 15,300 mm² packed on one side. At 160 × 120, the power-input block alone did not fit beside J1001. If the old housing's board turns out smaller, parts go on both sides. That is your call once the outline is known.

## 2. Tools

- **KiCad 10 is required.** The board file is KiCad 10 format; the schematic stays KiCad 7 format.
- **Rebuild the board:** `$KP hw/gen_pcb.py`, where `KP` is KiCad's own Python (README). On a routed board it rewrites **only the rules** and leaves your copper alone; `--force` throws the routing away.
- **Check the board:** `.venv/bin/python hw/check_pcb.py`. It checks:
  - footprints, nets and classes
  - widths
  - every DRC error (clearance, courtyards, edge and hole clearance, shorts, mask bridges)
  - schematic parity: each pad's net, the symbol fields, the footprints. The board's footprints are linked to their symbols, so **Update PCB from Schematic** works once routing has started

  Unrouted connections are counted, not failed.
- **Custom rule** (`ecu25kva.kicad_dru`): pads inside one footprint are exempt from net-class clearance, because that spacing is the maker's land pattern. Every class still applies to the copper you add.

## 3. Stack-up and classes

**Board:** 4 layers, 1.6 mm FR-4, **Tg ≥ 170 °C** (engine bay).

| Layer | Copper | Use |
|---|---|---|
| L1 top | 2 oz | Parts, power copper, short signals |
| L2 | 1 oz | **Solid ground plane.** No splits, no slots, unbroken under the switching stages and the MCU |
| L3 | 1 oz | Power distribution and slow signals |
| L4 bottom | 2 oz | Power copper; heat spreading into the housing contact areas |

**Widths** are computed (IPC-2221, 20 °C rise) for the outer 2 oz layers. An inner 1 oz layer needs much more: 18 A on an inner layer is over 5× the outer width. **So route high current on L1/L4 or as pours, not on L3.**

| Class | What | Current | Width (outer) | Clearance |
|---|---|---|---|---|
| `PWR_HI` | injector feed: pin 4 → VBAT_INJ, the hold-path diodes | 18 A | 5.35 mm | 0.6 mm |
| `RTN` | ground, and the injector shunt tops (~0 V, on fine-pitch amplifier pins) | 18 A | 5.35 mm (pour) | 0.15 mm |
| `PWR_LOOM` | pin 6 → VBAT_EGR → EGR bridge and its shunt. Protected only by the 10 A loom fuse, so sized for 135 % of it (ISO 8820-3) | 13.5 A | 3.6 mm | 0.3 mm |
| `HV100` | boost rail, bank nodes (pins 3, 5), low-side drains (pins 73, 29, 7), boost switch node | 18 A, up to ~116 V | 5.35 mm | 0.6 mm |
| `HV100_SIG` | injector high-side gates and bootstraps, divider midpoints, PZTA42 collectors, VDD_REF; the EGR high-side gates and bootstraps (VBAT + 12 V, ~40 V) | small, 31–116 V | 0.2 mm | 0.6 mm |
| `PWR` | pin 21 path behind the 5 A fuse F101, VBAT_PROT, metering valve, buck switch node, 12V_GATE | 6.4 A | 1.3 mm | 0.3 mm |
| `PWR_LV` | 3V3_MCU, 5V_MAIN, the boost controller's VDD and current sense: low voltage on 0.5 mm-pitch pins | 6.4 A | 1.3 mm | 0.15 mm |
| `CAN` | CAN1/CAN2 H and L | — | 0.2 mm, gap 0.25 (set from the fab's stack-up) | 0.2 mm |
| `ANALOG` | sensor inputs, clamps, ADC nets, VR pair | — | 0.25 mm | 0.2 mm |
| `Default` | logic | — | 0.2 mm | 0.15 mm |

**The 0.3 mm on battery power is a judgement, not a table row.** IPC-2221B B2 gives 0.1 mm up to 30 V and 0.6 mm from 31 V; 0.3 mm adds margin over the 24 V nominal for clamped transients.

**Peak versus average:** the 18 A is the injector peak phase, which is short. The class width is the conservative default. Where a pad forces you to neck down, keep the neck short and add copper on the other outer layer.

## 4. The ground: one plane, one join

- **L2 is one solid plane.** Power and signal returns are separated by **placement and routing**, not by cutting the plane.
- **The single point:** all high-current returns meet the board ground **at the battery-ground pins of J1001, and only there**. Those returns are:
  - the injector shunts R428 and R429
  - the boost shunt R402
  - the EGR shunt R507
  - the metering shunt R501
  - the TVS diodes D101, D105 and D108
  - the negative clamp Q102
  - the freewheel diodes D409 and D411
  - the reservoir C420

  Run them on L1/L4 copper to that point, then via into L2 there. Don't drop them into L2 next to the part.
- **Which pins are battery ground: open.** The schematic has J1001 pins 1 and 2 (`G_G_B_AT1/2`) **unconnected**: the OEM wiring diagram shows no battery negative. Pins 1–2 are the assumption (`HOUSING["ground_pins"]`). The continuity check (inspection brief 5.1) settles it. **Leave room for a wide GND connection to two of the six large pins.**
- **The sensor grounds** (SGND pins 8, 30 and 44, tied to GND on the schematic) join the plane **at their own front ends**, away from the power join.
- **SGND_34 and SGND_36 are not ground.** They go to the INA592 difference amplifiers' negative inputs, which is the whole point of `sensor_differential.cir`. Route each with its signal, as a pair.

## 5. Block by block

### Injector stage (`injector`, top band)

**The circuit:**
- Boost converter: L401, Q401, D401, shunt R402, controller U401 (TPS40210).
- 100 V reservoir: C401 in series with C420, balanced.
- Two high sides per bank:
  - Q408/Q410 from the boost rail (peak)
  - Q409/Q411 from the battery via D408/D410 (hold)
- Freewheel diodes D409/D411, ground → bank node.
- Low sides Q412, Q414, Q416.
- Turn-off diodes D412–D414: low side → boost rail.
- Shared bank shunts R428 (cylinders 1 and 3) and R429 (cylinder 2).

**Loops to keep tight** (`injector_boost.cir`, `injector_turnoff.cir`, `boost_converter.cir`):

1. **The turn-off loop, the most important on the board.** Each turn-off returns about **32 mJ** of coil energy (18 A in 200 µH, `injector_turnoff.cir`). The path is:
   - low-side drain (pins 73, 29, 7)
   - turn-off diode D412/D413/D414
   - BOOST_100V
   - C401/C420
   - ground
   - shunt
   - low-side source

   Keep the diodes and the reservoir within a few mm of each other, on a wide pour.
2. **The boost switch loop:** Q401 drain → D401 → C401/C420 → R402 → Q401 source. The switch node SW_BOOST is the noisiest copper on the board: make it small, and keep it away from the sensor and VR inputs.
3. **The peak path:** BOOST_100V → Q408/Q410 → INJ_A_03/INJ_B_05 → J1001 pins 3/5. That carries 18 A at up to 100 V: `HV100`, short and wide.

**Other rules:**
- **Shunts:** R428/R429 sit in the low-side source return. Take the sense lines to U406/U407 as a **Kelvin pair** from the shunt pads, not from the pour.
- **High-side drivers:** U402–U405 with bootstraps C409/C411/C413/C415. Keep each bootstrap capacitor at its driver's VB/VS pins. VS is the bank node, so the bootstrap loop rides at 100 V.
- **Creepage:** the 100 V copper is in `HV100`/`HV100_SIG`, at 0.6 mm (IPC-2221B, external, uncoated, 101–150 V). Don't run Default-class signals between HV pads.
- **L401 inductor:** no vias or sensitive traces underneath.
- **Heat:** the TO-263 FETs (Q408, Q410, Q412, Q414, Q416) and the SMPD diodes D408–D414 are the board's main heat. Put their tabs on large L1 pours, stitched to L4, over the housing contact area.

### Power input (`power_input`, left of J1001)

**The circuit:**
- **Pin 21:** F101 (5 A) → EMI filter L101 / C101–C104 / L102 (`emi_filter.cir`) → TVS D101 → reverse-battery P-FET Q101 → VBAT_PROT. The negative clamp Q102 sits on VBAT_PROT (`negative_pulses.cir`).
- **Pins 4 and 6** (the injector and EGR feeds): TVS D105/D108 → reverse FETs Q103/Q104 → filters L103/L104 → VBAT_INJ / VBAT_EGR. Each has bulk HXC capacitors and two R-C dampers (`feed_emi.cir`).

**Rules:**
- Place it in **the stage order**, input to output, with the pin side nearest J1001. A filter only works if its input and output copper don't couple around it.
- **Keep the dampers** (R110–R113 with C113/C114/C117/C118) **next to the bulk capacitors**. `feed_emi.cir` needs them for stability against the boost converter's negative input resistance; they are not optional EMI decoration.
- **The common-mode choke** that spec §6 calls for **is not on the schematic.** `emi_filter.cir` says it can only be modelled once a layout gives it a chassis return. Leave space at pin 21's entry for a common-mode choke and its chassis connection. **CISPR 25 Class 5 is the target** (owner, 12 Oct).
- **Q101's gate is passive:** R103 to ground with the zener D102. There is no controller (decisions log §5b), and the same goes for Q103/Q104.
- **Q102, the negative clamp, has a driven gate:** comparator U101 → gate driver U102 (UCC27517A) → Q102. Keep U102 at Q102's gate, with its return taken straight to Q102's source (ground), so the gate loop is small.
- **Heat:** Q103 and Q104 carry the feeds continuously. The sheet note gives Q103 "Tj 117 C at a 105 C board" and Q104 (EGR, 6.4 A stall) "Tj 139 C at a 105 C board, 155 C while cranking". Give both tabs large L1 pours stitched to L4, and put them on the housing contact area if the measured housing allows.

### Rails (`rails`, right)

**The circuit:**
- **Buck:** LM5164 (U201), L201, bootstrap C203, switch node `/rails/SW`.
- **Overvoltage cut-off:** U203 + Q201.
- **Sensor trackers:** U204–U206, TPS7B4253 (DDA package).

**Rules:**
- **Buck loop:** VIN capacitor → U201 → SW → L201 → output capacitor → ground. Keep it small. The datasheet's own layout applies.
- **L201** (WE-PD 1050): **no vias or sensitive traces underneath** (datasheet).
- **U204–U206 thermal pads:** solder-mask-defined, 2.6 × 3.2 mm opening on 2.95 × 4.9 copper (the drawn footprint). TI's optional thermal vias are your call.

### Metering valve and EGR bridge (`metering_egr`, top right, in the contact band)

**The circuit:**
- **Metering valve:** low-side FET Q501 on pin 88's return (`MU_RETURN`), 50 mΩ shunt R501, freewheel D501 to VBAT_PROT (`metering_unit_pwm.cir`).
- **EGR:** discrete H-bridge Q503–Q506, drivers U504/U505, 20 mΩ shunt R507, pins 59/81.

**Rules:**
- Kelvin sense from R501 and R507 to U501 and U503.
- **Bridge loop:** VBAT_EGR → high FET → motor pins → low FET → R507 → ground. Keep it compact, with bulk capacitance at the high-side drains.
- **Heat:** the bridge FETs Q503–Q506 and the metering FET Q501 make heat (the EGR stall is 6.4 A continuous). Keep their tabs over the housing contact band, on pours stitched to L4.

### MCU and supervisor (`mcu`, centre)

**The circuit:**
- S32K148 (U301), 144-LQFP.
- Decoupling.
- Bulk capacitor C313 with its **22 mΩ series resistor R306** (`/mcu/BULK_RTN`).
- Supervisor TPS3850 (U302).
- Debug header J301.

**Rules:**
- **Every decoupling capacitor at its pin**, with the via to L2 at the capacitor pad.
- **R306 is deliberate.** `mcu_pdn.cir`: "a very low-ESR bulk part makes this peak worse, not better." Keep R306 in series with C313. Don't bypass it.
- The quiet zone: no switching copper (SW_BOOST, `/rails/SW`, the bank nodes) under or beside the MCU.

### Sensors (`sensors_analog`, centre right)

**The circuit:**
- Divider, ratiometric, differential (INA592, U601–U605) and NTC front ends.
- Each ends in a 22 nF filter and a 3.3 V clamp at the MCU pin.
- U606 is the barometric pressure sensor (MPXHZ6115A).

**Rules:**
- Route each differential input with its SGND return as a pair, from the connector pin to the amplifier.
- Put the filter capacitor at the MCU pin, not at the connector.
- **U606 needs air:** keep its port clear, and line it up with the housing's vent (the round vent plug on the old housing). Confirm against the housing.

### Speed inputs (`speed_inputs`, centre right)

**The circuit:**
- **Crank VR**, pins 52/74: TVS D701 → resistors → clamps → comparator U701.
- **Cam Hall**, pin 46.

**Rules:**
- **Route the VR pair as a differential pair.** `vr_conditioner.cir`: "common-mode rejection at the input is doing real work against the injector currents flowing nearby." Keep it away from the injector block and SW_BOOST, over unbroken L2.
- At cranking the VR signal can be **under a volt** (`vr_conditioner.cir`), so coupled noise matters most exactly when the engine needs to start.

### CAN (`can`, right of J1001)

**The circuit:** two TCAN1042 transceivers (U901/U902), each with a split termination: R902/R903 + C903, and R905/R906 + C906.

**Rules:**
- **Route H/L as a pair**, matched, with the termination at the transceiver end and the midpoint capacitor to ground with a short via.
- **The common-mode choke** (`can_termination.cir`, like the power input) is not on the schematic. Leave space for one per channel between the connector and the transceiver.

### Discrete I/O (`discrete_io`, right)

**The circuit:** switch inputs, the supervised trip loop (`TRIP_SENSE`), and two relay drivers (Q806/Q807, freewheel D807/D808 to VBAT_PROT).

**Rules:** nothing critical beyond keeping each input's RC filter at the MCU end.

## 6. Test points

**There are no test-point footprints in the schematic yet.** Add them as `TP` symbols on the schematic first, so the board and schematic stay in step. The minimum set:

- **Rails:** VBAT_PROT, VBAT_INJ, VBAT_EGR, 12V_GATE, 5V_MAIN, 3V3_MCU, 5V_SENSOR_A/B/C, BOOST_100V (with a warning label)
- **CAN:** CAN1_H, CAN1_L, CAN2_H, CAN2_L
- **Timing:** CRANK_EDGE, CAM_EDGE
- **Injector current:** ISNS_INJ_A, ISNS_INJ_B (the amplifier outputs), plus a ground next to each

## 7. Before fabrication

Nothing is fabricated until all of these are true:

1. J1001's footprint, position and the outline are **measured** from the old ECU (Group 6) and replace the placeholders.
2. The **battery-ground pins** are confirmed (brief 5.1), and the schematic connects GND to them.
3. D806's part is chosen (trip-loop pin, brief 5.2).
4. The **fab confirms the stack-up**, and the CAN pair width/gap is set from it.
5. `check_pcb.py` passes with **zero** unrouted connections.
