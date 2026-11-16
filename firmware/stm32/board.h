/* The prototype board (STM32G474VET6) as the chip layer sees it: pins,
 * scaling, interrupt priorities and the flash map. Every number here comes
 * from a named place in the schematic generators or the core, so a change
 * there is a change here.
 *
 * Pins: prototype/stm32_pins.py (checked against ST's pin data); the AF
 * numbers are ST's GPIO modes file, prototype/lib. A test (build.py
 * --check) compares this file with both. */
#ifndef BOARD_H
#define BOARD_H

#include <stdint.h>

/* ---- clocks: 8 MHz crystal (Y301), PLL to 170 MHz ---- */
#define HSE_HZ 8000000u
#define SYSCLK_HZ 170000000u
#define TIMER_US_PSC (SYSCLK_HZ / 1000000u - 1u)   /* TIM2/TIM5 count microseconds */

/* ---- pins: port letter, number ---- */
#define PIN(port, n) ((uint8_t)(((port) - 'A') << 4 | (n)))
#define PIN_PORT(p) ((p) >> 4)
#define PIN_NUM(p) ((p) & 15u)

/* injector stage (injector sheet): low side per cylinder, two high sides
 * per bank. Cylinders 1 and 3 share bank A (pin 03, shunt A); cylinder 2
 * is bank B (pin 05, shunt B). Driven as GPIO from a priority-0 interrupt
 * (inj_hw.c); the pins are also TIM8/TIM20 channels, kept free for a
 * hardware-timed stage later. */
#define P_INJ_LS1 PIN('C', 6)
#define P_INJ_LS2 PIN('C', 7)
#define P_INJ_LS3 PIN('C', 8)
#define P_INJ_HS_A PIN('C', 9)        /* bank A from the 100 V boost rail: peak */
#define P_INJ_HS_B PIN('E', 2)
#define P_INJ_HS_A_BAT PIN('E', 3)    /* bank A from the battery: hold */
#define P_INJ_HS_B_BAT PIN('F', 2)
#define P_MU_PWM PIN('E', 1)          /* TIM20_CH4, AF6 */
#define AF_MU_PWM 6u
#define P_EGR_IN1 PIN('A', 8)
#define P_EGR_IN2 PIN('A', 9)
#define P_EGR_EN PIN('A', 10)
#define P_RLY_MAIN PIN('D', 5)
#define P_RLY_BUZZER PIN('D', 15)
#define P_BOOST_DIS PIN('D', 14)      /* high = stop the boost (BOOST-OVP) */
#define P_WDT_KICK PIN('C', 11)
#define P_LED PIN('B', 7)

/* inputs. The switch inputs are NPN buffers: the pad is the INVERSE of the
 * input (discrete_io sheet). Active-high inputs (ignition, water in fuel):
 * pad low = on. Contact-to-ground inputs (droop, diagnosis, stop): the
 * input is high with the contact open, so pad high = contact closed. */
#define P_IGNITION PIN('C', 10)
#define P_WIF PIN('D', 8)
#define P_DIAG PIN('D', 9)
#define P_STOP PIN('D', 10)
#define P_DROOP PIN('E', 5)
#define P_COOLANT_SW PIN('E', 4)
#define P_AUDIO_ABORT PIN('E', 6)
#define P_OVERRIDE_SS PIN('E', 0)
#define P_WDT_FAULT PIN('C', 12)

#define P_CRANK PIN('D', 4)           /* TIM2_CH2, AF2 */
#define P_CAM PIN('D', 7)             /* TIM2_CH3, AF2 */
#define AF_TIM2 2u
/* Which edge is a tooth. The core's interface says falling (ecu.h); the
 * speed-input sheet does not fix the conditioner's polarity, so bring-up
 * step 3 checks it on the scope. 1 = falling, 0 = rising. */
#define CRANK_FALLING 1
#define CAM_FALLING 1

#define P_CAN1_RX PIN('D', 0)
#define P_CAN1_TX PIN('D', 1)
#define P_CAN2_RX PIN('B', 5)
#define P_CAN2_TX PIN('B', 6)
#define AF_FDCAN 9u

/* ---- analog (sensors_analog, rails, injector, metering_egr sheets) ----
 * VREF+ is 3V3_A, measured each scan against VREFINT. */
