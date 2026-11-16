/* The microsecond clock. TIM2 (32-bit) counts microseconds and captures
 * the crank (CH2) and cam (CH3) edges at the core's priority; TIM5, a
 * second 32-bit timer started on the same clock edge, carries the
 * injection compares at the higher priority, because one timer has only
 * one interrupt priority. Both are reset by an update event and enabled
 * back to back, so they agree to within a few CPU cycles of 170. */
#include "hw.h"
#include "timebase.h"

void timebase_init(void)
{
    RCC->APB1ENR1 |= RCC_APB1ENR1_TIM2EN | RCC_APB1ENR1_TIM5EN;
    (void)RCC->APB1ENR1;
    TIM_TypeDef *const t[2] = { TIM2, TIM5 };
    for (int i = 0; i < 2; i++) {
        t[i]->CR1 = 0;
        t[i]->PSC = TIMER_US_PSC;
        t[i]->ARR = 0xFFFFFFFFu;
        t[i]->CNT = 0;
        t[i]->EGR = TIM_EGR_UG;               /* load PSC, clear its counter */
        t[i]->SR = 0;
    }
    /* TIM2: CH2 and CH3 input capture on TI2 / TI3, filter fCK_INT N = 8 */
    pin_mode(P_CRANK, PM_AF, AF_TIM2);
    pin_mode(P_CAM, PM_AF, AF_TIM2);
    TIM2->CCMR1 = (1u << TIM_CCMR1_CC2S_Pos) | (3u << TIM_CCMR1_IC2F_Pos);
    TIM2->CCMR2 = (1u << TIM_CCMR2_CC3S_Pos) | (3u << TIM_CCMR2_IC3F_Pos);
    TIM2->CCER = TIM_CCER_CC2E | (CRANK_FALLING ? TIM_CCER_CC2P : 0)
               | TIM_CCER_CC3E | (CAM_FALLING ? TIM_CCER_CC3P : 0);
    TIM2->DIER = TIM_DIER_CC2IE | TIM_DIER_CC3IE;
    /* TIM5: CH1 compare, timing only (frozen output) */
    TIM5->CCMR1 = 0;
    TIM5->CCR1 = 0;
    TIM5->DIER = 0;

    uint32_t m = irq_save();
    TIM2->CR1 = TIM_CR1_CEN;
    TIM5->CR1 = TIM_CR1_CEN;
    irq_restore(m);

    irq_on(TIM2_IRQn, PRIO_CORE);
    irq_on(TIM5_IRQn, PRIO_INJ);
}

uint32_t now_us(void) { return TIM2->CNT; }
