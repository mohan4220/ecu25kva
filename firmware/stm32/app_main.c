/* The application on the prototype: the core (firmware/core, or the
 * Simulink-generated build with ECU_MODEL) on the STM32G474. This file is
 * the firmware guide's sec. 14 list, item by item.
 *
 *   priority 0  TIM5, ADC1         injection timing and current (inj_hw.c)
 *   priority 2  SysTick, TIM2, CAN  the core's entry points, never nested
 *   priority 3  USB                 TinyUSB's interrupt
 *   thread      main loop           ecu_background, flash writes, USB, resets */
#include <string.h>
#include "hw.h"
#include "adc.h"
#include "timebase.h"
#include "inj_hw.h"
#include "can.h"
#include "flash.h"
#include "usb.h"
#include "ecu.h"
#include "eol.h"

static ecu_io io;
static volatile uint32_t ms;
static volatile uint32_t reset_at;    /* ms when a requested reset goes ahead; 0 none */
static uint32_t crank_overcap, cam_overcap, flash_fails;
static int clock_on_hsi;
/* For the bench, read with the debugger: the longest tick so far, in CPU
 * cycles (170 per us). It must stay well under 170000. */
volatile uint32_t tick_max_cycles;
extern volatile uint32_t ecc_hits;

/* ---- inputs: pads to the core's logical levels and connector volts ---- */
static void read_inputs(void)
{
    io.ignition = (uint8_t)!pin_get(P_IGNITION);   /* active high, inverted by the buffer */
    io.wif = (uint8_t)!pin_get(P_WIF);
    io.stop_sw = (uint8_t)pin_get(P_STOP);         /* contact to ground: closed = pad high */
    io.diag_sw = (uint8_t)pin_get(P_DIAG);
    io.droop_sw = (uint8_t)pin_get(P_DROOP);
    io.v_clt = adc_pin_v(AN_CLT) / G_DIFF;
    io.v_oil = adc_pin_v(AN_OIL) / G_DIFF;
    io.v_rail = adc_pin_v(AN_RAIL) / G_RATIO;
    io.v_boost = adc_pin_v(AN_BOOST) / G_DIFF;
    io.v_egr = adc_pin_v(AN_EGR_POS) / G_DIFF;
    io.v_5v = adc3_pin_v(AN_5V) / G_5V_MON;
    io.v_bat = adc_pin_v(AN_VBAT) / G_VBAT;
    io.v_sync = adc_pin_v(AN_SYNC) / G_SYNC;
    io.v_boost_rail = adc_pin_v(AN_BOOST_MON) / G_BOOST_MON;
    io.i_egr = adc_pin_v(AN_I_EGR) * A_PER_V_EGR;
    io.i_mu = adc_mu_amps();
    io.i_mu_valid = 1;
}

/* ---- the metering valve: TIM20 CH4 on PE1 ---- */
static uint32_t meter_arr;

static void meter_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_TIM20EN;
    (void)RCC->APB2ENR;
    TIM20->CR1 = 0;
    TIM20->PSC = 2;                                         /* 56.67 MHz */
    meter_arr = SYSCLK_HZ / 3u / METER_PWM_HZ - 1u;
    TIM20->ARR = meter_arr;
    TIM20->CCR4 = 0;
    TIM20->CCMR2 = (6u << TIM_CCMR2_OC4M_Pos) | TIM_CCMR2_OC4PE;   /* PWM mode 1 */
    TIM20->CCMR1 = 0;                                       /* CH1: timing only, no pin (PE2 is GPIO) */
    TIM20->CCR1 = 0;
    TIM20->CR2 = 3u << TIM_CR2_MMS_Pos;                     /* TRGO = CC1 compare pulse: the ADC sample */
    TIM20->CCER = TIM_CCER_CC4E;
    TIM20->BDTR = TIM_BDTR_MOE;
    TIM20->EGR = TIM_EGR_UG;
    TIM20->CR1 = TIM_CR1_ARPE | TIM_CR1_CEN;
    pin_mode(P_MU_PWM, PM_AF, AF_MU_PWM);
}

/* ---- the EGR bridge: TIM1 CH1 / CH2 on PA8 / PA9 ---- */
static uint32_t egr_arr;

