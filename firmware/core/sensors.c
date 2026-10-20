#include <math.h>
#include "sensors.h"

const uint32_t sens_spn[S_N] = { 110, 100, 157, 102, 27 };
const float sens_default[S_N] = { 90.0f, 300.0f, 1000.0f, 100.0f, 0.0f };
const float sens_v_lo[S_N] = { 0.1f, 0.2f, 0.2f, 0.2f, 0.2f };

/* 0.5-4.5 V linear spans (assumed): oil, rail, boost, EGR */
static const float span_lo[S_N] = { 0, 0, 0, 50.0f, 0 };
static const float span_hi[S_N] = { 0, 1000.0f, 1800.0f, 400.0f, 100.0f };

static float trim_g[S_N + 1] = { 1, 1, 1, 1, 1, 1 };
static float trim_o[S_N + 1];

void sens_trim(const float gain[S_N + 1], const float offset[S_N + 1])
{
    for (int i = 0; i <= S_N; i++) {
        trim_g[i] = gain[i];
        trim_o[i] = offset[i];
    }
}

#define NTC_R25 2500.0f             /* assumed: ohms at 20 degC */
#define NTC_BETA 3450.0f
#define NTC_PULLUP 2490.0f

float sens_convert(int ch, float v)
{
    if (ch == S_CLT) {
        float r = NTC_PULLUP * v / (5.0f - v);
        return 1.0f / (1.0f / 293.15f + logf(r / NTC_R25) / NTC_BETA) - 273.15f;
    }
    return span_lo[ch] + (v - 0.5f) / 4.0f * (span_hi[ch] - span_lo[ch]);
}

void sens_reset(sens_t *s)
{
    for (int i = 0; i < S_N; i++) {
        s->val[i] = sens_default[i];
        s->bad_ms[i] = 0;
        s->fmi[i] = 0;
    }
}

void sens_step_1ms(sens_t *s, const float v[S_N], float v_5v)
{
    v_5v = v_5v * trim_g[S_N] + trim_o[S_N];
    if (!(v_5v >= 4.5f && v_5v <= 5.5f))   /* supply fault: use nominal */
        v_5v = 5.0f;
    for (int i = 0; i < S_N; i++) {
        float vr = (v[i] * trim_g[i] + trim_o[i]) * 5.0f / v_5v;
        uint8_t now = !(vr <= SENS_V_HI) ? 3 : vr < sens_v_lo[i] ? 4 : 0;   /* NaN reads high */
        /* bad_ms counts time spent disagreeing with the latched state */
        if ((now != 0) != (s->fmi[i] != 0)) {
            if (++s->bad_ms[i] >= SENS_FAULT_MS) {
                s->fmi[i] = now;
                s->bad_ms[i] = 0;
            }
        } else {
            s->bad_ms[i] = 0;
            if (now)
                s->fmi[i] = now;
        }
        /* while a reading is out of range, hold the last good value: the
         * debounce delays the fault code, never lets a bad value through */
        if (s->fmi[i])
            s->val[i] = sens_default[i];
        else if (!now)
            s->val[i] = sens_convert(i, vr);
    }
}
