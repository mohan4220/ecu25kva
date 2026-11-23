#include "actuate.h"
#include "table.h"

/* EGR target by fuel: zero everywhere until calibrated (actuate.h) */
static const float EGR_Q[] = { 0.0f, 45.0f };
static const float EGR_T[] = { 0.0f, 0.0f };

float egr_target_pct(float fuel_mg)
{
    return table_lookup(EGR_Q, EGR_T, (int)(sizeof EGR_Q / sizeof EGR_Q[0]), fuel_mg);
}

float mu_ff(float cmd, float v_bat)
{
    float vb = (v_bat >= MU_VBAT_MIN && v_bat <= MU_VBAT_MAX) ? v_bat : MU_V_NOM;
    float d = cmd * (MU_V_FULL / vb);
    return d < 0 ? 0 : d > 1 ? 1 : d;
}

float mu_r_learn(float r, float duty, float v_bat, float i_meas)
{
    if (!(v_bat >= MU_VBAT_MIN && v_bat <= MU_VBAT_MAX) || !(i_meas >= MU_R_LEARN_A)
        || !(duty > 0.05f && duty < 0.95f))
        return r;
    float x = duty * v_bat / i_meas;
    x = x < MU_R_LO ? MU_R_LO : x > MU_R_HI ? MU_R_HI : x;
    return r + (x - r) * MU_R_ALPHA;
}

float mu_fallback_cmd(float cmd, float r)
{
    r = r < MU_R_LO ? MU_R_LO : r > MU_R_HI ? MU_R_HI : r;
    return cmd * (r / MU_R_NOM);
}

#ifndef ECU_MODEL    /* else generated: model/ecu_mucur.slx, ecu_egrpos.slx, via model_glue.c */
static float clampf(float x, float lo, float hi) { return x < lo ? lo : x > hi ? hi : x; }

void mu_reset(mu_t *m) { m->integ = 0; }

float mu_step(mu_t *m, float cmd, float i_meas, uint8_t valid, float v_bat, float dt_s)
{
    float vb = (v_bat >= MU_VBAT_MIN && v_bat <= MU_VBAT_MAX) ? v_bat : MU_V_NOM;
    float ff = cmd * (MU_V_FULL / vb);             /* a nominal coil carries cmd * MU_I_FULL */
    if (!valid) {
        m->integ = 0;
        return clampf(ff, 0, 1);
    }
    float err = cmd - i_meas / MU_I_FULL;           /* in units of MU_I_FULL */
    float out = ff + m->integ + MU_KP * err;
    /* integrate unless that pushes further into a limit */
    if (!((out >= 1.0f && err > 0) || (out <= 0.0f && err < 0)))
        m->integ = clampf(m->integ + MU_KI * err * dt_s, -MU_INTEG_MAX, MU_INTEG_MAX);
    return clampf(ff + m->integ + MU_KP * err, 0, 1);
}

void egrp_reset(egrp_t *e) { e->integ = e->prev = e->dfilt = 0; }

float egrp_step(egrp_t *e, float target, float pos, uint8_t enable, float dt_s)
{
    float dpos = (pos - e->prev) / dt_s;
    e->prev = pos;
    if (!enable || target <= EGR_CLOSED_PCT) {     /* coast: the spring closes it */
        e->integ = 0;
        e->dfilt = 0;
        return 0;
    }
    e->dfilt = e->dfilt + EGR_D_ALPHA * (dpos - e->dfilt);
    float err = target - pos;
    float out = EGR_KP * err + e->integ - EGR_KD * e->dfilt;
    if (!((out >= EGR_DUTY_MAX && err > 0) || (out <= -EGR_DUTY_MAX && err < 0)))
        e->integ = clampf(e->integ + EGR_KI * err * dt_s, -EGR_DUTY_MAX, EGR_DUTY_MAX);
    return clampf(EGR_KP * err + e->integ - EGR_KD * e->dfilt, -EGR_DUTY_MAX, EGR_DUTY_MAX);
}
#endif
