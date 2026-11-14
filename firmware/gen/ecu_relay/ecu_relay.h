/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_relay.h
 *
 * Code generated for Simulink model 'ecu_relay'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:48:46 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#ifndef ecu_relay_h_
#define ecu_relay_h_
#ifndef ecu_relay_COMMON_INCLUDES_
#define ecu_relay_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_relay_COMMON_INCLUDES_ */

#include "ecu_relay_types.h"
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
  uint16_T ms;                         /* '<Root>/MainRelay' */
  uint8_T is_Relay;                    /* '<Root>/MainRelay' */
} DW_ecu_relay_T;

/* Real-time Model Data Structure */
struct tag_RTM_ecu_relay_T {
  const char_T * volatile errorStatus;
  DW_ecu_relay_T *dwork;
};

/* Model entry point functions */
extern void ecu_relay_initialize(RT_MODEL_ecu_relay_T *const ecu_relay_M,
  uint8_T *ecu_relay_U_ignition, uint8_T *ecu_relay_U_stopped, uint8_T
  *ecu_relay_U_written, uint8_T *ecu_relay_Y_relay, uint8_T
  *ecu_relay_Y_afterrun, uint8_T *ecu_relay_Y_save);
extern void ecu_relay_step(RT_MODEL_ecu_relay_T *const ecu_relay_M, uint8_T
  ecu_relay_U_ignition, uint8_T ecu_relay_U_stopped, uint8_T ecu_relay_U_written,
  uint8_T *ecu_relay_Y_relay, uint8_T *ecu_relay_Y_afterrun, uint8_T
  *ecu_relay_Y_save);

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
 * '<Root>' : 'ecu_relay'
 * '<S1>'   : 'ecu_relay/MainRelay'
 */
#endif                                 /* ecu_relay_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
