/* Pins. Every gate output is written low BEFORE it becomes an output, so
 * there is no instant at which a pin drives a gate high; until then the
 * board's own pull-downs hold them (bring-up step 5). */
#include "hw.h"

static GPIO_TypeDef *const port[] = { GPIOA, GPIOB, GPIOC, GPIOD, GPIOE, GPIOF, GPIOG };

GPIO_TypeDef *pin_gpio(uint8_t p) { return port[PIN_PORT(p)]; }

void pin_mode(uint8_t p, int mode, uint8_t af)
{
    GPIO_TypeDef *g = pin_gpio(p);
    uint32_t n = PIN_NUM(p), m2 = 3u << (2u * n);
    uint32_t mbits = mode == PM_IN ? 0u : mode == PM_OUT ? 1u : mode == PM_AF ? 2u : 3u;
    if (mode == PM_AF) {
        volatile uint32_t *afr = &g->AFR[n >> 3];
        *afr = (*afr & ~(15u << (4u * (n & 7u)))) | (uint32_t)af << (4u * (n & 7u));
    }
    g->OTYPER &= ~(1u << n);                      /* push-pull */
    g->OSPEEDR = (g->OSPEEDR & ~m2) | (2u << (2u * n));   /* high: gate drivers and CAN */
    g->PUPDR &= ~m2;                              /* the board has the pulls */
    g->MODER = (g->MODER & ~m2) | mbits << (2u * n);
}

void pin_set(uint8_t p, int on)
{
    pin_gpio(p)->BSRR = on ? 1u << PIN_NUM(p) : 1u << (PIN_NUM(p) + 16u);
}

int pin_get(uint8_t p) { return (int)(pin_gpio(p)->IDR >> PIN_NUM(p) & 1u); }

static const uint8_t outputs[] = {
    P_INJ_LS1, P_INJ_LS2, P_INJ_LS3, P_INJ_HS_A, P_INJ_HS_B, P_INJ_HS_A_BAT, P_INJ_HS_B_BAT,
    P_MU_PWM, P_EGR_IN1, P_EGR_IN2, P_EGR_EN, P_RLY_MAIN, P_RLY_BUZZER, P_BOOST_DIS,
    P_WDT_KICK, P_LED,
};
static const uint8_t inputs[] = {
    P_IGNITION, P_WIF, P_DIAG, P_STOP, P_DROOP, P_COOLANT_SW, P_AUDIO_ABORT, P_OVERRIDE_SS,
    P_WDT_FAULT,
};

void pins_safe(void)
{
    RCC->AHB2ENR |= RCC_AHB2ENR_GPIOAEN | RCC_AHB2ENR_GPIOBEN | RCC_AHB2ENR_GPIOCEN
                  | RCC_AHB2ENR_GPIODEN | RCC_AHB2ENR_GPIOEEN | RCC_AHB2ENR_GPIOFEN
                  | RCC_AHB2ENR_GPIOGEN;
    RCC->APB1ENR1 |= RCC_APB1ENR1_PWREN;
    (void)RCC->AHB2ENR;
    (void)RCC->APB1ENR1;
    /* PB6 is CAN2's TX: release the USB-C dead-battery pull-down that
     * comes up on it (and on PB4) at reset (RM0440 sec. 6.4.3). */
    PWR->CR3 |= PWR_CR3_UCPD_DBDIS;
    for (unsigned i = 0; i < sizeof outputs; i++) {
        pin_set(outputs[i], 0);
        pin_mode(outputs[i], PM_OUT, 0);
    }
    for (unsigned i = 0; i < sizeof inputs; i++)
        pin_mode(inputs[i], PM_IN, 0);
}
