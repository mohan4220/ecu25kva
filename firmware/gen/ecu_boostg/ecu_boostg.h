/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_boostg.h
 *
 * Code generated for Simulink model 'ecu_boostg'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:48:07 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#ifndef ecu_boostg_h_
#define ecu_boostg_h_
#ifndef ecu_boostg_COMMON_INCLUDES_
#define ecu_boostg_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_boostg_COMMON_INCLUDES_ */

#include "ecu_boostg_types.h"
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
  uint16_T cnt;                        /* '<Root>/BoostGuard' */
  uint8_T latched;                     /* '<Root>/BoostGuard' */
  uint8_T is_Guard;                    /* '<Root>/BoostGuard' */
} DW_ecu_boostg_T;

/* Real-time Model Data Structure */
struct tag_RTM_ecu_boostg_T {
  const char_T * volatile errorStatus;
  DW_ecu_boostg_T *dwork;
};

/* Model entry point functions */
extern void ecu_boostg_initialize(RT_MODEL_ecu_boostg_T *const ecu_boostg_M,
  real32_T *ecu_boostg_U_v_rail, uint8_T *ecu_boostg_U_shut, uint8_T
  *ecu_boostg_Y_dis, uint8_T *ecu_boostg_Y_trip);
extern void ecu_boostg_step(RT_MODEL_ecu_boostg_T *const ecu_boostg_M, real32_T
  ecu_boostg_U_v_rail, uint8_T ecu_boostg_U_shut, uint8_T *ecu_boostg_Y_dis,
  uint8_T *ecu_boostg_Y_trip);

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
 * '<Root>' : 'ecu_boostg'
 * '<S1>'   : 'ecu_boostg/BoostGuard'
 */
#endif                                 /* ecu_boostg_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
