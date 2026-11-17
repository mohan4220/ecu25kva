/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_spdst.c
 *
 * Code generated for Simulink model 'ecu_spdst'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Mon Nov 16 16:27:12 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_spdst.h"
#include "rtwtypes.h"
#include <math.h>
#include <string.h>

/* Named constants for Chart: '<Root>/SpeedStates' */
#define ecu_spdst_IN_IDLE              ((uint8_T)1U)
#define ecu_spdst_IN_OFF               ((uint8_T)2U)
#define ecu_spdst_IN_OPERATING         ((uint8_T)3U)
#define ecu_spdst_IN_STEADY            ((uint8_T)4U)

/* Model step function */
void ecu_spdst_step(RT_MODEL_ecu_spdst_T *const ecu_spdst_M, real32_T
                    ecu_spdst_U_rpm, real32_T ecu_spdst_U_target, uint8_T
                    ecu_spdst_U_running, uint32_T ecu_spdst_U_idle_ms, uint8_T
                    *ecu_spdst_Y_idle, uint8_T *ecu_spdst_Y_state)
{
  DW_ecu_spdst_T *ecu_spdst_DW = ecu_spdst_M->dwork;
  real32_T abs_e;
  uint32_T qY;

  /* Abs: '<Root>/abs_e' incorporates:
   *  Inport: '<Root>/rpm'
   *  Inport: '<Root>/target'
   *  Sum: '<Root>/err'
   */
  abs_e = fabsf(ecu_spdst_U_rpm - ecu_spdst_U_target);

  /* Chart: '<Root>/SpeedStates' incorporates:
   *  Inport: '<Root>/idle_ms'
   *  Inport: '<Root>/running'
   */
  switch (ecu_spdst_DW->is_c3_ecu_spdst) {
   case ecu_spdst_IN_IDLE:
    if (ecu_spdst_U_running == 0) {
      ecu_spdst_DW->n = 0U;
      ecu_spdst_DW->is_c3_ecu_spdst = ecu_spdst_IN_OFF;

      /* Outport: '<Root>/idle' */
      *ecu_spdst_Y_idle = 0U;

      /* Outport: '<Root>/state' */
      *ecu_spdst_Y_state = 0U;
    } else {
      qY = ecu_spdst_DW->n + /*MW:OvSatOk*/ 1U;
      if (ecu_spdst_DW->n + 1U < ecu_spdst_DW->n) {
        qY = MAX_uint32_T;
      }

      if (qY >= ecu_spdst_U_idle_ms) {
        ecu_spdst_DW->n = 0U;
        ecu_spdst_DW->is_c3_ecu_spdst = ecu_spdst_IN_OPERATING;

        /* Outport: '<Root>/idle' */
        *ecu_spdst_Y_idle = 0U;

        /* Outport: '<Root>/state' */
        *ecu_spdst_Y_state = 2U;
      } else {
        qY = ecu_spdst_DW->n + /*MW:OvSatOk*/ 1U;
        if (ecu_spdst_DW->n + 1U < ecu_spdst_DW->n) {
          qY = MAX_uint32_T;
        }

        ecu_spdst_DW->n = qY;
      }
    }
    break;

   case ecu_spdst_IN_OFF:
    if ((ecu_spdst_U_running != 0) && (ecu_spdst_U_idle_ms > 0U)) {
      ecu_spdst_DW->n = 0U;
      ecu_spdst_DW->is_c3_ecu_spdst = ecu_spdst_IN_IDLE;

      /* Outport: '<Root>/idle' */
      *ecu_spdst_Y_idle = 1U;

      /* Outport: '<Root>/state' */
      *ecu_spdst_Y_state = 1U;
    } else if (ecu_spdst_U_running != 0) {
      ecu_spdst_DW->n = 0U;
      ecu_spdst_DW->is_c3_ecu_spdst = ecu_spdst_IN_OPERATING;

      /* Outport: '<Root>/idle' */
      *ecu_spdst_Y_idle = 0U;

      /* Outport: '<Root>/state' */
      *ecu_spdst_Y_state = 2U;
    }
    break;

   case ecu_spdst_IN_OPERATING:
    if (ecu_spdst_U_running == 0) {
      ecu_spdst_DW->n = 0U;
      ecu_spdst_DW->is_c3_ecu_spdst = ecu_spdst_IN_OFF;

      /* Outport: '<Root>/idle' */
      *ecu_spdst_Y_idle = 0U;

      /* Outport: '<Root>/state' */
      *ecu_spdst_Y_state = 0U;
    } else {
      qY = ecu_spdst_DW->n + /*MW:OvSatOk*/ 1U;
      if (ecu_spdst_DW->n + 1U < ecu_spdst_DW->n) {
        qY = MAX_uint32_T;
      }

      if ((abs_e <= 15.0F) && (qY >= 1000U)) {
        ecu_spdst_DW->n = 0U;
        ecu_spdst_DW->is_c3_ecu_spdst = ecu_spdst_IN_STEADY;

        /* Outport: '<Root>/idle' */
        *ecu_spdst_Y_idle = 0U;

        /* Outport: '<Root>/state' */
        *ecu_spdst_Y_state = 3U;
      } else if (abs_e <= 15.0F) {
        qY = ecu_spdst_DW->n + /*MW:OvSatOk*/ 1U;
        if (ecu_spdst_DW->n + 1U < ecu_spdst_DW->n) {
          qY = MAX_uint32_T;
        }

        ecu_spdst_DW->n = qY;
      } else {
        ecu_spdst_DW->n = 0U;
      }
    }
    break;

   default:
    /* case IN_STEADY: */
    if (ecu_spdst_U_running == 0) {
      ecu_spdst_DW->n = 0U;
      ecu_spdst_DW->is_c3_ecu_spdst = ecu_spdst_IN_OFF;

      /* Outport: '<Root>/idle' */
      *ecu_spdst_Y_idle = 0U;

      /* Outport: '<Root>/state' */
      *ecu_spdst_Y_state = 0U;
    } else if (abs_e > 30.0F) {
      ecu_spdst_DW->n = 0U;
      ecu_spdst_DW->is_c3_ecu_spdst = ecu_spdst_IN_OPERATING;

      /* Outport: '<Root>/idle' */
      *ecu_spdst_Y_idle = 0U;

      /* Outport: '<Root>/state' */
      *ecu_spdst_Y_state = 2U;
    }
    break;
  }

  /* End of Chart: '<Root>/SpeedStates' */
}

