# Work Step 1 — How the ECU works: the model, the circuit and the equations

**For:** an engineer who needs to understand the whole ECU from one
document: how the Simulink model runs, how the circuit is laid out, what
the controller and the plant are, and the equations inside each.
**Written:** 25 November 2026, from the repository as it stands
(`model/mdl_ecu25kva.m`, `firmware/core`, `firmware/sim/engine.py`,
`docs/schematic-guide.md`).

Every formula below is quoted from the C reference bodies in
`firmware/core`. The flashed build (`app_model`) runs code generated from
the Simulink component models, and the back-to-back test (b2b) proves each
model bit-exact against that C. So the equations here are the equations
the ECU runs.

Contents:

1. The Simulink model: where it starts and where it ends
2. The circuit: where it starts and where it ends
3. Controller and plant: what they are, their inputs and outputs
4. The plant's equations
5. The controller's equations
6. Diagnosis and fault equations
7. What is calibrated, what is assumed, what is still C

---

## 1. The Simulink model: where it starts and where it ends

The top model `model/ecu25kva.slx` (built by `model/mdl_ecu25kva.m`) has
four parts:

| Block | What it is | Flashed? |
|---|---|---|
| **TRIGGERS** | The scheduler: plays the chip's timers and interrupts | No (the chip does this) |
| **MODEL** | The ECU: the 27 component models (`ecu_*.slx`) | **Yes**, generated to C |
| **PLANT** | Engine, generator, fuel rail, metering coil, sensor voltages | No, simulation only |
| **SCENARIO** | Ignition, load, stop switch, battery and coolant profiles; the DSE panel | No |

There are three loops, one inside the other.

### 1.1 The whole run: t = 0 s to t = 20 s

```
 t = 0     battery 13.5 V (assumed), coolant 85 degC, everything off
 t = 0.5 s ignition ON
           starter turns until the ECU reports RUN (about 2 s)
 t = 8 s   20 kW load switched on
 t = 16 s  stop switch (pin 25) pressed
 t = 20 s  simulation ends (engine coasting below 300 rpm)
```

`model/test/sim_ecu25kva.m` also runs three more: a 25 s run for the
protection (low battery, coolant level, overheating, Protect, the DSE
dropping the ignition); a run with the metering current reading lost and
the 100 V boost rail at 110 V; and a run with the crank signal lost. It
checks 44 results across the four.

**About 13.5 V.** The battery is a 12 V battery. 13.5 V is an assumption,
not a measurement: the usual voltage of a 12 V lead-acid battery while
the engine's charging alternator charges it. The ECU does not depend on
it: it measures the battery on pin 04 and uses that. 13.5 V is used only
as the simulation's battery and as the fallback when the reading is
missing or implausible (`MU_V_NOM`). The injector hold limit is worked
out at both 12 V and 13.5 V. The running voltage measured on the set
will replace it.

### 1.2 Every millisecond: one loop around the four blocks

```
        +--------------+  function-call events  +----------------------+
  +---> |  TRIGGERS    | ---------------------> |  MODEL (the ECU)     |
  |     |  (scheduler) |                        |  = the flashed code  |
  |     +--------------+                        +----------+-----------+
  |                                                        | fuel, duty,
  |     +--------------+  ignition, load, stop  +----------v-----------+
  |     |  SCENARIO    | ---------------------> |  PLANT (sim only)    |
  |     +--------------+                        |  engine, rail, coil, |
  |                                             |  sensor voltages     |
  +------------ speed, sensor voltages <--------+----------------------+
```

**Start of the tick: TRIGGERS** (a Stateflow chart) sends:

| Event | When |
|---|---|
| `initialisation` | First tick only: loads the end-of-line trims |
| `cyl_event_isr` | Every cylinder event (every 240 deg of crank) |
| `one_ms_task` | Every 1 ms |
| `twenty_ms_task` | Every 20 ms |
| `five_hundred_ms_task` | Every 500 ms |
| `one_sec_task` | Every 1 s |
| `ten_sec_task` | Every 10 s |

**Middle of the tick: MODEL.** `one_ms_task` runs, in order:

