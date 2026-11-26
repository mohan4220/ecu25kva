# SOP — Learning the Simulink model

**For:** an engineer joining the project who knows basic MATLAB and Simulink
and needs to understand, change and trust this ECU's models.
**Time:** about a day, in eight lessons. Each ends with an exercise; do it,
because the exercises are where the model starts to make sense.

The reference for every model and button is `model/README.md`. This is the
learning path through it.

---

## Before you start

- **MATLAB R2026a** with Simulink, Stateflow, Simulink Coder and Embedded
  Coder. The licence here is academic: everything you generate says so, and
  is for learning and bench work only. Before any commercial use the code
  is regenerated under a commercial licence (decisions log §40).
- The repository, and `./verify.sh` passing on your machine (SOP §6). If it
  does not pass, fix that first: every lesson below compares against it.
- In MATLAB, once per session:
  ```matlab
  cd C:\Users\<you>\ecu25kva\model
  addpath(pwd, fullfile(pwd,'lib'), fullfile(pwd,'test'))
  ```

## The one idea to hold

The ECU that is flashed runs **code generated from these models**
(`app_model`), plus a small amount of hand-written C around them. Four
things keep that honest:

```
 firmware/core/*.h        the numbers: every gain, limit and table
        │  ecu_params.m reads them
        ▼
 model/mdl_ecu_*.m  ──▶  model/ecu_*.slx  ──Embedded Coder──▶  firmware/gen/ecu_*/   ──▶  app_model
   (scripts that lay       (the models you      (the C on the chip,
    a model out)            open and edit)        committed)
        ▲                                                │
        └──── firmware/core/*.c: the hand-written reference ◀── b2b: equal on millions of inputs
```

1. **The C headers are the single source of every number.** A model never
   holds its own copy of a calibration.
2. **Each model has a hand-written C twin**, compiled when `ECU_MODEL` is
   off. The back-to-back test (b2b) holds them equal.
3. **`model_glue.c`** connects each model to the firmware's C API, so the
   rest of the firmware and every test cannot tell which build it runs.
4. **The top model `ecu25kva.slx` is a simulation harness.** It is never
   code-generated; it runs the same component models against a simulated
   engine.

---

## Lesson 1 — The top model, and one run

**Open:** `open_system ecu25kva`

**Look at the five areas, left to right:**

| Area | What it is |
|---|---|
| Buttons (green) | Generate code, Build firmware, Bootloader, Flash, Clean, Run all checks, Simulate, Select_PCB |
| TRIGGERS | a Stateflow chart firing the firmware's tasks: initialisation, the cylinder event, 1 ms, 20 ms, 500 ms, 1 s, 10 s |
| MODEL (cyan) | the ECU: each task is a function-call subsystem holding the component models as Model blocks |
| PLANT (light blue) | the engine and generator, the fuel rail, the metering coil, the sensor voltages: simulation only |
| SCENARIO | ignition, the 20 kW step, the stop switch, and the profiles: battery, coolant temperature, 100 V boost rail, coolant level |

**Do:** double-click **Simulate**. It runs four times and prints 44 checks:

- run 1: start, 1500 rpm, 20 kW at 8 s, stop switch at 16 s;
- run 2: battery 9.2 V, the coolant-level switch open, the coolant rising
  past 100 °C and 104 °C until Protect shuts the set down;
- run 3: the metering current reading lost (the set runs on the
  feedforward) and the 100 V boost rail at 110 V (shutdown in 20 ms);
- run 4: the crank signal lost while running (shutdown at once).

Open `model/test/ecu25kva_sim.png`: speed, engine mode, fuel and rail.

**Exercise.** From the printed checks, answer: when does the engine reach
RUN? When does the coolant stop (110/0) fire, and why exactly then?
(Answer: about 1.1 s; 16.43 s, which is 2 s after the ECU's own reading
passed 104 °C — the debounce time in `diag.c`.)

## Lesson 2 — Follow one signal end to end

The best way in is to trace the coolant temperature from the engine to the
shutdown. Open each block as you go.

1. **SCENARIO `clt_degc`** — a lookup against time: flat 85 °C in run 1,
   a ramp to 106 °C in run 2.
2. **PLANT → `Sensors`** — turns °C into the volts pin 33 would see,
   through Bosch's NTC table, the 2.49k pull-up and the 100k/160k divider.
3. **MODEL → `one_ms_task` → `sensors`** (`ecu_sensors`) — volts back to
   °C; a range fault if the input is open or shorted.
