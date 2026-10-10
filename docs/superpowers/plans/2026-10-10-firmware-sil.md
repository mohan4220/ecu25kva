# Firmware core + engine simulator (SIL) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Engine-control firmware as portable C99, proven on the PC against a Python engine model by 11 PASS/FAIL scenarios.

**Architecture:** `firmware/core/` is hardware-free C: one `ecu_io` struct carries all inputs and outputs, and module state lives in `static` instances inside `ecu.c`. Each module takes its own state pointer so it can be unit-tested alone in `firmware/sim/test_core.c`. `firmware/sim/` builds the core into a shared library. `ecu.py` wraps it with ctypes, `engine.py` is the plant, and `run_sil.py` runs the scenarios using `Checks` from `sim/run_sim.py`.

**Tech Stack:** C99 (Apple clang, `-Wall -Wextra -Werror -std=c99`), make, Python 3 + numpy from `.venv`, ctypes.

**Spec:** `docs/superpowers/specs/2026-10-10-firmware-sil-design.md`

## Global Constraints

- `firmware/core/` is C99, with no heap, no OS, no blocking, and no hardware headers. Only `<stdint.h>`, `<stddef.h>`, `<string.h>` and `<math.h>` are allowed.
- All time arithmetic uses `uint32_t` µs with unsigned differences (`(uint32_t)(t - t0)`), so it survives wrap-around.
- Every assumed constant is a `#define` in its module's header with a `/* assumed */` or `/* calibration */` comment. These are the knobs the real engine will need.
- 60-2 wheel, 1 cam pulse per 720°, firing order 1-2-3 at 240°, overspeed **1650 rpm** latched, isochronous **1500 rpm**, droop **4 %**, rail setpoint **1000 bar**, normally-open metering, SOI **5° BTDC**.
- J1939: SA **234**, ID = `prio << 26 | pgn << 8 | sa`. EEC1 61444 at 20 ms, ET1 65262 at 1 s, EFL/P1 65263 at 500 ms, DM1 65226 at 1 s. Unavailable values are 0xFF.
- SHUTDOWN is cleared only by ignition low and then high.
- Commits carry no AI attribution trailer, matching the repo's history.
- Build outputs go in `firmware/sim/build/`, which is git-ignored.

## Decisions this plan takes inside the spec's latitude

| Item | Choice | Why |
|---|---|---|
| Crank timeout | **50 ms** without an edge while running = sync loss | Spec §7 #6 says "within 100 ms". A 100 ms timeout plus tick slack would miss that by about 1 ms. At 400 rpm the longest gap (the missing teeth) is 7.5 ms. |
| Watchdog kick | WDI toggles every **5 ms** (falling edge every 10 ms). The scenario window is **5–20 ms** | Spec §4.6 said toggle every tick. A 10 ms period lets the TPS3850 window (CWD/SET0/SET1, still OPEN on the MCU sheet) close well inside 26.67 ms. The real strap values are recorded in Task 10. |
| Wheel angle | Edge *n* after the gap is at *n*·6° of the revolution. The revolution after the one holding the cam edge is rev 0. Cycle angle = rev·360 + n·6. Cylinder 1 TDC (firing) is at `CRANK_TDC1_DEG` = **90°** (calibration) | One convention, shared by `crank.c` and `engine.py` |
| Droop law | `set = 1500·(1 − 0.04·fuel/FUEL_RATED_MG)`, with FUEL_RATED_MG = **34 mg** (fuel at 20 kW) | Scenario 4 measures at full load, and 34 mg is full load |
| Sensor scaling | All channels ratiometric: `vr = v·5/v_5v` (v_5v outside 4.5–5.5 V → use 5.0). Valid 0.2–4.8 V. Coolant: NTC 2.5 kΩ@20 °C, β 3450, 2.49 kΩ pull-up. Oil 0.5–4.5 V = 0–1000 kPa. Rail 0.5–4.5 V = 0–1800 bar. Boost 0.5–4.5 V = 50–400 kPa. EGR 0.5–4.5 V = 0–100 % | Placeholder front-ends. The real tables replace these per channel. |
| Sensor SPNs / defaults | coolant 110 / 90 °C, oil 100 / 300 kPa, rail 157 / 1000 bar, boost 102 / 100 kPa, EGR 27 / 0 % | J1939-71 SPNs. A defaulted value is *sent* as 0xFF. |
| Shutdown faults | overspeed SPN 190 FMI 0; sync loss SPN 636 FMI 2. Red-stop lamp for these, amber for sensor faults. Ignition off: no fault | J1939-73 |
| Occurrence count | Always 1 | `ponytail:` true counting needs non-volatile storage, which arrives with the S32K148 port |

