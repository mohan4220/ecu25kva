/* ECU_MODEL: the control functions, from code Embedded Coder generated
 * out of the Simulink/Stateflow models in model/ (firmware/gen/).
 *
 * Each function keeps the hand-written API (govern.h, rail.h, inject.h,
 * safety.h), so the rest of the firmware and every test call the
 * generated code unchanged. The hand-written bodies stay in govern.c,
 * rail.c, inject.c and safety.c as the reference build (ECU_MODEL off).
 *
 * Each model is a reusable function with its state in a DW struct the
 * caller owns (gov_t, rail_t); the stateless ones share one instance.
 * The Stateflow charts (mode.h) are single instances: their reset is the
 * generated initialize, which puts the chart back in its default state. */
#ifdef ECU_MODEL

#include "govern.h"
#include "rail.h"
#include "inject.h"
#include "safety.h"
#include "ecu_railset.h"
#include "ecu_egrtgt.h"
#include "ecu_soi.h"
#include "ecu_injdur.h"
#include "ecu_safety.h"
#include "mode.h"
#include "ecu_mode.h"
#include "ecu_boostg.h"
#include "ecu_boostm.h"
#include "ecu_egrg.h"
#include "ecu_wifg.h"
#include "ecu_underg.h"
#include "ecu_relay.h"
#include "sensors.h"
#include "ecu_sensors.h"
#include "ecu_sensaux.h"
#include "j1939.h"
#include "ecu_j1939.h"
#include "actuate.h"
#include "ecu_spdst.h"
#include "diag.h"
#include "ecu_diag.h"
#include "ecu_musup.h"
#include "ecu_muclose.h"
#include "ecu_lamps.h"
#include "crank.h"
#include "ecu_crank.h"
#include "ecu_crankrd.h"
#include <string.h>

/* ---- governor: model/ecu_gov.slx ----
 * gov_reset is the model's rst input, applied on the next step: the C
 * reset-then-step order. The generated step keeps its previous fuel and
 * setpoint in its own output arguments, so g->fuel and g->set are state. */
void gov_reset(gov_t *g, float fuel0, float rpm0)
{
    g->m.dwork = &g->dw;
    g->fuel0 = fuel0;
    g->rpm0 = rpm0;
    g->rst = 1;
    g->integ = g->fuel = fuel0;          /* as gov_reset leaves them, for readers */
    g->set = rpm0 < GOV_RPM_SET ? rpm0 : GOV_RPM_SET;
}

float gov_step(gov_t *g, float rpm, int droop, int idle, float dt_s)
{
    (void)dt_s;                          /* the model runs at its fixed 1 ms */
    g->m.dwork = &g->dw;                 /* re-bound: survives a struct copy */
    ecu_gov_step(&g->m, rpm, (uint8_t)(droop != 0), g->rst, g->fuel0, g->rpm0,
                 (uint8_t)(idle != 0), &g->fuel, &g->set);
    g->rst = 0;
    g->integ = g->dw.integ_z_DSTATE;
    return g->fuel;
}

/* ---- rail pressure: model/ecu_rail.slx, ecu_railset.slx ---- */
void rail_reset(rail_t *r)
{
    r->m.dwork = &r->dw;
    r->rst = 1;
    r->integ = 0;
}

float rail_step(rail_t *r, float set_bar, float rail_bar, float dt_s)
{
    (void)dt_s;
    float duty;
    r->m.dwork = &r->dw;
    ecu_rail_step(&r->m, set_bar, rail_bar, r->rst, &duty);
    r->rst = 0;
    r->integ = r->dw.integ_z_DSTATE;
    return duty;
}

static RT_MODEL_ecu_railset_T railset_m;
float rail_set_bar(float fuel_mg)
{
    float y;
    ecu_railset_step(&railset_m, fuel_mg, &y);
    return y;
}

/* ---- EGR target: model/ecu_egrtgt.slx ---- */
static RT_MODEL_ecu_egrtgt_T egrtgt_m;
float egr_target_pct(float fuel_mg)
{
    float y;
    ecu_egrtgt_step(&egrtgt_m, fuel_mg, &y);
    return y;
}

