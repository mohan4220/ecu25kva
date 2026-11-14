/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_railset.c
 *
 * Code generated for Simulink model 'ecu_railset'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:47:14 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_railset.h"
#include "rtwtypes.h"
#include "look1_iflf_binlcapw.h"
#include "ecu_railset_private.h"

/* Model step function */
void ecu_railset_step(RT_MODEL_ecu_railset_T *const ecu_railset_M, real32_T
                      ecu_railset_U_fuel_mg, real32_T *ecu_railset_Y_set_bar)
{
  /* Outport: '<Root>/set_bar' incorporates:
   *  Inport: '<Root>/fuel_mg'
   *  Lookup_n-D: '<Root>/table'
   */
  *ecu_railset_Y_set_bar = look1_iflf_binlcapw(ecu_railset_U_fuel_mg,
    rtCP_table_bp01Data, rtCP_table_tableData, 9U);
  UNUSED_PARAMETER(ecu_railset_M);
}

/* Model initialize function */
void ecu_railset_initialize(RT_MODEL_ecu_railset_T *const ecu_railset_M,
  real32_T *ecu_railset_U_fuel_mg, real32_T *ecu_railset_Y_set_bar)
{
  /* Registration code */

  /* initialize error status */
  rtmSetErrorStatus(ecu_railset_M, (NULL));

  /* external inputs */
  *ecu_railset_U_fuel_mg = 0.0F;

  /* external outputs */
  *ecu_railset_Y_set_bar = 0.0F;
  UNUSED_PARAMETER(ecu_railset_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
