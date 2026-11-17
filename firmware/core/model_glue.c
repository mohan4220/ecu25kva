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
#include "j1939.h"
#include "ecu_j1939.h"
#include "actuate.h"
#include "ecu_spdst.h"
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

/* ---- J1939 periodic PGNs: model/ecu_j1939.slx ("Set PGNs") ----
 * Stateless: every call computes all four and keeps the one asked for.
 * The identifiers stay in C (j1939_id), as does everything that sends. */
static RT_MODEL_ecu_j1939_T j1939_m;

static void pgns(ecu_can *f, int which, uint8_t prio, uint32_t pgn, float rpm, float clt, uint8_t clt_ok,
                 float oil, uint8_t oil_ok, uint32_t engine_s)
{
    uint8_t y[4][8];
    ecu_j1939_step(&j1939_m, rpm, clt, clt_ok, oil, oil_ok, engine_s, y[0], y[1], y[2], y[3]);
    f->id = j1939_id(prio, pgn, J1939_SA);
    f->len = 8;
    memcpy(f->data, y[which], 8);
}

void j1939_eec1(ecu_can *f, float rpm) { pgns(f, 0, 3, 61444, rpm, 0, 0, 0, 0, 0); }
void j1939_et1(ecu_can *f, float clt_c, int valid) { pgns(f, 1, 6, 65262, 0, clt_c, (uint8_t)(valid != 0), 0, 0, 0); }
void j1939_eflp1(ecu_can *f, float oil_kpa, int valid) { pgns(f, 2, 6, 65263, 0, 0, 0, oil_kpa, (uint8_t)(valid != 0), 0); }
void j1939_hours(ecu_can *f, uint32_t engine_s) { pgns(f, 3, 6, PGN_HOURS, 0, 0, 0, 0, 0, engine_s); }

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

#endif
