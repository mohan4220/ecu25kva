/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_injdur.c
 *
 * Code generated for Simulink model 'ecu_injdur'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:47:33 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_injdur.h"
#include <math.h>
#include "rtwtypes.h"

/* Model step function */
void ecu_injdur_step(RT_MODEL_ecu_injdur_T *const ecu_injdur_M, real32_T
                     ecu_injdur_U_fuel_mg, real32_T ecu_injdur_U_rail_bar,
                     uint32_T *ecu_injdur_Y_dur_us)
{
  real32_T tmp;

  /* Switch: '<Root>/dur' incorporates:
   *  Constant: '<Root>/ZERO'
   *  Inport: '<Root>/fuel_mg'
   *  RelationalOperator: '<Root>/on'
   */
  if (ecu_injdur_U_fuel_mg > 0.0F) {
    /* DataTypeConversion: '<Root>/to_us' incorporates:
     *  Constant: '<Root>/DEAD'
     *  Constant: '<Root>/HALF'
     *  Constant: '<Root>/RAIL_MIN'
     *  Gain: '<Root>/g_k'
     *  Inport: '<Root>/rail_bar'
     *  MinMax: '<Root>/p'
     *  Product: '<Root>/q'
     *  Sqrt: '<Root>/sqrt_p'
     *  Sum: '<Root>/add_dead'
     *  Sum: '<Root>/add_half'
     */
    tmp = fmodf(truncf((ecu_injdur_U_fuel_mg / (0.00191F * sqrtf(fmaxf
      (ecu_injdur_U_rail_bar, 100.0F))) + 323.0F) + 0.5F), 4.2949673E+9F);

    /* Outport: '<Root>/dur_us' incorporates:
     *  DataTypeConversion: '<Root>/to_us'
     */
    *ecu_injdur_Y_dur_us = tmp < 0.0F ? (uint32_T)-(int32_T)(uint32_T)-tmp :
      (uint32_T)tmp;
  } else {
    /* Outport: '<Root>/dur_us' incorporates:
     *  Constant: '<Root>/NONE'
     */
    *ecu_injdur_Y_dur_us = 0U;
  }

  /* End of Switch: '<Root>/dur' */
  UNUSED_PARAMETER(ecu_injdur_M);
}

/* Model initialize function */
void ecu_injdur_initialize(RT_MODEL_ecu_injdur_T *const ecu_injdur_M, real32_T
  *ecu_injdur_U_fuel_mg, real32_T *ecu_injdur_U_rail_bar, uint32_T
  *ecu_injdur_Y_dur_us)
{
  /* Registration code */

  /* initialize error status */
  rtmSetErrorStatus(ecu_injdur_M, (NULL));

  /* external inputs */
  *ecu_injdur_U_fuel_mg = 0.0F;
  *ecu_injdur_U_rail_bar = 0.0F;

  /* external outputs */
  *ecu_injdur_Y_dur_us = 0U;
  UNUSED_PARAMETER(ecu_injdur_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
