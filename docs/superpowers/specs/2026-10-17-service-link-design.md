# Service link: bootloader, end-of-line record, underspeed warning

**Date:** 2026-10-17
**Status:** owner's answers taken in conversation; written for review.
**Builds on:** `2026-10-10-firmware-sil-design.md` (the portable core, SIL)
and `2026-10-11-production-logging-design.md` (the persistent image).
**Prompted by:** a comparable production ECU's firmware (a TargetLink
model) has a bootloader, an end-of-line (EOL) write and an underspeed
fix. Ours has none of the three.

---

## 1. Purpose

1. **A bootloader**, so firmware can be updated in the field through
   the ECU's connector, without opening the box or a debug probe.
2. **An end-of-line record**: what the factory writes into each unit
   once (serial number, hardware revision, build date, analog trims, a
   "passed EOL" stamp), locked once written.
3. **An underspeed warning**: the engine running well below its speed
   setpoint (overload, a fuel fault) is reported, not ignored.

All of it is portable C in `firmware/`, tested on the PC before any
hardware exists, as the core already is.

**Success:** the new unit tests and SIL scenarios (§9) pass alongside
the existing 80 unit tests and 15 scenarios. A laptop tool, talking to
the simulated ECU, writes and locks an EOL record, enters programming,
flashes an image, survives a power cut mid-flash, and boots the new
image.

## 2. The owner's answers (17 October)

| Question | Answer |
|---|---|
| Underspeed action | **Warn; the DSE decides.** The DSE has its own under-frequency shutdown; the ECU does not stop the engine for underspeed |
| Link | **Both.** USB on the prototype, for quick iterations; CAN channel 2 in production |
| EOL scope | **The unit record**, locked once written. A factory output-test mode is later work |
| Protection | **Seed-key**, and the engine must be stopped. Not proof against a determined attacker |

## 3. Architecture

```
laptop: firmware/tools/ecu_service.py ── USB (framed serial) ──┐
                                      └── CAN ch 2 (ISO-TP) ───┤
                                                               ▼
                      one protocol: a subset of UDS (ISO 14229)
          ┌─────────────────────────────┴──────────────────────────────┐
  application (firmware/core)                          bootloader (firmware/boot)
  service.c: session, seed-key, read and write IDs,    boot.c: image check, jump;
  enter programming (reset with a request flag)        erase, download, verify
  eol.c: the record, its CRC, the trims                uses the same service and
  isotp.c: CAN framing  ·  link.c: USB framing         framing code
```

- **One protocol, two links.** The UDS payloads are the same on both;
  only the framing differs (§4). The laptop tool and both firmware
  sides treat the link as a byte pipe of whole messages.
- **UDS, not a home-made protocol**, because the industry's tools speak
  it: a technician's UDS tester can read the IDs; `python-udsoncan`
  could replace our tool.
- **The core stays hardware-free.** Flash, the reset, the "stay in the
  bootloader" flag and the CAN and USB drivers are host calls, listed in
  §8, as the S32K148 port contract already lists the others.

## 4. Links

**CAN channel 2** (ECU pins 86/87), kept off the DSE's J1939 bus:
- 11-bit IDs: request `0x7E0`, response `0x7E8` (the usual diagnostic
  pair), 500 kbit/s.
- ISO-TP (ISO 15765-2) framing: single frames, and first, consecutive
  and flow-control frames for anything over 7 bytes. Block size 0,
  STmin 0. Messages up to 4095 bytes.
- `isotp.c` is written here, about 150 lines; no library.

**USB** (prototype only, the STM32G474's USB device as a virtual serial
port): each message is `0x55, length (2 bytes, little-endian), payload,
CRC-16/CCITT of the payload`. A bad CRC or a length over 4095 drops the
message and resynchronises on the next `0x55`.

## 5. Services

