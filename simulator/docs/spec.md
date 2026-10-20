# ECU simulator, mode 1 (firmware only): design

Date: 2026-10-20. Branch `simulator`, cut from `firmware-service` (b97c836).
Status: draft for the owner's review.

## 0. Purpose

One program, `ecusim`, that runs the real firmware core (`firmware/core`,
unchanged C) against an engine model, live or from a script, and shows
everything in a browser. It is written for two people:

- the owner, on a Mac, changing the firmware and checking what it does;
- a friend on Windows, who downloads one `.exe`, double-clicks it and
  works in the browser. No Python, no compiler, no install.

Success means:

1. The 16 SIL scenarios run as scripts in `ecusim` and pass on Windows,
   macOS and Linux.
2. A person can start the engine, change load, inject a fault and watch
   speed, rail, DM1 and CAN react, at real speed or faster.
3. Scenarios and firmware builds are loaded from the browser.
4. Every run leaves a folder that says what happened and which firmware
   did it.

This is mode 1 of three (spec context: owner, 20 Oct). Mode 2 (prototype
board fed over USB) and mode 3 (bench rig) are later projects; nothing
here blocks them, and the engine model is kept free of I/O so a later
bench microcontroller can run it.

The Python SIL (`firmware/sim/run_sil.py`, `test_core.c`) stays as the
firmware's own regression gate. It checks some claims (sync edge count,
watchdog periods, CAN rates, the NVM image byte by byte) that the script
language below does not express. `ecusim` does not replace it.

## 1. Layout

```
simulator/
  Cargo.toml              workspace
  crates/plant/           engine, generator, rail, sensors, faults. No I/O.
  crates/sim/             firmware binding, the loop, scripts, checks, run folders
  crates/ecusim/          the binary: CLI, HTTP server, embedded UI
    ui/                   index.html, app.js, app.css, uPlot (vendored, MIT)
  crates/fwbuild/         builds firmware/core as a dynamic library
  scenarios/              the .seq library, embedded in the binary
    sil/                  the 16 SIL scenarios
    faults/               one per fault kind, for demonstration
  docs/spec.md            this file
  README.md               the user guide
.github/workflows/simulator.yml
```

Rust stable (1.80 or newer). Dependencies, all small and common:
`cc` (build), `libloading`, `tiny_http`, `serde`/`serde_json`, `sha2`,
`webbrowser`. No async runtime.

## 2. The loop

Exactly the loop of `run_sil.py`'s `Sim.run`, so results carry over:

- The plant steps every **20 µs** of simulated time.
- Crank and cam edges inside a step are delivered in time order through
  `ecu_crank_edge` / `ecu_cam_edge`; after each, injection commands whose
  `seq` changed are passed to the plant.
- Every **1 ms**: sensor volts into `ecu_io`, `ecu_tick_1ms`,
  `ecu_background`, an NVM save if `nvm_save` (into one of two in-memory
  slots, torn halfway when a tear is armed), CAN frames drained, one trace
  row recorded.
- Start-up: `ecu_init`, ignition on, `ecu_nvm_load` with both slots,
  `ecu_eol_load` with a passed record (serial `SIM`), as `run_sil.py`.
- Power cycle: as `Sim.power_cycle` (fresh init, reload slots and EOL,
  plant command state cleared, engine keeps its speed).

The firmware never sees the PC's clock, only simulated microseconds, so
pacing cannot change a result. **Pacing**: after each 10 ms simulated, the
loop sleeps until wall time catches up with `sim time / speed`. Speeds:
1×, 2×, 10×, max. If the PC falls behind, the UI shows the speed actually
reached.

## 3. Plant

A port of `firmware/sim/engine.py` to Rust `f64`, same constants, same
operation order. Faults the plant adds beyond the Python model:

