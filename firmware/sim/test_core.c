/* Unit tests for firmware/core. `make test` builds and runs them. */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "ecu.h"
#include "crank.h"
#include "sensors.h"
#include "govern.h"
#include "rail.h"
#include "inject.h"
#include "safety.h"
#include "j1939.h"
#include "nvm.h"
#include "log.h"

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

static void test_gov(void)
{
    gov_t g; gov_reset(&g, 10, 1500);
    for (int i = 0; i < 1000; i++) gov_step(&g, 1400, 0, 0.001f);
    CHECK(g.fuel == FUEL_MAX_MG);
    for (int i = 0; i < 1000; i++) gov_step(&g, 1600, 0, 0.001f);
    CHECK(g.fuel == 0.0f);
    CHECK(g.integ >= 0.0f);
    CHECK(fabsf(gov_setpoint(34, 1) - 1440.0f) <= 0.1f);
    CHECK(gov_setpoint(34, 0) == 1500.0f);
}

static void test_rail(void)
{
    rail_t r; rail_reset(&r);
    float d0 = rail_step(&r, 900, 0.001f), d = d0;
    for (int i = 0; i < 1000; i++) {
        d = rail_step(&r, 900, 0.001f);
        CHECK(d >= 0.0f && d <= 1.0f);
    }
    CHECK(METER_NC ? d > d0 : d < d0);        /* low pressure: open the valve further */
    for (int i = 0; i < 2000; i++) d = rail_step(&r, 1500, 0.001f);
    CHECK(d == METER_CLOSED);                 /* high pressure: valve shut */
}

static void test_inject_dur(void)
{
    float want = 300.0f + 34.0f / (0.0009f * sqrtf(1000.0f));
    CHECK(fabsf((float)inject_dur_us(34, 1000) - want) <= 2.0f);
    CHECK(inject_dur_us(10, 0) == inject_dur_us(10, 100));
    CHECK(inject_dur_us(0, 1000) == 0);
}

/* Spin to phase, then run 2 cycles calling inject_edge on every edge. */
static void test_inject_once_per_cycle(void)
{
    crank_t c; crank_reset(&c);
    ecu_inj inj[ECU_NCYL]; memset(inj, 0, sizeof inj);
    uint32_t t = 0, t84 = 0; int tooth = 0, checked = 0;
    spin(&c, 1500, 116, &t, &tooth);
    while (tooth != 0) spin(&c, 1500, 1, &t, &tooth);
    CHECK(crank_phased(&c));
    for (int i = 0; i < 232; i++) {
        inject_edge(&c, 20, 1000, inj);
        if (tooth == 14 && !checked) {         /* edge at 84 deg, SOI 85 */
            t84 = t;
            CHECK(fabsf((float)(inj[0].start_us - t84) - 1e6f / 9000.0f) <= 5.0f);
            checked = 1;
        }
        spin(&c, 1500, 1, &t, &tooth);
    }
    CHECK(checked);
    for (int k = 0; k < ECU_NCYL; k++)
        CHECK(inj[k].seq == 2);
}

static void test_inject_soi_in_gap(void)
{
    crank_t c; crank_reset(&c);
    uint32_t t = 0; int tooth = 0, due = 0;
    spin(&c, 1500, 116, &t, &tooth);
    while (tooth != 0) spin(&c, 1500, 1, &t, &tooth);
    for (int i = 0; i < 232; i++) {
        due += inject_due(&c, 350.0f);
        due += inject_due(&c, 2.0f) * 100;    /* across the 720 wrap */
        spin(&c, 1500, 1, &t, &tooth);
    }
    CHECK(due == 2 + 200);
}