| UDS service | ID | Application | Bootloader |
|---|---|---|---|
| Session control | `0x10` | default `01`, extended `03`; programming `02` resets into the bootloader | default, programming |
| ECU reset | `0x11` | `01` | `01` (runs the image if it is good) |
| Security access | `0x27` | seed `01`, key `02` | same |
| Tester present | `0x3E` | keeps a session alive | same |
| Read data by ID | `0x22` | the IDs in §6 | software version, boot version |
| Write data by ID | `0x2E` | EOL IDs, unlocked only | — |
| Routine control | `0x31` | `0xF000` lock EOL, `0xF001` unlock EOL | `0xFF00` erase the application, `0xFF01` check its CRC |
| Request download | `0x34` | — | address and length of the image |
| Transfer data | `0x36` | — | blocks of up to 1024 bytes, numbered |
| Request transfer exit | `0x37` | — | — |

- A refused request gets `0x7F, service, reason` with the standard
  reason codes: `0x22` conditions not correct (engine turning), `0x33`
  security denied, `0x35` wrong key, `0x36` too many attempts, `0x31`
  out of range, `0x24` wrong sequence, `0x72` programming failure.
- **Engine stopped** means state OFF, WAIT or SHUTDOWN and no crank
  tooth for 1 s. Extended and programming sessions are refused
  otherwise, and an extended session ends if the engine starts turning.
- A non-default session ends after 5 s without a message (`0x3E` keeps
  it alive).

**Seed-key.** The seed is 32 bits from the free-running µs counter mixed
with the ms counter, never 0. The key is the low 32 bits of
`SipHash-2-4(secret, seed as 4 bytes LE)`. (First written as CRC-32 of
seed ‖ secret; the final review showed that is affine, so one sniffed
unlock forges every key. Changed 20 October.) The secret is a build constant, `SEC_SECRET` in
`service.h`, and the tool reads the same 16 bytes from a file the owner
keeps. Three wrong keys lock security access for 10 s. Unlocked lasts
until the session ends.

## 6. The end-of-line record

```c
typedef struct {
    uint16_t magic, version;          /* 0xE01D, 1 */
    char     serial[16];              /* ASCII, zero-padded */
    uint16_t hw_rev;                  /* e.g. 0x0100 = rev 1.0 */
    uint32_t build_date;              /* yyyymmdd */
    float    gain[6], offset[6];      /* clt, oil, rail, boost, egr, 5 V ref */
    uint8_t  station, passed, locked, spare;
    uint32_t crc;                     /* CRC-32 over everything above */
} eol_record;                         /* 88 bytes */
```

- **Stored apart from the logs.** The persistent image (§2 of the logging
  design) is rewritten every few seconds; the record is written once. It
  lives in its own flash sector (S32K148: a D-flash sector; STM32G474:
  the last page), two copies, as the image is.
