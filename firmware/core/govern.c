#include "govern.h"

static float clampf(float x, float lo, float hi) { return x < lo ? lo : x > hi ? hi : x; }

void gov_reset(gov_t *g, float fuel0) { g->integ = g->fuel = fuel0; }

float gov_setpoint(float fuel, int droop)
{
    return droop ? GOV_RPM_SET * (1.0f - GOV_DROOP * fuel / FUEL_RATED_MG) : GOV_RPM_SET;
}

float gov_step(gov_t *g, float rpm, int droop, float dt_s)
{
    float err = gov_setpoint(g->fuel, droop) - rpm;
    g->integ = clampf(g->integ + GOV_KI * err * dt_s, 0, FUEL_MAX_MG);
    g->fuel = clampf(g->integ + GOV_KP * err, 0, FUEL_MAX_MG);
    return g->fuel;
}