```
 sensors (ecu_sensors, ecu_sensaux)        volts -> degC, kPa, bar
   |
 safety + guards                           overspeed, boost, EGR, WIF, underspeed
   |
 mode (ecu_mode)                           OFF / WAIT / CRANK / RUN / SHUTDOWN
   |
 governor (ecu_gov, ecu_spdst)             speed error -> fuel mg
   |
 rail (ecu_railset, ecu_rail)              rail setpoint -> valve current command
   |
 metering valve (ecu_musup, ecu_mucur)     coil learned -> PWM duty
   |
 EGR (ecu_egrpos)                          position -> bridge duty
   |
 relay (ecu_relay)                         main relay, after-run
   |
 diagnosis (ecu_diag -> 14 x ecu_deb)      faults set and healed
   |
 lamps (ecu_lamps)                         amber / red / Protect
```

- `cyl_event_isr`: `ecu_soi` and `ecu_injdur` give the start of injection
  and the pulse length.
- `twenty_ms_task` and the slower tasks: `ecu_j1939` packs the CAN frames
  (EEC1 every 20 ms, EFL/P1 every 500 ms, ET1 and IC1 every 1 s, HOURS
  every 10 s).

**End of the tick: PLANT** takes the fuel and valve duty, moves the engine
speed, rail pressure, coil current and temperatures one step, and turns
them back into sensor voltages for the next tick. The DSE is one block: if
Protect is lit, it switches the ignition off on the next tick.

### 1.3 The engine's own flow: `ecu_mode`

```
  OFF --ignition on--> WAIT --first tooth--> CRANK --phased, rpm > 400--> RUN
   ^                                                                       |
   |                                       stop switch, overspeed, sync    |
   +--------- engine stopped, after-run done <-- SHUTDOWN <----------------+
                                                 (fuel cut, boost off)
```

It starts at OFF and ends at SHUTDOWN, then OFF. In the normal run: RUN at
about 2 s, SHUTDOWN at 16 s (`model/test/ecu25kva_sim.png`, second plot).

---

## 2. The circuit: where it starts and where it ends

Both flows start at the Bosch 94-pin connector and end back at it. The
sheet numbers are those of `docs/schematic-guide.md` section 4.

### 2.1 Power: from battery pins 04/06 to every chip and actuator

```
 BATTERY 12 V (pins 04, 06; ground 01, 02)
   |
 [4.1 POWER INPUT]  EMI filter -> 5 A fuse -> TVS clamp (SMCJ43CA)
                    -> reverse-battery P-FET (SQM120P10) -> negative clamp
   |
   +--> [4.2 RAILS]  LM5164 buck -> 5V_MAIN -> TLV76733 LDO -> 3.3 V (MCU)
   |                 +-> TPS7B4253 trackers -> sensor 5 V (cut off above 41 V)
   |
   +--> [4.4 INJECTOR STAGE]  TPS40210 boost -> 100 V rail (zener stop near 110 V)
   |
   +--> [4.5 METERING + EGR]  battery to the valve FET and the H-bridge
```

The main relay (sheet 4.8): pin 71 (ignition) closes it in hardware; the
MCU then holds it through pin 50 until the after-run is done.

### 2.2 Signals: sensor pin -> front end -> MCU -> driver -> actuator pin

```
 INPUT PINS                FRONT END (sheet)                 MCU
 33,80,41,37 sensors  --> [4.6] INA592 diff amps (1/2) -->+
 35 rail pressure     --> [4.6] 10k/16k divider        -->|
 04 battery           --> [4.6] 120k/10k divider       -->|  ADC
 52/74 crank (VR)     --> [4.7] zero-cross comparator  -->|  timer capture
 46/44 cam (Hall)     --> [4.7] clamp                  -->|
 71,25,21,23 switches --> [4.8] NPN buffers (inverted) -->+  GPIO
                                                           |
                                              [4.3] MCU: runs the generated
                                                    Simulink code
                                                           |
 OUTPUT PINS               DRIVER (sheet)                  v
 03,05 + 73,29,07 inj <-- [4.4] boost/battery high sides + low-side FETs
 88 metering valve    <-- [4.5] low-side FET, 1 kHz PWM
 59/81 EGR valve      <-- [4.5] H-bridge (AUIRS2184)
 50 main relay        <-- [4.8] low-side FET
 55/77 J1939 to DSE   <-> [4.9] TCAN1042, 250 kbit/s
 87/86 service        <-> [4.9] TCAN1042, 1 Mbit/s
```

