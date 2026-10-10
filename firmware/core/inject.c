#include <math.h>
#include "inject.h"

uint32_t inject_dur_us(float fuel_mg, float rail_bar)
{
    if (fuel_mg <= 0)
        return 0;
    float p = rail_bar > INJ_RAIL_MIN ? rail_bar : INJ_RAIL_MIN;
    return (uint32_t)(INJ_DEAD_US + fuel_mg / (INJ_K * sqrtf(p)) + 0.5f);
}

/* Is soi the angle between this edge and the next (gap-aware, 720 wrap)? */
int inject_due(const crank_t *c, float soi_deg)
{
    float a = crank_angle(c);
    if (soi_deg < a)
        soi_deg += 720.0f;
    return soi_deg < crank_next_angle(c);
}

void inject_edge(const crank_t *c, float fuel_mg, float rail_bar, ecu_inj out[ECU_NCYL])
{
    for (int k = 0; k < ECU_NCYL; k++) {
        float soi = fmodf(CRANK_TDC1_DEG + 240.0f * k - INJ_SOI_BTDC + 720.0f, 720.0f);
        if (!inject_due(c, soi))
            continue;
        float ahead = soi - crank_angle(c);
        if (ahead < 0)
            ahead += 720.0f;
        out[k].start_us = crank_last_us(c) + (uint32_t)(ahead * crank_us_per_deg(c) + 0.5f);
        out[k].dur_us = inject_dur_us(fuel_mg, rail_bar);
        out[k].seq++;
    }
}

void inject_cancel(ecu_inj out[ECU_NCYL])
{
    for (int k = 0; k < ECU_NCYL; k++)
        out[k].dur_us = 0;
}