static void test_safety(void)
{
    CHECK(safety_check(1651, CRANK_F_NONE, 1, 1) == TRIP_OVERSPEED);
    CHECK(safety_check(1649, CRANK_F_NONE, 1, 1) == TRIP_NONE);
    CHECK(safety_check(1500, CRANK_F_GAP, 1, 0) == TRIP_NONE);
    CHECK(safety_check(1500, CRANK_F_GAP, 1, 1) == TRIP_SYNC);
    CHECK(safety_check(1500, CRANK_F_NONE, 0, 1) == TRIP_IGN);
    CHECK(safety_check(1700, CRANK_F_NONE, 0, 1) == TRIP_OVERSPEED);
}

static void test_faults(void)
{
    faults_t t; memset(&t, 0, sizeof t);
    faults_set(&t, 110, 3);
    faults_set(&t, 110, 3);
    CHECK(t.n == 1);
    for (uint32_t i = 0; i < 9; i++) faults_set(&t, 200 + i, 4);
    CHECK(t.n == 8);
    faults_clear(&t, 110, 3);
    CHECK(t.n == 7);
    for (int i = 0; i < t.n; i++) CHECK(t.f[i].spn == 200u + i && t.f[i].fmi == 4);
}

static void test_j1939_id(void)
{
    CHECK(j1939_id(3, 61444, 234) == 0x0CF004EAu);
}

static void test_eec1(void)
{
    ecu_can f; j1939_eec1(&f, 1500);
    CHECK(f.id == 0x0CF004EAu && f.len == 8);
    CHECK(f.data[3] == 0xE0 && f.data[4] == 0x2E);
    CHECK(f.data[0] == 0xFF && f.data[7] == 0xFF);
}

static void test_et1(void)
{
    ecu_can f;
    j1939_et1(&f, 90, 1);
    CHECK(f.id == 0x18FEEEEAu && f.data[0] == 130);
    j1939_et1(&f, 90, 0);
    CHECK(f.data[0] == 0xFF);
    j1939_eflp1(&f, 400, 1);
    CHECK(f.id == 0x18FEEFEAu && f.data[3] == 100 && f.data[7] == 0xFF);
}

static void test_dm1_single(void)
{
    faults_t t; memset(&t, 0, sizeof t);
    ecu_can f[4];
    CHECK(j1939_dm1(f, 4, &t, 0) == 1);
    CHECK(f[0].id == 0x18FECAEAu && f[0].data[2] == 0 && f[0].data[5] == 0 && f[0].data[6] == 0xFF);
    faults_set(&t, 110, 3);
    CHECK(j1939_dm1(f, 4, &t, LAMP_AMBER) == 1);
    CHECK(f[0].len == 8 && f[0].data[0] == LAMP_AMBER && f[0].data[1] == 0xFF);
    CHECK(f[0].data[2] == 0x6E && f[0].data[3] == 0x00 && f[0].data[4] == 0x03 && f[0].data[5] == 0x01);
}

static void test_dm1_bam(void)
{
    faults_t t; memset(&t, 0, sizeof t);
    ecu_can f[4];
    faults_set(&t, 110, 3); faults_set(&t, 100, 4); faults_set(&t, 190, 0);
    CHECK(j1939_dm1(f, 4, &t, LAMP_RED) == 3);
    CHECK(f[0].id == j1939_id(7, 0xECFF, 234));
    CHECK(f[0].data[0] == 32 && f[0].data[1] == 14 && f[0].data[2] == 0 && f[0].data[3] == 2);
    CHECK(f[0].data[5] == 0xCA && f[0].data[6] == 0xFE && f[0].data[7] == 0x00);
    CHECK(f[1].id == j1939_id(7, 0xEBFF, 234) && f[1].data[0] == 1 && f[2].data[0] == 2);
    CHECK(f[1].data[1] == LAMP_RED && f[1].data[3] == 0x6E);
    CHECK(j1939_dm1(f, 2, &t, 0) == 0);       /* would not fit */
    faults_set(&t, 102, 4);                   /* 18 bytes: 3 packets, last one padded */
    CHECK(j1939_dm1(f, 4, &t, 0) == 4);
    CHECK(f[3].data[0] == 3 && f[3].data[4] == 0x01 && f[3].data[5] == 0xFF && f[3].data[7] == 0xFF);
}