## Review Focus

1. **Rail sensor reading 0 bar or faulted** → `inject_dur_us` must not divide by zero or blow up. Clamp rail to `INJ_RAIL_MIN` 100 bar. (Test in Task 4.)
2. **`v_5v` = 0 V (sensor-supply short)** → no divide by zero, and the channels still report. Use 5.0 V. (Test in Task 3.)
3. **SOI that lands in the missing-tooth gap** (a calibration move) → the cylinder is still scheduled once per cycle, because the "next edge" angle is gap-aware. (Test in Task 4.)
4. **CAN queue full because the host didn't drain it** → frames are dropped and counted in `can_drops`, never written past `ECU_CANQ`. (Test in Task 7.)
5. **`uint32_t` µs wrap at 71.6 min** → crank rpm and timeout stay correct across the wrap. (Test in Task 2.)

---

## File Structure

```
firmware/core/ecu.h       ecu_io struct, ecu_state, 4 entry points, ecu_io_size()
firmware/core/ecu.c       static module instances, state machine, rate scheduler
firmware/core/crank.{c,h} 60-2 + cam decoder
firmware/core/sensors.{c,h}
firmware/core/govern.{c,h}
firmware/core/rail.{c,h}
firmware/core/inject.{c,h}
firmware/core/safety.{c,h} trip decision + fault table
firmware/core/j1939.{c,h}  frame builders
firmware/sim/Makefile      `make` → build/libecu.dylib, `make test` → build/test_core and run it
firmware/sim/test_core.c   C unit tests, all modules, one file
firmware/sim/ecu.py        ctypes wrapper
firmware/sim/engine.py     plant model, self-check in __main__
firmware/sim/run_sil.py    11 scenarios
```

---

### Task 1: Interface, build, ctypes wrapper

**Files:**
- Create: `firmware/core/ecu.h`, `firmware/core/ecu.c` (stub), `firmware/sim/Makefile`, `firmware/sim/test_core.c`, `firmware/sim/ecu.py`
- Modify: `.gitignore` (add `firmware/sim/build/`)

**Interfaces — Produces** (`ecu.h`, exact):

```c
#define ECU_NCYL 3
#define ECU_CANQ 16
typedef enum { ECU_OFF, ECU_WAIT, ECU_CRANK, ECU_RUN, ECU_SHUTDOWN } ecu_state;
typedef struct { uint32_t id; uint8_t len; uint8_t data[8]; } ecu_can;
typedef struct { uint32_t start_us, dur_us, seq; } ecu_inj; /* seq++ per new command; dur_us 0 = cancelled */
typedef struct {
    /* inputs (host writes) */
    float v_clt, v_oil, v_rail, v_boost, v_egr, v_5v;
    uint8_t ignition, droop_sw;
    /* outputs (host reads) */
    ecu_inj inj[ECU_NCYL];
    float meter_duty;            /* 0..1, normally open: more duty, less flow */
    uint8_t wdg;                 /* WDI pin level */
    ecu_can can[ECU_CANQ];
    uint8_t can_n;               /* host reads can[0..can_n), then sets can_n = 0 */
    uint16_t can_drops;
    /* status */
    uint8_t state, fault_n, synced;   /* synced = crank_synced() */
    float rpm, fuel_mg, rail_bar, clt_c, oil_kpa;
} ecu_io;
void ecu_init(ecu_io *io);
void ecu_crank_edge(ecu_io *io, uint32_t t_us);
void ecu_cam_edge(ecu_io *io, uint32_t t_us);
void ecu_tick_1ms(ecu_io *io, uint32_t t_us);
size_t ecu_io_size(void);
```

`ecu.py` produces `class Ecu` with `init()`, `crank_edge(t_us)`, `cam_edge(t_us)`, `tick(t_us)`, `drain_can() -> list[tuple[int, bytes]]`, and the attribute `io` (the ctypes `IO` structure). It loads `build/libecu.dylib` (or `.so`) relative to its own file.

Test harness in `test_core.c`: `#define CHECK(c)` prints file:line on failure and counts it. `main` calls each `test_*` function and returns nonzero if anything failed.

