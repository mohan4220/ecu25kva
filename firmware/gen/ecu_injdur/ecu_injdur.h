/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_injdur.h
 *
 * Code generated for Simulink model 'ecu_injdur'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Fri Nov 13 16:47:33 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#ifndef ecu_injdur_h_
#define ecu_injdur_h_
#ifndef ecu_injdur_COMMON_INCLUDES_
#define ecu_injdur_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* ecu_injdur_COMMON_INCLUDES_ */

#include "ecu_injdur_types.h"
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
struct tag_RTM_ecu_injdur_T {
  const char_T * volatile errorStatus;
};

/* Model entry point functions */
extern void ecu_injdur_initialize(RT_MODEL_ecu_injdur_T *const ecu_injdur_M,
  real32_T *ecu_injdur_U_fuel_mg, real32_T *ecu_injdur_U_rail_bar, uint32_T
  *ecu_injdur_Y_dur_us);
extern void ecu_injdur_step(RT_MODEL_ecu_injdur_T *const ecu_injdur_M, real32_T
  ecu_injdur_U_fuel_mg, real32_T ecu_injdur_U_rail_bar, uint32_T
  *ecu_injdur_Y_dur_us);

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
 * '<Root>' : 'ecu_injdur'
 */
#endif                                 /* ecu_injdur_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
