# Production logging + field fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fault memory, an event log, counters and a trip recorder that survive power-off and are readable over J1939, plus four field fixes, all in the portable core and proven in the SIL.

**Architecture:**
- `nvm.c` owns the persistent image: layout, CRC, slot choice and sealing.
- `log.c` writes into it: events, counters, DTC memory and the trip recorder.
- `ecu.c` wires both into the state machine. Its new `ecu_background` does the save policy and gates the watchdog.
- `j1939.c` gains a generic transport builder, used by DM1, DM2 and DM4.
- The SIL keeps the two NVM slots as Python `bytes`.

**Tech Stack:** C99, make, Python 3 ctypes — as before.

**Spec:** `docs/superpowers/specs/2026-10-11-production-logging-design.md`

## Global Constraints

- All constraints of `docs/superpowers/plans/2026-10-10-firmware-sil.md` still hold: no heap, no hardware headers, unsigned µs arithmetic, assumed values as `#define`s.
- The image is ≤ **4096** bytes. Header: magic **0xEC25**, version **1**, seq, len, CRC-32 (reflected, poly 0xEDB88320).
- No flash write is requested from `ecu_crank_edge` or `ecu_tick_1ms`. Only `ecu_background` sets `nvm_save`.
- Save on these events:
  - DTC first occurrence
  - trip-recorder completion (immediately)
  - entering SHUTDOWN
  - each start (CRANK→RUN)
  - every **3600 s** of engine running

  Rate limit: **10 s**, except a trip, which saves immediately.
- The ms counter wraps at **3 600 000**.
- WDI toggles only while `ecu_background` has run within **50 ms**.
- J1939 requests are answered only when DA is **234** or **255**.
- HOURS is SPN 247 at **0.05 h/bit** (180 s), bytes 1–4. It is sent on request and broadcast every **10 s**.
- Commits carry no AI trailer.

## Decisions this plan takes inside the spec

| Item | Choice | Why |
|---|---|---|
| Recorder trigger | Only overspeed and sync-loss trips, not ignition-off stops | A daily normal stop would otherwise overwrite the last real trip |
| When a trip saves | When the recorder's 50 post samples are done (1 s after the trip), bypassing the limiter | One save carries the whole recording; the ECU stays powered after a trip (U12) |
| Image handed to the host | `ecu_background` seals into a second static copy; `ecu_nvm_image()` returns that copy | The 1 ms tick keeps changing the live image while the host writes |
| Latched faults at an ignition cycle | `reset_all` marks every active DTC-memory entry as previously active | The DTC history must outlive the latch |
| DTC entry layout | status byte: bit 0 active, bit 1 used, bits 4–7 state. Freeze-frame scaling: battery 0.2 V/bit, fuel 0.25 mg/bit, oil 4 kPa/bit, coolant +40 | Fits 24 B |
| DM3 acknowledgement | None sent | `ponytail:` J1939-21 ACK is optional for DM3; add it if U4 says the DSE waits for one |
| One BAM at a time | A DM2/DM4 request that arrives while a BAM is in flight is held and served when it ends | J1939-21 allows one BAM per sender at a time |
| `trips_other` counter | Kept in the layout, never incremented yet | It reserves the slot without a layout-version bump |

## Review Focus

1. **The host never clears `nvm_save`** (storage dead) → the core keeps running and logging in RAM, keeps the request up, and never blocks. Test in Task 3.
2. **An image from an older layout version**, with a valid CRC but version ≠ 1 → it loads as fresh, logs `NVM_RESET`, and is not misread. Test in Task 2.
3. **DM2 requested with nothing stored** → a single DM2 frame with the all-zero DTC. Test in Task 6.
4. **A request addressed to another node** (DA 0) → ignored. Test in Task 6.
5. **The ignition-cycle reset must not wipe history**: after the cycle, the stored DTC is still there as previously active, and the counters are unchanged. Test in Task 4.

---

## File Structure

