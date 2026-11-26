/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_egrtgt.c
 *
 * Code generated for Simulink model 'ecu_egrtgt'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Thu Nov 26 09:16:20 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_egrtgt.h"
#include "rtwtypes.h"
#include "look1_iflf_binlcapw.h"
#include "ecu_egrtgt_private.h"

/* Model step function */
void ecu_egrtgt_step(RT_MODEL_ecu_egrtgt_T *const ecu_egrtgt_M, real32_T
                     ecu_egrtgt_U_fuel_mg, real32_T *ecu_egrtgt_Y_target_pct)
{
  /* Outport: '<Root>/target_pct' incorporates:
   *  Inport: '<Root>/fuel_mg'
   *  Lookup_n-D: '<Root>/table'
   */
  *ecu_egrtgt_Y_target_pct = look1_iflf_binlcapw(ecu_egrtgt_U_fuel_mg,
    rtCP_table_bp01Data, rtCP_table_tableData, 1U);
  UNUSED_PARAMETER(ecu_egrtgt_M);
}

/* Model initialize function */
void ecu_egrtgt_initialize(RT_MODEL_ecu_egrtgt_T *const ecu_egrtgt_M, real32_T
  *ecu_egrtgt_U_fuel_mg, real32_T *ecu_egrtgt_Y_target_pct)
{
  /* Registration code */

  /* initialize error status */
  rtmSetErrorStatus(ecu_egrtgt_M, (NULL));

  /* external inputs */
  *ecu_egrtgt_U_fuel_mg = 0.0F;

  /* external outputs */
  *ecu_egrtgt_Y_target_pct = 0.0F;
  UNUSED_PARAMETER(ecu_egrtgt_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
