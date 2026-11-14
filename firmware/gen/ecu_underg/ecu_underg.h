/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_underg.h
 *
 * Code generated for Simulink model 'ecu_underg'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:48:36 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#ifndef ecu_underg_h_
#define ecu_underg_h_
#ifndef ecu_underg_COMMON_INCLUDES_
#define ecu_underg_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_underg_COMMON_INCLUDES_ */

#include "ecu_underg_types.h"
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
  uint16_T n;                          /* '<Root>/Underspeed' */
  uint8_T is_c3_ecu_underg;            /* '<Root>/Underspeed' */
  uint8_T is_ARMED;                    /* '<Root>/Underspeed' */
} DW_ecu_underg_T;

/* Real-time Model Data Structure */
struct tag_RTM_ecu_underg_T {
  const char_T * volatile errorStatus;
  DW_ecu_underg_T *dwork;
};

/* Model entry point functions */
extern void ecu_underg_initialize(RT_MODEL_ecu_underg_T *const ecu_underg_M,
  real32_T *ecu_underg_U_rpm, uint8_T *ecu_underg_U_armed, uint8_T
  *ecu_underg_Y_raise, uint8_T *ecu_underg_Y_drop);
extern void ecu_underg_step(RT_MODEL_ecu_underg_T *const ecu_underg_M, real32_T
  ecu_underg_U_rpm, uint8_T ecu_underg_U_armed, uint8_T *ecu_underg_Y_raise,
  uint8_T *ecu_underg_Y_drop);

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
 * '<Root>' : 'ecu_underg'
 * '<S1>'   : 'ecu_underg/Underspeed'
 */
#endif                                 /* ecu_underg_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
