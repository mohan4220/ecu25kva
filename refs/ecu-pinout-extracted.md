# Kirloskar ECU — pinout extracted from GP3.8703.C4.pdf

Source: Kirloskar Oil Engines troubleshooting wiring diagram, manual `08-GP3-60-001`,
retrieved from `ikonnect.kirloskar.com`. PDF dated 2026-09-04.

This file records **only what the diagram shows**. Inferences and design decisions
live elsewhere. Where the diagram is ambiguous it is marked `[?]`.

The ECU physical connector is **94-pin** (PDF page 4). The wiring diagram shows
roughly 44 of those 94 pins — the ones relevant to field troubleshooting. Power
grounds, unused pins and internal-only pins are **not** shown. A complete pinout
requires the connector part number and the OEM pin list.

## Wire colour classes (PDF page 2 legend)

| Colour | Meaning |
|---|---|
| Red | DC positive, sensor supply voltage, AC phase 1, AC single phase, **injector output high side** |
| Black | DC negative, battery ground, sensor ground, AC neutral, **injector output low side** |
| Magenta | Analog input, PWM output, low side (on/off) |
| Cyan | Digital input, frequency input, frequency output |
| Yellow | CAN H, AC phase 2, **SENT interface** |
| Green | CAN L |
| Blue | AC phase 3 |

## Power

| ECU pin | Signal | Notes |
|---|---|---|
| 21 | Battery + feed | Red. Runs to battery/starter distribution |
| 04 | `V_V_BAT_1R` | Red, via **10 A** fuse, splice S8 |
| 06 | `V_V_BAT_2R` | Red, via **10 A** fuse |
| 09 | `SYNCHRONIZATION GROUND` | Drawn red despite "ground" in the name `[?]` |

Battery-negative / power-ground pins are not shown on the diagram.

## Analog sensors

| ECU pin | Signal | Sensor | Sensor pin |
|---|---|---|---|
| 11 | Switch Battery 5V | Boost P&T combo (4-pin) | 3 |
| 41 | Analog I/P _Pressure | Boost P&T combo | 4 |
| 79 | Analog I/P _TEMP. | Boost P&T combo | 2 |
| 34 | Sensor Ground | Boost P&T combo, via splice V3 | 1 |
| 33 | Analog I/P | Coolant temperature (2-pin) | 1 |
| — | Sensor Ground | Coolant temperature — **splices into V3 → pin 34** | 2 |
| 15 | Switch Battery 5V | EGR position (part of 5-pin EGR connector) | 3 |
| 37 | Analog I/P | EGR position | 5 |
| 36 | Sensor Ground | EGR position, via splice V4 | 4 |
| 39 | Switch Battery 5V | Oil pressure (3-pin) | B |
| 80 | Analog I/P | Oil pressure | C |
| — | Sensor Ground | Oil pressure — **splices into V4 → pin 36** | A |
| 32 | Switch Battery 5V | Rail pressure (3-pin) | 3 |
| 35 | Analog I/P | Rail pressure | 2 |
| 08 | Sensor Ground | Rail pressure — **dedicated, not spliced** | 1 |

Sensor-ground grouping as wired: `34` = boost + coolant, `36` = EGR + oil,
`08` = rail pressure alone, `30` = crank alone, `44` = cam alone.

## Speed sensors

| ECU pin | Signal | Sensor | Sensor pin |
|---|---|---|---|
| 45 | Switch Battery 5V | Camshaft speed (3-pin, Hall — square-wave symbol) | 3 |
| 46 | Frequency I/P | Camshaft speed | 2 |
| 44 | Sensor Ground | Camshaft speed | 1 |
| 52 | Frequency I/P HIGH | Crankshaft speed (3-pin, VR) | 2 |
| 74 | Frequency I/P LOW | Crankshaft speed | 1 |
| 30 | Sensor Ground | Crankshaft speed | 3 |

Crank pins 1/2 are drawn as a twisted pair. Cam pins are also twisted.

