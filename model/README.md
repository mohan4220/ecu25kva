# The 25 kVA ECU in Simulink and Stateflow

The ECU's application as models that Embedded Coder turns into the C the
board runs. Open **`ecu25kva.slx`**: it is the whole ECU in one model,
and its buttons generate the code, build the firmware and flash the board.

**Licence.** The MATLAB here is an academic licence, and every generated
file says so. This is for learning and bench testing. Before any
commercial use, regenerate the code under a commercial MATLAB, Simulink
and Embedded Coder licence and run `./verify.sh --matlab` again.

## `ecu25kva.slx`

```
 [Generate code] [Build firmware] [Bootloader] [Flash (ST-LINK)] [Flash (J-Link)]
 [Clean project] [Run all checks] [Simulate]   [Select_PCB ▾]    [software 0x0100]

 TRIGGERS ──────────────▶ MODEL ──────────────────────────────▶ PLANT (simulation only)
 initialisation            initialisation   trims
 cyl_event_isr             cyl_event_isr    ecu_soi, ecu_injdur
 one_ms_task               one_ms_task      ecu_sensors, ecu_safety, ecu_mode, ecu_gov,
                                            ecu_railset, ecu_rail, six guards
 twenty_ms_task            twenty_ms_task   Set PGNs (ecu_j1939), send EEC1
 five_hundred_ms_task      ...              send EFL/P1
 one_sec_task                               send ET1, the engine-hours count
 ten_sec_task                               send HOURS
```

- **TRIGGERS** is a Stateflow chart sending function-call events at the
  firmware's own rates. `cyl_event_isr` stands in for the crank-tooth
  interrupt, with one event per cylinder, because the plant has no teeth.
- **MODEL** holds the component models themselves, as Model blocks. What
  you simulate is what the code is generated from. The sequencer inside
  `one_ms_task` reproduces the order `ecu.c` sends the state machine its
  commands. It runs only in simulation; on the board, `ecu.c` does it.
- **PLANT** is the engine and generator: a mean-value model with
  `firmware/sim/engine.py`'s constants. It also models the rail, and the
  sensor voltages that the ECU then converts back.

### The buttons (double-click; each is also `ecu_project <action>`)

| Button | Does |
|---|---|
| Generate code | C from every component model into `firmware/gen/` |
| Build firmware | generate, then `firmware/stm32/build.py` and the image checks |
| Bootloader | build, then flash `boot.hex` and the application over SWD |
| Flash (ST-LINK) / (J-Link) | flash `app_model_signed.hex`, the code from these models |
| Clean project | delete the build folders (the committed `firmware/gen` stays) |
| Run all checks | `./verify.sh` |
| Simulate | `sim_ecu25kva`: run it closed loop and check it (20 checks) |
| Select_PCB | prototype STM32G474 (builds) or production S32K148 (no chip layer yet) |

Errors from code generation, the compiler, the image checks or the probe
go to the command window and to a dialog.

## The component models