```
firmware/core/nvm.{c,h}     image layout, crc32, pick/seal/fresh            (new)
firmware/core/log.{c,h}     events, counters, DTC memory, trip recorder     (new)
firmware/core/ecu.{c,h}     new io fields + entry points; field fixes; wiring
firmware/core/j1939.{c,h}   j1939_tp builder; DM2, DM4, HOURS; request parse
firmware/sim/test_core.c    unit tests (helpers ticks()/ecu_spin call ecu_background)
firmware/sim/ecu.py         mirror new fields; nvm_load, nvm_image, background, can_rx
firmware/sim/engine.py      drop_edge_once fault
firmware/sim/run_sil.py     background each ms, slots, power_cycle(); scenarios 12-15
```

---

### Task 1: Field fixes M1, M2, M5

**Files:** Modify `firmware/core/ecu.c`. Test: `firmware/sim/test_core.c`.

**Interfaces — Produces:** `#define MS_WRAP 3600000u` in `ecu.c`. The BAM spacing becomes a countdown, `bam_wait` (ms).

- [ ] **Step 1:** Write the tests:
  - `test_ecu_lost_tooth`: from `ecu_running` at 1500 rpm, skip one edge mid-wheel with `next_edge` without feeding it, then feed 1 edge → state SHUTDOWN, `dm1_first_spn(&io, SPN_POS)`.
  - `test_ecu_ms_wrap`: an ECU in WAIT; tick `MS_WRAP − 100` times without draining, then drain and tick 2000 with draining. Every EEC1 interval is exactly 20 ticks, and every DM1 interval exactly 1000.
  - `test_ecu_bam_not_split`: 3 sensor faults active, so DM1 is a BAM. Tick to the DM1 second without draining, so the queue is full and the CM is dropped. Then drain and tick 300 → no TP.DT frame (PGN 0xEBxx) seen.
- [ ] **Step 2:** Run `make -C firmware/sim test`. Expected: those 3 fail.
- [ ] **Step 3:** Implement:
  - **M1:** in `ecu_crank_edge`, if the crank fault is newly set by this edge while in RUN, `trip(io, TRIP_SYNC)` before `check`.
  - **M2:** after `ms++`, set `ms` to 0 when it reaches `MS_WRAP`. The BAM uses the `bam_wait` countdown.
  - **M5:** if `queue` drops the TP.CM, set `bam_n = 0`. `queue` returns `int` (1 if queued).
- [ ] **Step 4:** Run `make -C firmware/sim test && .venv/bin/python firmware/sim/run_sil.py`. Expected: 0 failures, and 11/11.
- [ ] **Step 5:** Commit with the message "Firmware: field fixes — lost-tooth diagnosis, hourly ms wrap, no split BAM".

### Task 2: The persistent image

**Files:**
- Create `firmware/core/nvm.{c,h}`.
- Modify `firmware/core/ecu.{c,h}` and `firmware/sim/ecu.py`.
- Test: `test_core.c`.

**Interfaces — Produces** (`nvm.h`):

```c
#define NVM_MAGIC 0xEC25u
#define NVM_VERSION 1u
#define NVM_DTCS 16
#define NVM_EVENTS 64
#define REC_PRE 100
#define REC_POST 50
typedef struct { uint16_t magic, version; uint32_t seq, len, crc; } nvm_hdr;
typedef struct { uint32_t ecu_s, engine_s, starts; uint16_t trips_overspeed, trips_sync, trips_other, wdg_resets;
                 uint32_t band_s[5]; uint32_t spare[2]; } nvm_counters;
typedef struct { uint32_t spn; uint8_t fmi, status, oc, vbat_q; uint32_t first_s, last_s;
                 uint16_t rpm, rail_bar; uint8_t load_pct, fuel_q, clt_p40, oil_q; } nvm_dtc;      /* 24 B */
typedef struct { uint32_t t_s; uint8_t code, spare; uint16_t arg, rpm, spare2; } nvm_event;     /* 12 B */
typedef struct { uint16_t rpm; uint8_t fuel_q, state; uint16_t rail_bar; } rec_sample;          /* 6 B */
typedef struct { uint32_t t_s; uint8_t reason, n_pre, n_post, spare; rec_sample s[REC_PRE + REC_POST]; } rec_trip;
typedef struct { nvm_hdr h; nvm_counters c; nvm_dtc dtc[NVM_DTCS]; nvm_event ev[NVM_EVENTS];
                 uint8_t ev_head, ev_n, rec_next, spare; rec_trip rec[2]; } nvm_image;
uint32_t nvm_crc32(const void *p, uint32_t len);
void nvm_fresh(nvm_image *m);                       /* zeroed, header set, seq 0 */
int  nvm_valid(const void *p, uint32_t len);        /* magic, version, len == sizeof, crc */
int  nvm_pick(const void *a, const void *b, uint32_t len);   /* 0 = a, 1 = b, -1 = neither; higher seq wins */
void nvm_seal(nvm_image *m);                        /* seq++, crc over everything after the header */
```

