# The ECU application in Simulink and Stateflow

The control and state logic of the firmware, as models that Embedded Coder
turns into the C that runs on the ECU. Design: `docs/superpowers/specs/2026-11-13-simulink-model-design.md`.

## What is here

| Model | Kind | Replaces (hand-written reference) |
|---|---|---|
| `ecu_mode` | Stateflow | the engine state machine: OFF → WAIT → CRANK → RUN, any → SHUTDOWN, RESET → OFF (`mode.c` `mode_cmd`) |
| `ecu_boostg` | Stateflow | boost-rail overvoltage guard: trip once, latched (`boostg_step`) |
| `ecu_egrg` | Stateflow | EGR stall guard: coast, retry, lock out (`egrg_step`) |
| `ecu_wifg` | Stateflow | water-in-fuel debounce (`wifg_step`) |
| `ecu_underg` | Stateflow | underspeed warning (`underg_step`) |
| `ecu_relay` | Stateflow | main relay and after-run (`relay_step`) |
| `ecu_gov` | Simulink | speed governor, PI with droop and start ramp (`govern.c`) |
| `ecu_rail` | Simulink | rail-pressure PI on the metering valve (`rail.c` `rail_step`) |
| `ecu_railset` | Simulink | rail setpoint table (`rail_set_bar`) |
| `ecu_soi` | Simulink | start-of-injection table (`inject_soi_btdc`) |
| `ecu_injdur` | Simulink | injector law, fuel → energising time (`inject_dur_us`) |
| `ecu_safety` | Simulink | the trip decision (`safety_check`) |
| `ecu_app` | Simulink | **all of the above, closed loop with an engine**: start, load step, stop switch |

`ecu_app` references the component models themselves (Model blocks), so
what you simulate is what the code is generated from. Its sequencer
(the order `ecu.c` drives the state machine in) and its mean-value
engine (the constants of `firmware/sim/engine.py`) are simulation-only.

**Not modelled, on purpose:** crank-tooth decoding, the per-tooth
injection scheduling, J1939, UDS, flash storage and the bootloader.
They stay hand-written C in `firmware/core`: they are event- and
byte-driven, and already tested.

## Open and simulate

In MATLAB, from this folder:

```matlab
addpath(pwd, fullfile(pwd, 'lib'), fullfile(pwd, 'test'))
open_system ecu_app        % or any ecu_*.slx
sim_ecu_app                % runs it, checks it, writes test/ecu_app_sim.png
```

## Change something

The `.slx` files are **built by scripts**: edit `mdl_<name>.m`, never the
model, then:

```matlab
build_all({'ecu_gov'})     % or build_all() for every model
gen_code({'ecu_gov'})      % C into firmware/gen/ecu_gov/
```

Constants are not typed here. `ecu_params.m` reads them from the
firmware's headers and tables (`govern.h`, `rail.c` ...), so a
calibration change is made once, in the C, and reaches the models on the
next `build_all`. The generated C is committed, so the firmware builds
without MATLAB.

Code generation settings (`lib/mb.m`): ERT, reusable functions with root
I/O as arguments, inlined parameters, single precision, ARM Cortex-M,
utilities in `firmware/gen/shared/`.

## How the firmware uses it

Build the firmware with `ECU_MODEL` defined and `firmware/gen/*` on the
include path (`make test-model` in `firmware/sim`). Then
`firmware/core/model_glue.c` provides `gov_step`, `rail_step`,
`mode_cmd`, `boostg_step` ... from the generated code, with the same
API, and the hand-written bodies drop out. Without `ECU_MODEL` the
hand-written reference is built, as before.

## How it is proven

| Test | What it shows |
|---|---|
| `firmware/sim` unit tests, built with `ECU_MODEL` | every firmware unit test passes on the generated code |
| SIL scenarios, `ECU_LIB=libecu_model` | the 16 engine scenarios pass on it |
| `test/run_b2b.sh` | each generated model against its hand-written C, on millions of random inputs: the PI loops, injector law, trip decision and all six charts agree **exactly**; the two tables within one or two units in the last place |
| `test/sim_ecu_app.m` | the closed loop in Simulink meets the SIL scenarios' limits |

The tables differ in the last place because Simulink's interpolation
orders its arithmetic differently from `table.h`. The back-to-back test
builds with `-ffp-contract=off`: with fused multiply-add the compiler,
not the model, can move a result by one unit in the last place.

## Flashing it

The generated code is ordinary C99 in the firmware tree. It is flashed
as part of the firmware image, built with `ECU_MODEL`, by the same
route as the hand-written build: ST-LINK on the prototype's SWD header,
or the UDS bootloader over CAN or USB.

**What still stands in the way is not the model.** The STM32 chip layer
(ADC, timers, CAN, USB, flash drivers) is not written yet, for either
build. Until it is, no firmware image can run on the board. The model
code is cross-compiled for the Cortex-M4F as a check that it is
target-ready (see `docs/firmware.md`).