static void egr_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_TIM1EN;
    (void)RCC->APB2ENR;
    TIM1->CR1 = 0;
    TIM1->PSC = 2;                                          /* 56.67 MHz */
    egr_arr = SYSCLK_HZ / 3u / EGR_PWM_HZ - 1u;
    TIM1->ARR = egr_arr;
    TIM1->CCR1 = TIM1->CCR2 = 0;
    TIM1->CCMR1 = (6u << TIM_CCMR1_OC1M_Pos) | TIM_CCMR1_OC1PE | (6u << TIM_CCMR1_OC2M_Pos) | TIM_CCMR1_OC2PE;
    TIM1->CCER = TIM_CCER_CC1E | TIM_CCER_CC2E;
    TIM1->BDTR = TIM_BDTR_MOE;
    TIM1->EGR = TIM_EGR_UG;
    TIM1->CR1 = TIM_CR1_ARPE | TIM_CR1_CEN;
    pin_mode(P_EGR_IN1, PM_AF, AF_EGR);
    pin_mode(P_EGR_IN2, PM_AF, AF_EGR);
}

static void write_outputs(void)
{
    float d = io.meter_duty;
    d = d < 0.0f ? 0.0f : d > 1.0f ? 1.0f : d;
    uint32_t c4 = (uint32_t)(d * (float)(meter_arr + 1u) + 0.5f);
    TIM20->CCR4 = c4;
    TIM20->CCR1 = c4 / 2u;                                  /* the middle of the on-time */
    /* EGR: sign-magnitude; the other leg held low (low-side brake while it
     * switches); EN only while driving. egr_off (the stall guard) coasts. */
    float e = io.egr_off ? 0.0f : io.egr_duty;
    e = e < -0.95f ? -0.95f : e > 0.95f ? 0.95f : e;
    uint32_t ce = (uint32_t)((e < 0 ? -e : e) * (float)(egr_arr + 1u) + 0.5f);
    TIM1->CCR1 = e > 0 ? ce : 0;
    TIM1->CCR2 = e < 0 ? ce : 0;
    pin_set(P_EGR_EN, ce != 0);
    pin_set(P_WDT_KICK, io.wdg);
    pin_set(P_RLY_MAIN, io.main_relay);
    pin_set(P_BOOST_DIS, io.boost_dis);
    /* status LED: 1 Hz stopped, 5 Hz cranking or running, on in SHUTDOWN;
     * 2 Hz if the crystal failed and the clock is HSI16 */
    uint32_t half = clock_on_hsi ? 250u : (io.state == ECU_CRANK || io.state == ECU_RUN) ? 100u : 500u;
    pin_set(P_LED, io.state == ECU_SHUTDOWN ? 1 : (int)(ms / half & 1u));
}

/* ---- the core's entry points ---- */
void SysTick_Handler(void)
{
    uint32_t c0 = cycles();
    ms++;
    usb_ms = ms;
    uint32_t t = now_us();
    read_inputs();
    if (io.usb_in_n == 0)
        io.usb_in_n = (uint8_t)usb_to_core(io.usb_in, ECU_USB_IN);
    ecu_tick_1ms(&io, t);
    inj_hw_sync(&io);
    write_outputs();
    can_pump(0);
    can_pump(1);
    if (io.usb_out_n) {
        usb_from_core(io.usb_out, io.usb_out_n);
        io.usb_out_n = 0;
    }
    if ((io.reset_req || io.boot_req) && !reset_at)
        reset_at = ms + 50u;                            /* the response goes out first */
    if (ms % 1000u == 0)
        inj_hw_levels(adc_vdda());
    uint32_t dc = cycles() - c0;
    if (dc > tick_max_cycles)
        tick_max_cycles = dc;
}

void TIM2_IRQHandler(void)
{
    uint32_t sr = TIM2->SR;
    if (sr & TIM_SR_CC2IF) {
        ecu_crank_edge(&io, TIM2->CCR2);                /* reading CCR2 clears CC2IF */
        inj_hw_sync(&io);
    }
    if (sr & TIM_SR_CC3IF)
        ecu_cam_edge(&io, TIM2->CCR3);
    if (sr & (TIM_SR_CC2OF | TIM_SR_CC3OF)) {
        crank_overcap += !!(sr & TIM_SR_CC2OF);
        cam_overcap += !!(sr & TIM_SR_CC3OF);
        TIM2->SR = ~(TIM_SR_CC2OF | TIM_SR_CC3OF);
    }
}

