# The STM32G474 chip layer (the prototype board)

The code that puts `firmware/core` (or its Simulink-generated twin) on the
prototype's STM32G474VET6. It is the firmware guide's §14 list, item by
item, for this chip. Written 14 November 2026. **It has been compiled,
linked and checked on the PC, but has not yet run on a board.** Bring-up
is where it meets the hardware (`prototype/docs/bring-up.md`).

## Build

Nothing to install beyond the project's `.venv`. The compiler is the same
zig the PC builds use:

```bash
.venv/bin/python firmware/stm32/build.py --check   # build, and check the pins against ST's data
.venv/bin/python firmware/stm32/test_image.py      # check what it built
```

`./verify.sh` runs both, plus the injector sequencing test.

Outputs in `firmware/stm32/build/` (not committed; one command rebuilds them):

| File | What | Flash with |
|---|---|---|
| `app_standalone.hex` | the application alone at 0x08000000, no bootloader | SWD, **the first thing on a new board** |
| `boot.hex` | the bootloader, 32 KiB at 0x08000000 | SWD, once |
| `app_signed.hex` | the application with the header the bootloader accepts (any hardware revision) | SWD, with `boot.hex` |
| `app.bin` | the application for the service tool's `flash` command | USB or CAN channel 2 |
| `app_model.*` | the same, built with `ECU_MODEL` (the Simulink code) | as above |

```bash
# SWD on J301, ST-LINK V3 (STM32CubeProgrammer, or OpenOCD)
STM32_Programmer_CLI -c port=SWD -w firmware/stm32/build/app_standalone.hex -v -rst
STM32_Programmer_CLI -c port=SWD -w firmware/stm32/build/boot.hex -w firmware/stm32/build/app_signed.hex -v -rst
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg -c "program firmware/stm32/build/app_standalone.hex verify reset exit"

# then, with the bootloader in place, over USB (J302) or CAN channel 2
.venv/bin/python firmware/tools/ecu_service.py --link usb:COM5 --secret key.bin flash \
    firmware/stm32/build/app.bin --sw-ver 0x00010000 --hw-min 0x0000 --hw-max 0xFFFF
```

The option bytes must be as the chip ships: **DBANK = 1** (dual bank, 2 KiB
pages). If it is not, the application runs but stores nothing.

## Where things are

| File | §14 item | What it does |
|---|---|---|
| `board.h` | — | every pin, scale factor, priority and flash address, each with its source |
| `startup.c` | — | vectors, reset, faults: a fault turns every gate off by register, then waits for the watchdog |
| `clock.c` | — | 170 MHz from the 8 MHz crystal (range 1 boost, 4 wait states); HSI48 for USB |
| `gpio.c` | — | every gate written low *before* it becomes an output |
| `timebase.c` | 1, 2 | TIM2 counts µs and captures crank (CH2) and cam (CH3); TIM5, started on the same clock edge, carries the injection compares |
| `inj_logic.c`, `inj_hw.c` | 3 | peak and hold, below |
| `app_main.c` | 4–9, 12 | metering PWM (TIM20 CH4, with CH1 timing the current sample), EGR bridge PWM (TIM1), inputs, outputs, the tick, storage, resets |
| `adc.c` | — | ADC2 and ADC3 scan continuously into DMA, 16× oversampled; VDDA measured against VREFINT |
| `can.c` | 5, 10 | FDCAN1 J1939 at 250 kbit/s; FDCAN2 service link at 1 Mbit/s |
| `flash.c` | 7, 11, 13 | bank-2 writes as a non-blocking job; bank-1 erases from RAM, feeding the watchdog |
| `usb.c`, `tusb_config.h` | 10 | CDC-ACM serial port (TinyUSB 0.20.0) |
| `boot_main.c` | 13 | the bootloader's host |
| `vendor/` | — | ST's device header v1.2.6, Arm CMSIS-Core 5.9.0 (Apache-2.0), TinyUSB 0.20.0 (MIT), each with its licence |

## Interrupts

| Priority | What | Why |
|---|---|---|
| 0 | TIM5 compare, ADC1 watchdogs | injection timing and current: nothing may delay them |
| 2 | SysTick (1 ms), TIM2 capture, FDCAN1/2 | the core's entry points, at one level, so they never nest (§14 item 9) |
| 3 | USB | TinyUSB |
| thread | main loop | `ecu_background` (with level 2 masked, item 9), flash jobs, USB, resets |

## The injector stage

The board has no driver IC: the injector stage is seven discrete gates, two
current shunts, and firmware. `inj_logic.c` decides, `inj_hw.c` applies, and
`test_inj.c` checks the decisions against a 200 µH / 0.5 Ω coil model on the PC.

1. **Start** (TIM5 compare): low side on, the bank's boost high side on. The current climbs at about 0.5 A/µs from 100 V.
2. **Peak:** ADC1 converts the bank's shunt continuously, about every 0.45 µs. Its watchdog fires at **18 A**, and the boost side goes off. The coil freewheels through D_fw.
3. **Hold:** the battery side chops between **9 and 11 A**. Each crossing is a watchdog event.
4. **End** (TIM5 compare): every gate off, and the current recirculates into the boost rail.

Simulated on the coil model, the peak arrives in 37 µs (the circuit simulation says 38) and the hold stays within the band.

**Safety rules, independent of the core:**
- No peak within 60 µs ends the injection, because a dead current sense must not leave 100 V on a coil.
- Over 26 A in any phase ends it.
- No injection runs longer than 5 ms.
- A start found more than 50 µs late is skipped, not shifted.
- Two injections at once are refused.

Cylinders 1 and 3 share bank A (shunt A, ADC1 IN3). Cylinder 2 is bank B (IN4).

## The flash map

| Address | What |
|---|---|
| 0x08000000 | bootloader, 32 KiB; its version at 0x08007FE0 |
| 0x08008000 | image header (64 bytes, written last by the bootloader) |
| 0x08008200 | application vectors (VTOR needs 512-byte alignment) |
| … 0x0807BFFF | application area, 464 KiB. Code is kept in bank 1 (below 0x08040000; the build checks it) |
| 0x0807C000, 0x0807D000 | fault memory, slots 0 and 1, 4 KiB each |
| 0x0807F000, 0x0807F800 | end-of-line record, copies a and b, one page each so that b survives a's erase |

RAM: the first 32 bytes of SRAM1 hold the stay flag, shared by both images.

**The bootloader erases lazily.** The tool's erase request covers 464 KiB,
which takes about 5 s, and the tool waits 2 s for a reply. So the request
erases only the header's page, which invalidates the old image the moment
it answers. Every other page is erased just before the first write into it.

## What is a placeholder, and what to check on the bench

| Item | Now | Settled by |
|---|---|---|
| Peak and hold currents | 18 A, 9–11 A (the simulation's) | U5, the injector part number |
| Metering PWM frequency | 1 kHz (`METER_PWM_HZ`) | the valve's data, or the old ECU on a scope |
| Crank and cam edge | falling (`CRANK_FALLING`, `CAM_FALLING`) | bring-up step 3, on the scope |
| EGR bridge | driven by the position PID (TIM1, sign-magnitude); the target table is zeros, so it coasts | the emissions calibration |
| EGR PWM frequency | 1 kHz (`EGR_PWM_HZ`) | the valve's data |
| USB VID/PID | 0x1209/0x0001, pid.codes' test pair | a product needs its own |
| Tick time | unknown on the chip | read `tick_max_cycles` with the debugger: it must stay well under 170000 |

**Not here:** the S32K148 production chip layer. It is written against the same `ecu_io` interface.