- [ ] **Step 1:** Write `test_io_size`: `CHECK(ecu_io_size() == sizeof(ecu_io))`, then `ecu_init` on a zeroed `ecu_io` and `CHECK(io.state == ECU_OFF)`.
- [ ] **Step 2:** Run `make -C firmware/sim test`. It is expected to fail because ecu.c doesn't exist yet.
- [ ] **Step 3:** Write `ecu.h` as above. Write the `ecu.c` stub: init memsets the outputs and sets state OFF; the other entry points are empty. Write the Makefile: `CFLAGS=-std=c99 -Wall -Wextra -Werror -O2 -I../core`, targets `build/libecu.dylib` (`-shared -fPIC`), `build/test_core`, and `test` (builds and runs).
- [ ] **Step 4:** Write `ecu.py` so that it raises an error if `ctypes.sizeof(IO) != lib.ecu_io_size()`. Its `__main__` constructs an `Ecu`, calls `init()`, and asserts `io.state == 0`.
- [ ] **Step 5:** Run `make -C firmware/sim test && make -C firmware/sim && .venv/bin/python firmware/sim/ecu.py`. Expected: 0 failures, exit 0.
- [ ] **Step 6:** Commit with the message "Firmware: the ecu_io interface, build and ctypes wrapper".

### Task 2: Crank and cam decoder

**Files:** Create `firmware/core/crank.{c,h}`. Test: `test_core.c`.

**Interfaces — Produces:**

```c
#define CRANK_TEETH 60
#define CRANK_TDC1_DEG 90.0f         /* calibration: cycle angle of cyl 1 firing TDC */
#define CRANK_TIMEOUT_US 50000u
enum { CRANK_F_NONE, CRANK_F_GAP, CRANK_F_TIMEOUT };
typedef struct { /* implementer's */ } crank_t;
void  crank_reset(crank_t *c);
void  crank_edge(crank_t *c, uint32_t t_us);
void  crank_cam(crank_t *c, uint32_t t_us);
void  crank_poll(crank_t *c, uint32_t t_us);       /* sets CRANK_F_TIMEOUT once synced */
int   crank_synced(const crank_t *c);              /* two gaps 58 edges apart */
int   crank_phased(const crank_t *c);              /* synced + cam seen */
float crank_rpm(const crank_t *c);                 /* 0 until 7 edges */
float crank_angle(const crank_t *c);               /* cycle angle 0..720 of the last edge */
float crank_next_angle(const crank_t *c);          /* angle of the next edge, gap-aware */
float crank_us_per_deg(const crank_t *c);
uint32_t crank_last_us(const crank_t *c);
uint8_t crank_fault(const crank_t *c);
```

Rules (from spec §4.1 and the decisions table):
- Gap edge: period > 1.5 × the previous period. It counts as 18° in rpm.
- rpm = degrees over the last 6 periods ÷ elapsed time.
- Once synced, a gap at any edge count other than 58, or a non-gap at count 58, sets `CRANK_F_GAP`. Before sync, the same condition just restarts sync.
- The cam sets the phase so that the revolution after the cam edge is rev 0.

The test helper `feed(crank_t*, float rpm, int edges, uint32_t *t, int start_tooth)` generates 60-2 edge times. It is reused in Tasks 4 and 7, so declare it `static` near the top of test_core.c.

- [ ] **Step 1:** Write the tests:
  - `test_crank_sync`: from a random start tooth at 600 rpm, synced within ≤ 116 edges, and `crank_rpm` within 0.5 % of 600.
  - `test_crank_rpm_gap`: rpm stays within 0.5 % while the gap is in the 6-period window.
  - `test_crank_phase`: after a cam edge, the first edge after the next gap has `crank_angle == 0`, and the edge 15 later has 90.
  - `test_crank_bad_gap`: synced, then one missing edge in mid-wheel → `CRANK_F_GAP`.
  - `test_crank_timeout`: synced, then `crank_poll` at last+49 ms → none, and at last+51 ms → `CRANK_F_TIMEOUT`.
  - `test_crank_wrap`: start `t` at `0xFFFFFFFF - 20000`, run across the wrap, and rpm stays within 0.5 % with no timeout.
- [ ] **Step 2:** Run `make -C firmware/sim test`. Expected to fail at link (undefined `crank_*`).
- [ ] **Step 3:** Implement `crank.c`. Add it to the Makefile's source list.
- [ ] **Step 4:** Run `make -C firmware/sim test`. Expected: 0 failures.
- [ ] **Step 5:** Commit with the message "Firmware: 60-2 crank and cam decoder".

