/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_musup.c
 *
 * Code generated for Simulink model 'ecu_musup'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Tue Nov 24 00:39:26 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_musup.h"
#include "rtwtypes.h"

/* Model step function */
void ecu_musup_step(RT_MODEL_ecu_musup_T *const ecu_musup_M, real32_T
                    ecu_musup_U_cmd, real32_T ecu_musup_U_duty_prev, real32_T
                    ecu_musup_U_v_bat, real32_T ecu_musup_U_i_mu, uint8_T
                    ecu_musup_U_i_valid, uint8_T ecu_musup_U_act_open, uint8_T
                    ecu_musup_U_act_over, real32_T ecu_musup_U_r_p, uint16_T
                    ecu_musup_U_bad_p, real32_T *ecu_musup_Y_cmd_out, uint8_T
                    *ecu_musup_Y_meas, real32_T *ecu_musup_Y_r_n, uint16_T
                    *ecu_musup_Y_bad_n)
{
  real32_T x;
  uint32_T tmp;
  boolean_T odd;

  /* MATLAB Function: '<Root>/sup' incorporates:
   *  Inport: '<Root>/act_open'
   *  Inport: '<Root>/act_over'
   *  Inport: '<Root>/bad_p'
   *  Inport: '<Root>/duty_prev'
   *  Inport: '<Root>/i_mu'
   *  Inport: '<Root>/i_valid'
   *  Inport: '<Root>/v_bat'
   */
  if (ecu_musup_U_i_valid != 0) {
    if ((ecu_musup_U_duty_prev * ecu_musup_U_v_bat / 6.91F > 0.25F) &&
        (ecu_musup_U_i_mu < 0.05F)) {
      odd = true;
    } else {
      odd = (ecu_musup_U_i_mu > 3.0F);
    }
  } else {
    odd = false;
  }

  if (odd) {
    if (ecu_musup_U_bad_p < 65535) {
      tmp = ecu_musup_U_bad_p + 1U;
      if (ecu_musup_U_bad_p + 1U > 65535U) {
        tmp = 65535U;
      }

      *ecu_musup_Y_bad_n = (uint16_T)tmp;
    } else {
      *ecu_musup_Y_bad_n = ecu_musup_U_bad_p;
    }
  } else {
    *ecu_musup_Y_bad_n = 0U;
  }

  odd = ((ecu_musup_U_i_valid != 0) && (*ecu_musup_Y_bad_n < 10) &&
         (ecu_musup_U_act_open == 0) && (ecu_musup_U_act_over == 0));

  /* Outport: '<Root>/r_n' incorporates:
   *  Inport: '<Root>/r_p'
   *  MATLAB Function: '<Root>/sup'
   */
  *ecu_musup_Y_r_n = ecu_musup_U_r_p;

  /* MATLAB Function: '<Root>/sup' incorporates:
   *  Inport: '<Root>/duty_prev'
   *  Inport: '<Root>/i_mu'
   *  Inport: '<Root>/r_p'
   *  Inport: '<Root>/v_bat'
   */
  if (odd) {
    if ((ecu_musup_U_v_bat >= 6.0F) && (ecu_musup_U_v_bat <= 18.0F) &&
        (ecu_musup_U_i_mu >= 0.9F) && (ecu_musup_U_duty_prev > 0.05F) &&
        (ecu_musup_U_duty_prev < 0.95F)) {
      x = ecu_musup_U_duty_prev * ecu_musup_U_v_bat / ecu_musup_U_i_mu;
      if (x < 1.85F) {
        x = 1.85F;
      } else if (x > 6.91F) {
        x = 6.91F;
      }

      /* Outport: '<Root>/r_n' incorporates:
       *  Inport: '<Root>/r_p'
       */
      *ecu_musup_Y_r_n = (x - ecu_musup_U_r_p) * 0.001F + ecu_musup_U_r_p;
    }

    /* Outport: '<Root>/cmd_out' incorporates:
     *  Inport: '<Root>/cmd'
     *  Inport: '<Root>/duty_prev'
     *  Inport: '<Root>/i_mu'
     *  Inport: '<Root>/v_bat'
     */
    *ecu_musup_Y_cmd_out = ecu_musup_U_cmd;
  } else {
    x = ecu_musup_U_r_p;
    if (ecu_musup_U_r_p < 1.85F) {
      x = 1.85F;
    } else if (ecu_musup_U_r_p > 6.91F) {
      x = 6.91F;
    }

    /* Outport: '<Root>/cmd_out' incorporates:
     *  Inport: '<Root>/cmd'
     *  Inport: '<Root>/r_p'
     */
    *ecu_musup_Y_cmd_out = x / 3.75F * ecu_musup_U_cmd;
  }

  /* Outport: '<Root>/meas' incorporates:
   *  MATLAB Function: '<Root>/sup'
   */
  *ecu_musup_Y_meas = odd;
  UNUSED_PARAMETER(ecu_musup_M);
}

/* Model initialize function */
void ecu_musup_initialize(RT_MODEL_ecu_musup_T *const ecu_musup_M, real32_T
  *ecu_musup_U_cmd, real32_T *ecu_musup_U_duty_prev, real32_T *ecu_musup_U_v_bat,
  real32_T *ecu_musup_U_i_mu, uint8_T *ecu_musup_U_i_valid, uint8_T
  *ecu_musup_U_act_open, uint8_T *ecu_musup_U_act_over, real32_T
  *ecu_musup_U_r_p, uint16_T *ecu_musup_U_bad_p, real32_T *ecu_musup_Y_cmd_out,
  uint8_T *ecu_musup_Y_meas, real32_T *ecu_musup_Y_r_n, uint16_T
  *ecu_musup_Y_bad_n)
{
  /* Registration code */

  /* initialize error status */
  rtmSetErrorStatus(ecu_musup_M, (NULL));

  /* external inputs */
  *ecu_musup_U_cmd = 0.0F;
  *ecu_musup_U_duty_prev = 0.0F;
  *ecu_musup_U_v_bat = 0.0F;
  *ecu_musup_U_i_mu = 0.0F;
  *ecu_musup_U_i_valid = 0U;
  *ecu_musup_U_act_open = 0U;
  *ecu_musup_U_act_over = 0U;
  *ecu_musup_U_r_p = 0.0F;
  *ecu_musup_U_bad_p = 0U;

  /* external outputs */
  *ecu_musup_Y_cmd_out = 0.0F;
  *ecu_musup_Y_meas = 0U;
  *ecu_musup_Y_r_n = 0.0F;
  *ecu_musup_Y_bad_n = 0U;
  UNUSED_PARAMETER(ecu_musup_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
