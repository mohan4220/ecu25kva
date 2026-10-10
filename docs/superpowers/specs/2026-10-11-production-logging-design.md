# Production logging and field fixes: design

**Date:** 2026-10-11
**Status:** design agreed in conversation; written for review.
**Builds on:** `2026-10-10-firmware-sil-design.md` (the portable core and SIL).
**Context:** this ECU goes into a production genset that runs for months
without a stop. Nothing the core knows survives power-off today.

---

## 1. Purpose

1. **Logs a production ECU keeps:**
   - fault memory with snapshots
   - an event log
   - lifetime counters
   - a trip recorder

   All four survive power-off and can be read over J1939.
2. **Four defects that are minor on a bench but real in the field**
   (from the final review of the SIL branch):
   - the 49.7-day counter wrap
   - the unconditional watchdog kick
   - the wrong fault code on a lost tooth
   - a split DM1 message

All of it stays in the portable core. Only two small host actions touch
storage, and the simulator proves the logs before hardware exists.

**Success:** new unit tests and SIL scenarios (§8) pass alongside the
existing 46 tests and 11 scenarios.

## 2. Storage model

The core keeps one **persistent image**, a packed struct, at most
**4096 bytes**. That size fits the S32K148's FlexRAM emulated EEPROM.
The image carries a header: magic, layout version, sequence number and
CRC-32.

The host keeps **two slots**, A and B, and writes alternately to them, so
a write torn by power loss always leaves one good copy:

```c
void ecu_nvm_load(ecu_io *io, const void *slot_a, const void *slot_b, uint32_t len);
const void *ecu_nvm_image(uint32_t *len);   /* what to write when io->nvm_save is set */
```

- **Loading.** `ecu_nvm_load` runs after `ecu_init`. It takes the valid
  slot with the higher sequence number. If neither slot is valid (blank,
  bad CRC or wrong version), it starts a fresh image and logs
  `NVM_RESET`.
- **Saving.** When the core wants the image saved, it sets
  `io->nvm_save = 1` and `io->nvm_slot` (0 or 1). The host writes
  `ecu_nvm_image()` to that slot and clears `nvm_save`. On the PC, a
  slot is a file.
- **No flash writes in interrupts.** Saves are requested only from the
  new background entry point (§6), never from the edge or tick
  interrupts.

**Save policy (wear):**
- Save on any of these:
  - a DTC's first occurrence
  - every trip, with the trip recorder
  - entering SHUTDOWN
  - each start
  - every **60 min** of running (the counters)
- At most one save per **10 s**, except a trip, which saves at once.
- Expected rate: about 30 per day, roughly 220 k over 20 years, or 110 k
  per slot. The dev-kit spec must choose storage that endures this,
  either EEE or D-flash with wear levelling.

## 3. What the image holds

| Block | Content | Bytes |
|---|---|---|
| Header | magic `0xEC25`, version, seq, CRC-32 | 16 |
| Counters | ECU powered seconds; engine running seconds; starts; trips (overspeed, sync loss, other); watchdog resets; seconds in each load band (<25, 25–50, 50–75, 75–100, >100 % of rated fuel) | 48 |
| DTC memory | 16 entries of 24 B (see below) | 384 |
| Event log | ring of 64 entries of 12 B | 768 |
| Trip recorder | last 2 trips, 150 samples of 6 B each, plus 8 B header | 1816 |
| **Total** | | **3032** (fits 4096) |

**Time.** The board has no real-time clock, so every timestamp is **ECU
powered seconds**, and engine hours are counted separately. The DSE4522
has a clock and keeps its own wall-time log.

**DTC entry** (J1939-73 style, one per SPN+FMI):
- status: active or previously active
- occurrence count, saturating at 126
- first-seen and last-seen times
- a **freeze frame captured at first occurrence**:
  - rpm
  - load % (fuel ÷ rated)
  - fuel
  - rail bar
  - coolant °C
  - oil kPa
  - battery volts
  - state

When the table is full, the oldest *previously active* entry is
replaced. At most 8 can be active, so one always exists.

**Event entry:** time, code, a 16-bit argument, and rpm. The codes:
- `POWER_ON` (argument = reset cause)
- `IGN_ON`, `IGN_OFF`
- `CRANK`, `RUN`
- `SHUTDOWN` (argument = trip reason)
- `DTC_SET`, `DTC_CLEAR` (argument = DTC index)
- `DM3_CLEAR`
- `NVM_RESET`

