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
 * middle. The current that closes the valve: 1.8 A, the maximum working
 * current published for Bosch's metering units (the set's is 0 928 400
 * 820, owner 22 Nov; decisions log 27). The same data puts idle at
 * 1.38-1.43 A, which the 1.35 A assumed before could not reach. Command
 * 1.0 means this current. Family data, not the part's own sheet. */
#define MU_R_NOM 3.75f               /* coil ohms, nominal (measured 2.5-5) */
#define MU_I_FULL 1.8f               /* A: command 1.0, the valve closed (Bosch family max, 1.8 A) */
#define MU_V_FULL 6.75f              /* MU_I_FULL * MU_R_NOM: volts across the coil at command 1.0 */
#define MU_V_NOM 13.5f               /* the battery when there is no plausible reading */
#define MU_VBAT_MIN 6.0f             /* a 12 V system: outside this, assume MU_V_NOM */
#define MU_VBAT_MAX 18.0f
/* The gains in duty per unit of current error, scaled by 3.75/10 when the
 * coil was measured, and by 1.8/1.35 when the unit grew to 1.8 A, so the
 * loop keeps its dynamics in amps. The integral covers the whole coil
 * spread: 1.85 ohm (2.5 cold) to 6.91 ohm (5 hot) against the 3.75
 * feedforward, at command 1.0 from 13.5 V up (+0.42 duty for the hot
 * coil). Below about 12.4 V the hot 5 ohm coil cannot reach 1.8 A at
 * all (12.4 / 6.91); the running set charges at 14.5 V. */
#define MU_KP 0.1f                   /* calibration, duty per unit of current error */
#define MU_KI 10.0f                  /* calibration, duty/(unit*s): coil tau 3 ms */
#define MU_INTEG_MAX 0.5f

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
 * duty of 1.0 -- 1.35 A in a 10 ohm coil, 8.6 A in a cold 1.85 ohm one.
 * The trip and the reset use it for one tick; the loop takes over next. */
float mu_ff(float cmd, float v_bat);

/* THE COIL'S OWN RESISTANCE, learned (decisions log 34). Feedforward alone
 * (no trusted current reading) assumed the nominal 3.75 ohm, which drives
 * the cold 2.5 ohm coil to 3.65 A at command 1.0, twice its 1.8 A. Now:
 * while ISNS_MU is trusted and above MU_R_LEARN_A, the resistance the
 * loop actually sees (duty x battery / current) is filtered into r; the
 * fallback scales its command by r / MU_R_NOM. Never learned -- production
 * has no ISNS_MU, so there the fallback IS the normal mode -- r stays
 * MU_R_NOM, as before: the rail loop around it sets the current the valve
 * needs, and only a command saturated at "closed" can overdrive a cold
 * low coil (3.65 A). Assuming MU_R_LO there instead would leave a nominal
 * coil unable ever to close the valve. Above MU_R_LEARN_A the freewheel
 * diode's drop is under 8 % of the reading. */
#define MU_R_LO 1.85f                /* 2.5 ohm at -40 C */
#define MU_R_HI 6.91f                /* 5 ohm at +125 C */
#define MU_R_LEARN_A 0.9f            /* learn only above this current */
#define MU_R_ALPHA 0.001f            /* per 1 ms: tau 1 s */
#define MU_DISTRUST_MS 10            /* an impossible reading this long: feedforward (3 coil taus) */
float mu_r_learn(float r, float duty, float v_bat, float i_meas);
float mu_fallback_cmd(float cmd, float r);

/* THE METERING SUPERVISION, one tick (decisions log 34, 41). Whether the
 * current reading is trusted -- valid, not impossible (open load or over
 * current, as diag.h judges them) for MU_DISTRUST_MS, and neither DTC
 * active -- and, while it is, the coil's resistance learned from it; when
 * it is not, the command scaled to the learned coil. duty_prev is last
 * tick's duty, the one that made this current. Returns the command for
 * mu_step; *meas is mu_step's valid. The state is the caller's: with
 * ECU_MODEL the step is model/ecu_musup.slx, which takes and returns it. */
typedef struct { float r; uint16_t bad_ms; } mu_sup_t;
void  mu_sup_reset(mu_sup_t *s);                 /* r = MU_R_NOM, nothing distrusted */
float mu_sup_step(mu_sup_t *s, float cmd, float duty_prev, float v_bat, float i_mu,
                  uint8_t i_valid, uint8_t act_open, uint8_t act_over, uint8_t *meas);
/* The duty that holds the valve closed on the learned coil, for the trip
 * and the reset: mu_ff(mu_fallback_cmd(METER_CLOSED, r), v_bat). With
 * ECU_MODEL, model/ecu_muclose.slx. */
float mu_close_duty(float r, float v_bat);

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
