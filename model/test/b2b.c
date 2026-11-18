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
#include "ecu_j1939.h"
#include "actuate.h"
#include "ecu_mucur.h"
#include "ecu_egrpos.h"
#include "ecu_spdst.h"
#include "ecu_deb.h"
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
    /* J1939 PGN data: every byte, from inside and outside every range */
    { RT_MODEL_ecu_j1939_T m; uint8_t y[4][8]; ecu_can f;
      bad = 0;
      for (int i = 0; i < N; i++) {
          float rpm = rnd(-200, 9000), clt = rnd(-80, 260), oil = rnd(-20, 1100);
          uint8_t co = rand() & 1, oo = rand() & 1;
          uint32_t es = (uint32_t)rand() * 65599u + (uint32_t)rand();
          ecu_j1939_step(&m, rpm, clt, co, oil, oo, es, y[0], y[1], y[2], y[3]);
          j1939_eec1(&f, rpm); bad += memcmp(f.data, y[0], 8) != 0;
          j1939_et1(&f, clt, co); bad += memcmp(f.data, y[1], 8) != 0;
          j1939_eflp1(&f, oil, oo); bad += memcmp(f.data, y[2], 8) != 0;
          j1939_hours(&f, es); bad += memcmp(f.data, y[3], 8) != 0;
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
    return fails != 0;
}