4. **`diag`** (`ecu_diag`) — 14 conditions. Number 13 is "coolant over
   104 °C"; number 12 "over 100 °C".
5. **`deb_clt_stop`** (`ecu_deb`) — the condition must hold 2000 ticks
   before it is a fault, and heals on its own time.
6. **`protect`** — fault 13 is the Protect lamp.
7. **Top level `DSE_ignition`** — the stand-in for the DSE4522: Protect
   drops the ignition, and the engine-mode chart goes to SHUTDOWN.

**Exercise.** Run run 2 yourself: copy the `in2 = ...` lines and
`out2 = sim(in2)` from `model/test/sim_ecu25kva.m` into the command window,
then plot fault 13 against the mode:
```matlab
act = out2.get('dg_act'); md = out2.get('mode');
plot(act.Time, double(act.Data(:,13)), md.Time, double(md.Data)/4)
```
Then find, in `firmware/core/diag.h`, the line that sets 104 °C.

## Lesson 3 — Reading a component model

There are two kinds.

**Simulink with a MATLAB Function block** (most of them: `ecu_gov`,
`ecu_diag`, `ecu_crank` …). Open `ecu_diag.slx`, double-click `cond`. You
see plain MATLAB, each line mirroring `diag.c`. Note the habits:

- every number is `single(...)`; there is no `double` arithmetic anywhere,
  because the chip's image check forbids double-precision routines;
- loop indices are `int32`, for the same reason;
- the thresholds were written in by the script from `diag.h`; they are not
  typed in the model.

**Stateflow charts** (`ecu_mode`, `ecu_deb`, the six guards, `ecu_spdst`,
`ecu_relay`). Open `ecu_deb.slx`: two states, CLEAR and ACTIVE, and two
transitions with counters. Then open `ecu_mode.slx`: OFF, WAIT, CRANK, RUN,
SHUTDOWN.

**Stateless models with their state passed in and out.** `ecu_musup`
(the metering-valve supervision) and `ecu_crank` (the crank decoder) take
their state as inputs and return the new state as outputs. The C keeps it
in a struct. That keeps the struct identical in both builds and makes the
proof simple.

**Exercise.** In `ecu_deb`, work out by hand what `act` does for a
condition that is true for 1999 ticks, false for 1, then true for 2000.
Check your answer against `deb_step` in `firmware/core/mode.c`.

## Lesson 4 — From model to the C on the chip

**Do:**

```matlab
gen_code({'ecu_diag'})
```

Open `firmware/gen/ecu_diag/ecu_diag.c` beside `firmware/core/diag.c`. The
same comparisons, in the same order, the thresholds as literals.

Then open `firmware/core/model_glue.c` and find `diag_cond`: with
`ECU_MODEL` defined, the firmware's `diag_cond()` calls
`ecu_diag_step()`. In `diag.c` the hand-written body sits inside
`#ifndef ECU_MODEL`. That one switch decides which build you get:

| Build | How | Used for |
|---|---|---|
| hand-written | no `ECU_MODEL` | the reference |
| model-generated | `-DECU_MODEL` | **the board** (`app_model`), and the PC tests run on it too |

**Exercise.** List three functions whose bodies are switched by
`ECU_MODEL`, and name the model that replaces each. (`grep -n "ifndef
ECU_MODEL" firmware/core/*.c` gets you started.)

## Lesson 5 — How it is proven

```sh
sh model/test/run_b2b.sh          # in Git Bash, from the repository
```

Every model is run against its C twin on millions of inputs, and each line
must say `largest difference 0`. The good tests aim at the edges: a third
of the diagnosis inputs sit exactly on a threshold or one float step either
side, and the crank test drives a wheel with noise, missing teeth, stalls
and the clock wrapping.

**A test that cannot fail proves nothing.** Each model was checked by
breaking a copy of its C on purpose (decisions log §40, §41).

