/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_soi.c
 *
 * Code generated for Simulink model 'ecu_soi'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:47:23 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_soi.h"
#include "rtwtypes.h"
#include "look1_iflf_binlcapw.h"
#include "ecu_soi_private.h"

/* Model step function */
void ecu_soi_step(RT_MODEL_ecu_soi_T *const ecu_soi_M, real32_T
                  ecu_soi_U_fuel_mg, real32_T *ecu_soi_Y_soi_deg)
{
  /* Outport: '<Root>/soi_deg' incorporates:
   *  Inport: '<Root>/fuel_mg'
   *  Lookup_n-D: '<Root>/table'
   */
  *ecu_soi_Y_soi_deg = look1_iflf_binlcapw(ecu_soi_U_fuel_mg,
    rtCP_table_bp01Data, rtCP_table_tableData, 7U);
  UNUSED_PARAMETER(ecu_soi_M);
}

/* Model initialize function */
void ecu_soi_initialize(RT_MODEL_ecu_soi_T *const ecu_soi_M, real32_T
  *ecu_soi_U_fuel_mg, real32_T *ecu_soi_Y_soi_deg)
{
  /* Registration code */

  /* initialize error status */
  rtmSetErrorStatus(ecu_soi_M, (NULL));

  /* external inputs */
  *ecu_soi_U_fuel_mg = 0.0F;

  /* external outputs */
  *ecu_soi_Y_soi_deg = 0.0F;
  UNUSED_PARAMETER(ecu_soi_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
