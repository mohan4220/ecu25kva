/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_relay.c
 *
 * Code generated for Simulink model 'ecu_relay'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:48:46 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_relay.h"
#include "rtwtypes.h"
#include <string.h>

/* Named constants for Chart: '<Root>/MainRelay' */
#define ecu_relay_IN_AFTER_RUN         ((uint8_T)1U)
#define ecu_relay_IN_HELD              ((uint8_T)2U)
#define ecu_relay_IN_OFF               ((uint8_T)3U)

/* Model step function */
void ecu_relay_step(RT_MODEL_ecu_relay_T *const ecu_relay_M, uint8_T
                    ecu_relay_U_ignition, uint8_T ecu_relay_U_stopped, uint8_T
                    ecu_relay_U_written, uint8_T *ecu_relay_Y_relay, uint8_T
                    *ecu_relay_Y_afterrun, uint8_T *ecu_relay_Y_save)
{
  DW_ecu_relay_T *ecu_relay_DW = ecu_relay_M->dwork;
  uint32_T tmp;

  /* Outport: '<Root>/save' incorporates:
   *  Chart: '<Root>/MainRelay'
   */
  *ecu_relay_Y_save = 0U;

  /* Chart: '<Root>/MainRelay' incorporates:
   *  Inport: '<Root>/ignition'
   *  Inport: '<Root>/stopped'
   *  Inport: '<Root>/written'
   */
  switch (ecu_relay_DW->is_Relay) {
   case ecu_relay_IN_AFTER_RUN:
    /* Outport: '<Root>/relay' */
    *ecu_relay_Y_relay = 1U;

    /* Outport: '<Root>/afterrun' */
    *ecu_relay_Y_afterrun = 1U;
    if (ecu_relay_U_ignition != 0) {
      ecu_relay_DW->ms = 0U;
      ecu_relay_DW->is_Relay = ecu_relay_IN_HELD;

      /* Outport: '<Root>/afterrun' */
      *ecu_relay_Y_afterrun = 0U;
    } else {
      tmp = ecu_relay_DW->ms + 1U;
      if (ecu_relay_DW->ms + 1U > 65535U) {
        tmp = 65535U;
      }

      if (((ecu_relay_U_stopped != 0) && (ecu_relay_U_written != 0)) || (tmp >=
           60000U)) {
        ecu_relay_DW->is_Relay = ecu_relay_IN_OFF;

        /* Outport: '<Root>/relay' */
        *ecu_relay_Y_relay = 0U;

        /* Outport: '<Root>/afterrun' */
        *ecu_relay_Y_afterrun = 0U;
      } else {
        tmp = ecu_relay_DW->ms + 1U;
        if (ecu_relay_DW->ms + 1U > 65535U) {
          tmp = 65535U;
        }

        if ((uint16_T)tmp <= 60000) {
          ecu_relay_DW->ms = (uint16_T)tmp;
        } else {
          ecu_relay_DW->ms = 60000U;
        }
      }
    }
    break;

   case ecu_relay_IN_HELD:
    /* Outport: '<Root>/relay' */
    *ecu_relay_Y_relay = 1U;

    /* Outport: '<Root>/afterrun' */
    *ecu_relay_Y_afterrun = 0U;
    if (ecu_relay_U_ignition == 0) {
      /* Outport: '<Root>/save' */
      *ecu_relay_Y_save = 1U;
      ecu_relay_DW->ms = 1U;
      ecu_relay_DW->is_Relay = ecu_relay_IN_AFTER_RUN;

      /* Outport: '<Root>/afterrun' */
      *ecu_relay_Y_afterrun = 1U;
    }
    break;

   default:
    /* Outport: '<Root>/relay' */
    /* case IN_OFF: */
    *ecu_relay_Y_relay = 0U;

    /* Outport: '<Root>/afterrun' */
    *ecu_relay_Y_afterrun = 0U;
    if (ecu_relay_U_ignition != 0) {
      ecu_relay_DW->is_Relay = ecu_relay_IN_HELD;

      /* Outport: '<Root>/relay' */
      *ecu_relay_Y_relay = 1U;
    }
    break;
  }
}

/* Model initialize function */
void ecu_relay_initialize(RT_MODEL_ecu_relay_T *const ecu_relay_M, uint8_T
  *ecu_relay_U_ignition, uint8_T *ecu_relay_U_stopped, uint8_T
  *ecu_relay_U_written, uint8_T *ecu_relay_Y_relay, uint8_T
  *ecu_relay_Y_afterrun, uint8_T *ecu_relay_Y_save)
{
  DW_ecu_relay_T *ecu_relay_DW = ecu_relay_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_relay_DW, 0,
                sizeof(DW_ecu_relay_T));

  /* external inputs */
  *ecu_relay_U_ignition = 0U;
  *ecu_relay_U_stopped = 0U;
  *ecu_relay_U_written = 0U;

  /* external outputs */
  *ecu_relay_Y_relay = 0U;
  *ecu_relay_Y_afterrun = 0U;
  *ecu_relay_Y_save = 0U;

  /* Chart: '<Root>/MainRelay' */
  ecu_relay_DW->ms = 0U;

  /* Outport: '<Root>/save' incorporates:
   *  Chart: '<Root>/MainRelay'
   * */
  *ecu_relay_Y_save = 0U;

  /* Chart: '<Root>/MainRelay' */
  ecu_relay_DW->is_Relay = ecu_relay_IN_OFF;

  /* Outport: '<Root>/relay' incorporates:
   *  Chart: '<Root>/MainRelay'
   * */
  *ecu_relay_Y_relay = 0U;

  /* Outport: '<Root>/afterrun' incorporates:
   *  Chart: '<Root>/MainRelay'
   * */
  *ecu_relay_Y_afterrun = 0U;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