Changes to `ecu.h`:
- New inputs `float v_bat; uint8_t reset_cause;`
- New outputs `uint8_t nvm_save, nvm_slot;`
- New entry points:

```c
void ecu_nvm_load(ecu_io *io, const void *slot_a, const void *slot_b, uint32_t len);
const void *ecu_nvm_image(uint32_t *len);
```

`ecu.py` mirrors the new fields and adds `nvm_load(a: bytes, b: bytes)` and `nvm_image() -> bytes`.

- [ ] **Step 1:** Write the tests:
  - `test_nvm_size`: `sizeof(nvm_image) <= 4096`.
  - `test_crc32`: `nvm_crc32("123456789", 9) == 0xCBF43926u`.
  - `test_nvm_pick`:
    - two sealed images, seq 1 and 2 → picks the seq-2 slot
    - corrupt one byte of the seq-2 slot → picks seq 1
    - both zero → −1
  - `test_nvm_old_version` (Review Focus 2): version 0 with a correct CRC → `nvm_valid` is 0.
- [ ] **Step 2:** Run `make -C firmware/sim test`. Expected to fail.
- [ ] **Step 3:** Implement `nvm.c`. In `ecu.c`: `static nvm_image img, out;`. `ecu_nvm_load` does `nvm_pick` and copies the result into `img`, or calls `nvm_fresh`. `ecu_nvm_image` returns `&out`. Logging comes in Task 3.
- [ ] **Step 4:** Run `make -C firmware/sim test && make -C firmware/sim && .venv/bin/python firmware/sim/ecu.py`. Expected: 0 failures, and `ecu.py ok`.
- [ ] **Step 5:** Commit with the message "Firmware: persistent image with CRC and A/B slots".

### Task 3: Events, counters, save policy, background + watchdog (M3)

**Files:**
- Create `firmware/core/log.{c,h}`.
- Modify `ecu.c`, `ecu.h` and `ecu.py`.
- Modify `test_core.c`. The `ticks()` and `ecu_spin()` helpers now call `ecu_background` after every tick and clear `io->nvm_save`, acting as a host whose writes always succeed.

**Interfaces — Produces:**

```c
/* log.h */
enum { EV_POWER_ON = 1, EV_IGN_ON, EV_IGN_OFF, EV_CRANK, EV_RUN, EV_SHUTDOWN,
       EV_DTC_SET, EV_DTC_CLEAR, EV_DM3_CLEAR, EV_NVM_RESET };
void log_event(nvm_image *m, uint32_t t_s, uint8_t code, uint16_t arg, uint16_t rpm);
const nvm_event *log_event_at(const nvm_image *m, int back);   /* 0 = newest; NULL past ev_n */
void log_second(nvm_image *m, int running, float load_frac);   /* ecu_s++, engine_s/band_s when running */
/* ecu.h */
void ecu_background(ecu_io *io);
#define ECU_BG_MS 50
#define SAVE_GAP_S 10
#define SAVE_RUN_S 3600
```

Event hooks in `ecu.c`:
- `POWER_ON` (arg = `reset_cause`) at load. A reset cause of 1 does `wdg_resets++`.
- `NVM_RESET` when no slot is valid.
- `IGN_ON` (OFF→WAIT).
- `IGN_OFF` (ignition falling edge, seen in the tick).
- `CRANK`.
- `RUN`, which also does `starts++`.
- `SHUTDOWN` (arg = TRIP_*), which also does `trips_overspeed++` or `trips_sync++`.