static void rx_j1939(const ecu_can *f) { ecu_can_rx(&io, f); }
static void rx_service(const ecu_can *f) { ecu_can2_rx(&io, f); }

/* ---- stored data ---- */
static uint8_t slot_a[NVM_SLOT_SIZE], slot_b[NVM_SLOT_SIZE];

/* A copy of flash, or blank if reading it hit an ECC error (startup.c). */
static void read_safe(void *dst, uint32_t addr, uint32_t n)
{
    uint32_t e = ecc_hits;
    memcpy(dst, (const void *)(uintptr_t)addr, n);
    if (ecc_hits != e)
        memset(dst, 0xFF, n);
}

static void load_stored(void)
{
    uint32_t len;
    (void)ecu_nvm_image(&len);
    read_safe(slot_a, NVM_SLOT0, len);
    read_safe(slot_b, NVM_SLOT1, len);
    ecu_nvm_load(&io, slot_a, slot_b, len);
    uint8_t ea[sizeof(eol_record)], eb[sizeof(eol_record)];
    read_safe(ea, EOL_A, sizeof ea);
    read_safe(eb, EOL_B, sizeof eb);
    ecu_eol_load(&io, ea, eb);
}

static flash_job job;
enum { JOB_NONE, JOB_NVM, JOB_EOL_A, JOB_EOL_B };
static int job_kind;
static uint8_t eol_copy[128];
static uint32_t eol_len;

static void storage_step(void)
{
    if (job_kind != JOB_NONE) {
        if (flash_job_step(&job))
            return;
        flash_fails += !job.ok;
        if (job_kind == JOB_NVM) {
            io.nvm_save = 0;
        } else if (job_kind == JOB_EOL_A) {
            job_kind = JOB_EOL_B;
            flash_job_start(&job, EOL_B, eol_copy, eol_len);  /* the same bytes, copy b */
            return;
        } else {
            io.eol_save = 0;
        }
        job_kind = JOB_NONE;
        return;
    }
    uint32_t len;
    if (io.eol_save) {
        uint32_t b = core_mask();                       /* a service write may be changing it */
        const void *p = ecu_eol_image(&len);
        eol_len = len < sizeof eol_copy ? len : (uint32_t)sizeof eol_copy;
        memcpy(eol_copy, p, eol_len);
        core_unmask(b);
        flash_job_start(&job, EOL_A, eol_copy, eol_len);
        job_kind = JOB_EOL_A;
    } else if (io.nvm_save) {
        const void *p = ecu_nvm_image(&len);            /* stable until nvm_save clears */
        flash_job_start(&job, io.nvm_slot ? NVM_SLOT1 : NVM_SLOT0, p, len);
        job_kind = JOB_NVM;
    }
}

static void maybe_reset(void)
{
    if (!reset_at || (int32_t)(ms - reset_at) < 0)
        return;
    /* the reply must have left, and no flash write may be cut */
    int quiet = usb_tx_idle() && io.can2_n == 0 && job_kind == JOB_NONE;
    if (!quiet && (int32_t)(ms - reset_at) < 500)
        return;
    if (io.boot_req)
        SHARED->stay = STAY_MAGIC;
    inj_hw_stop();
    NVIC_SystemReset();
}

int main(void)
{
    pins_safe();
    clock_on_hsi = clock_init() != 0;
    adc_init();
    meter_init();
    adc_mu_init();
    egr_init();

    ecu_init(&io);
    io.reset_cause = reset_cause();
    const boot_info_t *bi = (const boot_info_t *)BOOT_INFO_ADDR;
    io.boot_ver = bi->magic == BOOT_INFO_MAGIC ? bi->version : 0;
    if (flash_dual_bank())
        load_stored();
    else
        ecu_nvm_load(&io, slot_a, slot_b, 0);           /* single-bank: nothing stored */
    read_inputs();

    timebase_init();
    inj_hw_init();
    can_init(0, rx_j1939, io.can, &io.can_n);
    can_init(1, rx_service, io.can2, &io.can2_n);
    usb_init();
    systick_1ms(PRIO_CORE);

    for (;;) {
        uint32_t b = core_mask();                       /* sec. 14 item 9: the image copy */
        ecu_background(&io);
        core_unmask(b);
        if (flash_dual_bank())
            storage_step();
        else
            io.nvm_save = io.eol_save = 0;
        usb_task();
        maybe_reset();
    }
}
