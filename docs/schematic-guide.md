# Circuits, Schematics and the Model

*How the 25 kVA ECU's hardware works, sheet by sheet, and how the Simulink
model drives it. 17 November 2026. The schematics follow each explanation,
plotted from the KiCad files as they stand.*

The ECU is one board with four jobs:

- **survive the genset's electrical supply**;
- **read the engine** through its sensors;
- **decide** in firmware, most of it generated from the Simulink model;
- **drive the actuators**: three injectors, the fuel metering valve and the EGR valve.

Every circuit was checked in simulation first: 28 SPICE blocks in `sim/`,
all passing. The pinout is the Bosch MD1CS162's.

## 1. The board at a glance

```
 BATTERY (pins 04, 06)
   |
   v
 [Power input] --> [Rails] --> 5 V, 3.3 V, sensor 5 V -----------+
   |                                                              |
   +--> [Injector stage] <-- 100 V boost rail                     |
   +--> [Metering valve + EGR bridge]                             v
                                                              +-------+
 SENSORS ----> [Analog front ends] -------------------------> |       | --> CAN: DSE4522,
 CRANK/CAM --> [Speed inputs] ------------------------------> |  MCU  |     service tool
 SWITCHES ---> [Discrete I/O] ------------------------------> |       | --> relays
                                                              |       | --> injectors,
                                                              +-------+     valve, EGR
 supervisor + watchdog: any fault drops every power gate (GATE_KILL)
```

Ten sheets make the production board (`hw/`, NXP S32K148, Bosch 94-pin
connector). The prototype (`prototype/`, STM32G474, screw terminals)
reuses eight of them unchanged and swaps the MCU and connector sheets.
Both boards are 4 layers, 1.6 mm FR-4, Tg ≥ 170 °C.

## 2. From pin to model

Every signal follows the same chain:

```
 connector pin -> front end (a sheet) -> MCU pin -> chip driver
               -> ecu_io field -> core C -> Simulink model
```

The `ecu_io` struct (`firmware/core/ecu.h`) is the one boundary between
hardware and logic. Below it is chip-specific C (`firmware/stm32`); above
it, the same code runs on the PC, in Simulink and on the board. MCU pins
are the prototype's.

**Inputs**

| Signal | Pin | Front end (sheet) | MCU pin | `ecu_io` | Used by |
| --- | --- | --- | --- | --- | --- |
| Coolant temperature | 33 (return 34) | INA592, gain 1/2 (sensors) | PC2, ADC2 | `v_clt` | `ecu_sensors` → J1939 ET1 |
| Oil pressure | 80 (36) | INA592 (sensors) | PC4, ADC2 | `v_oil` | `ecu_sensors` → J1939 EFL/P1 |
| Rail pressure | 35 (08) | 10k/16k ratiometric (sensors) | PC5, ADC2 | `v_rail` | `ecu_sensors` → `ecu_rail` |
| Boost pressure | 41 (34) | INA592 (sensors) | PC0, ADC2 | `v_boost` | `ecu_sensors` |
| EGR position | 37 (36) | INA592 (sensors) | PC3, ADC2 | `v_egr` | `ecu_sensors` → `ecu_egrpos` |
| Sensor 5 V | — | 10k/15k (rails) | PB1, ADC3 | `v_5v` | `ecu_sensors` (ratiometric correction) |
| Battery | 04 | 120k/10k (sensors) | PA0, ADC2 | `v_bat` | `ecu_mucur` (feedforward), fault records |
| Crank, 60−2 VR | 52 / 74 | zero-cross comparator (speed) | PD4, TIM2 capture | `ecu_crank_edge()` | `crank.c` → rpm → `ecu_safety`, `ecu_mode`, `ecu_gov`, `ecu_spdst` |
| Cam, Hall | 46 / 44 | open-collector input (speed) | PD7, TIM2 capture | `ecu_cam_edge()` | `crank.c` (which cylinder) |
| Ignition | 71 | NPN buffer, inverted (discrete) | PC10 | `ignition` | `ecu_mode`, `ecu_safety`, `ecu_relay` |
| Stop switch | 25 | NPN buffer + hardware gate kill (discrete, mcu) | PD10 | `stop_sw` | `ecu_mode` (shutdown) |
| Water in fuel | 21 | NPN buffer (discrete) | PD8 | `wif` | `ecu_wifg` |
| Droop switch | 23 | NPN buffer (discrete) | PE5 | `droop_sw` | `ecu_gov` |
| Boost rail voltage | — | 0.0243 divider (prototype) | PB11, ADC2 | `v_boost_rail` | `ecu_boostg`, `ecu_boostm` |
| Metering valve current | — | 50 mΩ × INA181 gain 20 (metering) | PA6, ADC2 injected | `i_mu` | `ecu_mucur` |
| EGR bridge current | — | 20 mΩ × INA181 gain 20 (metering) | PA7, ADC2 | `i_egr` | `ecu_egrg` |
| Injector current, banks A and B | — | 5 mΩ × INA181 gain 20 (injector) | PA2, PA3, ADC1 | — (chip only) | peak-and-hold in `inj_hw.c` |

