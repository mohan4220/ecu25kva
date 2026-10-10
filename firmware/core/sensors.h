/* Sensor volts -> engineering units, with range faults.
 * All transfer functions are placeholders (assumed) until each real
 * front-end is characterised; sens_convert is the one place to change. */
#ifndef SENSORS_H
#define SENSORS_H

#include <stdint.h>

enum { S_CLT, S_OIL, S_RAIL, S_BOOST, S_EGR, S_N };

extern const float sens_v_lo[S_N];  /* below: FMI 4 (CLT lower: 0.2 V is still a real 129 degC) */
#define SENS_V_HI 4.8f              /* above: FMI 3 */
#define SENS_FAULT_MS 100           /* out of range this long to set, in range to clear */

typedef struct {
    float val[S_N];                 /* degC, kPa, bar, kPa abs, % */
    uint16_t bad_ms[S_N];
    uint8_t fmi[S_N];               /* 0 ok, 3 high, 4 low */
} sens_t;

extern const uint32_t sens_spn[S_N];
extern const float sens_default[S_N];

void  sens_reset(sens_t *s);
void  sens_step_1ms(sens_t *s, const float v[S_N], float v_5v);
float sens_convert(int ch, float v_ratiometric);

#endif
