#ifndef ADC_H
#define ADC_H
#include <stdint.h>
#include "stm32g4xx.h"

void adc_init(void);                  /* ADC1 (injector shunts), ADC2/ADC3 scans running */
float adc_pin_v(int idx);             /* ADC2 scan entry AN_*, volts at the pin */
float adc3_pin_v(int idx);            /* ADC3 scan entry */
float adc_vdda(void);                 /* the measured 3V3_A, from VREFINT */
void  adc_mu_init(void);              /* ISNS_MU: ADC2 injected, triggered by TIM20 TRGO */
float adc_mu_amps(void);              /* the last mid-on-time sample, A */
void adc_calibrate_enable(ADC_TypeDef *a);

#endif
