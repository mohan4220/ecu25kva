/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_underg.c
 *
 * Code generated for Simulink model 'ecu_underg'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:48:36 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_underg.h"
#include "rtwtypes.h"
#include <string.h>

/* Named constants for Chart: '<Root>/Underspeed' */
#define ecu_underg_IN_ARMED            ((uint8_T)1U)
#define ecu_underg_IN_DISARMED         ((uint8_T)2U)
#define ecu_underg_IN_HIGH             ((uint8_T)1U)
#define ecu_underg_IN_HIGH_COUNT       ((uint8_T)2U)
#define ecu_underg_IN_LOW              ((uint8_T)3U)
#define ecu_underg_IN_LOW_COUNT        ((uint8_T)4U)
#define ecu_underg_IN_MID              ((uint8_T)5U)
#define ecu_underg_IN_NO_ACTIVE_CHILD  ((uint8_T)0U)

/* Model step function */
void ecu_underg_step(RT_MODEL_ecu_underg_T *const ecu_underg_M, real32_T
                     ecu_underg_U_rpm, uint8_T ecu_underg_U_armed, uint8_T
                     *ecu_underg_Y_raise, uint8_T *ecu_underg_Y_drop)
{
  DW_ecu_underg_T *ecu_underg_DW = ecu_underg_M->dwork;
  uint32_T tmp;

  /* Chart: '<Root>/Underspeed' incorporates:
   *  Inport: '<Root>/armed'
   *  Inport: '<Root>/rpm'
   */
  if (ecu_underg_DW->is_c3_ecu_underg == ecu_underg_IN_ARMED) {
    if (ecu_underg_U_armed == 0) {
      ecu_underg_DW->is_ARMED = ecu_underg_IN_NO_ACTIVE_CHILD;
      ecu_underg_DW->is_c3_ecu_underg = ecu_underg_IN_DISARMED;

      /* Outport: '<Root>/raise' */
      *ecu_underg_Y_raise = 0U;

      /* Outport: '<Root>/drop' */
      *ecu_underg_Y_drop = 1U;
    } else {
      switch (ecu_underg_DW->is_ARMED) {
       case ecu_underg_IN_HIGH:
        /* Outport: '<Root>/raise' */
        *ecu_underg_Y_raise = 0U;

        /* Outport: '<Root>/drop' */
        *ecu_underg_Y_drop = 1U;
        if (ecu_underg_U_rpm < 1350.0F) {
          ecu_underg_DW->n = 1U;
          ecu_underg_DW->is_ARMED = ecu_underg_IN_LOW_COUNT;

          /* Outport: '<Root>/drop' */
          *ecu_underg_Y_drop = 0U;
        } else if (ecu_underg_U_rpm <= 1400.0F) {
          ecu_underg_DW->is_ARMED = ecu_underg_IN_MID;

          /* Outport: '<Root>/drop' */
          *ecu_underg_Y_drop = 0U;
        }
        break;

       case ecu_underg_IN_HIGH_COUNT:
        /* Outport: '<Root>/raise' */
        *ecu_underg_Y_raise = 0U;

        /* Outport: '<Root>/drop' */
        *ecu_underg_Y_drop = 0U;
        if (ecu_underg_U_rpm < 1350.0F) {
          ecu_underg_DW->n = 1U;
          ecu_underg_DW->is_ARMED = ecu_underg_IN_LOW_COUNT;
        } else if (ecu_underg_U_rpm <= 1400.0F) {
          ecu_underg_DW->is_ARMED = ecu_underg_IN_MID;
        } else {
          tmp = ecu_underg_DW->n + 1U;
          if (ecu_underg_DW->n + 1U > 65535U) {
            tmp = 65535U;
          }

          if (tmp >= 1000U) {
            ecu_underg_DW->is_ARMED = ecu_underg_IN_HIGH;

            /* Outport: '<Root>/drop' */
            *ecu_underg_Y_drop = 1U;
          } else {
            tmp = ecu_underg_DW->n + 1U;
            if (ecu_underg_DW->n + 1U > 65535U) {
              tmp = 65535U;
            }

            ecu_underg_DW->n = (uint16_T)tmp;
          }
        }
        break;

       case ecu_underg_IN_LOW:
        /* Outport: '<Root>/raise' */
        *ecu_underg_Y_raise = 1U;

        /* Outport: '<Root>/drop' */
        *ecu_underg_Y_drop = 0U;
        if (ecu_underg_U_rpm > 1400.0F) {
          ecu_underg_DW->n = 1U;
          ecu_underg_DW->is_ARMED = ecu_underg_IN_HIGH_COUNT;

          /* Outport: '<Root>/raise' */
          *ecu_underg_Y_raise = 0U;
        } else if (ecu_underg_U_rpm >= 1350.0F) {
          ecu_underg_DW->is_ARMED = ecu_underg_IN_MID;

          /* Outport: '<Root>/raise' */
          *ecu_underg_Y_raise = 0U;
        }
        break;

       case ecu_underg_IN_LOW_COUNT:
        /* Outport: '<Root>/raise' */
        *ecu_underg_Y_raise = 0U;

        /* Outport: '<Root>/drop' */
        *ecu_underg_Y_drop = 0U;
        if (ecu_underg_U_rpm > 1400.0F) {
          ecu_underg_DW->n = 1U;
          ecu_underg_DW->is_ARMED = ecu_underg_IN_HIGH_COUNT;
        } else if (ecu_underg_U_rpm >= 1350.0F) {
          ecu_underg_DW->is_ARMED = ecu_underg_IN_MID;
        } else {
          tmp = ecu_underg_DW->n + 1U;
          if (ecu_underg_DW->n + 1U > 65535U) {
            tmp = 65535U;
          }

          if (tmp >= 3000U) {
            ecu_underg_DW->is_ARMED = ecu_underg_IN_LOW;

            /* Outport: '<Root>/raise' */
            *ecu_underg_Y_raise = 1U;
          } else {
            tmp = ecu_underg_DW->n + 1U;
            if (ecu_underg_DW->n + 1U > 65535U) {
              tmp = 65535U;
            }

            ecu_underg_DW->n = (uint16_T)tmp;
          }
        }
        break;

       default:
        /* Outport: '<Root>/raise' */
        /* case IN_MID: */
        *ecu_underg_Y_raise = 0U;

        /* Outport: '<Root>/drop' */
        *ecu_underg_Y_drop = 0U;
        if (ecu_underg_U_rpm < 1350.0F) {
          ecu_underg_DW->n = 1U;
          ecu_underg_DW->is_ARMED = ecu_underg_IN_LOW_COUNT;
        } else if (ecu_underg_U_rpm > 1400.0F) {
          ecu_underg_DW->n = 1U;
          ecu_underg_DW->is_ARMED = ecu_underg_IN_HIGH_COUNT;
        }
        break;
      }
    }
  } else {
    /* Outport: '<Root>/raise' */
    /* case IN_DISARMED: */
    *ecu_underg_Y_raise = 0U;

    /* Outport: '<Root>/drop' */
    *ecu_underg_Y_drop = 1U;
    if ((ecu_underg_U_armed != 0) && (ecu_underg_U_rpm < 1350.0F)) {
      ecu_underg_DW->n = 1U;
      ecu_underg_DW->is_c3_ecu_underg = ecu_underg_IN_ARMED;
      ecu_underg_DW->is_ARMED = ecu_underg_IN_LOW_COUNT;

      /* Outport: '<Root>/drop' */
      *ecu_underg_Y_drop = 0U;
    } else if ((ecu_underg_U_armed != 0) && (ecu_underg_U_rpm > 1400.0F)) {
      ecu_underg_DW->n = 1U;
      ecu_underg_DW->is_c3_ecu_underg = ecu_underg_IN_ARMED;
      ecu_underg_DW->is_ARMED = ecu_underg_IN_HIGH_COUNT;

      /* Outport: '<Root>/drop' */
      *ecu_underg_Y_drop = 0U;
    } else if (ecu_underg_U_armed != 0) {
      ecu_underg_DW->is_c3_ecu_underg = ecu_underg_IN_ARMED;
      ecu_underg_DW->is_ARMED = ecu_underg_IN_MID;

      /* Outport: '<Root>/drop' */
      *ecu_underg_Y_drop = 0U;
    }
  }

  /* End of Chart: '<Root>/Underspeed' */
}

