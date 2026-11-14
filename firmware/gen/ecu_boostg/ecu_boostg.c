/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_boostg.c
 *
 * Code generated for Simulink model 'ecu_boostg'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:48:07 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_boostg.h"
#include "rtwtypes.h"
#include <string.h>

/* Named constants for Chart: '<Root>/BoostGuard' */
#define ecu_boostg_IN_HIGH             ((uint8_T)1U)
#define ecu_boostg_IN_LATCHED          ((uint8_T)2U)
#define ecu_boostg_IN_OK               ((uint8_T)3U)

/* Model step function */
void ecu_boostg_step(RT_MODEL_ecu_boostg_T *const ecu_boostg_M, real32_T
                     ecu_boostg_U_v_rail, uint8_T ecu_boostg_U_shut, uint8_T
                     *ecu_boostg_Y_dis, uint8_T *ecu_boostg_Y_trip)
{
  DW_ecu_boostg_T *ecu_boostg_DW = ecu_boostg_M->dwork;
  uint32_T tmp;

  /* Outport: '<Root>/trip' incorporates:
   *  Chart: '<Root>/BoostGuard'
   */
  *ecu_boostg_Y_trip = 0U;

  /* Outport: '<Root>/dis' incorporates:
   *  Chart: '<Root>/BoostGuard'
   *  Inport: '<Root>/shut'
   */
  *ecu_boostg_Y_dis = (uint8_T)((ecu_boostg_U_shut != 0) ||
    (ecu_boostg_DW->latched != 0));

  /* Chart: '<Root>/BoostGuard' incorporates:
   *  Inport: '<Root>/v_rail'
   */
  switch (ecu_boostg_DW->is_Guard) {
   case ecu_boostg_IN_HIGH:
    if (ecu_boostg_U_v_rail <= 106.0F) {
      ecu_boostg_DW->is_Guard = ecu_boostg_IN_OK;
    } else {
      tmp = ecu_boostg_DW->cnt + 1U;
      if (ecu_boostg_DW->cnt + 1U > 65535U) {
        tmp = 65535U;
      }

      if (tmp >= 20U) {
        /* Outport: '<Root>/trip' */
        *ecu_boostg_Y_trip = 1U;
        ecu_boostg_DW->is_Guard = ecu_boostg_IN_LATCHED;
        ecu_boostg_DW->latched = 1U;

        /* Outport: '<Root>/dis' */
        *ecu_boostg_Y_dis = 1U;
      } else {
        tmp = ecu_boostg_DW->cnt + 1U;
        if (ecu_boostg_DW->cnt + 1U > 65535U) {
          tmp = 65535U;
        }

        ecu_boostg_DW->cnt = (uint16_T)tmp;
      }
    }
    break;

   case ecu_boostg_IN_LATCHED:
    break;

   default:
    /* case IN_OK: */
    if (ecu_boostg_U_v_rail > 106.0F) {
      ecu_boostg_DW->cnt = 1U;
      ecu_boostg_DW->is_Guard = ecu_boostg_IN_HIGH;
    }
    break;
  }
}

/* Model initialize function */
void ecu_boostg_initialize(RT_MODEL_ecu_boostg_T *const ecu_boostg_M, real32_T
  *ecu_boostg_U_v_rail, uint8_T *ecu_boostg_U_shut, uint8_T *ecu_boostg_Y_dis,
  uint8_T *ecu_boostg_Y_trip)
{
  DW_ecu_boostg_T *ecu_boostg_DW = ecu_boostg_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_boostg_DW, 0,
                sizeof(DW_ecu_boostg_T));

  /* external inputs */
  *ecu_boostg_U_v_rail = 0.0F;
  *ecu_boostg_U_shut = 0U;

  /* external outputs */
  *ecu_boostg_Y_dis = 0U;
  *ecu_boostg_Y_trip = 0U;

  /* Chart: '<Root>/BoostGuard' */
  ecu_boostg_DW->cnt = 0U;
  ecu_boostg_DW->latched = 0U;

  /* Outport: '<Root>/dis' incorporates:
   *  Chart: '<Root>/BoostGuard'
   * */
  *ecu_boostg_Y_dis = 0U;

  /* Outport: '<Root>/trip' incorporates:
   *  Chart: '<Root>/BoostGuard'
   * */
  *ecu_boostg_Y_trip = 0U;

  /* Chart: '<Root>/BoostGuard' */
  ecu_boostg_DW->is_Guard = ecu_boostg_IN_OK;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