## Digital inputs

| ECU pin | Signal | Colour | Notes |
|---|---|---|---|
| 43 | Digital I/P — coolant switch | Cyan | Switch element drawn at the pin |
| 23 | Digital I/P — droop switch | Cyan | |
| 01 | `G_G_B AT1` | — | Switch return / ground leg |
| 02 | `G_G_B AT2` | — | Switch return / ground leg, splice V2 |
| 20 | `AUDIO ABORT` | **Red** | Red ⇒ switched-battery, i.e. active-high |
| 24 | `OVERSIDE SWITCH` | **Red** | Traces via XC1/XC11 pin 18 to `-S7 Override SS SW` |
| 71 | `IGNITION` | Red | |

`OVERSIDE SWITCH` (pin 24) and `Override SS SW -S7` are the **same component**.
There is no separate overspeed switch.

## Outputs

| ECU pin | Signal | Colour | Notes |
|---|---|---|---|
| 88 | `PWM Output` → fuel metering unit | Black | Metering unit pin 1. Pin 2 is fed from fused battery (20 A, `8F1`) ⇒ **low-side PWM drive** |
| 59 | `EGR HIGH` | Magenta | EGR connector pin 1 |
| 81 | `EGR LOW` | Black | EGR connector pin 2. High/Low pair ⇒ bridge drive |
| 50 | `MAIN RELAY` | Black | Low-side |
| 69 | `BUZZER RELAY` | Black | Low-side |

## Injectors — bank-shared high side

| ECU pin | Signal | Goes to |
|---|---|---|
| 03 | Injector output **HIGH side** | **Cylinder 1 pin 1 AND cylinder 3 pin 1**, joined at splice V5 |
| 05 | Injector output **HIGH side** | Cylinder 2 pin 1 |
| 73 | Injector output LOW side | Cylinder 1 pin 2 |
| 07 | Injector output LOW side | Cylinder 3 pin 2 |
| 29 | Injector output LOW side | Cylinder 2 pin 2 |

Two high-side banks, three low-side selects — **5 pins, not 6**. Bank A = cyl 1+3,
bank B = cyl 2. Injector connectors are 2-pin.

## CAN — two channels

| ECU pin | Signal | Colour |
|---|---|---|
| 55 | CAN H (channel 1) | Yellow |
| 77 | CAN L (channel 1) | Green |
| 87 | CAN H (channel 2) | Yellow |
| 86 | CAN L (channel 2) | Green |

Both drawn as twisted pairs with bidirectional markers.

## Signals that are NOT on the ECU

These appear in the system but route through the XC11/XC1 36-pin harness
connectors to the panel/GCU, not to the ECU:

- **Fuel level sensor** (2-pin variable resistor) → XC pin 22, wire `1C2`
- **Water-in-fuel switch** (`WIF SW`, 3-pin) → XC pin 16/1, wire `4B`

Present in the connector appendix (PDF pages 3–4) but not traced to an ECU pin
anywhere in the diagram — needs confirmation against a different variant or a
fuller document:

- **Intake Throttle Valve** connector — **6-pin**
- **Catalyst Temperature Sensor** connector — 2-pin, **one only**
- **Fuel Pump** connector — 2-pin
- **Charging Alternator** connector — 2-pin

## Absent from the entire system

No magnetic pickup (MPU). No DEF/urea sensor. No LIN bus. No SCR. No barometric
sensor in the harness. No separate overspeed switch. Engine speed reaches the
GCU over CAN only.

## Other system components named

Genset control unit: **Kirloskar KG640C** (terminals J1–J8).
Terminal blocks `XDBK1`/`XDBK2`/`XDBK3`, relay board `-13RB1`, battery charger
`11BC1`, starter `8STR1` with solenoid `-SOL`, alternator `8ALTR1`, fuse `F1 40 A`,
MCB `F3 40A/3P 10kA`, power terminal board `XPTB1` 100/125 A 415 VAC 3-phase.