**Exercise (do it on a copy, never on the real file):** copy
`firmware/core/diag.c` to a scratch folder, change the coolant stop's `>`
to `>=`, build b2b against the copy (the command in `run_b2b.sh`, with the
copy's path), and see the diagnosis line FAIL. Delete the copy.

## Lesson 6 — Changing a calibration, the safe way

Example: the coolant warning from 100 °C to 98 °C. **Practise on a branch.**

1. Change `DG_CLT_WARN_C` in `firmware/core/diag.h`. **Nothing else holds
   that number.**
2. Rebuild the model from its script and regenerate its code:
   ```matlab
   build_all({'ecu_diag'}); gen_code({'ecu_diag'})
   ```
3. `./verify.sh --matlab`. b2b still passes (both sides moved together);
   the Simulate check for the coolant warning now fires earlier — the check
   computes its expected time from the ECU's own reading, so it still passes,
   and you can see the new time in its printout.
4. Write the reason in `docs/decisions-log.md`.

**Two rules here that save days:**

- **`build_all` rebuilds a model from its script and erases edits made in
  Simulink.** If you edited a model by hand, change its `mdl_*.m` script to
  match, or don't use `build_all` on it.
- **Never edit `firmware/gen/` by hand.** It is overwritten by the next
  `gen_code`.

**Exercise.** Do the 98 °C change on a branch, find the new warning time in
the Simulate output, then throw the branch away.

## Lesson 7 — Adding a model (the recipe)

`ecu_diag` (§40) and `ecu_musup` (§41) were added this way; read their
commits alongside.

1. **The C API in a header** (`diag.h`, `actuate.h`): one function, its
   inputs and outputs, and a comment saying which model replaces it.
2. **The reference body in the `.c`**, inside `#ifndef ECU_MODEL`. Run the
   unit tests: the refactor alone must change nothing.
3. **The model script `model/mdl_ecu_<name>.m`**: a MATLAB Function block
   built with `mb` and `mfun` (`model/lib/`), every number from `P`.
4. **Register it**: `model/model_list.m`, and any new constant in the
   `need` list of `model/ecu_params.m` (a missing one then fails loudly).
5. `build_all({'ecu_<name>'}); gen_code({'ecu_<name>'})`, then read the
   generated C.
6. **Glue** in `firmware/core/model_glue.c`.
7. **Prove it** in `model/test/b2b.c`: random inputs, edges, NaN, every
   branch counted; then break a copy and see it fail.
8. If it belongs in the simulation, add it to `mdl_ecu25kva.m` and a check
   to `sim_ecu25kva.m`.
9. `./verify.sh --matlab`, the decisions log, `model/README.md`, the SOP.

## Lesson 8 — The traps (each one has happened here)

| Trap | What goes wrong | Do instead |
|---|---|---|
| a `double` in a model | the chip image fails its check (double-precision routines) | `single(...)` everywhere; `int32` loop indices |
| `int64` in a model | this target has no native 64-bit: Embedded Coder emits slow "multiword" helpers | do the arithmetic in 32 bits (see `since()` in `mdl_ecu_crank.m`) |
| unsigned subtraction | MATLAB saturates at 0; C wraps | branch on which is larger, as `since()` does |
| integer division | MATLAB rounds; C truncates | `idivide(a, b, 'floor')` |
| a counter past 255 | MATLAB `uint8` saturates; C wraps | `mod(int32(x) + 1, 256)` |
| `\b` in a MATLAB regex | not supported | `\<` and `\>` |
| `setBlockParameter` with two parameters | "Not enough input arguments" | repeat the block path before each parameter |
| editing an `.slx`, then `build_all` | your edit is gone | change the `mdl_*.m` script |
| an interrupt path as a model | the call and the state packing add microseconds | keep microsecond interrupts in C (the injector stage, §41) |

---

## Where things are

| Path | What |
|---|---|
| `model/ecu25kva.slx`, `mdl_ecu25kva.m` | the top model and its script |
| `model/ecu_*.slx`, `mdl_ecu_*.m` | the 27 component models and their scripts |
| `model/model_list.m` | which models exist, in build order |
| `model/ecu_params.m` | reads every constant from `firmware/core` |
| `model/build_all.m`, `gen_code.m`, `ecu_project.m` | build, generate, the buttons |
| `model/lib/` | `mb` (model building), `mfun` (MATLAB Function blocks), `sfb` (Stateflow) |
| `model/test/b2b.c`, `run_b2b.sh` | the back-to-back proof |
| `model/test/sim_ecu25kva.m` | the four closed-loop runs and their 44 checks |
| `firmware/gen/` | the generated C (committed; never edit) |
| `firmware/core/model_glue.c` | the models behind the firmware's API |
| `docs/decisions-log.md` §40, §41 | why each part is a model, or is not |

## You know the model when you can

- [ ] say which build is flashed, and what the other one is for;
- [ ] trace the coolant temperature from the plant to the DSE's shutdown;
- [ ] read a MATLAB Function block and a Stateflow chart and find their C twins;
- [ ] change a calibration so that the header, the model, the code and the proof all agree;
- [ ] break a copy and watch b2b catch it;
- [ ] name four traps from Lesson 8 and how each is avoided.
