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
#include "isotp.h"
#include "link.h"
#include "eol.h"
#include "service.h"

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
    float d = 0;
    for (int i = 0; i < 500; i++)              /* high first: move off the end stop */
        d = rail_step(&r, 1000, 1100, 0.001f);
    float d0 = d;
    for (int i = 0; i < 1000; i++) {
        d = rail_step(&r, 1000, 900, 0.001f);
        CHECK(d >= 0.0f && d <= 1.0f);
    }
    CHECK(METER_NC ? d > d0 : d < d0);        /* low pressure: open the valve further */
    for (int i = 0; i < 2000; i++) d = rail_step(&r, 1000, 1500, 0.001f);
    CHECK(d == METER_CLOSED);                 /* high pressure: valve shut */
    /* The old ECU's recording: current falls as pressure rises, and rises
     * to stop the engine. A normally-open valve: full duty closes it. */
    CHECK(METER_NC == 0 && METER_CLOSED == 1.0f);
}

/* Rail setpoint and start of injection follow fuel, as the old ECU's
 * own tables do at 1500 rpm (field evidence 2026-10-14). */
static void test_cal_tables(void)
{
    CHECK(fabsf(rail_set_bar(6.5f) - 827.0f) <= 1.0f);
    CHECK(fabsf(rail_set_bar(12.0f) - 994.0f) <= 1.0f);
    CHECK(fabsf(rail_set_bar(0.0f) - 827.0f) <= 1.0f);   /* held below the data */
    CHECK(fabsf(rail_set_bar(45.0f) - 1171.0f) <= 1.0f); /* and above it */
    CHECK(rail_set_bar(9.0f) > rail_set_bar(8.5f) && rail_set_bar(9.0f) < rail_set_bar(9.5f));
    CHECK(fabsf(inject_soi_btdc(6.5f) - 11.5f) <= 0.05f);
    CHECK(fabsf(inject_soi_btdc(17.0f) - 15.9f) <= 0.05f);
    CHECK(fabsf(inject_soi_btdc(45.0f) - 14.2f) <= 0.05f);
}

