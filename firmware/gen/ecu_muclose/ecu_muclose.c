/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_muclose.c
 *
 * Code generated for Simulink model 'ecu_muclose'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Tue Nov 24 00:40:06 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_muclose.h"
#include "rtwtypes.h"

/* Model step function */
void ecu_muclose_step(RT_MODEL_ecu_muclose_T *const ecu_muclose_M, real32_T
                      ecu_muclose_U_r, real32_T ecu_muclose_U_v_bat, real32_T
                      *ecu_muclose_Y_duty)
{
  real32_T tmp;
  real32_T x;

  /* MATLAB Function: '<Root>/close' incorporates:
   *  Inport: '<Root>/r'
   *  Inport: '<Root>/v_bat'
   */
  x = ecu_muclose_U_r;
  if (ecu_muclose_U_r < 1.85F) {
    x = 1.85F;
  } else if (ecu_muclose_U_r > 6.91F) {
    x = 6.91F;
  }

  if ((ecu_muclose_U_v_bat >= 6.0F) && (ecu_muclose_U_v_bat <= 18.0F)) {
    tmp = ecu_muclose_U_v_bat;
  } else {
    tmp = 13.5F;
  }

  *ecu_muclose_Y_duty = x / 3.75F * (6.75F / tmp);
  if (*ecu_muclose_Y_duty < 0.0F) {
    *ecu_muclose_Y_duty = 0.0F;
  } else if (*ecu_muclose_Y_duty > 1.0F) {
    *ecu_muclose_Y_duty = 1.0F;
  }

  /* End of MATLAB Function: '<Root>/close' */
  UNUSED_PARAMETER(ecu_muclose_M);
}

/* Model initialize function */
void ecu_muclose_initialize(RT_MODEL_ecu_muclose_T *const ecu_muclose_M,
  real32_T *ecu_muclose_U_r, real32_T *ecu_muclose_U_v_bat, real32_T
  *ecu_muclose_Y_duty)
{
  /* Registration code */

  /* initialize error status */
  rtmSetErrorStatus(ecu_muclose_M, (NULL));

  /* external inputs */
  *ecu_muclose_U_r = 0.0F;
  *ecu_muclose_U_v_bat = 0.0F;

  /* external outputs */
  *ecu_muclose_Y_duty = 0.0F;
  UNUSED_PARAMETER(ecu_muclose_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
