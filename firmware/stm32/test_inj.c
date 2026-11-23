/* The injector sequencing (inj_logic.c) against a coil model, on the PC.
 * Coil: 200 uH, 0.5 ohm (injector_boost.cir). Rails: 100 V boost, 13.5 V
 * battery, 0.7 V diodes. The ADC samples every 0.45 us (ADC1 at 6.5
 * cycles) and the watchdog fires on the first sample past the level.
 *
 *   zig cc -std=c99 -Wall -Wextra -Werror -Ifirmware/stm32 \
 *       firmware/stm32/test_inj.c firmware/stm32/inj_logic.c -o t && ./t */
#include <stdio.h>
#include <string.h>
#include "inj_logic.h"
#include "board.h"

static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL %s:%d: ", __FILE__, __LINE__); \
    printf(__VA_ARGS__); printf("\n"); } } while (0)

typedef struct {
    double i;                         /* coil current, A */
    double i_max, hold_min, hold_max; /* over the hold window */
    double t_peak;                    /* first time at the peak level, us */
    uint32_t t_off;                   /* when every gate went off, us */
    int broken_sense, stuck_high;
    int bank_seen;                    /* the high side that fired: 0 A, 1 B */
    double r;                         /* coil resistance, ohm (0 = the nominal 0.5) */
} coil_t;

static double sense(const coil_t *c, uint8_t gates)
{
    if (c->stuck_high)
        return 30.0;
    if (c->broken_sense)
        return 0.0;
    return (gates & (G_LS1 | G_LS2 | G_LS3)) ? c->i : 0.0;
}

/* run from t0 to t1 us; the timer runs on whole microseconds */
static void run(inj_t *s, coil_t *c, uint32_t t0, uint32_t t1, uint32_t hold_from, uint32_t hold_to)
{
    const double L = 200e-6, R = c->r > 0 ? c->r : 0.5, dt = 0.05e-6;
    double t = t0, next_adc = t0;
    uint32_t us = t0;
    uint8_t prev = 0;
    while (t < t1) {
        if (t >= us) {
            uint32_t nt;
            if (inj_next(s, &nt) && (int32_t)(us - nt) >= 0)
                inj_timer(s, us);
            us++;
        }
        uint8_t g = s->gates;
        if (g & (G_HS_A | G_HS_A_BAT))
            c->bank_seen = 0;
        if (g & (G_HS_B | G_HS_B_BAT))
            c->bank_seen = 1;
        if (prev && !g)
            c->t_off = (uint32_t)t;
        prev = g;
        int ls = (g & (G_LS1 | G_LS2 | G_LS3)) != 0;
        double v;
        if (!ls)
            v = c->i > 0 ? -100.7 : 0;                 /* recirculation into the boost rail */
        else if (g & (G_HS_A | G_HS_B))
            v = 100.0;
        else if (g & (G_HS_A_BAT | G_HS_B_BAT))
            v = 13.5;
        else
            v = c->i > 0 ? -0.7 : 0;                   /* D_fw */
        c->i += (v - c->i * R) / L * dt;
        if (c->i < 0)
            c->i = 0;
        if (c->i > c->i_max)
            c->i_max = c->i;
        if (c->t_peak == 0 && c->i >= INJ_PEAK_A)
            c->t_peak = t - t0;
        if (t >= hold_from && t < hold_to) {
            if (c->i < c->hold_min) c->hold_min = c->i;
            if (c->i > c->hold_max) c->hold_max = c->i;
        }
        if (t >= next_adc) {
            next_adc += 0.45;
            double a = sense(c, g);
            uint16_t cnt = (uint16_t)(a / A_PER_V_INJ / VDDA_NOM * 4095.0);
            if (s->active >= 0 && cnt >= s->c_over)
                inj_over(s);
            else if (s->watch == W_ABOVE && cnt > s->lvl)
                inj_cross(s, us);
            else if (s->watch == W_BELOW && cnt < s->lvl)
                inj_cross(s, us);
        }
        t += dt * 1e6;
    }
}

static void fresh(inj_t *s, coil_t *c)
{
    inj_init(s);
    memset(c, 0, sizeof *c);
    c->hold_min = 1e9;
}

