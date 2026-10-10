/* Speed governor: PI on rpm error, output = fuel per injection. */
#ifndef GOVERN_H
#define GOVERN_H

#define GOV_RPM_SET 1500.0f
#define GOV_DROOP 0.04f              /* assumed: droop switch closed */
#define FUEL_MAX_MG 45.0f            /* assumed */
#define FUEL_RATED_MG 34.0f          /* assumed: fuel at 20 kW */
#define GOV_KP 0.15f                 /* calibration, mg/rpm */
#define GOV_KI 0.6f                  /* calibration, mg/(rpm*s) */

typedef struct { float integ, fuel; } gov_t;

void  gov_reset(gov_t *g, float fuel0);      /* bumpless: integ = fuel0 */
float gov_setpoint(float fuel, int droop);
float gov_step(gov_t *g, float rpm, int droop, float dt_s);

#endif
