/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_mode.c
 *
 * Code generated for Simulink model 'ecu_mode'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:47:58 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_mode.h"
#include "rtwtypes.h"
#include <string.h>

/* Named constants for Chart: '<Root>/EngineMode' */
#define ecu_mode_IN_CRANK              ((uint8_T)1U)
#define ecu_mode_IN_Engine             ((uint8_T)1U)
#define ecu_mode_IN_NO_ACTIVE_CHILD    ((uint8_T)0U)
#define ecu_mode_IN_OFF                ((uint8_T)2U)
#define ecu_mode_IN_RUN                ((uint8_T)3U)
#define ecu_mode_IN_SHUTDOWN           ((uint8_T)2U)
#define ecu_mode_IN_WAIT               ((uint8_T)4U)

/* Model step function */
void ecu_mode_step(RT_MODEL_ecu_mode_T *const ecu_mode_M, uint8_T ecu_mode_U_cmd,
                   uint8_T ecu_mode_U_phased, real32_T ecu_mode_U_rpm, uint8_T
                   *ecu_mode_Y_mode)
{
  DW_ecu_mode_T *ecu_mode_DW = ecu_mode_M->dwork;

  /* Chart: '<Root>/EngineMode' incorporates:
   *  Inport: '<Root>/cmd'
   *  Inport: '<Root>/phased'
   *  Inport: '<Root>/rpm'
   */
  if (ecu_mode_DW->is_c3_ecu_mode == ecu_mode_IN_Engine) {
    switch (ecu_mode_U_cmd) {
     case 4U:
      ecu_mode_DW->is_Engine = ecu_mode_IN_NO_ACTIVE_CHILD;
      ecu_mode_DW->is_c3_ecu_mode = ecu_mode_IN_SHUTDOWN;

      /* Outport: '<Root>/mode' */
      *ecu_mode_Y_mode = 4U;
      break;

     case 5U:
      ecu_mode_DW->is_Engine = ecu_mode_IN_OFF;

      /* Outport: '<Root>/mode' */
      *ecu_mode_Y_mode = 0U;
      break;

     default:
      switch (ecu_mode_DW->is_Engine) {
       case ecu_mode_IN_CRANK:
        /* Outport: '<Root>/mode' */
        *ecu_mode_Y_mode = 2U;
        if ((ecu_mode_U_cmd == 3) && (ecu_mode_U_phased != 0) && (ecu_mode_U_rpm
             >= 400.0F)) {
          ecu_mode_DW->is_Engine = ecu_mode_IN_RUN;

          /* Outport: '<Root>/mode' */
          *ecu_mode_Y_mode = 3U;
        }
        break;

       case ecu_mode_IN_OFF:
        /* Outport: '<Root>/mode' */
        *ecu_mode_Y_mode = 0U;
        if (ecu_mode_U_cmd == 1) {
          ecu_mode_DW->is_Engine = ecu_mode_IN_WAIT;

          /* Outport: '<Root>/mode' */
          *ecu_mode_Y_mode = 1U;
        }
        break;

       case ecu_mode_IN_RUN:
        /* Outport: '<Root>/mode' */
        *ecu_mode_Y_mode = 3U;
        break;

       default:
        /* Outport: '<Root>/mode' */
        /* case IN_WAIT: */
        *ecu_mode_Y_mode = 1U;
        if (ecu_mode_U_cmd == 2) {
          ecu_mode_DW->is_Engine = ecu_mode_IN_CRANK;

          /* Outport: '<Root>/mode' */
          *ecu_mode_Y_mode = 2U;
        }
        break;
      }
      break;
    }
  } else {
    /* Outport: '<Root>/mode' */
    /* case IN_SHUTDOWN: */
    *ecu_mode_Y_mode = 4U;
    if (ecu_mode_U_cmd == 5) {
      ecu_mode_DW->is_c3_ecu_mode = ecu_mode_IN_Engine;
      ecu_mode_DW->is_Engine = ecu_mode_IN_OFF;

      /* Outport: '<Root>/mode' */
      *ecu_mode_Y_mode = 0U;
    }
  }

  /* End of Chart: '<Root>/EngineMode' */
}

/* Model initialize function */
void ecu_mode_initialize(RT_MODEL_ecu_mode_T *const ecu_mode_M, uint8_T
  *ecu_mode_U_cmd, uint8_T *ecu_mode_U_phased, real32_T *ecu_mode_U_rpm, uint8_T
  *ecu_mode_Y_mode)
{
  DW_ecu_mode_T *ecu_mode_DW = ecu_mode_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_mode_DW, 0,
                sizeof(DW_ecu_mode_T));

  /* external inputs */
  *ecu_mode_U_cmd = 0U;
  *ecu_mode_U_phased = 0U;
  *ecu_mode_U_rpm = 0.0F;

  /* external outputs */
  *ecu_mode_Y_mode = 0U;

  /* Chart: '<Root>/EngineMode' */
  ecu_mode_DW->is_c3_ecu_mode = ecu_mode_IN_Engine;
  ecu_mode_DW->is_Engine = ecu_mode_IN_OFF;

  /* Outport: '<Root>/mode' incorporates:
   *  Chart: '<Root>/EngineMode'
   * */
  *ecu_mode_Y_mode = 0U;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
