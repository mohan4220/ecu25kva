# ECU simulator, mode 1: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ecusim`, one Rust binary that runs the unchanged C firmware core
against a Rust port of the engine model, live or from `.seq` scripts, with
a browser UI embedded in it.

**Architecture:** `plant` (engine model, faults, no I/O) → `sim` (firmware
binding, the 20 µs / 1 ms loop of `run_sil.py`, scripts, checks, J1939
reassembly) → `ecusim` (CLI, run folders, paced live thread, HTTP + SSE
server, embedded UI). `fwbuild` compiles `firmware/core` into a dynamic
library with the platform's C compiler.

**Tech Stack:** Rust stable ≥ 1.80; `cc`, `libloading`, `tiny_http`,
`serde`/`serde_json`, `sha2`, `webbrowser`; uPlot 1.6.30 vendored.

**Spec:** `simulator/docs/spec.md`

## Global Constraints

- Everything lives in `simulator/` (workspace root `simulator/Cargo.toml`), plus `.github/workflows/simulator.yml` and the two-line firmware change in `firmware/core/ecu.h`, `ecu.c`, `rail.h`.
- Rust stable 1.80 or newer. Dependencies only: `cc`, `libloading`, `tiny_http`, `serde`/`serde_json`, `sha2`, `webbrowser`. No async runtime, no CLI-parser crate.
- The plant steps every 20 µs; the firmware ticks every 1 ms; trace rows are one per ms (spec §2).
- Firmware is called with `t_us as u32` (wrapping), as `ecu.py` does.
- Start-up: `ecu_init`, ignition 1, `ecu_nvm_load` with both slots, `ecu_eol_load` with a passed record whose serial is `SIM` (spec §2).
- The server binds `127.0.0.1`, port 8025 or the next free one; `--share` binds all interfaces and refuses `POST /firmware` (spec §6).
- `ecusim run` exits 0 all pass, 1 any fail, 2 script or firmware error (spec §8).
- Commits carry no AI-attribution trailer (owner's standing rule).
- Do not push; the owner decides.

## Review Focus

1. A live session longer than 71.6 min: firmware times wrap at 2³² µs; the plant must keep accepting injection commands across the wrap (Task 1 test `command_across_u32_wrap`).
2. A file that is not a loadable library (a `.seq`, random bytes, another architecture) uploaded as firmware: a clear refusal, no crash (Task 3 test `load_rejects_garbage`).
3. A script written in Windows Notepad: CRLF line ends and a UTF-8 BOM must parse; actions after `end`, times going backwards and unknown names are errors with their line numbers (Task 5 test `parse_crlf_bom_and_errors`).
4. The same firmware file name uploaded twice with different contents: the second must actually run (Task 3 test `reload_same_path_runs_new_code`).
5. The browser tab closed or reloaded during a run: the run goes on, the dead subscriber is dropped, a new tab picks up (Task 8 test `sse_subscriber_dropped_on_disconnect`).

---

### Task 1: Workspace and plant port

**Files:**
- Create: `simulator/Cargo.toml` (workspace, members `crates/*`, `resolver = "2"`), `simulator/.gitignore` (`target/`, `build/`, `runs/`)
- Create: `simulator/crates/plant/Cargo.toml`, `simulator/crates/plant/src/lib.rs`
- Create: `simulator/tools/golden.py`, `simulator/crates/plant/tests/golden.rs`, `simulator/crates/plant/tests/golden/*.csv`

**Interfaces:**
- Produces (`plant`):
  - consts `NCYL = 3`, and every constant of `engine.py` under the same name.
  - `pub struct Engine` with pub fields `theta: f64, omega: f64, rail_bar: f64, clt_c: f64, duty: f64, load_kw: f64, starter: bool, net_torque: f64`; `Engine::new()`.
  - `fn rpm(&self) -> f64`
  - `fn command(&mut self, cyl: usize, start_us: u32, dur_us: u32, seq: u32)`. It takes firmware (wrapping) times and unwraps each to the u64 nearest the plant's current time.
  - `fn step(&mut self, t_us: u64, dt_us: u32, edges: &mut Vec<(u64, bool)>)`. It appends `(time, is_cam)` and does not sort.
  - `fn volts(&self) -> [f64; 6]`, indexed by `pub enum Ch { Clt, Oil, Rail, Boost, Egr, V5 }` as `usize`.

- [ ] **Step 1: Write `tools/golden.py`.** It imports `firmware/sim/engine.py` and writes four CSVs, one row per ms (`t_us,rpm,rail_bar,theta`), plus `<name>_edges.csv` (`t_us,is_cam`):
  - `starter`: from rest, starter on, 2 s.
  - `held`: omega forced to 1500 rpm every step, `stuck_fuel_mg = 34`, 20 kW, 0.16 s.
  - `rail_fill`: omega forced to 150 rpm, duty 0, 1 s.
  - `free`: omega starts at 1500 rpm; duty 0.3; 10 kW. Every cylinder k gets a command at `k*26667 + n*80000` µs, dur 1500 µs, seq n+1. Runs 2 s.

  It also writes `closed_start.csv` (`t_ms,rpm,state,rail_bar`) from `run_sil.Sim().start(5.0)`, which Task 4 uses. Run `.venv/bin/python simulator/tools/golden.py` from the repo root.
- [ ] **Step 2: Write the failing tests in `tests/golden.rs`:**
  - `golden_<name>` for each of the four profiles. Edge lists must be identical. Every row's rpm and rail must satisfy `|a-b| <= 1e-6 * max(|b|, 1.0)`.
  - `self_check_starter`: the mean over 1.6–2 s is in 140..=150 rpm.
  - `self_check_torque_balance`: \|mean net torque\| < 0.10 × load torque.
  - `self_check_edges`: 116 crank and 1 cam over one cycle from theta 3.0.
  - `self_check_rail_fill`: the rail rises by more than 100 bar.
  - `command_across_u32_wrap`: the plant is at t = 2³² − 500 µs. Command cyl 0 at `start_us = 100` (wrapped), dur 1500. Step past 2³² + 2000 µs. `fuel[0] > 0`.
- [ ] **Step 3: Run** `cd simulator && cargo test -p plant`. Expected: FAIL (does not compile: `Engine` not found).
- [ ] **Step 4: Port `engine.py` into `plant/src/lib.rs`.** Same constants, same operation order: the `%` and `floor` in the same places, `f64` throughout. `fuel` and `cmd` (as `Option<(u64,u32)>`) are pub. `stuck_fuel_mg`, `crank_lost`, `drop_edge_once` and `v_override` wait for Task 2. Python's `%` on negative floats is `rem_euclid`.
- [ ] **Step 5: Run** `cargo test -p plant`. Expected: all PASS.
- [ ] **Step 6: Commit.** `git add simulator && git commit -m "Simulator: workspace, engine model ported to Rust, golden traces"`

### Task 2: Plant faults

**Files:**
- Modify: `simulator/crates/plant/src/lib.rs`
- Test: `simulator/crates/plant/tests/faults.rs`

**Interfaces:**
- Produces (`plant`):
  - `pub enum SensorFault { None, Open, Short, Short5v, Volts(f64), Offset(f64), Stuck(f64) }` and `pub sensor: [SensorFault; 6]`. `Stuck` holds the volts at the moment it was set; `Engine::stick(ch)` sets it.
  - `pub crank_lost: bool`, `pub crank_drop: u32` (edges still to drop), `pub crank_extra: u32` (spurious edges still to add), `pub cam_lost: bool`.
  - `pub stuck_fuel: [Option<f64>; NCYL]` replaces Python's `stuck_fuel_mg`. Fuel stuck for all cylinders sets all three.
  - `pub leak: f64`, the multiplier on `LEAK`, default 1.0.

- [ ] **Step 1: Write the failing tests:**
  - `open_volts`: Clt 5.0, and Oil, Rail, Boost, Egr, V5 0.0.
  - `short` gives 0.0; `short5v` gives 5.0; `volts_forced`: `Volts(2.2)` gives 2.2.
  - `offset_adds`: model + 0.3.
  - `stuck_holds`: `stick(Clt)`, then the coolant warms and the value is unchanged.
  - `crank_lost_no_edges` and `cam_lost_no_cam`, each over one cycle at 1500 rpm.
  - `drop_two`: 114 crank edges in the cycle, against 116.
  - `extra_one`: 117 edges. The extra one is midway (±1 µs) between the two real edges around it.
  - `stuck_one_cylinder`: only `fuel[1]` is refilled at its TDC.
  - `leak_drains`: with `leak = 10`, the rail falls faster than with 1.

  Also re-run `golden.rs` to prove the defaults change nothing.
- [ ] **Step 2: Run** `cargo test -p plant`. Expected: FAIL (fields missing).
- [ ] **Step 3: Implement** in `step` and `volts`. An extra edge is emitted on the next real tooth: it is placed midway between that tooth's time and the previous tooth's time, recorded in `last_crank_us`. The extra goes out before the real one.
- [ ] **Step 4: Run** `cargo test -p plant`. Expected: all PASS, golden included.
- [ ] **Step 5: Commit.** `"Simulator: plant faults"`

### Task 3: Firmware binding and `fwbuild`

**Files:**
- Modify: `firmware/core/ecu.h`:
  - add `#ifndef ECU_ABI_VERSION` / `#define ECU_ABI_VERSION 1u` / `#endif`, with the comment from spec §4;
  - add `uint32_t ecu_abi_version(void);`;
  - add an `ECU_API` macro: `__declspec(dllexport)` if `_WIN32 && ECU_DLL`, else empty. It goes on every entry point the spec lists.
- Modify: `firmware/core/ecu.c` (define `ecu_abi_version`), `firmware/core/rail.h` (`ECU_API` on `rail_set_bar`)
- Create: `simulator/crates/fwbuild/{Cargo.toml,build.rs,src/lib.rs,src/main.rs}`
- Create: `simulator/crates/sim/{Cargo.toml,build.rs,src/lib.rs,src/fw.rs}`
- Test: `simulator/crates/sim/tests/binding.rs`

**Interfaces:**
- Produces (`fwbuild`):
  - `pub fn build(core: &Path, out: &Path, defines: &[&str]) -> Result<(), String>`. It compiles every `*.c` in `core` into one shared library.
  - `pub fn default_core() -> PathBuf` returns `<repo>/firmware/core`.
  - `pub fn lib_name() -> &'static str` returns `ecu_fw.dll`, `ecu_fw.dylib` or `ecu_fw.so`.
  - CLI: `fwbuild [--core DIR] [--out FILE] [-D NAME=VAL]...`. The default out is `simulator/build/<lib_name>`.
- Produces (`sim::fw`):
  - `#[repr(C)] pub struct EcuIo`, a field-for-field copy of `ecu_io` (order as `ecu.py`'s `IO`), plus `EcuCan` and `EcuInj`, all `Default`.
  - `pub struct Firmware { pub name: String, pub sha256: Option<String>, pub abi: u32, .. }`.
  - `Firmware::bundled() -> Arc<Firmware>` returns the same Arc every call.
  - `Firmware::load(path: &Path) -> Result<Arc<Firmware>, String>` copies to a fresh temp name, then opens it. It refuses a missing symbol (naming it), an ABI ≠ 1, or `ecu_io_size()` ≠ `size_of::<EcuIo>()`, with messages that say which.
  - Safe methods taking `&mut EcuIo`: `init`, `crank_edge(io, u32)`, `cam_edge(io, u32)`, `tick_1ms(io, u32)`, `background`, `can_rx(io, &EcuCan)`, `nvm_load(io, a: &[u8], b: &[u8])`, `eol_load(io, &[u8; 84], &[u8; 84])`.
  - `nvm_image(&self) -> Vec<u8>` and `rail_set_bar(&self, f32) -> f32`.
  - `fn claim(self: &Arc<Self>) -> Claim`. It blocks while another `Claim` on the same firmware is alive (Mutex<bool> + Condvar); dropping the `Claim` frees it.
  - `pub fn eol_record_sim() -> [u8; 84]`, the port of `ecu.py`'s `eol_record(b"SIM", passed=1)` (zlib CRC-32, written inline in `sim::crc32`).

- [ ] **Step 1: Write the failing tests in `binding.rs`.** Each builds its libraries with `fwbuild::build` (a dev-dependency) into a temp dir.
  - `io_size_matches`: `size_of::<EcuIo>()` equals the bundled `ecu_io_size()`.
  - `abi_is_1`.
  - `loaded_is_a_different_instance`: the loaded `init` pointer is not the bundled one's.
  - `wrong_abi_refused`: built with `-DECU_ABI_VERSION=99u`; the error contains "ABI 99".
  - `missing_symbol_refused`: a core dir holding one `.c` that defines only `ecu_abi_version`; the error names `ecu_io_size`.
  - `load_rejects_garbage`: a file of 1 KiB random bytes; `Err`, no panic.
  - `reload_same_path_runs_new_code`: write a good library to P and load it. Overwrite P with the ABI-99 build. Loading P gives the ABI-99 error.
  - `claim_serialises`: a second `claim()` from another thread waits until the first is dropped.
- [ ] **Step 2: Run** `cargo test -p sim --test binding`. Expected: FAIL (crates do not compile).
- [ ] **Step 3: Make the firmware change.** Run `make -C firmware/sim test` and `.venv/bin/python firmware/sim/run_sil.py`. Expected: 101 and 7 tests ok, 16/16 scenarios pass.
- [ ] **Step 4: Implement `fwbuild`.**
  - `build.rs` exports `TARGET` as `FWBUILD_TARGET`.
  - `build` uses `cc::Build::new().target(T).host(T).opt_level(2).cargo_metadata(false).get_compiler()`.
  - With MSVC: `/nologo /O2 /LD /DECU_DLL <defines as /D> <c files> /Fe:<out> /Fo:<tmp>\`.
  - Otherwise: `-std=c99 -O2 -shared -fPIC <defines as -D> <c files> -o <out> -lm`.
  - It returns the compiler's stderr on failure.
- [ ] **Step 5: Implement `sim`.**
  - `build.rs` compiles `firmware/core/*.c` with `cc` (std c99) as a static lib, and reruns when that dir changes.
  - `fw.rs` holds the API struct of `unsafe extern "C" fn` pointers, filled from the linked `extern "C"` block or from `libloading` symbols.
  - A loaded `Firmware` keeps its `Library` alive.
- [ ] **Step 6: Run** `cargo test -p sim --test binding`. Expected: all PASS.
- [ ] **Step 7: Commit.** `"Simulator: firmware binding, loadable firmware, fwbuild; firmware gains ecu_abi_version"`

### Task 4: The loop and J1939 reassembly

**Files:**
- Create: `simulator/crates/sim/src/{sim.rs,j1939.rs,nvm.rs}`
- Test: `simulator/crates/sim/tests/loop.rs`, unit tests in `j1939.rs` and `nvm.rs`

**Interfaces:**
- Consumes: `plant::Engine` (Tasks 1–2), `sim::fw` (Task 3).
- Produces:
  - `j1939::pgn(id: u32) -> u32`, which is `id >> 8 & 0xFFFF`.
  - `j1939::Bam`: `push(&mut self, t_ms: u64, f: &EcuCan) -> Option<Msg>` passes single frames through and reassembles a TP.CM BAM (pgn & 0xFF00 == 0xEC00, control 32) from its TP.DT frames (0xEB00).
  - `pub struct Msg { t_ms: u64, pgn: u32, data: Vec<u8> }`.
  - `j1939::dtcs(data: &[u8]) -> Vec<(u32, u8)>`, a port of `run_sil.dtcs` over the full length.
  - `j1939::lamps(data: &[u8]) -> u8`, which is `data[0]`.
  - `j1939::name(pgn) -> &'static str`: EEC1, ET1, EFL/P1, DM1–DM4, HOURS, TP.CM, TP.DT, REQUEST, else "".
  - `nvm::stored(slots: &[Vec<u8>; 2]) -> Option<Vec<(u32, u8)>>`. It reads the DTCs whose status has bit 1, from the newest slot valid as `nvm_valid` checks it (magic 0xEC25, version 1, len, CRC-32 with the crc field at offset 12 zeroed).
  - `pub struct Row { t_ms: u64, rpm: f64, ecu_rpm: f32, state: u8, synced: u8, rail: f64, rail_set: f32, duty: f32, fuel: f32, load: f64, clt: f64, oil: f32, wdg: u8, starter: bool, ignition: u8 }`.
  - `pub struct CanRec { t_ms: u64, rx: bool, id: u32, data: Vec<u8> }`.
  - `pub struct Sim { pub eng: Engine, pub io: Box<EcuIo>, pub t_us: u64, pub trace: Vec<Row>, pub can: Vec<CanRec>, pub msgs: Vec<Msg>, pub states: Vec<(u64, u8)>, pub slots: [Vec<u8>; 2], pub tear_next: bool, pub release_on_run: bool, .. }`.
  - `Sim::new(fw: Arc<Firmware>) -> Sim` claims the firmware and does the start-up of Global Constraints.
  - `fn step_ms(&mut self)` advances exactly 1 ms with the loop of spec §2. Edges are sorted by `(time, is_cam)`, as Python's `sorted`.
  - `fn request(&mut self, pgn: u32)` sends id `0x18EAFF03`, len 3, pgn LE, and logs it as rx.
  - `fn power_cycle(&mut self)` matches `Sim.power_cycle`.

- [ ] **Step 1: Write the failing tests:**
  - `bam_two_dtcs`: a TP.CM plus two TP.DT for a 10-byte DM1 gives one `Msg` whose `dtcs` is `[(110,3),(100,4)]`.
  - `single_frame_passthrough`.
  - `nvm_torn_slot_ignored`: the higher seq is torn, so the other is used.
  - `closed_start_matches_python`: `Sim` with `release_on_run` runs to 5000 ms against `golden/closed_start.csv`. The state sequence is equal, and the max \|rpm diff\| is < 1 rpm.
  - `power_cycle_keeps_history`: stuck fuel 80 at 6 s, run to 9 s, `power_cycle`; `nvm::stored` contains (190, 0).
- [ ] **Step 2: Run** `cargo test -p sim`. Expected: FAIL (not defined).
- [ ] **Step 3: Implement** `j1939.rs`, `nvm.rs`, `sim.rs`.
- [ ] **Step 4: Run** `cargo test -p sim`. Expected: all PASS. If `closed_start` drifts by more than 1 rpm, find the operation-order difference. Do not widen the tolerance without a ruling.
- [ ] **Step 5: Commit.** `"Simulator: loop as run_sil, J1939 reassembly, NVM read"`

### Task 5: Scripts and checks

**Files:**
- Create: `simulator/crates/sim/src/{seq.rs,check.rs}`
- Modify: `simulator/docs/spec.md` §5 (add the `change` check)
- Test: unit tests in both files

**Interfaces:**
- Consumes: `Sim`, `Msg`, `Row`, `nvm::stored`, `j1939::dtcs` (Task 4).
- Produces:
  - `pub enum Action`: one variant per spec §5 action and §3 fault. `Display` writes it back in script syntax, without the time.
  - `pub enum Check`: the spec §5 table plus `Change { sig, lo, hi, a: (f64,f64), b: (f64,f64) }`, written `expect <signal> mean change <lo>..<hi> from <a0>..<a1> to <b0>..<b1>` and meaning mean(b) − mean(a). This addition goes into the spec table.
  - `pub struct Script { pub name: String, pub actions: Vec<(u64, Action)>, pub end_us: u64, pub checks: Vec<(usize, String, Check)> }`. Times are in µs, and each check keeps its line number and text.
  - `seq::parse(name: &str, text: &str) -> Result<Script, Vec<(usize, String)>>`. Lines are numbered from 1, and every error is collected.
  - `Sim::apply(&mut self, a: &Action)`.
  - `seq::run(fw: Arc<Firmware>, s: &Script) -> (Sim, Vec<Outcome>)`. Before each ms it applies the actions due at or before `t_us`, then steps until `end_us`.
  - `pub struct Outcome { pub line: usize, pub text: String, pub found: String, pub pass: bool }`.
  - `check::evaluate(checks: &[(usize,String,Check)], sim: &Sim) -> Vec<Outcome>`.
  - Bands are inclusive. Windows are `t0 <= t < t1` on `Row.t_ms` as seconds. `within <s> of <t>` means (t, t+s].
  - Lamp names map to `j1939.h`: red 0x10, amber 0x04, protect 0x01, mil 0x40.

- [ ] **Step 1: Write the failing tests:**
  - `parse_all_actions`: one line per action, and each round-trips through `Display`.
  - `parse_crlf_bom_and_errors`: CRLF and a BOM parse. These are each an error with the right line number: an action after `end`, a time going backwards, `sensor xyz open`, `foo`, a missing `end`, and `expect rpm mean 1..2 over 3`.
  - One pass test and one fail test per check kind, on a `Sim` built by hand (its `trace`, `msgs`, `states`, `slots` filled in directly). The `change` check: 1500 → 1440 passes `-75..-45`.
  - `fmi_wildcard`: `636/*` matches (636, 2).
- [ ] **Step 2: Run** `cargo test -p sim`. Expected: FAIL.
- [ ] **Step 3: Implement** `seq.rs` and `check.rs`. `start` turns the starter on and sets `release_on_run`. The loop clears the starter at the first ms whose state is RUN.
- [ ] **Step 4: Run** `cargo test -p sim`. Expected: all PASS.
- [ ] **Step 5: Commit.** `"Simulator: .seq scripts and checks"`

### Task 6: Scenario library, run folders, headless CLI

**Files:**
- Create: `simulator/scenarios/sil/01-start.seq` … `16-overload.seq` and `simulator/scenarios/faults/*.seq` (one per row of spec §3, actions only)
- Create: `simulator/crates/ecusim/{Cargo.toml,src/main.rs,src/runs.rs,src/library.rs}`
- Test: `simulator/crates/ecusim/tests/cli.rs`, unit test in `library.rs`

**Interfaces:**
- Consumes: `seq::parse`, `seq::run`, `Firmware` (Tasks 3, 5).
- Produces:
  - `library::LIBRARY: &[(&str, &str)]`, written out by hand as (`"sil/01-start.seq"`, `include_str!(...)`).
  - `runs::write(dir: &Path, name: &str, sim: &Sim, events: &[String], outcomes: &[Outcome], fw: &Firmware) -> io::Result<PathBuf>`. It writes the five files of spec §7. The folder is `<YYYYMMDD-HHMMSS>-<name>`, from the local time via `std::time` (UTC is acceptable; ruling if so); a `-2` suffix is added if it exists.
  - `runs::report(outcomes) -> String`: one line per check (`PASS`/`FAIL`, text, found), then `n/m checks pass`.
  - `main`: `ecusim run <files>... [--fw LIB] [--out DIR]` (default `./runs`), exiting with codes 0, 1 or 2. Bare `ecusim` and `--port`/`--share` are wired in Task 8.

The 16 scripts. Each also carries a comment naming the Python-only claims of spec §5:

| File | Actions | Checks |
|---|---|---|
| 01-start | `0 start`, `5 end` | rpm mean 1485..1515 over 4.9..5; rpm max ..1600 over 0..5; no trip |
| 02-load-step | `0 start`, `8 load 20`, `13 end` | rpm min 1350.. over 8..13; rpm mean 1485..1515 over 12.9..13; never dm1 190/18 |
| 03-load-reject | `0 start`, `5 load 20`, `12 load 0`, `17 end` | rpm max ..1650 over 12..17; no trip |
| 04-droop | `0 droop on`, `0 start`, `10 load 20`, `18 end` | rpm mean change -75..-45 from 9..10 to 17..18 |
| 05-runaway | `0 start`, `6 fuel stuck 80`, `7 end` | trip within 1000 ms of 6; dm1 190/0 within 1 of 6 |
| 06-crank-loss | `0 start`, `6 crank lost`, `7.5 end` | trip within 100 ms of 6; dm1 636/* within 1.5 of 6 |
| 07-ignition-off | `0 start`, `6 ignition off`, `36 end` | trip within 30000 ms of 6; dm1 clear over 6.001..36; rpm min ..50 over 6..36 |
| 08-sensor-open | `0 start`, `6 sensor clt open`, `9 end` | dm1 110/3 within 1.2 of 6; state RUN at end |
| 09-can-content | `0 start`, `8 end` | no trip; state RUN at end |
| 10-rail | `0 start`, `8 load 20`, `16 end` | rail_err min -0.05.. and max ..0.05, over 6..8 and over 14..16 |
| 11-watchdog | `0 start`, `8 load 20`, `13 end` | no trip; state RUN at end |
| 12-history | `0 start`, `6 fuel stuck 80`, `9 power cycle`, `9 end` | stored 190/0 |
| 13-torn-save | `0 start`, `3 tear next save`, `3 ignition off`, `16 power cycle`, `16 end` | trip within 13000 ms of 3 |
| 14-dm2-dm3 | `0 start`, `6 sensor clt open`, `7.5 sensor clt clear`, `8 request dm2`, `8.1 sensor oil volts 0.1`, `9 request dm3`, `9.1 request dm2`, `11.2 end` | dm2 110/3 after 8; dm2 empty after 9.1; dm1 100/4 within 2.2 of 9 |
| 15-lost-tooth | `0 start`, `6 crank drop 1`, `8 end` | trip within 2000 ms of 6; stored 636/2; not stored 190/0 |
| 16-overload | `0 start`, `8 load 30`, `20 end` | rpm min ..1350 over 8..20; dm1 190/18 within 6 of 8; lamp amber with 190/18; no trip; state RUN at end |

- [ ] **Step 1: Write the failing tests:**
  - `library_matches_dir`: every file under `scenarios/` is in `LIBRARY`, and the reverse.
  - `library_parses`: every entry parses.
  - `sil_all_pass`: runs `ecusim run ../../scenarios/sil/*.seq --out <tmp>` through `env!("CARGO_BIN_EXE_ecusim")` and expects exit 0.
  - `failing_check_exits_1`: a script with `expect rpm mean 0..1 over 4..5` exits 1, and its `report.txt` has `FAIL`.
  - `bad_script_exits_2`.
  - `run_folder_files`: all five files exist. `trace.csv` has 5000 rows plus a header. `events.txt` parses as a script. `firmware.txt` names "bundled" and ABI 1.
- [ ] **Step 2: Run** `cargo test -p ecusim`. Expected: FAIL.
- [ ] **Step 3: Write the scripts and implement** `library.rs`, `runs.rs` and `main.rs`. If a SIL band fails while the Python SIL passes, take the Python claim's actual value from `run_sil.py` and rule; do not loosen silently.
- [ ] **Step 4: Run** `cargo test -p ecusim`. Expected: all PASS.
- [ ] **Step 5: Commit.** `"Simulator: scenario library, run folders, ecusim run"`

### Task 7: Paced live runner

**Files:**
- Create: `simulator/crates/ecusim/src/live.rs`
- Test: unit tests in `live.rs`

**Interfaces:**
- Consumes: `Sim`, `seq`, `check`, `runs` (Tasks 4–6).
- Produces:
  - `pub enum Cmd { Line(String), Script(Script), Run, Pause, Stop, Reset, Speed(Option<f64>), Firmware(Arc<Firmware>) }`. `Speed(None)` means max.
  - `pub fn spawn(fw: Arc<Firmware>, runs_dir: PathBuf) -> (mpsc::Sender<Cmd>, Hub)`.
  - `Hub`: `subscribe() -> mpsc::Receiver<String>` gives SSE `event:`/`data:` text blocks. `publish` drops a subscriber whose send fails.
  - The thread publishes these events:
    - `rows` every 50 ms of wall time: one row per 10 ms of sim time, as JSON arrays in Row order;
    - `can` new frames;
    - `dm1` the latest DTCs and lamps;
    - `status`: sim seconds, target and reached speed, firmware name, `running|paused|stopped`;
    - `event`: an applied action or state change, in script syntax;
    - `report`: the outcomes and run folder at the end of a run.
  - Pacing: after every 10 sim-ms, sleep until `wall >= start + sim/speed`. The reached speed is measured over the last second.
  - A `Line` is parsed as one action, applied at the current sim time, and appended to the events. Stop writes the run folder, with `end` at the stop time. A script ends by itself at `end_us`, then evaluates and writes.
- [ ] **Step 1: Write the failing tests:**
  - `pacing_1x`: `Run` at speed 1 for 2 sim-s takes 2 s of wall time within 5 %.
  - `line_applies_now`: `Line("load 20")` at about 1 s gives `eng.load_kw == 20`, and the events hold `<t> load 20`.
  - `stop_writes_folder`: its `events.txt` parses.
  - `script_reports`: `01-start` at max sends a `report` with all checks passing.
  - `bad_line_reported`: `Line("load")` publishes an `event` error and does not stop the run.
- [ ] **Step 2: Run** `cargo test -p ecusim live`. Expected: FAIL.
- [ ] **Step 3: Implement** `live.rs`. The sim thread owns the `Sim` and polls commands with `try_recv` between 10 ms chunks; while paused or stopped it uses `recv_timeout(100 ms)`.
- [ ] **Step 4: Run** `cargo test -p ecusim live`. Expected: all PASS.
- [ ] **Step 5: Commit.** `"Simulator: paced live runner"`

### Task 8: HTTP server and browser UI

**Files:**
- Create: `simulator/crates/ecusim/src/server.rs`
- Create: `simulator/crates/ecusim/ui/{index.html,app.js,app.css,uPlot.iife.min.js,uPlot.min.css,LICENSE-uPlot}`, with uPlot 1.6.30 from `https://unpkg.com/uplot@1.6.30/dist/`
- Modify: `simulator/crates/ecusim/src/main.rs` (bare `ecusim`, `--port`, `--share`)
- Test: `simulator/crates/ecusim/tests/server.rs`

**Interfaces:**
- Consumes: `live::spawn`, `Cmd`, `Hub` (Task 7); `LIBRARY` (Task 6); `Firmware::load` (Task 3).
- Produces:
  - `server::bind(port: u16, share: bool) -> (tiny_http::Server, u16)` tries `port`, then the next 20.
  - `server::serve(server, tx, hub, share, runs_dir)` handles the routes of spec §6. UI files come from `include_bytes!`. `/events` streams the hub over a chunked response, one thread per subscriber.
  - `POST /cmd` takes a line or `run|pause|stop|reset|speed <x|max>`. `POST /scenario` returns 400 with `[{line,msg}]` JSON on parse errors. `POST /firmware` writes the body to a temp file and calls `Firmware::load`; it returns 403 under share and 400 with the message on refusal. `GET /library` lists the bundled scripts plus `./scenarios/*.seq`.
  - Bare `ecusim` binds, prints the URL, and opens it with `webbrowser`.
- [ ] **Step 1: Write the failing tests** (a server on a free port, plain `std::net::TcpStream` HTTP):
  - `port_busy_takes_next`: hold 8025 (or the test's port) and expect the next.
  - `cmd_load_applies`.
  - `scenario_errors_have_lines`.
  - `firmware_refused_under_share`: 403.
  - `firmware_garbage_400`.
  - `library_lists_sil`: 16 sil entries.
  - `sse_subscriber_dropped_on_disconnect`: open `/events`, read one block, close it, run 200 ms more. The hub has 0 subscribers and the run is still running. A new `/events` gets blocks.
- [ ] **Step 2: Run** `cargo test -p ecusim --test server`. Expected: FAIL.
- [ ] **Step 3: Implement `server.rs` and the UI** (spec §6 panels).
  - `app.js`: an `EventSource('/events')`; uPlot charts keep the last 30 s and show the whole run when stopped.
  - Controls post `/cmd`. The scenario editor is a `<textarea>` with drag-and-drop, Open… (`<input type=file>`) and Save as… (a Blob download); parse errors are marked by line.
  - Load firmware… sends the file input's bytes to `POST /firmware`. The firmware panel shows "load only firmware you trust".
  - The runs list reads `trace.csv` into the charts.
  - Colours are CSS variables, with a dark scheme under `prefers-color-scheme`.
- [ ] **Step 4: Run** `cargo test -p ecusim`. Expected: all PASS.
- [ ] **Step 5: Check by hand** with `cargo run -p ecusim --release`:
  - Start: the charts move and DM1 shows SPN 628 FMI 13 only if the EOL is not loaded (it is, so DM1 is clear).
  - A 20 kW load step, then `sensor clt open`: DM1 shows 110/3.
  - Run `16-overload` at 10×.
  - Load a `fwbuild` library.
  - Reload the tab mid-run.

  Note what was seen in the ledger.
- [ ] **Step 6: Commit.** `"Simulator: browser UI and server"`

### Task 9: CI, guide, project docs

**Files:**
- Create: `.github/workflows/simulator.yml`, `simulator/README.md`
- Modify: `README.md` (one line pointing at `simulator/`), `docs/firmware.md` (`ecu_abi_version` row in the entry-point table), `docs/decisions-log.md` (§17, the simulator), `docs/status.md`, `docs/HANDOFF.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the workflow.** It runs on push and pull requests touching `simulator/**`, `firmware/core/**` or the workflow, with a matrix of `windows-latest`, `macos-latest` and `ubuntu-latest`. Its steps, with working dir `simulator`:
  - `cargo test --workspace --release`;
  - `cargo build --release -p ecusim`;
  - `target/release/ecusim run scenarios/sil/*.seq --out ci-runs`, run as a bash step;
  - `cargo run --release -p fwbuild`;
  - upload artifacts `ecusim-<os>` (the binary, renamed `ecusim-windows.exe`, `ecusim-macos`, `ecusim-linux`) and `ecu_fw-<os>`.

  Run `cargo test --workspace --release` locally. Expected: all PASS. Check the YAML with `python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" .github/workflows/simulator.yml`; use the `.venv` python if PyYAML is there, otherwise skip the check and ledger it.
- [ ] **Step 2: Write `simulator/README.md`.**
  - First section, for the friend on Windows: download from the Actions artifacts, unzip, double-click, SmartScreen "More info → Run anyway", the browser opens.
  - Then: live controls; loading and writing scripts (the action and check tables, linked to the spec); loading firmware (`fwbuild`, the CI artifacts, the trust warning); run folders; `ecusim run`; building from source (`cargo build --release -p ecusim`; on Windows, Rust with the MSVC build tools).
- [ ] **Step 3: Update the project docs.**
  - decisions-log §17: all Rust; the bundled plus loadable firmware; the ABI check; the Python SIL kept as the firmware gate; the `change` check added.
  - status, HANDOFF (traps: `Firmware::load` copies to a temp name because the OS caches the path; one instance per process; bump `ECU_ABI_VERSION` with `ecu_io`).
  - Rebuild the PDF: `cd docs && CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ../.venv/bin/python build_pdf.py`. Expected: it builds without error.
- [ ] **Step 4: Run the whole check:**
  - `cd simulator && cargo test --workspace --release`;
  - `make -C firmware/sim test`;
  - `.venv/bin/python firmware/sim/run_sil.py`.

  Expected: all PASS, 16/16.
- [ ] **Step 5: Commit.** `"Simulator: CI for three OSes, user guide, decisions §17"`