### Task 3: Sensors

**Files:** Create `firmware/core/sensors.{c,h}`. Test: `test_core.c`.

**Interfaces — Produces:**

```c
enum { S_CLT, S_OIL, S_RAIL, S_BOOST, S_EGR, S_N };
typedef struct { float val[S_N]; uint16_t bad_ms[S_N]; uint8_t fmi[S_N]; } sens_t;  /* fmi 0 = ok, 3 high, 4 low */
extern const uint32_t sens_spn[S_N];      /* 110, 100, 157, 102, 27 */
void  sens_reset(sens_t *s);              /* vals = defaults, no faults */
void  sens_step_1ms(sens_t *s, const float v[S_N], float v_5v);
float sens_convert(int ch, float v_ratiometric);   /* pure transfer function */
```

Scaling, ranges and defaults come from the decisions table. A fault sets after 100 consecutive out-of-range ms and clears after 100 in range. While faulted, `val` is the default.

- [ ] **Step 1:** Write the tests:
  - `test_sens_convert`:
    - CLT at 2.5 V (R = 2490 Ω): about 20.1 °C ± 0.5
    - oil 2.5 V = 500 kPa
    - rail 4.5 V = 1800 bar
    - boost 0.5 V = 50 kPa
    - EGR 2.5 V = 50 %
  - `test_sens_ratiometric`: rail 2.25 V with v_5v 4.5 → same as 2.5 V at 5.0.
  - `test_sens_open`: CLT 4.95 V for 99 ms → fmi 0, at 100 ms → fmi 3, and val 90.
  - `test_sens_low`: oil 0.1 V for 100 ms → fmi 4.
  - `test_sens_5v_short`: `v_5v` 0.0 with all channels 2.5 V → no NaN/inf in val, and no faults.
- [ ] **Step 2:** Run `make -C firmware/sim test`. Expected to fail.
- [ ] **Step 3:** Implement. Use `logf` for the NTC.
- [ ] **Step 4:** Run `make -C firmware/sim test`. Expected: 0 failures.
- [ ] **Step 5:** Commit with the message "Firmware: sensor conversion and range faults".

### Task 4: Governor, rail control, injection

**Files:** Create `firmware/core/govern.{c,h}`, `rail.{c,h}`, `inject.{c,h}`. Test: `test_core.c`.

**Interfaces — Consumes:** `crank_t` and `crank_*` (Task 2), `ecu_inj` (Task 1).

**Interfaces — Produces:**

```c
/* govern.h */
#define GOV_RPM_SET 1500.0f
#define GOV_DROOP 0.04f
#define FUEL_MAX_MG 45.0f     /* assumed */
#define FUEL_RATED_MG 34.0f   /* assumed: fuel at 20 kW */
#define GOV_KP 0.15f          /* calibration, mg/rpm */
#define GOV_KI 0.6f           /* calibration, mg/(rpm*s) */
typedef struct { float integ, fuel; } gov_t;
void  gov_reset(gov_t *g, float fuel0);           /* bumpless: integ = fuel0 */
float gov_setpoint(float fuel, int droop);
float gov_step(gov_t *g, float rpm, int droop, float dt_s);   /* returns fuel mg in [0, FUEL_MAX_MG] */

/* rail.h */
#define RAIL_SET_BAR 1000.0f
#define RAIL_KP 0.0005f       /* calibration, duty/bar */
#define RAIL_KI 0.002f        /* calibration, duty/(bar*s) */
#define RAIL_DUTY_LIMP 0.3f   /* calibration: fixed duty while the rail sensor is faulted */
typedef struct { float integ; } rail_t;
void  rail_reset(rail_t *r);
float rail_step(rail_t *r, float rail_bar, float dt_s);  /* duty [0,1], rises when pressure is high */

/* inject.h */
#define INJ_SOI_BTDC 5.0f     /* calibration */
#define INJ_DEAD_US 300.0f    /* assumed */
#define INJ_K 0.0009f         /* assumed: mg/us per sqrt(bar) */
#define INJ_RAIL_MIN 100.0f
#define FUEL_START_MG 30.0f   /* calibration */
uint32_t inject_dur_us(float fuel_mg, float rail_bar);   /* 0 if fuel <= 0 */
void inject_edge(const crank_t *c, float fuel_mg, float rail_bar, ecu_inj out[ECU_NCYL]);
int  inject_due(const crank_t *c, float soi_deg);        /* angle <= soi < next_angle, 720-wrap aware */
void inject_cancel(ecu_inj out[ECU_NCYL]);              /* dur_us = 0, seq unchanged */
```

