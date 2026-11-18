/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_deb.c
 *
 * Code generated for Simulink model 'ecu_deb'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Wed Nov 18 10:05:49 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_deb.h"
#include "rtwtypes.h"
#include <string.h>

/* Named constants for Chart: '<Root>/Debounce' */
#define ecu_deb_IN_ACTIVE              ((uint8_T)1U)
#define ecu_deb_IN_CLEAR               ((uint8_T)2U)

/* Model step function */
void ecu_deb_step(RT_MODEL_ecu_deb_T *const ecu_deb_M, uint8_T ecu_deb_U_cond,
                  uint16_T ecu_deb_U_deb_ms, uint16_T ecu_deb_U_heal_ms, uint8_T
                  *ecu_deb_Y_act)
{
  DW_ecu_deb_T *ecu_deb_DW = ecu_deb_M->dwork;
  uint32_T tmp;

  /* Chart: '<Root>/Debounce' incorporates:
   *  Inport: '<Root>/cond'
   *  Inport: '<Root>/deb_ms'
   *  Inport: '<Root>/heal_ms'
   */
  if (ecu_deb_DW->is_c3_ecu_deb == ecu_deb_IN_ACTIVE) {
    tmp = ecu_deb_DW->n + 1U;
    if (ecu_deb_DW->n + 1U > 65535U) {
      tmp = 65535U;
    }

    if ((ecu_deb_U_cond == 0) && ((int32_T)tmp >= ecu_deb_U_heal_ms)) {
      ecu_deb_DW->n = 0U;
      ecu_deb_DW->is_c3_ecu_deb = ecu_deb_IN_CLEAR;

      /* Outport: '<Root>/act' */
      *ecu_deb_Y_act = 0U;
    } else if (ecu_deb_U_cond == 0) {
      tmp = ecu_deb_DW->n + 1U;
      if (ecu_deb_DW->n + 1U > 65535U) {
        tmp = 65535U;
      }

      ecu_deb_DW->n = (uint16_T)tmp;
    } else {
      ecu_deb_DW->n = 0U;
    }
  } else {
    /* case IN_CLEAR: */
    tmp = ecu_deb_DW->n + 1U;
    if (ecu_deb_DW->n + 1U > 65535U) {
      tmp = 65535U;
    }

    if ((ecu_deb_U_cond != 0) && ((int32_T)tmp >= ecu_deb_U_deb_ms)) {
      ecu_deb_DW->n = 0U;
      ecu_deb_DW->is_c3_ecu_deb = ecu_deb_IN_ACTIVE;

      /* Outport: '<Root>/act' */
      *ecu_deb_Y_act = 1U;
    } else if (ecu_deb_U_cond != 0) {
      tmp = ecu_deb_DW->n + 1U;
      if (ecu_deb_DW->n + 1U > 65535U) {
        tmp = 65535U;
      }

      ecu_deb_DW->n = (uint16_T)tmp;
    } else {
      ecu_deb_DW->n = 0U;
    }
  }

  /* End of Chart: '<Root>/Debounce' */
}

/* Model initialize function */
void ecu_deb_initialize(RT_MODEL_ecu_deb_T *const ecu_deb_M, uint8_T
  *ecu_deb_U_cond, uint16_T *ecu_deb_U_deb_ms, uint16_T *ecu_deb_U_heal_ms,
  uint8_T *ecu_deb_Y_act)
{
  DW_ecu_deb_T *ecu_deb_DW = ecu_deb_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_deb_DW, 0,
                sizeof(DW_ecu_deb_T));

  /* external inputs */
  *ecu_deb_U_cond = 0U;
  *ecu_deb_U_deb_ms = 0U;
  *ecu_deb_U_heal_ms = 0U;

  /* external outputs */
  *ecu_deb_Y_act = 0U;

  /* Chart: '<Root>/Debounce' */
  ecu_deb_DW->n = 0U;
  ecu_deb_DW->is_c3_ecu_deb = ecu_deb_IN_CLEAR;

  /* Outport: '<Root>/act' incorporates:
   *  Chart: '<Root>/Debounce'
   * */
  *ecu_deb_Y_act = 0U;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
