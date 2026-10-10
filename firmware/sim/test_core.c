/* Unit tests for firmware/core. `make test` builds and runs them. */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "ecu.h"
#include "crank.h"
#include "sensors.h"

static int fails;
#define CHECK(c) do { if (!(c)) { fails++; \
    printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #c); } } while (0)

/* A 60-2 wheel turning at `rpm`. *tooth counts 0..115 over one 720 deg
 * cycle: edge n = tooth % 58 sits at n*6 deg of its revolution, and the
 * gap (two missing teeth) precedes edge 0. Advances *t to the next edge
 * and returns 1 when that edge is the cam's (cycle angle 660). */
static double t_frac;
static int next_edge(float rpm, uint32_t *t, int *tooth)
{
    double slot = 1e6 / rpm;                 /* us per 6 deg */
    *tooth = (*tooth + 1) % 116;
    t_frac += (*tooth % 58 == 0) ? 3 * slot : slot;
    uint32_t whole = (uint32_t)t_frac;
    *t += whole;
    t_frac -= whole;
    return *tooth == 58 + 50;
}

static void spin(crank_t *c, float rpm, int edges, uint32_t *t, int *tooth)
{
    for (int i = 0; i < edges; i++) {
        if (next_edge(rpm, t, tooth))
            crank_cam(c, *t - 10);
        crank_edge(c, *t);
    }
}

static int near(float a, float b, float rel) { return fabsf(a - b) <= rel * fabsf(b); }

static void test_crank_sync(void)
{
    for (int start = 0; start < 58; start += 7) {
        crank_t c; crank_reset(&c);
        uint32_t t = 1000; int tooth = start, n = 0;
        while (!crank_synced(&c) && n < 200) { spin(&c, 600, 1, &t, &tooth); n++; }
        CHECK(n <= 118);      /* 2 revs + the 2 edges before any period ratio exists */
        CHECK(near(crank_rpm(&c), 600, 0.005f));
    }
}

static void test_crank_rpm_gap(void)
{
    crank_t c; crank_reset(&c);
    uint32_t t = 0; int tooth = 0;
    spin(&c, 1500, 120, &t, &tooth);
    for (int i = 0; i < 116; i++) {
        spin(&c, 1500, 1, &t, &tooth);
        CHECK(near(crank_rpm(&c), 1500, 0.005f));
    }
}

static void test_crank_phase(void)
{
    crank_t c; crank_reset(&c);
    uint32_t t = 0; int tooth = 0;
    spin(&c, 600, 116, &t, &tooth);          /* synced; cam seen at tooth 108 */
    while (tooth != 0) spin(&c, 600, 1, &t, &tooth);
    CHECK(crank_phased(&c));
    CHECK(crank_angle(&c) == 0.0f);
    spin(&c, 600, 15, &t, &tooth);
    CHECK(crank_angle(&c) == 90.0f);
    spin(&c, 600, 57 - 15, &t, &tooth);       /* edge 57, next is past the gap */
    CHECK(crank_angle(&c) == 342.0f);
    CHECK(crank_next_angle(&c) == 360.0f);
}

static void test_crank_bad_gap(void)
{
    crank_t c; crank_reset(&c);
    uint32_t t = 0; int tooth = 0;
    spin(&c, 600, 150, &t, &tooth);
    CHECK(crank_fault(&c) == CRANK_F_NONE);
    while (tooth % 58 != 20) spin(&c, 600, 1, &t, &tooth);
    next_edge(600, &t, &tooth);               /* this edge goes missing */
    spin(&c, 600, 1, &t, &tooth);
    CHECK(crank_fault(&c) == CRANK_F_GAP);
}

static void test_crank_timeout(void)
{
    crank_t c; crank_reset(&c);
    uint32_t t = 0; int tooth = 0;
    spin(&c, 600, 150, &t, &tooth);
    crank_poll(&c, t + 49000);
    CHECK(crank_fault(&c) == CRANK_F_NONE);
    crank_poll(&c, t + 51000);
    CHECK(crank_fault(&c) == CRANK_F_TIMEOUT);
}

static void test_crank_wrap(void)
{
    crank_t c; crank_reset(&c);
    uint32_t t = 0xFFFFFFFFu - 20000; int tooth = 0;
    for (int i = 0; i < 200; i++) {
        spin(&c, 1500, 1, &t, &tooth);
        crank_poll(&c, t + 500);
        if (i > 120) CHECK(near(crank_rpm(&c), 1500, 0.005f));
    }
    CHECK(t < 0x80000000u);                   /* really did wrap */
    CHECK(crank_fault(&c) == CRANK_F_NONE);
}

static void all_volts(float v[S_N], float x) { for (int i = 0; i < S_N; i++) v[i] = x; }

static void test_sens_convert(void)
{
    CHECK(fabsf(sens_convert(S_CLT, 2.5f) - 20.1f) <= 0.5f);
    CHECK(fabsf(sens_convert(S_OIL, 2.5f) - 500.0f) <= 0.5f);
    CHECK(fabsf(sens_convert(S_RAIL, 4.5f) - 1800.0f) <= 0.5f);
    CHECK(fabsf(sens_convert(S_BOOST, 0.5f) - 50.0f) <= 0.5f);
    CHECK(fabsf(sens_convert(S_EGR, 2.5f) - 50.0f) <= 0.5f);
}

static void test_sens_ratiometric(void)
{
    sens_t a, b; float v[S_N];
    sens_reset(&a); sens_reset(&b);
    all_volts(v, 2.25f); sens_step_1ms(&a, v, 4.5f);
    all_volts(v, 2.5f);  sens_step_1ms(&b, v, 5.0f);
    CHECK(fabsf(a.val[S_RAIL] - b.val[S_RAIL]) < 0.01f);
}

static void test_sens_open(void)
{
    sens_t s; float v[S_N];
    sens_reset(&s); all_volts(v, 2.5f); v[S_CLT] = 4.95f;
    for (int i = 0; i < 99; i++) sens_step_1ms(&s, v, 5.0f);
    CHECK(s.fmi[S_CLT] == 0);
    sens_step_1ms(&s, v, 5.0f);
    CHECK(s.fmi[S_CLT] == 3);
    CHECK(s.val[S_CLT] == 90.0f);
}

static void test_sens_low(void)
{
    sens_t s; float v[S_N];
    sens_reset(&s); all_volts(v, 2.5f); v[S_OIL] = 0.1f;
    for (int i = 0; i < 100; i++) sens_step_1ms(&s, v, 5.0f);
    CHECK(s.fmi[S_OIL] == 4);
}

static void test_sens_5v_short(void)
{
    sens_t s; float v[S_N];
    sens_reset(&s); all_volts(v, 2.5f);
    for (int i = 0; i < 200; i++) sens_step_1ms(&s, v, 0.0f);
    for (int i = 0; i < S_N; i++) {
        CHECK(isfinite(s.val[i]));
        CHECK(s.fmi[i] == 0);
    }
}

static void test_io_size(void)
{
    ecu_io io;
    memset(&io, 0, sizeof io);
    CHECK(ecu_io_size() == sizeof(ecu_io));
    ecu_init(&io);
    CHECK(io.state == ECU_OFF);
}

int main(void)
{
    test_io_size();
    test_crank_sync();
    test_crank_rpm_gap();
    test_crank_phase();
    test_crank_bad_gap();
    test_crank_timeout();
    test_crank_wrap();
    test_sens_convert();
    test_sens_ratiometric();
    test_sens_open();
    test_sens_low();
    test_sens_5v_short();
    printf("%s: %d failure(s)\n", fails ? "FAIL" : "ok", fails);
    return fails != 0;
}