Feedback on the board: shunts with INA181 amplifiers measure the
injector, metering valve and EGR currents back into the ADC. That is how
the MCU shapes the injector current (peak 18 A, hold 9-11 A) and closes
the metering current loop.

### 2.3 Safety: around the MCU, not through it

```
 TPS3850 watchdog (kicked every 10 ms) -+
 MCU reset -----------------------------+--> GATE_KILL --> every injector,
 stop switch pin 25 (hardware) ---------+                  metering and EGR
                                                           gate forced OFF
 110 V zener --> boost converter stopped
```

### 2.4 How the circuit lines up with the model

| Circuit | Simulink |
|---|---|
| Battery, sensors, crank, switches (the real world) | PLANT + SCENARIO |
| Front ends -> ADC / timer / GPIO | `ecu_io` inputs into `one_ms_task` |
| MCU timers and interrupts | TRIGGERS |
| MCU running the code | MODEL: `ecu_sensors` ... `ecu_lamps` |
| Drivers -> actuator pins, CAN | MODEL outputs: fuel, duty, egr_duty, relay, J1939 frames |

---

## 3. Controller and plant: what they are, their inputs and outputs

```
              setpoint                    command (output)
  operator --> 1500 rpm --> CONTROLLER ----------------------> PLANT
                               ^                                |
                               |    measurement (input)         |
                               +--------------------------------+
```

- **Controller:** decides. Here, the ECU (MODEL).
- **Plant:** what is controlled. Here, the engine, generator, rail and valves (PLANT).
- The plant's outputs are the controller's inputs, and the other way round.

### 3.1 Controller (MODEL) inputs

| Input | What it is | From (sim) | On the board |
|---|---|---|---|
| `v_sens` (5) | Coolant, oil, rail, boost, EGR sensor voltages | PLANT | Pins 33, 80, 35, 41, 37 -> ADC |
| `v_5v` | Sensor supply | PLANT | 10k/15k divider |
| `rpm` | Engine speed | PLANT | Crank pins 52/74 -> `crank.c` |
| `i_mu` | Metering coil current | PLANT | 50 mOhm shunt + INA181 |
| `v_bts` | Charge-air temperature | PLANT | Pin 79 |
| `v_bat` | Battery | SCENARIO | Pin 04 divider |
| `ignition` | Key on | SCENARIO (through the DSE block) | Pin 71 |
| `stop_sw` | Stop switch | SCENARIO | Pin 25 |
| `clt_low` | Coolant level switch | SCENARIO | Pin 43 |
| `droop`, `wif` | Droop switch, water in fuel | Constants | Pins 23, 21 |
| `v_boost_rail`, `i_egr` | 100 V rail, EGR current | Constants | Divider, EGR shunt |

### 3.2 Controller (MODEL) outputs

| Output | What it is | To (sim) | On the board |
|---|---|---|---|
| `fuel_mg` -> `soi_deg`, `dur_us` | Fuel, injection start and length | PLANT | Injector pins 03/05 + 73/29/07 |
| `duty` | Metering valve PWM | PLANT | Pin 88 |
| `starter` | Starter request, **simulation only** (a sequencer in MODEL, so the plant can crank) | PLANT | None: the DSE4522 drives the starter; the ECU has no starter output |
| `egr_duty`, `egr_off` | EGR bridge | Logged | Pins 59/81 |
| `relay`, `afterrun` | Main relay | Logged | Pin 50 |
| `boost_dis` | Stop the 100 V boost | Logged | Boost DIS/EN |
| `protect`, `lamps` | Fault lamps | DSE block | J1939 DM1 to the DSE4522 |
| `eec1`, `et1_tx`, `eflp1_tx`, `ic1`, `hours_tx` | J1939 frames | Logged and checked | CAN pins 55/77 |

### 3.3 Plant (PLANT) inputs and outputs

- **Inputs:** `fuel_mg`, `duty`, `starter` from the controller; `load_kw`,
  `v_bat`, `clt_degc`, `r_coil` from the scenario.
- **Outputs:** `rpm`, `v_sens`, `v_5v`, `rail_bar`, `i_mu`, `v_bts`,
  `cyl_edge`, back into the controller.

Only the controller is flashed. On the genset the real engine replaces
PLANT and the wires replace the lines; the controller's inputs and outputs
stay exactly the same.