| Fault | Script | Effect |
|---|---|---|
| Sensor open | `sensor <ch> open` | CLT 5.0 V (pull-up); oil, rail, boost, EGR and the 5 V monitor 0.0 V |
| Sensor short to ground | `sensor <ch> short` | 0.0 V |
| Sensor short to 5 V | `sensor <ch> short5v` | 5.0 V |
| Forced reading | `sensor <ch> volts <V>` | that voltage |
| Offset | `sensor <ch> offset <V>` | model volts plus V |
| Stuck | `sensor <ch> stuck` | holds the volts it had |
| Clear | `sensor <ch> clear` | model volts again |
| Crank signal lost | `crank lost` / `crank restore` | no crank edges |
| Lost teeth | `crank drop <n>` | the next n edges missing |
| Extra teeth | `crank extra <n>` | n spurious edges, each midway between two teeth |
| Cam lost | `cam lost` / `cam restore` | no cam edges |
| Stuck fuel | `fuel stuck <mg> [cyl <k>]` / `fuel free` | as Python's `stuck_fuel_mg`; one cylinder if `cyl` |
| Rail leak | `leak <x>` | leak coefficient times x (1 = normal) |

Channels: `clt oil rail boost egr 5v`. Open-circuit volts follow the
board: the NTC has a pull-up, the 0.5–4.5 V sensors read low when open
(`sensors.c`: above 4.8 V is FMI 3, below the channel's low limit FMI 4).

## 4. Firmware binding

The C core has global state, so a firmware is one instance per process and
one run at a time.

- **Bundled**: `crates/sim/build.rs` compiles `firmware/core/*.c` with
  `cc` and links it statically. It is the default, and the reason the
  binary needs nothing beside it.
- **Loaded**: a `.dll`, `.dylib` or `.so` chosen in the UI (or `--fw` on
  the command line). The upload is copied to a fresh temporary file name
  each time (operating systems reuse an already-loaded path), then
  opened with `libloading`.

Both fill one struct of function pointers; the loop does not know which
it has. Required symbols: `ecu_abi_version`, `ecu_io_size`, `ecu_init`,
`ecu_crank_edge`, `ecu_cam_edge`, `ecu_tick_1ms`, `ecu_background`,
`ecu_nvm_load`, `ecu_nvm_image`, `ecu_can_rx`, `ecu_eol_load`,
`rail_set_bar`.

**Firmware change** (the only one): `ecu.h` gains

```c
#define ECU_ABI_VERSION 1u   /* bump whenever ecu_io or an entry point changes */
uint32_t ecu_abi_version(void);
```

and an `ECU_API` marker on those symbols (`__declspec(dllexport)` when
building a Windows DLL, empty otherwise). The loader refuses a library
with a missing symbol, a different ABI version, or an `ecu_io_size()`
that differs from the Rust struct, and says which. Rust's `EcuIo` is a
`#[repr(C)]` copy of `ecu_io`; a test checks its size against the bundled
`ecu_io_size()`.

**Building a firmware library**: `cargo run -p fwbuild` compiles
`firmware/core` with the platform's C compiler (found by `cc`: MSVC on
Windows, clang on macOS, gcc on Linux) into `simulator/build/ecu_fw.*`.
CI attaches one per OS, so the friend can try a firmware branch without a
compiler.

Loading a library runs its code with the user's rights: the UI says
"load only firmware you trust", and `--share` mode refuses uploads.

## 5. Scripts (`.seq`)

Plain text, one line each, `#` starts a comment. Times are seconds of
simulated time, non-decreasing. Errors are reported with the line number
before anything runs.

```
# 2  load step 0 -> 20 kW
0    start
8    load 20
13   end
expect rpm min 1350.. over 8..13
expect rpm mean 1485..1515 over 12.9..13
expect never dm1 190/18
```

**Actions** (`<t> <action>`):

| Action | Meaning |
|---|---|
| `start` | starter on until the firmware reaches RUN, then off (`Sim.start`) |
| `starter on\|off` | starter by hand |
| `load <kW>` | electrical load |
| `ignition on\|off` | ignition input |
| `ignition bounce <ms>` | off for ms, then on |
| `droop on\|off` | droop switch |
| sensor, crank, cam, fuel, leak | faults, section 3 |
| `request dm2\|dm3\|dm4\|hours` | a J1939 request from a tool at address 3 |
| `power cycle` | section 2 |
| `tear next save` | the next NVM save is cut halfway |
| `end` | the run stops here; required, last |

