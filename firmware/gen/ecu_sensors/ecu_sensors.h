/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_sensors.h
 *
 * Code generated for Simulink model 'ecu_sensors'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Sun Nov 22 23:07:16 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#ifndef ecu_sensors_h_
#define ecu_sensors_h_
#ifndef ecu_sensors_COMMON_INCLUDES_
#define ecu_sensors_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_sensors_COMMON_INCLUDES_ */

#include "ecu_sensors_types.h"
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
  real32_T val_z_DSTATE[5];            /* '<Root>/val_z' */
  uint16_T bad_z_DSTATE[5];            /* '<Root>/bad_z' */
  uint8_T fmi_z_DSTATE[5];             /* '<Root>/fmi_z' */
} DW_ecu_sensors_T;

/* Real-time Model Data Structure */
struct tag_RTM_ecu_sensors_T {
  const char_T * volatile errorStatus;
  DW_ecu_sensors_T *dwork;
};

/* Model entry point functions */
extern void ecu_sensors_initialize(RT_MODEL_ecu_sensors_T *const ecu_sensors_M,
  real32_T ecu_sensors_U_v[5], real32_T *ecu_sensors_U_v_5v, real32_T
  ecu_sensors_U_gain[6], real32_T ecu_sensors_U_offset[6], real32_T
  ecu_sensors_Y_val[5], uint8_T ecu_sensors_Y_fmi[5]);
extern void ecu_sensors_step(RT_MODEL_ecu_sensors_T *const ecu_sensors_M,
  real32_T ecu_sensors_U_v[5], real32_T ecu_sensors_U_v_5v, real32_T
  ecu_sensors_U_gain[6], real32_T ecu_sensors_U_offset[6], real32_T
  ecu_sensors_Y_val[5], uint8_T ecu_sensors_Y_fmi[5]);

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
 * '<Root>' : 'ecu_sensors'
 * '<S1>'   : 'ecu_sensors/convert'
 */
#endif                                 /* ecu_sensors_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