/* Model initialize function */
void ecu_spdst_initialize(RT_MODEL_ecu_spdst_T *const ecu_spdst_M, real32_T
  *ecu_spdst_U_rpm, real32_T *ecu_spdst_U_target, uint8_T *ecu_spdst_U_running,
  uint32_T *ecu_spdst_U_idle_ms, uint8_T *ecu_spdst_Y_idle, uint8_T
  *ecu_spdst_Y_state)
{
  DW_ecu_spdst_T *ecu_spdst_DW = ecu_spdst_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_spdst_DW, 0,
                sizeof(DW_ecu_spdst_T));

  /* external inputs */
  *ecu_spdst_U_rpm = 0.0F;
  *ecu_spdst_U_target = 0.0F;
  *ecu_spdst_U_running = 0U;
  *ecu_spdst_U_idle_ms = 0U;

  /* external outputs */
  *ecu_spdst_Y_idle = 0U;
  *ecu_spdst_Y_state = 0U;

  /* Chart: '<Root>/SpeedStates' */
  ecu_spdst_DW->n = 0U;
  ecu_spdst_DW->is_c3_ecu_spdst = ecu_spdst_IN_OFF;

  /* Outport: '<Root>/idle' incorporates:
   *  Chart: '<Root>/SpeedStates'
   * */
  *ecu_spdst_Y_idle = 0U;

  /* Outport: '<Root>/state' incorporates:
   *  Chart: '<Root>/SpeedStates'
   * */
  *ecu_spdst_Y_state = 0U;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
