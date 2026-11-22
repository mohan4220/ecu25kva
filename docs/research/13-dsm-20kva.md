# 13. The 20 kVA set's DSM sheet: its fault diagnoses, and what this ECU took

**Source:** the owner's "DSM Sheet.pdf" (18 November 2026), the fault-diagnosis
table of the 20 kVA genset's controller. Each row gives a fault's code
(J1939 SPN and FMI), how it is detected, its debounce and healing times, and
what the lamp does.

**Status of every value here: from the 20 kVA set, not confirmed on the 25 kVA
engine.** What the firmware took is in `firmware/core/diag.h` and decisions
log §24. Each value there is marked as either "sheet" or "here" (chosen for
this set).

## The first thing: it is a different fuel system

The sheet's "Actuator" rows are for a fuel rack moved by an electronic
governor, with a position sensor on it: fuel rack position SPN 1210, rack
over-current, "governing actuator stuck" and "sweep stuck". This set is
common rail (Bosch MD1CS162), so none of those rows applies as written. They
map to the metering valve and the rail:

| 20 kVA (rack) | This set |
|---|---|
| Rack position short to battery or ground (1210/3, /4) | Rail pressure sensor high or low (157/3, /4). This already existed |
| Rack actuator over current (2551/6, above 4 A) | Metering valve over current, 1347/6 above 3.0 A. New. The loop holds at most 1.8 A, the closing current (decisions log 27) |
| Engine fuel rack position open (1210/8) | Metering valve open load, 1347/5. New |
| Governing actuator stuck (241/7) | Rail pressure not following its target, 157/7. New |

## Row by row

Mark: **Took** = in the firmware; **DSE** = the DSE4522's job here (this follows Bosch:
the MD1CS162 has no pin for it); **No** = not taken; **Have** = this
firmware already did it.

### EGR (an H-bridge with a position sensor; this set has the same)

