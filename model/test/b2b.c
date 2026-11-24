/* Back-to-back: each generated model against its hand-written original,
 * on the same inputs, and the largest difference reported. Build with the
 * reference sources (no ECU_MODEL) plus firmware/gen; run_b2b.sh does. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include "govern.h"
#include "rail.h"
#include "inject.h"
#include "safety.h"
#include "mode.h"
#include "ecu_gov.h"
#include "ecu_rail.h"
#include "ecu_railset.h"
#include "ecu_soi.h"
#include "ecu_injdur.h"
#include "ecu_safety.h"
#include "ecu_mode.h"
#include "ecu_boostg.h"
#include "ecu_boostm.h"
#include "ecu_egrg.h"
#include "ecu_wifg.h"
#include "ecu_underg.h"
#include "ecu_relay.h"
#include "sensors.h"
#include "j1939.h"
#include "ecu_sensors.h"
#include "ecu_sensaux.h"
#include "ecu_j1939.h"
#include "actuate.h"
#include "ecu_mucur.h"
#include "ecu_egrpos.h"
#include "ecu_spdst.h"
#include "ecu_deb.h"
#include "diag.h"
#include "ecu_diag.h"
#include "ecu_musup.h"
#include "ecu_muclose.h"
#include "ecu_lamps.h"
#include "crank.h"
#include "ecu_crank.h"
#include "ecu_crankrd.h"
#include "j1939.h"
#include <math.h>
#include <string.h>

/* A random input that holds for a random while: the guards count time,
 * so white noise would never reach a threshold. */
typedef struct { float v; int left; } hold_t;
static float held(hold_t *h, float lo, float hi, int max_ms)
{
    if (h->left-- <= 0) { h->v = lo + (hi - lo) * (float)rand() / (float)RAND_MAX; h->left = rand() % max_ms; }
    return h->v;
}

static float rnd(float lo, float hi) { return lo + (hi - lo) * (float)rand() / (float)RAND_MAX; }
static int fails;
static void report(const char *what, double worst, double tol)
{
    int ok = worst <= tol;
    fails += !ok;
    printf("%-34s largest difference %-12.6g %s\n", what, worst, ok ? "ok" : "FAIL");
}

static const float dg_edge[] = { DG_BAT_MEASURED_V, DG_BAT_EGR_LO, DG_BAT_EGR_HI, DG_EGR_DRIVE,
    -DG_EGR_DRIVE, DG_EGR_OPEN_A, DG_EGR_COAST, -DG_EGR_COAST, DG_EGR_HARD, DG_EGR_POS_PCT,
    DG_MU_OPEN_A, DG_MU_MAX_A, DG_RAIL_DEV_BAR, DG_SPD_HIGH_RPM, DG_OIL_RUN_KPA, DG_OIL_STOP_KPA,
    DG_BAT_HIGH_V, DG_BAT_HIGH_RET_V, DG_BAT_LOW_V, DG_BAT_LOW_RET_V,
    DG_CLT_WARN_C, DG_CLT_WARN_RET_C, DG_CLT_STOP_C, DG_CLT_STOP_RET_C, 0.0f };
static float dg_pick(float lo, float hi)
{
    int r = rand() % 2000;
    if (r == 0)
        return NAN;
    if (r % 3 == 0) {
        float e = dg_edge[rand() % (int)(sizeof dg_edge / sizeof dg_edge[0])];
        int w = rand() % 3;
        return w == 0 ? e : nextafterf(e, w == 1 ? 1e9f : -1e9f);
    }
    return rnd(lo, hi);
}
static uint8_t dg_bit(void) { return (uint8_t)(rand() & 1); }
static int feq(float a, float b) { return a == b || (a != a && b != b); }   /* equal, or both NaN */

/* crank_t packed as ecu_crank's two vectors (mdl_ecu_crank.m's layout) */
static void ck_pack(const crank_t *c, uint32_t a[8], uint8_t b[33])
{
    a[0] = c->last_us; a[1] = c->prev_period;
    for (int i = 0; i < CRANK_WIN; i++) { a[2 + i] = c->per[i]; b[i] = c->deg[i]; }
    b[6] = c->nper; b[7] = c->head; b[8] = c->have; b[9] = c->count; b[10] = c->gap_seen;
    b[11] = c->synced; b[12] = c->phased; b[13] = c->rev; b[14] = c->fault; b[15] = c->prev_gap;
    const crank_sig *g[4] = { &c->cur, &c->prev, &c->mark, &c->other };
    for (int k = 0; k < 4; k++) { b[16 + 3 * k] = g[k]->n; b[17 + 3 * k] = g[k]->first; b[18 + 3 * k] = g[k]->last; }
    b[28] = c->prev_ok; b[29] = c->learned; b[30] = c->proven; b[31] = c->miss; b[32] = c->clean;
}

