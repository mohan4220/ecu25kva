# Service Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A bootloader, an end-of-line record and an underspeed warning in the portable firmware, reached over USB or CAN channel 2 with one UDS subset, all proven on the PC.

**Architecture:** Portable C beside the existing core: `isotp.c` and `link.c` frame messages, `service.c` runs the shared UDS session and security logic, `eol.c` keeps the unit record, `firmware/boot/boot.c` is the bootloader. Hardware stays behind host calls, as the core's port contract already does. A Python tool drives it all through the simulator.

**Tech Stack:** C99 (`-Wall -Wextra -Werror`), the existing `firmware/sim` Makefile and ctypes simulator, Python 3 (`.venv`), `pyserial` and `python-can`/`can-isotp` only for real links.

**Spec:** `docs/superpowers/specs/2026-10-17-service-link-design.md`

## Global Constraints

- The core touches no hardware; every new host action is a flag or buffer in `ecu_io`, or a call in the spec's §8 table.
- CAN channel 2 IDs: request `0x7E0`, response `0x7E8`, 11-bit. Messages ≤ 4095 bytes.
- USB frame: `0x55`, length 2 bytes LE, payload, CRC-16/CCITT (poly `0x1021`, init `0xFFFF`) of the payload.
- Engine stopped: state OFF, WAIT or SHUTDOWN and no crank tooth for 1000 ms.
- Session timeout 5000 ms; 3 wrong keys lock security for 10 000 ms.
- Key = CRC-32 (the existing `nvm_crc32`) over seed (4 bytes LE) then `SEC_SECRET` (16 bytes).
- EOL trims: gain 0.9–1.1, offset −0.1…+0.1 V; defaults 1 and 0.
- Underspeed: below 1350 rpm for 3000 ms raises SPN 190 FMI 18; above 1400 rpm for 1000 ms clears; never a shutdown.
- Bootloader area 32 KiB; it never erases or writes below the application base.
- Existing 80 unit tests and 15 SIL scenarios keep passing.

## Review Focus

1. **A service request arriving while the engine turns** (a laptop left connected): extended and programming sessions refused; an open session closes when the first tooth arrives. Test: `test_svc_engine_turning` (Task 3).
2. **A power cut at any point of a flash**: the next reset stays in the bootloader and a rerun succeeds. Test: `test_boot_power_cut_every_write` (Task 4), and the tool's end-to-end cut (Task 5).
3. **An ISO-TP frame lost or out of order** must not deliver a corrupted message. Test: `test_isotp_lost_cf` (Task 2).
4. **A normal load step mistaken for underspeed.** Test: SIL scenario 2 asserts no SPN 190 FMI 18 (Task 1).
5. **A unit that skipped the EOL line runs silently on default trims.** Test: `test_eol_missing_raises_628` (Task 3).

---

## File Structure

```
firmware/core/safety.h, ecu.c        underspeed (Task 1)
firmware/core/isotp.{c,h}            ISO-TP framing (Task 2)
firmware/core/link.{c,h}             USB framing, CRC-16 (Task 2)
firmware/core/service.{c,h}          UDS session, security, dispatch (Task 3)
firmware/core/eol.{c,h}              the record, trims (Task 3)
firmware/core/sensors.c, ecu.{c,h}   trims applied; service entry points (Task 3)
firmware/boot/boot.{c,h}             the bootloader core (Task 4)
firmware/sim/Makefile                builds libboot, test_boot (Task 4)
firmware/sim/test_core.c, test_boot.c
firmware/sim/run_sil.py              scenario 16 (Task 1)
firmware/tools/ecu_service.py        the laptop tool (Task 5)
firmware/sim/test_service.py         tool end to end (Task 5)
docs/firmware.md, decisions-log.md §16, status.md, HANDOFF.md, README.md (Task 6)
```

---

### Task 1: Underspeed warning

**Files:** Modify `firmware/core/safety.h`, `firmware/core/ecu.c`, `firmware/sim/test_core.c`, `firmware/sim/run_sil.py`.

**Interfaces:**
- Produces: `#define UNDERSPEED_RPM 1350.0f`, `UNDERSPEED_CLEAR_RPM 1400.0f`, `UNDERSPEED_MS 3000`, `UNDERSPEED_CLEAR_MS 1000`, `#define FMI_LOW_MODERATE 18u` in `safety.h`.

