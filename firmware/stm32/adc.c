/* The sensor ADCs. ADC2 scans the sensors and currents, ADC3 the 5 V
 * monitor, the barometer and VREFINT; each runs continuously into a DMA
 * buffer with 16x hardware oversampling, so the 1 ms tick reads the last
 * averaged value of every channel without waiting. ADC1 belongs to the
 * injector stage (inj_hw.c), and is only calibrated and enabled here.
 *
 * Sequence as ST's HAL and RM0440 sec. 21.4: leave deep power-down,
 * regulator on and 20 us, single-ended calibration, 4 ADC clocks, enable. */
#include "hw.h"
#include "adc.h"

#define VREFINT_CAL (*(const uint16_t *)0x1FFF75AAu)   /* at VREF+ = 3.000 V, 30 C */
#define DMAREQ_ADC2 36u                                /* DMAMUX request IDs (HAL) */
#define DMAREQ_ADC3 37u

static volatile uint16_t buf2[AN_N2], buf3[AN_N3];
static const uint8_t ch2[AN_N2] = ADC2_CHANNELS, ch3[AN_N3] = ADC3_CHANNELS;

void adc_calibrate_enable(ADC_TypeDef *a)
{
    a->CR = 0;                                    /* DEEPPWD off */
    a->CR = ADC_CR_ADVREGEN;
    delay_us(25);
    a->CR |= ADC_CR_ADCAL;                        /* ADCALDIF = 0: single-ended */
    while (a->CR & ADC_CR_ADCAL) {}
    delay_us(1);
    a->ISR = ADC_ISR_ADRDY;
    a->CR |= ADC_CR_ADEN;
    while (!(a->ISR & ADC_ISR_ADRDY)) {}
    a->ISR = ADC_ISR_ADRDY;
}

/* every channel's sample time to `code` (SMPR1: 0-9, SMPR2: 10-18) */
static void smp_all(ADC_TypeDef *a, uint32_t code)
{
    uint32_t s1 = 0, s2 = 0;
    for (int i = 0; i < 10; i++)
        s1 |= code << (3 * i);
    for (int i = 0; i < 9; i++)
        s2 |= code << (3 * i);
    a->SMPR1 = s1;
    a->SMPR2 = s2;
}

static void sequence(ADC_TypeDef *a, const uint8_t *ch, int n)
{
    volatile uint32_t *sqr[4] = { &a->SQR1, &a->SQR2, &a->SQR3, &a->SQR4 };
    uint32_t v[4] = { (uint32_t)(n - 1), 0, 0, 0 };
    for (int i = 0; i < n; i++) {
        int slot = i + 1;                         /* SQ1 sits after L in SQR1 */
        v[slot / 5] |= (uint32_t)ch[i] << (6 * (slot % 5));
    }
    for (int i = 0; i < 4; i++)
        *sqr[i] = v[i];
}

static void scan(ADC_TypeDef *a, DMA_Channel_TypeDef *d, DMAMUX_Channel_TypeDef *mx, uint32_t req,
                 const uint8_t *ch, volatile uint16_t *dst, int n)
{
    sequence(a, ch, n);
    /* continuous, DMA circular, overwrite on overrun, 12 bits right */
    a->CFGR = ADC_CFGR_CONT | ADC_CFGR_DMAEN | ADC_CFGR_DMACFG | ADC_CFGR_OVRMOD;
    /* 16x oversampling, shift 4: still 12 bits, 4x less noise */
    a->CFGR2 = ADC_CFGR2_ROVSE | (3u << ADC_CFGR2_OVSR_Pos) | (4u << ADC_CFGR2_OVSS_Pos);
    mx->CCR = req;
    d->CCR = 0;
    d->CPAR = (uint32_t)(uintptr_t)&a->DR;
    d->CMAR = (uint32_t)(uintptr_t)dst;
    d->CNDTR = (uint32_t)n;
    d->CCR = DMA_CCR_MINC | DMA_CCR_CIRC | DMA_CCR_PSIZE_0 | DMA_CCR_MSIZE_0 | DMA_CCR_PL_1 | DMA_CCR_EN;
    a->CR |= ADC_CR_ADSTART;
}

void adc_init(void)
{
    RCC->AHB2ENR |= RCC_AHB2ENR_ADC12EN | RCC_AHB2ENR_ADC345EN;
    RCC->AHB1ENR |= RCC_AHB1ENR_DMA1EN | RCC_AHB1ENR_DMAMUX1EN;
    (void)RCC->AHB1ENR;
    /* synchronous clock HCLK/4 = 42.5 MHz (max 60) */
    ADC12_COMMON->CCR = 3u << ADC_CCR_CKMODE_Pos;
    ADC345_COMMON->CCR = 3u << ADC_CCR_CKMODE_Pos | ADC_CCR_VREFEN;
    delay_us(15);                                 /* VREFINT start-up, 12 us */

    adc_calibrate_enable(ADC1);
    adc_calibrate_enable(ADC2);
    adc_calibrate_enable(ADC3);

    /* ADC2: 47.5 cycles; the sensor dividers are a few k with a capacitor */
    smp_all(ADC2, 4u);
    scan(ADC2, DMA1_Channel1, DMAMUX1_Channel0, DMAREQ_ADC2, ch2, buf2, AN_N2);
    /* ADC3: 640.5 cycles, VREFINT needs 4 us of sampling */
    smp_all(ADC3, 7u);
    scan(ADC3, DMA1_Channel2, DMAMUX1_Channel1, DMAREQ_ADC3, ch3, buf3, AN_N3);
}

float adc_vdda(void)
{
    uint16_t r = buf3[AN_VREFINT];
    if (r == 0)
        return VDDA_NOM;
    float v = 3.0f * (float)VREFINT_CAL / (float)r;
    return (v > 3.1f && v < 3.5f) ? v : VDDA_NOM;
}

float adc_pin_v(int idx) { return (float)buf2[idx] * adc_vdda() / 4095.0f; }
float adc3_pin_v(int idx) { return (float)buf3[idx] * adc_vdda() / 4095.0f; }