/* ---- injection: model/ecu_soi.slx, ecu_injdur.slx ---- */
static RT_MODEL_ecu_soi_T soi_m;
float inject_soi_btdc(float fuel_mg)
{
    float y;
    ecu_soi_step(&soi_m, fuel_mg, &y);
    return y;
}

static RT_MODEL_ecu_injdur_T injdur_m;
uint32_t inject_dur_us(float fuel_mg, float rail_bar)
{
    uint32_t t;
    ecu_injdur_step(&injdur_m, fuel_mg, rail_bar, &t);
    return t;
}

/* ---- trip decision: model/ecu_safety.slx ---- */
static RT_MODEL_ecu_safety_T safety_m;
int safety_check(float rpm, uint8_t crank_fault, uint8_t ignition, int running)
{
    uint8_t why;
    ecu_safety_step(&safety_m, rpm, crank_fault, ignition, (uint8_t)(running != 0), &why);
    return why;
}

/* ---- Stateflow charts. Outputs are kept between calls: a chart only
 * writes an output when its state says so, as the generated code does. ---- */

/* engine mode: model/ecu_mode.slx */
static RT_MODEL_ecu_mode_T mode_m;
static DW_ecu_mode_T mode_dw;
static uint8_t mode_y, mode_up;

uint8_t mode_cmd(uint8_t cmd, uint8_t ignition, uint8_t phased, float rpm)
{
    if (!mode_up) {                      /* first use: the chart at its default, OFF */
        uint8_t c = 0, i = 0, p = 0;
        float r = 0;
        mode_m.dwork = &mode_dw;
        ecu_mode_initialize(&mode_m, &c, &i, &p, &r, &mode_y);
        mode_up = 1;
    }
    ecu_mode_step(&mode_m, cmd, ignition, phased, rpm, &mode_y);
    return mode_y;
}

/* boost guard: model/ecu_boostg.slx */
static RT_MODEL_ecu_boostg_T boostg_m;
static DW_ecu_boostg_T boostg_dw;
static uint8_t boostg_dis, boostg_trip;

void boostg_reset(void)
{
    float v = 0;
    uint8_t sh = 0;
    boostg_m.dwork = &boostg_dw;
    ecu_boostg_initialize(&boostg_m, &v, &sh, &boostg_dis, &boostg_trip);
}

void boostg_step(float v_rail, uint8_t shut, uint8_t *dis, uint8_t *trip)
{
    ecu_boostg_step(&boostg_m, v_rail, shut, &boostg_dis, &boostg_trip);
    *dis = boostg_dis;
    *trip = boostg_trip;
}

/* boost rail warnings: model/ecu_boostm.slx */
static RT_MODEL_ecu_boostm_T boostm_m;
static DW_ecu_boostm_T boostm_dw;
static uint8_t boostm_y[4];

void boostm_reset(void)
{
    float v = 0;
    uint8_t f = 0;
    boostm_m.dwork = &boostm_dw;
    ecu_boostm_initialize(&boostm_m, &v, &f, &boostm_y[0], &boostm_y[1], &boostm_y[2], &boostm_y[3]);
}

void boostm_step(float v_rail, uint8_t fuelling, uint8_t *hi_raise, uint8_t *hi_drop,
                 uint8_t *lo_raise, uint8_t *lo_drop)
{
    ecu_boostm_step(&boostm_m, v_rail, fuelling, &boostm_y[0], &boostm_y[1], &boostm_y[2], &boostm_y[3]);
    *hi_raise = boostm_y[0];
    *hi_drop = boostm_y[1];
    *lo_raise = boostm_y[2];
    *lo_drop = boostm_y[3];
}

/* EGR stall guard: model/ecu_egrg.slx */
static RT_MODEL_ecu_egrg_T egrg_m;
static DW_ecu_egrg_T egrg_dw;
static uint8_t egrg_off, egrg_raise;

void egrg_reset(void)
{
    float i = 0;
    egrg_m.dwork = &egrg_dw;
    ecu_egrg_initialize(&egrg_m, &i, &egrg_off, &egrg_raise);
}

void egrg_step(float i_egr, uint8_t *off, uint8_t *raise)
{
    ecu_egrg_step(&egrg_m, i_egr, &egrg_off, &egrg_raise);
    *off = egrg_off;
    *raise = egrg_raise;
}

