/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_safety.c
 *
 * Code generated for Simulink model 'ecu_safety'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:47:47 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_safety.h"
#include "rtwtypes.h"

/* Model step function */
void ecu_safety_step(RT_MODEL_ecu_safety_T *const ecu_safety_M, real32_T
                     ecu_safety_U_rpm, uint8_T ecu_safety_U_crank_fault, uint8_T
                     ecu_safety_U_ignition, uint8_T ecu_safety_U_running,
                     uint8_T *ecu_safety_Y_why)
{
  /* MATLAB Function: '<Root>/decide' incorporates:
   *  Inport: '<Root>/crank_fault'
   *  Inport: '<Root>/ignition'
   *  Inport: '<Root>/rpm'
   *  Inport: '<Root>/running'
   */
  if (ecu_safety_U_rpm > 1650.0F) {
    /* Outport: '<Root>/why' */
    *ecu_safety_Y_why = 1U;
  } else if ((ecu_safety_U_running != 0) && (ecu_safety_U_crank_fault != 0)) {
    /* Outport: '<Root>/why' */
    *ecu_safety_Y_why = 2U;
  } else if (ecu_safety_U_ignition == 0) {
    /* Outport: '<Root>/why' */
    *ecu_safety_Y_why = 3U;
  } else {
    /* Outport: '<Root>/why' */
    *ecu_safety_Y_why = 0U;
  }

  /* End of MATLAB Function: '<Root>/decide' */
  UNUSED_PARAMETER(ecu_safety_M);
}

/* Model initialize function */
void ecu_safety_initialize(RT_MODEL_ecu_safety_T *const ecu_safety_M, real32_T
  *ecu_safety_U_rpm, uint8_T *ecu_safety_U_crank_fault, uint8_T
  *ecu_safety_U_ignition, uint8_T *ecu_safety_U_running, uint8_T
  *ecu_safety_Y_why)
{
  /* Registration code */

  /* initialize error status */
  rtmSetErrorStatus(ecu_safety_M, (NULL));

  /* external inputs */
  *ecu_safety_U_rpm = 0.0F;
  *ecu_safety_U_crank_fault = 0U;
  *ecu_safety_U_ignition = 0U;
  *ecu_safety_U_running = 0U;

  /* external outputs */
  *ecu_safety_Y_why = 0U;
  UNUSED_PARAMETER(ecu_safety_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
