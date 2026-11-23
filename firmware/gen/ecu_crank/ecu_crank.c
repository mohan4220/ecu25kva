/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: ecu_crank.c
 *
 * Code generated for Simulink model 'ecu_crank'.
 *
 * Model version                  : 1.1
 * Simulink Coder version         : 26.1 (R2026a) 20-Nov-2025
 * C/C++ source code generated on : Tue Nov 24 00:58:40 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "ecu_crank.h"
#include "rtwtypes.h"
#include <string.h>

/* Model step function */
void ecu_crank_step(RT_MODEL_ecu_crank_T *const ecu_crank_M, uint8_T
                    ecu_crank_U_ev, uint32_T ecu_crank_U_t_us, uint32_T
                    ecu_crank_U_a_in[8], uint8_T ecu_crank_U_b_in[33], uint32_T
                    ecu_crank_Y_a[8], uint8_T ecu_crank_Y_b[33])
{
  int32_T i;
  uint32_T period;
  uint32_T qY;
  int8_T nxt;
  boolean_T agrees;
  boolean_T gap;
  boolean_T guard1;
  boolean_T missed;
  boolean_T tmp;
  for (i = 0; i < 8; i++) {
    /* Outport: '<Root>/a' incorporates:
     *  Inport: '<Root>/a_in'
     *  MATLAB Function: '<Root>/step'
     */
    ecu_crank_Y_a[i] = ecu_crank_U_a_in[i];
  }

  /* MATLAB Function: '<Root>/step' incorporates:
   *  Inport: '<Root>/a_in'
   *  Inport: '<Root>/b_in'
   *  Inport: '<Root>/ev'
   *  Inport: '<Root>/t_us'
   *  Outport: '<Root>/a'
   */
  for (i = 0; i < 33; i++) {
    ecu_crank_Y_b[i] = ecu_crank_U_b_in[i];
  }

  switch (ecu_crank_U_ev) {
   case 0U:
    if (ecu_crank_U_b_in[8] == 0) {
      ecu_crank_Y_b[8] = 1U;
      ecu_crank_Y_a[0] = ecu_crank_U_t_us;
    } else {
      if (ecu_crank_U_t_us >= ecu_crank_U_a_in[0]) {
        period = ecu_crank_U_t_us -
          /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
          /*MW:OvSatOk*/ ecu_crank_U_a_in[0];
        if (period > ecu_crank_U_t_us) {
          period = 0U;
        }
      } else {
        qY = (ecu_crank_U_t_us - ecu_crank_U_a_in[0]) + MAX_uint32_T;
        if (qY < ecu_crank_U_t_us) {
          qY = MAX_uint32_T;
        }

        period = qY + /*MW:OvSatOk*/ 1U;
        if (qY + 1U < qY) {
          period = MAX_uint32_T;
        }
      }

      if (period > 50000U) {
        if (ecu_crank_U_b_in[11] != 0) {
          ecu_crank_Y_b[14] = 2U;
        }

        ecu_crank_Y_b[11] = 0U;
        ecu_crank_Y_b[12] = 0U;
        ecu_crank_Y_a[1] = 0U;
        ecu_crank_Y_b[6] = 0U;
        ecu_crank_Y_b[7] = 0U;
        ecu_crank_Y_b[10] = 0U;
        ecu_crank_Y_b[9] = 0U;
        ecu_crank_Y_b[15] = 0U;
        ecu_crank_Y_a[0] = ecu_crank_U_t_us;
      } else {
        if (ecu_crank_U_b_in[15] != 0) {
          qY = ecu_crank_U_a_in[1] / 3U;
        } else {
          qY = ecu_crank_U_a_in[1];
        }

        if (period >= (qY >> 1)) {
          qY = (ecu_crank_U_a_in[1] >> 1) + /*MW:OvSatOk*/ ecu_crank_U_a_in[1];
          if (qY < ecu_crank_U_a_in[1]) {
            qY = MAX_uint32_T;
          }

          gap = ((ecu_crank_U_a_in[1] != 0U) && (period > qY));
          ecu_crank_Y_a[ecu_crank_U_b_in[7] + 2] = period;
          if (gap) {
            ecu_crank_Y_b[ecu_crank_U_b_in[7]] = 18U;
          } else {
            ecu_crank_Y_b[ecu_crank_U_b_in[7]] = 6U;
          }

          i = (ecu_crank_U_b_in[7] - (int32_T)((uint32_T)(ecu_crank_U_b_in[7] +
                 1) / 6U) * 6) + 1;
          if (i < 0) {
            i = 0;
          } else if (i > 255) {
            i = 255;
          }

          ecu_crank_Y_b[7] = (uint8_T)i;
          if (ecu_crank_Y_b[6] < 6) {
            qY = ecu_crank_Y_b[6] + 1U;
            if (ecu_crank_Y_b[6] + 1U > 255U) {
              qY = 255U;
            }

            ecu_crank_Y_b[6] = (uint8_T)qY;
          }

          if (gap) {
            agrees = ((ecu_crank_Y_b[10] == 0) || (ecu_crank_Y_b[9] != 57));
            if (agrees) {
              if (ecu_crank_Y_b[11] != 0) {
                ecu_crank_Y_b[14] = 1U;
              }

              ecu_crank_Y_b[11] = 0U;
              ecu_crank_Y_b[12] = 0U;
              ecu_crank_Y_b[6] = 0U;
            } else if (ecu_crank_Y_b[11] == 0) {
              ecu_crank_Y_b[11] = 1U;
            }

            ecu_crank_Y_b[10] = 1U;
            ecu_crank_Y_b[9] = 0U;
            if (agrees) {
              ecu_crank_Y_b[28] = 0U;
              ecu_crank_Y_b[13] ^= 1;
            } else {
              nxt = -1;
              missed = false;
              if (ecu_crank_Y_b[29] != 0) {
                if (ecu_crank_Y_b[17] > ecu_crank_Y_b[23]) {
                  qY = (uint32_T)ecu_crank_Y_b[17] -
                    /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
                    /*MW:OvSatOk*/ ecu_crank_Y_b[23];
                  if (qY > ecu_crank_Y_b[17]) {
                    qY = 0U;
                  }

                  agrees = (qY <= 2U);
                } else {
                  qY = (uint32_T)ecu_crank_Y_b[23] -
                    /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
                    /*MW:OvSatOk*/ ecu_crank_Y_b[17];
                  if (qY > ecu_crank_Y_b[23]) {
                    qY = 0U;
                  }

                  agrees = (qY <= 2U);
                }

                if (ecu_crank_Y_b[18] > ecu_crank_Y_b[24]) {
                  qY = (uint32_T)ecu_crank_Y_b[18] -
                    /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
                    /*MW:OvSatOk*/ ecu_crank_Y_b[24];
                  if (qY > ecu_crank_Y_b[18]) {
                    qY = 0U;
                  }

                  tmp = (qY <= 2U);
                } else {
                  qY = (uint32_T)ecu_crank_Y_b[24] -
                    /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
                    /*MW:OvSatOk*/ ecu_crank_Y_b[18];
                  if (qY > ecu_crank_Y_b[24]) {
                    qY = 0U;
                  }

                  tmp = (qY <= 2U);
                }

                guard1 = false;
                if ((ecu_crank_Y_b[16] == ecu_crank_Y_b[22]) && ((ecu_crank_Y_b
                      [16] == 0) || (agrees && tmp))) {
                  nxt = 0;
                  guard1 = true;
                } else {
                  if (ecu_crank_Y_b[17] > ecu_crank_Y_b[26]) {
                    qY = (uint32_T)ecu_crank_Y_b[17] -
                      /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
                      /*MW:OvSatOk*/ ecu_crank_Y_b[26];
                    if (qY > ecu_crank_Y_b[17]) {
                      qY = 0U;
                    }

                    agrees = (qY <= 2U);
                  } else {
                    qY = (uint32_T)ecu_crank_Y_b[26] -
                      /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
                      /*MW:OvSatOk*/ ecu_crank_Y_b[17];
                    if (qY > ecu_crank_Y_b[26]) {
                      qY = 0U;
                    }

                    agrees = (qY <= 2U);
                  }

                  if (ecu_crank_Y_b[18] > ecu_crank_Y_b[27]) {
                    qY = (uint32_T)ecu_crank_Y_b[18] -
                      /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
                      /*MW:OvSatOk*/ ecu_crank_Y_b[27];
                    if (qY > ecu_crank_Y_b[18]) {
                      qY = 0U;
                    }

                    tmp = (qY <= 2U);
                  } else {
                    qY = (uint32_T)ecu_crank_Y_b[27] -
                      /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
                      /*MW:OvSatOk*/ ecu_crank_Y_b[18];
                    if (qY > ecu_crank_Y_b[27]) {
                      qY = 0U;
                    }

                    tmp = (qY <= 2U);
                  }

                  if ((ecu_crank_Y_b[16] == ecu_crank_Y_b[25]) &&
                      ((ecu_crank_Y_b[16] == 0) || (agrees && tmp))) {
                    nxt = 1;
                    guard1 = true;
                  } else {
                    missed = true;
                    ecu_crank_Y_b[32] = 0U;
                    if (ecu_crank_Y_b[30] == 0) {
                      ecu_crank_Y_b[29] = 0U;
                    } else {
                      i = (ecu_crank_Y_b[31] - (((ecu_crank_Y_b[31] + 1) >> 8) <<
                            8)) + 1;
                      if (i < 0) {
                        i = 0;
                      } else if (i > 255) {
                        i = 255;
                      }

                      ecu_crank_Y_b[31] = (uint8_T)i;
                      if (ecu_crank_Y_b[31] >= 2) {
                        ecu_crank_Y_b[29] = 0U;
                      }
                    }
                  }
                }

                if (guard1) {
                  i = (ecu_crank_Y_b[32] - (((ecu_crank_Y_b[32] + 1) >> 8) << 8))
                    + 1;
                  if (i < 0) {
                    i = 0;
                  } else if (i > 255) {
                    i = 255;
                  }

                  ecu_crank_Y_b[32] = (uint8_T)i;
                  if (ecu_crank_Y_b[32] >= 2) {
                    ecu_crank_Y_b[32] = 2U;
                    ecu_crank_Y_b[30] = 1U;
                    ecu_crank_Y_b[31] = 0U;
                  }
                }
              }

              if ((ecu_crank_Y_b[29] == 0) && (ecu_crank_Y_b[28] != 0) &&
                  !missed) {
                guard1 = false;
                if (ecu_crank_Y_b[16] != ecu_crank_Y_b[19]) {
                  nxt = (int8_T)(ecu_crank_Y_b[16] > ecu_crank_Y_b[19]);
                  guard1 = true;
                } else if (ecu_crank_Y_b[16] == 0) {
                } else {
                  if (ecu_crank_Y_b[17] > ecu_crank_Y_b[20]) {
                    qY = (uint32_T)ecu_crank_Y_b[17] -
                      /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
                      /*MW:OvSatOk*/ ecu_crank_Y_b[20];
                    if (qY > ecu_crank_Y_b[17]) {
                      qY = 0U;
                    }

                    agrees = (qY <= 2U);
                  } else {
                    qY = (uint32_T)ecu_crank_Y_b[20] -
                      /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
                      /*MW:OvSatOk*/ ecu_crank_Y_b[17];
                    if (qY > ecu_crank_Y_b[20]) {
                      qY = 0U;
                    }

                    agrees = (qY <= 2U);
                  }

                  if (!agrees) {
                    nxt = (int8_T)(ecu_crank_Y_b[17] < ecu_crank_Y_b[20]);
                    guard1 = true;
                  } else {
                    if (ecu_crank_Y_b[18] > ecu_crank_Y_b[21]) {
                      qY = (uint32_T)ecu_crank_Y_b[18] -
                        /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
                        /*MW:OvSatOk*/ ecu_crank_Y_b[21];
                      if (qY > ecu_crank_Y_b[18]) {
                        qY = 0U;
                      }

                      agrees = (qY <= 2U);
                    } else {
                      qY = (uint32_T)ecu_crank_Y_b[21] -
                        /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
                        /*MW:OvSatOk*/ ecu_crank_Y_b[18];
                      if (qY > ecu_crank_Y_b[21]) {
                        qY = 0U;
                      }

                      agrees = (qY <= 2U);
                    }

                    if (!agrees) {
                      nxt = (int8_T)(ecu_crank_Y_b[18] < ecu_crank_Y_b[21]);
                      guard1 = true;
                    }
                  }
                }

                if (guard1) {
                  if (nxt != 0) {
                    ecu_crank_Y_b[22] = ecu_crank_Y_b[16];
                    ecu_crank_Y_b[25] = ecu_crank_Y_b[19];
                    ecu_crank_Y_b[23] = ecu_crank_Y_b[17];
                    ecu_crank_Y_b[26] = ecu_crank_Y_b[20];
                    ecu_crank_Y_b[24] = ecu_crank_Y_b[18];
                    ecu_crank_Y_b[27] = ecu_crank_Y_b[21];
                    nxt = 0;
                  } else {
                    ecu_crank_Y_b[22] = ecu_crank_Y_b[19];
                    ecu_crank_Y_b[25] = ecu_crank_Y_b[16];
                    ecu_crank_Y_b[23] = ecu_crank_Y_b[20];
                    ecu_crank_Y_b[26] = ecu_crank_Y_b[17];
                    ecu_crank_Y_b[24] = ecu_crank_Y_b[21];
                    ecu_crank_Y_b[27] = ecu_crank_Y_b[18];
                    nxt = 1;
                  }

                  ecu_crank_Y_b[29] = 1U;
                  ecu_crank_Y_b[30] = 0U;
                  ecu_crank_Y_b[31] = 0U;
                  ecu_crank_Y_b[32] = 0U;
                }
              }

              if (nxt < 0) {
                ecu_crank_Y_b[12] = 0U;
                ecu_crank_Y_b[13] ^= 1;
              } else {
                agrees = ((ecu_crank_Y_b[12] == 0) || ((int32_T)((uint32_T)nxt ^
                            1U) == ecu_crank_Y_b[13]));
                ecu_crank_Y_b[13] = (uint8_T)nxt;
                ecu_crank_Y_b[12] = (uint8_T)((ecu_crank_Y_b[11] != 0) && agrees);
              }

              ecu_crank_Y_b[19] = ecu_crank_Y_b[16];
              ecu_crank_Y_b[20] = ecu_crank_Y_b[17];
              ecu_crank_Y_b[21] = ecu_crank_Y_b[18];
              ecu_crank_Y_b[28] = (uint8_T)!missed;
            }

            ecu_crank_Y_b[16] = 0U;
            ecu_crank_Y_b[17] = 0U;
            ecu_crank_Y_b[18] = 0U;
          } else {
            i = (ecu_crank_Y_b[9] - (((ecu_crank_Y_b[9] + 1) >> 8) << 8)) + 1;
            if (i < 0) {
              i = 0;
            } else if (i > 255) {
              i = 255;
            }

            ecu_crank_Y_b[9] = (uint8_T)i;
            if (ecu_crank_Y_b[9] >= 58) {
              if (ecu_crank_Y_b[11] != 0) {
                ecu_crank_Y_b[14] = 1U;
              }

              ecu_crank_Y_b[11] = 0U;
              ecu_crank_Y_b[12] = 0U;
              ecu_crank_Y_b[6] = 0U;
              ecu_crank_Y_b[10] = 0U;
            }
          }

          ecu_crank_Y_a[0] = ecu_crank_U_t_us;
          ecu_crank_Y_a[1] = period;
          ecu_crank_Y_b[15] = gap;
        }
      }
    }
    break;

   case 1U:
    if (ecu_crank_U_b_in[16] == 0) {
      ecu_crank_Y_b[17] = ecu_crank_U_b_in[9];
    }

    ecu_crank_Y_b[18] = ecu_crank_U_b_in[9];
    if (ecu_crank_U_b_in[16] < 255) {
      qY = ecu_crank_U_b_in[16] + 1U;
      if (ecu_crank_U_b_in[16] + 1U > 255U) {
        qY = 255U;
      }

      ecu_crank_Y_b[16] = (uint8_T)qY;
    }
    break;

   case 2U:
    if (ecu_crank_U_t_us >= ecu_crank_U_a_in[0]) {
      period = ecu_crank_U_t_us -
        /*MW:operator MISRA2012:D4.1 CERT-C:INT30-C 'Justifying MISRA C rule violation'*/
        /*MW:OvSatOk*/ ecu_crank_U_a_in[0];
      if (period > ecu_crank_U_t_us) {
        period = 0U;
      }
    } else {
      qY = (ecu_crank_U_t_us - ecu_crank_U_a_in[0]) + MAX_uint32_T;
      if (qY < ecu_crank_U_t_us) {
        qY = MAX_uint32_T;
      }

      period = qY + /*MW:OvSatOk*/ 1U;
      if (qY + 1U < qY) {
        period = MAX_uint32_T;
      }
    }

    if ((ecu_crank_U_b_in[11] != 0) && ((period > 50000U) && (period <=
          2147483647U))) {
      if (ecu_crank_U_b_in[11] != 0) {
        ecu_crank_Y_b[14] = 2U;
      }

      ecu_crank_Y_b[11] = 0U;
      ecu_crank_Y_b[12] = 0U;
      ecu_crank_Y_b[6] = 0U;
    }
    break;
  }

  UNUSED_PARAMETER(ecu_crank_M);
}

/* Model initialize function */
void ecu_crank_initialize(RT_MODEL_ecu_crank_T *const ecu_crank_M, uint8_T
  *ecu_crank_U_ev, uint32_T *ecu_crank_U_t_us, uint32_T ecu_crank_U_a_in[8],
  uint8_T ecu_crank_U_b_in[33], uint32_T ecu_crank_Y_a[8], uint8_T
  ecu_crank_Y_b[33])
{
  /* Registration code */

  /* initialize error status */
  rtmSetErrorStatus(ecu_crank_M, (NULL));

  /* external inputs */
  (void)memset(&ecu_crank_U_a_in[0], 0, sizeof(uint32_T) << 3U);
  (void)memset(&ecu_crank_U_b_in[0], 0, 33U * sizeof(uint8_T));
  *ecu_crank_U_ev = 0U;
  *ecu_crank_U_t_us = 0U;

  /* external outputs */
  (void)memset(&ecu_crank_Y_a[0], 0, sizeof(uint32_T) << 3U);
  (void)memset(&ecu_crank_Y_b[0], 0, 33U * sizeof(uint8_T));
  UNUSED_PARAMETER(ecu_crank_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
