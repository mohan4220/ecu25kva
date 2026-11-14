/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_wifg.h
 *
 * Code generated for Simulink model 'ecu_wifg'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:48:27 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#ifndef ecu_wifg_h_
#define ecu_wifg_h_
#ifndef ecu_wifg_COMMON_INCLUDES_
#define ecu_wifg_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_wifg_COMMON_INCLUDES_ */

#include "ecu_wifg_types.h"
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
  uint16_T n;                          /* '<Root>/WaterInFuel' */
  uint8_T is_c3_ecu_wifg;              /* '<Root>/WaterInFuel' */
} DW_ecu_wifg_T;

/* Real-time Model Data Structure */
struct tag_RTM_ecu_wifg_T {
  const char_T * volatile errorStatus;
  DW_ecu_wifg_T *dwork;
};

/* Model entry point functions */
extern void ecu_wifg_initialize(RT_MODEL_ecu_wifg_T *const ecu_wifg_M, uint8_T
  *ecu_wifg_U_wif, uint8_T *ecu_wifg_Y_raise, uint8_T *ecu_wifg_Y_drop);
extern void ecu_wifg_step(RT_MODEL_ecu_wifg_T *const ecu_wifg_M, uint8_T
  ecu_wifg_U_wif, uint8_T *ecu_wifg_Y_raise, uint8_T *ecu_wifg_Y_drop);

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
 * '<Root>' : 'ecu_wifg'
 * '<S1>'   : 'ecu_wifg/WaterInFuel'
 */
#endif                                 /* ecu_wifg_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