**Checks** (`expect ...`, evaluated when the run ends):

| Check | Passes when |
|---|---|
| `expect <signal> <mean\|min\|max> <lo>..<hi> over <t0>..<t1>` | the statistic of that signal in the window is inside the band; either bound may be left out |
| `expect <signal> mean change <lo>..<hi> from <a0>..<a1> to <b0>..<b1>` | the mean over the second window minus the mean over the first is inside the band (added 20 Oct for the droop scenario) |
| `expect dm1 <spn>/<fmi> within <s> of <t>` | a DM1 carrying it is sent in (t, t+s] |
| `expect never dm1 <spn>/<fmi>` | no DM1 in the run carries it |
| `expect dm1 clear over <t0>..<t1>` | every DM1 in the window carries no DTC |
| `expect lamp <amber\|red\|protect\|mil>[+...] with <spn>/<fmi>` | the first DM1 carrying it has exactly those lamps on |
| `expect trip within <ms> ms of <t>` | the state reaches SHUTDOWN in (t, t+ms] |
| `expect no trip` | SHUTDOWN never happens |
| `expect state <OFF\|WAIT\|CRANK\|RUN\|SHUTDOWN> at end` | the state when the run stops |
| `expect stored <spn>/<fmi>` / `expect not stored <spn>/<fmi>` | in the newest valid NVM slot at the end |
| `expect dm2 <spn>/<fmi> after <t>` / `expect dm2 empty after <t>` | the first DM2 sent after t |

`<fmi>` may be `*` (any). Signals: `rpm` (engine), `ecu_rpm`, `rail`,
`rail_err` (rail over the firmware's setpoint, minus 1; 0 while the
setpoint is 0), `duty`, `fuel`, `clt`, `oil`, `load`.

A live session's actions are written in this same syntax (section 7), so
anything done by hand can be saved and replayed.

