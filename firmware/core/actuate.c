#include "actuate.h"
#include "diag.h"
#include "rail.h"
#include "table.h"

/* EGR target by fuel: zero everywhere until calibrated (actuate.h).
 * The table stays here (ecu_params reads it into model/ecu_egrtgt.slx). */
#ifndef ECU_MODEL    /* else generated: model/ecu_egrtgt.slx, via model_glue.c */
static const float EGR_Q[] = { 0.0f, 45.0f };
static const float EGR_T[] = { 0.0f, 0.0f };

float egr_target_pct(float fuel_mg)
{
    return table_lookup(EGR_Q, EGR_T, (int)(sizeof EGR_Q / sizeof EGR_Q[0]), fuel_mg);
}
#endif

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

void mu_sup_reset(mu_sup_t *s)
{
    s->r = MU_R_NOM;
    s->bad_ms = 0;
}

#ifndef ECU_MODEL    /* else generated: model/ecu_musup.slx, ecu_muclose.slx, via model_glue.c */
float mu_sup_step(mu_sup_t *s, float cmd, float duty_prev, float v_bat, float i_mu,
                  uint8_t i_valid, uint8_t act_open, uint8_t act_over, uint8_t *meas)
{
    /* an impossible reading stops being trusted after MU_DISTRUST_MS, not
     * after the DTC's 500 ms: in scenario 19 (23 Nov) a reading lost at
     * 20 kW wound the integral up for those 500 ms and drew 3.7 A from a
     * cold coil */
    uint8_t odd = i_valid && ((DG_MU_DRIVEN(duty_prev, v_bat) && i_mu < DG_MU_OPEN_A)
                              || i_mu > DG_MU_MAX_A);
    s->bad_ms = odd ? (s->bad_ms < 0xFFFFu ? (uint16_t)(s->bad_ms + 1) : s->bad_ms) : 0;
    uint8_t m = i_valid && s->bad_ms < MU_DISTRUST_MS && !act_open && !act_over;
    if (m)
        s->r = mu_r_learn(s->r, duty_prev, v_bat, i_mu);
    *meas = m;
    return m ? cmd : mu_fallback_cmd(cmd, s->r);
}

float mu_close_duty(float r, float v_bat)
{
    return mu_ff(mu_fallback_cmd(METER_CLOSED, r), v_bat);
}
#endif

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
