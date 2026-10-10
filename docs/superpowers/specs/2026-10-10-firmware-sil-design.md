# Firmware core + engine simulator (software-in-the-loop) — design

**Date:** 2026-10-10
**Status:** Approved in conversation 2026-10-10; this is the written form.
**Parent:** `2026-09-13-ecu-reconciled-spec-design.md` (phase 4, "firmware skeleton").

---

## 1. Purpose

The hardware design is complete to schematic, with 26 circuit blocks
passing. No firmware exists yet. A competing team already runs firmware
on a board wired to an Arduino that fakes the engine signals.

This phase closes that gap in the order that costs least:

1. **Now (this spec):** the engine-control firmware as portable C, run on
   the PC against a Python engine simulator. Every control and safety
   function is proven before any hardware exists.
2. **Next (its own spec):** the same core on an NXP S32K148 evaluation
   board, with an Arduino generating the engine signals — the competitor's
   setup, with control logic already proven.
3. **Later:** the same core on our own PCB.

**Success:** the scenario suite in §7 passes on the PC, run by one command,
in the same PASS/FAIL style as `sim/run_sim.py`.

## 2. Decisions taken in conversation

| Decision | Choice |
|---|---|
| Approach | C: PC simulation now, dev kit next |
| Connector | The Bosch 94-pin stays (affects pin mapping in the dev-kit spec, not this one) |
| Crank wheel | **60-2** (assumed — Bosch EDC17 standard; one constant to change) |
| Cam | **1 pulse per 720°** (assumed) |
| Firing order | **1-2-3**, 240° apart (assumed). Bank A = cylinders 1 and 3, bank B = cylinder 2 (spec §2.1) |
| Overspeed trip | **1650 rpm**, latched — below the DSE4522's 1680 rpm over-frequency and 1710 rpm CAN overspeed (spec §3) |
| Governor | Isochronous at 1500 rpm; droop switch (pin 23) selects **4 %** droop (assumed) |
| Calibration | Placeholder maps only; real maps are out of scope (spec §9) |

## 3. Architecture

```
firmware/
  core/            portable C99, no hardware, no OS, no heap
    ecu.h          the whole interface: ecu_io struct + 4 functions
    ecu.c          state machine, scheduling of the loops below
    crank.c/.h     60-2 decoder: sync, rpm, angle, cylinder phase
    inject.c/.h    per-cylinder injection commands from angle + fuel
    govern.c/.h    speed PI with droop, fuel limit
    rail.c/.h      rail-pressure PI on the metering-unit duty
    sensors.c/.h   volts -> engineering units, range checks
    safety.c/.h    overspeed, sync loss, ignition, latch, watchdog kick
    j1939.c/.h     EEC1, ET1, EFL/P1, DM1 frame building
  sim/
    Makefile       builds core into libecu.dylib / .so with the host cc
    engine.py      the engine + generator + rail + sensor model
    ecu.py         ctypes wrapper around libecu
    run_sil.py     scenarios and PASS/FAIL checks
```

**The interface is a struct, not callbacks.** `ecu_io` holds every input
(sensor volts, switch levels, edge timestamps) and every output
(injection commands, metering duty, relay states, CAN frames out, fault
flags). The simulator fills inputs and reads outputs; the S32K148 port
will do the same from its peripherals. Nothing in `core/` includes a
hardware header, so the core compiles and runs identically on both.

```c
void ecu_init(ecu_io *io);
void ecu_crank_edge(ecu_io *io, uint32_t t_us);   /* falling edge of a tooth */
void ecu_cam_edge(ecu_io *io, uint32_t t_us);
void ecu_tick_1ms(ecu_io *io, uint32_t t_us);      /* slow loops, CAN, safety */
```

Injection is output as **commands**, not pin levels: for each cylinder, a
start time and a duration, as a timer's output-compare would execute them.
The simulator integrates fuel exactly from those; the dev kit will load
them into FTM channels. This keeps simulation steps coarse without
quantising fuel.

## 4. Firmware functions

### 4.1 Crank and cam

- 60-2 wheel: the gap is the tooth whose period exceeds 1.5× the previous
  one. Sync is declared after two consecutive gaps 58 teeth apart.
- The cam pulse picks which of the two revolutions is the compression
  stroke of cylinder 1. Until it arrives, no injection.
- rpm from the period of the last 6 teeth; angle by interpolating within
  the current tooth.
- **Loss of sync** (a gap in the wrong place, or no edge for 100 ms while
  running) is a fault: injection stops, state goes to SHUTDOWN.

### 4.2 State machine

```
OFF --ignition on--> WAIT --crank edges--> CRANK --sync + 400 rpm--> RUN
any --overspeed / sync loss while running / ignition off--> SHUTDOWN
SHUTDOWN --ignition off then on--> OFF
```

SHUTDOWN is latched: all injection commands cleared, metering output off,
fault active on DM1. Only an ignition cycle clears it.

### 4.3 Injection

One main injection per cylinder per cycle. Start of injection at a fixed
placeholder angle, 5° BTDC. Duration from the fuel demand through a
placeholder map: `t_us = dead_us + fuel_mg / flow(rail_bar)`. While
cranking, a fixed start fuel.

### 4.4 Governor

PI on speed error, output = fuel per injection (mg), clamped to
`[0, fuel_max]`. Setpoint 1500 rpm; with the droop switch closed the
setpoint falls 4 % from no load to full fuel. Anti-windup by clamping
the integrator.

### 4.5 Rail pressure

