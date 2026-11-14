/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_boostm.c
 *
 * Code generated for Simulink model 'ecu_boostm'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Sat Nov 14 17:30:09 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_boostm.h"
#include "rtwtypes.h"
#include <string.h>

/* Named constants for Chart: '<Root>/BoostWarnings' */
#define ecu_boostm_IN_CLEAR            ((uint8_T)1U)
#define ecu_boostm_IN_CLEARING         ((uint8_T)2U)
#define ecu_boostm_IN_SET              ((uint8_T)3U)
#define ecu_boostm_IN_SETTING          ((uint8_T)4U)

/* Model step function */
void ecu_boostm_step(RT_MODEL_ecu_boostm_T *const ecu_boostm_M, real32_T
                     ecu_boostm_U_v_rail, uint8_T ecu_boostm_U_fuelling, uint8_T
                     *ecu_boostm_Y_hi_raise, uint8_T *ecu_boostm_Y_hi_drop,
                     uint8_T *ecu_boostm_Y_lo_raise, uint8_T
                     *ecu_boostm_Y_lo_drop)
{
  DW_ecu_boostm_T *ecu_boostm_DW = ecu_boostm_M->dwork;
  uint32_T tmp;

  /* Chart: '<Root>/BoostWarnings' incorporates:
   *  Inport: '<Root>/fuelling'
   *  Inport: '<Root>/v_rail'
   */
  switch (ecu_boostm_DW->is_HIGH) {
   case ecu_boostm_IN_CLEAR:
    if (ecu_boostm_U_v_rail > 104.0F) {
      ecu_boostm_DW->nh = 1U;
      ecu_boostm_DW->is_HIGH = ecu_boostm_IN_SETTING;

      /* Outport: '<Root>/hi_raise' */
      *ecu_boostm_Y_hi_raise = 0U;

      /* Outport: '<Root>/hi_drop' */
      *ecu_boostm_Y_hi_drop = 0U;
    }
    break;

   case ecu_boostm_IN_CLEARING:
    if (ecu_boostm_U_v_rail > 104.0F) {
      ecu_boostm_DW->nh = 1U;
      ecu_boostm_DW->is_HIGH = ecu_boostm_IN_SETTING;

      /* Outport: '<Root>/hi_raise' */
      *ecu_boostm_Y_hi_raise = 0U;

      /* Outport: '<Root>/hi_drop' */
      *ecu_boostm_Y_hi_drop = 0U;
    } else {
      tmp = ecu_boostm_DW->nh + 1U;
      if (ecu_boostm_DW->nh + 1U > 65535U) {
        tmp = 65535U;
      }

      if (tmp >= 2000U) {
        ecu_boostm_DW->is_HIGH = ecu_boostm_IN_CLEAR;

        /* Outport: '<Root>/hi_raise' */
        *ecu_boostm_Y_hi_raise = 0U;

        /* Outport: '<Root>/hi_drop' */
        *ecu_boostm_Y_hi_drop = 1U;
      } else {
        tmp = ecu_boostm_DW->nh + 1U;
        if (ecu_boostm_DW->nh + 1U > 65535U) {
          tmp = 65535U;
        }

        ecu_boostm_DW->nh = (uint16_T)tmp;
      }
    }
    break;

   case ecu_boostm_IN_SET:
    if (ecu_boostm_U_v_rail <= 104.0F) {
      ecu_boostm_DW->nh = 1U;
      ecu_boostm_DW->is_HIGH = ecu_boostm_IN_CLEARING;

      /* Outport: '<Root>/hi_raise' */
      *ecu_boostm_Y_hi_raise = 0U;

      /* Outport: '<Root>/hi_drop' */
      *ecu_boostm_Y_hi_drop = 0U;
    }
    break;

   default:
    /* case IN_SETTING: */
    if (ecu_boostm_U_v_rail <= 104.0F) {
      ecu_boostm_DW->nh = 1U;
      ecu_boostm_DW->is_HIGH = ecu_boostm_IN_CLEARING;

      /* Outport: '<Root>/hi_raise' */
      *ecu_boostm_Y_hi_raise = 0U;

      /* Outport: '<Root>/hi_drop' */
      *ecu_boostm_Y_hi_drop = 0U;
    } else {
      tmp = ecu_boostm_DW->nh + 1U;
      if (ecu_boostm_DW->nh + 1U > 65535U) {
        tmp = 65535U;
      }

      if (tmp >= 2000U) {
        ecu_boostm_DW->is_HIGH = ecu_boostm_IN_SET;

        /* Outport: '<Root>/hi_raise' */
        *ecu_boostm_Y_hi_raise = 1U;

        /* Outport: '<Root>/hi_drop' */
        *ecu_boostm_Y_hi_drop = 0U;
      } else {
        tmp = ecu_boostm_DW->nh + 1U;
        if (ecu_boostm_DW->nh + 1U > 65535U) {
          tmp = 65535U;
        }

        ecu_boostm_DW->nh = (uint16_T)tmp;
      }
    }
    break;
  }

  switch (ecu_boostm_DW->is_LOW) {
   case ecu_boostm_IN_CLEAR:
    if ((ecu_boostm_U_fuelling != 0) && (ecu_boostm_U_v_rail > 0.0F) &&
        (ecu_boostm_U_v_rail < 80.0F)) {
      ecu_boostm_DW->nl = 1U;
      ecu_boostm_DW->is_LOW = ecu_boostm_IN_SETTING;

      /* Outport: '<Root>/lo_raise' */
      *ecu_boostm_Y_lo_raise = 0U;

      /* Outport: '<Root>/lo_drop' */
      *ecu_boostm_Y_lo_drop = 0U;
    }
    break;

   case ecu_boostm_IN_CLEARING:
    if ((ecu_boostm_U_fuelling != 0) && (ecu_boostm_U_v_rail > 0.0F) &&
        (ecu_boostm_U_v_rail < 80.0F)) {
      ecu_boostm_DW->nl = 1U;
      ecu_boostm_DW->is_LOW = ecu_boostm_IN_SETTING;

      /* Outport: '<Root>/lo_raise' */
      *ecu_boostm_Y_lo_raise = 0U;

      /* Outport: '<Root>/lo_drop' */
      *ecu_boostm_Y_lo_drop = 0U;
    } else {
      tmp = ecu_boostm_DW->nl + 1U;
      if (ecu_boostm_DW->nl + 1U > 65535U) {
        tmp = 65535U;
      }

      if (tmp >= 500U) {
        ecu_boostm_DW->is_LOW = ecu_boostm_IN_CLEAR;

        /* Outport: '<Root>/lo_raise' */
        *ecu_boostm_Y_lo_raise = 0U;

        /* Outport: '<Root>/lo_drop' */
        *ecu_boostm_Y_lo_drop = 1U;
      } else {
        tmp = ecu_boostm_DW->nl + 1U;
        if (ecu_boostm_DW->nl + 1U > 65535U) {
          tmp = 65535U;
        }

        ecu_boostm_DW->nl = (uint16_T)tmp;
      }
    }
    break;

   case ecu_boostm_IN_SET:
    if ((ecu_boostm_U_fuelling == 0) || (ecu_boostm_U_v_rail <= 0.0F) ||
        (ecu_boostm_U_v_rail >= 80.0F)) {
      ecu_boostm_DW->nl = 1U;
      ecu_boostm_DW->is_LOW = ecu_boostm_IN_CLEARING;

      /* Outport: '<Root>/lo_raise' */
      *ecu_boostm_Y_lo_raise = 0U;

      /* Outport: '<Root>/lo_drop' */
      *ecu_boostm_Y_lo_drop = 0U;
    }
    break;

   default:
    /* case IN_SETTING: */
    if ((ecu_boostm_U_fuelling == 0) || (ecu_boostm_U_v_rail <= 0.0F) ||
        (ecu_boostm_U_v_rail >= 80.0F)) {
      ecu_boostm_DW->nl = 1U;
      ecu_boostm_DW->is_LOW = ecu_boostm_IN_CLEARING;

      /* Outport: '<Root>/lo_raise' */
      *ecu_boostm_Y_lo_raise = 0U;

      /* Outport: '<Root>/lo_drop' */
      *ecu_boostm_Y_lo_drop = 0U;
    } else {
      tmp = ecu_boostm_DW->nl + 1U;
      if (ecu_boostm_DW->nl + 1U > 65535U) {
        tmp = 65535U;
      }

      if (tmp >= 500U) {
        ecu_boostm_DW->is_LOW = ecu_boostm_IN_SET;

        /* Outport: '<Root>/lo_raise' */
        *ecu_boostm_Y_lo_raise = 1U;

        /* Outport: '<Root>/lo_drop' */
        *ecu_boostm_Y_lo_drop = 0U;
      } else {
        tmp = ecu_boostm_DW->nl + 1U;
        if (ecu_boostm_DW->nl + 1U > 65535U) {
          tmp = 65535U;
        }

        ecu_boostm_DW->nl = (uint16_T)tmp;
      }
    }
    break;
  }

  /* End of Chart: '<Root>/BoostWarnings' */
}

