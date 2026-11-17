/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_egrpos.c
 *
 * Code generated for Simulink model 'ecu_egrpos'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Mon Nov 16 16:26:51 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_egrpos.h"
#include "rtwtypes.h"
#include <string.h>

/* Model step function */
void ecu_egrpos_step(RT_MODEL_ecu_egrpos_T *const ecu_egrpos_M, real32_T
                     ecu_egrpos_U_target, real32_T ecu_egrpos_U_pos, uint8_T
                     ecu_egrpos_U_enable, real32_T *ecu_egrpos_Y_duty)
{
  DW_ecu_egrpos_T *ecu_egrpos_DW = ecu_egrpos_M->dwork;
  real32_T out;
  real32_T out_tmp;
  real32_T out_tmp_0;
  real32_T rtb_prev_z;

  /* UnitDelay: '<Root>/prev_z' */
  rtb_prev_z = ecu_egrpos_DW->prev_z_DSTATE;

  /* MATLAB Function: '<Root>/pid' incorporates:
   *  Inport: '<Root>/enable'
   *  Inport: '<Root>/pos'
   *  Inport: '<Root>/target'
   *  UnitDelay: '<Root>/dfilt_z'
   *  UnitDelay: '<Root>/integ_z'
   *  UnitDelay: '<Root>/prev_z'
   */
  ecu_egrpos_DW->prev_z_DSTATE = ecu_egrpos_U_pos;
  if ((ecu_egrpos_U_enable == 0) || (ecu_egrpos_U_target <= 2.0F)) {
    ecu_egrpos_DW->integ_z_DSTATE = 0.0F;
    ecu_egrpos_DW->dfilt_z_DSTATE = 0.0F;

    /* Outport: '<Root>/duty' */
    *ecu_egrpos_Y_duty = 0.0F;
  } else {
    ecu_egrpos_DW->dfilt_z_DSTATE += ((ecu_egrpos_U_pos - rtb_prev_z) / 0.001F -
      ecu_egrpos_DW->dfilt_z_DSTATE) * 0.1F;
    rtb_prev_z = ecu_egrpos_U_target - ecu_egrpos_U_pos;
    out_tmp = 0.02F * rtb_prev_z;
    out_tmp_0 = 0.0005F * ecu_egrpos_DW->dfilt_z_DSTATE;
    out = (out_tmp + ecu_egrpos_DW->integ_z_DSTATE) - out_tmp_0;
    if (((out < 0.95F) || (rtb_prev_z <= 0.0F)) && ((out > -0.95F) ||
         (rtb_prev_z >= 0.0F))) {
      ecu_egrpos_DW->integ_z_DSTATE += 0.1F * rtb_prev_z * 0.001F;
      if (ecu_egrpos_DW->integ_z_DSTATE < -0.95F) {
        ecu_egrpos_DW->integ_z_DSTATE = -0.95F;
      } else if (ecu_egrpos_DW->integ_z_DSTATE > 0.95F) {
        ecu_egrpos_DW->integ_z_DSTATE = 0.95F;
      }
    }

    *ecu_egrpos_Y_duty = (out_tmp + ecu_egrpos_DW->integ_z_DSTATE) - out_tmp_0;
    if (*ecu_egrpos_Y_duty < -0.95F) {
      /* Outport: '<Root>/duty' */
      *ecu_egrpos_Y_duty = -0.95F;
    } else if (*ecu_egrpos_Y_duty > 0.95F) {
      /* Outport: '<Root>/duty' */
      *ecu_egrpos_Y_duty = 0.95F;
    }
  }

  /* End of MATLAB Function: '<Root>/pid' */
}

/* Model initialize function */
void ecu_egrpos_initialize(RT_MODEL_ecu_egrpos_T *const ecu_egrpos_M, real32_T
  *ecu_egrpos_U_target, real32_T *ecu_egrpos_U_pos, uint8_T *ecu_egrpos_U_enable,
  real32_T *ecu_egrpos_Y_duty)
{
  DW_ecu_egrpos_T *ecu_egrpos_DW = ecu_egrpos_M->dwork;

  /* Registration code */

  /* states (dwork) */
  (void) memset((void *)ecu_egrpos_DW, 0,
                sizeof(DW_ecu_egrpos_T));

  /* external inputs */
  *ecu_egrpos_U_target = 0.0F;
  *ecu_egrpos_U_pos = 0.0F;
  *ecu_egrpos_U_enable = 0U;

  /* external outputs */
  *ecu_egrpos_Y_duty = 0.0F;
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