**Trip recorder.** A RAM ring is always recording, one sample every
**20 ms**: rpm, fuel, rail pressure and state. On a trip, the core keeps
100 samples from before the trip (2 s) and 50 after (1 s), then copies
them into the older of the two recorder slots and saves.

## 4. New inputs and outputs in `ecu_io`

| Field | Direction | Purpose |
|---|---|---|
| `v_bat` | in | battery volts, for the freeze frame (the board already has the divider) |
| `reset_cause` | in, set before `ecu_init` | 0 power-on, 1 watchdog, 2 other; logged, and watchdog resets are counted |
| `nvm_save`, `nvm_slot` | out | save request (§2) |

CAN receive is a new entry point, for J1939 requests:
`void ecu_can_rx(ecu_io *io, const ecu_can *f);`

## 5. J1939 readout

| PGN | Name | When | Content |
|---|---|---|---|
| 65227 (0xFECB) | DM2 | on request (PGN 59904) | previously active DTCs, same layout as DM1; BAM if more than one |
| 65228 (0xFECC) | DM3 | on request | clears previously active DTCs and their freeze frames; logs `DM3_CLEAR` |
| 65229 (0xFECD) | DM4 | on request | freeze frames: per DTC the standard fields (speed, % load, coolant), then the manufacturer bytes (rail, oil, battery, state) |
| 65253 (0xFEE5) | HOURS | on request, and broadcast every 10 s | SPN 247 engine total hours, 0.05 h/bit, bytes 1–4 |

Only requests addressed to 234 or to global (255) are answered. The 10 s
HOURS broadcast is a hedge until U4 confirms whether the DSE requests it.

The event log and trip recorder have no J1939 message. A service tool
reads them over UDS on CAN, and that tool is in the dev-kit spec. Until
then, the SIL reads them from the image.

## 6. Background entry point and watchdog (fixes M3)

```c
void ecu_background(ecu_io *io);   /* main loop, as often as it likes */
```

It does the slow work: the save policy, and copying the trip recorder
into the image. It also **checks in**.

The 1 ms tick toggles WDI only while the background loop has checked in
within the last **50 ms**. If the main loop hangs while interrupts still
run, the kicks stop and the TPS3850 resets the MCU. The next boot logs
`POWER_ON` with reset cause 1 and increments the watchdog-reset counter.

## 7. The other three field fixes

- **M2, counter wrap.** The millisecond counter wraps at **3 600 000
  (1 h)**. Every period divides that, and the hourly save uses it. The
  BAM packet spacing becomes a countdown, so no comparison crosses the
  wrap.
- **M1, lost-tooth diagnosis.** When a crank fault is raised on the same
  edge, it takes priority over overspeed. A lost tooth then logs SPN 636,
  not 190. A real overspeed with a healthy wheel still logs 190. Either
  way the engine stops.
- **M5, split DM1.** If the TP.CM frame can't be queued, its TP.DT
  packets are dropped too, so a receiver never sees a half message.

## 8. Tests

**Unit tests (C):**
- Image round trip.
- Corrupt slot B (the newest) → slot A is loaded.
- Both slots blank → fresh image and `NVM_RESET`.
- DTC occurrence counting and the freeze frame captured once.
- Table-full replacement.
- DM2, DM3 and DM4 frames.
- HOURS encoding.
- The ms counter across its wrap.
- Watchdog:
  - no kicks once background stops for 50 ms
  - kicks resume once it returns
- Save rate limit.
- An hour of running → one hourly save and 3600 engine seconds.

**SIL scenarios (new, numbered on from the 11):**

| # | Scenario | Pass when |
|---|---|---|
| 12 | Runaway, then power cycle | after reload: DTC 190/0 previously active, oc 1, freeze-frame rpm ≥ 1650; event log has `SHUTDOWN` (overspeed); trip recorder's last pre-trip sample ≥ 1650 rpm |
| 13 | Torn save | power cut mid-write of the newest slot → reload gets the previous image, nothing lost but that save |
| 14 | DM2 / DM3 over CAN | the request gets the stored DTC back; after DM3, DM2 is empty and active faults are untouched |
| 15 | Lost tooth at 1500 rpm | SHUTDOWN with SPN 636 stored, not 190 |

## 9. Out of scope

- The UDS service tool and the event-log and trip-recorder readout
  through it (dev-kit spec).
- Calibration storage and XCP (dev-kit spec; it gets its own image).
- The S32K148 flash driver and EEE setup (dev-kit spec).
- Wall-clock timestamps (no RTC).
