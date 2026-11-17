/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_spdst.h
 *
 * Code generated for Simulink model 'ecu_spdst'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Mon Nov 16 16:27:12 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#ifndef ecu_spdst_h_
#define ecu_spdst_h_
#ifndef ecu_spdst_COMMON_INCLUDES_
#define ecu_spdst_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_spdst_COMMON_INCLUDES_ */

#include "ecu_spdst_types.h"
#include <string.h>

/* Macros for accessing real-time model data structure */
#ifndef rtmGetRootDWork
#define rtmGetRootDWork(rtm)           ((rtm)->dwork)
#endif

#ifndef rtmSetRootDWork
#define rtmSetRootDWork(rtm, val)      ((rtm)->dwork = (val))
#endif

#ifndef rtmGetErrorStatus
#define rtmGetErrorStatus(rtm)         ((rtm)->errorStatus)
#endif

#ifndef rtmSetErrorStatus
#define rtmSetErrorStatus(rtm, val)    ((rtm)->errorStatus = (val))
#endif

/* Block states (default storage) for system '<Root>' */
typedef struct {
  uint32_T n;                          /* '<Root>/SpeedStates' */
  uint8_T is_c3_ecu_spdst;             /* '<Root>/SpeedStates' */
} DW_ecu_spdst_T;

/* Real-time Model Data Structure */
struct tag_RTM_ecu_spdst_T {
  const char_T * volatile errorStatus;
  DW_ecu_spdst_T *dwork;
};

/* Model entry point functions */
extern void ecu_spdst_initialize(RT_MODEL_ecu_spdst_T *const ecu_spdst_M,
  real32_T *ecu_spdst_U_rpm, real32_T *ecu_spdst_U_target, uint8_T
  *ecu_spdst_U_running, uint32_T *ecu_spdst_U_idle_ms, uint8_T *ecu_spdst_Y_idle,
  uint8_T *ecu_spdst_Y_state);
extern void ecu_spdst_step(RT_MODEL_ecu_spdst_T *const ecu_spdst_M, real32_T
  ecu_spdst_U_rpm, real32_T ecu_spdst_U_target, uint8_T ecu_spdst_U_running,
  uint32_T ecu_spdst_U_idle_ms, uint8_T *ecu_spdst_Y_idle, uint8_T
  *ecu_spdst_Y_state);

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
 * '<Root>' : 'ecu_spdst'
 * '<S1>'   : 'ecu_spdst/SpeedStates'
 */
#endif                                 /* ecu_spdst_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
