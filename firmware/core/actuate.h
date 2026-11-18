/* The inner loops of the two cascades (decisions log 23), after the
 * 20 kVA set's cascade PID: an outer loop sets a target, an inner loop
 * on the actuator's own measurement makes the PWM.
 *
 * METERING VALVE (pin 88): rail pressure -> valve current -> PWM.
 *   The rail PI's output is a CURRENT command, in units of the full
 *   current MU_I_FULL (so 1.0 = the current that closes the valve). The
 *   inner loop feeds forward the battery voltage and closes on the coil
 *   current (ISNS_MU), so a hot coil or a sagging battery no longer moves
 *   the valve. This is what the old Bosch ECU does (its MeUn_iSet, field
 *   evidence 2026-10-14). Without a current measurement it is feedforward
 *   only: the duty is the command times MU_V_FULL / battery, so that a
 *   nominal coil carries the commanded current.
 *
 * EGR VALVE (pins 59/81, position on pin 37): target position -> PID on
 *   position -> bridge duty. Derivative on the measurement (no kick when
 *   the target steps), filtered; the integral stops while the output is
 *   saturated. At or below EGR_CLOSED_PCT, or not enabled, the bridge
 *   COASTS: the spring closes the valve, and driving against the closed
 *   stop would only stall the motor (and trip the stall guard). */
#ifndef ACTUATE_H
#define ACTUATE_H

#include <stdint.h>

/* The coil, MEASURED 18 Nov 2026 on the set's metering unit: 2.5-5 ohm
 * (decisions log 25; the 10 ohm before was a class guess). Nominal is the
 * middle. The current that closes the valve is still ASSUMED, 1.35 A
 * (it comes from the unit's own data): command 1.0 means that current. */
#define MU_R_NOM 3.75f               /* coil ohms, nominal (measured 2.5-5) */
#define MU_I_FULL 1.35f              /* A: command 1.0, the valve closed (assumed) */
#define MU_V_FULL 5.0625f            /* MU_I_FULL * MU_R_NOM: volts across the coil at command 1.0 */
#define MU_V_NOM 13.5f               /* the battery when there is no plausible reading */
#define MU_VBAT_MIN 6.0f             /* a 12 V system: outside this, assume MU_V_NOM */
#define MU_VBAT_MAX 18.0f
/* The gains in duty per unit of current error, scaled by 3.75/10 when the
 * coil was measured so the loop keeps its dynamics (a lower-resistance
 * coil gives more current per unit of duty). The integral covers the
 * whole coil spread: 1.85 ohm (2.5 cold) to 6.91 ohm (5 hot) against the
 * 3.75 feedforward, down to a 10 V battery. */
#define MU_KP 0.075f                 /* calibration, duty per unit of current error */
#define MU_KI 7.5f                   /* calibration, duty/(unit*s): coil tau 3 ms */
#define MU_INTEG_MAX 0.4f

#define EGR_KP 0.02f                 /* calibration, duty/% */
#define EGR_KI 0.1f                  /* calibration, duty/(%*s) */
#define EGR_KD 0.0005f               /* calibration, duty*s/%, on the measurement */
#define EGR_D_ALPHA 0.1f             /* derivative filter, per 1 ms step */
#define EGR_DUTY_MAX 0.95f           /* the bridge's bootstrap needs a low phase */
#define EGR_CLOSED_PCT 2.0f          /* at or below: coast, the spring closes it */

#ifdef ECU_MODEL
/* generated from model/ecu_mucur.slx and ecu_egrpos.slx; model_glue.c */
#include "ecu_mucur.h"
#include "ecu_egrpos.h"
typedef struct { float integ; RT_MODEL_ecu_mucur_T m; DW_ecu_mucur_T dw; } mu_t;
typedef struct { float integ, prev, dfilt; RT_MODEL_ecu_egrpos_T m; DW_ecu_egrpos_T dw; } egrp_t;
#else
typedef struct { float integ; } mu_t;
typedef struct { float integ, prev, dfilt; } egrp_t;
#endif

/* The feedforward alone: the duty that makes a nominal coil carry cmd
 * (units of MU_I_FULL) on this battery. Used where there is no loop yet:
 * the trip and the reset, which until the coil was measured set a raw
 * duty of 1.0 -- 1.35 A in a 10 ohm coil, 8.6 A in a cold 1.85 ohm one. */
float mu_ff(float cmd, float v_bat);

void  mu_reset(mu_t *m);
/* cmd: the rail PI's output, current in units of MU_I_FULL. Returns the duty. */
float mu_step(mu_t *m, float cmd, float i_meas, uint8_t valid, float v_bat, float dt_s);

void  egrp_reset(egrp_t *e);
/* target, pos: percent open. Returns the bridge duty, -EGR_DUTY_MAX..+EGR_DUTY_MAX. */
float egrp_step(egrp_t *e, float target, float pos, uint8_t enable, float dt_s);
/* The EGR target by fuel. A placeholder of zeros (no EGR) until the
 * emissions calibration exists (decisions log, 12 Nov: certification
 * after the prototype works). */
float egr_target_pct(float fuel_mg);

#endif
