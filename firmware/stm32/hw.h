/* Small register-level helpers shared by the application and the
 * bootloader: clocks, pins, the microsecond clock, resets. */
#ifndef HW_H
#define HW_H

#include <stdint.h>
#include "stm32g4xx.h"
#include "board.h"

/* clock.c */
int  clock_init(void);                 /* 170 MHz from the crystal; 0 ok, -1 on HSI16 */
void clock_usb48(void);                /* HSI48 trimmed by USB SOF (CRS) */
void systick_1ms(uint32_t prio);
void delay_us(uint32_t us);            /* busy wait on the DWT cycle counter */
uint32_t cycles(void);

/* gpio.c */
enum { PM_IN, PM_OUT, PM_AF, PM_AN };
void pin_mode(uint8_t p, int mode, uint8_t af);
void pin_set(uint8_t p, int on);
int  pin_get(uint8_t p);
void pins_safe(void);                  /* every output its off state, before anything else */
GPIO_TypeDef *pin_gpio(uint8_t p);

static inline uint32_t irq_save(void)
{
    uint32_t m = __get_PRIMASK();
    __disable_irq();
    return m;
}
static inline void irq_restore(uint32_t m) { __set_PRIMASK(m); }

/* Mask the core's level (and USB) but not injection timing. */
static inline uint32_t core_mask(void)
{
    uint32_t b = __get_BASEPRI();
    __set_BASEPRI(PRIO_CORE << (8u - __NVIC_PRIO_BITS));
    return b;
}
static inline void core_unmask(uint32_t b) { __set_BASEPRI(b); }

void irq_on(IRQn_Type n, uint32_t prio);

/* reset cause for ecu_io.reset_cause: 0 power-on, 1 watchdog, 2 other */
uint8_t reset_cause(void);

#endif
