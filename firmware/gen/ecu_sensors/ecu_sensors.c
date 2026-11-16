/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_sensors.c
 *
 * Code generated for Simulink model 'ecu_sensors'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Mon Nov 16 14:16:07 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_sensors.h"
#include <math.h>
#include "rtwtypes.h"
#include <string.h>
#include "ecu_sensors_private.h"

/* Model step function */
void ecu_sensors_step(RT_MODEL_ecu_sensors_T *const ecu_sensors_M, real32_T
                      ecu_sensors_U_v[5], real32_T ecu_sensors_U_v_5v, real32_T
                      ecu_sensors_U_gain[6], real32_T ecu_sensors_U_offset[6],
                      real32_T ecu_sensors_Y_val[5], uint8_T ecu_sensors_Y_fmi[5])
{
  DW_ecu_sensors_T *ecu_sensors_DW = ecu_sensors_M->dwork;
  int32_T i;
  real32_T v5;
  real32_T vr;
  uint32_T tmp;
  uint16_T bad_z_DSTATE;
  int8_T d;
  uint8_T fmi_z_DSTATE;
  uint8_T now;
  static const int16_T c[5] = { 90, 300, 1000, 100, 0 };

  static const int8_T d_0[5] = { 0, 0, 0, 50, 0 };

  static const int16_T e[5] = { 0, 1000, 1800, 400, 100 };

  static const real32_T f[5] = { 0.1F, 0.2F, 0.2F, 0.2F, 0.2F };

  /* MATLAB Function: '<Root>/convert' incorporates:
   *  Inport: '<Root>/gain'
   *  Inport: '<Root>/offset'
   *  Inport: '<Root>/v'
   *  Inport: '<Root>/v_5v'
   *  UnitDelay: '<Root>/bad_z'
   */
  v5 = ecu_sensors_U_v_5v * ecu_sensors_U_gain[5] + ecu_sensors_U_offset[5];
  if ((v5 < 4.5F) || (v5 > 5.5F)) {
    v5 = 5.0F;
  }

  for (i = 0; i < 5; i++) {
    vr = (ecu_sensors_U_v[i] * ecu_sensors_U_gain[i] + ecu_sensors_U_offset[i]) *
      5.0F / v5;
    if (vr > 4.8F) {
      now = 3U;
    } else if (vr < f[i]) {
      now = 4U;
    } else {
      now = 0U;
    }

    fmi_z_DSTATE = ecu_sensors_DW->fmi_z_DSTATE[i];
    if ((now != 0) != (fmi_z_DSTATE != 0)) {
      bad_z_DSTATE = ecu_sensors_DW->bad_z_DSTATE[i];
      tmp = bad_z_DSTATE + 1U;
      if (bad_z_DSTATE + 1U > 65535U) {
        tmp = 65535U;
      }

      /* UnitDelay: '<Root>/bad_z' */
      ecu_sensors_DW->bad_z_DSTATE[i] = (uint16_T)tmp;
      if ((uint16_T)tmp >= 100) {
        fmi_z_DSTATE = now;
        ecu_sensors_DW->fmi_z_DSTATE[i] = now;
        ecu_sensors_DW->bad_z_DSTATE[i] = 0U;
      }
    } else {
      ecu_sensors_DW->bad_z_DSTATE[i] = 0U;
      if (now != 0) {
        fmi_z_DSTATE = now;
        ecu_sensors_DW->fmi_z_DSTATE[i] = now;
      }
    }

    if (fmi_z_DSTATE != 0) {
      ecu_sensors_DW->val_z_DSTATE[i] = c[i];
    } else if (now == 0) {
      if (i == 0) {
        ecu_sensors_DW->val_z_DSTATE[0] = 1.0F / (logf(2490.0F * vr / (5.0F - vr)
          / 2500.0F) / 3450.0F + 0.003411223F) - 273.15F;
      } else {
        d = d_0[i];
        ecu_sensors_DW->val_z_DSTATE[i] = (vr - 0.5F) / 4.0F * (real32_T)(e[i] -
          d) + (real32_T)d;
      }
    }

    /* Outport: '<Root>/val' incorporates:
     *  Inport: '<Root>/v'
     *  UnitDelay: '<Root>/bad_z'
     */
    ecu_sensors_Y_val[i] = ecu_sensors_DW->val_z_DSTATE[i];

    /* Outport: '<Root>/fmi' */
    ecu_sensors_Y_fmi[i] = fmi_z_DSTATE;
  }

  /* End of MATLAB Function: '<Root>/convert' */
}

/* Model initialize function */
void ecu_sensors_initialize(RT_MODEL_ecu_sensors_T *const ecu_sensors_M,
  real32_T ecu_sensors_U_v[5], real32_T *ecu_sensors_U_v_5v, real32_T
  ecu_sensors_U_gain[6], real32_T ecu_sensors_U_offset[6], real32_T
  ecu_sensors_Y_val[5], uint8_T ecu_sensors_Y_fmi[5])
{
  DW_ecu_sensors_T *ecu_sensors_DW = ecu_sensors_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_sensors_DW, 0,
                sizeof(DW_ecu_sensors_T));

  /* external inputs */
  (void)memset(&ecu_sensors_U_v[0], 0, 5U * sizeof(real32_T));
  (void)memset(&ecu_sensors_U_gain[0], 0, 6U * sizeof(real32_T));
  (void)memset(&ecu_sensors_U_offset[0], 0, 6U * sizeof(real32_T));
  *ecu_sensors_U_v_5v = 0.0F;

  /* external outputs */
  (void)memset(&ecu_sensors_Y_val[0], 0, 5U * sizeof(real32_T));
  (void)memset(&ecu_sensors_Y_fmi[0], 0, 5U * sizeof(uint8_T));

  {
    int32_T i;

    /* InitializeConditions for UnitDelay: '<Root>/val_z' */
    for (i = 0; i < 5; i++) {
      ecu_sensors_DW->val_z_DSTATE[i] = rtCP_val_z_InitialCondition[i];
    }

    /* End of InitializeConditions for UnitDelay: '<Root>/val_z' */
  }
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
