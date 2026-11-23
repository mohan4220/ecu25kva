/* The injector stage on the chip: inj_logic.c's decisions, applied.
 *
 *   TIM5 CH1 compare   the next start, end or peak timeout (priority 0)
 *   ADC1 continuous    the active bank's shunt, ~0.45 us per sample
 *     AWD1             the next crossing inj_logic is waiting for
 *     AWD2             over-current, at any time during an injection
 *   GPIO BSRR          the seven gates
 *
 * The core's commands arrive at its own priority (after ecu_crank_edge
 * and ecu_tick_1ms) through inj_hw_sync, which takes them with every
 * interrupt masked for the few cycles it needs. */
#include "hw.h"
#include "adc.h"
#include "inj_hw.h"
#include "inj_logic.h"
#include "ecu.h"

static inj_t S;
static uint32_t seen_seq[ECU_NCYL];
static uint8_t applied_gates, applied_watch;
static uint16_t applied_lvl;

/* gate bit -> pin */
static const struct { uint8_t bit, pin; } gate_pin[] = {
    { G_LS1, P_INJ_LS1 }, { G_LS2, P_INJ_LS2 }, { G_LS3, P_INJ_LS3 }, { G_HS_A, P_INJ_HS_A },
    { G_HS_B, P_INJ_HS_B }, { G_HS_A_BAT, P_INJ_HS_A_BAT }, { G_HS_B_BAT, P_INJ_HS_B_BAT },
};

static void write_gates(uint8_t g)
{
    /* one BSRR per port, low sides' port (C) first */
    uint32_t c = 0, e = 0, f = 0;
    for (unsigned i = 0; i < sizeof gate_pin / sizeof gate_pin[0]; i++) {
        uint8_t p = gate_pin[i].pin;
        uint32_t b = (g & gate_pin[i].bit) ? 1u << PIN_NUM(p) : 1u << (PIN_NUM(p) + 16u);
        if (PIN_PORT(p) == 'C' - 'A') c |= b;
        else if (PIN_PORT(p) == 'E' - 'A') e |= b;
        else f |= b;
    }
    GPIOC->BSRR = c;
    GPIOE->BSRR = e;
    GPIOF->BSRR = f;
}

static void adc_stop(void)
{
    ADC1->IER = 0;
    if (ADC1->CR & ADC_CR_ADSTART) {
        ADC1->CR |= ADC_CR_ADSTP;
        for (int i = 0; i < 200 && (ADC1->CR & ADC_CR_ADSTP); i++) {}   /* < 1 us */
    }
    ADC1->ISR = ADC_ISR_AWD1 | ADC_ISR_AWD2 | ADC_ISR_OVR | ADC_ISR_EOC | ADC_ISR_EOS;
}

static void set_window(uint8_t watch, uint16_t lvl)
{
    /* AWD1 flags a sample OUTSIDE [LT1, HT1] */
    uint32_t lt = watch == W_BELOW ? lvl : 0u, ht = watch == W_ABOVE ? lvl : 4095u;
    ADC1->TR1 = (ADC1->TR1 & ADC_TR1_AWDFILT) | ht << ADC_TR1_HT1_Pos | lt;
    ADC1->ISR = ADC_ISR_AWD1;
}

static void adc_start(uint8_t bank)
{
    uint32_t ch = bank ? ADC1_CH_BANK_B : ADC1_CH_BANK_A;
    adc_stop();
    ADC1->SQR1 = ch << ADC_SQR1_SQ1_Pos;                  /* L = 0: one channel */
    ADC1->CFGR = ADC_CFGR_CONT | ADC_CFGR_OVRMOD | ADC_CFGR_AWD1SGL | ADC_CFGR_AWD1EN
               | ch << ADC_CFGR_AWD1CH_Pos;
    ADC1->CFGR2 = 0;
    ADC1->AWD2CR = 1u << ch;
    ADC1->TR2 = (uint32_t)(S.c_over >> 4) << ADC_TR2_HT2_Pos;   /* 8-bit: the top bits */
    ADC1->TR1 = 1u << ADC_TR1_AWDFILT_Pos;                    /* two samples in a row */
    set_window(S.watch, S.lvl);
    ADC1->ISR = ADC_ISR_AWD1 | ADC_ISR_AWD2 | ADC_ISR_OVR;
    ADC1->IER = ADC_IER_AWD1IE | ADC_IER_AWD2IE;
    ADC1->CR |= ADC_CR_ADSTART;
}