**Outputs**

| Actuator | Pins | Driver (sheet) | MCU pin | `ecu_io` | Decided by |
| --- | --- | --- | --- | --- | --- |
| Injectors | 03, 05 (banks), 73, 29, 07 (cylinders) | boost and battery high sides, low sides (injector) | PC6–PC9, PE2, PE3, PF2 | `inj[]` start, duration | `ecu_soi`, `ecu_injdur`; current shape in `inj_logic.c` |
| Fuel metering valve | 88 | low-side FET, PWM (metering) | PE1, TIM20 | `meter_duty` | `ecu_rail` → `ecu_mucur` |
| EGR valve | 59 / 81 | H-bridge (metering) | PA8, PA9 (TIM1), PA10 enable | `egr_duty`, `egr_off` | `ecu_egrpos`, `ecu_egrg` |
| Main relay | 50 | low-side FET + ignition wake (discrete) | PD5 | `main_relay` | `ecu_relay` |
| Boost converter off | — | DIS/EN pin (injector) | PD14 | `boost_dis` | `ecu_boostg` |
| Watchdog kick | — | TPS3850 (mcu) | PC11 | `wdg` | `ecu.c` |
| J1939 to the DSE4522 | 55 / 77 | TCAN1042, 250 kbit/s (can) | FDCAN1 | `can[]` | `ecu_j1939` (data), `j1939.c` (sending) |
| Service link | 87 / 86; USB on the prototype | TCAN1042, 1 Mbit/s (can) | FDCAN2; USB | `can2[]`, `usb_*` | `service.c` (UDS) |

## 3. The logic: what runs when

The MCU runs four things at four priorities. The **TRIGGERS** block in
`ecu25kva.slx` is the model of exactly this.

```
 PRIORITY 0  injection timing + injector current (inj_hw.c: TIM5, ADC1)
             start -> peak 18 A from 100 V -> hold 9-11 A from battery -> end
 PRIORITY 2  every crank tooth (TIM2 capture)
             crank.c: decode 60-2 -> rpm, phase
             -> ecu_safety (overspeed caught on that very tooth)
             -> ecu_soi + ecu_injdur -> next injection's start and length
 PRIORITY 2  every 1 ms (SysTick) = one_ms_task
             read inputs -> ecu_sensors -> ecu_safety -> ecu_mode
             -> ecu_spdst -> ecu_gov -> ecu_railset -> ecu_rail
             -> ecu_mucur -> ecu_egrpos
             -> guards: ecu_boostg, ecu_boostm, ecu_egrg,
                        ecu_wifg, ecu_underg, ecu_relay
             -> write outputs (PWM, relays, watchdog)
             -> J1939 frames (ecu_j1939)
 MAIN LOOP   save the fault memory to flash, USB, resets
```

**The engine states** (`ecu_mode`, Stateflow):

```
 OFF --ignition--> WAIT --first tooth--> CRANK --phased, speed up--> RUN
  ^                                                                  |
  +---- ignition off, engine stopped, then on ---- SHUTDOWN <--------+
                                                   overspeed, lost crank, stop switch,
                                                   ignition off, boost overvoltage
```

