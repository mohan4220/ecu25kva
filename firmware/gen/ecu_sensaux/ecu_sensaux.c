/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_sensaux.c
 *
 * Code generated for Simulink model 'ecu_sensaux'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Mon Nov 23 11:18:17 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_sensaux.h"
#include <math.h>
#include "rtwtypes.h"
#include <string.h>

/* Model step function */
void ecu_sensaux_step(RT_MODEL_ecu_sensaux_T *const ecu_sensaux_M, real32_T
                      ecu_sensaux_U_v, real32_T ecu_sensaux_U_v_5v, real32_T
                      *ecu_sensaux_Y_val, uint8_T *ecu_sensaux_Y_fmi)
{
  DW_ecu_sensaux_T *ecu_sensaux_DW = ecu_sensaux_M->dwork;
  int32_T k;
  int32_T tmp_0;
  int32_T tmp_1;
  real32_T val_n_tmp;
  real32_T val_n_tmp_0;
  real32_T vr;
  uint32_T tmp;
  uint8_T now;
  static const uint16_T c[20] = { 45313U, 26114U, 15462U, 9397U, 5896U, 3792U,
    2500U, 1707U, 1175U, 834U, 596U, 436U, 323U, 243U, 187U, 144U, 113U, 89U,
    71U, 57U };

  int32_T exitg1;

  /* MATLAB Function: '<Root>/aux' incorporates:
   *  Inport: '<Root>/v'
   *  Inport: '<Root>/v_5v'
   *  UnitDelay: '<Root>/bad_z'
   *  UnitDelay: '<Root>/fmi_z'
   */
  vr = ecu_sensaux_U_v_5v;
  if ((ecu_sensaux_U_v_5v < 4.5F) || (ecu_sensaux_U_v_5v > 5.5F)) {
    vr = 5.0F;
  }

  vr = ecu_sensaux_U_v * 5.0F / vr;
  if (vr > 4.8F) {
    now = 3U;
  } else if (vr < 0.1F) {
    now = 4U;
  } else {
    now = 0U;
  }

  if ((now != 0) != (ecu_sensaux_DW->fmi_z_DSTATE != 0)) {
    tmp = ecu_sensaux_DW->bad_z_DSTATE + 1U;
    if (ecu_sensaux_DW->bad_z_DSTATE + 1U > 65535U) {
      tmp = 65535U;
    }

    ecu_sensaux_DW->bad_z_DSTATE = (uint16_T)tmp;
    if ((uint16_T)tmp >= 100) {
      ecu_sensaux_DW->fmi_z_DSTATE = now;
      ecu_sensaux_DW->bad_z_DSTATE = 0U;
    }
  } else {
    ecu_sensaux_DW->bad_z_DSTATE = 0U;
    if (now != 0) {
      ecu_sensaux_DW->fmi_z_DSTATE = now;
    }
  }

  if (ecu_sensaux_DW->fmi_z_DSTATE != 0) {
    ecu_sensaux_DW->val_z_DSTATE = 40.0F;
  } else if (now == 0) {
    vr = 2490.0F * vr / (5.0F - vr);
    if (vr < 260000.0F) {
      vr = vr * 260000.0F / (260000.0F - vr);
    } else {
      vr = 1.0E+9F;
    }

    if (vr >= 45313.0F) {
      ecu_sensaux_DW->val_z_DSTATE = -40.0F;
    } else if (vr <= 57.0F) {
      ecu_sensaux_DW->val_z_DSTATE = 150.0F;
    } else {
      k = 1;
      do {
        exitg1 = 0;
        if (k > 2147483646) {
          tmp_0 = MAX_int32_T;
        } else {
          tmp_0 = k + 1;
        }

        if (vr <= c[tmp_0 - 1]) {
          if (k <= 2147483646) {
            k++;
          }
        } else {
          exitg1 = 1;
        }
      } while (exitg1 == 0);

      if (k > 2147483646) {
        tmp_0 = MAX_int32_T;
        tmp_1 = MAX_int32_T;
      } else {
        tmp_0 = k + 1;
        tmp_1 = k + 1;
      }

      val_n_tmp = c[k - 1];
      val_n_tmp_0 = (real32_T)(k - 1) * 10.0F - 40.0F;
      ecu_sensaux_DW->val_z_DSTATE = (((real32_T)(tmp_0 - 1) * 10.0F - 40.0F) -
        val_n_tmp_0) * (logf(val_n_tmp / vr) / logf(val_n_tmp / (real32_T)
        c[tmp_1 - 1])) + val_n_tmp_0;
    }
  }

  /* Outport: '<Root>/val' incorporates:
   *  MATLAB Function: '<Root>/aux'
   */
  *ecu_sensaux_Y_val = ecu_sensaux_DW->val_z_DSTATE;

  /* Outport: '<Root>/fmi' incorporates:
   *  MATLAB Function: '<Root>/aux'
   */
  *ecu_sensaux_Y_fmi = ecu_sensaux_DW->fmi_z_DSTATE;
}

/* Model initialize function */
void ecu_sensaux_initialize(RT_MODEL_ecu_sensaux_T *const ecu_sensaux_M,
  real32_T *ecu_sensaux_U_v, real32_T *ecu_sensaux_U_v_5v, real32_T
  *ecu_sensaux_Y_val, uint8_T *ecu_sensaux_Y_fmi)
{
  DW_ecu_sensaux_T *ecu_sensaux_DW = ecu_sensaux_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_sensaux_DW, 0,
                sizeof(DW_ecu_sensaux_T));

  /* external inputs */
  *ecu_sensaux_U_v = 0.0F;
  *ecu_sensaux_U_v_5v = 0.0F;

  /* external outputs */
  *ecu_sensaux_Y_val = 0.0F;
  *ecu_sensaux_Y_fmi = 0U;

  /* InitializeConditions for UnitDelay: '<Root>/val_z' */
  ecu_sensaux_DW->val_z_DSTATE = 40.0F;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
