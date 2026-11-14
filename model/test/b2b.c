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
#include "ecu_egrg.h"
#include "ecu_wifg.h"
#include "ecu_underg.h"
#include "ecu_relay.h"

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
        float a = gov_step(&g, rpm, droop, 0.001f);
        ecu_gov_step(&gm, rpm, (uint8_t)droop, rst, f0, r0, &fy, &sy);
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
    { RT_MODEL_ecu_mode_T m; DW_ecu_mode_T dw; uint8_t y, c0 = 0, p0 = 0; float r0f = 0;
      m.dwork = &dw; ecu_mode_initialize(&m, &c0, &p0, &r0f, &y); mode_cmd(MODE_RESET, 0, 0);
      bad = 0;
      for (int i = 0; i < N; i++) {
          uint8_t cmd = (uint8_t)(1 + rand() % 5), ph = rand() & 1; float sp = rnd(0, 800);
          if (cmd == MODE_RESET && rand() % 4) cmd = MODE_TOOTH;     /* resets rarer */
          uint8_t a = mode_cmd(cmd, ph, sp);
          ecu_mode_step(&m, cmd, ph, sp, &y);
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
    return fails != 0;
}