- Duration: `dead + fuel / (INJ_K·sqrt(max(rail, INJ_RAIL_MIN)))`.
- `inject_edge` is called on each edge when phased. For cylinder index k (0, 1, 2 = cylinders 1, 2, 3), SOI = `CRANK_TDC1_DEG + 240k − INJ_SOI_BTDC` mod 720. If `crank_angle ≤ SOI < crank_next_angle` (with the 720 wrap handled), it writes start = `last_us + (SOI − angle)·us_per_deg`, writes dur, and does `seq++`.
- Both PIs clamp the integrator to the output range (anti-windup).

- [ ] **Step 1:** Write the tests:
  - `test_gov`:
    - rpm 1400 for 1 s from `gov_reset(g, 10)` → fuel rises and saturates at 45
    - rpm 1600 → fuel 0, with integ ≥ 0 (no windup)
    - `gov_setpoint(34, 1)` = 1440 ± 0.1
    - `gov_setpoint(34, 0)` = 1500
  - `test_rail`: 1100 bar → duty rises over 1 s; 500 bar → duty 0; duty always within [0, 1].
  - `test_inject_dur`:
    - `inject_dur_us(34, 1000)` = 300 + 34/(0.0009·√1000) ± 2 µs
    - `inject_dur_us(10, 0)` finite and equal to `inject_dur_us(10, 100)`
    - `inject_dur_us(0, 1000) == 0`
  - `test_inject_once_per_cycle`: feed 2 phased cycles at 1500 rpm, calling `inject_edge` each edge → each cylinder's `seq` advanced by exactly 2, and cylinder 1's start is at the predicted 85° time ± 5 µs.
  - `test_inject_soi_in_gap`: `inject_due(c, 350.0f)` (inside the gap) is true on exactly one edge per cycle over 2 cycles.
- [ ] **Step 2:** Run `make -C firmware/sim test`. Expected to fail.
- [ ] **Step 3:** Implement the three modules.
- [ ] **Step 4:** Run `make -C firmware/sim test`. Expected: 0 failures.
- [ ] **Step 5:** Commit with the message "Firmware: speed governor, rail pressure loop, injection scheduling".

### Task 5: Safety decision and fault table

**Files:** Create `firmware/core/safety.{c,h}`. Test: `test_core.c`.

**Interfaces — Produces:**

```c
#define OVERSPEED_RPM 1650.0f
#define SPN_SPEED 190u
#define SPN_POS 636u
enum { TRIP_NONE, TRIP_OVERSPEED, TRIP_SYNC, TRIP_IGN };
int safety_check(float rpm, uint8_t crank_fault, uint8_t ignition, int running); /* priority: overspeed, sync, ignition */
typedef struct { uint32_t spn; uint8_t fmi, oc; } fault_t;
typedef struct { fault_t f[8]; uint8_t n; } faults_t;
void faults_set(faults_t *t, uint32_t spn, uint8_t fmi);    /* idempotent; oc = 1; ignores when full */
void faults_clear(faults_t *t, uint32_t spn, uint8_t fmi);
```

- `TRIP_SYNC` only when `running`.
- Overspeed in any state.

- [ ] **Step 1:** Write the tests:
  - `test_safety`:
    - 1651 rpm → OVERSPEED
    - 1649 → NONE
    - a sync fault with running 0 → NONE, and with 1 → SYNC
    - ignition 0 → IGN
    - overspeed with ignition 0 → OVERSPEED
  - `test_faults`: set twice → n 1; set 9 distinct → n 8; clear → n 7 with the others intact.
- [ ] **Step 2:** Run `make -C firmware/sim test`. Expected to fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `make -C firmware/sim test`. Expected: 0 failures.
- [ ] **Step 5:** Commit with the message "Firmware: trip decision and fault table".

### Task 6: J1939 frames

**Files:** Create `firmware/core/j1939.{c,h}`. Test: `test_core.c`.

**Interfaces — Consumes:** `faults_t` (Task 5), `ecu_can` (Task 1).

**Interfaces — Produces:**