- [ ] **Step 1: Write the failing unit test** `test_underspeed` in `test_core.c`: run the core to RUN with the setpoint ramp finished, hold 1340 rpm (drive crank edges at that period) — at 2900 ms `fault_active(190, 18)` is false, at 3100 ms true, state still `ECU_RUN`; then 1410 rpm — after 1100 ms the fault is gone. Use the existing test helpers for crank edges and ticks.
- [ ] **Step 2: Run** `make -C firmware/sim test`. Expected: FAIL in `test_underspeed`.
- [ ] **Step 3: Implement** in `ecu.c`'s 1 ms tick, after the safety check: armed when `io->state == ECU_RUN` and `gov.set >= gov_setpoint(gov.fuel, io->droop_sw) - 1.0f`; two ms counters (below, above); `fault_raise(io, SPN_SPEED, FMI_LOW_MODERATE)` / `fault_drop(...)`. Disarming (leaving RUN) resets both counters and drops the fault.
- [ ] **Step 4: Run** `make -C firmware/sim test`. Expected: all pass.
- [ ] **Step 5: SIL.** Add `overload()` to `run_sil.py`: start, then a load beyond the engine (the fuel limit, 45 mg, cannot hold 1350 rpm); assert SPN 190 FMI 18 in DM1 within 5 s of the sag, state stays RUN. In `load_step()` add: no SPN 190 FMI 18 at any time. Run `.venv/bin/python firmware/sim/run_sil.py`. Expected: 16 scenarios pass.
- [ ] **Step 6: Commit** "Firmware: underspeed warning, SPN 190 FMI 18, no shutdown".

### Task 2: ISO-TP and USB framing

**Files:** Create `firmware/core/isotp.{c,h}`, `firmware/core/link.{c,h}`; modify `firmware/sim/test_core.c`.

**Interfaces:**
- Produces (`isotp.h`): `typedef struct isotp isotp_t;` (fields public, in the header); `void isotp_init(isotp_t *t, uint32_t tx_id);` `int isotp_send(isotp_t *t, const uint8_t *msg, uint16_t len);` (0 ok, -1 busy or too long) `int isotp_rx(isotp_t *t, const ecu_can *f, uint8_t *msg, uint16_t *len);` (1 when a whole message is in `msg`) `int isotp_next(isotp_t *t, ecu_can *out);` (1 when a frame must be sent: a flow control or the next consecutive frame) `#define ISOTP_MAX 4095`.
- Produces (`link.h`): `uint16_t crc16_ccitt(const uint8_t *p, uint16_t n);` `uint16_t link_frame(const uint8_t *msg, uint16_t n, uint8_t *out);` (returns `n + 5`) `typedef struct link_rx link_rx_t;` `int link_feed(link_rx_t *r, uint8_t byte, uint8_t *msg, uint16_t *len);` (1 when a whole message is in `msg`).

- [ ] **Step 1: Failing tests** in `test_core.c`: `test_isotp_roundtrip` (lengths 1, 7, 8, 4095: send through one `isotp_t`, feed every frame from `isotp_next` into a second, including its flow control back; the received bytes equal the sent); `test_isotp_lost_cf` (drop the third consecutive frame: no message is delivered, and the next full message still arrives); `test_link_roundtrip` and `test_link_bad_crc` (a corrupted CRC drops that message; the following message arrives).
- [ ] **Step 2: Run** `make -C firmware/sim test`. Expected: FAIL (undefined `isotp_init`).
- [ ] **Step 3: Implement** both. ISO-TP: single frame ≤ 7 bytes; first frame with 12-bit length; flow control `0x30, 0, 0`; consecutive frames with a 4-bit sequence; a wrong sequence aborts reception. Pad frames to 8 bytes with `0xAA`. Link: resynchronise on `0x55`; reject length > 4095.
- [ ] **Step 4: Run.** Expected: all pass.
- [ ] **Step 5: Commit** "Firmware: ISO-TP and USB framing for the service link".

### Task 3: Service core, EOL record, trims

**Files:** Create `firmware/core/service.{c,h}`, `firmware/core/eol.{c,h}`; modify `firmware/core/ecu.{c,h}`, `firmware/core/sensors.{c,h}`, `firmware/sim/ecu.py` (new `ecu_io` fields), `firmware/sim/test_core.c`.

