/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_crankrd.c
 *
 * Code generated for Simulink model 'ecu_crankrd'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Tue Nov 24 00:55:28 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_crankrd.h"
#include "rtwtypes.h"
#include <string.h>

/* Model step function */
void ecu_crankrd_step(RT_MODEL_ecu_crankrd_T *const ecu_crankrd_M, uint32_T
                      ecu_crankrd_U_a[8], uint8_T ecu_crankrd_U_b[33], real32_T *
                      ecu_crankrd_Y_rpm, real32_T *ecu_crankrd_Y_angle, real32_T
                      *ecu_crankrd_Y_next_angle, real32_T
                      *ecu_crankrd_Y_us_per_deg)
{
  int32_T i;
  uint32_T deg;
  uint32_T qY;
  uint32_T us;

  /* MATLAB Function: '<Root>/rd' incorporates:
   *  Inport: '<Root>/a'
   *  Inport: '<Root>/b'
   */
  if (ecu_crankrd_U_b[6] < 6) {
    *ecu_crankrd_Y_rpm = 0.0F;
  } else {
    us = 0U;
    deg = 0U;
    for (i = 0; i < 6; i++) {
      qY = ecu_crankrd_U_a[i + 2] + /*MW:OvSatOk*/ us;
      if (qY < us) {
        qY = MAX_uint32_T;
      }

      us = qY;
      deg += ecu_crankrd_U_b[i];
    }

    *ecu_crankrd_Y_rpm = (real32_T)deg / (real32_T)us * 1.0E+6F / 6.0F;
  }

  *ecu_crankrd_Y_angle = (real32_T)ecu_crankrd_U_b[13] * 360.0F + (real32_T)
    ecu_crankrd_U_b[9] * 6.0F;
  if (*ecu_crankrd_Y_rpm > 0.0F) {
    /* Outport: '<Root>/us_per_deg' */
    *ecu_crankrd_Y_us_per_deg = 1.0E+6F / (*ecu_crankrd_Y_rpm * 6.0F);
  } else {
    /* Outport: '<Root>/us_per_deg' */
    *ecu_crankrd_Y_us_per_deg = 0.0F;
  }

  if (ecu_crankrd_U_b[9] == 57) {
    /* Outport: '<Root>/next_angle' */
    *ecu_crankrd_Y_next_angle = *ecu_crankrd_Y_angle + 18.0F;
  } else {
    /* Outport: '<Root>/next_angle' */
    *ecu_crankrd_Y_next_angle = *ecu_crankrd_Y_angle + 6.0F;
  }

  /* End of MATLAB Function: '<Root>/rd' */
  UNUSED_PARAMETER(ecu_crankrd_M);
}

/* Model initialize function */
void ecu_crankrd_initialize(RT_MODEL_ecu_crankrd_T *const ecu_crankrd_M,
  uint32_T ecu_crankrd_U_a[8], uint8_T ecu_crankrd_U_b[33], real32_T
  *ecu_crankrd_Y_rpm, real32_T *ecu_crankrd_Y_angle, real32_T
  *ecu_crankrd_Y_next_angle, real32_T *ecu_crankrd_Y_us_per_deg)
{
  /* Registration code */

  /* initialize error status */
  rtmSetErrorStatus(ecu_crankrd_M, (NULL));

  /* external inputs */
  (void)memset(&ecu_crankrd_U_a[0], 0, sizeof(uint32_T) << 3U);
  (void)memset(&ecu_crankrd_U_b[0], 0, 33U * sizeof(uint8_T));

  /* external outputs */
  *ecu_crankrd_Y_rpm = 0.0F;
  *ecu_crankrd_Y_angle = 0.0F;
  *ecu_crankrd_Y_next_angle = 0.0F;
  *ecu_crankrd_Y_us_per_deg = 0.0F;
  UNUSED_PARAMETER(ecu_crankrd_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