int main(void)
{
    inj_t s;
    coil_t c;

    /* 1. a 1.5 ms injection on cylinder 1 */
    fresh(&s, &c);
    inj_command(&s, 0, 1000, 1500);
    run(&s, &c, 0, 3000, 1400, 2450);
    CHECK(c.t_peak - 1000 > 30 && c.t_peak - 1000 < 50, "peak after %.1f us (38 nominal)",
          c.t_peak - 1000);
    CHECK(c.i_max < INJ_PEAK_A + 1.0, "peak overshoot to %.2f A", c.i_max);
    CHECK(c.hold_min > INJ_HOLD_LO_A - 0.5 && c.hold_max < INJ_HOLD_HI_A + 0.5,
          "hold %.2f..%.2f A", c.hold_min, c.hold_max);
    CHECK(c.t_off >= 2500 && c.t_off <= 2501, "gates off at %u us, want 2500", c.t_off);
    CHECK(s.n_done == 1 && s.active < 0 && s.gates == 0, "done %u", s.n_done);
    CHECK(c.bank_seen == 0, "cylinder 1 on bank A");
    CHECK(c.i < 0.01, "current gone after the end: %.3f A", c.i);

    /* 2. cylinder 2 is bank B */
    fresh(&s, &c);
    inj_command(&s, 1, 500, 800);
    run(&s, &c, 0, 2000, 0, 0);
    CHECK(c.bank_seen == 1 && s.n_done == 1, "cylinder 2 on bank B");

    /* 3. a cancel before the start: nothing happens */
    fresh(&s, &c);
    inj_command(&s, 2, 1000, 1000);
    run(&s, &c, 0, 500, 0, 0);
    inj_command(&s, 2, 0, 0);
    run(&s, &c, 500, 3000, 0, 0);
    CHECK(c.i_max == 0 && s.n_done == 0, "cancelled, yet %.2f A", c.i_max);

    /* 4. a cancel after the start: it runs to its end */
    fresh(&s, &c);
    inj_command(&s, 0, 1000, 1000);
    run(&s, &c, 0, 1200, 0, 0);
    inj_command(&s, 0, 0, 0);
    run(&s, &c, 1200, 3000, 0, 0);
    CHECK(s.n_done == 1 && c.t_off >= 2000 && c.t_off <= 2001, "ran to %u", c.t_off);

    /* 5. two at once: the second is refused */
    fresh(&s, &c);
    inj_command(&s, 0, 1000, 1000);
    inj_command(&s, 1, 1500, 1000);
    run(&s, &c, 0, 4000, 0, 0);
    CHECK(s.n_done == 1 && s.n_overlap == 1, "done %u overlap %u", s.n_done, s.n_overlap);

    /* 6. a dead current sense: ends at the peak timeout, not at 100 V forever */
    fresh(&s, &c);
    c.broken_sense = 1;
    inj_command(&s, 0, 1000, 1500);
    run(&s, &c, 0, 3000, 0, 0);
    CHECK(s.n_peak_timeout == 1 && c.t_off <= 1000 + INJ_PEAK_MAX_US + 1,
          "timeout %u, off at %u", s.n_peak_timeout, c.t_off);
    CHECK(c.i_max < 0.5 * INJ_PEAK_MAX_US + 1, "dead sense reached %.1f A", c.i_max);

    /* 7. a start found late is skipped */
    fresh(&s, &c);
    inj_command(&s, 0, 1000, 1500);
    run(&s, &c, 1100, 3000, 0, 0);
    CHECK(s.n_late == 1 && c.i_max == 0, "late %u", s.n_late);

    /* 8. the cap */
    fresh(&s, &c);
    inj_command(&s, 0, 1000, 9000);
    run(&s, &c, 0, 8000, 0, 0);
    CHECK(s.n_capped == 1 && c.t_off >= 1000 + INJ_CAP_US && c.t_off <= 1001 + INJ_CAP_US,
          "capped %u off at %u", s.n_capped, c.t_off);

    /* 9. over-current: off at once */
    fresh(&s, &c);
    c.stuck_high = 1;
    inj_command(&s, 0, 1000, 1500);
    run(&s, &c, 0, 3000, 0, 0);
    CHECK(s.n_over == 1 && c.t_off <= 1002, "over %u off at %u", s.n_over, c.t_off);

    /* 10. the microsecond clock wraps mid-injection */
    fresh(&s, &c);
    inj_command(&s, 0, 0xFFFFFC00u, 1500);
    run(&s, &c, 0xFFFFF000u, 0xFFFFFFF0u, 0, 0);
    CHECK(s.active == 0, "running across the wrap");
    run(&s, &c, 0, 2000, 0, 0);
    CHECK(s.n_done == 1, "ended after the wrap");

    /* 11. one command per cylinder, a full cycle at 1500 rpm */
    fresh(&s, &c);
    for (int k = 0; k < 3; k++)
        inj_command(&s, k, 1000 + 26667u * (uint32_t)k, 1500);
    run(&s, &c, 0, 82000, 0, 0);
    CHECK(s.n_done == 3 && s.n_overlap == 0 && s.n_late == 0, "cycle done %u", s.n_done);

    CHECK(s.n_hold_short == 0, "hold short %u on the nominal coil", s.n_hold_short);

    /* 12. the owner's rating, 0.2-2.0 ohm (decisions log 38). 0.2 holds;
     * 2.0 at 20 C is 2.83 hot (125 C): it cannot reach 9 A from 13.5 V, and is counted */
    fresh(&s, &c);
    c.r = 0.2;                        /* L/R = 1 ms: the fall from the peak to 9 A */
    inj_command(&s, 0, 1000, 1500);   /* through D_fw takes ~0.55 ms, so the hold */
    run(&s, &c, 0, 3000, 1700, 2450); /* is judged from 1.7 ms */
    CHECK(c.hold_min > INJ_HOLD_LO_A - 0.5 && c.hold_max < INJ_HOLD_HI_A + 0.5 && s.n_hold_short == 0,
          "0.2 ohm hold %.2f..%.2f A, short %u", c.hold_min, c.hold_max, s.n_hold_short);
    fresh(&s, &c);
    c.r = 2.83;
    inj_command(&s, 0, 1000, 1500);
    run(&s, &c, 0, 3000, 1400, 2450);
    CHECK(s.n_peak_timeout == 0 && s.n_done == 1, "2.83 ohm: peak reached (timeout %u)", s.n_peak_timeout);
    CHECK(s.n_hold_short == 1 && c.hold_max < INJ_HOLD_LO_A, "2.83 ohm: hold %.2f A max, short %u",
          c.hold_max, s.n_hold_short);

    printf(fails ? "%d FAILED\n" : "inj: 12 cases pass\n", fails);
    return fails != 0;
}