---

## 4. The plant's equations

A mean-value model: averages, not individual strokes. Constants are read
from `firmware/sim/engine.py`, so the Python SIL and Simulink run the same
engine. Each equation is stepped every 1 ms by forward Euler:
`x[k+1] = x[k] + 0.001 * dx/dt`.

### 4.1 Engine speed (Newton's law for rotation)

```
J * dw/dt = T_ind + T_starter - T_friction - T_load        rpm = w * 60 / (2 pi)
```

| Term | Equation | Constants |
|---|---|---|
| Inertia | J | 2.0 kg m2 (engine + alternator rotor) |
| Combustion | T_ind = W * m_fuel * n_cyl / (4 pi) | W = 19.5 J/mg (42.6 kJ/g x 0.46); n_cyl = 3; 4 pi: one firing per two revolutions |
| Friction | T_friction = 10 + 0.006 * rpm  (N m) | |
| Generator | T_load = P_load / (eta * w) * min(1, (rpm / 1410)^2) | eta = 0.9; the AVR knee at 1410 rpm |
| Starter | T_starter = 100 * (1 - rpm / 165), only below 165 rpm while requested | 100 N m stall |

The fuel reaching the cylinders lags the command by about 40 ms:

```
m_fuel[k] = a * m_fuel[k-1] + (1 - a) * m_cmd[k],     a = exp(-1/40)
```

Worked example at 1500 rpm (w = 157 rad/s):

| | No load | 20 kW |
|---|---|---|
| T_load | 0 | 20000 / 0.9 / 157 = 141.5 N m |
| T_friction | 19 N m | 19 N m |
| Fuel needed | about 4.1 mg/stroke | about 34.5 mg/stroke |

The governor has to find these fuel values by itself.

### 4.2 Rail pressure (fuel in minus fuel out)

```
dp/dt = K * (Q_pump - Q_leak - Q_inj)

Q_pump = (4.0 / 1500) * rpm * (1 - frac)          cm3/s; valve normally open
Q_leak = 1e-4 * p                                  cm3/s
Q_inj  = 0.0012 * m_fuel * 3 * rpm / 120           cm3/s
K = 750 bar/cm3;  p held between 0 and 1800 bar (relief valve)
```

### 4.3 Metering valve coil (R-L circuit)

```
i[k] = i[k-1] + (d * V_bat / R_coil - i[k-1]) * (1 - exp(-1/3))      tau = 3 ms
frac = min(1, i / 1.8 A)                                              fraction of full closing
```

- R_coil is 3.75 ohm (4.5 ohm in run 2, so the ECU must learn it).
- The ECU reads the previous millisecond's current, as a real ADC samples
  the current already flowing.

### 4.4 Sensor voltages (each transfer function, backwards)

| Sensor | Physical value | Voltage |
|---|---|---|
| Coolant (pin 33) | From the scenario, 85 degC default | Bosch NTC table -> R, parallel NTC_LOAD, pull-up divider from 5 V |
| Charge air (pin 79) | 30 degC + 0.6 degC per kW | Same NTC circuit |
| Oil (pin 80) | 400 kPa x rpm / 1500 | 0.5 V + 4 V x value / span |
| Rail (pin 35) | p from 4.2 | 0.5-4.5 V over 0-1800 bar |
| Boost (pin 41) | 100 + 100 x kW / 25 kPa | 0.5-4.5 V over 50-400 kPa |
| EGR position (pin 37) | Valve shut | 0.5 V |
| Sensor supply | 5 V exactly | 5 V |

### 4.5 Cylinder events

```
theta[k] = theta[k-1] + rpm * 6 * 0.001      degrees per ms
```

Each time theta passes 240 deg (720 / 3 cylinders) the plant sends one
`cyl_edge`, which fires `cyl_event_isr`.

### 4.6 What the plant does not model

- The constants are estimates from `engine.py`, not measured on the KOEL
  engine (inertia, friction and pump flow matter most).
- No per-stroke torque pulses and no crank teeth: the crank decoder is
  proven separately (b2b, the unit tests, the 19 SIL scenarios).
- Coolant temperature is a scenario input, not a heat model.
- EGR is fixed shut; the boost rail and EGR current are constants.

---

## 5. The controller's equations

All single precision; dt = 0.001 s; `clamp(x, lo, hi)` limits x.