```c
#define J1939_SA 234
#define LAMP_RED 0x10
#define LAMP_AMBER 0x04
uint32_t j1939_id(uint8_t prio, uint32_t pgn, uint8_t sa);
void j1939_eec1(ecu_can *f, float rpm);                    /* prio 3, PGN 61444 */
void j1939_et1(ecu_can *f, float clt_c, int valid);        /* prio 6, PGN 65262 */
void j1939_eflp1(ecu_can *f, float oil_kpa, int valid);    /* prio 6, PGN 65263 */
int  j1939_dm1(ecu_can *out, int max, const faults_t *t, uint8_t lamps); /* frames written */
```

- All unused bytes are 0xFF.
- EEC1: `data[3..4]` = rpm/0.125, little-endian.
- ET1: `data[0]` = clt + 40.
- EFL/P1: `data[3]` = oil/4, `data[7]` = 0xFF (no level sensor).
- DM1 with ≤ 1 fault is one frame. Bytes: `lamps, 0xFF`, then the DTC, padded with 0xFF. With no faults the DTC is `00 00 00 00`.
- DTC encoding: `spn & 0xFF, (spn >> 8) & 0xFF, ((spn >> 11) & 0xE0) | fmi, oc & 0x7F`.
- DM1 with > 1 fault is BAM:
  - TP.CM: prio 7, PGN 0xECFF. Data `32, size_lo, size_hi, npkts, 0xFF, 0xCA, 0xFE, 0x00`.
  - Then the TP.DT frames: PGN 0xEBFF, `seq, 7 bytes`, with the last frame padded with 0xFF.

- [ ] **Step 1:** Write the tests:
  - `test_j1939_id`: `j1939_id(3, 61444, 234) == 0x0CF004EA`.
  - `test_eec1`: rpm 1500 → `data[3] == 0xE0 && data[4] == 0x2E`.
  - `test_et1`: 90 °C → `data[0] == 130`; invalid → 0xFF.
  - `test_dm1_single`: SPN 110 FMI 3 → `data[2..5] == 6E 00 03 01` and len 8.
  - `test_dm1_bam`: 3 faults → returns 1 + 2 frames; the CM byte 1 is size 14; the DT seqs are 1 and 2.
  - `test_dm1_spn_high`: SPN 520192 (0x7F000) → `data[4]` = 0xF0, high bits in `data[5]` = 0xE0 | fmi.
- [ ] **Step 2:** Run `make -C firmware/sim test`. Expected to fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `make -C firmware/sim test`. Expected: 0 failures.
- [ ] **Step 5:** Commit with the message "Firmware: J1939 EEC1, ET1, EFL/P1 and DM1 frames".

### Task 7: State machine and scheduler (`ecu.c`)

**Files:** Modify `firmware/core/ecu.c`. Test: `test_core.c`.

**Interfaces — Consumes:** everything from Tasks 2–6.

**Interfaces — Produces:** the behaviour of the 4 entry points:

- **`ecu_crank_edge`:**
  - WAIT → CRANK on the first edge.
  - Calls `crank_edge`, then runs `safety_check` and acts on any trip immediately (the overspeed check runs on every edge).
  - If phased and in CRANK or RUN: `inject_edge` with `FUEL_START_MG` in CRANK and `gov` fuel in RUN.
  - CRANK → RUN when phased and rpm ≥ 400; `gov_reset(fuel = FUEL_START_MG)`.
  - In WAIT or CRANK, a crank fault resets the decoder instead of tripping.
- **`ecu_tick_1ms`:**
  - `crank_poll` and `sens_step_1ms`; sensor faults are mirrored into `faults_t` (set and clear).
  - `safety_check`.
  - The governor runs in RUN with dt 0.001. The rail loop runs in CRANK and RUN; otherwise duty is 0. If the rail sensor is faulted, duty is fixed at `RAIL_DUTY_LIMP` 0.3.
  - WDI toggles every 5 ms.
  - CAN scheduling in every state except OFF: EEC1, ET1, EFL/P1 and DM1 at their rates. BAM DT frames go out one per 50 ms after the CM.
  - Updates the status fields.
  - Ignition handling: OFF and ignition high → WAIT. SHUTDOWN, then ignition low, then high → full re-init, then WAIT.
- **Trip:**
  - state = SHUTDOWN, `inject_cancel`, duty 0.
  - Overspeed → fault SPN 190 FMI 0. Sync → SPN 636 FMI 2. Ignition → no fault.
  - The lamp is red if any shutdown fault is set, amber if any other fault, else 0.
- **Queueing:** a full queue increments `can_drops` and never writes past `ECU_CANQ`.