/* Apply the logic's state; program the next compare. Priority 0. */
static void apply(void)
{
    if (S.gates != applied_gates) {
        write_gates(S.gates);
        applied_gates = S.gates;
    }
    if (S.watch != applied_watch || S.lvl != applied_lvl) {
        if (S.watch == W_OFF)
            adc_stop();
        else if (applied_watch == W_OFF)
            adc_start(S.bank);
        else
            set_window(S.watch, S.lvl);
        applied_watch = S.watch;
        applied_lvl = S.lvl;
    }
    uint32_t t;
    if (inj_next(&S, &t)) {
        TIM5->CCR1 = t;
        TIM5->SR = ~TIM_SR_CC1IF;
        TIM5->DIER = TIM_DIER_CC1IE;
        if ((int32_t)(TIM5->CNT - t) >= 0)               /* already due: do not wait 71 minutes */
            NVIC_SetPendingIRQ(TIM5_IRQn);
    } else {
        TIM5->DIER = 0;
    }
}

void TIM5_IRQHandler(void)
{
    TIM5->SR = ~TIM_SR_CC1IF;
    inj_timer(&S, TIM5->CNT);
    apply();
}

void ADC1_2_IRQHandler(void)
{
    uint32_t isr = ADC1->ISR;
    if (isr & ADC_ISR_AWD2) {
        ADC1->ISR = ADC_ISR_AWD2;
        inj_over(&S);
    } else if (isr & ADC_ISR_AWD1) {
        ADC1->ISR = ADC_ISR_AWD1;
        inj_cross(&S, TIM5->CNT);
    }
    apply();
}

void inj_hw_init(void)
{
    inj_init(&S);
    inj_set_levels(&S, adc_vdda());
    write_gates(0);
    applied_gates = 0;
    applied_watch = W_OFF;
    adc_stop();
    /* 6.5 cycles on IN3 and IN4: the INA181 drives the sample capacitor */
    ADC1->SMPR1 = 1u << ADC_SMPR1_SMP3_Pos | 1u << ADC_SMPR1_SMP4_Pos;
    irq_on(ADC1_2_IRQn, PRIO_INJ);
}

/* After every core entry point: take the commands whose seq moved. */
void inj_hw_sync(const ecu_io *io)
{
    uint32_t m = 0;
    int any = 0;
    for (int k = 0; k < ECU_NCYL; k++) {
        if (io->inj[k].seq == seen_seq[k])
            continue;
        if (!any) {
            m = irq_save();
            any = 1;
        }
        seen_seq[k] = io->inj[k].seq;
        inj_command(&S, k, io->inj[k].start_us, io->inj[k].dur_us);
    }
    if (any) {
        apply();
        irq_restore(m);
    }
}

/* Once a second: VDDA moves the counts a little; only between injections. */
void inj_hw_levels(float vdda)
{
    uint32_t m = irq_save();
    if (S.active < 0)
        inj_set_levels(&S, vdda);
    irq_restore(m);
}

void inj_hw_stop(void)
{
    uint32_t m = irq_save();
    for (int k = 0; k < ECU_NCYL; k++)
        inj_command(&S, k, 0, 0);
    if (S.active >= 0)
        inj_over(&S);                                     /* counted as forced off */
    apply();
    irq_restore(m);
}

const inj_stats *inj_hw_stats(void)
{
    static inj_stats st;
    st.done = S.n_done;
    st.late = S.n_late;
    st.overlap = S.n_overlap;
    st.peak_timeout = S.n_peak_timeout;
    st.over = S.n_over;
    st.capped = S.n_capped;
    st.hold_short = S.n_hold_short;
    return &st;
}
