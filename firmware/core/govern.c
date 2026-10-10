#include "govern.h"

static float clampf(float x, float lo, float hi) { return x < lo ? lo : x > hi ? hi : x; }

void gov_reset(gov_t *g, float fuel0, float rpm0)
{
    g->integ = g->fuel = fuel0;
    g->set = rpm0 < GOV_RPM_SET ? rpm0 : GOV_RPM_SET;
}

float gov_setpoint(float fuel, int droop)
{
    return droop ? GOV_RPM_SET * (1.0f - GOV_DROOP * fuel / FUEL_RATED_MG) : GOV_RPM_SET;
}

float gov_step(gov_t *g, float rpm, int droop, float dt_s)
{
    /* the setpoint ramps from the RUN-entry speed, so the start does not
     * slam into the fuel limit and overshoot towards the overspeed trip */
    g->set = clampf(g->set + GOV_RAMP_RPM_S * dt_s, 0, GOV_RPM_SET);
    float target = gov_setpoint(g->fuel, droop);
    float err = (g->set < target ? g->set : target) - rpm;
    g->integ = clampf(g->integ + GOV_KI * err * dt_s, 0, FUEL_MAX_MG);
    g->fuel = clampf(g->integ + GOV_KP * err, 0, FUEL_MAX_MG);
    return g->fuel;
}