static void test_dm1_spn_high(void)
{
    faults_t t; memset(&t, 0, sizeof t);
    ecu_can f[1];
    faults_set(&t, 520192, 5);
    j1939_dm1(f, 1, &t, 0);
    CHECK(f[0].data[2] == 0x00 && f[0].data[3] == 0xF0 && f[0].data[4] == (0xE0 | 5));
}

/* ---- whole-ECU tests through the four entry points ---- */

static uint32_t tick_t;
static int host_dead;                /* storage that never completes a write */
static int seals;                    /* saves the host has been asked for */

static void host_tick(ecu_io *io)
{
    ecu_tick_1ms(io, tick_t);
    ecu_background(io);
    if (io->nvm_save && !host_dead) { seals++; io->nvm_save = 0; }
}

static void ecu_up(ecu_io *io)
{
    memset(io, 0, sizeof *io);
    ecu_init(io);
    io->ignition = 1;
    io->v_clt = io->v_oil = io->v_rail = io->v_boost = io->v_egr = 2.5f;
    io->v_5v = 5.0f;
    io->v_bat = 24.0f;
    ecu_nvm_load(io, NULL, NULL, 0);
    tick_t = 0;
    host_dead = 0;
    seals = 0;
}

static void ticks(ecu_io *io, int n, int drain)
{
    for (int i = 0; i < n; i++) {
        tick_t += 1000;
        host_tick(io);
        if (drain) io->can_n = 0;
    }
}

/* Edges at `rpm`, with 1 ms ticks interleaved when with_ticks. */
static void ecu_spin(ecu_io *io, float rpm, int edges, uint32_t *t, int *tooth, int with_ticks)
{
    for (int i = 0; i < edges; i++) {
        int cam = next_edge(rpm, t, tooth);
        while (with_ticks && tick_t + 1000 <= *t) {
            tick_t += 1000;
            host_tick(io);
            io->can_n = 0;
        }
        if (cam) ecu_cam_edge(io, *t - 10);
        ecu_crank_edge(io, *t);
    }
}

static void ecu_running(ecu_io *io, uint32_t *t, int *tooth)
{
    ecu_up(io);
    *t = 0; *tooth = 0;
    ecu_spin(io, 300, 174, t, tooth, 1);
    for (float rpm = 300; rpm < 1500; rpm *= 1.02f)    /* a real engine ramps */
        ecu_spin(io, rpm, 1, t, tooth, 1);
    ecu_spin(io, 1500, 116, t, tooth, 1);
}

/* Tick until the next DM1 and report whether its first DTC is `spn`
 * (0 = the empty "no fault" DTC). */
static int dm1_first_spn(ecu_io *io, uint32_t spn)
{
    for (int i = 0; i < 1000; i++) {
        tick_t += 1000;
        host_tick(io);
        for (int k = 0; k < io->can_n; k++) {
            ecu_can *f = &io->can[k];
            if (f->id == 0x18FECAEAu) {
                uint32_t got = f->data[2] | f->data[3] << 8 | (uint32_t)(f->data[4] & 0xE0) << 11;
                io->can_n = 0;
                return got == spn;
            }
        }
        io->can_n = 0;
    }
    return 0;
}

static void test_ecu_start(void)
{
    ecu_io io; uint32_t t = 0; int tooth = 0;
    ecu_up(&io);
    ticks(&io, 1, 1);
    CHECK(io.state == ECU_WAIT);
    ecu_spin(&io, 300, 174, &t, &tooth, 1);
    CHECK(io.state == ECU_CRANK);
    CHECK(io.synced);
    CHECK(io.inj[0].seq + io.inj[1].seq + io.inj[2].seq > 0);
    ecu_spin(&io, 600, 116, &t, &tooth, 1);
    CHECK(io.state == ECU_RUN);
}

