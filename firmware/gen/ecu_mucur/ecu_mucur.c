/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_mucur.c
 *
 * Code generated for Simulink model 'ecu_mucur'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Sun Nov 22 21:14:55 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_mucur.h"
#include "rtwtypes.h"
#include <string.h>

/* Model step function */
void ecu_mucur_step(RT_MODEL_ecu_mucur_T *const ecu_mucur_M, real32_T
                    ecu_mucur_U_cmd, real32_T ecu_mucur_U_i_meas, uint8_T
                    ecu_mucur_U_valid, real32_T ecu_mucur_U_v_bat, real32_T
                    *ecu_mucur_Y_duty)
{
  DW_ecu_mucur_T *ecu_mucur_DW = ecu_mucur_M->dwork;
  real32_T err;
  real32_T out;
  real32_T out_tmp;

  /* MATLAB Function: '<Root>/loop' incorporates:
   *  Inport: '<Root>/cmd'
   *  Inport: '<Root>/i_meas'
   *  Inport: '<Root>/v_bat'
   *  Inport: '<Root>/valid'
   *  UnitDelay: '<Root>/integ_z'
   */
  if ((ecu_mucur_U_v_bat >= 6.0F) && (ecu_mucur_U_v_bat <= 18.0F)) {
    err = ecu_mucur_U_v_bat;
  } else {
    err = 13.5F;
  }

  *ecu_mucur_Y_duty = 6.75F / err * ecu_mucur_U_cmd;
  if (ecu_mucur_U_valid == 0) {
    ecu_mucur_DW->integ_z_DSTATE = 0.0F;
    if (*ecu_mucur_Y_duty < 0.0F) {
      /* Outport: '<Root>/duty' */
      *ecu_mucur_Y_duty = 0.0F;
    } else if (*ecu_mucur_Y_duty > 1.0F) {
      /* Outport: '<Root>/duty' */
      *ecu_mucur_Y_duty = 1.0F;
    }
  } else {
    err = ecu_mucur_U_cmd - ecu_mucur_U_i_meas / 1.8F;
    out_tmp = 0.1F * err;
    out = (*ecu_mucur_Y_duty + ecu_mucur_DW->integ_z_DSTATE) + out_tmp;
    if (((out < 1.0F) || (err <= 0.0F)) && ((out > 0.0F) || (err >= 0.0F))) {
      ecu_mucur_DW->integ_z_DSTATE += 10.0F * err * 0.001F;
      if (ecu_mucur_DW->integ_z_DSTATE < -0.5F) {
        ecu_mucur_DW->integ_z_DSTATE = -0.5F;
      } else if (ecu_mucur_DW->integ_z_DSTATE > 0.5F) {
        ecu_mucur_DW->integ_z_DSTATE = 0.5F;
      }
    }

    *ecu_mucur_Y_duty = (*ecu_mucur_Y_duty + ecu_mucur_DW->integ_z_DSTATE) +
      out_tmp;
    if (*ecu_mucur_Y_duty < 0.0F) {
      /* Outport: '<Root>/duty' */
      *ecu_mucur_Y_duty = 0.0F;
    } else if (*ecu_mucur_Y_duty > 1.0F) {
      /* Outport: '<Root>/duty' */
      *ecu_mucur_Y_duty = 1.0F;
    }
  }

  /* End of MATLAB Function: '<Root>/loop' */
}

/* Model initialize function */
void ecu_mucur_initialize(RT_MODEL_ecu_mucur_T *const ecu_mucur_M, real32_T
  *ecu_mucur_U_cmd, real32_T *ecu_mucur_U_i_meas, uint8_T *ecu_mucur_U_valid,
  real32_T *ecu_mucur_U_v_bat, real32_T *ecu_mucur_Y_duty)
{
  DW_ecu_mucur_T *ecu_mucur_DW = ecu_mucur_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_mucur_DW, 0,
                sizeof(DW_ecu_mucur_T));

  /* external inputs */
  *ecu_mucur_U_cmd = 0.0F;
  *ecu_mucur_U_i_meas = 0.0F;
  *ecu_mucur_U_valid = 0U;
  *ecu_mucur_U_v_bat = 0.0F;

  /* external outputs */
  *ecu_mucur_Y_duty = 0.0F;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