`log_second` runs once per 1000 ms of tick, with load = `fuel_mg / FUEL_RATED_MG`.

Save requests: a flag `save_req` is set by:
- a start
- entering SHUTDOWN
- `engine_s % SAVE_RUN_S == 0`

`ecu_background` checks in for the watchdog, and seals into `out` when:
- `save_req` is set, and
- at least `SAVE_GAP_S` have passed since the last save, and
- `!io->nvm_save`.

On a seal it sets `io->nvm_slot = out.h.seq & 1` and `io->nvm_save = 1`.

- [ ] **Step 1:** Write the tests:
  - `test_log_ring`: 70 events → `ev_n == 64`; the newest is the 70th, and the oldest kept is the 7th.
  - `test_ecu_wdg_needs_background`: tick 100 without background → WDI changes at most once, and only within the first 50 ms. Tick 100 with background → 20 changes.
  - `test_ecu_hour`: in RUN, tick 3 600 000 → `engine_s == 3600` and exactly one hourly seal. The start's save comes before that; count the seals after the start.
  - `test_ecu_save_rate`: 5 save-worthy events in 2 s → one seal now, the next ≥ 10 s later.
  - `test_ecu_storage_dead` (Review Focus 1): never clear `nvm_save`. 20 s of RUN plus a trip → no crash, state as normal, `nvm_save` still 1, events still logged in RAM (`ev_n` rising).
  - `test_ecu_power_on_event`: load with `reset_cause = 1` → the newest event is `POWER_ON` with arg 1, and `wdg_resets == 1`.
- [ ] **Step 2:** Run `make -C firmware/sim test`. Expected to fail.
- [ ] **Step 3:** Implement. Update `test_ecu_wdg` so that it calls the background loop.
- [ ] **Step 4:** Run `make -C firmware/sim test`. Expected: 0 failures.
- [ ] **Step 5:** Commit with the message "Firmware: event log, counters, save policy; watchdog needs the main loop".

### Task 4: DTC memory with freeze frames

**Files:** Modify `log.{c,h}` and `ecu.c`. Test: `test_core.c`.

**Interfaces — Produces:**

```c
typedef struct { float rpm, load_frac, fuel_mg, rail_bar, clt_c, oil_kpa, v_bat; uint8_t state; } log_snap;
int  log_dtc_set(nvm_image *m, uint32_t spn, uint8_t fmi, uint32_t t_s, const log_snap *s); /* 1 = first occurrence */
void log_dtc_inactive(nvm_image *m, uint32_t spn, uint8_t fmi);
void log_dtc_all_inactive(nvm_image *m);
int  log_dm3_clear(nvm_image *m);            /* drops previously active entries; returns count */
const nvm_dtc *log_dtc_find(const nvm_image *m, uint32_t spn, uint8_t fmi);
```

Behaviour:
- **New entry:** the freeze frame is captured once; status = used | active; oc = 1.
- **Re-raise:** `oc++` (saturating at 126), `last_s` updated, the freeze frame left unchanged.
- **Table full:** the entry replaced is the previously-active one with the smallest `last_s`.

`ecu.c` routes every `faults_set` and `faults_clear` through `fault_raise` and `fault_drop` helpers, which also call `log_*`, log `DTC_SET`/`DTC_CLEAR`, and set `save_req` on a first occurrence. `reset_all` calls `log_dtc_all_inactive`.

- [ ] **Step 1:** Write the tests:
  - `test_dtc_first_and_count`:
    - set twice → oc 2, and the freeze-frame rpm is from the first set
    - clear → not active, but still found
  - `test_dtc_full`: fill 16 inactive entries with rising `last_s`, then set a 17th → the smallest-`last_s` entry is gone.
  - `test_dm3_clear`: 2 inactive and 1 active → returns 2, and the active one survives.
  - `test_ecu_history_survives_ignition_cycle` (Review Focus 5):
    - runaway trip via the `test_ecu_overspeed_edge` path
    - ignition cycle (`IGN_OFF_MS` low, stopped)
    - then: DTC 190/0 found, not active, oc 1; `trips_overspeed == 1`