static void test_ecu_overspeed_edge(void)
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);
    CHECK(io.state == ECU_RUN);
    float rpm = 1500; int tripped = 0;
    while (rpm < 1700 && !tripped) {
        ecu_spin(&io, rpm, 1, &t, &tooth, 0);
        if (io.rpm > OVERSPEED_RPM) {
            CHECK(io.state == ECU_SHUTDOWN);
            tripped = 1;
        } else {
            CHECK(io.state == ECU_RUN);
        }
        rpm += 1;
    }
    CHECK(tripped);
    uint32_t seq[ECU_NCYL];
    for (int k = 0; k < ECU_NCYL; k++) { CHECK(io.inj[k].dur_us == 0); seq[k] = io.inj[k].seq; }
    ecu_spin(&io, 1700, 116, &t, &tooth, 0);
    for (int k = 0; k < ECU_NCYL; k++) CHECK(io.inj[k].seq == seq[k]);
    tick_t = t;
    CHECK(dm1_first_spn(&io, SPN_SPEED));
}

static void test_ecu_ignition(void)
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);
    tick_t = t;
    io.ignition = 0;
    ticks(&io, 1, 1);
    CHECK(io.state == ECU_SHUTDOWN);
    CHECK(io.fault_n == 0);
    CHECK(dm1_first_spn(&io, 0));
    ticks(&io, IGN_OFF_MS, 1);
    io.ignition = 1;
    ticks(&io, 1, 1);
    CHECK(io.state == ECU_WAIT);
}

static void test_ecu_shutdown_valve_closed(void)      /* final review C1 */
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);
    tick_t = t;
    io.ignition = 0;
    ticks(&io, 1, 1);
    CHECK(io.state == ECU_SHUTDOWN && io.meter_duty == METER_CLOSED);
}

static void test_ecu_tick_before_edge(void)           /* final review I1 */
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);
    float fuel = io.fuel_mg;
    ecu_tick_1ms(&io, t - 5);                 /* tick stamped just before the last edge */
    CHECK(io.rpm > 1400.0f);
    CHECK(fabsf(io.fuel_mg - fuel) < 2.0f);
}

static void test_crank_after_pause(void)              /* final review I2 */
{
    crank_t c; crank_reset(&c);
    crank_edge(&c, 1000);                     /* stray edge while waiting */
    crank_edge(&c, 2000);
    uint32_t t = 30000000; int tooth = 0, n = 0;
    while (!crank_synced(&c) && n < 300) { spin(&c, 150, 1, &t, &tooth); n++; }
    CHECK(n <= 118);
}

static void test_ecu_ignition_dip_keeps_latch(void)   /* final review I3 */
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);
    io.ignition = 0;
    ecu_spin(&io, 1400, 2, &t, &tooth, 1);     /* still turning */
    io.ignition = 1;
    ecu_spin(&io, 1400, 116, &t, &tooth, 1);
    CHECK(io.state == ECU_SHUTDOWN);
    uint32_t seq0 = io.inj[0].seq;
    ecu_spin(&io, 1400, 116, &t, &tooth, 1);
    CHECK(io.inj[0].seq == seq0);
    /* stopped, and the ignition held off long enough: the latch clears */
    io.ignition = 0;
    tick_t = t;
    ticks(&io, IGN_OFF_MS + 60, 1);
    io.ignition = 1;
    ticks(&io, 1, 1);
    CHECK(io.state == ECU_WAIT);
}

static void test_ecu_crank_loss(void)
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);
    tick_t = t;
    ticks(&io, 49, 1);
    CHECK(io.state == ECU_RUN);
    ticks(&io, 2, 1);
    CHECK(io.state == ECU_SHUTDOWN);
    CHECK(dm1_first_spn(&io, SPN_POS));
}

static void test_ecu_wdg(void)
{
    ecu_io io; ecu_up(&io);
    uint8_t last = io.wdg; int since = 0, bad = 0, changes = 0;
    for (int i = 0; i < 100; i++) {
        ticks(&io, 1, 1);
        since++;
        if (io.wdg != last) { bad += since != 5; since = 0; changes++; last = io.wdg; }
    }
    CHECK(changes == 20);
    CHECK(bad == 0);
}

