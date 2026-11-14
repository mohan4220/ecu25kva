/* Speed governor: PI on rpm error, output = fuel per injection. */
#ifndef GOVERN_H
#define GOVERN_H

#define GOV_RPM_SET 1500.0f
#define GOV_DROOP 0.04f              /* assumed: droop switch closed */
#define FUEL_MAX_MG 45.0f            /* assumed */
#define FUEL_RATED_MG 34.0f          /* assumed: fuel at 20 kW */
#define GOV_KP 0.5f                  /* calibration, mg/rpm */
#define GOV_KI 2.0f                  /* calibration, mg/(rpm*s) */
#define GOV_RAMP_RPM_S 500.0f        /* calibration: setpoint ramp from RUN entry */

#ifdef ECU_MODEL
/* ECU_MODEL: the governor is generated from model/ecu_gov.slx (Embedded
 * Coder); model_glue.c keeps this API. integ, fuel and set stay readable. */
#include <stdint.h>
#include "ecu_gov.h"
typedef struct {
    float integ, fuel, set;
    float fuel0, rpm0;               /* gov_reset's values, applied on the next step */
    uint8_t rst;
    RT_MODEL_ecu_gov_T m;
    DW_ecu_gov_T dw;
} gov_t;
#else
typedef struct { float integ, fuel, set; } gov_t;   /* set: ramping speed setpoint */
#endif

void  gov_reset(gov_t *g, float fuel0, float rpm0);   /* bumpless: set = rpm0, integ = fuel0 */
float gov_setpoint(float fuel, int droop);
float gov_step(gov_t *g, float rpm, int droop, float dt_s);

#endif
