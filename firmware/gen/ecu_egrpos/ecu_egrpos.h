/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_egrpos.h
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

#ifndef ecu_egrpos_h_
#define ecu_egrpos_h_
#ifndef ecu_egrpos_COMMON_INCLUDES_
#define ecu_egrpos_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_egrpos_COMMON_INCLUDES_ */

#include "ecu_egrpos_types.h"
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
  real32_T integ_z_DSTATE;             /* '<Root>/integ_z' */
  real32_T prev_z_DSTATE;              /* '<Root>/prev_z' */
  real32_T dfilt_z_DSTATE;             /* '<Root>/dfilt_z' */
} DW_ecu_egrpos_T;

/* Real-time Model Data Structure */
struct tag_RTM_ecu_egrpos_T {
  const char_T * volatile errorStatus;
  DW_ecu_egrpos_T *dwork;
};

/* Model entry point functions */
extern void ecu_egrpos_initialize(RT_MODEL_ecu_egrpos_T *const ecu_egrpos_M,
  real32_T *ecu_egrpos_U_target, real32_T *ecu_egrpos_U_pos, uint8_T
  *ecu_egrpos_U_enable, real32_T *ecu_egrpos_Y_duty);
extern void ecu_egrpos_step(RT_MODEL_ecu_egrpos_T *const ecu_egrpos_M, real32_T
  ecu_egrpos_U_target, real32_T ecu_egrpos_U_pos, uint8_T ecu_egrpos_U_enable,
  real32_T *ecu_egrpos_Y_duty);

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
 * '<Root>' : 'ecu_egrpos'
 * '<S1>'   : 'ecu_egrpos/pid'
 */
#endif                                 /* ecu_egrpos_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