/* Model initialize function */
void ecu_underg_initialize(RT_MODEL_ecu_underg_T *const ecu_underg_M, real32_T
  *ecu_underg_U_rpm, uint8_T *ecu_underg_U_armed, uint8_T *ecu_underg_Y_raise,
  uint8_T *ecu_underg_Y_drop)
{
  DW_ecu_underg_T *ecu_underg_DW = ecu_underg_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_underg_DW, 0,
                sizeof(DW_ecu_underg_T));

  /* external inputs */
  *ecu_underg_U_rpm = 0.0F;
  *ecu_underg_U_armed = 0U;

  /* external outputs */
  *ecu_underg_Y_raise = 0U;
  *ecu_underg_Y_drop = 0U;

  /* SystemInitialize for Chart: '<Root>/Underspeed' */
  ecu_underg_DW->is_ARMED = ecu_underg_IN_NO_ACTIVE_CHILD;

  /* Chart: '<Root>/Underspeed' */
  ecu_underg_DW->n = 0U;
  ecu_underg_DW->is_c3_ecu_underg = ecu_underg_IN_DISARMED;

  /* Outport: '<Root>/raise' incorporates:
   *  Chart: '<Root>/Underspeed'
   * */
  *ecu_underg_Y_raise = 0U;

  /* Outport: '<Root>/drop' incorporates:
   *  Chart: '<Root>/Underspeed'
   * */
  *ecu_underg_Y_drop = 1U;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
