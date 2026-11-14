/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_gov.c
 *
 * Code generated for Simulink model 'ecu_gov'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:46:47 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_gov.h"
#include <math.h>
#include "rtwtypes.h"
#include <string.h>

/* Model step function */
void ecu_gov_step(RT_MODEL_ecu_gov_T *const ecu_gov_M, real32_T ecu_gov_U_rpm,
                  uint8_T ecu_gov_U_droop, uint8_T ecu_gov_U_rst, real32_T
                  ecu_gov_U_fuel0, real32_T ecu_gov_U_rpm0, real32_T
                  *ecu_gov_Y_fuel, real32_T *ecu_gov_Y_set)
{
  DW_ecu_gov_T *ecu_gov_DW = ecu_gov_M->dwork;
  real32_T rtb_integ_add;
  real32_T rtb_pi_add;

  /* Switch: '<Root>/tgt' incorporates:
   *  Constant: '<Root>/ONE'
   *  Constant: '<Root>/RATED'
   *  Constant: '<Root>/SET'
   *  Gain: '<Root>/g_droop'
   *  Gain: '<Root>/g_set'
   *  Inport: '<Root>/droop'
   *  Product: '<Root>/div_rated'
   *  Sum: '<Root>/one_minus'
   *  Switch: '<Root>/fuel_prev'
   */
  if (ecu_gov_U_droop != 0) {
    /* Switch: '<Root>/fuel_prev' incorporates:
     *  Inport: '<Root>/fuel0'
     *  Inport: '<Root>/rst'
     */
    if (ecu_gov_U_rst != 0) {
      *ecu_gov_Y_fuel = ecu_gov_U_fuel0;
    }

    rtb_integ_add = (1.0F - 0.04F * *ecu_gov_Y_fuel / 34.0F) * 1500.0F;
  } else {
    rtb_integ_add = 1500.0F;
  }

  /* End of Switch: '<Root>/tgt' */

  /* Switch: '<Root>/set_prev' incorporates:
   *  Constant: '<Root>/SET'
   *  Inport: '<Root>/rpm0'
   *  Inport: '<Root>/rst'
   *  MinMax: '<Root>/set_init'
   *  UnitDelay: '<Root>/set_z'
   */
  if (ecu_gov_U_rst != 0) {
    rtb_pi_add = fminf(ecu_gov_U_rpm0, 1500.0F);
  } else {
    rtb_pi_add = *ecu_gov_Y_set;
  }

  /* End of Switch: '<Root>/set_prev' */

  /* Saturate: '<Root>/set_sat' incorporates:
   *  Constant: '<Root>/RAMP_DT'
   *  Sum: '<Root>/set_add'
   */
  if (rtb_pi_add + 0.5F > 1500.0F) {
    *ecu_gov_Y_set = 1500.0F;
  } else if (rtb_pi_add + 0.5F < 0.0F) {
    *ecu_gov_Y_set = 0.0F;
  } else {
    *ecu_gov_Y_set = rtb_pi_add + 0.5F;
  }

  /* End of Saturate: '<Root>/set_sat' */

  /* Sum: '<Root>/err' incorporates:
   *  Inport: '<Root>/rpm'
   *  MinMax: '<Root>/sp'
   *  UnitDelay: '<Root>/set_z'
   */
  rtb_pi_add = fminf(*ecu_gov_Y_set, rtb_integ_add) - ecu_gov_U_rpm;

  /* Switch: '<Root>/integ_prev' incorporates:
   *  Gain: '<Root>/g_dt'
   *  Gain: '<Root>/g_ki'
   *  Inport: '<Root>/fuel0'
   *  Inport: '<Root>/rst'
   *  Sum: '<Root>/integ_add'
   */
  if (ecu_gov_U_rst != 0) {
    ecu_gov_DW->integ_z_DSTATE = ecu_gov_U_fuel0;
  }

  ecu_gov_DW->integ_z_DSTATE += 2.0F * rtb_pi_add * 0.001F;

  /* Saturate: '<Root>/integ_sat' */
  if (ecu_gov_DW->integ_z_DSTATE > 45.0F) {
    /* Switch: '<Root>/integ_prev' */
    ecu_gov_DW->integ_z_DSTATE = 45.0F;
  } else if (ecu_gov_DW->integ_z_DSTATE < 0.0F) {
    /* Switch: '<Root>/integ_prev' */
    ecu_gov_DW->integ_z_DSTATE = 0.0F;
  }

  /* End of Saturate: '<Root>/integ_sat' */

  /* Switch: '<Root>/fuel_prev' incorporates:
   *  Gain: '<Root>/g_kp'
   *  Sum: '<Root>/pi_add'
   *  UnitDelay: '<Root>/integ_z'
   */
  *ecu_gov_Y_fuel = 0.5F * rtb_pi_add + ecu_gov_DW->integ_z_DSTATE;

  /* Saturate: '<Root>/fuel_sat' */
  if (*ecu_gov_Y_fuel > 45.0F) {
    /* Switch: '<Root>/fuel_prev' */
    *ecu_gov_Y_fuel = 45.0F;
  } else if (*ecu_gov_Y_fuel < 0.0F) {
    /* Switch: '<Root>/fuel_prev' */
    *ecu_gov_Y_fuel = 0.0F;
  }

  /* End of Saturate: '<Root>/fuel_sat' */
}

/* Model initialize function */
void ecu_gov_initialize(RT_MODEL_ecu_gov_T *const ecu_gov_M, real32_T
  *ecu_gov_U_rpm, uint8_T *ecu_gov_U_droop, uint8_T *ecu_gov_U_rst, real32_T
  *ecu_gov_U_fuel0, real32_T *ecu_gov_U_rpm0, real32_T *ecu_gov_Y_fuel, real32_T
  *ecu_gov_Y_set)
{
  DW_ecu_gov_T *ecu_gov_DW = ecu_gov_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_gov_DW, 0,
                sizeof(DW_ecu_gov_T));

  /* external inputs */
  *ecu_gov_U_rpm = 0.0F;
  *ecu_gov_U_droop = 0U;
  *ecu_gov_U_rst = 0U;
  *ecu_gov_U_fuel0 = 0.0F;
  *ecu_gov_U_rpm0 = 0.0F;

  /* external outputs */
  *ecu_gov_Y_fuel = 0.0F;
  *ecu_gov_Y_set = 0.0F;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