PI on rail pressure error drives the metering-unit duty. Setpoint a
placeholder constant (1000 bar). The metering unit is treated as
**normally open** (inlet metering): more duty, less flow. Duty is zero
in SHUTDOWN — the engine stops because injection stops, and the trip
module removes the metering unit's supply independently (spec §3).

### 4.6 Safety (highest priority)

Evaluated on **every crank edge** as well as every 1 ms tick:
- rpm > 1650 → SHUTDOWN. Injection commands for pending cylinders are
  cancelled in the same call, so at most the injection already open
  completes.
- Sync loss while running → SHUTDOWN.
- Ignition input low → SHUTDOWN (normal stop, no fault code).
- Watchdog: `ecu_tick_1ms` toggles a kick output every tick. The simulator
  checks the kick period stays inside the supervisor's window.

### 4.7 Sensors

Volts → units for coolant temperature (NTC table), oil pressure, rail
pressure, boost pressure and EGR position. The ratiometric channels are
corrected by the measured 5 V sensor rail (spec §4). Each channel has a
valid range; outside it for 100 ms raises a fault with its J1939
SPN/FMI (FMI 3 high, FMI 4 low), and the value is replaced by a safe
default.

### 4.8 J1939 to the DSE4522

Source address **234**. 29-bit ID = priority << 26 | PGN << 8 | SA.

| PGN | Name | Rate | Content |
|---|---|---|---|
| 61444 (0xF004) | EEC1 | 20 ms | SPN 190 engine speed, 0.125 rpm/bit, bytes 4–5 |
| 65262 (0xFEEE) | ET1 | 1 s | SPN 110 coolant temperature, 1 °C/bit, −40 offset, byte 1 |
| 65263 (0xFEEF) | EFL/P1 | 500 ms | SPN 100 oil pressure, 4 kPa/bit, byte 4; SPN 111 coolant level, 0.4 %/bit, byte 8 |
| 65226 (0xFECA) | DM1 | 1 s | active faults (SPN, FMI, occurrence count); single-frame if one fault, else BAM |

Unavailable values are sent as 0xFF per J1939. The exact PGN set the
DSE expects is still open (U4); this table is the J1939-71 standard set.

## 5. Engine simulator

All parameters are assumed and marked in `engine.py`.

- **Rotation:** one inertia (engine + alternator rotor, ~2 kg·m²).
  Torque = indicated torque from each injection − friction(rpm) − generator
  load. Indicated torque is applied per combustion event in the 180° after
  TDC, so the speed ripple the decoder sees is realistic.
- **Starter:** drives the crank to 150 rpm while cranking is requested.
- **Generator load:** electrical kW, settable at any time (0–25 kVA at
  0.8 pf = 20 kW).
- **Rail:** pump flow ∝ rpm × (1 − metering duty); out = injected fuel +
  leakage; pressure from a bulk-modulus volume model; relief at 1800 bar.
- **Sensors:** coolant warms first-order towards a load-dependent
  temperature; oil pressure ∝ rpm; boost ∝ load; each produced as the
  volts the front-end would deliver.
- **Signals:** a 60-2 crank edge every tooth, a cam edge per 720°.
- **Fault injection:** sensor open/short, stuck fuel (fixed injection
  regardless of command — a runaway), crank signal lost, CAN frames logged
  for checking.

Time advances in 20 µs steps. Each step: integrate the engine, call
`ecu_crank_edge`/`ecu_cam_edge` when an edge falls inside the step, call
`ecu_tick_1ms` every 1 ms, and apply injection commands as they mature.

## 6. Error handling

The core never allocates, never blocks, and never trusts an input:
every sensor is range-checked (§4.7), every timing input is checked
against sync (§4.1), and every failure ends in the latched SHUTDOWN
state or a substituted default with a DM1 fault. There is no recovery
path that restores injection without an ignition cycle.

## 7. Scenarios that must pass

| # | Scenario | Pass when |
|---|---|---|
| 1 | Start | sync within 2 revolutions of cranking; 1500 rpm ± 1 % within 5 s |
| 2 | Load step 0 → 20 kW | dip < 10 %, back inside ± 1 % within 5 s |
| 3 | Load rejection 20 → 0 kW | overshoot stays below the 1650 rpm trip |
| 4 | Droop switch | steady speed falls 4 % ± 1 % at full load |
| 5 | Runaway (stuck fuel) | SHUTDOWN at 1650 rpm; no new injection command after the trip edge |
| 6 | Crank signal lost while running | SHUTDOWN within 100 ms |
| 7 | Ignition off | SHUTDOWN, no fault code; engine stops |
| 8 | Coolant sensor open | DM1 carries SPN 110 FMI 3 within 1.2 s; engine keeps running |
| 9 | CAN content | EEC1 every 20 ms ± 2 ms with speed within 0.5 %; ET1, EFL/P1, DM1 at their rates |
| 10 | Rail pressure | inside ± 5 % of setpoint in steady running |
| 11 | Watchdog | kick period inside the supervisor window throughout |

## 8. Out of scope for this spec

- Injector peak/hold current regulation (chip timers, comparators): dev-kit spec.
- Pilot and post injections; real calibration maps.
- The S32K148 HAL, the Arduino engine faker, the dev-kit wiring: next spec.
- EGR closed-loop control: position sensing only for now, the valve held
  closed. Added when the plant model is worth having.

## 9. Toolchain

Host C compiler (Apple clang, already installed) builds the shared
library; Python 3 with numpy, both already in `.venv`. No new
dependencies. The S32K148 port will add `arm-none-eabi-gcc`.
