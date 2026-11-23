/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_sensaux.h
 *
 * Code generated for Simulink model 'ecu_sensaux'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Mon Nov 23 11:18:17 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#ifndef ecu_sensaux_h_
#define ecu_sensaux_h_
#ifndef ecu_sensaux_COMMON_INCLUDES_
#define ecu_sensaux_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_sensaux_COMMON_INCLUDES_ */

#include "ecu_sensaux_types.h"
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
  real32_T val_z_DSTATE;               /* '<Root>/val_z' */
  uint16_T bad_z_DSTATE;               /* '<Root>/bad_z' */
  uint8_T fmi_z_DSTATE;                /* '<Root>/fmi_z' */
} DW_ecu_sensaux_T;

/* Real-time Model Data Structure */
struct tag_RTM_ecu_sensaux_T {
  const char_T * volatile errorStatus;
  DW_ecu_sensaux_T *dwork;
};

/* Model entry point functions */
extern void ecu_sensaux_initialize(RT_MODEL_ecu_sensaux_T *const ecu_sensaux_M,
  real32_T *ecu_sensaux_U_v, real32_T *ecu_sensaux_U_v_5v, real32_T
  *ecu_sensaux_Y_val, uint8_T *ecu_sensaux_Y_fmi);
extern void ecu_sensaux_step(RT_MODEL_ecu_sensaux_T *const ecu_sensaux_M,
  real32_T ecu_sensaux_U_v, real32_T ecu_sensaux_U_v_5v, real32_T
  *ecu_sensaux_Y_val, uint8_T *ecu_sensaux_Y_fmi);

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
 * '<Root>' : 'ecu_sensaux'
 * '<S1>'   : 'ecu_sensaux/aux'
 */
#endif                                 /* ecu_sensaux_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