- [ ] **Step 1:** Write the tests. Use the Task 2 `feed` helper plus the cam, and `ignition = 1`, `v_* = 2.5`, `v_5v = 5`.
  - `test_ecu_start`: 300 rpm for 3 revs → CRANK, inj seq advancing. 600 rpm → RUN.
  - `test_ecu_overspeed_edge`:
    - In RUN, feed edges ramping to 1700 rpm, with no tick calls.
    - The state is SHUTDOWN at the first edge where rpm > 1650, all `dur_us == 0`, and seqs are frozen through 1 more rev.
    - DM1 carries SPN 190.
  - `test_ecu_ignition`: ignition 0 → SHUTDOWN, `fault_n == 0`. Then 1 → WAIT.
  - `test_ecu_crank_loss`: in RUN, ticks only, for 51 ms → SHUTDOWN, SPN 636.
  - `test_ecu_wdg`: 100 ticks → `wdg` changes exactly every 5 ticks.
  - `test_ecu_can_rates`: 1000 ticks with draining → 50 EEC1, 1 ET1, 2 EFL/P1, 1 DM1.
  - `test_ecu_can_overflow`: 1000 ticks without draining → `can_n == ECU_CANQ`, `can_drops > 0`.
- [ ] **Step 2:** Run `make -C firmware/sim test`. Expected to fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `make -C firmware/sim test`. Expected: 0 failures.
- [ ] **Step 5:** Commit with the message "Firmware: state machine, safety latch and rate scheduler".

### Task 8: Engine model

**Files:** Create `firmware/sim/engine.py` (self-check in `__main__`).

**Interfaces — Produces:**

```python
class Engine:
    # assumed constants at module top, each with a comment:
    # J=2.0 kg m2, LHV*eta_i = 17.9 J/mg, friction = 10 + 0.006*rpm N m,
    # gen eff 0.9, starter 100 N m * (1 - rpm/150) >= 0,
    # rail: V/B -> 750 bar/cm3, pump 4/1500 cm3/s/rpm * (1-duty), leak 1e-4 cm3/s/bar, relief 1800,
    # 1 mg fuel = 0.0012 cm3, injector: same INJ_DEAD_US / INJ_K law as the firmware
    rpm: float; rail_bar: float; clt_c: float
    load_kw: float = 0; starter: bool = False
    clt_open = False; stuck_fuel_mg: float | None = None; crank_lost = False
    def command(self, cyl: int, start_us: int, dur_us: int, seq: int) -> None  # latch new seq; dur 0 cancels if not yet started
    def step(self, t_us: int, dt_us: int = 20) -> tuple[list[int], list[int]]  # crank, cam edge times inside the step
    def volts(self) -> dict  # keys v_clt v_oil v_rail v_boost v_egr v_5v
```

- **Wheel:** edges at n·6° for n = 0..57 of each revolution. Cam edge at cycle angle 660°.
- **Combustion:** the fuel actually delivered (dur − dead)·K·√rail is integrated against the rail pressure. Its work is released as constant torque over 0–180° after that cylinder's TDC. Stuck fuel replaces the commanded mass every cycle.
- **Edge timing:** an edge time is interpolated inside the step.
- **Sensors:** coolant starts at 80 °C, τ 60 s towards 75 + 15·load/20 kW. Oil = 400·rpm/1500 kPa. Boost = 100 + 100·load/20. EGR 0 %.
  - Convert to volts with the inverse of the Task 3 scaling.
  - `clt_open` → 5.0 V; `crank_lost` → no crank edges.

- [ ] **Step 1:** Write the self-check `__main__` with asserts:
  - starter only, 2 s → 140 ≤ rpm ≤ 150
  - held at 1500 rpm with 34 mg per event and 20 kW load → |net torque| < 10 % of the load torque
  - one simulated revolution at 1500 rpm gives 58 crank edges and the cam once per 2 revs
  - no fuel and duty 0 at 150 rpm → rail rising
- [ ] **Step 2:** Run `.venv/bin/python firmware/sim/engine.py`. Expected to fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `.venv/bin/python firmware/sim/engine.py`. Expected: exit 0.
- [ ] **Step 5:** Commit with the message "SIL: engine, generator and rail model".

### Task 9: Scenarios

**Files:** Create `firmware/sim/run_sil.py`. Modify only the calibration constants in `govern.h`, `rail.h` and `inject.h` if tuning needs it.

**Interfaces — Consumes:** `Ecu` (Task 1), `Engine` (Task 8), `Checks` (import from `sim/run_sim.py` via `sys.path`).