### 5.1 Sensors (`ecu_sensors`): voltage -> physical value

```
v_r = (v * g + o) * 5 / V_5V           trim, then ratiometric correction
                                        (V_5V outside 4.5-5.5 V: 5 V is used)
linear sensors:  x = x_lo + (v_r - 0.5) / 4 * (x_hi - x_lo)
coolant NTC:     R = R_pu * v / (5 - v);  R_ntc = R * R_L / (R_L - R);  degC from Bosch's table
```

| Sensor | Span | Default while faulted |
|---|---|---|
| Coolant | NTC table | 90 degC |
| Oil | 0-1000 kPa | 300 kPa |
| Rail | 0-1800 bar | 1000 bar |
| Boost | 50-400 kPa | 100 kPa |
| EGR position | 0-100 % | 0 % |

### 5.2 Engine state (`ecu_mode`)

| Mode | Fuel |
|---|---|
| CRANK | 30 mg fixed (`FUEL_START_MG`) |
| RUN | Governor output |
| Any other | 0 |

### 5.3 Governor (`ecu_gov`): speed -> fuel

```
n_set[k]  = min(n_set[k-1] + 500 * dt, 1500)                 ramp from the RUN-entry speed
n_target  = 1500 * (1 - 0.04 * m_fuel / 34)    droop switch closed
          = 1500                                 otherwise (the simulation)
e         = min(n_set, n_target) - n
I[k]      = clamp(I[k-1] + K_I * e * dt, 0, 45)
m_fuel    = clamp(I + K_P * e, 0, 45)  mg                    K_P = 0.5 mg/rpm, K_I = 2.0 mg/(rpm s)
```

Speed state (`ecu_spdst`): STEADY within +/- 15 rpm of target for 1 s;
OPERATING otherwise.

### 5.4 Rail setpoint (`ecu_railset`): fuel -> pressure target

From the old Bosch ECU at 1500 rpm; linear between points, held at the ends.

| Fuel (mg) | 6.5 | 8.5 | 9.5 | 10.5 | 14.5 | 16.5 | 18.5 | 20.5 | 25.5 | 26.5 |
|---|---|---|---|---|---|---|---|---|---|---|
| Rail (bar) | 827 | 838 | 885 | 994 | 994 | 1046 | 1108 | 1147 | 1156 | 1171 |

### 5.5 Rail pressure loop (`ecu_rail`): pressure -> valve current command

The valve is normally open: too much pressure needs more current.

```
e    = p_rail - p_set
I[k] = clamp(I[k-1] + K_I * e * dt, 0, 1)
c    = clamp(I + K_P * e, 0, 1)          K_P = 0.002 /bar, K_I = 0.01 /(bar s)
```

c is the current command as a fraction of 1.8 A (1.0 = valve closed). With
the rail sensor faulted, a fixed limp opening is used instead.

### 5.6 Metering coil supervision (`ecu_musup`)

Learning the coil (only with the reading plausible, battery 6-18 V, duty
5-95 %, current over 0.9 A):

```
R_meas = d_prev * V_bat / i_meas
R[k]   = R[k-1] + 0.001 * (R_meas - R[k-1])      tau 1 s; clamped 1.85-6.91 ohm
```

Fallback, when the current reading has been impossible for 10 ms:

```
c' = c * R / 3.75
```

### 5.7 Metering current loop (`ecu_mucur`): current -> PWM duty

```
d_ff = c * 6.75 V / V_bat                 6.75 V = 1.8 A x 3.75 ohm (V_bat outside 6-18 V: 13.5 V)
e    = c - i_meas / 1.8
I[k] = clamp(I[k-1] + K_I * e * dt, -0.5, 0.5)     frozen while the output is at a limit
d    = clamp(d_ff + I + K_P * e, 0, 1)             K_P = 0.1, K_I = 10 /s
```

With the reading not valid, d = d_ff alone.

### 5.8 Injection (`cyl_event_isr`)

Start of injection (`ecu_soi`), from the old ECU:

| Fuel (mg) | 6.5 | 8.5 | 11.5 | 14.5 | 17 | 18.5 | 20.5 | 26.5 |
|---|---|---|---|---|---|---|---|---|
| deg BTDC | 11.5 | 12.4 | 13.5 | 15.5 | 15.9 | 16.0 | 14.6 | 14.2 |