**Interfaces:**
- Consumes: Task 2's `isotp_*`, `link_*`; `nvm_crc32`.
- Produces (`eol.h`): the `eol_record` struct exactly as spec §6; `void eol_default(eol_record *r);` `int eol_valid(const eol_record *r);` `void eol_seal(eol_record *r);` `int eol_pick(const eol_record *a, const eol_record *b);` (newest good, -1 none).
- Produces (`service.h`): `#define SEC_SECRET {16 bytes}`; `typedef struct svc svc_t;` `uint32_t svc_key(uint32_t seed);` `uint16_t svc_handle(svc_t *s, const uint8_t *req, uint16_t n, uint8_t *resp, uint32_t ms, uint32_t us, int engine_stopped, int (*extra)(svc_t *, const uint8_t *, uint16_t, uint8_t *));` — handles `0x10 0x27 0x3E 0x11`, session timeout and the security lock-out; passes everything else to `extra`, which the application (EOL IDs, routines) and the bootloader (programming) each supply. `int svc_unlocked(const svc_t *s);` `uint8_t svc_session(const svc_t *s);`
- Produces (`ecu.h` additions): inputs `uint8_t usb_in[64]; uint8_t usb_in_n;` outputs `uint8_t usb_out[512]; uint16_t usb_out_n;` `ecu_can can2[ECU_CANQ]; uint8_t can2_n;` `uint8_t eol_save, boot_req;` entry points `void ecu_can2_rx(ecu_io *io, const ecu_can *f);` `void ecu_eol_load(ecu_io *io, const void *a, const void *b);` `const void *ecu_eol_image(uint32_t *len);` USB bytes are consumed in `ecu_background`. `boot_req` set means: host sets the stay flag and resets.

- [ ] **Step 1: Failing tests:** `test_svc_seed_key` (seed never 0; right key unlocks; three wrong keys → `0x7F 27 36` for 10 s, then a new seed works); `test_svc_engine_turning` (at 300 rpm, `10 03` → `7F 10 22`; open an extended session stopped, start cranking → the session is back to default); `test_svc_timeout` (no message for 5001 ms → default session, locked); `test_eol_write_lock` (unlock, write serial and trims, read back; `31 01 F000` locks; a write then → `7F 2E 22`; `31 01 F001` unlocks; rewrite works; `eol_save` is set after each change); `test_eol_trim_range` (gain 1.2 → `7F 2E 31`); `test_eol_missing_raises_628` (load two blank copies → SPN 628 FMI 13 active, trims 1/0); `test_trim_applied` (coolant gain 1.05 moves `clt_c` as `sens_convert(v·1.05)` predicts); `test_boot_request` (stopped, unlocked, `10 02` → positive response, then `boot_req == 1`).
- [ ] **Step 2: Run** `make -C firmware/sim test`. Expected: FAIL (undefined `svc_handle`).
- [ ] **Step 3: Implement.** The application's `extra` serves `0x22` (spec §6 IDs), `0x2E` (serial, hardware revision, build date, trims, station, passed), `0x31` `F000`/`F001`. Each EOL change seals the record and sets `eol_save`. `sensors.c` gains `void sens_trim(const float gain[6], const float offset[6]);` applied before conversion. CAN channel 2 goes through an `isotp_t` with tx ID `0x7E8`, accepting only `0x7E0`; frames out go to `can2[]`.
- [ ] **Step 4: Run** `make -C firmware/sim test` and `.venv/bin/python firmware/sim/run_sil.py`. Expected: all pass (the scenarios load no EOL record: they must see SPN 628 only where they check DM1 exactly — load a valid record in the scenario harness so existing DM1 assertions are unchanged).
- [ ] **Step 5: Commit** "Firmware: service core, seed-key, end-of-line record, analog trims".

### Task 4: Bootloader core

**Files:** Create `firmware/boot/boot.{c,h}`, `firmware/sim/test_boot.c`; modify `firmware/sim/Makefile` (targets `build/libboot.$(EXT)`, `build/test_boot`; `test` runs both).

**Interfaces:**
- Consumes: Task 2 framing, Task 3 `svc_handle`, `svc_unlocked`, `eol_record`.
- Produces (`boot.h`): `#define BOOT_SIZE 0x8000u` `typedef struct { uint32_t magic, hver, len, crc, sw_ver; uint16_t hw_min, hw_max; } img_hdr;` (`magic` `0x1A6EC25u`) `typedef struct { int (*erase)(uint32_t a, uint32_t n); int (*write)(uint32_t a, const uint8_t *p, uint32_t n); int (*read)(uint32_t a, uint8_t *p, uint32_t n); uint32_t app_base, app_size; } boot_flash;` `int boot_decide(const boot_flash *f, int stay, uint16_t hw_rev);` (1 jump, 0 stay) `uint16_t boot_handle(boot_t *b, const uint8_t *req, uint16_t n, uint8_t *resp, uint32_t ms, uint32_t us);`