- [ ] **Step 2:** Run `make -C firmware/sim test`. Expected to fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `make -C firmware/sim test`. Expected: 0 failures.
- [ ] **Step 5:** Commit with the message "Firmware: DTC memory with freeze frames".

### Task 5: Trip recorder

**Files:** Modify `log.{c,h}` and `ecu.c`. Test: `test_core.c`.

**Interfaces — Produces:**

```c
typedef struct { rec_sample ring[REC_PRE]; uint8_t head, n; uint8_t post_left; int8_t slot; } rec_t;
void rec_reset(rec_t *r);
int  rec_push(rec_t *r, nvm_image *m, rec_sample s);   /* every 20 ms; returns 1 when a recording completes */
void rec_trigger(rec_t *r, nvm_image *m, uint32_t t_s, uint8_t reason);  /* copies the pre ring into rec[rec_next] */
```

`ecu.c` pushes a sample every 20 ms from the tick, in every state except OFF. It triggers on `trip()` for OVERSPEED and SYNC only. When the recording completes, it sets `save_now`, which `ecu_background` honours even inside the 10 s gap.

- [ ] **Step 1:** Write the tests:
  - `test_rec_pre_post`:
    - push 300 samples with rpm = index, trigger at index 300, push 60 more
    - → `n_pre == 100`, `s[0].rpm == 200`, `s[99].rpm == 299`, `n_post == 50`, `s[149].rpm == 349`
    - completion is returned exactly once
  - `test_rec_two_slots`: 3 triggers → slots used 0, 1, 0; `rec_next` alternates.
  - `test_ecu_trip_saves_now`: a save just happened (gap active); overspeed trip → a seal within 1.1 s of the trip, with `rec[*].reason == TRIP_OVERSPEED`.
- [ ] **Step 2:** Run `make -C firmware/sim test`. Expected to fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `make -C firmware/sim test`. Expected: 0 failures.
- [ ] **Step 5:** Commit with the message "Firmware: trip recorder, 2 s before and 1 s after each trip".

### Task 6: J1939 readout — DM2, DM3, DM4, HOURS

**Files:** Modify `j1939.{c,h}` and `ecu.{c,h}`. Modify `ecu.py` (`can_rx(id, data)`). Test: `test_core.c`.

**Interfaces — Produces:**

```c
int  j1939_tp(ecu_can *out, int max, uint8_t prio, uint32_t pgn, const uint8_t *buf, int n); /* 1 frame or BAM */
int  j1939_dm2(ecu_can *out, int max, const nvm_image *m);
int  j1939_dm4(ecu_can *out, int max, const nvm_image *m);
void j1939_hours(ecu_can *f, uint32_t engine_s);
uint32_t j1939_request_pgn(const ecu_can *f, uint8_t sa);   /* requested PGN, or 0 if not a request for sa/255 */
void ecu_can_rx(ecu_io *io, const ecu_can *f);
```

- `j1939_dm1` is re-expressed on top of `j1939_tp`, with no change in output. The existing DM1 tests are the guard.
- BAM buffer: 48 frames.
- DM4 per DTC: `len=17, DTC(4), 0xFF, 0xFF, rpm/0.125 (2, LE), load % (1), coolant+40 (1), 0xFF 0xFF, rail bar (2, LE), oil/4, vbat/0.2, state`.
- `ecu_can_rx` acts on requests for DM2 (65227), DM3 (65228), DM4 (65229) and HOURS (65253). A BAM response waits if one is in flight.
- HOURS is also broadcast every 10 000 ms.