`run_sil.py` structure:
- A `Sim` class joins `Engine` and `Ecu`. Every 20 µs it steps the engine and passes its edges to the ECU. Every 1 ms it writes the volts, calls `tick` and drains the CAN queue into a log of `(t_us, id, data)`. On a seq change it forwards the injection commands to the engine.
- `run(until_s)` records a trace: t, rpm, state, rail, duty, wdg.
- One function per scenario returns `Checks`.
- `main()` mirrors `run_sim.main`, with name filtering. `python run_sil.py start` runs one scenario.
- It runs `make` first if `build/libecu.*` is older than any `core/*.[ch]`.

| fn | Setup | Checks (spec §7) |
|---|---|---|
| `start` | ignition on, starter until RUN | sync within 2 revs of the first edge; 1500 ± 15 rpm by 5 s |
| `load_step` | settle at 1500 rpm, then 0→20 kW | min rpm > 1350; inside ± 15 rpm within 5 s |
| `load_reject` | 20 kW settled, then →0 | max rpm < 1650; state never SHUTDOWN |
| `droop` | droop_sw 1; 0 kW then 20 kW, settle each | (n0 − n20)/1500 = 0.04 ± 0.01 |
| `runaway` | RUN, stuck_fuel_mg = 80 | SHUTDOWN at the first edge > 1650 rpm (trip rpm < 1660); no seq increase after the trip; DM1 has SPN 190 FMI 0 |
| `crank_loss` | RUN, crank_lost | SHUTDOWN ≤ 100 ms after loss; DM1 has SPN 636 |
| `ignition_off` | RUN, ignition 0 | SHUTDOWN; DM1 shows no DTC; rpm < 50 within 10 s |
| `sensor_open` | RUN, clt_open | DM1 SPN 110 FMI 3 within 1.2 s; state RUN after 3 s |
| `can_content` | RUN 2 s | EEC1 interval 20 ± 2 ms; decoded speed within 0.5 % of engine rpm; ET1, EFL/P1, DM1 intervals 1000/500/1000 ± 2 ms |
| `rail` | RUN 0 and 20 kW, settled | rail within ± 5 % of 1000 bar over the last 2 s |
| `watchdog` | over the whole `start`+`load_step` run | every WDI falling-edge period within 5–20 ms |

- [ ] **Step 1:** Write `run_sil.py` with all 11 scenarios.
- [ ] **Step 2:** Run `.venv/bin/python firmware/sim/run_sil.py`. Record which scenarios fail.
- [ ] **Step 3:** Tune only the `/* calibration */` constants (GOV_KP/KI, RAIL_KP/KI, FUEL_START_MG) until all pass. If a scenario can't pass by tuning, stop and report, because it is a design question. Re-run `make -C firmware/sim test` after every change.
- [ ] **Step 4:** Run `.venv/bin/python firmware/sim/run_sil.py`. Expected: `11/11 scenarios pass`, exit 0. Note the wall time.
- [ ] **Step 5:** Commit with the message "SIL: the eleven scenarios pass".

### Task 10: Bible

**Files:**
- Modify `docs/decisions-log.md`: add a new §11, "Firmware on the PC first (10 October)".
- Modify `docs/status.md`: the phase 4 row and an entry for this work.
- Modify `docs/HANDOFF.md`.
- Modify `README.md`: how to run `make -C firmware/sim test` and `run_sil.py`.
- Modify `hw/gen_sheet_mcu.py` (note text only).
- Run: `docs/build_pdf.py`.

- [ ] **Step 1:** Write §11 in the log's plain-language style. Cover:
  - why the PC comes first
  - the interface struct
  - the decisions table from this plan, including the 50 ms timeout and the 10 ms WDI period
  - the gains the tuning settled on
  - what is assumed (the 60-2 wheel, firing order, sensor tables) and how each is changed
- [ ] **Step 2:** Update the SET0/SET1 OPEN note in `gen_sheet_mcu.py`. Firmware now kicks at a 10 ms period, so the window must accept 5–20 ms. The strap values against the TPS3850 tables stay OPEN until checked, but the period they need is now known. Regenerate the MCU sheet (`scratchpad/regen.sh` or the sheet generator with `--force`). Revert any sheet whose diff is UUID-only.
- [ ] **Step 3:** Run `.venv/bin/python docs/build_pdf.py`. Expected: ECU-Bible.pdf rebuilt with §11 present.
- [ ] **Step 4:** Commit with the message "Bible: record the firmware SIL decisions".