- [ ] **Step 1: Failing tests** in `test_boot.c` with a simulated flash (a byte array; `write` fails after a set count to model a power cut): `test_boot_decide` (blank → stay; good image → jump; stay flag → stay; `hw_rev` outside `hw_min..hw_max` → stay); `test_boot_bounds` (erase or write below `app_base` → `7F 31 31`/`7F 36 31`, flash unchanged); `test_boot_flash_ok` (programming session, unlock, erase, download 40 000 bytes in 1024-byte blocks, exit, check → positive; `boot_decide` → jump); `test_boot_header_last` (the header bytes are the last write); `test_boot_power_cut_every_write` (for every write index k, cut power at k, then `boot_decide` → stay; rerun the whole flash → jump); `test_boot_bad_sequence` (a skipped block counter → `7F 36 24`).
- [ ] **Step 2: Run** `make -C firmware/sim test`. Expected: FAIL (no `boot.c`).
- [ ] **Step 3: Implement.** The image header goes at `app_base`; the image data from `app_base + 64`. `0x34` records address and length; `0x36` appends in order; `0x37` then `0x31 FF01` computes the CRC over what was written and only then writes the header. The bootloader's `extra` for `svc_handle` serves `0x31 FF00/FF01`, `0x34`, `0x36`, `0x37`, and `0x22 F180/F195`.
- [ ] **Step 4: Run.** Expected: all pass.
- [ ] **Step 5: Commit** "Firmware: bootloader core, image header written last".

### Task 5: The laptop tool, end to end

**Files:** Create `firmware/tools/ecu_service.py`, `firmware/sim/test_service.py`; modify `firmware/sim/ecu.py` (bindings for the new entry points and `libboot`).

**Interfaces:**
- Consumes: the C entry points of Tasks 3–4 through ctypes; the framing rules of the Global Constraints.
- Produces: CLI `ecu_service.py --link {usb:PORT, can:INTERFACE:CHANNEL, sim} --secret FILE COMMAND` with commands `info`, `eol-read`, `eol-write --serial S --hw-rev R --date YYYYMMDD [--trims FILE.json] [--station N] [--passed]`, `eol-lock`, `eol-unlock`, `flash IMAGE.bin --sw-ver V --hw-min R --hw-max R`. `pyserial` and `python-can`/`can-isotp` are imported only by their links.

- [ ] **Step 1: Failing test** `test_service.py`: through the `sim` link: `eol-write` then `eol-read` shows the values; `eol-lock`, then `eol-write` exits non-zero with "locked"; `flash` a 64 KiB random image → the simulated boot decides "jump" and the flash holds the image; a second `flash` with a power cut at 50 % of the transfer, then a rerun → "jump" with the new image; with the engine turning, `eol-write` exits non-zero with "engine must be stopped".
- [ ] **Step 2: Run** `.venv/bin/python firmware/sim/test_service.py`. Expected: FAIL (no tool).
- [ ] **Step 3: Implement** the tool: a UDS client (request, wait for `service + 0x40` or `0x7F`, map reason codes to plain messages), the seed-key, the flash sequence of spec §7, and the three links.
- [ ] **Step 4: Run.** Expected: pass; then `make -C firmware/sim test` and `run_sil.py` still pass.
- [ ] **Step 5: Commit** "Firmware: laptop service tool, USB, CAN and simulated links".

### Task 6: Documents and the bible

**Files:** Modify `docs/firmware.md` (a new section "The service link"; §6 underspeed; §13 test counts; §14 the host calls of spec §8), `docs/decisions-log.md` (new §16: the owner's four answers, what was found in the comparable ECU, the risks of spec §12), `docs/status.md` and `docs/HANDOFF.md` (where it stands), `README.md` (the tool's commands), then rebuild `docs/pdf` with `CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" .venv/bin/python docs/build_pdf.py` from `docs/`.

- [ ] **Step 1:** Write the documents.
- [ ] **Step 2: Run** `make -C firmware/sim test`, `run_sil.py`, `test_service.py`, `sim/run_sim.py`. Expected: all pass.
- [ ] **Step 3:** Rebuild the PDF. Expected: "ECU-Bible.pdf  N pages".
- [ ] **Step 4: Commit** "Firmware: service link documented, decisions §16".
