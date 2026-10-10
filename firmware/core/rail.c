#include "rail.h"

static float clampf(float x, float lo, float hi) { return x < lo ? lo : x > hi ? hi : x; }

void rail_reset(rail_t *r) { r->integ = 0; }

float rail_step(rail_t *r, float rail_bar, float dt_s)
{
    float err = METER_NC ? RAIL_SET_BAR - rail_bar : rail_bar - RAIL_SET_BAR;
    r->integ = clampf(r->integ + RAIL_KI * err * dt_s, 0, 1);
    return clampf(r->integ + RAIL_KP * err, 0, 1);
}
