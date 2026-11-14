/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_rail.c
 *
 * Code generated for Simulink model 'ecu_rail'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:47:06 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_rail.h"
#include "rtwtypes.h"
#include <string.h>

/* Model step function */
void ecu_rail_step(RT_MODEL_ecu_rail_T *const ecu_rail_M, real32_T
                   ecu_rail_U_set_bar, real32_T ecu_rail_U_rail_bar, uint8_T
                   ecu_rail_U_rst, real32_T *ecu_rail_Y_duty)
{
  DW_ecu_rail_T *ecu_rail_DW = ecu_rail_M->dwork;
  real32_T rtb_pi_add;

  /* Sum: '<Root>/err' incorporates:
   *  Inport: '<Root>/rail_bar'
   *  Inport: '<Root>/set_bar'
   */
  rtb_pi_add = ecu_rail_U_rail_bar - ecu_rail_U_set_bar;

  /* Switch: '<Root>/integ_prev' incorporates:
   *  Constant: '<Root>/ZERO'
   *  Gain: '<Root>/g_dt'
   *  Gain: '<Root>/g_ki'
   *  Inport: '<Root>/rst'
   *  Sum: '<Root>/integ_add'
   */
  if (ecu_rail_U_rst != 0) {
    ecu_rail_DW->integ_z_DSTATE = 0.0F;
  }

  ecu_rail_DW->integ_z_DSTATE += 0.01F * rtb_pi_add * 0.001F;

  /* Saturate: '<Root>/integ_sat' */
  if (ecu_rail_DW->integ_z_DSTATE > 1.0F) {
    /* Switch: '<Root>/integ_prev' */
    ecu_rail_DW->integ_z_DSTATE = 1.0F;
  } else if (ecu_rail_DW->integ_z_DSTATE < 0.0F) {
    /* Switch: '<Root>/integ_prev' */
    ecu_rail_DW->integ_z_DSTATE = 0.0F;
  }

  /* End of Saturate: '<Root>/integ_sat' */

  /* Sum: '<Root>/pi_add' incorporates:
   *  Gain: '<Root>/g_kp'
   *  UnitDelay: '<Root>/integ_z'
   */
  *ecu_rail_Y_duty = 0.002F * rtb_pi_add + ecu_rail_DW->integ_z_DSTATE;

  /* Saturate: '<Root>/duty_sat' */
  if (*ecu_rail_Y_duty > 1.0F) {
    /* Sum: '<Root>/pi_add' incorporates:
     *  Outport: '<Root>/duty'
     */
    *ecu_rail_Y_duty = 1.0F;
  } else if (*ecu_rail_Y_duty < 0.0F) {
    /* Sum: '<Root>/pi_add' incorporates:
     *  Outport: '<Root>/duty'
     */
    *ecu_rail_Y_duty = 0.0F;
  }

  /* End of Saturate: '<Root>/duty_sat' */
}

/* Model initialize function */
void ecu_rail_initialize(RT_MODEL_ecu_rail_T *const ecu_rail_M, real32_T
  *ecu_rail_U_set_bar, real32_T *ecu_rail_U_rail_bar, uint8_T *ecu_rail_U_rst,
  real32_T *ecu_rail_Y_duty)
{
  DW_ecu_rail_T *ecu_rail_DW = ecu_rail_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_rail_DW, 0,
                sizeof(DW_ecu_rail_T));

  /* external inputs */
  *ecu_rail_U_set_bar = 0.0F;
  *ecu_rail_U_rail_bar = 0.0F;
  *ecu_rail_U_rst = 0U;

  /* external outputs */
  *ecu_rail_Y_duty = 0.0F;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