**The three control cascades:** an outer loop sets a target, an inner loop
reaches it. This is the 20 kVA set's cascade, adapted (decisions log §23).

| Cascade | Outer loop | Inner loop | Actuator |
| --- | --- | --- | --- |
| Speed | `ecu_spdst` picks idle or 1500 rpm; `ecu_gov` PI → fuel mg | `ecu_injdur`: fuel → injection time | injectors |
| Rail pressure | `ecu_railset` + `ecu_rail` PI → valve current | `ecu_mucur`: current loop on ISNS_MU | metering valve |
| EGR | target table → position | `ecu_egrpos`: PID on pin 37 | EGR bridge |

**Protection in layers:** the firmware trips first (`ecu_safety`,
`ecu_boostg`). Hardware backs it up: a 110 V zener stops the boost
converter, and GATE_KILL drops every gate on a watchdog reset or the stop
switch. Outside the board, a standalone overspeed trip is mandatory,
because the DSE4522 takes its speed from this ECU.

<!-- sheet prod 1 -->

## 4. Sheet by sheet

### 4.1 Power input

**Why it matters.** The genset's 12 V supply is hostile: load dumps,
negative spikes, reverse connection. This sheet is what lets everything
downstream survive.

**How it works.**

- Battery → EMI filter → 5 A fuse.
- An **SMCJ43CA** TVS clamps ISO 7637 pulse 2a at 73.3 V. Its 43 V
  standoff lets a 40 V load dump pass without conducting.
- A **P-channel reverse-battery FET** (SQM120P10, 100 V) needs no
  controller.
- A **negative clamp**: a comparator (TLV3201) and driver (UCC27517A)
  switch an N-FET, so the buck never sees its −0.3 V limit.
- Pins 04 (electronics and injectors) and 06 (EGR) each have their own
  P-FET.

**Proven by:** `reverse_battery`, `transient_clamp`, `load_dump`,
`negative_pulses`, `emi_filter`, `power_path`.

**Model link:** none directly. The battery voltage it delivers is read as
`v_bat`, which `ecu_mucur` uses to feed the metering valve's PWM forward.

<!-- sheet prod 2 -->

### 4.2 Rails

**Why it matters.** Every chip and sensor needs a clean, exact supply. The
3.3 V rail must stay within 3.143–3.459 V, or the supervisor resets the board.

**How it works.**

- An **LM5164** buck (100 V input) makes 5V_MAIN.
- A **TLV76733** LDO makes 3V3_MCU, to 1 %.
- Sensor supplies come from **TPS7B4253** trackers, one per sensor group,
  behind a **TPS48110** cut-off that opens above about 41 V. A shorted
  sensor wire then cannot pull down the MCU's rail.
- A 10k/15k divider reports the sensor 5 V to the MCU.

**Proven by:** `buck_preregulator`, `sensor_rail`, `mcu_pdn` (the
decoupling against the regulator).

**Model link:** `v_5v` → `ecu_sensors`. The sensors are ratiometric, so
each reading is corrected by the measured supply.

<!-- sheet prod 3 -->

### 4.3 MCU, supervisor and the kill path (production: S32K148)

**Why it matters.** This is the brain, and the safety net for when the
brain fails.

**How it works.**

- **S32K148** MCU.
- A **TPS3850** window watchdog must be kicked every 10 ms: not faster,
  not slower. It also supervises the 3.3 V rail.
- On any reset, the **GATE_KILL** net rises and forces every injector,
  metering and EGR gate off, with no help from the MCU.
- The stop switch, pin 25, does the same in hardware.

**Proven by:** `supervisor`, `stop_kill`.

**Model link:** the MCU's timers and interrupts are what **TRIGGERS** in
`ecu25kva.slx` represents. The watchdog kick (`wdg`) comes from `ecu.c`,
and only while the main loop is alive.

<!-- sheet prod 4 -->

### 4.4 Injector stage

**Why it matters.** A common-rail injector opens only at about 18 A.
From 12 V that takes 439 µs; from 100 V, 38 µs. This sheet makes that
100 V and switches it.

**How it works.**