/* Model initialize function */
void ecu_boostm_initialize(RT_MODEL_ecu_boostm_T *const ecu_boostm_M, real32_T
  *ecu_boostm_U_v_rail, uint8_T *ecu_boostm_U_fuelling, uint8_T
  *ecu_boostm_Y_hi_raise, uint8_T *ecu_boostm_Y_hi_drop, uint8_T
  *ecu_boostm_Y_lo_raise, uint8_T *ecu_boostm_Y_lo_drop)
{
  DW_ecu_boostm_T *ecu_boostm_DW = ecu_boostm_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_boostm_DW, 0,
                sizeof(DW_ecu_boostm_T));

  /* external inputs */
  *ecu_boostm_U_v_rail = 0.0F;
  *ecu_boostm_U_fuelling = 0U;

  /* external outputs */
  *ecu_boostm_Y_hi_raise = 0U;
  *ecu_boostm_Y_hi_drop = 0U;
  *ecu_boostm_Y_lo_raise = 0U;
  *ecu_boostm_Y_lo_drop = 0U;

  /* Chart: '<Root>/BoostWarnings' */
  ecu_boostm_DW->nh = 0U;
  ecu_boostm_DW->is_HIGH = ecu_boostm_IN_CLEARING;

  /* Outport: '<Root>/hi_raise' incorporates:
   *  Chart: '<Root>/BoostWarnings'
   * */
  *ecu_boostm_Y_hi_raise = 0U;

  /* Outport: '<Root>/hi_drop' incorporates:
   *  Chart: '<Root>/BoostWarnings'
   * */
  *ecu_boostm_Y_hi_drop = 0U;

  /* Chart: '<Root>/BoostWarnings' */
  ecu_boostm_DW->nl = 0U;
  ecu_boostm_DW->is_LOW = ecu_boostm_IN_CLEARING;

  /* Outport: '<Root>/lo_raise' incorporates:
   *  Chart: '<Root>/BoostWarnings'
   * */
  *ecu_boostm_Y_lo_raise = 0U;

  /* Outport: '<Root>/lo_drop' incorporates:
   *  Chart: '<Root>/BoostWarnings'
   * */
  *ecu_boostm_Y_lo_drop = 0U;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
