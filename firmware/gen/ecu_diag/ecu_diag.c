/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_diag.c
 *
 * Code generated for Simulink model 'ecu_diag'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Mon Nov 23 23:37:38 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_diag.h"
#include <math.h>
#include "rtwtypes.h"
#include <string.h>

/* Model step function */
void ecu_diag_step(RT_MODEL_ecu_diag_T *const ecu_diag_M, uint8_T
                   ecu_diag_U_running, uint8_T ecu_diag_U_ign_on, uint8_T
                   ecu_diag_U_stopped, real32_T ecu_diag_U_rpm, real32_T
                   ecu_diag_U_v_bat, real32_T ecu_diag_U_egr_duty, real32_T
                   ecu_diag_U_i_egr_f, real32_T ecu_diag_U_egr_pos, uint8_T
                   ecu_diag_U_egr_pos_ok, uint8_T ecu_diag_U_egr_off, real32_T
                   ecu_diag_U_mu_duty, real32_T ecu_diag_U_i_mu, uint8_T
                   ecu_diag_U_i_mu_valid, real32_T ecu_diag_U_rail_set, real32_T
                   ecu_diag_U_rail_bar, uint8_T ecu_diag_U_rail_ok, real32_T
                   ecu_diag_U_oil_kpa, uint8_T ecu_diag_U_oil_ok, uint8_T
                   ecu_diag_U_bat_high_act, uint8_T ecu_diag_U_bat_low_act,
                   real32_T ecu_diag_U_clt_c, uint8_T ecu_diag_U_clt_ok, uint8_T
                   ecu_diag_U_clt_low, uint8_T ecu_diag_U_clt_warn_act, uint8_T
                   ecu_diag_U_clt_stop_act, uint8_T ecu_diag_Y_c[14])
{
  int32_T tmp;
  real32_T d;
  boolean_T bat_known;
  boolean_T egr;

  /* MATLAB Function: '<Root>/cond' incorporates:
   *  Inport: '<Root>/bat_high_act'
   *  Inport: '<Root>/bat_low_act'
   *  Inport: '<Root>/clt_c'
   *  Inport: '<Root>/clt_low'
   *  Inport: '<Root>/clt_ok'
   *  Inport: '<Root>/clt_stop_act'
   *  Inport: '<Root>/clt_warn_act'
   *  Inport: '<Root>/egr_duty'
   *  Inport: '<Root>/egr_off'
   *  Inport: '<Root>/egr_pos'
   *  Inport: '<Root>/egr_pos_ok'
   *  Inport: '<Root>/i_egr_f'
   *  Inport: '<Root>/i_mu'
   *  Inport: '<Root>/i_mu_valid'
   *  Inport: '<Root>/ign_on'
   *  Inport: '<Root>/mu_duty'
   *  Inport: '<Root>/oil_kpa'
   *  Inport: '<Root>/oil_ok'
   *  Inport: '<Root>/rail_bar'
   *  Inport: '<Root>/rail_ok'
   *  Inport: '<Root>/rail_set'
   *  Inport: '<Root>/rpm'
   *  Inport: '<Root>/running'
   *  Inport: '<Root>/stopped'
   *  Inport: '<Root>/v_bat'
   *  Outport: '<Root>/c'
   */
  bat_known = (ecu_diag_U_v_bat >= 1.0F);
  egr = ((ecu_diag_U_running != 0) && (ecu_diag_U_egr_off == 0) && (!bat_known ||
          ((ecu_diag_U_v_bat >= 10.0F) && (ecu_diag_U_v_bat <= 15.0F))));
  d = fabsf(ecu_diag_U_egr_duty);
  ecu_diag_Y_c[0] = (uint8_T)(egr && (d > 0.2F) && (ecu_diag_U_i_egr_f <= 0.1F));
  egr = (egr && (ecu_diag_U_egr_pos_ok != 0));
  ecu_diag_Y_c[1] = (uint8_T)(egr && (d < 0.05F) && (ecu_diag_U_egr_pos > 35.0F));
  ecu_diag_Y_c[2] = (uint8_T)(egr && (ecu_diag_U_egr_duty >= 0.9F) &&
    (ecu_diag_U_egr_pos < 35.0F));
  ecu_diag_Y_c[3] = (uint8_T)((ecu_diag_U_i_mu_valid != 0) &&
    ((ecu_diag_U_mu_duty * ecu_diag_U_v_bat / 6.91F > 0.25F) && (ecu_diag_U_i_mu
    < 0.05F)));
  ecu_diag_Y_c[4] = (uint8_T)((ecu_diag_U_i_mu_valid != 0) && (ecu_diag_U_i_mu >
    3.0F));
  d = fabsf(ecu_diag_U_rail_set - ecu_diag_U_rail_bar);
  ecu_diag_Y_c[5] = (uint8_T)((ecu_diag_U_running != 0) && (ecu_diag_U_rail_ok
    != 0) && (d > 150.0F) && (d > 0.25F * ecu_diag_U_rail_set));
  ecu_diag_Y_c[6] = (uint8_T)((ecu_diag_U_running != 0) && (ecu_diag_U_rpm >
    1590.0F));
  egr = ((ecu_diag_U_ign_on != 0) && (ecu_diag_U_stopped != 0) &&
         (ecu_diag_U_oil_ok != 0));
  ecu_diag_Y_c[7] = (uint8_T)(egr && (ecu_diag_U_oil_kpa > 200.0F));
  ecu_diag_Y_c[8] = (uint8_T)(egr && (ecu_diag_U_oil_kpa > 100.0F) &&
    (ecu_diag_U_oil_kpa <= 200.0F));
  if (ecu_diag_U_bat_high_act != 0) {
    d = 14.5F;
  } else {
    d = 15.0F;
  }

  ecu_diag_Y_c[9] = (uint8_T)((ecu_diag_U_ign_on != 0) && bat_known &&
    (ecu_diag_U_v_bat > d));
  if (ecu_diag_U_bat_low_act != 0) {
    d = 10.0F;
  } else {
    d = 9.5F;
  }

  ecu_diag_Y_c[10] = (uint8_T)((ecu_diag_U_running != 0) && bat_known &&
    (ecu_diag_U_v_bat < d));
  if (ecu_diag_U_clt_warn_act != 0) {
    tmp = 98;
  } else {
    tmp = 100;
  }

  egr = ((ecu_diag_U_ign_on != 0) && (ecu_diag_U_clt_ok != 0));
  ecu_diag_Y_c[11] = (uint8_T)(egr && (ecu_diag_U_clt_c > tmp));
  if (ecu_diag_U_clt_stop_act != 0) {
    tmp = 102;
  } else {
    tmp = 104;
  }

  ecu_diag_Y_c[12] = (uint8_T)(egr && (ecu_diag_U_clt_c > tmp));
  ecu_diag_Y_c[13] = (uint8_T)((ecu_diag_U_ign_on != 0) && (ecu_diag_U_clt_low
    != 0));

  /* End of MATLAB Function: '<Root>/cond' */
  UNUSED_PARAMETER(ecu_diag_M);
}