- **The trims are used**: every analog input is corrected as
  `v · gain + offset` before conversion, in `sensors.c`. A missing or bad
  record means gain 1, offset 0, and a fault code (SPN 628 "program
  memory", FMI 13 "out of calibration"), so a unit that skipped the line
  says so on the DSE's screen.
- **Write rules:** only in the extended session, unlocked, engine
  stopped, record not locked. A trim must be within gain 0.9–1.1 and
  offset ±0.1 V, or `0x31`. Routine `0xF000` sets `locked`; `0xF001`
  (unlocked) clears it again, for a rework, and logs an event.
- **Read IDs** (UDS standard where one exists): `0xF18C` serial,
  `0xF191` hardware revision, `0xF18B` build date, `0xF195` software
  version, `0xF180` boot version, `0x0100` trims, `0x0101` station,
  passed, locked.

## 7. The bootloader

**Flash layout** (each chip's sizes in its host layer):

```
[ bootloader, 32 KiB | image header | application ... ]
```

- **Image header**, at the start of the application area: magic,
  header version, image length, CRC-32 of the image, software version,
  hardware revisions it accepts (min, max).
- **At reset:** if the "stay" flag is set (a RAM word the reset keeps,
  set by the application on a programming request), stay. Otherwise,
  if the header is good, the CRC matches and `hw_rev` (from the EOL
  record) is in range, jump to the application. Otherwise stay.
- **Programming:** programming session, security unlocked, erase
  (`0x31 FF00`), download (`0x34`, `0x36`…, `0x37`), check (`0x31
  FF01`), reset. **The header is written last**, after the whole image
  has been written and its CRC checked against what was sent. A power
  cut anywhere before that leaves no valid header: the next reset stays
  in the bootloader and the update is simply run again.
- **The bootloader never writes its own area.** Every erase and write
  address is checked against the application area; anything else is
  `0x31`.
- **While in the bootloader the engine cannot run:** no injection, the
  metering valve at its safe state, the gates held off by their pull-
  downs. The watchdog is still kicked.
- **Rollback** is not offered: one application slot. A bad image that
  passes the CRC but misbehaves is fixed by flashing the previous one.

## 8. Host calls (added to the port contract, firmware.md §14)

| Call | What the host does |
|---|---|
| `link_send(buf, len)` | send one response on whichever link the request came in on |
| `stay_flag_set()`, `stay_flag_get()`, `stay_flag_clear()` | one RAM word the reset does not clear |
| `system_reset()` | a software reset |
| `flash_erase(addr, len)`, `flash_write(addr, buf, len)`, `flash_read(addr, buf, len)` | the application area only; a write is whole 8-byte words |
| `eol_store(rec)`, `eol_load(a, b)` | the record's two copies, as the image's |
| `jump_to_app(addr)` | set the stack and vector table, branch |

For the PC, each call has a simulated version: flash is a byte array
that can be "powered off" after any write.

## 9. Underspeed

- **Armed** in RUN, once the setpoint ramp from start has finished
  (the governor's setpoint has reached its target).
- **Raised** when speed stays below **1350 rpm (90 % of 1500)** for
  **3 s**: fault SPN 190 (engine speed), FMI 18 (low, moderately
  severe), in DM1 for the DSE, with its snapshot and event as every
  fault has.
- **Cleared** when speed stays above **1400 rpm** for **1 s**.
- **No shutdown:** the ECU keeps governing. The DSE's own under-frequency
  settings decide whether the set stops.
- 1350 rpm is the load-step scenario's own floor (scenario 2), so a
  normal load step never raises it. Both numbers are tuning knobs in
  `safety.h`.

## 10. Testing

| Test | Proves |
|---|---|
| unit: ISO-TP | a 1-byte, a 7-byte, an 8-byte and a 4095-byte message round-trip; a lost consecutive frame is dropped, not misassembled |
| unit: USB framing | round trip; a bad CRC is dropped and the next message still arrives |
| unit: security | wrong key ×3 locks for 10 s; a seed is never 0; locked services are refused before unlock |
| unit: engine stopped | extended and programming sessions refused at 300 rpm; a session ends when the engine turns |
| unit: EOL | write, read back, lock, write refused, unlock, rewrite; a trim out of range refused; a bad CRC falls back to gain 1 and raises SPN 628 |
| unit: trims | a gain of 1.05 moves the coolant reading as the formula says |
| unit: bootloader | erase and write refused outside the application area; header last; a power cut after every write leaves "stay"; a good image with the wrong hardware revision does not run |
| unit: underspeed | 1340 rpm for 2.9 s: nothing; 3.1 s: SPN 190 FMI 18; back over 1400 for 1 s: cleared; no shutdown |
| SIL 16: overload | a load beyond the engine raises the underspeed warning; the engine keeps running |
| SIL 2 (existing): load step | does not raise it |
| tool, end to end | against the simulated ECU: write and lock the record; flash an image; a power cut at 50 % of the transfer, then a rerun, boots the new image |

## 11. Not in this work

- **The chip layers**: the STM32G474 and S32K148 flash, CAN, USB and
  reset drivers. Neither chip has a port yet; §8 is their contract.
  The prototype is first flashed over SWD (J301), as any new board is.
- A factory output-test mode (the owner's later work).
- Signed images (the owner chose seed-key).
- Rollback to a previous image.

## 12. Risks

- **The seed-key secret is in every unit's flash.** Anyone who reads one
  unit's flash can compute keys for all. Acceptable for "stop casual
  writes"; the answer to tampering is signed images (§11).
- **A CAN update at 500 kbit/s** moves about 30 KiB/s at best; a 256 KiB
  image takes about 10 s plus the erase. USB is faster.
- **The DSE's under-frequency settings are unknown** (U4). If the DSE
  ignores DM1 and has no under-frequency trip, nothing stops a set that
  sits overloaded. That belongs in the U4 questions.