| Model | Kind | Replaces (hand-written reference) |
|---|---|---|
| `ecu_sensors` | Simulink | volts to units, the 5 V correction, end-of-line trims, debounced range faults (`sensors.c`) |
| `ecu_safety` | Simulink | the trip decision (`safety_check`) |
| `ecu_mode` | Stateflow | the engine state machine: OFF, WAIT, CRANK, RUN, SHUTDOWN (`mode.c` `mode_cmd`) |
| `ecu_gov` | Simulink | speed governor, PI with droop and start ramp (`govern.c`) |
| `ecu_railset` | Simulink | rail setpoint table (`rail_set_bar`) |
| `ecu_rail` | Simulink | rail-pressure PI on the metering valve (`rail.c`) |
| `ecu_soi` | Simulink | start-of-injection table (`inject_soi_btdc`) |
| `ecu_injdur` | Simulink | injector law, fuel to energising time (`inject_dur_us`) |
| `ecu_boostg` | Stateflow | boost-rail overvoltage trip, latched (`boostg_step`) |
| `ecu_boostm` | Stateflow | boost-rail warnings, high and low (`boostm_step`) |
| `ecu_egrg` | Stateflow | EGR stall: coast, retry, lock out (`egrg_step`) |
| `ecu_wifg` | Stateflow | water-in-fuel debounce (`wifg_step`) |
| `ecu_underg` | Stateflow | underspeed warning (`underg_step`) |
| `ecu_relay` | Stateflow | main relay and after-run (`relay_step`) |
| `ecu_j1939` | Simulink | the J1939 PGNs' data: EEC1, ET1, EFL/P1, HOURS (`j1939.c`) |
| `ecu_mucur` | Simulink | metering valve current loop, the inner stage of rail → current → PWM (`actuate.c` `mu_step`) |
| `ecu_egrpos` | Simulink | EGR valve position PID, derivative on the measurement (`egrp_step`) |
| `ecu_spdst` | Stateflow | speed states: OFF, IDLE, OPERATING, STEADY; the governor's idle input (`spdst_step`) |
| `ecu_sensaux` | Simulink | pin 79, charge-air temperature: the coolant's NTC table and front end, its own range fault (`sens_aux_step_1ms`, decisions log 33/34) |
| `ecu_deb` | Stateflow | a fault's debounce and healing, one chart with an instance per diagnosis: the 11 engine-side diagnoses of `diag.h` (`deb_step`) |

They have no rate of their own (sample-time independent). They take the
rate of whatever task calls them.

**What stays hand-written C, on purpose:** the parts that are driven by
events or bytes: crank-tooth decoding and per-tooth injection timing,
the fault memory and event log, the DM1/DM2/DM4 transport and requests,
the diagnoses' conditions (`diag.c`, plain comparisons: their timing is `ecu_deb`),
UDS, ISO-TP, the bootloader, flash storage, and the chip drivers
(`firmware/stm32`). They are already tested; a model would add nothing.

## Changing something

**Edit the models in Simulink** (any `ecu_*.slx`), save, then press
**Generate code** and **Build firmware**. Then **Run all checks**:
- **The back-to-back test** compares every model with its hand-written
  reference. If you changed behaviour on purpose, it reports the
  difference. Then change the C reference to match, or retire it.
- **The scenarios** check the engine still starts, holds 1500 rpm and stops.

Constants come from the firmware's C headers (`ecu_params.m`) when a model
is built from its script (`mdl_<name>.m`). The scripts lay a model out
from scratch: running `build_all` **overwrites edits made in Simulink**,
so use it only to start a model over.

Code generation (`lib/mb.m`): ERT, reusable functions with root I/O as
arguments, inlined parameters, single precision, ARM Cortex-M, C99,
utilities in `firmware/gen/shared/`. The generated C is committed, so the
firmware builds without MATLAB.

## How it is proven

`./verify.sh` runs all of this except the Simulink run; `--matlab` adds it.

| Test | What it shows |
|---|---|
| `firmware/sim` unit tests, built with `ECU_MODEL` | every firmware unit test passes on the generated code |
| SIL scenarios, `ECU_LIB=libecu_model` | the 16 engine scenarios pass on it |
| `test/run_b2b.sh` | each generated model against its hand-written C, on millions of random inputs. The PI loops, injector law, trip decision, all six charts, the sensor conversion, the J1939 bytes, both cascade loops and the speed states agree **exactly**; the two tables within one or two units in the last place |
| `test/sim_ecu25kva.m` | the whole model, closed loop: start, load, stop, the sensor chain, the injection, the J1939 frames |
| `firmware/stm32/test_image.py` | the image built from this code is one the bootloader accepts |

The tables differ in the last place because Simulink's interpolation
orders its arithmetic differently from `table.h`. The back-to-back test
builds with `-ffp-contract=off`, because with fused multiply-add the
compiler, not the model, can move a result by one unit in the last place.

## Flashing it

**Build firmware** produces `firmware/stm32/build/app_model_signed.hex`:
these models' code plus the hand-written C and the STM32 chip layer.
Flash it with **Flash (ST-LINK)** or **Flash (J-Link)**, or over USB or
CAN with the service tool (`firmware/stm32/README.md`). It has been
compiled, linked and checked on the PC; it has not yet run on a board.