static void test_ecu_can_rates(void)
{
    ecu_io io; ecu_up(&io);
    int eec1 = 0, et1 = 0, efl = 0, dm1 = 0;
    for (int i = 0; i < 1000; i++) {
        ticks(&io, 1, 0);
        for (int k = 0; k < io.can_n; k++) {
            uint32_t pgn = io.can[k].id >> 8 & 0xFFFF;
            eec1 += pgn == 0xF004; et1 += pgn == 0xFEEE; efl += pgn == 0xFEEF; dm1 += pgn == 0xFECA;
        }
        io.can_n = 0;
    }
    CHECK(eec1 == 50 && et1 == 1 && efl == 2 && dm1 == 1);
    CHECK(io.can_drops == 0);
}

static void test_ecu_can_overflow(void)
{
    ecu_io io; ecu_up(&io);
    ticks(&io, 1000, 0);
    CHECK(io.can_n == ECU_CANQ);
    CHECK(io.can_drops > 0);
}

static void test_ecu_sensor_fault_clears(void)
{
    ecu_io io; ecu_up(&io);
    io.v_oil = 0.1f;  ticks(&io, 101, 1);
    CHECK(io.fault_n == 1);
    io.v_oil = 2.5f;  ticks(&io, 101, 1);
    CHECK(io.fault_n == 0);
    io.v_clt = 4.95f; ticks(&io, 101, 1);
    CHECK(io.fault_n == 1);
    io.v_clt = 2.5f;  ticks(&io, 101, 1);
    CHECK(io.fault_n == 0);
}

/* ---- SME review findings (C = critical, I = important) ---- */

static void test_inject_cancel_visible(void)          /* C1 */
{
    ecu_inj inj[ECU_NCYL] = { { 100, 1500, 4 }, { 0, 0, 2 }, { 0, 0, 0 } };
    inject_cancel(inj);
    CHECK(inj[0].dur_us == 0 && inj[0].seq == 5);      /* a live command: seq moves */
    CHECK(inj[1].seq == 2 && inj[2].seq == 0);         /* nothing pending: unchanged */
    inject_cancel(inj);
    CHECK(inj[0].seq == 5);
}

static void test_crank_poll_before_last(void)         /* C2 */
{
    crank_t c; crank_reset(&c);
    uint32_t t = 0; int tooth = 0;
    spin(&c, 1500, 150, &t, &tooth);
    crank_poll(&c, t - 5);
    CHECK(crank_fault(&c) == CRANK_F_NONE && crank_synced(&c));
}

static void test_crank_stray_cam(void)                /* I1 */
{
    crank_t c; crank_reset(&c);
    uint32_t t = 0; int tooth = 0;
    spin(&c, 600, 116, &t, &tooth);
    while (tooth != 20) spin(&c, 600, 1, &t, &tooth);  /* rev 0, edge 20 */
    CHECK(crank_phased(&c));
    crank_cam(&c, t + 5);                              /* noise */
    while (tooth != 58) spin(&c, 600, 1, &t, &tooth);  /* past the next gap */
    CHECK(!crank_phased(&c));
    while (tooth != 0) spin(&c, 600, 1, &t, &tooth);   /* real cam, then gap */
    CHECK(crank_phased(&c) && crank_angle(&c) == 0.0f);
}

static void test_sens_hold_while_bad(void)            /* I2 */
{
    sens_t s; float v[S_N];
    sens_reset(&s); all_volts(v, 2.5f);
    for (int i = 0; i < 10; i++) sens_step_1ms(&s, v, 5.0f);
    v[S_CLT] = 5.1f; v[S_RAIL] = 0.0f;
    for (int i = 0; i < 50; i++) sens_step_1ms(&s, v, 5.0f);
    CHECK(fabsf(s.val[S_CLT] - 20.1f) <= 0.5f);
    CHECK(fabsf(s.val[S_RAIL] - 900.0f) <= 0.5f);
}