| Code | Description | Detection (sheet) | Debounce / heal (sheet) | Here |
|---|---|---|---|---|
| 2791/0 | Valve jammed open | PWM < 5 %, position > 35 %, position voltage < 4470 mV, EGR operating | 20 / 20 loops | **Took** as 2791/0: duty below 5 %, position above 35 %, 1 s / 200 ms |
| 2791/1 | Position sensor source high | position voltage > 4470 mV | 10 / 10 loops | **Have**: SPN 27 FMI 3 above 4.8 V. FMI 1 is not J1939's "voltage high" |
| 2791/2 | Position sensor source low | position voltage < 200 mV | 35 / 35 loops | **Have**: SPN 27 FMI 4 below 0.2 V |
| 2791/5 | Open load | PWM > 20 % and current ≤ 0.1 A | 20 / 13 loops | **Took**: \|duty\| > 20 % and filtered current ≤ 0.1 A, 200 / 130 ms |
| 2791/6 | Over current | current > 6 A | 10 / 10 loops | **Have**: the stall guard, above 5 A for 1.5 s, then coast and retry (sized on this bridge) |
| 2791/14 | Under voltage | battery < 10 V | 3 / 3 | **Took** as a condition: EGR is diagnosed only from 10 to 15 V, with no separate code |
| 2791/17 | Short circuit | current > 6 A | 10 / 10 | **No**: the same condition as FMI 6, so the two can never be told apart |
| 2791/22 | Current limited | current > 6 A | 10 / 10 | **No**: FMI 22 is not a J1939 FMI (0–21 and 31) |
| 2791/31 | Jammed closed | PWM > 95 %, position < 35 % | 20 / 20 loops | **Took** as 2791/7 (J1939's "mechanical system not responding"), duty ≥ 90 % (this bridge tops out at 95 %), 1 s / 200 ms |
| 2802/3, /4 | EGR battery high / low | battery > 15 V / < 10 V | 3 / 3 | **Took** as the 10–15 V window above. Battery faults are 168/16 and /18 |

### Oil pressure (LOP), coolant (ECT), fuel level (FL)

| Code | Description | Sheet | Here |
|---|---|---|---|
| 100/1 | Oil pressure low (shutdown, red) | below 200 (or the switch open), 2 s | **DSE**: we send oil pressure (EFL/P1); the DSE shuts down |
| 601/18 | Low oil pressure warning | below 250, 2 s | **DSE** |
| 100/3, /4, 244/8 | Oil sensor voltage high / low / open | above 4600 mV / below 200 mV | **Have**: SPN 100 FMI 3 / 4 |
| 248/13 | Oil pressure before cranking | above 100, 0.5 s | **Took** as 100/2: above 100 kPa with the engine stopped, 2 s. Above 200 kPa with no crank teeth it is 190/8 instead (see Speed) |
| 110/0, 602/16 | Coolant over temperature 104 °C / warning 100 °C | 2 s | **DSE**: we send coolant temperature (ET1) |
| 110/3, /4, 246/8 | Coolant sensor resistance high / low / open | high: 3 k–20 kΩ, open: above 20 kΩ, low: below 10 Ω | **Have**: SPN 110 FMI 3 / 4. **The sheet's "Res_high" band is doubtful:** 3–20 kΩ is a normal cold reading for an NTC |
| 96/0, /1, /4, 247/8, 603/18 | Fuel level | resistance bands | **DSE** (no fuel level pin on the MD1CS162). **"High fuel level" (700–2800 Ω) is doubtful the same way** |

### Speed

| Code | Description | Sheet | Here |
|---|---|---|---|
| 190/0 | Overspeed (shutdown) | above 1650 rpm, 4 s | **Have**: 1650 rpm trips at once, below the DSE's 1680 / 1710 |
| 190/1 | Underspeed (shutdown) | at or below 1300 rpm, 4 s | **Have** as a warning: 190/18 below 1350 rpm. The DSE decides on frequency |
| 608/16 | High speed warning | above 1590 rpm | **Took** as 190/16, 2 s / 1 s, amber |
| 608/18 | Low speed warning | below 1425 rpm | **No**: the underspeed warning covers it, and droop alone takes the set to 1440 |
| 190/8 | Speed sensor erratic | frequency ≤ 100, OR (frequency 0 and oil > 200) | **Took** the second half only: oil above 200 kPa and no crank tooth for 1 s, 2 s. **The first half fires at standstill** |
| 608/13 | Pre-crank speed | frequency > 50 before cranking | **No**: the state machine already tracks teeth before CRANK |

### Battery, alternator, crank, stop, maintenance

| Code | Description | Sheet | Here |
|---|---|---|---|
| 604/16 | High battery warning | above 14.8 V, 5 s | **Took** as 168/16. This set charges at 14.5–14.6 V (field evidence 14 Oct), so the margin is 0.2 V. Check it on the bench |
| 605/18 | Low battery warning | below 11.9 V, 5 s | **Took** as 168/18, **running only**: cranking pulls any battery below 10 V |
| 158/0, /1 | ECU voltage high / low (shutdown) | above 15 V / below 10 V, 5 s | **No**: a battery is no reason to stop a genset; the DSE has its own battery alarms. **The sheet doesn't limit the low one to running** |
| 167/1, 606/18 | Charging alternator | below 12 V (6 s, shutdown) / 12.7 V | **DSE** (it has the charge-fail input). Our 168/18 covers charging lost while running |
| 252/13 | Crank attempts finished | | **DSE** |
| 970/31 | Emergency stop | pressed 2.5 s | **Have**: pin 25 latches SHUTDOWN at once, and the hardware kill doesn't wait |
| 1000/8, /9, /11 | Oil, air and fuel filter | running hours ≥ 45000 | **DSE**. **The fuel filter row has no variable, and 45,000 hours is not a filter interval** (probably minutes) |

## Mistakes and doubts in the sheet (not copied)

1. **Speed sensor erratic fires at standstill.** "Frequency ≤ 100" is true whenever
   the engine is stopped or cranking.
2. **Low ECU voltage (< 10 V, shutdown) and charging alternator (< 12 V, shutdown)
   are not limited to running.** Both would trip during cranking.
3. **The high and low battery warnings use the shutdown enables**
   (`shut_highBatt_V_enable`, `shut_lowBatt_V_enable`), not warning enables.
   It looks like a copy-paste error.
4. **2791/6, /17 and /22 have one condition** (current > 6 A), so they can't be told
   apart.
5. **Non-standard codes:** FMI 22 does not exist in J1939. Position voltage
   high/low should be FMI 3/4, not 1/2. SPNs 244–252, 601–608, 2802 and 2551
   look like the maker's own; the DSE4522 shows its text from the standard
   table. Check each against J1939-71 before use.
6. **Coolant "Res_high" (3–20 kΩ) and "High fuel level" (700–2800 Ω)** look
   like normal readings. Either they depend on an undocumented "state" value
   or they are mis-transcribed.
7. **Fuel filter:** the condition has no variable, and 45,000 is not hours.
8. **EGR STG healing uses the debounce calibration** (`CAL_Deb_STG`), not a
   healing one.
9. **The debounce counts have no loop time.** They are read here as a 10 ms
   loop.

## Lamps

The sheet's rule (amber: keeps running; red: shuts down) matches this
firmware. Every diagnosis taken from the sheet is **amber** here. The red
shutdowns stay overspeed, crank sync, boost rail and the stop switch, and the
DSE stops the engine on Protect.
