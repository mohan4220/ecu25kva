#ifndef INJ_HW_H
#define INJ_HW_H
#include <stdint.h>
#include "ecu.h"

typedef struct { uint32_t done, late, overlap, peak_timeout, over, capped, hold_short; } inj_stats;

void inj_hw_init(void);               /* after adc_init and timebase_init */
void inj_hw_sync(const ecu_io *io);   /* after ecu_crank_edge / ecu_tick_1ms */
void inj_hw_levels(float vdda);
void inj_hw_stop(void);               /* every command dropped, gates off */
const inj_stats *inj_hw_stats(void);

#endif