**The 16 SIL scenarios** become `scenarios/sil/01-start.seq` …
`16-overload.seq`, with the actions of `run_sil.py` and its claims as
checks, wherever a check above can say them. Claims it cannot say (the
edge on which overspeed trips, sync within 118 edges, watchdog periods,
CAN intervals, freeze-frame contents, the torn save's reload) stay in the
Python SIL; each `.seq` names those in a comment.

## 6. Browser UI

`ecusim` with no arguments serves on `127.0.0.1` (port 8025, or the next
free one) and opens the default browser. One page:

- **Run bar**: Run, Pause, Stop, Reset; speed 1× / 2× / 10× / max, with
  the speed reached; simulated time; firmware name.
- **Controls** (live): Start, Stop (ignition off), load slider 0–30 kW,
  droop switch, and a fault menu that sends any action of section 5.
  Every control sends one script line, applied at the current time.
- **Charts** (uPlot, last 30 s scrolling, or the whole run when stopped):
  engine and ECU speed; rail and setpoint; metering duty and fuel; load;
  the state as a band.
- **DM1**: active DTCs with SPN name, FMI and lamps.
- **CAN**: the last 200 frames, in and out, with PGN names.
- **Scenario**: a library list (bundled, plus `.seq` files in
  `./scenarios/`), Open… and drag-and-drop, an editor, Run, and Save as…
  (a browser download). Parse errors show against their line.
- **Firmware**: Load firmware… (a file input), the bundled one by default,
  with the reason if one is refused.
- **Runs**: past run folders, opened into the charts; each run's report.

Transport, all plain HTTP from one thread pool:

- `GET /` and the UI files, embedded with `include_bytes!`.
- `GET /events`: Server-Sent Events. Every 50 ms one batch of trace rows
  (one per 10 ms), new CAN frames, the DM1 list, status; events as they
  happen; the report when a run ends.
- `POST /cmd`: one script line, or `run|pause|stop|reset|speed <x>`.
- `POST /scenario`: script text; parse errors come back with line numbers.
- `POST /firmware`: the library's bytes.
- `GET /library`, `GET /runs`, `GET /runs/<id>/<file>`.

`--share` binds all interfaces so another PC on the LAN can watch, and
then refuses `POST /firmware`.

## 7. Run folders

Each run writes `./runs/<YYYYMMDD-HHMMSS>-<name>/`:

| File | Content |
|---|---|
| `trace.csv` | one row per ms: t_ms, rpm, ecu_rpm, state, synced, rail, rail_set, duty, fuel, load, clt, oil, wdg, starter, ignition |
| `can.csv` | t_ms, dir (tx/rx), id (hex), data (hex), PGN name |
| `events.txt` | every action applied, scripted or live, as script lines; state changes as comments; ends with `end` |
| `report.txt` | each check, the value found, pass or fail; the totals |
| `firmware.txt` | bundled or the file name, its SHA-256, ABI version |

A 60 s run is about 4 MB of trace. `events.txt` of a live session runs
as a script.

## 8. Command line

```
ecusim                                   open the UI
ecusim run <file.seq>... [--fw <lib>]    run headless at max speed, write run folders
       [--out <dir>]                     print each report
ecusim --port <n> --share                as section 6
```

`run` exits 0 when every check passes, 1 when any fails, 2 on a script or
firmware error.

## 9. Portability and release

- GitHub Actions, `.github/workflows/simulator.yml`, on Windows, macOS
  (arm64) and Ubuntu: `cargo test`, then `ecusim run scenarios/sil/*.seq`,
  then release builds of `ecusim` and `ecu_fw`, uploaded as artifacts
  (`ecusim-windows.exe`, `ecusim-macos`, `ecusim-linux`, and the three
  firmware libraries). CI runs only after the branch is pushed, which the
  owner decides.
- The README's first section is the friend's: download, double-click,
  Windows SmartScreen's "More info → Run anyway" (the binary is
  unsigned), the browser opens.
- Same script and firmware on the same OS give the same trace, bit for
  bit. Across operating systems `sin`/`exp` may differ in the last bit,
  so traces can differ slightly; the checks' bands absorb it.

## 10. Testing

- **Plant against Python**: `simulator/tools/golden.py` (run once, with
  the repo's `.venv`) drives `engine.py` open loop through three profiles
  (starter from rest; held at 1500 rpm with 34 mg and 20 kW; rail fill
  while cranking) and writes CSVs into `crates/plant/tests/golden/`,
  committed. The Rust plant must give the same edge times and agree on
  speed and rail to 1e-6 relative. The four `_self_check` claims are also
  Rust tests.
- **Plant faults**: one test per row of section 3 (for example: `crank
  extra 1` adds exactly one edge, midway; `sensor clt open` reads 5.0 V).
- **Binding**: `EcuIo` size equals the bundled `ecu_io_size()`;
  `ecu_abi_version()` is 1; a library from `fwbuild` loads, runs
  `01-start.seq` with the same trace as the bundled one, and its
  `ecu_init` is a different address from the bundled one; a library with
  a wrong ABI or a missing symbol is refused with a message naming it.
- **Scripts**: the parser accepts every bundled `.seq` and rejects bad
  lines with their numbers; each kind of check passes and fails on a
  hand-built record.
- **The 16**: `ecusim run scenarios/sil/*.seq` passes, in `cargo test`
  and in CI on all three operating systems.
- **Server**: `POST /cmd` with `load 20` changes the load at the current
  time and appears in `events.txt`; `POST /firmware` is refused under
  `--share`.
- **Pacing**: at 1× a 2 s run takes 2 s of wall time within 5 %.

The UI's look is checked by hand.

## 11. Not in v1

- Modes 2 and 3.
- The service tool (UDS, flashing, EOL) in the UI; `ecu_service.py --link
  sim` already covers it.
- Parameter sweeps and parallel runs (the firmware is one instance per
  process).
- Editing engine-model constants from the UI.
- A code-signed or notarised binary.