static void test_crank_glitch(void)                   /* I3 */
{
    crank_t c; crank_reset(&c);
    uint32_t t = 0; int tooth = 0;
    spin(&c, 1500, 150, &t, &tooth);
    while (tooth % 58 != 30) spin(&c, 1500, 1, &t, &tooth);
    crank_edge(&c, t + 200);                           /* 30 % into a 667 us tooth */
    CHECK(near(crank_rpm(&c), 1500, 0.005f));
    for (int i = 0; i < 70; i++) {
        spin(&c, 1500, 1, &t, &tooth);
        CHECK(near(crank_rpm(&c), 1500, 0.005f));
    }
    CHECK(crank_fault(&c) == CRANK_F_NONE);
}

static void test_gov_ramp(void)                       /* I4 */
{
    gov_t g; gov_reset(&g, 30, 400);
    CHECK(fabsf(gov_step(&g, 400, 0, 0.001f) - 30.0f) <= 1.0f);   /* bumpless */
    for (int i = 1; i < 1000; i++) gov_step(&g, 400, 0, 0.001f);
    CHECK(fabsf(g.set - (400 + GOV_RAMP_RPM_S)) <= 2.0f);
}

static void test_ecu_rpm_decays(void)                 /* I5 */
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);
    tick_t = t;
    io.ignition = 0;
    ticks(&io, 60, 1);
    CHECK(io.rpm == 0.0f);
}

static void test_sens_clt_hot_not_short(void)         /* I6 */
{
    sens_t s; float v[S_N];
    sens_reset(&s); all_volts(v, 2.5f); v[S_CLT] = 0.15f;
    for (int i = 0; i < 200; i++) sens_step_1ms(&s, v, 5.0f);
    CHECK(s.fmi[S_CLT] == 0 && s.val[S_CLT] > 125.0f);
}

static void test_inject_lead(void)                    /* I7 */
{
    crank_t c; crank_reset(&c);
    ecu_inj inj = { 0, 0, 0 };
    uint32_t t = 0; int tooth = 0;
    spin(&c, 1500, 116, &t, &tooth);
    while (tooth != 0) spin(&c, 1500, 1, &t, &tooth);
    for (int i = 0; i < 116; i++) {
        if (inject_cyl(&c, 84.0f, 20, 1000, &inj))    /* SOI exactly on edge 14 */
            CHECK(inj.start_us - crank_last_us(&c) >= 100);
        spin(&c, 1500, 1, &t, &tooth);
    }
    CHECK(inj.seq == 1);
}

/* ---- production field fixes ---- */

static void test_ecu_lost_tooth(void)                 /* M1 */
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);
    while (tooth % 58 != 20) ecu_spin(&io, 1500, 1, &t, &tooth, 1);
    next_edge(1500, &t, &tooth);              /* this tooth goes missing */
    ecu_spin(&io, 1500, 1, &t, &tooth, 0);
    CHECK(io.state == ECU_SHUTDOWN);
    tick_t = t;
    CHECK(dm1_first_spn(&io, SPN_POS));
}

static void test_ecu_ms_wrap(void)                    /* M2 */
{
    ecu_io io; ecu_up(&io);
    ticks(&io, ECU_MS_WRAP - 100, 1);
    int last_eec1 = -1, last_dm1 = -1, bad = 0, seen = 0;
    for (int i = 0; i < 2000; i++) {
        ticks(&io, 1, 0);
        for (int k = 0; k < io.can_n; k++) {
            uint32_t pgn = io.can[k].id >> 8 & 0xFFFF;
            if (pgn == 0xF004) { if (last_eec1 >= 0) bad += i - last_eec1 != 20; last_eec1 = i; seen++; }
            if (pgn == 0xFECA) { if (last_dm1 >= 0) bad += i - last_dm1 != 1000; last_dm1 = i; }
        }
        io.can_n = 0;
    }
    CHECK(seen >= 99 && last_dm1 >= 0);
    CHECK(bad == 0);
}

