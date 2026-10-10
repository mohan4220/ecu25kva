/* One main injection per cylinder per cycle, as start-time + duration
 * commands. Cylinder index k = 0,1,2 is cylinder 1,2,3 (firing order
 * 1-2-3, 240 deg apart). */
#ifndef INJECT_H
#define INJECT_H

#include "ecu.h"
#include "crank.h"

#define INJ_SOI_BTDC 5.0f            /* calibration */
#define INJ_DEAD_US 300.0f           /* assumed */
#define INJ_K 0.0009f                /* assumed: mg/us per sqrt(bar) */
#define INJ_RAIL_MIN 100.0f          /* floor for the flow law */
#define FUEL_START_MG 30.0f          /* calibration: fixed fuel while cranking */

uint32_t inject_dur_us(float fuel_mg, float rail_bar);
int  inject_due(const crank_t *c, float soi_deg);
void inject_edge(const crank_t *c, float fuel_mg, float rail_bar, ecu_inj out[ECU_NCYL]);
void inject_cancel(ecu_inj out[ECU_NCYL]);

#endif
