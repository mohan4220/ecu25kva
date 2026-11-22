#include <math.h>
#include "sensors.h"

const uint32_t sens_spn[S_N] = { 110, 100, 157, 102, 27 };
const float sens_default[S_N] = { 90.0f, 300.0f, 1000.0f, 100.0f, 0.0f };
const float sens_v_lo[S_N] = { 0.1f, 0.2f, 0.2f, 0.2f, 0.2f };

/* 0.5-4.5 V linear spans (assumed): oil, rail, boost, EGR. The rail's
 * 1800 bar is the part's own range (Bosch 0 281 006 425, an 1800 bar
 * RDS4-family sensor; decisions log 30); its curve is still assumed.
 * The oil's 0-10 bar, 0.5-4.5 V is the part's own data sheet: Honeywell
 * PX3AN2BF010BSDAX, sealed gauge, diagnostics on (decisions log 31). */
static const float span_lo[S_N] = { 0, 0, 0, 50.0f, 0 };
static const float span_hi[S_N] = { 0, 1000.0f, 1800.0f, 400.0f, 100.0f };

#ifndef ECU_MODEL    /* else generated: model/ecu_sensors.slx, via model_glue.c */
static float trim_g[S_N + 1] = { 1, 1, 1, 1, 1, 1 };
static float trim_o[S_N + 1];

void sens_trim(const float gain[S_N + 1], const float offset[S_N + 1])
{
    for (int i = 0; i <= S_N; i++) {
        trim_g[i] = gain[i];
        trim_o[i] = offset[i];
    }
}

#endif

#define NTC_PULLUP 2490.0f
#define NTC_N 20

/* The coolant sensor, Bosch 0 281 002 209 (owner, 22 Nov 2026; decisions
 * log 32): NTC, 2.5 kohm +/-6 % at 20 degC. Bosch's characteristic for its
 * 2.5 kohm NTC family (NTC M12-H), -40..150 degC. Interpolated in ln(R),
 * which is close to how an NTC behaves between points. The beta law used
 * until 22 Nov (beta 3450) read 2.8 degC high at 100 degC and 3.9 at 110:
 * the DSE warns at 100 and stops at 104 on the temperature this sends. */
static const float ntc_t[NTC_N] = { -40, -30, -20, -10, 0, 10, 20, 30, 40, 50,
                                    60, 70, 80, 90, 100, 110, 120, 130, 140, 150 };
static const float ntc_r[NTC_N] = { 45313, 26114, 15462, 9397, 5896, 3792, 2500, 1707, 1175, 834,
                                    596, 436, 323, 243, 187, 144, 113, 89, 71, 57 };

static float ntc_degc(float r)
{
    if (!(r < ntc_r[0]))                  /* colder than the table, or NaN */
        return ntc_t[0];
    if (r <= ntc_r[NTC_N - 1])
        return ntc_t[NTC_N - 1];
    int k = 0;
    while (r <= ntc_r[k + 1])
        k++;
    return ntc_t[k] + (ntc_t[k + 1] - ntc_t[k]) * (logf(ntc_r[k] / r) / logf(ntc_r[k] / ntc_r[k + 1]));
}

float sens_convert(int ch, float v)
{
    if (ch == S_CLT) {
        float r = NTC_PULLUP * v / (5.0f - v);
        return ntc_degc(r);
    }
    return span_lo[ch] + (v - 0.5f) / 4.0f * (span_hi[ch] - span_lo[ch]);
}

#ifndef ECU_MODEL
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
#endif
