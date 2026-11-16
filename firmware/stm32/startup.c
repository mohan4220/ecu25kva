/* Reset, the vector table and the fault handlers, shared by the
 * application and the bootloader. */
#include "hw.h"

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
int main(void);
extern void (*const vectors[])(void);

volatile uint32_t ecc_hits;            /* flash double-bit errors seen by the NMI */

void Reset_Handler(void)
{
    volatile uint32_t *s = &_sidata, *d = &_sdata;
    while (d < &_edata)
        *d++ = *s++;
    for (d = &_sbss; d < &_ebss; )
        *d++ = 0;
    SCB->CPACR |= (3u << 20) | (3u << 22);       /* CP10, CP11: the FPU */
    SCB->VTOR = (uint32_t)(uintptr_t)vectors;   /* the bootloader set it too; standalone, it is 0 */
    __DSB();
    __ISB();
    main();
    for (;;) {}
}

/* Every gate off, at once, by register: whatever went wrong, the injector
 * stage and the metering valve stop. The relays stay as they are (the
 * main relay is also held by the wake FET). The external watchdog then
 * resets the chip and GATE_KILL backs this up in hardware. */
static void gates_off(void)
{
    GPIOC->BSRR = (1u << 6 | 1u << 7 | 1u << 8 | 1u << 9) << 16;
    GPIOE->BSRR = (1u << 1 | 1u << 2 | 1u << 3) << 16;
    GPIOE->MODER = (GPIOE->MODER & ~(3u << 2)) | 1u << 2;   /* PE1: from TIM20 to plain low */
    GPIOF->BSRR = (1u << 2) << 16;
    GPIOA->BSRR = (1u << 8 | 1u << 9 | 1u << 10) << 16;
}

void Fault_Handler(void)
{
    gates_off();
    for (;;) {}
}

/* A double-bit ECC error reading flash raises the NMI and the read
 * returns garbage. Reading a half-written page after a power cut is the
 * one way it happens here, and the reader checks a CRC anyway: count it
 * and carry on. Anything else is a fault. */
void NMI_Handler(void)
{
    if (FLASH->ECCR & FLASH_ECCR_ECCD) {
        FLASH->ECCR |= FLASH_ECCR_ECCD;
        ecc_hits++;
        return;
    }
    Fault_Handler();
}

void Default_Handler(void) { Fault_Handler(); }

#define WEAK __attribute__((weak, alias("Default_Handler")))
void SysTick_Handler(void) WEAK;
void TIM2_IRQHandler(void) WEAK;
void TIM5_IRQHandler(void) WEAK;
void ADC1_2_IRQHandler(void) WEAK;
void FDCAN1_IT0_IRQHandler(void) WEAK;
void FDCAN2_IT0_IRQHandler(void) WEAK;
void USB_HP_IRQHandler(void) WEAK;
void USB_LP_IRQHandler(void) WEAK;
void USBWakeUp_IRQHandler(void) WEAK;

#define NVEC (16 + 102)
typedef void (*vec_t)(void);

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Winitializer-overrides"
#pragma clang diagnostic ignored "-Wpedantic"
__attribute__((section(".isr_vector"), used))
const vec_t vectors[NVEC] = {
    [0 ... NVEC - 1] = Default_Handler,
    [0] = (vec_t)(uintptr_t)&_estack,
    [1] = Reset_Handler,
    [2] = NMI_Handler,
    [3] = Fault_Handler,               /* HardFault */
    [4] = Fault_Handler,               /* MemManage */
    [5] = Fault_Handler,               /* BusFault */
    [6] = Fault_Handler,               /* UsageFault */
    [7] = 0, [8] = 0, [9] = 0, [10] = 0, [13] = 0,
    [11] = Default_Handler,            /* SVC */
    [12] = Default_Handler,            /* DebugMon */
    [14] = Default_Handler,            /* PendSV */
    [15] = SysTick_Handler,
    [16 + TIM2_IRQn] = TIM2_IRQHandler,
    [16 + TIM5_IRQn] = TIM5_IRQHandler,
    [16 + ADC1_2_IRQn] = ADC1_2_IRQHandler,
    [16 + FDCAN1_IT0_IRQn] = FDCAN1_IT0_IRQHandler,
    [16 + FDCAN2_IT0_IRQn] = FDCAN2_IT0_IRQHandler,
    [16 + USB_HP_IRQn] = USB_HP_IRQHandler,
    [16 + USB_LP_IRQn] = USB_LP_IRQHandler,
    [16 + USBWakeUp_IRQn] = USBWakeUp_IRQHandler,
};
#pragma clang diagnostic pop