Duration (`ecu_injdur`): flow rises with the square root of rail pressure,
plus a fixed opening delay (both measured):

```
t_inj = 323 us + m_fuel / (0.00191 * sqrt(max(p_rail, 100)))
```

| Condition | Fuel | Rail | Duration |
|---|---|---|---|
| No load | about 4 mg | about 827 bar | about 400 us |
| 20 kW | about 34.5 mg | about 1170 bar | about 850 us |

The current shape (peak 18 A from 100 V, hold 9-11 A from the battery) is
in the chip layer (`firmware/stm32/inj_logic.c`), not in the model.

### 5.9 EGR position (`ecu_egrpos`): PID, derivative on the measurement

```
e    = x_target - x
D[k] = D[k-1] + 0.1 * ((x[k] - x[k-1]) / dt - D[k-1])
d    = clamp(K_P * e + I - K_D * D, -0.95, 0.95)       K_P = 0.02, K_I = 0.1, K_D = 0.0005
target at or below closed: the bridge coasts, the spring closes the valve
```

The target table is zeros until there is an emissions calibration.

### 5.10 J1939 (`ecu_j1939`): scaling into CAN bytes

```
EEC1 speed raw = rpm / 0.125        ET1 coolant raw = degC + 40        oil raw = kPa / 4
```

Each value is clamped into its byte range (above 250 means error or not
available).

### 5.11 The two cascades

```
rpm -> [gov] -> fuel -+-> [railset] -> p_set -> [rail] -> c -> [musup] -> [mucur] -> duty -> valve
                      +-> [soi]     -> start angle  -+
                      +-> [injdur]  -> duration     -+-> injectors
```

---

## 6. Diagnosis and fault equations

```
measurements -> [condition] -> [debounce / heal] -> active fault -> fault table -> [lamps] -> DM1 -> DSE
                ecu_diag        ecu_deb x 14        (SPN/FMI)       ecu.c          ecu_lamps
                ecu_sensors     (guards' own timers)
                ecu_safety, guards
```

### 6.1 Debounce and heal (`ecu_deb`, one per fault)

Counter n (ms) and state act (0 healthy, 1 active), every 1 ms:

```
healthy (act = 0):  n = cond ? n + 1 : 0;      act -> 1 when cond and n + 1 >= T_deb
active  (act = 1):  n = cond ? 0 : n + 1;      act -> 0 when not cond and n + 1 >= T_heal
```

A fault must hold continuously for T_deb to set and be gone continuously
for T_heal to heal. Battery and coolant also have hysteresis: once active,
the threshold moves to the return level.

### 6.2 The 14 diagnoses (`ecu_diag`)

EGR faults are checked only while running, with the bridge enabled and
the battery 10-15 V. The EGR current is filtered first:
`i_f = i_f + 0.05 * (i - i_f)` (about 20 ms).

| # | SPN/FMI | Fault | Condition | Set / heal |
|---|---|---|---|---|
| 1 | 2791/5 | EGR open circuit | abs(duty) > 20 %; filtered current <= 0.1 A | 200 / 130 ms |
| 2 | 2791/0 | EGR stuck open | abs(duty) < 5 %; position > 35 % | 1 s / 200 ms |
| 3 | 2791/7 | EGR stuck shut | duty >= 90 %; position < 35 % | 1 s / 200 ms |
| 4 | 1347/5 | Metering valve open circuit | reading valid; d x V_bat / 6.91 > 0.25 A; i_mu < 0.05 A | 500 ms / 0 |
| 5 | 1347/6 | Metering valve overcurrent | i_mu > 3.0 A | 500 ms / 0 |
| 6 | 157/7 | Rail not following | running; sensor OK; abs(p_set - p) > 150 bar and > 25 % of p_set | 2 s / 1 s |
| 7 | 190/16 | Speed high (warning) | running; rpm > 1590 | 2 s / 1 s |
| 8 | 190/8 | Speed signal lost | ignition on; stopped; oil > 200 kPa | 2 s / 0 |
| 9 | 100/2 | Oil pressure implausible | ignition on; stopped; 100 < oil <= 200 kPa | 2 s / 0 |
| 10 | 168/16 | Battery high | ignition on; V_bat > 15.0 V (14.5 V once active) | 10 s / 0 |
| 11 | 168/18 | Battery low | running only; V_bat < 9.5 V (10.0 V once active) | 10 s / 0 |
| 12 | 110/16 | Coolant hot | ignition on; sensor OK; > 100 degC (98 once active) | 2 s / 0 |
| 13 | 110/0 | Coolant too hot (stop) | ignition on; sensor OK; > 104 degC (102 once active) | 2 s / 0 |
| 14 | 111/18 | Coolant level low | ignition on; pin 43 open | 5 s / 1 s |

