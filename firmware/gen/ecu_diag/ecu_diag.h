/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_diag.h
 *
 * Code generated for Simulink model 'ecu_diag'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Mon Nov 23 23:37:38 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#ifndef ecu_diag_h_
#define ecu_diag_h_
#ifndef ecu_diag_COMMON_INCLUDES_
#define ecu_diag_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_diag_COMMON_INCLUDES_ */

#include "ecu_diag_types.h"
#include "rt_defines.h"
#include <stddef.h>

/* Macros for accessing real-time model data structure */
#ifndef rtmGetErrorStatus
#define rtmGetErrorStatus(rtm)         ((rtm)->errorStatus)
#endif

#ifndef rtmSetErrorStatus
#define rtmSetErrorStatus(rtm, val)    ((rtm)->errorStatus = (val))
#endif

/* Real-time Model Data Structure */
struct tag_RTM_ecu_diag_T {
  const char_T * volatile errorStatus;
};

/* Model entry point functions */
extern void ecu_diag_initialize(RT_MODEL_ecu_diag_T *const ecu_diag_M, uint8_T
  *ecu_diag_U_running, uint8_T *ecu_diag_U_ign_on, uint8_T *ecu_diag_U_stopped,
  real32_T *ecu_diag_U_rpm, real32_T *ecu_diag_U_v_bat, real32_T
  *ecu_diag_U_egr_duty, real32_T *ecu_diag_U_i_egr_f, real32_T
  *ecu_diag_U_egr_pos, uint8_T *ecu_diag_U_egr_pos_ok, uint8_T
  *ecu_diag_U_egr_off, real32_T *ecu_diag_U_mu_duty, real32_T *ecu_diag_U_i_mu,
  uint8_T *ecu_diag_U_i_mu_valid, real32_T *ecu_diag_U_rail_set, real32_T
  *ecu_diag_U_rail_bar, uint8_T *ecu_diag_U_rail_ok, real32_T
  *ecu_diag_U_oil_kpa, uint8_T *ecu_diag_U_oil_ok, uint8_T
  *ecu_diag_U_bat_high_act, uint8_T *ecu_diag_U_bat_low_act, real32_T
  *ecu_diag_U_clt_c, uint8_T *ecu_diag_U_clt_ok, uint8_T *ecu_diag_U_clt_low,
  uint8_T *ecu_diag_U_clt_warn_act, uint8_T *ecu_diag_U_clt_stop_act, uint8_T
  ecu_diag_Y_c[14]);
extern void ecu_diag_step(RT_MODEL_ecu_diag_T *const ecu_diag_M, uint8_T
  ecu_diag_U_running, uint8_T ecu_diag_U_ign_on, uint8_T ecu_diag_U_stopped,
  real32_T ecu_diag_U_rpm, real32_T ecu_diag_U_v_bat, real32_T
  ecu_diag_U_egr_duty, real32_T ecu_diag_U_i_egr_f, real32_T ecu_diag_U_egr_pos,
  uint8_T ecu_diag_U_egr_pos_ok, uint8_T ecu_diag_U_egr_off, real32_T
  ecu_diag_U_mu_duty, real32_T ecu_diag_U_i_mu, uint8_T ecu_diag_U_i_mu_valid,
  real32_T ecu_diag_U_rail_set, real32_T ecu_diag_U_rail_bar, uint8_T
  ecu_diag_U_rail_ok, real32_T ecu_diag_U_oil_kpa, uint8_T ecu_diag_U_oil_ok,
  uint8_T ecu_diag_U_bat_high_act, uint8_T ecu_diag_U_bat_low_act, real32_T
  ecu_diag_U_clt_c, uint8_T ecu_diag_U_clt_ok, uint8_T ecu_diag_U_clt_low,
  uint8_T ecu_diag_U_clt_warn_act, uint8_T ecu_diag_U_clt_stop_act, uint8_T
  ecu_diag_Y_c[14]);

/*-
 * The generated code includes comments that allow you to trace directly
 * back to the appropriate location in the model.  The basic format
 * is <system>/block_name, where system is the system number (uniquely
 * assigned by Simulink) and block_name is the name of the block.
 *
 * Use the MATLAB hilite_system command to trace the generated code back
 * to the model.  For example,
 *
 * hilite_system('<S3>')    - opens system 3
 * hilite_system('<S3>/Kp') - opens and selects block Kp which resides in S3
 *
 * Here is the system hierarchy for this model
 *
 * '<Root>' : 'ecu_diag'
 * '<S1>'   : 'ecu_diag/cond'
 */
#endif                                 /* ecu_diag_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
