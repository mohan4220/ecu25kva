# MD1CS162 pinout, from the Bosch terminal diagram

Source: `T4.435.04.0.PR-terminal-diagram-MD1CS162.pdf`, Bosch drawing
`0 462 YU4 15D`, "Terminal diagram MD1CS162 KOEL CPCB4+ 3 cyl", ECU software
MD1CS162-3.21. Second edition, 7 October 2022, which removed pins 26, 67, 42 and 91.
The drawing lists 3R550TA, 3R1190NA and 3R1190TA. The owner confirmed on
7 November 2026 that it applies to our 3GK550ETA4SR1, with the same sensors and
ratings.

**This is the master pinout for the board.** It replaces
`ecu-pinout-extracted.md` (KOEL harness diagram GP3.8703.C4) wherever the two
disagree. Read from a 400 dpi render of the drawing.

Name prefixes: `I_` input, `O_` output, `B_` bus, `G_` ground, `V_` supply in.
Second letter: `A` analog, `S` switch, `F` frequency, `T` PWM low side,
`P` power stage (injector), `V` 5 V sensor supply, `R` sensor return, `D` data,
`G` power ground.

## Power and ground

| Pin | Bosch name | Wiring on the drawing |
|---|---|---|
| 04 | `V_V_BAT_1R` | Main relay terminal 87 → splice V1 → 10 A fuse → pin. Length ≤ 1.5 m |
| 06 | `V_V_BAT_2R` | Same, separate 10 A fuse |
| 50 | `O_S_MRLY` | Main relay coil, terminal 85. Terminal 86 and contact 30 sit on Term. 30 behind one fuse. Low-side output |
| 71 | `I_S_T15` | Ignition (terminal 15), from a GCU relay whose contact is fed from Term. 30 through 5 A |
| 01 | `G_G_BAT1` | Battery negative (terminal 31) |
| 02 | `G_G_BAT2` | Battery negative via splice V2. Length ≤ 1.0 m |

There is **no permanent battery feed to the ECU.** The ignition on 71 wakes the
ECU. The ECU pulls 50 low, the main relay closes, and the ECU then runs from 04/06.
Relay 87 also feeds, through V1 and a customer fuse, the "main-relay line" that
supplies the metering unit, the water-in-fuel switch and the buzzer relay coil.

## Inputs from the GCU and switches

| Pin | Bosch name | Function | Active level, as drawn |
|---|---|---|---|
| 20 | `I_S_AAS` | Audio abort switch | High: GCU relay contact to Term. 30 |
| 24 | `I_S_OS` | Override switch | High: GCU relay contact to Term. 30 |
| 14 | `I_S_DIA` | Diagnosis request switch | GCU relay contact. Its other side runs down to terminal 31, so **low** |
| 25 | `I_S_STST` | Engine-compartment stop / emergency switch | GCU relay contact, other side to terminal 31, so **low** |
| 09 | `I_A_SYNC` | Synchronisation input signal | **Analog**, wired direct from the GCU |
| 43 | `I_S_CLS` | Coolant switch | Low: switch to terminal 31 |
| 23 | `I_S_DROOP` | Droop switch | Low: switch to terminal 31 |
| 21 | `I_S_WFLS` | Water-in-fuel sensor (F 002 H23 583) | **High**. Sensor pin 1 is ground and pin 3 is the main-relay line. Its switch connects 3 to 2, and 2 goes to pin 21. Open, so floating, when there is no water |

## Sensors

| Pin | Bosch name | Sensor (Bosch number) | Sensor pin |
|---|---|---|---|
| 11 | `O_V_5VBPS` | Boost pressure + temperature (0 281 006 102) | 3 |
| 41 | `I_A_BPS` | | 4 |
| 79 | `I_A_BTS` | | 2 |
| 34 | `G_R_BPS` | | 1, via splice V3 (shared with the coolant sensor) |
| 33 | `I_A_CTS` | Coolant temperature (0 281 002 209) | 1. Pin 2 `G_R_CTS` → V3 → 34 |
| 39 | `O_V_5VOPS` | Oil pressure, Honeywell PX3AN2BF010BSDAX | B |
| 80 | `I_A_OPS` | | C. `G_R_OPS` (A) goes to line ref 76 = V4 → 36 |
| 32 | `O_V_5VRAILPS` | Rail pressure (0 281 006 425) | 3 |
| 35 | `I_A_RAILPS` | | 2 |
| 08 | `G_R_RAILPS` | | 1, dedicated |
| 45 | `O_V_5VCAS` | Cam (segment) speed, Hall (0 281 002 667) | 3 |
| 46 | `I_F_CAS` | | 2 |
| 44 | `G_R_CAS` | | 1 |
| 74 | `I_F_CRSNEG` | Crank speed, inductive DG6 (0 281 002 214) | 1 |
| 52 | `I_F_CRSPOS` | | 2 |
| 30 | `G_R_CRS` | | 3 (shield / return) |
| 15 | `O_V_5VEGR` | EGR position, Padmini | 3 |
| 37 | `I_A_EGR` | | 5 |
| 36 | `G_R_EGR` | | 4, via splice V4 (shared with the oil sensor) |

The boxed numbers 55 and 76 near V4 and the oil sensor are **drawing line
references** that tie the oil ground into V4. They are not ECU pins.

## Outputs

| Pin | Bosch name | Load |
|---|---|---|
| 03 | `O_P_INJVH1` | Injector high side, cyl 1 + cyl 3 (splice V5) |
| 05 | `O_P_INJVH2` | Injector high side, cyl 2 |
| 73 | `O_P_INJVL1` | Injector low side, cyl 1 |
| 07 | `O_P_INJVL2` | Injector low side, cyl 3 |
| 29 | `O_P_INJVL3` | Injector low side, cyl 2 |
| 88 | `O_T_MEU` | Fuel metering unit CB18 (0 928 400 820). Its other pin is on the main-relay line |
| 59 | `O_T_EGRPOS` | EGR actuator H-bridge, + |
| 81 | `O_T_EGRNEG` | EGR actuator H-bridge, − |
| 69 | `O_T_BUZZ` | Buzzer relay coil. The coil's other side is on the main-relay line |

Injectors CRI-2-16 (0 445 B76 1X3), firing order 1-2-3, ECU control order
Inj1, Inj3, Inj2. Injector leads ≤ 1.5 m. Pins 50 and 69 are marked "ECU pin
not equipped with freewheeling diode", so **the relay must contain the diode**,
not the harness.

## CAN

| Pin | Bosch name | Bus |
|---|---|---|
| 87 | `B_D_CANH1` | CAN 1, "Application CAN line", **1000 kbit/s**, flashing and UDS |
| 86 | `B_D_CANL1` | |
| 55 | `B_D_CANH2` | CAN 2, "PT CAN line", **250 kbit/s**, inter-ECU (J1939) and OBD |
| 77 | `B_D_CANL2` | |

## Where this differs from the KOEL harness diagram

| Pin | KOEL GP3.8703.C4 | Bosch |
|---|---|---|
| 21 | Battery + feed | Water-in-fuel input, active high |
| 01 / 02 | "Switch return" | Power ground |
| 09 | "Synchronization ground" | Analog sync input from the GCU |
| 14, 25 | Not shown | Diagnosis request, stop switch |
| 55/77 vs 87/86 | 55/77 called "channel 1" | 87/86 is CAN 1 (1000k, UDS); 55/77 is CAN 2 (250k, J1939) |
| Water-in-fuel | To the panel via XC | To ECU pin 21 |

Everything else matches.
