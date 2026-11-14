/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_wifg.c
 *
 * Code generated for Simulink model 'ecu_wifg'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:48:27 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_wifg.h"
#include "rtwtypes.h"
#include <string.h>

/* Named constants for Chart: '<Root>/WaterInFuel' */
#define ecu_wifg_IN_DRY                ((uint8_T)1U)
#define ecu_wifg_IN_DRYING             ((uint8_T)2U)
#define ecu_wifg_IN_WET                ((uint8_T)3U)
#define ecu_wifg_IN_WETTING            ((uint8_T)4U)

/* Model step function */
void ecu_wifg_step(RT_MODEL_ecu_wifg_T *const ecu_wifg_M, uint8_T ecu_wifg_U_wif,
                   uint8_T *ecu_wifg_Y_raise, uint8_T *ecu_wifg_Y_drop)
{
  DW_ecu_wifg_T *ecu_wifg_DW = ecu_wifg_M->dwork;
  uint32_T tmp;

  /* Chart: '<Root>/WaterInFuel' incorporates:
   *  Inport: '<Root>/wif'
   */
  switch (ecu_wifg_DW->is_c3_ecu_wifg) {
   case ecu_wifg_IN_DRY:
    if (ecu_wifg_U_wif != 0) {
      ecu_wifg_DW->n = 1U;
      ecu_wifg_DW->is_c3_ecu_wifg = ecu_wifg_IN_WETTING;

      /* Outport: '<Root>/raise' */
      *ecu_wifg_Y_raise = 0U;

      /* Outport: '<Root>/drop' */
      *ecu_wifg_Y_drop = 0U;
    }
    break;

   case ecu_wifg_IN_DRYING:
    if (ecu_wifg_U_wif != 0) {
      ecu_wifg_DW->n = 1U;
      ecu_wifg_DW->is_c3_ecu_wifg = ecu_wifg_IN_WETTING;

      /* Outport: '<Root>/raise' */
      *ecu_wifg_Y_raise = 0U;

      /* Outport: '<Root>/drop' */
      *ecu_wifg_Y_drop = 0U;
    } else {
      tmp = ecu_wifg_DW->n + 1U;
      if (ecu_wifg_DW->n + 1U > 65535U) {
        tmp = 65535U;
      }

      if (tmp >= 2000U) {
        ecu_wifg_DW->is_c3_ecu_wifg = ecu_wifg_IN_DRY;

        /* Outport: '<Root>/raise' */
        *ecu_wifg_Y_raise = 0U;

        /* Outport: '<Root>/drop' */
        *ecu_wifg_Y_drop = 1U;
      } else {
        tmp = ecu_wifg_DW->n + 1U;
        if (ecu_wifg_DW->n + 1U > 65535U) {
          tmp = 65535U;
        }

        ecu_wifg_DW->n = (uint16_T)tmp;
      }
    }
    break;

   case ecu_wifg_IN_WET:
    if (ecu_wifg_U_wif == 0) {
      ecu_wifg_DW->n = 1U;
      ecu_wifg_DW->is_c3_ecu_wifg = ecu_wifg_IN_DRYING;

      /* Outport: '<Root>/raise' */
      *ecu_wifg_Y_raise = 0U;

      /* Outport: '<Root>/drop' */
      *ecu_wifg_Y_drop = 0U;
    }
    break;

   default:
    /* case IN_WETTING: */
    if (ecu_wifg_U_wif == 0) {
      ecu_wifg_DW->n = 1U;
      ecu_wifg_DW->is_c3_ecu_wifg = ecu_wifg_IN_DRYING;

      /* Outport: '<Root>/raise' */
      *ecu_wifg_Y_raise = 0U;

      /* Outport: '<Root>/drop' */
      *ecu_wifg_Y_drop = 0U;
    } else {
      tmp = ecu_wifg_DW->n + 1U;
      if (ecu_wifg_DW->n + 1U > 65535U) {
        tmp = 65535U;
      }

      if (tmp >= 2000U) {
        ecu_wifg_DW->is_c3_ecu_wifg = ecu_wifg_IN_WET;

        /* Outport: '<Root>/raise' */
        *ecu_wifg_Y_raise = 1U;

        /* Outport: '<Root>/drop' */
        *ecu_wifg_Y_drop = 0U;
      } else {
        tmp = ecu_wifg_DW->n + 1U;
        if (ecu_wifg_DW->n + 1U > 65535U) {
          tmp = 65535U;
        }

        ecu_wifg_DW->n = (uint16_T)tmp;
      }
    }
    break;
  }

  /* End of Chart: '<Root>/WaterInFuel' */
}

/* Model initialize function */
void ecu_wifg_initialize(RT_MODEL_ecu_wifg_T *const ecu_wifg_M, uint8_T
  *ecu_wifg_U_wif, uint8_T *ecu_wifg_Y_raise, uint8_T *ecu_wifg_Y_drop)
{
  DW_ecu_wifg_T *ecu_wifg_DW = ecu_wifg_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_wifg_DW, 0,
                sizeof(DW_ecu_wifg_T));

  /* external inputs */
  *ecu_wifg_U_wif = 0U;

  /* external outputs */
  *ecu_wifg_Y_raise = 0U;
  *ecu_wifg_Y_drop = 0U;

  /* Chart: '<Root>/WaterInFuel' */
  ecu_wifg_DW->n = 0U;
  ecu_wifg_DW->is_c3_ecu_wifg = ecu_wifg_IN_DRYING;

  /* Outport: '<Root>/raise' incorporates:
   *  Chart: '<Root>/WaterInFuel'
   * */
  *ecu_wifg_Y_raise = 0U;

  /* Outport: '<Root>/drop' incorporates:
   *  Chart: '<Root>/WaterInFuel'
   * */
  *ecu_wifg_Y_drop = 0U;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