int main(void)
{
    srand(1);
    double w;

    /* governor: random speed walk with resets */
    gov_t g; RT_MODEL_ecu_gov_T gm; DW_ecu_gov_T gdw = {0}; gm.dwork = &gdw;
    float fy = 0, sy = 0; uint8_t rst = 0; float f0 = 0, r0 = 0;
    gov_reset(&g, 0, 0); rst = 1; f0 = 0; r0 = 0;
    w = 0;
    float rpm = 1500;
    for (int i = 0; i < 2000000; i++) {
        if (i % 50000 == 0) { f0 = rnd(0, 45); r0 = rnd(300, 1600); gov_reset(&g, f0, r0); rst = 1; }
        rpm += rnd(-5, 5); if (rpm < 0) rpm = 0;
        int droop = (i / 100000) & 1;
        int idle = (i / 37000) % 3 == 0;               /* the speed states' IDLE, on and off */
        float a = gov_step(&g, rpm, droop, idle, 0.001f);
        ecu_gov_step(&gm, rpm, (uint8_t)droop, rst, f0, r0, (uint8_t)idle, &fy, &sy);
        rst = 0;
        double d = fabs(a - fy) + fabs(g.set - sy);
        if (d > w) w = d;
    }
    report("governor (fuel + setpoint, mg/rpm)", w, 0);

    /* rail PI */
    rail_t r; RT_MODEL_ecu_rail_T rm; DW_ecu_rail_T rdw = {0}; rm.dwork = &rdw;
    rail_reset(&r); w = 0; rst = 1;
    for (int i = 0; i < 2000000; i++) {
        if (i % 70000 == 0) { rail_reset(&r); rst = 1; }
        float set = rnd(800, 1200), bar = rnd(600, 1400), y;
        float a = rail_step(&r, set, bar, 0.001f);
        ecu_rail_step(&rm, set, bar, rst, &y);
        rst = 0;
        if (fabs(a - y) > w) w = fabs(a - y);
    }
    report("rail PI (duty)", w, 0);

    /* tables and injector law, swept */
    RT_MODEL_ecu_railset_T tm; RT_MODEL_ecu_soi_T sm; RT_MODEL_ecu_injdur_T im; RT_MODEL_ecu_safety_T fm;
    double wr = 0, ws = 0, wi = 0, wf = 0;
    for (int i = 0; i <= 1000000; i++) {
        float q = -5.0f + 55.0f * (float)i / 1000000.0f, y;
        ecu_railset_step(&tm, q, &y); if (fabs(rail_set_bar(q) - y) > wr) wr = fabs(rail_set_bar(q) - y);
        ecu_soi_step(&sm, q, &y);     if (fabs(inject_soi_btdc(q) - y) > ws) ws = fabs(inject_soi_btdc(q) - y);
        float p = rnd(0, 1800); uint32_t t;
        ecu_injdur_step(&im, q, p, &t);
        double d = fabs((double)inject_dur_us(q, p) - (double)t); if (d > wi) wi = d;
        float sp = rnd(0, 2000); uint8_t cf = rand() & 1, ig = rand() & 1, ru = rand() & 1, why;
        ecu_safety_step(&fm, sp, cf, ig, ru, &why);
        if (why != safety_check(sp, cf, ig, ru)) wf = 1;
    }
    report("rail setpoint table (bar)", wr, 2.5e-4);   /* 2 ulp at 1171 */
    report("start-of-injection table (deg)", ws, 2e-6);  /* 2 ulp at 16 */
    report("injector law (us)", wi, 0);
    report("trip decision (mismatches)", wf, 0);

    /* ---- the Stateflow charts against mode.c, tick by tick ---- */
    const int N = 3000000;
    long bad, hit[5] = {0}, n1, n2;
    { RT_MODEL_ecu_mode_T m; DW_ecu_mode_T dw; uint8_t y, c0 = 0, i0 = 0, p0 = 0; float r0f = 0; hold_t hi = {0}, hs = {0};
      m.dwork = &dw; ecu_mode_initialize(&m, &c0, &i0, &p0, &r0f, &y); mode_cmd(MODE_RESET, 0, 0, 0);
      bad = 0;
      for (int i = 0; i < N; i++) {
          /* mostly ticks, as the firmware sends them; the ignition and a
           * stopped engine held long enough to complete ignition cycles */
          int r = rand() % 100;
          uint8_t cmd = r < 85 ? MODE_TICK : r < 92 ? MODE_TOOTH : r < 97 ? MODE_RUN_OK : r < 99 ? MODE_TRIP : MODE_RESET;
          uint8_t ig = held(&hi, 0, 1, 1500) > 0.4f, ph = rand() & 1;
          float sp = held(&hs, 0, 1, 2000) > 0.5f ? 0.0f : rnd(1, 800);
          uint8_t a = mode_cmd(cmd, ig, ph, sp);
          ecu_mode_step(&m, cmd, ig, ph, sp, &y);
          bad += a != y; hit[y]++;
      }
      report("engine mode chart (mismatched ticks)", (double)bad, 0);
      printf("   ticks in OFF/WAIT/CRANK/RUN/SHUTDOWN: %ld %ld %ld %ld %ld\n", hit[0], hit[1], hit[2], hit[3], hit[4]); }
    { RT_MODEL_ecu_boostg_T m; DW_ecu_boostg_T dw; uint8_t d, t, d2, t2, s0 = 0; float v0 = 0; hold_t h = {0}, hs = {0};
      m.dwork = &dw; ecu_boostg_initialize(&m, &v0, &s0, &d, &t); boostg_reset(); bad = 0; n1 = 0;
      for (int i = 0; i < N; i++) {
          if (rand() % 200000 == 0) { boostg_reset(); ecu_boostg_initialize(&m, &v0, &s0, &d, &t); }
          float v = held(&h, 95, 110, 40); uint8_t sh = held(&hs, 0, 1, 5000) > 0.9f;
          boostg_step(v, sh, &d2, &t2); ecu_boostg_step(&m, v, sh, &d, &t);
          bad += d != d2 || t != t2; n1 += t;
      }
      report("boost guard chart (mismatched ticks)", (double)bad, 0);
      printf("   trips exercised: %ld\n", n1); }
    { RT_MODEL_ecu_boostm_T m; DW_ecu_boostm_T dw; uint8_t y[4], c[4], f0 = 0; float v0 = 0; hold_t h = {0}, hf = {0};
      m.dwork = &dw; ecu_boostm_initialize(&m, &v0, &f0, &y[0], &y[1], &y[2], &y[3]); boostm_reset(); bad = 0; n1 = n2 = 0;
      for (int i = 0; i < N; i++) {
          if (rand() % 400000 == 0) { boostm_reset(); ecu_boostm_initialize(&m, &v0, &f0, &y[0], &y[1], &y[2], &y[3]); }
          float v = held(&h, -1, 110, 4000); if (v < 0) v = 0;
          uint8_t f = held(&hf, 0, 1, 6000) > 0.3f;
          boostm_step(v, f, &c[0], &c[1], &c[2], &c[3]);
          ecu_boostm_step(&m, v, f, &y[0], &y[1], &y[2], &y[3]);
          bad += y[0] != c[0] || y[1] != c[1] || y[2] != c[2] || y[3] != c[3];
          n1 += c[0]; n2 += c[2];
      }
      report("boost warnings chart (mismatched ticks)", (double)bad, 0);
      printf("   ticks warning high / low: %ld %ld\n", n1, n2); }
    { RT_MODEL_ecu_egrg_T m; DW_ecu_egrg_T dw; uint8_t o, r1, o2, r2; float i0 = 0; hold_t h = {0};
      m.dwork = &dw; ecu_egrg_initialize(&m, &i0, &o, &r1); egrg_reset(); bad = 0; n1 = 0;
      for (int i = 0; i < N; i++) {
          if (rand() % 400000 == 0) { egrg_reset(); ecu_egrg_initialize(&m, &i0, &o, &r1); }
          float a = held(&h, 0, 7, 3000);
          egrg_step(a, &o2, &r2); ecu_egrg_step(&m, a, &o, &r1);
          bad += o != o2 || r1 != r2; n1 += r1;
      }
      report("EGR stall chart (mismatched ticks)", (double)bad, 0);
      printf("   stalls exercised: %ld\n", n1); }
    { RT_MODEL_ecu_wifg_T m; DW_ecu_wifg_T dw; uint8_t ra, dr, ra2, dr2, w0 = 0; hold_t h = {0};
      m.dwork = &dw; ecu_wifg_initialize(&m, &w0, &ra, &dr); wifg_reset(); bad = 0; n1 = n2 = 0;
      for (int i = 0; i < N; i++) {
          uint8_t w = held(&h, 0, 1, 5000) > 0.5f;
          wifg_step(w, &ra2, &dr2); ecu_wifg_step(&m, w, &ra, &dr);
          bad += ra != ra2 || dr != dr2; n1 += ra; n2 += dr;
      }
      report("water-in-fuel chart (mismatched ticks)", (double)bad, 0);
      printf("   ticks raising / dropping: %ld %ld\n", n1, n2); }
    { RT_MODEL_ecu_underg_T m; DW_ecu_underg_T dw; uint8_t ra, dr, ra2, dr2, a0 = 0; float r0x = 0; hold_t h = {0}, ha = {0};
      m.dwork = &dw; ecu_underg_initialize(&m, &r0x, &a0, &ra, &dr); underg_reset(); bad = 0; n1 = n2 = 0;
      for (int i = 0; i < N; i++) {
          if (rand() % 400000 == 0) { underg_reset(); ecu_underg_initialize(&m, &r0x, &a0, &ra, &dr); }
          float sp = held(&h, 1300, 1450, 4000); uint8_t ar = held(&ha, 0, 1, 20000) > 0.2f;
          underg_step(sp, ar, &ra2, &dr2); ecu_underg_step(&m, sp, ar, &ra, &dr);
          bad += ra != ra2 || dr != dr2; n1 += ra; n2 += dr;
      }
      report("underspeed chart (mismatched ticks)", (double)bad, 0);
      printf("   ticks raising / dropping: %ld %ld\n", n1, n2); }
    { RT_MODEL_ecu_relay_T m; DW_ecu_relay_T dw; uint8_t rl, af, sv, rl2, af2, sv2, z0 = 0, z1 = 0, z2 = 0; hold_t hi = {0}, hs = {0}, hw = {0};
      m.dwork = &dw; ecu_relay_initialize(&m, &z0, &z1, &z2, &rl, &af, &sv); relay_reset(); bad = 0; n1 = n2 = 0;
      for (int i = 0; i < N; i++) {
          uint8_t ig = held(&hi, 0, 1, 90000) > 0.5f, st = held(&hs, 0, 1, 3000) > 0.5f, wr = held(&hw, 0, 1, 2000) > 0.5f;
          relay_step(ig, st, wr, &rl2, &af2, &sv2); ecu_relay_step(&m, ig, st, wr, &rl, &af, &sv);
          bad += rl != rl2 || af != af2 || sv != sv2; n1 += sv; n2 += (af2 == 0 && rl2 == 0);
      }
      report("main relay chart (mismatched ticks)", (double)bad, 0);
      printf("   after-runs started: %ld, ticks released: %ld\n", n1, n2); }
    /* sensors: volts across and beyond every range, a sagging 5 V, trims
     * that change at run time, resets; every value and FMI, every tick */
    { RT_MODEL_ecu_sensors_T m; DW_ecu_sensors_T dw; sens_t ref; float val[S_N]; uint8_t fmi[S_N];
      float g[S_N + 1], o[S_N + 1], v[S_N], v5 = 5; hold_t hv[S_N], h5 = {0};
      float zv[S_N], z5, zg[S_N + 1], zo[S_N + 1];   /* initialize zeroes what it is given */
      memset(hv, 0, sizeof hv);
      for (int k = 0; k <= S_N; k++) { g[k] = 1; o[k] = 0; }
      m.dwork = &dw; sens_trim(g, o); sens_reset(&ref);
      ecu_sensors_initialize(&m, zv, &z5, zg, zo, val, fmi);
      double worst = 0; bad = 0; n1 = n2 = 0;
      for (int i = 0; i < N; i++) {
          if (rand() % 300000 == 0) { sens_reset(&ref); ecu_sensors_initialize(&m, zv, &z5, zg, zo, val, fmi); }
          if (rand() % 200000 == 0) {
              for (int k = 0; k <= S_N; k++) { g[k] = rnd(0.9f, 1.1f); o[k] = rnd(-0.1f, 0.1f); }
              sens_trim(g, o);
          }
          for (int k = 0; k < S_N; k++) {
              v[k] = held(&hv[k], -0.5f, 5.3f, 400);
              if (rand() % 5000 == 0) v[k] = sens_v_lo[k];          /* the edges themselves */
              if (rand() % 5000 == 0) v[k] = SENS_V_HI;
          }
          v5 = held(&h5, 4.3f, 5.7f, 3000);
          sens_step_1ms(&ref, v, v5);
          ecu_sensors_step(&m, v, v5, g, o, val, fmi);
          for (int k = 0; k < S_N; k++) {
              double d = fabs((double)val[k] - (double)ref.val[k]);
              if (d > worst) worst = d;
              bad += fmi[k] != ref.fmi[k];
              n1 += ref.fmi[k] == 3; n2 += ref.fmi[k] == 4;
          }
      }
      report("sensors: values", worst, 0);
      report("sensors: FMIs (mismatched)", (double)bad, 0);
      printf("   channel-ticks at FMI 3 / FMI 4: %ld %ld\n", n1, n2); }
    /* pin 79, charge-air temperature (ecu_sensaux, decisions log 33/34):
     * volts across the NTC range and beyond, a sagging 5 V, resets */
    { RT_MODEL_ecu_sensaux_T m; DW_ecu_sensaux_T dw; sens_aux_t ref; float val, zv = 0, z5 = 0;
      uint8_t fmi; hold_t hv = {0}, h5 = {0};
      m.dwork = &dw; sens_aux_reset(&ref);
      ecu_sensaux_initialize(&m, &zv, &z5, &val, &fmi);
      double worst = 0; bad = 0; n1 = n2 = 0;
      for (int i = 0; i < N; i++) {
          if (rand() % 300000 == 0) { sens_aux_reset(&ref); ecu_sensaux_initialize(&m, &zv, &z5, &val, &fmi); }
          float v = held(&hv, -0.5f, 5.3f, 400), v5 = held(&h5, 4.3f, 5.7f, 3000);
          if (rand() % 5000 == 0) v = sens_v_lo[S_CLT];
          if (rand() % 5000 == 0) v = SENS_V_HI;
          sens_aux_step_1ms(&ref, v, v5);
          ecu_sensaux_step(&m, v, v5, &val, &fmi);
          double d = fabs((double)val - (double)ref.val);
          if (d > worst) worst = d;
          bad += fmi != ref.fmi; n1 += ref.fmi == 3; n2 += ref.fmi == 4;
      }
      report("charge-air temperature: values", worst, 0);
      report("charge-air temperature: FMIs (mismatched)", (double)bad, 0);
      printf("   ticks at FMI 3 / FMI 4: %ld %ld\n", n1, n2); }
    /* J1939 PGN data: every byte, from inside and outside every range */
    { RT_MODEL_ecu_j1939_T m; uint8_t y[5][8]; ecu_can f;
      bad = 0;
      for (int i = 0; i < N; i++) {
          float rpm = rnd(-200, 9000), clt = rnd(-80, 260), oil = rnd(-20, 1100), ia = rnd(-80, 260);
          uint8_t co = rand() & 1, oo = rand() & 1, cl = rand() & 1, io = rand() & 1;
          uint32_t es = (uint32_t)rand() * 65599u + (uint32_t)rand();
          ecu_j1939_step(&m, rpm, clt, co, oil, oo, es, cl, ia, io, y[0], y[1], y[2], y[3], y[4]);
          j1939_eec1(&f, rpm); bad += memcmp(f.data, y[0], 8) != 0;
          j1939_et1(&f, clt, co); bad += memcmp(f.data, y[1], 8) != 0;
          j1939_eflp1(&f, oil, oo, cl); bad += memcmp(f.data, y[2], 8) != 0;
          j1939_hours(&f, es); bad += memcmp(f.data, y[3], 8) != 0;
          j1939_ic1(&f, ia, io); bad += memcmp(f.data, y[4], 8) != 0;
      }
      report("J1939 PGN bytes (mismatched frames)", (double)bad, 0); }
    /* the metering valve's current loop: commands, measurements and battery
     * readings inside and outside their ranges, the measurement coming and going */
    { mu_t ref; RT_MODEL_ecu_mucur_T m; DW_ecu_mucur_T dw; float y, z0 = 0, z1 = 0, z2 = 0, z3 = 0; uint8_t zv = 0;
      hold_t hc = {0}, hi = {0}, hb = {0}, hv = {0};
      double worst = 0;
      mu_reset(&ref); m.dwork = &dw; ecu_mucur_initialize(&m, &z0, &z1, &zv, &z2, &z3);
      for (int i = 0; i < N; i++) {
          if (rand() % 500000 == 0) { mu_reset(&ref); ecu_mucur_initialize(&m, &z0, &z1, &zv, &z2, &z3); }
          float c = held(&hc, -0.1f, 1.2f, 300), im = held(&hi, -0.1f, 2.0f, 50);
          float vb = held(&hb, 0.0f, 26.0f, 2000);
          uint8_t va = held(&hv, 0, 1, 20000) > 0.2f;
          float a = mu_step(&ref, c, im, va, vb, 0.001f);
          ecu_mucur_step(&m, c, im, va, vb, &y);
          double d = fabs((double)a - (double)y);
          if (d > worst) worst = d;
      }
      report("metering current loop (duty)", worst, 0); }
    /* the EGR position PID: targets either side of the closed band, a
     * moving position, enable on and off */
    { egrp_t ref; RT_MODEL_ecu_egrpos_T m; DW_ecu_egrpos_T dw; float y, z0 = 0, z1 = 0, z2 = 0; uint8_t ze = 0;
      hold_t ht = {0}, he = {0};
      double worst = 0; float pos = 20;
      egrp_reset(&ref); m.dwork = &dw; ecu_egrpos_initialize(&m, &z0, &z1, &ze, &z2);
      for (int i = 0; i < N; i++) {
          if (rand() % 500000 == 0) { egrp_reset(&ref); ecu_egrpos_initialize(&m, &z0, &z1, &ze, &z2); }
          float t = held(&ht, -5.0f, 100.0f, 3000);
          pos += rnd(-0.3f, 0.3f); if (pos < 0) pos = 0; if (pos > 100) pos = 100;
          uint8_t en = held(&he, 0, 1, 20000) > 0.2f;
          float a = egrp_step(&ref, t, pos, en, 0.001f);
          ecu_egrpos_step(&m, t, pos, en, &y);
          double d = fabs((double)a - (double)y);
          if (d > worst) worst = d;
      }
      report("EGR position PID (duty)", worst, 0); }
    /* the speed states: running on and off, speeds in and out of the band,
     * idle times from none to seconds */
    { RT_MODEL_ecu_spdst_T m; DW_ecu_spdst_T dw; uint8_t id, st, id2, st2, zr = 0, zi = 0, zs = 0;
      float zf = 0, zg = 0; uint32_t zm = 0;
      hold_t hr = {0}, hn = {0}, hm = {0};
      long n1 = 0, n2 = 0, n3 = 0; bad = 0;
      spdst_reset(); m.dwork = &dw; ecu_spdst_initialize(&m, &zf, &zg, &zr, &zm, &zi, &zs);
      for (int i = 0; i < N; i++) {
          uint8_t run = held(&hr, 0, 1, 40000) > 0.15f;
          float sp = held(&hn, 1440, 1560, 900);
          uint32_t im = (uint32_t)held(&hm, 0, 4000, 60000);
          spdst_step(run, sp, 1500, im, &id2, &st2);
          ecu_spdst_step(&m, sp, 1500, run, im, &id, &st);
          bad += id != id2 || st != st2;
          n1 += st2 == SPD_IDLE; n2 += st2 == SPD_OPERATING; n3 += st2 == SPD_STEADY;
      }
      report("speed states chart (mismatched ticks)", (double)bad, 0);
      printf("   ticks idle / operating / steady: %ld %ld %ld\n", n1, n2, n3); }
    /* the fault debounce: one chart, many instances -- four at once on
     * different times, so a shared state would show; times from 0 up */
    { RT_MODEL_ecu_deb_T m[4]; DW_ecu_deb_T dw[4]; deb_t ref[4]; uint8_t y[4];
      hold_t hc[4] = {{0}}, ht = {0}; uint16_t db[4], hl[4];
      long n1 = 0; bad = 0;
      for (int k = 0; k < 4; k++) {
          uint8_t c0 = 0; uint16_t a0 = 0, b0 = 0;
          m[k].dwork = &dw[k]; ecu_deb_initialize(&m[k], &c0, &a0, &b0, &y[k]); deb_reset(&ref[k]);
          db[k] = (uint16_t)(k * 700); hl[k] = (uint16_t)(k * 300);
      }
      for (int i = 0; i < N; i++) {
          if (held(&ht, 0, 1, 50000) > 0.999f)        /* now and then: new times */
              for (int k = 0; k < 4; k++) { db[k] = (uint16_t)(rand() % 3000); hl[k] = (uint16_t)(rand() % 2000); }
          for (int k = 0; k < 4; k++) {
              uint8_t c = held(&hc[k], 0, 1, 2500) > 0.5f;
              uint8_t a = deb_step(&ref[k], c, db[k], hl[k]);
              ecu_deb_step(&m[k], c, db[k], hl[k], &y[k]);
              bad += a != y[k]; n1 += a;
          }
      }
      report("fault debounce chart x4 (mismatched)", (double)bad, 0);
      printf("   ticks active: %ld\n", n1); }
    /* the diagnoses and coolant protection (ecu_diag, decisions log 24, 35):
     * every input random over its range or, a third of the time, exactly on
     * one of diag.h's thresholds or one float step either side, and now and
     * then NaN. All 14 conditions must agree on every tick, and each must
     * have fired, or a match proves nothing. */
    { RT_MODEL_ecu_diag_T m; uint8_t cm[DG_N], cr[DG_N];
      long hit[DG_N] = {0}; bad = 0;
      for (int i = 0; i < N; i++) {
          diag_in_t in = {
              .running = dg_bit(), .ign_on = dg_bit(), .stopped = dg_bit(),
              .rpm = dg_pick(0, 1800), .v_bat = dg_pick(0, 17),
              .egr_duty = dg_pick(-1, 1), .i_egr_f = dg_pick(0, 2), .egr_pos = dg_pick(0, 100),
              .egr_pos_ok = dg_bit(), .egr_off = dg_bit(),
              .mu_duty = dg_pick(0, 1), .i_mu = dg_pick(0, 3.5f), .i_mu_valid = dg_bit(),
              .rail_set = dg_pick(0, 1800), .rail_bar = dg_pick(0, 1800), .rail_ok = dg_bit(),
              .oil_kpa = dg_pick(0, 1000), .oil_ok = dg_bit(),
              .bat_high_act = dg_bit(), .bat_low_act = dg_bit(),
              .clt_c = dg_pick(-40, 140), .clt_ok = dg_bit(), .clt_low = dg_bit(),
              .clt_warn_act = dg_bit(), .clt_stop_act = dg_bit(),
          };
          diag_cond(&in, cr);
          ecu_diag_step(&m, in.running, in.ign_on, in.stopped, in.rpm, in.v_bat,
                        in.egr_duty, in.i_egr_f, in.egr_pos, in.egr_pos_ok, in.egr_off,
                        in.mu_duty, in.i_mu, in.i_mu_valid, in.rail_set, in.rail_bar, in.rail_ok,
                        in.oil_kpa, in.oil_ok, in.bat_high_act, in.bat_low_act,
                        in.clt_c, in.clt_ok, in.clt_low, in.clt_warn_act, in.clt_stop_act, cm);
          for (int k = 0; k < DG_N; k++) { bad += cm[k] != cr[k]; hit[k] += cr[k]; }
      }
      report("diagnoses and coolant protection, 14 conditions (mismatched)", (double)bad, 0);
      long least = hit[0]; int kl = 0;
      for (int k = 1; k < DG_N; k++) if (hit[k] < least) { least = hit[k]; kl = k; }
      printf("   every condition fired; the least, #%d, %ld times\n", kl + 1, least);
      if (least < 1000) { printf("   FAIL: condition #%d barely exercised\n", kl + 1); fails++; } }
    /* the metering valve's supervision (ecu_musup, decisions log 34, 41):
     * both run side by side, each with its own state, inputs held for
     * random stretches so the distrust count reaches MU_DISTRUST_MS and the
     * coil is learned; every output and both states compared every tick */
    { RT_MODEL_ecu_musup_T m; mu_sup_t ref, mod;
      hold_t hc = {0}, hd = {0}, hv = {0}, hi = {0}, hk = {0}, ho = {0}, hq = {0};
      long nd = 0, nl = 0, nf = 0; bad = 0;
      mu_sup_reset(&ref); mu_sup_reset(&mod);
      for (int i = 0; i < N; i++) {
          if (rand() % 400000 == 0) { mu_sup_reset(&ref); mu_sup_reset(&mod); }
          float cmd = held(&hc, -0.2f, 1.2f, 800);
          float dp = rand() % 50 == 0 ? dg_pick(0, 1) : held(&hd, 0, 1, 300);
          float vb = rand() % 50 == 0 ? dg_pick(5, 19) : held(&hv, 5, 19, 3000);
          float k = held(&hk, 0, 1, 2000);                 /* how the current relates to the duty */
          float im = k < 0.15f ? held(&hi, 0, 0.06f, 200)  /* reads open */
                   : k < 0.25f ? held(&hi, 2.9f, 3.4f, 200) /* reads over */
                   : dp * vb / held(&ho, 1.5f, 7.5f, 5000); /* a coil, somewhere in its range */
          uint8_t iv = held(&hq, 0, 1, 4000) > 0.1f;
          uint8_t ao = rand() % 3000 == 0, ac = rand() % 3000 == 0;
          uint8_t mr, mm; float cr, cm, rr2; uint16_t bb;
          cr = mu_sup_step(&ref, cmd, dp, vb, im, iv, ao, ac, &mr);
          ecu_musup_step(&m, cmd, dp, vb, im, iv, ao, ac, mod.r, mod.bad_ms, &cm, &mm, &rr2, &bb);
          mod.r = rr2; mod.bad_ms = bb;
          bad += mr != mm || !feq(cr, cm) || !feq(ref.r, mod.r) || ref.bad_ms != mod.bad_ms;
          nd += ref.bad_ms >= MU_DISTRUST_MS; nl += mr && ref.r != MU_R_NOM; nf += !mr;
      }
      report("metering supervision: trust, learning, fallback (mismatched)", (double)bad, 0);
      printf("   ticks distrusted %ld, learned-coil %ld, on the fallback %ld\n", nd, nl, nf);
      if (nd < 1000 || nl < 1000 || nf < 1000) { printf("   FAIL: a branch barely exercised\n"); fails++; } }
    /* the closed-valve duty on the learned coil (ecu_muclose) */
    { RT_MODEL_ecu_muclose_T m; bad = 0;
      static const float re[] = { MU_R_LO, MU_R_HI, MU_R_NOM, MU_VBAT_MIN, MU_VBAT_MAX, 0.0f };
      for (int i = 0; i < N; i++) {
          float r = rand() % 3 == 0 ? nextafterf(re[rand() % 6], (rand() & 1) ? 1e9f : -1e9f) : rnd(0, 9);
          float vb = rand() % 3 == 0 ? nextafterf(re[rand() % 6], (rand() & 1) ? 1e9f : -1e9f) : dg_pick(0, 20);
          float d;
          ecu_muclose_step(&m, r, vb, &d);
          float e = mu_close_duty(r, vb);
          bad += !feq(d, e);
      }
      report("closed-valve duty on the learned coil (mismatched)", (double)bad, 0); }
    /* DM1's lamps (ecu_lamps): random fault tables mixing the shutdown
     * faults, their near misses (110/16, 520192/16, 190/16) and anything */
    { RT_MODEL_ecu_lamps_T m; long nred = 0, namb = 0, n0 = 0; bad = 0;
      static const uint32_t sp[] = { SPN_SPEED, SPN_POS, SPN_BOOST_RAIL, SPN_CLT, 111, 168, 2791, 1347, 157, 97 };
      static const uint8_t fm[] = { 0, 0, 16, 18, 3, 4, 7, 31 };
      for (int i = 0; i < N; i++) {
          faults_t t; memset(&t, 0, sizeof t);
          t.n = (uint8_t)(rand() % (FAULTS_MAX + 1));
          for (int k = 0; k < FAULTS_MAX; k++) {      /* the unused rows too: only n may be read */
              t.f[k].spn = rand() % 4 == 0 ? (uint32_t)rand() : sp[rand() % 10];
              t.f[k].fmi = rand() % 4 == 0 ? (uint8_t)(rand() & 31) : fm[rand() % 8];
          }
          uint32_t spn[FAULTS_MAX]; uint8_t fmi[FAULTS_MAX], lm;
          for (int k = 0; k < FAULTS_MAX; k++) { spn[k] = t.f[k].spn; fmi[k] = t.f[k].fmi; }
          ecu_lamps_step(&m, spn, fmi, t.n, &lm);
          uint8_t lr = fault_lamps(&t);
          bad += lm != lr; nred += (lr & LAMP_PROTECT) != 0; namb += (lr & LAMP_AMBER) != 0; n0 += lr == 0;
      }
      report("DM1 lamps: which faults light Protect (mismatched)", (double)bad, 0);
      printf("   tables with Protect %ld, amber %ld, none %ld\n", nred, namb, n0); }
    /* the crank decoder and the cam-wheel learning (ecu_crank, ecu_crankrd,
     * decisions log 39, 41). A 60-2 wheel at 30-2500 rpm, swinging; a cam
     * wheel chosen now and then (one segment, 3+1, 2+2, two alike, random);
     * missing teeth, noise edges, stalls past the timeout, polls stamped
     * before the last edge, and the microsecond clock wrapping. The whole
     * state and the four read values must match after every event. */
    { RT_MODEL_ecu_crank_T m; RT_MODEL_ecu_crankrd_T mr;
      crank_t ref; uint32_t a[8], an[8]; uint8_t b[33], bn[33];
      static const int wheels[5][4] = { {108, -1, -1, -1}, {10, 50, 55, 90}, {10, 15, 70, 108},
                                        {20, 78, -1, -1}, {-1, -1, -1, -1} };
      int wsel = 0, tooth = 0; double t = 4294000000.0, rpm = 300;   /* starts just before the wrap */
      long nsync = 0, nphase = 0, nlearn = 0, nfault = 0; bad = 0;
      crank_reset(&ref); memset(a, 0, sizeof a); memset(b, 0, sizeof b);
      for (int i = 0; i < N; i++) {
          int r = rand() % 1000;
          if (r == 0) {                                  /* now and then: start over, a new wheel */
              crank_reset(&ref); memset(a, 0, sizeof a); memset(b, 0, sizeof b);
              wsel = rand() % 5;
          }
          rpm += (rnd(-1, 1)) * 3;
          if (rpm < 30) rpm = 30;
          if (rpm > 2500) rpm = 2500;
          uint8_t ev; uint32_t tu;
          if (r < 20) {                                  /* a poll, sometimes just before the last edge */
              ev = 2; tu = (uint32_t)((uint64_t)(t + rnd(-200, 60000)) & 0xFFFFFFFFu);
          } else {
              double slot = 1e6 / (rpm * 6);
              tooth = (tooth + 1) % 116;
              double dt = (tooth % 58 == 0) ? 3 * slot : slot;
              if (r < 25) dt *= rnd(0.05f, 0.4f);        /* noise */
              else if (r < 28) dt *= 2;                  /* a missing tooth */
              else if (r < 29) dt += 60000;              /* a stall past the timeout */
              t += dt;
              tu = (uint32_t)((uint64_t)t & 0xFFFFFFFFu);
              int cam = 0;
              for (int k = 0; k < 4; k++) cam |= wheels[wsel][k] == tooth;
              if (wsel == 4) cam = rand() % 40 == 0;
              if (cam) {                                 /* the cam edge just before its tooth */
                  uint32_t tc = tu - 10;
                  crank_cam(&ref, tc);
                  ecu_crank_step(&m, 1, tc, a, b, an, bn);
                  memcpy(a, an, sizeof a); memcpy(b, bn, sizeof b);
              }
              ev = 0;
          }
          if (ev == 0) crank_edge(&ref, tu); else crank_poll(&ref, tu);
          ecu_crank_step(&m, ev, tu, a, b, an, bn);
          memcpy(a, an, sizeof a); memcpy(b, bn, sizeof b);
          uint32_t ra[8]; uint8_t rb[33];
          ck_pack(&ref, ra, rb);
          float o[4];
          ecu_crankrd_step(&mr, a, b, &o[0], &o[1], &o[2], &o[3]);
          bad += memcmp(ra, a, sizeof a) != 0 || memcmp(rb, b, sizeof b) != 0
                 || !feq(o[0], crank_rpm(&ref)) || !feq(o[1], crank_angle(&ref))
                 || !feq(o[2], crank_next_angle(&ref)) || !feq(o[3], crank_us_per_deg(&ref));
          nsync += ref.synced; nphase += ref.phased; nlearn += ref.learned; nfault += ref.fault != 0;
      }
      report("crank decoder and cam-wheel learning, state + reads (mismatched)", (double)bad, 0);
      printf("   events synced %ld, phased %ld, wheel learned %ld, with a fault %ld\n", nsync, nphase, nlearn, nfault);
      if (nphase < 10000 || nfault < 10000) { printf("   FAIL: barely exercised\n"); fails++; } }
    return fails != 0;
}
