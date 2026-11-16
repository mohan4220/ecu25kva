/* 170 MHz from the 8 MHz crystal, the way RM0440 sec. 6.1.5 and ST's HAL
 * (HAL_RCC_ClockConfig) do it: range 1 boost mode, 4 wait states, HCLK
 * halved across the switch to the PLL and restored after 1 us. */
#include "hw.h"

uint32_t SystemCoreClock = 16000000u;  /* CMSIS expects it */

static int wait(volatile uint32_t *reg, uint32_t mask, uint32_t want, uint32_t loops)
{
    while (((*reg & mask) == want ? 0 : 1) && loops)
        loops--;
    return loops ? 0 : -1;
}

int clock_init(void)
{
    int on_hsi = 0;
    RCC->APB1ENR1 |= RCC_APB1ENR1_PWREN;
    RCC->APB2ENR |= RCC_APB2ENR_SYSCFGEN;
    (void)RCC->APB1ENR1;

    RCC->CR |= RCC_CR_HSEON;
    if (wait(&RCC->CR, RCC_CR_HSERDY, RCC_CR_HSERDY, 400000u)) {   /* ~100 ms on HSI16 */
        RCC->CR &= ~RCC_CR_HSEON;
        on_hsi = 1;
    }

    /* range 1 boost (R1MODE = 0) before the frequency rises above 150 MHz */
    PWR->CR5 &= ~PWR_CR5_R1MODE;
    FLASH->ACR = (FLASH->ACR & ~FLASH_ACR_LATENCY) | FLASH_ACR_LATENCY_4WS
               | FLASH_ACR_PRFTEN | FLASH_ACR_ICEN | FLASH_ACR_DCEN;
    while ((FLASH->ACR & FLASH_ACR_LATENCY) != FLASH_ACR_LATENCY_4WS) {}

    /* VCO = 8 MHz / 2 x 85 = 340 MHz (HSI16: / 4); SYSCLK = VCO / 2 */
    RCC->CR &= ~RCC_CR_PLLON;
    while (RCC->CR & RCC_CR_PLLRDY) {}
    RCC->PLLCFGR = (on_hsi ? RCC_PLLCFGR_PLLSRC_HSI : RCC_PLLCFGR_PLLSRC_HSE)
                 | ((on_hsi ? 4u : 2u) - 1u) << RCC_PLLCFGR_PLLM_Pos
                 | 85u << RCC_PLLCFGR_PLLN_Pos
                 | 0u << RCC_PLLCFGR_PLLR_Pos          /* /2 */
                 | RCC_PLLCFGR_PLLREN;
    RCC->CR |= RCC_CR_PLLON;
    while (!(RCC->CR & RCC_CR_PLLRDY)) {}

    RCC->CFGR = (RCC->CFGR & ~(RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2))
              | RCC_CFGR_HPRE_DIV2;
    RCC->CFGR = (RCC->CFGR & ~RCC_CFGR_SW) | RCC_CFGR_SW_PLL;
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_PLL) {}
    for (volatile uint32_t i = 0; i < 200u; i++) {}     /* > 1 us at 85 MHz */
    RCC->CFGR &= ~RCC_CFGR_HPRE;                        /* HCLK = 170 MHz, APB1 = APB2 = 170 MHz */
    SystemCoreClock = SYSCLK_HZ;

    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    /* CYCCNT keeps counting across the switch: the bootloader times the watchdog on it */
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    return on_hsi ? -1 : 0;
}

/* USB needs 48 MHz to 0.25 %: HSI48, trimmed continuously from the host's
 * start-of-frame (CRS, whose reset configuration already selects USB SOF). */
void clock_usb48(void)
{
    RCC->CRRCR |= RCC_CRRCR_HSI48ON;
    while (!(RCC->CRRCR & RCC_CRRCR_HSI48RDY)) {}
    RCC->CCIPR &= ~RCC_CCIPR_CLK48SEL;                  /* 00: HSI48 */
    RCC->APB1ENR1 |= RCC_APB1ENR1_CRSEN;
    (void)RCC->APB1ENR1;
    CRS->CR |= CRS_CR_AUTOTRIMEN | CRS_CR_CEN;
}

void systick_1ms(uint32_t prio)
{
    SysTick->LOAD = SystemCoreClock / 1000u - 1u;
    SysTick->VAL = 0;
    NVIC_SetPriority(SysTick_IRQn, prio);
    SysTick->CTRL = SysTick_CTRL_CLKSOURCE_Msk | SysTick_CTRL_TICKINT_Msk | SysTick_CTRL_ENABLE_Msk;
}

uint32_t cycles(void) { return DWT->CYCCNT; }

void delay_us(uint32_t us)
{
    uint32_t t0 = DWT->CYCCNT, n = us * (SystemCoreClock / 1000000u);
    while (DWT->CYCCNT - t0 < n) {}
}

void irq_on(IRQn_Type n, uint32_t prio)
{
    NVIC_SetPriority(n, prio);
    NVIC_ClearPendingIRQ(n);
    NVIC_EnableIRQ(n);
}

uint8_t reset_cause(void)
{
    uint32_t csr = RCC->CSR;
    RCC->CSR |= RCC_CSR_RMVF;
    if (csr & (RCC_CSR_BORRSTF))
        return 0;                               /* power-on (BOR follows every power-up) */
    /* The TPS3850 resets the chip through NRST, so its trips read as a pin
     * reset; so does a debugger's. On the engine there is no debugger. */
    if (csr & (RCC_CSR_IWDGRSTF | RCC_CSR_WWDGRSTF | RCC_CSR_PINRSTF))
        return (csr & RCC_CSR_SFTRSTF) ? 2 : 1;
    return 2;
}