### 6.3 Sensor faults (`ecu_sensors`)

```
now = 3  if v_r > 4.8 V                (high: short to supply)
      4  if v_r < v_lo (0.1-0.2 V)     (low: open or short to ground)
      0  otherwise
set after 100 ms out of range; clear after 100 ms back in range
```

While set, the sensor reads its default (5.1). The code goes out on the
sensor's own SPN: coolant 110, oil 100, rail 157, boost 102, EGR
position 27, charge air 105.

### 6.4 Trips and guards

`ecu_safety`, every tick (overspeed also on every crank tooth):

```
OVERSPEED     if rpm > 1650                 (below the DSE's 1680 / 1710 rpm trips)
SYNC LOST     if running and crank fault    (no tooth for 50 ms, or a wrong gap)
IGNITION OFF  if ignition = 0
```

| Guard | Condition | Time | Result |
|---|---|---|---|
| `ecu_boostg` | 100 V rail > 106 V | 20 ms | 520192 high severe: boost off, SHUTDOWN |
| `ecu_boostm` | rail > 104 V | 2 s | Warning |
| `ecu_boostm` | rail < 80 V while running | 500 ms | Warning |
| `ecu_egrg` | EGR current > 5 A | 1.5 s | Coast, cool 5 s, retry; fault after 3 tries |
| `ecu_wifg` | Water in fuel | 2 s (2 s to clear) | WIF fault (amber) |
| `ecu_underg` | rpm < 1350 while running | 3 s | 190 low (amber); clears above 1400 rpm for 1 s |

### 6.5 Lamps (`ecu_lamps`)

Every active fault sits in a table of up to 16 (what DM1 sends). The
lamps byte is an OR over it:

```
lamps = OR over faults of:  RED | PROTECT  if the fault is 190/0, 636/any, 520192 severe or 110/0
                            AMBER          otherwise
```

| Lamp | Bit | DSE4522 reaction |
|---|---|---|
| PROTECT | 0x01 | Shuts the set down |
| AMBER | 0x04 | Warning; the engine keeps running |
| RED | 0x10 | Shows red |

Only overspeed, loss of crank position, boost overvoltage and coolant over
104 degC shut the set down. The coolant shutdown is the ECU's job because
this set's DSE coolant alarms are at 150 / 200 degC (decisions log 35).

---

## 7. What is calibrated, what is assumed, what is still C

| Item | Status |
|---|---|
| Rail setpoint and SOI tables | Copied from the old ECU's behaviour (field evidence, 14 Oct) |
| Injector dead time 323 us, flow 0.00191 | Measured |
| Metering coil 3.75 ohm nominal | Measured 2.5-5 ohm (decisions log 25) |
| Governor, rail, metering and EGR gains | Starting values, to tune on the engine |
| Diagnosis thresholds and times | KOEL 20 kVA sheet or chosen here; battery limits from this set's DSE; coolant limits chosen by the owner |
| Plant constants | Estimates (`engine.py`), not measured on this engine |
| Battery 13.5 V in the simulation | Assumed charging voltage; the running reading will replace it |
| EGR target table | Generated (`ecu_egrtgt`, decisions log 43); zeros: no emissions calibration yet |
| Fault table (`fault_raise` / `fault_drop`), fault memory, DM1/DM2 sending | Hand-written C (`ecu.c`, `j1939.c`) |
| Crank decoder | Generated (`ecu_crank`), proven by b2b; not in the top model's simulation, whose run 4 checks the trip on its fault output |
| Injector current shape | Hand-written C (`inj_logic.c`), kept in C for interrupt timing (decisions log 41) |

**Next:** the owner's no-load PCAN recording checks the J1939 scaling
(5.10) and the DM1 codes and lamps (6.5) against the old ECU, and gives
real readings to compare the plant (section 4) with.