/* Model initialize function */
void ecu_diag_initialize(RT_MODEL_ecu_diag_T *const ecu_diag_M, uint8_T
  *ecu_diag_U_running, uint8_T *ecu_diag_U_ign_on, uint8_T *ecu_diag_U_stopped,
  real32_T *ecu_diag_U_rpm, real32_T *ecu_diag_U_v_bat, real32_T
  *ecu_diag_U_egr_duty, real32_T *ecu_diag_U_i_egr_f, real32_T
  *ecu_diag_U_egr_pos, uint8_T *ecu_diag_U_egr_pos_ok, uint8_T
  *ecu_diag_U_egr_off, real32_T *ecu_diag_U_mu_duty, real32_T *ecu_diag_U_i_mu,
  uint8_T *ecu_diag_U_i_mu_valid, real32_T *ecu_diag_U_rail_set, real32_T
  *ecu_diag_U_rail_bar, uint8_T *ecu_diag_U_rail_ok, real32_T
  *ecu_diag_U_oil_kpa, uint8_T *ecu_diag_U_oil_ok, uint8_T
  *ecu_diag_U_bat_high_act, uint8_T *ecu_diag_U_bat_low_act, real32_T
  *ecu_diag_U_clt_c, uint8_T *ecu_diag_U_clt_ok, uint8_T *ecu_diag_U_clt_low,
  uint8_T *ecu_diag_U_clt_warn_act, uint8_T *ecu_diag_U_clt_stop_act, uint8_T
  ecu_diag_Y_c[14])
{
  /* Registration code */

  /* initialize error status */
  rtmSetErrorStatus(ecu_diag_M, (NULL));

  /* external inputs */
  *ecu_diag_U_running = 0U;
  *ecu_diag_U_ign_on = 0U;
  *ecu_diag_U_stopped = 0U;
  *ecu_diag_U_rpm = 0.0F;
  *ecu_diag_U_v_bat = 0.0F;
  *ecu_diag_U_egr_duty = 0.0F;
  *ecu_diag_U_i_egr_f = 0.0F;
  *ecu_diag_U_egr_pos = 0.0F;
  *ecu_diag_U_egr_pos_ok = 0U;
  *ecu_diag_U_egr_off = 0U;
  *ecu_diag_U_mu_duty = 0.0F;
  *ecu_diag_U_i_mu = 0.0F;
  *ecu_diag_U_i_mu_valid = 0U;
  *ecu_diag_U_rail_set = 0.0F;
  *ecu_diag_U_rail_bar = 0.0F;
  *ecu_diag_U_rail_ok = 0U;
  *ecu_diag_U_oil_kpa = 0.0F;
  *ecu_diag_U_oil_ok = 0U;
  *ecu_diag_U_bat_high_act = 0U;
  *ecu_diag_U_bat_low_act = 0U;
  *ecu_diag_U_clt_c = 0.0F;
  *ecu_diag_U_clt_ok = 0U;
  *ecu_diag_U_clt_low = 0U;
  *ecu_diag_U_clt_warn_act = 0U;
  *ecu_diag_U_clt_stop_act = 0U;

  /* external outputs */
  (void)memset(&ecu_diag_Y_c[0], 0, 14U * sizeof(uint8_T));
  UNUSED_PARAMETER(ecu_diag_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
