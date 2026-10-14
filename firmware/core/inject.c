#include <math.h>
#include "inject.h"
#include "table.h"

/* Start of the main injection, deg before TDC, from the old ECU at 1500
 * rpm: median per 1 mg of fuel, steady running (field evidence 2026-10-14
 * sec. 3b). Held beyond 26.5 mg. */
static const float SOI_Q[] = { 6.5f, 8.5f, 11.5f, 14.5f, 17.0f, 18.5f, 20.5f, 26.5f };
static const float SOI_D[] = { 11.5f, 12.4f, 13.5f, 15.5f, 15.9f, 16.0f, 14.6f, 14.2f };

float inject_soi_btdc(float fuel_mg)
{
    return table_lookup(SOI_Q, SOI_D, (int)(sizeof SOI_Q / sizeof SOI_Q[0]), fuel_mg);
}

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

/* Schedule one cylinder from the edge before SOI - lead, so the start time
 * is never in the past by the time a timer compare is loaded. */
int inject_cyl(const crank_t *c, float soi_deg, float fuel_mg, float rail_bar, ecu_inj *out)
{
    float early = soi_deg - INJ_LEAD_DEG;
    if (!inject_due(c, early < 0 ? early + 720.0f : early))
        return 0;
    float ahead = soi_deg - crank_angle(c);
    if (ahead < 0)
        ahead += 720.0f;
    out->start_us = crank_last_us(c) + (uint32_t)(ahead * crank_us_per_deg(c) + 0.5f);
    out->dur_us = inject_dur_us(fuel_mg, rail_bar);
    out->seq++;
    return 1;
}

void inject_edge(const crank_t *c, float fuel_mg, float rail_bar, ecu_inj out[ECU_NCYL])
{
    float soi = inject_soi_btdc(fuel_mg);
    for (int k = 0; k < ECU_NCYL; k++)
        inject_cyl(c, fmodf(CRANK_TDC1_DEG + 240.0f * k - soi + 720.0f, 720.0f),
                   fuel_mg, rail_bar, &out[k]);
}

void inject_cancel(ecu_inj out[ECU_NCYL])
{
    for (int k = 0; k < ECU_NCYL; k++)
        if (out[k].dur_us) {
            out[k].dur_us = 0;
            out[k].seq++;            /* a cancel is a new command too */
        }
}