#define VDDA_NOM 3.30f
#define G_DIFF 0.5f                   /* INA592 difference stage, G = 1/2 */
#define G_RATIO (16.0f / 26.0f)       /* 10k/16k ratiometric divider */
#define G_5V_MON (15.0f / 25.0f)      /* 10k/15k on 5V_MAIN */
#define G_VBAT (10.0f / 130.0f)       /* 120k/10k */
#define G_SYNC (10.0f / 32.0f)        /* 22k/10k, pin 09 */
#define G_BOOST_MON (24.9f / 1022.9f) /* 2 x 499k / 24.9k (prototype/additions.py) */
#define A_PER_V_INJ 10.0f             /* 5 mOhm x INA181A1 gain 20 = 0.1 V/A */
#define A_PER_V_MU 1.0f               /* 50 mOhm x 20 */
#define A_PER_V_EGR 2.5f              /* 20 mOhm x 20 = 0.4 V/A */

/* ADC2 scan order; each is ADC2_INx on its pin (stm32_pins.py). */
enum { AN_CLT, AN_OIL, AN_RAIL, AN_BOOST, AN_EGR_POS, AN_VBAT, AN_SYNC,
       AN_BOOST_MON, AN_I_EGR, AN_I_MU, AN_VBAT2, AN_BOOST_T, AN_N2 };
#define ADC2_CHANNELS { 8, 5, 11, 6, 9, 1, 12, 14, 4, 3, 2, 7 }
/* ADC3: the 5 V monitor, the barometer, VREFINT */
enum { AN_5V, AN_BARO, AN_VREFINT, AN_N3 };
#define ADC3_CHANNELS { 1, 12, 18 }
/* ADC1: the injector shunts only, one at a time (inj_hw.c) */
#define ADC1_CH_BANK_A 3u
#define ADC1_CH_BANK_B 4u

/* ---- metering valve PWM. The frequency is not settled
 * (metering_unit_pwm.cir: "make it a firmware constant"); 1 kHz is the
 * block's middle case. */
#define METER_PWM_HZ 1000u

/* ---- injector current law (U5 open: the sim's figures) ---- */
#define INJ_PEAK_A 18.0f              /* injector_boost.cir: needle lifts at ~18 A */
#define INJ_HOLD_LO_A 9.0f            /* hold band around the ~10 A the sim used */
#define INJ_HOLD_HI_A 11.0f
#define INJ_OVER_A 26.0f              /* any phase: all gates off */
#define INJ_PEAK_MAX_US 60u           /* 38 us nominal, 45 worst; past this the sense is broken */
#define INJ_CAP_US 5000u              /* no single injection longer, whatever the core asks */
#define INJ_LATE_US 50u               /* a start this late is skipped, not shifted */

/* ---- interrupt priorities (4 bits). Injection timing above all; the
 * core's three entry points share one level (firmware guide sec. 14 item 9). */
#define PRIO_INJ 0u                   /* TIM5 compare, ADC1 watchdogs */
#define PRIO_CORE 2u                  /* SysTick, TIM2 capture, FDCAN */
#define PRIO_USB 3u

/* ---- flash map (dual bank, 2 KiB pages). Bank 2 holds the stored data,
 * so a write never stalls code running from bank 1. ---- */
#define FLASH_BASE_ADDR 0x08000000u
#define FLASH_PAGE 2048u
#define FLASH_BANK2 0x08040000u
#define BOOT_BASE FLASH_BASE_ADDR
#define BOOT_INFO_ADDR 0x08007FE0u    /* the bootloader's version, read by the application */
#define APP_BASE 0x08008000u          /* the image header (boot.h BOOT_HDR = 64 bytes) */
#define APP_VECTORS (APP_BASE + 0x200u)   /* VTOR needs 512-byte alignment here */
#define APP_END 0x0807C000u
#define APP_SIZE (APP_END - APP_BASE)
#define NVM_SLOT0 0x0807C000u         /* 2 pages each: the image is 3036 bytes */
#define NVM_SLOT1 0x0807D000u
#define NVM_SLOT_SIZE 0x1000u
#define EOL_A 0x0807F000u             /* one page each, so copy b survives copy a's erase */
#define EOL_B 0x0807F800u

/* ---- RAM shared by the bootloader and the application: the first 32
 * bytes of SRAM1, outside both images' .data and .bss ---- */
#define SHARED_RAM 0x20000000u
#define STAY_MAGIC 0x57A1B007u
#define BOOT_INFO_MAGIC 0xB0071AF0u

typedef struct {
    volatile uint32_t stay;           /* STAY_MAGIC: the bootloader stays */
    volatile uint32_t spare[7];
} shared_ram_t;
#define SHARED ((shared_ram_t *)SHARED_RAM)

typedef struct {
    uint32_t magic;                   /* BOOT_INFO_MAGIC */
    uint16_t version;                 /* boot.h BOOT_VERSION */
    uint16_t spare;
} boot_info_t;

#endif