static void test_ecu_bam_not_split(void)              /* M5 */
{
    ecu_io io; ecu_up(&io);
    io.v_clt = 4.95f; io.v_oil = 0.1f; io.v_boost = 4.95f;
    ticks(&io, 150, 1);
    CHECK(io.fault_n == 3);
    ticks(&io, 850, 0);                       /* queue full when DM1 (a BAM) is due */
    CHECK(io.can_drops > 0);
    io.can_n = 0;
    int dt = 0;
    for (int i = 0; i < 300; i++) {
        ticks(&io, 1, 0);
        for (int k = 0; k < io.can_n; k++) dt += (io.can[k].id >> 16 & 0xFF) == 0xEB;
        io.can_n = 0;
    }
    CHECK(dt == 0);
}

/* ---- persistent image ---- */

static nvm_image na, nb;

static void test_nvm_size(void) { CHECK(sizeof(nvm_image) <= 4096); }

static void test_crc32(void) { CHECK(nvm_crc32("123456789", 9) == 0xCBF43926u); }

static void test_nvm_pick(void)
{
    nvm_fresh(&na); nvm_seal(&na);
    nb = na;        nvm_seal(&nb);
    CHECK(na.h.seq == 1 && nb.h.seq == 2);
    CHECK(nvm_pick(&na, &nb, sizeof na) == 1);
    CHECK(nvm_pick(&nb, &na, sizeof na) == 0);
    ((uint8_t *)&nb)[1000] ^= 1;
    CHECK(nvm_pick(&na, &nb, sizeof na) == 0);
    memset(&na, 0, sizeof na); memset(&nb, 0, sizeof nb);
    CHECK(nvm_pick(&na, &nb, sizeof na) == -1);
    nvm_fresh(&na); nvm_seal(&na);
    CHECK(nvm_pick(&na, &na, sizeof na - 1) == -1);   /* wrong length */
}

static void test_nvm_old_version(void)
{
    nvm_fresh(&na);
    na.h.version = 0;
    nvm_seal(&na);                            /* CRC correct for the old layout */
    CHECK(!nvm_valid(&na, sizeof na));
}

static void test_ecu_nvm_load(void)
{
    ecu_io io; ecu_up(&io);
    nvm_fresh(&na); na.c.starts = 7; nvm_seal(&na);
    memset(&nb, 0, sizeof nb);
    ecu_nvm_load(&io, &nb, &na, sizeof na);
    uint32_t len = 0;
    const nvm_image *img = ecu_nvm_image(&len);
    CHECK(len == sizeof(nvm_image));
    CHECK(img->c.starts == 7);                /* blank slot A ignored, slot B taken */
}

/* ---- events, counters, saves, watchdog ---- */

static const nvm_image *live(void) { return ecu_nvm_live(); }

static void test_log_ring(void)
{
    nvm_fresh(&na);
    for (int i = 1; i <= 70; i++) log_event(&na, (uint32_t)i, EV_CRANK, (uint16_t)i, 0);
    CHECK(na.ev_n == 64);
    CHECK(log_event_at(&na, 0)->arg == 70);
    CHECK(log_event_at(&na, 63)->arg == 7);
    CHECK(log_event_at(&na, 64) == NULL);
}

static void test_ecu_wdg_needs_background(void)
{
    ecu_io io; ecu_up(&io);
    ticks(&io, 100, 1);                       /* healthy: WDI toggling */
    uint8_t last = io.wdg; int late_changes = 0, changes = 0;
    for (int i = 0; i < 100; i++) {           /* main loop hung, interrupts alive */
        tick_t += 1000;
        ecu_tick_1ms(&io, tick_t);
        if (io.wdg != last) { changes++; if (i >= 50) late_changes++; last = io.wdg; }
    }
    CHECK(late_changes == 0);
    CHECK(changes <= 10);
    int back = 0;
    for (int i = 0; i < 20; i++) { ticks(&io, 1, 1); back += io.wdg != last; last = io.wdg; }
    CHECK(back == 4);                         /* kicks resume with the loop */
}