/* water in fuel: model/ecu_wifg.slx */
static RT_MODEL_ecu_wifg_T wifg_m;
static DW_ecu_wifg_T wifg_dw;
static uint8_t wifg_raise, wifg_drop;

void wifg_reset(void)
{
    uint8_t w = 0;
    wifg_m.dwork = &wifg_dw;
    ecu_wifg_initialize(&wifg_m, &w, &wifg_raise, &wifg_drop);
}

void wifg_step(uint8_t wif, uint8_t *raise, uint8_t *drop)
{
    ecu_wifg_step(&wifg_m, wif, &wifg_raise, &wifg_drop);
    *raise = wifg_raise;
    *drop = wifg_drop;
}

/* underspeed: model/ecu_underg.slx */
static RT_MODEL_ecu_underg_T underg_m;
static DW_ecu_underg_T underg_dw;
static uint8_t underg_raise, underg_drop;

void underg_reset(void)
{
    float r = 0;
    uint8_t a = 0;
    underg_m.dwork = &underg_dw;
    ecu_underg_initialize(&underg_m, &r, &a, &underg_raise, &underg_drop);
}

void underg_step(float rpm, uint8_t armed, uint8_t *raise, uint8_t *drop)
{
    ecu_underg_step(&underg_m, rpm, armed, &underg_raise, &underg_drop);
    *raise = underg_raise;
    *drop = underg_drop;
}

/* main relay: model/ecu_relay.slx */
static RT_MODEL_ecu_relay_T relay_m;
static DW_ecu_relay_T relay_dw;
static uint8_t relay_y, relay_after, relay_save;

void relay_reset(void)
{
    uint8_t i = 0, s = 0, w = 0;
    relay_m.dwork = &relay_dw;
    ecu_relay_initialize(&relay_m, &i, &s, &w, &relay_y, &relay_after, &relay_save);
}

void relay_step(uint8_t ignition, uint8_t stopped, uint8_t written,
                uint8_t *relay, uint8_t *afterrun, uint8_t *save)
{
    ecu_relay_step(&relay_m, ignition, stopped, written, &relay_y, &relay_after, &relay_save);
    *relay = relay_y;
    *afterrun = relay_after;
    *save = relay_save;
}

/* ---- sensors: model/ecu_sensors.slx ----
 * One instance (ecu.c's). The model keeps the debounce counts, latched
 * FMIs and last values in its own state; sens_t gets a copy each step, so
 * ecu.c reads sens.val / sens.fmi as before. The trims are its inputs. */
static RT_MODEL_ecu_sensors_T sens_m;
static DW_ecu_sensors_T sens_dw;
static float trim_g[S_N + 1] = { 1, 1, 1, 1, 1, 1 };
static float trim_o[S_N + 1];

void sens_trim(const float gain[S_N + 1], const float offset[S_N + 1])
{
    memcpy(trim_g, gain, sizeof trim_g);
    memcpy(trim_o, offset, sizeof trim_o);
}

void sens_reset(sens_t *s)
{
    /* the generated initialize zeroes every array it is given: scratch
     * ones, never the live trims */
    float v[S_N] = { 0 }, v5 = 0, g[S_N + 1], o[S_N + 1];
    sens_m.dwork = &sens_dw;
    ecu_sensors_initialize(&sens_m, v, &v5, g, o, s->val, s->fmi);
    for (int i = 0; i < S_N; i++) {
        s->val[i] = sens_default[i];
        s->bad_ms[i] = 0;
        s->fmi[i] = 0;
    }
}

void sens_step_1ms(sens_t *s, const float v[S_N], float v_5v)
{
    float in[S_N];
    memcpy(in, v, sizeof in);
    sens_m.dwork = &sens_dw;
    ecu_sensors_step(&sens_m, in, v_5v, trim_g, trim_o, s->val, s->fmi);
    for (int i = 0; i < S_N; i++)
        s->bad_ms[i] = sens_dw.bad_z_DSTATE[i];
}

/* ---- pin 79, charge-air temperature: model/ecu_sensaux.slx ----
 * One instance, as the sensors. (decisions log 33, 34) */
