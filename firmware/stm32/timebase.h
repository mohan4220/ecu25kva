#ifndef TIMEBASE_H
#define TIMEBASE_H
#include <stdint.h>
void timebase_init(void);             /* TIM2 + TIM5 microseconds, captures armed */
uint32_t now_us(void);
#endif