static void test_ecu_power_on_event(void)
{
    ecu_io io; ecu_up(&io);
    io.reset_cause = 1;
    ecu_nvm_load(&io, NULL, NULL, 0);
    const nvm_event *e = log_event_at(live(), 0);
    CHECK(e && e->code == EV_POWER_ON && e->arg == 1);
    CHECK(log_event_at(live(), 1)->code == EV_NVM_RESET);
    CHECK(live()->c.wdg_resets == 1);
}

static void test_ecu_hour(void)
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);
    CHECK(io.state == ECU_RUN && seals >= 1);  /* the start was saved */
    uint32_t e0 = live()->c.engine_s;
    seals = 0;
    ecu_spin(&io, 1500, (int)(3600.0 * 1500 / 60 * 58), &t, &tooth, 1);
    CHECK(live()->c.engine_s - e0 >= 3599 && live()->c.engine_s - e0 <= 3601);
    CHECK(seals == 1);
    CHECK(live()->c.band_s[0] >= 3599);       /* no load: lowest band */
}

static void test_ecu_save_rate(void)
{
    ecu_io io; ecu_up(&io);
    ticks(&io, 100, 1);
    int when[8], n = 0;
    for (int ms = 0; ms < 15000; ms++) {
        int phase = ms % 600;
        if (ms < 2400) io.ignition = phase < 100 ? 1 : 0;   /* off: SHUTDOWN every 0.6 s */
        else io.ignition = 0;
        int before = seals;
        ticks(&io, 1, 1);
        if (seals != before && n < 8) when[n++] = ms;
    }
    CHECK(n == 2);
    CHECK(n == 2 && when[1] - when[0] >= 10000);
}

static void test_ecu_storage_dead(void)
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);
    host_dead = 1;
    uint8_t n0 = live()->ev_n;
    io.ignition = 0;
    ecu_spin(&io, 1500, 2000, &t, &tooth, 1);
    io.ignition = 1;
    tick_t = t;
    ticks(&io, 20000, 1);
    CHECK(io.state == ECU_SHUTDOWN);
    CHECK(io.nvm_save == 1);
    CHECK(live()->ev_n > n0);
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
    test_gov();
    test_rail();
    test_inject_dur();
    test_inject_once_per_cycle();
    test_inject_soi_in_gap();
    test_safety();
    test_faults();
    test_j1939_id();
    test_eec1();
    test_et1();
    test_dm1_single();
    test_dm1_bam();
    test_dm1_spn_high();
    test_ecu_start();
    test_ecu_overspeed_edge();
    test_ecu_ignition();
    test_ecu_crank_loss();
    test_ecu_wdg();
    test_ecu_can_rates();
    test_ecu_can_overflow();
    test_ecu_sensor_fault_clears();
    test_inject_cancel_visible();
    test_crank_poll_before_last();
    test_crank_stray_cam();
    test_sens_hold_while_bad();
    test_crank_glitch();
    test_gov_ramp();
    test_ecu_rpm_decays();
    test_sens_clt_hot_not_short();
    test_inject_lead();
    test_ecu_shutdown_valve_closed();
    test_ecu_tick_before_edge();
    test_crank_after_pause();
    test_ecu_ignition_dip_keeps_latch();
    test_ecu_lost_tooth();
    test_ecu_ms_wrap();
    test_ecu_bam_not_split();
    test_nvm_size();
    test_crc32();
    test_nvm_pick();
    test_nvm_old_version();
    test_ecu_nvm_load();
    test_log_ring();
    test_ecu_wdg_needs_background();
    test_ecu_power_on_event();
    test_ecu_hour();
    test_ecu_save_rate();
    test_ecu_storage_dead();
    printf("%s: %d failure(s)\n", fails ? "FAIL" : "ok", fails);
    return fails != 0;
}
