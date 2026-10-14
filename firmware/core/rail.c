#include "rail.h"
#include "table.h"

/* The old ECU's setpoint at 1500 rpm, median per 1 mg of fuel, steady
 * running (field evidence 2026-10-14 sec. 3c). Held beyond 26.5 mg: no
 * data above that yet. */
static const float RAIL_Q[] = { 6.5f, 8.5f, 9.5f, 10.5f, 14.5f, 16.5f, 18.5f, 20.5f, 25.5f, 26.5f };
static const float RAIL_P[] = { 827, 838, 885, 994, 994, 1046, 1108, 1147, 1156, 1171 };

float rail_set_bar(float fuel_mg)
{
    return table_lookup(RAIL_Q, RAIL_P, (int)(sizeof RAIL_Q / sizeof RAIL_Q[0]), fuel_mg);
}

static float clampf(float x, float lo, float hi) { return x < lo ? lo : x > hi ? hi : x; }

void rail_reset(rail_t *r) { r->integ = 0; }

float rail_step(rail_t *r, float set_bar, float rail_bar, float dt_s)
{
    float err = METER_NC ? set_bar - rail_bar : rail_bar - set_bar;
    r->integ = clampf(r->integ + RAIL_KI * err * dt_s, 0, 1);
    return clampf(r->integ + RAIL_KP * err, 0, 1);
}
