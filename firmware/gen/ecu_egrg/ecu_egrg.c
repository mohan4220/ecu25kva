/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_egrg.c
 *
 * Code generated for Simulink model 'ecu_egrg'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:48:18 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_egrg.h"
#include "rtwtypes.h"
#include <string.h>

/* Named constants for Chart: '<Root>/EgrStallGuard' */
#define ecu_egrg_IN_COAST              ((uint8_T)1U)
#define ecu_egrg_IN_LOCKED             ((uint8_T)2U)
#define ecu_egrg_IN_NORMAL             ((uint8_T)3U)

/* Model step function */
void ecu_egrg_step(RT_MODEL_ecu_egrg_T *const ecu_egrg_M, real32_T
                   ecu_egrg_U_i_egr, uint8_T *ecu_egrg_Y_off, uint8_T
                   *ecu_egrg_Y_raise)
{
  DW_ecu_egrg_T *ecu_egrg_DW = ecu_egrg_M->dwork;
  uint32_T qY;

  /* Outport: '<Root>/raise' incorporates:
   *  Chart: '<Root>/EgrStallGuard'
   */
  *ecu_egrg_Y_raise = 0U;

  /* Chart: '<Root>/EgrStallGuard' incorporates:
   *  Inport: '<Root>/i_egr'
   */
  if (ecu_egrg_U_i_egr > 5.0F) {
    qY = ecu_egrg_DW->hot + 1U;
    if (ecu_egrg_DW->hot + 1U > 65535U) {
      qY = 65535U;
    }

    if ((uint16_T)qY <= 1500) {
      ecu_egrg_DW->hot = (uint16_T)qY;
    } else {
      ecu_egrg_DW->hot = 1500U;
    }
  } else if (ecu_egrg_DW->hot > 0) {
    qY = ecu_egrg_DW->hot -
      /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
      /*MW:OvSatOk*/ 1U;
    if (ecu_egrg_DW->hot - 1U > ecu_egrg_DW->hot) {
      qY = 0U;
    }

    ecu_egrg_DW->hot = (uint16_T)qY;
  }

  switch (ecu_egrg_DW->is_Guard) {
   case ecu_egrg_IN_COAST:
    /* Outport: '<Root>/off' */
    *ecu_egrg_Y_off = 1U;
    if (ecu_egrg_DW->cool <= 1) {
      ecu_egrg_DW->cool = 0U;
      ecu_egrg_DW->is_Guard = ecu_egrg_IN_NORMAL;

      /* Outport: '<Root>/off' */
      *ecu_egrg_Y_off = 0U;
    } else {
      qY = ecu_egrg_DW->cool -
        /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
        /*MW:OvSatOk*/ 1U;
      if (ecu_egrg_DW->cool - 1U > ecu_egrg_DW->cool) {
        qY = 0U;
      }

      ecu_egrg_DW->cool = (uint16_T)qY;
    }
    break;

   case ecu_egrg_IN_LOCKED:
    /* Outport: '<Root>/off' */
    *ecu_egrg_Y_off = 1U;
    break;

   default:
    /* Outport: '<Root>/off' */
    /* case IN_NORMAL: */
    *ecu_egrg_Y_off = 0U;
    qY = ecu_egrg_DW->stalls + 1U;
    if (ecu_egrg_DW->stalls + 1U > 255U) {
      qY = 255U;
    }

    if ((ecu_egrg_DW->hot >= 1500) && (qY >= 3U)) {
      ecu_egrg_DW->hot = 0U;
      ecu_egrg_DW->cool = 5000U;

      /* Outport: '<Root>/raise' */
      *ecu_egrg_Y_raise = 1U;
      ecu_egrg_DW->stalls = 3U;
      ecu_egrg_DW->is_Guard = ecu_egrg_IN_LOCKED;

      /* Outport: '<Root>/off' */
      *ecu_egrg_Y_off = 1U;
    } else if (ecu_egrg_DW->hot >= 1500) {
      ecu_egrg_DW->hot = 0U;
      ecu_egrg_DW->cool = 5000U;

      /* Outport: '<Root>/raise' */
      *ecu_egrg_Y_raise = 1U;
      qY = ecu_egrg_DW->stalls + 1U;
      if (ecu_egrg_DW->stalls + 1U > 255U) {
        qY = 255U;
      }

      ecu_egrg_DW->stalls = (uint8_T)qY;
      ecu_egrg_DW->is_Guard = ecu_egrg_IN_COAST;

      /* Outport: '<Root>/off' */
      *ecu_egrg_Y_off = 1U;
    }
    break;
  }
}

/* Model initialize function */
void ecu_egrg_initialize(RT_MODEL_ecu_egrg_T *const ecu_egrg_M, real32_T
  *ecu_egrg_U_i_egr, uint8_T *ecu_egrg_Y_off, uint8_T *ecu_egrg_Y_raise)
{
  DW_ecu_egrg_T *ecu_egrg_DW = ecu_egrg_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_egrg_DW, 0,
                sizeof(DW_ecu_egrg_T));

  /* external inputs */
  *ecu_egrg_U_i_egr = 0.0F;

  /* external outputs */
  *ecu_egrg_Y_off = 0U;
  *ecu_egrg_Y_raise = 0U;

  /* Chart: '<Root>/EgrStallGuard' */
  ecu_egrg_DW->hot = 0U;
  ecu_egrg_DW->cool = 0U;
  ecu_egrg_DW->stalls = 0U;

  /* Outport: '<Root>/raise' incorporates:
   *  Chart: '<Root>/EgrStallGuard'
   * */
  *ecu_egrg_Y_raise = 0U;

  /* Chart: '<Root>/EgrStallGuard' */
  ecu_egrg_DW->is_Guard = ecu_egrg_IN_NORMAL;

  /* Outport: '<Root>/off' incorporates:
   *  Chart: '<Root>/EgrStallGuard'
   * */
  *ecu_egrg_Y_off = 0U;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