- A **TPS40210** boost converter makes BOOST_100V (99.7 V).
- A **110 V zener** into its DIS/EN pin stops it in hardware at 105–119 V.
  The MCU can also stop it (BOOST_DIS).
- **Two banks:** A serves cylinders 1 and 3 (pin 03), B serves cylinder 2
  (pin 05). Each has a boost high side for the peak and a battery high
  side for the hold, driven by AUIRS2181 drivers.
- Three **low-side FETs** (SQM85N15, 150 V) pick the cylinder: pins 73,
  29, 07.
- At turn-off the coil's energy returns into the boost rail through
  recirculation diodes, so the current dies in about 36 µs.
- 5 mΩ shunts with INA181 amplifiers (gain 20) measure each bank.

**Proven by:** `boost_converter`, `boost_ovp`, `injector_boost`,
`injector_turnoff`.

**Model link:**

- **When and how long:** `ecu_soi` (start angle) and `ecu_injdur`
  (fuel → time), from the governor's fuel.
- **The current shape:** peak 18 A → hold 9–11 A → off, in the chip layer
  (`inj_logic.c`, tested against a coil model).
- **The boost rail** is watched by `ecu_boostg` (trip above 106 V) and
  `ecu_boostm` (warnings).

<!-- sheet prod 5 -->

### 4.5 Metering valve and EGR bridge

**Why it matters.** The metering valve sets how much fuel the pump lets
into the rail, so it sets rail pressure. The EGR valve recirculates
exhaust, for emissions.

**How it works.**

- **Metering (pin 88):** a low-side FET switches the valve coil (about
  10 Ω, 30 mH) at 1 kHz, with a freewheel diode.
- A 50 mΩ shunt and an INA181 measure the coil current. It is sampled in
  the middle of each on-pulse.
- The valve is normally open: more current means less fuel.
- **EGR (pins 59/81):** a discrete H-bridge of four 100 V FETs, with one
  AUIRS2184 per leg, so a leg can never short itself.
- EGR_EN low means **coast**: the safe state, held in copper and on
  GATE_KILL.
- A 20 mΩ shunt measures the stall current, up to 6.4 A.

**Proven by:** `metering_unit_pwm`, `egr_hbridge`, `feed_emi`.

**Model link:** `ecu_rail` (pressure PI) → current command → `ecu_mucur`
(current loop) → PWM. `ecu_egrpos` (position PID) → bridge duty, and
`ecu_egrg` lets the bridge coast on a stall.

<!-- sheet prod 6 -->

### 4.6 Analog sensors

**Why it matters.** Rail pressure closes the fuel loop. Coolant and oil
go to the DSE4522 over J1939. A wrong reading is a wrong engine.

**How it works.**

- **Rail pressure** uses a 10k/16k divider: 0–5 V becomes 0–3.08 V, and
  the reading is ratiometric to the sensor supply.
- **Coolant, oil, boost pressure, boost temperature and EGR position**
  use **INA592 difference amplifiers** (gain 1/2). They measure against
  their own return pins, 34 and 36, so ground noise cancels.
- Battery dividers (120k/10k), the GCU sync input (22k/10k) and an
  onboard barometer complete the sheet.

**Proven by:** `sensor_ratiometric`, `sensor_differential`,
`ntc_frontend`, `battery_sense`.

**Model link:** everything goes to `ecu_sensors`. It applies the
end-of-line trims, converts to °C, kPa and bar, and flags an open or
short after 100 ms (FMI 3 or 4).

<!-- sheet prod 7 -->

### 4.7 Speed inputs

**Why it matters.** Engine speed and position time everything:
injection, governing, overspeed. With no clean crank signal there is no
engine.

**How it works.**

- **Crank (pins 52/74):** a variable-reluctance sensor on a 60−2 wheel.
  It gives about 2 V while cranking and 20 V running.
- A **zero-cross comparator** (TLV3201) with hysteresis gives clean edges
  at both. A fixed threshold would miss every cranking tooth.
- **Cam (pins 46/44):** a Hall sensor's open-collector output, clamped
  for the 3.3 V MCU.

**Proven by:** `vr_conditioner`, `cam_frontend`.

