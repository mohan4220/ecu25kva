/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_boostm.h
 *
 * Code generated for Simulink model 'ecu_boostm'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Sat Nov 14 17:30:09 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#ifndef ecu_boostm_h_
#define ecu_boostm_h_
#ifndef ecu_boostm_COMMON_INCLUDES_
#define ecu_boostm_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_boostm_COMMON_INCLUDES_ */

#include "ecu_boostm_types.h"
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
  uint16_T nh;                         /* '<Root>/BoostWarnings' */
  uint16_T nl;                         /* '<Root>/BoostWarnings' */
  uint8_T is_HIGH;                     /* '<Root>/BoostWarnings' */
  uint8_T is_LOW;                      /* '<Root>/BoostWarnings' */
} DW_ecu_boostm_T;

/* Real-time Model Data Structure */
struct tag_RTM_ecu_boostm_T {
  const char_T * volatile errorStatus;
  DW_ecu_boostm_T *dwork;
};

/* Model entry point functions */
extern void ecu_boostm_initialize(RT_MODEL_ecu_boostm_T *const ecu_boostm_M,
  real32_T *ecu_boostm_U_v_rail, uint8_T *ecu_boostm_U_fuelling, uint8_T
  *ecu_boostm_Y_hi_raise, uint8_T *ecu_boostm_Y_hi_drop, uint8_T
  *ecu_boostm_Y_lo_raise, uint8_T *ecu_boostm_Y_lo_drop);
extern void ecu_boostm_step(RT_MODEL_ecu_boostm_T *const ecu_boostm_M, real32_T
  ecu_boostm_U_v_rail, uint8_T ecu_boostm_U_fuelling, uint8_T
  *ecu_boostm_Y_hi_raise, uint8_T *ecu_boostm_Y_hi_drop, uint8_T
  *ecu_boostm_Y_lo_raise, uint8_T *ecu_boostm_Y_lo_drop);

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
 * '<Root>' : 'ecu_boostm'
 * '<S1>'   : 'ecu_boostm/BoostWarnings'
 */
#endif                                 /* ecu_boostm_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