static RT_MODEL_ecu_sensaux_T aux_m;
static DW_ecu_sensaux_T aux_dw;

void sens_aux_reset(sens_aux_t *a)
{
    float v = 0, v5 = 0;
    aux_m.dwork = &aux_dw;
    ecu_sensaux_initialize(&aux_m, &v, &v5, &a->val, &a->fmi);
    a->val = SENS_AUX_DEFAULT;
    a->bad_ms = 0;
    a->fmi = 0;
}

void sens_aux_step_1ms(sens_aux_t *a, float v, float v_5v)
{
    aux_m.dwork = &aux_dw;
    ecu_sensaux_step(&aux_m, v, v_5v, &a->val, &a->fmi);
    a->bad_ms = aux_dw.bad_z_DSTATE;
}

/* ---- J1939 periodic PGNs: model/ecu_j1939.slx ("Set PGNs") ----
 * Stateless: every call computes all four and keeps the one asked for.
 * The identifiers stay in C (j1939_id), as does everything that sends. */
static RT_MODEL_ecu_j1939_T j1939_m;

static void pgns(ecu_can *f, int which, uint8_t prio, uint32_t pgn, float rpm, float clt, uint8_t clt_ok,
                 float oil, uint8_t oil_ok, uint32_t engine_s, uint8_t clt_low, float intake, uint8_t intake_ok)
{
    uint8_t y[5][8];
    ecu_j1939_step(&j1939_m, rpm, clt, clt_ok, oil, oil_ok, engine_s, clt_low, intake, intake_ok,
                   y[0], y[1], y[2], y[3], y[4]);
    f->id = j1939_id(prio, pgn, J1939_SA);
    f->len = 8;
    memcpy(f->data, y[which], 8);
}

void j1939_eec1(ecu_can *f, float rpm) { pgns(f, 0, 3, 61444, rpm, 0, 0, 0, 0, 0, 0, 0, 0); }
void j1939_et1(ecu_can *f, float clt_c, int valid) { pgns(f, 1, 6, 65262, 0, clt_c, (uint8_t)(valid != 0), 0, 0, 0, 0, 0, 0); }
void j1939_eflp1(ecu_can *f, float oil_kpa, int valid, int clt_low)
{
    pgns(f, 2, 6, 65263, 0, 0, 0, oil_kpa, (uint8_t)(valid != 0), 0, (uint8_t)(clt_low != 0), 0, 0);
}
void j1939_hours(ecu_can *f, uint32_t engine_s) { pgns(f, 3, 6, PGN_HOURS, 0, 0, 0, 0, 0, engine_s, 0, 0, 0); }
void j1939_ic1(ecu_can *f, float intake_c, int valid) { pgns(f, 4, 6, 65270, 0, 0, 0, 0, 0, 0, 0, intake_c, (uint8_t)(valid != 0)); }

/* ---- the cascades' inner loops: model/ecu_mucur.slx, ecu_egrpos.slx ----
 * State in the caller's struct, as the governor's; integ etc. mirrored
 * for readers. The generated initialize zeroes what it is given: scratch. */
void mu_reset(mu_t *m)
{
    float a = 0, b = 0, d = 0, y = 0;
    uint8_t v = 0;
    m->m.dwork = &m->dw;
    ecu_mucur_initialize(&m->m, &a, &b, &v, &d, &y);
    m->integ = 0;
}

float mu_step(mu_t *m, float cmd, float i_meas, uint8_t valid, float v_bat, float dt_s)
{
    float y;
    (void)dt_s;
    m->m.dwork = &m->dw;
    ecu_mucur_step(&m->m, cmd, i_meas, valid, v_bat, &y);
    m->integ = m->dw.integ_z_DSTATE;
    return y;
}

void egrp_reset(egrp_t *e)
{
    float a = 0, b = 0, y = 0;
    uint8_t en = 0;
    e->m.dwork = &e->dw;
    ecu_egrpos_initialize(&e->m, &a, &b, &en, &y);
    e->integ = e->prev = e->dfilt = 0;
}

