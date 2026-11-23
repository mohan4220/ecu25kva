/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_lamps.c
 *
 * Code generated for Simulink model 'ecu_lamps'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Tue Nov 24 00:46:30 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_lamps.h"
#include "rtwtypes.h"
#include <string.h>

/* Model step function */
void ecu_lamps_step(RT_MODEL_ecu_lamps_T *const ecu_lamps_M, uint32_T
                    ecu_lamps_U_spn[16], uint8_T ecu_lamps_U_fmi[16], uint8_T
                    ecu_lamps_U_n, uint8_T *ecu_lamps_Y_lamps)
{
  int32_T i;
  int32_T last;
  uint32_T spn;

  /* MATLAB Function: '<Root>/lamps_of' incorporates:
   *  Inport: '<Root>/fmi'
   *  Inport: '<Root>/n'
   *  Inport: '<Root>/spn'
   */
  *ecu_lamps_Y_lamps = 0U;
  if (ecu_lamps_U_n <= 16) {
    last = ecu_lamps_U_n;
  } else {
    last = 16;
  }

  for (i = 0; i < last; i++) {
    spn = ecu_lamps_U_spn[i];
    if ((spn == 190U) && (ecu_lamps_U_fmi[i] == 0)) {
      *ecu_lamps_Y_lamps = (uint8_T)(*ecu_lamps_Y_lamps | 17);
    } else if (spn == 636U) {
      *ecu_lamps_Y_lamps = (uint8_T)(*ecu_lamps_Y_lamps | 17);
    } else if ((spn == 520192U) && (ecu_lamps_U_fmi[i] == 0)) {
      *ecu_lamps_Y_lamps = (uint8_T)(*ecu_lamps_Y_lamps | 17);
    } else if (spn == 110U) {
      if (ecu_lamps_U_fmi[i] == 0) {
        *ecu_lamps_Y_lamps = (uint8_T)(*ecu_lamps_Y_lamps | 17);
      } else {
        *ecu_lamps_Y_lamps = (uint8_T)(*ecu_lamps_Y_lamps | 4);
      }
    } else {
      *ecu_lamps_Y_lamps = (uint8_T)(*ecu_lamps_Y_lamps | 4);
    }
  }

  /* End of MATLAB Function: '<Root>/lamps_of' */
  UNUSED_PARAMETER(ecu_lamps_M);
}

/* Model initialize function */
void ecu_lamps_initialize(RT_MODEL_ecu_lamps_T *const ecu_lamps_M, uint32_T
  ecu_lamps_U_spn[16], uint8_T ecu_lamps_U_fmi[16], uint8_T *ecu_lamps_U_n,
  uint8_T *ecu_lamps_Y_lamps)
{
  /* Registration code */

  /* initialize error status */
  rtmSetErrorStatus(ecu_lamps_M, (NULL));

  /* external inputs */
  (void)memset(&ecu_lamps_U_spn[0], 0, sizeof(uint32_T) << 4U);
  (void)memset(&ecu_lamps_U_fmi[0], 0, sizeof(uint8_T) << 4U);
  *ecu_lamps_U_n = 0U;

  /* external outputs */
  *ecu_lamps_Y_lamps = 0U;
  UNUSED_PARAMETER(ecu_lamps_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