static void test_inject_dur(void)
{
    /* measured on the old ECU: energising time at fuel and rail pressure */
    CHECK(fabsf((float)inject_dur_us(11.4f, 941) - 513.5f) <= 6.0f);
    CHECK(fabsf((float)inject_dur_us(15.2f, 1039) - 567.1f) <= 6.0f);
    CHECK(fabsf((float)inject_dur_us(6.7f, 827) - 446.7f) <= 6.0f);
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
        if (tooth == 12 && !checked) {         /* edge at 72 deg, SOI 90 - table(20 mg) */
            t84 = t;
            float ahead = 90.0f - inject_soi_btdc(20) - 72.0f;
            CHECK(fabsf((float)(inj[0].start_us - t84) - ahead * 1e6f / 9000.0f) <= 5.0f);
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
    eol_record r;
    eol_default(&r);
    eol_seal(&r);
    ecu_eol_load(io, &r, &r);              /* a unit that passed the line */
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

/* Edges at `rpm`, with 1 ms ticks interleaved when with_ticks. The last
 * DM1's lamp byte seen while spinning is kept in spin_lamps. */
static uint8_t spin_lamps;
static void ecu_spin(ecu_io *io, float rpm, int edges, uint32_t *t, int *tooth, int with_ticks)
{
    for (int i = 0; i < edges; i++) {
        int cam = next_edge(rpm, t, tooth);
        while (with_ticks && tick_t + 1000 <= *t) {
            tick_t += 1000;
            host_tick(io);
            for (int k = 0; k < io->can_n; k++)
                if (io->can[k].id == 0x18FECAEAu) spin_lamps = io->can[k].data[0];
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
 * (0 = the empty "no fault" DTC). Its lamp byte is left in dm1_lamps. */
static uint8_t dm1_lamps, dm1_fmi;
static int dm1_first_spn(ecu_io *io, uint32_t spn)
{
    for (int i = 0; i < 1000; i++) {
        tick_t += 1000;
        host_tick(io);
        for (int k = 0; k < io->can_n; k++) {
            ecu_can *f = &io->can[k];
            if (f->id == 0x18FECAEAu) {
                uint32_t got = f->data[2] | f->data[3] << 8 | (uint32_t)(f->data[4] & 0xE0) << 11;
                dm1_lamps = f->data[0];
                dm1_fmi = f->data[4] & 0x1F;
                io->can_n = 0;
                return got == spn;
            }
        }
        io->can_n = 0;
    }
    return 0;
}

/* Edges at `rpm`, ticks interleaved, for `dur` ms of simulated time. */
static void ecu_hold(ecu_io *io, float rpm, uint32_t dur, uint32_t *t, int *tooth)
{
    uint32_t end = tick_t + dur * 1000u;         /* tick_t is in us */
    while (tick_t < end)
        ecu_spin(io, rpm, 1, t, tooth, 1);
}

static void test_underspeed(void)
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);
    ecu_hold(&io, 1500, 3000, &t, &tooth);          /* the setpoint ramp is over */
    CHECK(io.fault_n == 0);
    ecu_hold(&io, 1340, 2900, &t, &tooth);
    CHECK(io.fault_n == 0);
    ecu_hold(&io, 1340, 200, &t, &tooth);
    CHECK(io.fault_n == 1);
    CHECK(io.state == ECU_RUN);                      /* a warning, never a shutdown */
    ecu_hold(&io, 1410, 900, &t, &tooth);
    CHECK(io.fault_n == 1);
    ecu_hold(&io, 1410, 200, &t, &tooth);
    CHECK(io.fault_n == 0);
    ecu_hold(&io, 1340, 4200, &t, &tooth);           /* and one DM1 after it rose */
    const nvm_dtc *d = log_dtc_find(ecu_nvm_live(), SPN_SPEED, FMI_LOW_MODERATE);
    CHECK(d && (d->status & DTC_ACTIVE));
    CHECK(spin_lamps == LAMP_AMBER);                 /* not Protect: the DSE decides */
}

/* ---- service link framing ---- */
static uint8_t msg_a[ISOTP_MAX], msg_b[ISOTP_MAX];

/* Send `n` bytes from one end to the other, frame by frame, the flow
 * control going back. `drop` = index of a consecutive frame to lose (0 none;
 * negative: that frame arrives twice).
 * Returns the length delivered, -1 if nothing arrived. */
static int isotp_pass(isotp_t *tx, isotp_t *rx, const uint8_t *m, uint16_t n, int drop)
{
    uint16_t got = 0;
    int delivered = -1, cf = 0;
    CHECK(isotp_send(tx, m, n) == 0);
    for (int guard = 0; guard < 2000; guard++) {
        ecu_can f;
        int moved = 0;
        if (isotp_next(tx, &f)) {
            moved = 1;
            CHECK(f.id == tx->tx_id && f.len == 8);
            if ((f.data[0] >> 4) == 2 && ++cf == drop)
                continue;                               /* lost on the bus */
            if (isotp_rx(rx, &f, msg_b, &got))
                delivered = got;
            if (cf == -drop && (f.data[0] >> 4) == 2 && isotp_rx(rx, &f, msg_b, &got))
                delivered = got;                        /* repeated on the bus */
        }
        if (isotp_next(rx, &f)) {                       /* flow control back */
            moved = 1;
            isotp_rx(tx, &f, msg_a, &got);
        }
        if (!moved)
            break;
    }
    return delivered;
}

static void test_isotp_roundtrip(void)
{
    static isotp_t a, b;
    isotp_init(&a, 0x7E0);
    isotp_init(&b, 0x7E8);
    static uint8_t m[ISOTP_MAX];
    for (int i = 0; i < ISOTP_MAX; i++) m[i] = (uint8_t)(i * 7 + 3);
    const uint16_t lens[] = { 1, 7, 8, ISOTP_MAX };
    for (int k = 0; k < 4; k++) {
        memset(msg_b, 0, sizeof msg_b);
        CHECK(isotp_pass(&a, &b, m, lens[k], 0) == lens[k]);
        CHECK(memcmp(msg_b, m, lens[k]) == 0);
    }
    CHECK(isotp_send(&a, m, ISOTP_MAX + 1) == -1);
    CHECK(isotp_send(&a, m, 0) == -1);
}

static void test_isotp_lost_cf(void)
{
    static isotp_t a, b;
    isotp_init(&a, 0x7E0);
    isotp_init(&b, 0x7E8);
    uint8_t m[100];
    for (int i = 0; i < 100; i++) m[i] = (uint8_t)i;
    CHECK(isotp_pass(&a, &b, m, 100, 3) == -1);       /* never a corrupted message */
    CHECK(isotp_pass(&a, &b, m, 100, -3) == -1);      /* nor a repeated frame's */
    m[0] = 0x5A;
    CHECK(isotp_pass(&a, &b, m, 100, 0) == 100);      /* the next one still arrives */
    CHECK(memcmp(msg_b, m, 100) == 0);
}

static void test_link_roundtrip(void)
{
    CHECK(crc16_ccitt((const uint8_t *)"123456789", 9) == 0x29B1);   /* CRC-16/CCITT-FALSE */
    static link_rx_t r;
    memset(&r, 0, sizeof r);
    uint8_t m[300], fr[310];
    for (int i = 0; i < 300; i++) m[i] = (uint8_t)(255 - i);
    uint16_t n = link_frame(m, 300, fr), len = 0;
    CHECK(n == 305 && fr[0] == 0x55);
    int whole = 0;
    for (uint16_t i = 0; i < n; i++)
        whole += link_feed(&r, fr[i], msg_b, &len);
    CHECK(whole == 1 && len == 300 && memcmp(msg_b, m, 300) == 0);
}

static void test_link_bad_crc(void)
{
    static link_rx_t r;
    memset(&r, 0, sizeof r);
    uint8_t m[10] = { 0x22, 0xF1, 0x8C }, fr[40];
    uint16_t len = 0;
    uint16_t n = link_frame(m, 3, fr);
    fr[n - 1] ^= 0x01;                                  /* corrupted on the wire */
    n += link_frame(m, 10, fr + n);
    int whole = 0;
    for (uint16_t i = 0; i < n; i++)
        whole += link_feed(&r, fr[i], msg_b, &len);
    CHECK(whole == 1 && len == 10);                      /* only the good one */
    uint8_t big[] = { 0x55, 0xFF, 0x0F };                /* 4095 + 1 would follow: too long */
    big[1] = 0x00; big[2] = 0x10;
    for (int i = 0; i < 3; i++) whole += link_feed(&r, big[i], msg_b, &len);
    n = link_frame(m, 3, fr);
    for (uint16_t i = 0; i < n; i++) whole += link_feed(&r, fr[i], msg_b, &len);
    CHECK(whole == 2 && len == 3);                       /* resynchronised on the next 0x55 */
}

/* ---- service core ---- */
static uint8_t rsp[600];

/* One UDS request over the USB link; returns the response length (0 none). */
static uint16_t uds(ecu_io *io, const uint8_t *req, uint16_t n)
{
    static link_rx_t r;
    uint8_t fr[80];
    uint16_t m = link_frame(req, n, fr), len = 0, got = 0;
    for (uint16_t i = 0; i < m; i += 64) {
        io->usb_in_n = (uint8_t)(m - i < 64 ? m - i : 64);
        memcpy(io->usb_in, fr + i, io->usb_in_n);
        ecu_background(io);
    }
    for (uint16_t i = 0; i < io->usb_out_n; i++)
        if (link_feed(&r, io->usb_out[i], rsp, &len))
            got = len;
    io->usb_out_n = 0;
    return got;
}

#define UDS(io, ...) uds(io, (const uint8_t[]){ __VA_ARGS__ }, sizeof((const uint8_t[]){ __VA_ARGS__ }))

static void unlock(ecu_io *io)
{
    CHECK(UDS(io, 0x10, 0x03) >= 2 && rsp[0] == 0x50);
    CHECK(UDS(io, 0x27, 0x01) == 6 && rsp[0] == 0x67);
    uint32_t seed = rsp[2] | rsp[3] << 8 | rsp[4] << 16 | (uint32_t)rsp[5] << 24;
    uint32_t k = svc_key(seed);
    CHECK(UDS(io, 0x27, 0x02, (uint8_t)k, (uint8_t)(k >> 8), (uint8_t)(k >> 16),
              (uint8_t)(k >> 24)) == 2 && rsp[0] == 0x67);
}

static int nrc(uint16_t n, uint8_t sid, uint8_t code)
{
    return n == 3 && rsp[0] == 0x7F && rsp[1] == sid && rsp[2] == code;
}

static uint16_t direct(svc_t *s, const uint8_t *req, uint16_t n, uint32_t ms)
{
    return svc_handle(s, req, n, rsp, ms, ms * 1000u + 17, 1, NULL);
}
#define DIRECT(s, ms, ...) direct(s, (const uint8_t[]){ __VA_ARGS__ }, \
    sizeof((const uint8_t[]){ __VA_ARGS__ }), ms)

static uint32_t seed_of(void) { return rsp[2] | rsp[3] << 8 | rsp[4] << 16 | (uint32_t)rsp[5] << 24; }

static uint16_t key_req(svc_t *s, uint32_t k, uint32_t ms)
{
    const uint8_t q[] = { 0x27, 0x02, (uint8_t)k, (uint8_t)(k >> 8), (uint8_t)(k >> 16), (uint8_t)(k >> 24) };
    return direct(s, q, 6, ms);
}

static void test_svc_seed_key(void)
{
    static svc_t s;
    svc_init(&s, 0);
    CHECK(nrc(DIRECT(&s, 10, 0x27, 0x01), 0x27, 0x7F));      /* not in the default session */
    CHECK(DIRECT(&s, 10, 0x10, 0x03) == 6 && rsp[0] == 0x50 && rsp[1] == 0x03);
    CHECK(svc_handle(&s, (const uint8_t[]){ 0x27, 0x01 }, 2, rsp, 10, 0, 1, NULL) == 6
          && seed_of() != 0);                                  /* us 0: still not 0 */
    CHECK(nrc(key_req(&s, 0, 20), 0x27, 0x35));                /* a seed is out: wrong key 1 */
    for (int i = 0; i < 2; i++) {
        CHECK(DIRECT(&s, 30 + 20 * i, 0x27, 0x01) == 6);
        CHECK(nrc(key_req(&s, svc_key(seed_of()) + 1, 40 + 20 * i), 0x27, i == 0 ? 0x35 : 0x36));
    }
    CHECK(!svc_unlocked(&s));
    CHECK(DIRECT(&s, 4000, 0x3E, 0x00) == 2 && rsp[0] == 0x7E);
    CHECK(DIRECT(&s, 8000, 0x3E, 0x00) == 2);
    CHECK(nrc(DIRECT(&s, 10059, 0x27, 0x01), 0x27, 0x36));     /* locked out for 10 s */
    CHECK(DIRECT(&s, 10061, 0x27, 0x01) == 6);
    CHECK(key_req(&s, svc_key(seed_of()), 10062) == 2 && rsp[0] == 0x67 && rsp[1] == 0x02);
    CHECK(svc_unlocked(&s));
    CHECK(nrc(key_req(&s, 1, 10063), 0x27, 0x24));             /* no seed out */
    CHECK(DIRECT(&s, 10064, 0x3E, 0x80) == 0);                 /* suppressed response */
}

static void test_svc_timeout(void)
{
    static svc_t s;
    svc_init(&s, 0);
    CHECK(DIRECT(&s, 100, 0x10, 0x03) == 6);
    CHECK(DIRECT(&s, 100, 0x27, 0x01) == 6);
    CHECK(key_req(&s, svc_key(seed_of()), 100) == 2 && svc_unlocked(&s));
    svc_tick(&s, 5100, 1);
    CHECK(svc_session(&s) == 3 && svc_unlocked(&s));
    svc_tick(&s, 5101 + 1, 1);
    CHECK(svc_session(&s) == 1 && !svc_unlocked(&s));
}

static void test_svc_engine_turning(void)
{
    ecu_io io; uint32_t t = 0; int tooth = 0;
    ecu_up(&io);
    ticks(&io, 1, 1);
    ecu_spin(&io, 300, 174, &t, &tooth, 1);
    CHECK(io.state == ECU_CRANK);
    CHECK(nrc(UDS(&io, 0x10, 0x03), 0x10, 0x22));
    CHECK(nrc(UDS(&io, 0x10, 0x02), 0x10, 0x22));
    ecu_up(&io);
    t = 0; tooth = 0;
    ticks(&io, 1100, 1);                                       /* WAIT, no tooth for 1 s */
    CHECK(UDS(&io, 0x10, 0x03) == 6 && io.session == 3);
    tick_t = 1100000; t = tick_t;
    ecu_spin(&io, 300, 40, &t, &tooth, 1);                     /* someone cranks it */
    CHECK(io.session == 1);
}

static void eol_write_ok(ecu_io *io, const uint8_t *q, uint16_t n)
{
    io->eol_save = 0;
    CHECK(uds(io, q, n) == 3 && rsp[0] == 0x6E && rsp[1] == q[1] && rsp[2] == q[2]);
    CHECK(io->eol_save == 1);
}

static void test_eol_write_lock(void)
{
    ecu_io io;
    ecu_up(&io);
    ticks(&io, 1100, 1);
    unlock(&io);
    const uint8_t sn[] = { 0x2E, 0xF1, 0x8C, 'S', 'N', '0', '0', '0', '1' };
    eol_write_ok(&io, sn, sizeof sn);
    uint8_t tr[3 + 48] = { 0x2E, 0x01, 0x00 };
    float g[12] = { 1.01f, 1, 1, 1, 1, 0.99f, 0.02f, 0, 0, 0, 0, -0.01f };
    memcpy(tr + 3, g, 48);
    eol_write_ok(&io, tr, sizeof tr);
    CHECK(UDS(&io, 0x22, 0xF1, 0x8C) == 19 && rsp[0] == 0x62 && memcmp(rsp + 3, "SN0001\0", 7) == 0);
    CHECK(UDS(&io, 0x22, 0x01, 0x00) == 51 && memcmp(rsp + 3, g, 48) == 0);
    uint32_t len;
    const eol_record *img = ecu_eol_image(&len);
    CHECK(len == sizeof(eol_record) && eol_valid(img) && img->gain[0] == 1.01f);
    io.eol_save = 0;
    CHECK(UDS(&io, 0x31, 0x01, 0xF0, 0x00) == 4 && rsp[0] == 0x71 && io.eol_save == 1);
    CHECK(img->locked == 1);
    CHECK(nrc(uds(&io, sn, sizeof sn), 0x2E, 0x22));          /* locked */
    CHECK(UDS(&io, 0x22, 0x01, 0x01) == 6 && rsp[5] == 1);
    CHECK(UDS(&io, 0x31, 0x01, 0xF0, 0x01) == 4 && img->locked == 0);
    eol_write_ok(&io, sn, sizeof sn);
}

static void test_eol_trim_range(void)
{
    ecu_io io;
    ecu_up(&io);
    ticks(&io, 1100, 1);
    unlock(&io);
    uint8_t tr[3 + 48] = { 0x2E, 0x01, 0x00 };
    float g[12] = { 1.2f, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0 };
    memcpy(tr + 3, g, 48);
    CHECK(nrc(uds(&io, tr, sizeof tr), 0x2E, 0x31));
    g[0] = 1; g[6] = 0.2f;
    memcpy(tr + 3, g, 48);
    CHECK(nrc(uds(&io, tr, sizeof tr), 0x2E, 0x31));
    CHECK(nrc(UDS(&io, 0x2E, 0x01, 0x00, 1, 2), 0x2E, 0x13));   /* wrong length */
}

static void test_eol_missing_raises_628(void)
{
    ecu_io io;
    ecu_up(&io);
    static eol_record blank;
    memset(&blank, 0, sizeof blank);
    ecu_eol_load(&io, &blank, &blank);
    ticks(&io, 10, 1);
    const nvm_dtc *d = log_dtc_find(ecu_nvm_live(), 628, 13);
    CHECK(d && (d->status & DTC_ACTIVE));
    CHECK(near(io.clt_c, sens_convert(S_CLT, 2.5f), 1e-4f));     /* gain 1, offset 0 */
}

static void test_trim_applied(void)
{
    ecu_io io;
    ecu_up(&io);
    eol_record r;
    eol_default(&r);
    r.gain[S_CLT] = 1.05f;
    eol_seal(&r);
    ecu_eol_load(&io, &r, &r);
    ticks(&io, 10, 1);
    CHECK(near(io.clt_c, sens_convert(S_CLT, 2.5f * 1.05f), 1e-4f));
    CHECK(io.fault_n == 0);
}

static void test_boot_request(void)
{
    ecu_io io;
    ecu_up(&io);
    ticks(&io, 1100, 1);
    CHECK(UDS(&io, 0x10, 0x03) == 6);
    CHECK(nrc(UDS(&io, 0x10, 0x02), 0x10, 0x33));              /* not unlocked */
    CHECK(io.boot_req == 0);
    unlock(&io);
    CHECK(UDS(&io, 0x10, 0x02) == 6 && rsp[0] == 0x50 && rsp[1] == 0x02);
    CHECK(io.boot_req == 1);
    CHECK(UDS(&io, 0x11, 0x01) == 2 && rsp[0] == 0x51 && io.reset_req == 1);
}

static void test_can2_read(void)
{
    ecu_io io;
    ecu_up(&io);
    ticks(&io, 1100, 1);
    static isotp_t tester;
    isotp_init(&tester, 0x7E0);
    ecu_can f;
    CHECK(isotp_send(&tester, (const uint8_t[]){ 0x22, 0xF1, 0x8C }, 3) == 0);
    CHECK(isotp_next(&tester, &f));
    ecu_can other = f;
    other.id = 0x7E1;
    ecu_can2_rx(&io, &other);                                   /* not ours */
    ecu_can2_rx(&io, &f);
    uint16_t len = 0;
    int got = 0;
    for (int ms = 0; ms < 20 && !got; ms++) {
        ticks(&io, 1, 1);
        for (int k = 0; k < io.can2_n; k++) {
            CHECK(io.can2[k].id == 0x7E8);
            got |= isotp_rx(&tester, &io.can2[k], rsp, &len);
        }
        io.can2_n = 0;
        if (isotp_next(&tester, &f))                            /* flow control */
            ecu_can2_rx(&io, &f);
    }
    CHECK(got && len == 19 && rsp[0] == 0x62);
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
    CHECK(dm1_lamps == (LAMP_RED | LAMP_PROTECT));   /* the DSE shuts down on Protect */
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
    CHECK(dm1_lamps == (LAMP_RED | LAMP_PROTECT));
}

static void test_ecu_sensor_lamp(void)
{
    ecu_io io; ecu_up(&io);
    io.v_clt = 4.95f; ticks(&io, 150, 1);
    CHECK(dm1_first_spn(&io, 110));
    CHECK(dm1_lamps == LAMP_AMBER);           /* a sensor fault is a warning, never Protect */
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

/* ---- DTC memory ---- */

static void test_dtc_first_and_count(void)
{
    nvm_fresh(&na);
    log_snap s1 = { 1000, 0.5f, 17, 1000, 85, 400, 24.0f, ECU_RUN };
    log_snap s2 = s1; s2.rpm = 2000;
    CHECK(log_dtc_set(&na, 110, 3, 5, &s1) == 1);
    CHECK(log_dtc_set(&na, 110, 3, 9, &s2) == 0);
    const nvm_dtc *d = log_dtc_find(&na, 110, 3);
    CHECK(d && d->oc == 2 && d->rpm == 1000 && d->first_s == 5 && d->last_s == 9);
    CHECK(d && d->load_pct == 50 && d->fuel_q == 68 && d->clt_p40 == 125 && d->oil_q == 100 && d->vbat_q == 120);
    CHECK(d && (d->status & 1) && (d->status >> 4) == ECU_RUN);
    log_dtc_inactive(&na, 110, 3);
    d = log_dtc_find(&na, 110, 3);
    CHECK(d && !(d->status & 1));
}

static void test_dtc_full(void)
{
    nvm_fresh(&na);
    log_snap z = { 0 };
    for (uint32_t i = 1; i <= NVM_DTCS; i++) {
        log_dtc_set(&na, 500 + i, 4, i, &z);
        log_dtc_inactive(&na, 500 + i, 4);
    }
    CHECK(log_dtc_set(&na, 999, 3, 100, &z) == 1);
    CHECK(log_dtc_find(&na, 501, 4) == NULL);          /* oldest last_s replaced */
    CHECK(log_dtc_find(&na, 502, 4) && log_dtc_find(&na, 999, 3));
}

static void test_dm3_clear(void)
{
    nvm_fresh(&na);
    log_snap z = { 0 };
    log_dtc_set(&na, 1, 3, 1, &z); log_dtc_inactive(&na, 1, 3);
    log_dtc_set(&na, 2, 3, 1, &z); log_dtc_inactive(&na, 2, 3);
    log_dtc_set(&na, 3, 3, 1, &z);
    CHECK(log_dm3_clear(&na) == 2);
    CHECK(!log_dtc_find(&na, 1, 3) && !log_dtc_find(&na, 2, 3) && log_dtc_find(&na, 3, 3));
}

static void test_ecu_history_survives_ignition_cycle(void)
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);
    for (float rpm = 1500; rpm < 1700 && io.state == ECU_RUN; rpm += 1)
        ecu_spin(&io, rpm, 1, &t, &tooth, 0);
    CHECK(io.state == ECU_SHUTDOWN);
    tick_t = t;
    io.ignition = 0;
    ticks(&io, IGN_OFF_MS + 100, 1);          /* engine stopped, ignition held off */
    io.ignition = 1;
    ticks(&io, 1, 1);
    CHECK(io.state == ECU_WAIT);
    const nvm_dtc *d = log_dtc_find(live(), SPN_SPEED, 0);
    CHECK(d && !(d->status & 1) && d->oc == 1 && d->rpm >= 1650);
    CHECK(live()->c.trips_overspeed == 1);
}

/* ---- trip recorder ---- */

static rec_sample smp(int i) { rec_sample x = { (uint16_t)i, 0, 0, 0 }; return x; }

static void test_rec_pre_post(void)
{
    rec_t r; rec_reset(&r); nvm_fresh(&na);
    for (int i = 0; i < 300; i++) CHECK(rec_push(&r, &na, smp(i)) == 0);
    rec_trigger(&r, &na, 42, TRIP_OVERSPEED);
    int done = 0;
    for (int i = 300; i < 360; i++) done += rec_push(&r, &na, smp(i));
    CHECK(done == 1);
    const rec_trip *t = &na.rec[0];
    CHECK(t->t_s == 42 && t->reason == TRIP_OVERSPEED);
    CHECK(t->n_pre == 100 && t->s[0].rpm == 200 && t->s[99].rpm == 299);
    CHECK(t->n_post == 50 && t->s[149].rpm == 349);
}

static void test_rec_two_slots(void)
{
    rec_t r; rec_reset(&r); nvm_fresh(&na);
    int used[3];
    for (int k = 0; k < 3; k++) {
        used[k] = na.rec_next;
        rec_trigger(&r, &na, (uint32_t)k, TRIP_SYNC);
        for (int i = 0; i < REC_POST; i++) rec_push(&r, &na, smp(i));
    }
    CHECK(used[0] == 0 && used[1] == 1 && used[2] == 0);
    CHECK(na.rec[0].t_s == 2 && na.rec[1].t_s == 1);
}

static void test_ecu_trip_saves_now(void)
{
    ecu_io io; uint32_t t; int tooth;
    ecu_running(&io, &t, &tooth);             /* the start's save opened the 10 s gap */
    seals = 0;
    for (float rpm = 1500; rpm < 1700 && io.state == ECU_RUN; rpm += 1)
        ecu_spin(&io, rpm, 1, &t, &tooth, 0);
    CHECK(io.state == ECU_SHUTDOWN);
    tick_t = t;
    ticks(&io, 1100, 1);
    CHECK(seals >= 1);
    uint32_t len;
    const nvm_image *o = ecu_nvm_image(&len);
    CHECK(o->rec[0].reason == TRIP_OVERSPEED && o->rec[0].n_post == REC_POST);
}

/* ---- J1939 readout ---- */

static void test_request_parse(void)
{
    ecu_can f = { 0x18EAEA01u, 3, { 0xCB, 0xFE, 0x00 } };
    CHECK(j1939_request_pgn(&f, 234) == 65227);
    f.id = 0x18EAFF01u;
    CHECK(j1939_request_pgn(&f, 234) == 65227);
    f.id = 0x18EA0001u;                       /* addressed to node 0 */
    CHECK(j1939_request_pgn(&f, 234) == 0);
    f.id = 0x18FEEE01u;                       /* not a request */
    CHECK(j1939_request_pgn(&f, 234) == 0);
}

static void test_hours(void)
{
    ecu_can f; j1939_hours(&f, 3600);
    CHECK(f.id == 0x18FEE5EAu);
    CHECK(f.data[0] == 20 && f.data[1] == 0 && f.data[2] == 0 && f.data[3] == 0);
    CHECK(f.data[4] == 0xFF && f.data[7] == 0xFF);
}

static void test_dm2_empty(void)
{
    nvm_fresh(&na);
    ecu_can f[4];
    CHECK(j1939_dm2(f, 4, &na) == 1);
    CHECK((f[0].id >> 8 & 0xFFFF) == 0xFECB);
    CHECK(f[0].data[2] == 0 && f[0].data[3] == 0 && f[0].data[4] == 0 && f[0].data[5] == 0);
}

static void test_dm4_layout(void)
{
    nvm_fresh(&na);
    log_snap s1 = { 1652, 0.8f, 30, 1030, 85, 400, 24.0f, ECU_RUN };
    log_dtc_set(&na, SPN_SPEED, 0, 7, &s1);
    static ecu_can f[48];
    CHECK(j1939_dm4(f, 48, &na) == 4);        /* 18 bytes: TP.CM + 3 TP.DT */
    CHECK(f[0].data[1] == 18 && f[0].data[5] == 0xCD && f[0].data[6] == 0xFE);
    CHECK(f[1].data[1] == 17);                /* freeze frame length */
    CHECK(f[1].data[2] == 190 && f[1].data[5] == 1);   /* SPN low byte, occurrence count */
    CHECK(f[2].data[1] == 0xA0 && f[2].data[2] == 0x33);   /* 1652 / 0.125 = 13216 */
    CHECK(f[2].data[3] == 80 && f[2].data[4] == 125);      /* load %, coolant + 40 */
}

static void test_ecu_dm3_request(void)
{
    ecu_io io; ecu_up(&io);
    io.v_oil = 0.1f;  ticks(&io, 150, 1);
    io.v_oil = 2.5f;  ticks(&io, 150, 1);     /* 100/4 now previously active */
    io.v_clt = 4.95f; ticks(&io, 150, 1);     /* 110/3 active */
    ecu_can r = { 0x18EAFF01u, 3, { 0xCC, 0xFE, 0x00 } };
    ecu_can_rx(&io, &r);
    CHECK(log_dtc_find(live(), 100, 4) == NULL);
    CHECK(log_dtc_find(live(), 110, 3) != NULL);
    CHECK(log_event_at(live(), 0)->code == EV_DM3_CLEAR);
}

static void test_ecu_dm2_waits_for_bam(void)
{
    ecu_io io; ecu_up(&io);
    io.v_oil = 0.1f; io.v_boost = 4.95f; ticks(&io, 150, 1);
    io.v_oil = 2.5f; io.v_boost = 2.5f;  ticks(&io, 150, 1);   /* two stored: DM2 is a BAM */
    io.v_clt = 4.95f; io.v_egr = 0.1f; io.v_rail = 4.95f;      /* three active: DM1 is a BAM */
    int dm1_cm = -1, dm1_last_dt = -1, dm2_cm = -1, dt_seen = 0, asked = 0;
    for (int i = 0; i < 3000 && dm2_cm < 0; i++) {
        ticks(&io, 1, 0);
        for (int k = 0; k < io.can_n; k++) {
            ecu_can *f = &io.can[k];
            int pf = f->id >> 16 & 0xFF;
            if (pf == 0xEC && f->data[5] == 0xCA && dm1_cm < 0) dm1_cm = i;
            if (pf == 0xEC && f->data[5] == 0xCB) dm2_cm = i;
            if (pf == 0xEB && dm1_cm >= 0 && dm2_cm < 0 && ++dt_seen <= 2) dm1_last_dt = i;
        }
        io.can_n = 0;
        if (dm1_cm >= 0 && !asked) {
            ecu_can r = { 0x18EAEA01u, 3, { 0xCB, 0xFE, 0x00 } };
            ecu_can_rx(&io, &r);
            asked = 1;
        }
    }
    CHECK(dm1_cm >= 0 && dm2_cm > dm1_last_dt && dm1_last_dt > dm1_cm);
}

static void test_ecu_load_marks_inactive(void)
{
    ecu_io io; ecu_up(&io);
    nvm_fresh(&na);
    log_snap z = { 0 };
    log_dtc_set(&na, SPN_SPEED, 0, 1, &z);    /* saved while active */
    nvm_seal(&na);
    ecu_nvm_load(&io, &na, NULL, sizeof na);
    const nvm_dtc *d = log_dtc_find(live(), SPN_SPEED, 0);
    CHECK(d && !(d->status & DTC_ACTIVE));    /* nothing is active until detected again */
}

/* ---- final review: production logging ---- */

static void test_ecu_flapping_sensor_keeps_log(void)   /* I1 */
{
    ecu_io io; ecu_up(&io);
    ticks(&io, 10, 1);
    uint8_t head0 = live()->ev_head, n0 = live()->ev_n;
    for (int k = 0; k < 66; k++) {            /* a loose connector, 3.3 Hz for 20 s */
        io.v_oil = 0.1f; ticks(&io, 150, 1);
        io.v_oil = 2.5f; ticks(&io, 150, 1);
    }
    for (int k = 0; k < 100; k++) {           /* a bouncing ignition contact */
        io.ignition = 0; ticks(&io, 1, 1);
        io.ignition = 1; ticks(&io, 1, 1);
    }
    int added = (live()->ev_head - head0 + NVM_EVENTS) % NVM_EVENTS;
    CHECK(n0 + added <= NVM_EVENTS && added <= 4);
}

static void test_ecu_dm1_not_starved(void)            /* I2 */
{
    ecu_io io; ecu_up(&io);
    io.v_oil = 0.1f; io.v_boost = 4.95f; ticks(&io, 150, 1);
    io.v_oil = 2.5f; io.v_boost = 2.5f;  ticks(&io, 150, 1);   /* two stored */
    io.v_clt = 4.95f; io.v_egr = 0.1f; io.v_rail = 4.95f;      /* three active: DM1 is a BAM */
    ticks(&io, 200, 1);
    int dm1 = 0;
    for (int i = 0; i < 20000; i++) {
        if (i % 300 == 0) {                   /* a tool polling freeze frames */
            ecu_can r = { 0x18EAEA01u, 3, { 0xCD, 0xFE, 0x00 } };
            ecu_can_rx(&io, &r);
        }
        ticks(&io, 1, 0);
        for (int k = 0; k < io.can_n; k++)
            dm1 += (io.can[k].id >> 16 & 0xFF) == 0xEC && io.can[k].data[5] == 0xCA;
        io.can_n = 0;
    }
    CHECK(dm1 >= 18);
}

static void test_ecu_wdg_reset_saved(void)            /* I3 */
{
    ecu_io io; ecu_up(&io);
    io.reset_cause = 1;
    ecu_nvm_load(&io, NULL, NULL, 0);
    seals = 0;
    ticks(&io, 12000, 1);                     /* waiting, never cranked */
    uint32_t len;
    const nvm_image *o = ecu_nvm_image(&len);
    CHECK(seals >= 1 && o->c.wdg_resets == 1);
}

static void test_ecu_bam_dt_not_dropped(void)         /* review M2, graded Important */
{
    ecu_io io; ecu_up(&io);
    io.v_clt = 4.95f; io.v_egr = 0.1f; io.v_rail = 4.95f;
    ticks(&io, 150, 1);
    while (1) {                               /* to the DM1 TP.CM */
        ticks(&io, 1, 0);
        int cm = 0;
        for (int k = 0; k < io.can_n; k++) cm |= (io.can[k].id >> 16 & 0xFF) == 0xEC;
        if (cm) break;
        io.can_n = 0;
    }
    io.can_n = ECU_CANQ;                      /* queue full when the first TP.DT is due */
    ticks(&io, 60, 0);
    io.can_n = 0;
    int seq[8], n = 0;
    for (int i = 0; i < 300; i++) {
        ticks(&io, 1, 0);
        for (int k = 0; k < io.can_n; k++)
            if ((io.can[k].id >> 16 & 0xFF) == 0xEB && n < 8) seq[n++] = io.can[k].data[0];
        io.can_n = 0;
    }
    CHECK(n == 2 && seq[0] == 1 && seq[1] == 2);
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
    test_cal_tables();
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
    test_ecu_sensor_lamp();
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
    test_dtc_first_and_count();
    test_dtc_full();
    test_dm3_clear();
    test_ecu_history_survives_ignition_cycle();
    test_rec_pre_post();
    test_rec_two_slots();
    test_ecu_trip_saves_now();
    test_request_parse();
    test_hours();
    test_dm2_empty();
    test_dm4_layout();
    test_ecu_dm3_request();
    test_ecu_dm2_waits_for_bam();
    test_ecu_load_marks_inactive();
    test_ecu_flapping_sensor_keeps_log();
    test_ecu_dm1_not_starved();
    test_ecu_wdg_reset_saved();
    test_ecu_bam_dt_not_dropped();
    test_underspeed();
    test_isotp_roundtrip();
    test_isotp_lost_cf();
    test_link_roundtrip();
    test_link_bad_crc();
    test_svc_seed_key();
    test_svc_timeout();
    test_svc_engine_turning();
    test_eol_write_lock();
    test_eol_trim_range();
    test_eol_missing_raises_628();
    test_trim_applied();
    test_boot_request();
    test_can2_read();
    printf("%s: %d failure(s)\n", fails ? "FAIL" : "ok", fails);
    return fails != 0;
}