**Model link:** `crank.c` (hand-written, because it is event-driven)
turns the edges into rpm and phase. That rpm feeds `ecu_safety`,
`ecu_mode`, `ecu_gov`, `ecu_spdst` and `ecu_underg`. In `ecu25kva.slx`
the plant's cylinder events stand in for it (`cyl_event_isr`).

<!-- sheet prod 8 -->

### 4.8 Discrete inputs and relays

**Why it matters.** The ignition, the stop switch and water-in-fuel are
the operator's and the panel's commands. The main relay is the board's
own power supply.

**How it works.**

- **Inputs** use NPN buffers (PMBT3904) with a 4.7 µF debounce. The pad
  never leaves 0–3.3 V, whatever the harness does.
- The logic is **inverted**: pad low means input active.
- **Relay drivers** are 100 V FETs with flyback protection.
- Pin 71 closes the main relay **in hardware**, through a wake FET, even
  with the MCU in reset. The firmware then holds it through the
  after-run (pin 50).

**Proven by:** `discrete_input`, `relay_driver`, `main_relay`.

**Model link:**

- `ignition` → `ecu_mode`, `ecu_safety`, `ecu_relay`.
- `stop_sw` → shutdown.
- `wif` → `ecu_wifg`.
- `droop_sw` → `ecu_gov`.
- `ecu_relay` → the main relay.

<!-- sheet prod 9 -->

### 4.9 CAN

**Why it matters.** The DSE4522 panel gets engine speed, coolant and oil
from this bus, and its protections act on them.

**How it works.**

- Two **TCAN1042** transceivers.
- **CAN1, J1939:** pins 55/77, 250 kbit/s, to the DSE.
- **CAN2, service:** pins 87/86, 1 Mbit/s, for the laptop tool.
- Each bus is **split-terminated** (60 Ω + 60 Ω, thin film,
  50 ppm/°C), with a common-mode choke.

**Proven by:** `can_termination`.

**Model link:** `ecu_j1939` builds the data of EEC1 (speed), ET1
(coolant), EFL/P1 (oil) and HOURS. `j1939.c` sends them, with DM1 fault
codes; the service link runs UDS in `service.c`.

<!-- sheet prod 10 -->

### 4.10 Connector

**Why it matters.** The new ECU must plug into the existing harness.

**How it works.** A Bosch 94-pin header, `1 928 405 192 / 194`, code C,
wired to the **MD1CS162 terminal diagram**, which is the master pinout.
Grounds are pins 01 and 02. The board outline and connector position wait
for the old ECU to be measured.

**Model link:** none. Every pin above reaches the model through the
chain in section 2.

<!-- sheet prod 11 -->

## 5. The prototype board

**Why it exists.** A board that can be built and tested now, before the
production housing is measured. It carries the same circuits with an
**STM32G474** MCU and screw terminals, on 300 × 200 mm. Its chip layer is
`firmware/stm32`, and it flashes the code generated from the model
(`app_model_signed.hex`).

**What differs from production:**

- **MCU sheet:** STM32G474VET6, 8 MHz crystal, USB-C service port (J302,
  data only), SWD debug header (J301), plus monitors for the battery and
  the 100 V rail (`v_boost_rail`).
- **Lab I/O sheet:** the terminals J1001–J1009 instead of the Bosch
  connector, 24 test points (TP12 is the 100 V rail), and a bridge header
  for the sensor inputs.
- **The other eight sheets** are the production sheets, unchanged.

**Before power-up:** follow `prototype/docs/bring-up.md`. TP12 can hold
about 100 V for minutes after power-off: measure it below 5 V before
touching the board.

The prototype's full schematic set follows: the root sheet, then the same
order as above, with the STM32 MCU in place of the S32K148 and the lab I/O
sheet in place of the connector.

<!-- sheet proto 1 -->
<!-- sheet proto 2 -->
<!-- sheet proto 3 -->
<!-- sheet proto 4 -->
<!-- sheet proto 5 -->
<!-- sheet proto 6 -->
<!-- sheet proto 7 -->
<!-- sheet proto 8 -->
<!-- sheet proto 9 -->
<!-- sheet proto 10 -->
<!-- sheet proto 11 -->
