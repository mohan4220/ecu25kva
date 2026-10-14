/* One main injection per cylinder per cycle, as start-time + duration
 * commands. Cylinder index k = 0,1,2 is cylinder 1,2,3 (firing order
 * 1-2-3, 240 deg apart). */
#ifndef INJECT_H
#define INJECT_H

#include "ecu.h"
#include "crank.h"

/* Injector law t = dead + q / (K sqrt(p)), fitted to the old ECU's own
 * energising times: 20 473 steady samples, residual within +/-6 us
 * (field evidence 2026-10-14 sec. 3d). */
#define INJ_DEAD_US 323.0f           /* measured */
#define INJ_K 0.00191f               /* measured: mg/us per sqrt(bar) */
#define INJ_RAIL_MIN 100.0f          /* floor for the flow law */
#define INJ_LEAD_DEG 1.0f            /* schedule at least this far ahead: >= 100 us at 1650 rpm */
#define FUEL_START_MG 30.0f          /* calibration: fixed fuel while cranking */

uint32_t inject_dur_us(float fuel_mg, float rail_bar);
float inject_soi_btdc(float fuel_mg);
int  inject_due(const crank_t *c, float soi_deg);
int  inject_cyl(const crank_t *c, float soi_deg, float fuel_mg, float rail_bar, ecu_inj *out);
void inject_edge(const crank_t *c, float fuel_mg, float rail_bar, ecu_inj out[ECU_NCYL]);
void inject_cancel(ecu_inj out[ECU_NCYL]);

#endif