float egrp_step(egrp_t *e, float target, float pos, uint8_t enable, float dt_s)
{
    float y;
    (void)dt_s;
    e->m.dwork = &e->dw;
    ecu_egrpos_step(&e->m, target, pos, enable, &y);
    e->integ = e->dw.integ_z_DSTATE;
    e->prev = e->dw.prev_z_DSTATE;
    e->dfilt = e->dw.dfilt_z_DSTATE;
    return y;
}

/* ---- speed states: model/ecu_spdst.slx ----
 * A chart writes its outputs only in entry actions and holds them in the
 * caller's storage otherwise: that storage must persist, so it is ours,
 * not the caller's locals. */
static RT_MODEL_ecu_spdst_T spdst_m;
static DW_ecu_spdst_T spdst_dw;
static uint8_t spdst_idle, spdst_state;

void spdst_reset(void)
{
    float r = 0, t = 0;
    uint8_t run = 0;
    uint32_t ms = 0;
    spdst_m.dwork = &spdst_dw;
    ecu_spdst_initialize(&spdst_m, &r, &t, &run, &ms, &spdst_idle, &spdst_state);
}

void spdst_step(uint8_t running, float rpm, float target, uint32_t idle_ms,
                uint8_t *idle, uint8_t *state)
{
    ecu_spdst_step(&spdst_m, rpm, target, running, idle_ms, &spdst_idle, &spdst_state);
    *idle = spdst_idle;
    *state = spdst_state;
}

/* ---- a fault's debounce: model/ecu_deb.slx ----
 * Many instances, so the state is the caller's (deb_t), and so is the
 * output: the chart writes act only in its entry actions. */
void deb_reset(deb_t *d)
{
    uint8_t c = 0;
    uint16_t a = 0, b = 0;
    d->m.dwork = &d->dw;
    ecu_deb_initialize(&d->m, &c, &a, &b, &d->act);
}

uint8_t deb_step(deb_t *d, uint8_t cond, uint16_t deb_ms, uint16_t heal_ms)
{
    ecu_deb_step(&d->m, cond, deb_ms, heal_ms, &d->act);
    return d->act;
}

/* ---- the diagnoses and coolant protection: model/ecu_diag.slx ----
 * Pure, so one shared instance; the C body in diag.c is the reference
 * build. The debounce of each is ecu_deb above. */
static RT_MODEL_ecu_diag_T diag_m;
void diag_cond(const diag_in_t *in, uint8_t cond[DG_N])
{
    ecu_diag_step(&diag_m, in->running, in->ign_on, in->stopped, in->rpm, in->v_bat,
                  in->egr_duty, in->i_egr_f, in->egr_pos, in->egr_pos_ok, in->egr_off,
                  in->mu_duty, in->i_mu, in->i_mu_valid,
                  in->rail_set, in->rail_bar, in->rail_ok,
                  in->oil_kpa, in->oil_ok, in->bat_high_act, in->bat_low_act,
                  in->clt_c, in->clt_ok, in->clt_low, in->clt_warn_act, in->clt_stop_act,
                  cond);
}

/* ---- the metering valve's supervision and closed-valve duty:
 * model/ecu_musup.slx, ecu_muclose.slx. Both pure; the learned ohms and
 * the distrust count are the caller's (mu_sup_t), in and out. ---- */
static RT_MODEL_ecu_musup_T musup_m;
float mu_sup_step(mu_sup_t *s, float cmd, float duty_prev, float v_bat, float i_mu,
                  uint8_t i_valid, uint8_t act_open, uint8_t act_over, uint8_t *meas)
{
    float out, r;
    uint16_t bad;
    ecu_musup_step(&musup_m, cmd, duty_prev, v_bat, i_mu, i_valid, act_open, act_over,
                   s->r, s->bad_ms, &out, meas, &r, &bad);
    s->r = r;
    s->bad_ms = bad;
    return out;
}

static RT_MODEL_ecu_muclose_T muclose_m;
float mu_close_duty(float r, float v_bat)
{
    float d;
    ecu_muclose_step(&muclose_m, r, v_bat, &d);
    return d;
}

