/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_j1939.h
 *
 * Code generated for Simulink model 'ecu_j1939'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Tue Nov 24 14:24:19 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#ifndef ecu_j1939_h_
#define ecu_j1939_h_
#ifndef ecu_j1939_COMMON_INCLUDES_
#define ecu_j1939_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_j1939_COMMON_INCLUDES_ */

#include "ecu_j1939_types.h"
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
struct tag_RTM_ecu_j1939_T {
  const char_T * volatile errorStatus;
};

/* Model entry point functions */
extern void ecu_j1939_initialize(RT_MODEL_ecu_j1939_T *const ecu_j1939_M,
  real32_T *ecu_j1939_U_rpm, real32_T *ecu_j1939_U_clt_c, uint8_T
  *ecu_j1939_U_clt_ok, real32_T *ecu_j1939_U_oil_kpa, uint8_T
  *ecu_j1939_U_oil_ok, uint32_T *ecu_j1939_U_engine_s, uint8_T
  *ecu_j1939_U_clt_low, real32_T *ecu_j1939_U_intake_c, uint8_T
  *ecu_j1939_U_intake_ok, uint8_T ecu_j1939_Y_eec1[8], uint8_T ecu_j1939_Y_et1[8],
  uint8_T ecu_j1939_Y_eflp1[8], uint8_T ecu_j1939_Y_hours[8], uint8_T
  ecu_j1939_Y_ic1[8]);
extern void ecu_j1939_step(RT_MODEL_ecu_j1939_T *const ecu_j1939_M, real32_T
  ecu_j1939_U_rpm, real32_T ecu_j1939_U_clt_c, uint8_T ecu_j1939_U_clt_ok,
  real32_T ecu_j1939_U_oil_kpa, uint8_T ecu_j1939_U_oil_ok, uint32_T
  ecu_j1939_U_engine_s, uint8_T ecu_j1939_U_clt_low, real32_T
  ecu_j1939_U_intake_c, uint8_T ecu_j1939_U_intake_ok, uint8_T ecu_j1939_Y_eec1
  [8], uint8_T ecu_j1939_Y_et1[8], uint8_T ecu_j1939_Y_eflp1[8], uint8_T
  ecu_j1939_Y_hours[8], uint8_T ecu_j1939_Y_ic1[8]);

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
 * '<Root>' : 'ecu_j1939'
 * '<S1>'   : 'ecu_j1939/set_pgns'
 */
#endif                                 /* ecu_j1939_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
