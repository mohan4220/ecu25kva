/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_j1939.c
 *
 * Code generated for Simulink model 'ecu_j1939'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Mon Nov 16 14:16:17 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_j1939.h"
#include <math.h>
#include "rtwtypes.h"
#include <string.h>

/* Model step function */
void ecu_j1939_step(RT_MODEL_ecu_j1939_T *const ecu_j1939_M, real32_T
                    ecu_j1939_U_rpm, real32_T ecu_j1939_U_clt_c, uint8_T
                    ecu_j1939_U_clt_ok, real32_T ecu_j1939_U_oil_kpa, uint8_T
                    ecu_j1939_U_oil_ok, uint32_T ecu_j1939_U_engine_s, uint8_T
                    ecu_j1939_Y_eec1[8], uint8_T ecu_j1939_Y_et1[8], uint8_T
                    ecu_j1939_Y_eflp1[8], uint8_T ecu_j1939_Y_hours[8])
{
  int32_T i;
  real32_T x;
  uint32_T h;
  uint16_T tmp;
  for (i = 0; i < 8; i++) {
    /* Outport: '<Root>/eec1' incorporates:
     *  MATLAB Function: '<Root>/set_pgns'
     */
    ecu_j1939_Y_eec1[i] = MAX_uint8_T;

    /* Outport: '<Root>/et1' incorporates:
     *  MATLAB Function: '<Root>/set_pgns'
     */
    ecu_j1939_Y_et1[i] = MAX_uint8_T;

    /* Outport: '<Root>/eflp1' incorporates:
     *  MATLAB Function: '<Root>/set_pgns'
     */
    ecu_j1939_Y_eflp1[i] = MAX_uint8_T;

    /* Outport: '<Root>/hours' incorporates:
     *  MATLAB Function: '<Root>/set_pgns'
     */
    ecu_j1939_Y_hours[i] = MAX_uint8_T;
  }

  /* MATLAB Function: '<Root>/set_pgns' incorporates:
   *  Inport: '<Root>/clt_c'
   *  Inport: '<Root>/clt_ok'
   *  Inport: '<Root>/engine_s'
   *  Inport: '<Root>/oil_kpa'
   *  Inport: '<Root>/oil_ok'
   *  Inport: '<Root>/rpm'
   *  Outport: '<Root>/eec1'
   *  Outport: '<Root>/eflp1'
   *  Outport: '<Root>/et1'
   *  Outport: '<Root>/hours'
   */
  x = ecu_j1939_U_rpm;
  if (ecu_j1939_U_rpm < 0.0F) {
    x = 0.0F;
  } else if (ecu_j1939_U_rpm > 8031.0F) {
    x = 8031.0F;
  }

  x = floorf(x / 0.125F + 0.5F);
  if (x < 65536.0F) {
    if (x >= 0.0F) {
      tmp = (uint16_T)x;
    } else {
      tmp = 0U;
    }
  } else {
    tmp = MAX_uint16_T;
  }

  ecu_j1939_Y_eec1[3] = (uint8_T)(tmp & 255U);
  ecu_j1939_Y_eec1[4] = (uint8_T)(tmp >> 8);
  if (ecu_j1939_U_clt_ok != 0) {
    if (ecu_j1939_U_clt_c + 40.0F < 0.0F) {
      ecu_j1939_Y_et1[0] = 0U;
    } else if (ecu_j1939_U_clt_c + 40.0F > 250.0F) {
      ecu_j1939_Y_et1[0] = 250U;
    } else {
      x = floorf((ecu_j1939_U_clt_c + 40.0F) + 0.5F);
      if (x < 256.0F) {
        if (x >= 0.0F) {
          ecu_j1939_Y_et1[0] = (uint8_T)x;
        } else {
          ecu_j1939_Y_et1[0] = 0U;
        }
      } else {
        ecu_j1939_Y_et1[0] = MAX_uint8_T;
      }
    }
  }

  if (ecu_j1939_U_oil_ok != 0) {
    x = ecu_j1939_U_oil_kpa / 4.0F;
    if (x < 0.0F) {
      ecu_j1939_Y_eflp1[3] = 0U;
    } else if (x > 250.0F) {
      ecu_j1939_Y_eflp1[3] = 250U;
    } else {
      x = floorf(x + 0.5F);
      if (x < 256.0F) {
        ecu_j1939_Y_eflp1[3] = (uint8_T)x;
      } else {
        ecu_j1939_Y_eflp1[3] = MAX_uint8_T;
      }
    }
  }

  h = ecu_j1939_U_engine_s / 180U;
  ecu_j1939_Y_hours[0] = (uint8_T)(h & 255U);
  ecu_j1939_Y_hours[1] = (uint8_T)(h >> 8 & 255U);
  ecu_j1939_Y_hours[2] = (uint8_T)(h >> 16 & 255U);
  ecu_j1939_Y_hours[3] = (uint8_T)(h >> 24);
  UNUSED_PARAMETER(ecu_j1939_M);
}

/* Model initialize function */
void ecu_j1939_initialize(RT_MODEL_ecu_j1939_T *const ecu_j1939_M, real32_T
  *ecu_j1939_U_rpm, real32_T *ecu_j1939_U_clt_c, uint8_T *ecu_j1939_U_clt_ok,
  real32_T *ecu_j1939_U_oil_kpa, uint8_T *ecu_j1939_U_oil_ok, uint32_T
  *ecu_j1939_U_engine_s, uint8_T ecu_j1939_Y_eec1[8], uint8_T ecu_j1939_Y_et1[8],
  uint8_T ecu_j1939_Y_eflp1[8], uint8_T ecu_j1939_Y_hours[8])
{
  /* Registration code */

  /* initialize error status */
  rtmSetErrorStatus(ecu_j1939_M, (NULL));

  /* external inputs */
  *ecu_j1939_U_rpm = 0.0F;
  *ecu_j1939_U_clt_c = 0.0F;
  *ecu_j1939_U_clt_ok = 0U;
  *ecu_j1939_U_oil_kpa = 0.0F;
  *ecu_j1939_U_oil_ok = 0U;
  *ecu_j1939_U_engine_s = 0U;

  /* external outputs */
  (void)memset(&ecu_j1939_Y_eec1[0], 0, sizeof(uint8_T) << 3U);
  (void)memset(&ecu_j1939_Y_et1[0], 0, sizeof(uint8_T) << 3U);
  (void)memset(&ecu_j1939_Y_eflp1[0], 0, sizeof(uint8_T) << 3U);
  (void)memset(&ecu_j1939_Y_hours[0], 0, sizeof(uint8_T) << 3U);
  UNUSED_PARAMETER(ecu_j1939_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