/* ---- DM1's lamps, which faults light Protect: model/ecu_lamps.slx ---- */
static RT_MODEL_ecu_lamps_T lamps_m;
uint8_t fault_lamps(const faults_t *t)
{
    uint32_t spn[FAULTS_MAX];
    uint8_t fmi[FAULTS_MAX], l;
    for (int i = 0; i < FAULTS_MAX; i++) {
        spn[i] = t->f[i].spn;
        fmi[i] = t->f[i].fmi;
    }
    ecu_lamps_step(&lamps_m, spn, fmi, t->n, &l);
    return l;
}

/* ---- the crank decoder: model/ecu_crank.slx (updates), ecu_crankrd.slx
 * (what is read). Both pure: crank_t is packed into the model's two
 * vectors and back, so it is the same struct in both builds. The layout
 * is mdl_ecu_crank.m's. ---- */
static void crank_pack(const crank_t *c, uint32_t a[8], uint8_t b[33])
{
    a[0] = c->last_us; a[1] = c->prev_period;
    for (int i = 0; i < CRANK_WIN; i++) { a[2 + i] = c->per[i]; b[i] = c->deg[i]; }
    b[6] = c->nper; b[7] = c->head; b[8] = c->have; b[9] = c->count; b[10] = c->gap_seen;
    b[11] = c->synced; b[12] = c->phased; b[13] = c->rev; b[14] = c->fault; b[15] = c->prev_gap;
    const crank_sig *g[4] = { &c->cur, &c->prev, &c->mark, &c->other };
    for (int k = 0; k < 4; k++) { b[16 + 3 * k] = g[k]->n; b[17 + 3 * k] = g[k]->first; b[18 + 3 * k] = g[k]->last; }
    b[28] = c->prev_ok; b[29] = c->learned; b[30] = c->proven; b[31] = c->miss; b[32] = c->clean;
}

static void crank_unpack(crank_t *c, const uint32_t a[8], const uint8_t b[33])
{
    c->last_us = a[0]; c->prev_period = a[1];
    for (int i = 0; i < CRANK_WIN; i++) { c->per[i] = a[2 + i]; c->deg[i] = b[i]; }
    c->nper = b[6]; c->head = b[7]; c->have = b[8]; c->count = b[9]; c->gap_seen = b[10];
    c->synced = b[11]; c->phased = b[12]; c->rev = b[13]; c->fault = b[14]; c->prev_gap = b[15];
    crank_sig *g[4] = { &c->cur, &c->prev, &c->mark, &c->other };
    for (int k = 0; k < 4; k++) { g[k]->n = b[16 + 3 * k]; g[k]->first = b[17 + 3 * k]; g[k]->last = b[18 + 3 * k]; }
    c->prev_ok = b[28]; c->learned = b[29]; c->proven = b[30]; c->miss = b[31]; c->clean = b[32];
}

static RT_MODEL_ecu_crank_T crank_m;
static void crank_event(crank_t *c, uint8_t ev, uint32_t t_us)
{
    uint32_t a[8], an[8];
    uint8_t b[33], bn[33];
    crank_pack(c, a, b);
    ecu_crank_step(&crank_m, ev, t_us, a, b, an, bn);
    crank_unpack(c, an, bn);
}
void crank_edge(crank_t *c, uint32_t t_us) { crank_event(c, 0, t_us); }
void crank_cam(crank_t *c, uint32_t t_us) { crank_event(c, 1, t_us); }
void crank_poll(crank_t *c, uint32_t t_us) { crank_event(c, 2, t_us); }

static RT_MODEL_ecu_crankrd_T crankrd_m;
static void crank_read(const crank_t *c, float out[4])
{
    uint32_t a[8];
    uint8_t b[33];
    crank_pack(c, a, b);
    ecu_crankrd_step(&crankrd_m, a, b, &out[0], &out[1], &out[2], &out[3]);
}
float crank_rpm(const crank_t *c) { float o[4]; crank_read(c, o); return o[0]; }
float crank_angle(const crank_t *c) { float o[4]; crank_read(c, o); return o[1]; }
float crank_next_angle(const crank_t *c) { float o[4]; crank_read(c, o); return o[2]; }
float crank_us_per_deg(const crank_t *c) { float o[4]; crank_read(c, o); return o[3]; }

#endif
