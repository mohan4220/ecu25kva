/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_musup.h
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

#ifndef ecu_musup_h_
#define ecu_musup_h_
#ifndef ecu_musup_COMMON_INCLUDES_
#define ecu_musup_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_musup_COMMON_INCLUDES_ */

#include "ecu_musup_types.h"
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
struct tag_RTM_ecu_musup_T {
  const char_T * volatile errorStatus;
};

/* Model entry point functions */
extern void ecu_musup_initialize(RT_MODEL_ecu_musup_T *const ecu_musup_M,
  real32_T *ecu_musup_U_cmd, real32_T *ecu_musup_U_duty_prev, real32_T
  *ecu_musup_U_v_bat, real32_T *ecu_musup_U_i_mu, uint8_T *ecu_musup_U_i_valid,
  uint8_T *ecu_musup_U_act_open, uint8_T *ecu_musup_U_act_over, real32_T
  *ecu_musup_U_r_p, uint16_T *ecu_musup_U_bad_p, real32_T *ecu_musup_Y_cmd_out,
  uint8_T *ecu_musup_Y_meas, real32_T *ecu_musup_Y_r_n, uint16_T
  *ecu_musup_Y_bad_n);
extern void ecu_musup_step(RT_MODEL_ecu_musup_T *const ecu_musup_M, real32_T
  ecu_musup_U_cmd, real32_T ecu_musup_U_duty_prev, real32_T ecu_musup_U_v_bat,
  real32_T ecu_musup_U_i_mu, uint8_T ecu_musup_U_i_valid, uint8_T
  ecu_musup_U_act_open, uint8_T ecu_musup_U_act_over, real32_T ecu_musup_U_r_p,
  uint16_T ecu_musup_U_bad_p, real32_T *ecu_musup_Y_cmd_out, uint8_T
  *ecu_musup_Y_meas, real32_T *ecu_musup_Y_r_n, uint16_T *ecu_musup_Y_bad_n);

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
 * '<Root>' : 'ecu_musup'
 * '<S1>'   : 'ecu_musup/sup'
 */
#endif                                 /* ecu_musup_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