- [ ] **Step 1:** Write the tests:
  - `test_request_parse`:
    - id `0x18EAEA00 | src`, data `CB FE 00` → 65227
    - id `0x18EAFF00`, global → 65227
    - id `0x18EA0000` (DA 0, Review Focus 4) → 0
  - `test_hours`: `engine_s = 3600` → raw 20 in `data[0..3]`, `data[4..7] == 0xFF`.
  - `test_dm2_empty` (Review Focus 3): no stored DTCs → 1 frame, PGN 0xFECB, DTC bytes all zero.
  - `test_dm4_layout`: one stored 190/0 with freeze-frame rpm 1652 → `data[0] == 17`, rpm bytes = 13216 LE, and length 18 → BAM.
  - `test_ecu_dm3_request`: 1 inactive and 1 active stored; request DM3 → only the active one is left; the newest event is `DM3_CLEAR`.
  - `test_ecu_dm2_waits_for_bam`: request DM2 while a DM1 BAM is in flight → its TP.CM appears only after the last DM1 TP.DT.
- [ ] **Step 2:** Run `make -C firmware/sim test`. Expected to fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `make -C firmware/sim test`. Expected: 0 failures.
- [ ] **Step 5:** Commit with the message "Firmware: J1939 DM2, DM3, DM4 and engine hours".

### Task 7: SIL — power cycles and scenarios 12–15

**Files:** Modify `firmware/sim/engine.py` (`drop_edge_once: bool`; when set, the next crank edge is suppressed and the flag clears) and `firmware/sim/run_sil.py`.

**Interfaces — Consumes:** `Ecu.nvm_load / nvm_image / background / can_rx` (Tasks 2, 3 and 6).

`Sim` changes:
- `self.slots = [b"", b""]`.
- After each tick it calls `background()`. If `io.nvm_save` is set, it stores `nvm_image()` in `slots[io.nvm_slot]` and clears the flag.
- `power_cycle(torn=False)` re-inits the ECU and calls `nvm_load(*slots)`. The engine is kept. With `torn`, the last write leaves only the first half of the new image, the rest of that slot zeroed.
- `request(pgn)` sends a global request through `can_rx`.
- `image()` decodes counters, DTCs, events and recorder from slot bytes with `struct`, using the Task 2 layout.

| fn | Setup | Checks |
|---|---|---|
| `history_after_power_cycle` (12) | runaway as in scenario 5, run 2 s, `power_cycle()` | DTC 190/0 previously active, oc 1, freeze-frame rpm ≥ 1650; an event `SHUTDOWN` arg OVERSPEED; the recorder's last pre sample rpm ≥ 1650; starts ≥ 1 |
| `torn_save` (13) | run, force a save (start), then `power_cycle(torn=True)` while the next save is being written | reload gets the previous seq; counters equal that image's |
| `dm2_dm3_over_can` (14) | sensor_open, then clear it, then request DM2 | DM2 carries 110/3; after DM3, DM2 is empty; active faults unchanged |
| `lost_tooth` (15) | RUN at 1500 rpm, `drop_edge_once` | SHUTDOWN; stored DTC 636 present, 190 absent |

- [ ] **Step 1:** Write the 4 scenarios and the `Sim` changes.
- [ ] **Step 2:** Run `.venv/bin/python firmware/sim/run_sil.py`. Expected: `15/15 scenarios pass`. Investigate any failure as a defect; don't relax a check.
- [ ] **Step 3:** Commit with the message "SIL: logs survive power cycles and torn saves; scenarios 12-15".

### Task 8: Bible

**Files:**
- Modify `docs/decisions-log.md`: new §12, "Logs a production ECU keeps (11 October)".
- Modify `docs/status.md`, `docs/HANDOFF.md` and `README.md` (scenario count 15).
- Run `docs/build_pdf.py`.

- [ ] **Step 1:** Write §12 in plain language. Cover:
  - the four record types and why each exists
  - the A/B slots
  - the wear budget
  - background-gated watchdog
  - the four field fixes
  - the decisions table above
  - the open items for the dev-kit spec (storage choice for 110 k writes per slot, UDS readout, DM3 ACK)
- [ ] **Step 2:** Run `CHROME=... .venv/bin/python docs/build_pdf.py`. Expected: ECU-Bible.pdf rebuilt with §12.
- [ ] **Step 3:** Commit with the message "Bible: record the production logging decisions".
