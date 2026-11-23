#include <string.h>
#include "crank.h"

#define EDGES (CRANK_TEETH - 2)      /* 58 real teeth: edges 0..57 */

void crank_reset(crank_t *c) { memset(c, 0, sizeof *c); }

#ifndef ECU_MODEL    /* else generated: model/ecu_crank.slx, ecu_crankrd.slx, via model_glue.c */
static void lose(crank_t *c, uint8_t why)
{
    if (c->synced)
        c->fault = why;
    c->synced = c->phased = 0;
    c->nper = 0;                     /* the window holds the bad edge: rpm restarts fresh */
}

static int near_tooth(uint8_t a, uint8_t b)
{
    return (a > b ? a - b : b - a) <= CRANK_CAM_TOL;
}

static int sig_match(crank_sig a, crank_sig b)
{
    return a.n == b.n && (a.n == 0 || (near_tooth(a.first, b.first) && near_tooth(a.last, b.last)));
}

/* Which of two different signatures is the marker: more edges; then the
 * earlier first edge; then the earlier last edge. 1 = a, 0 = b, -1 = they
 * are too alike to tell apart. */
static int sig_marker(crank_sig a, crank_sig b)
{
    if (a.n != b.n)
        return a.n > b.n;
    if (a.n == 0)
        return -1;
    if (!near_tooth(a.first, b.first))
        return a.first < b.first;
    if (!near_tooth(a.last, b.last))
        return a.last < b.last;
    return -1;
}

/* At a gap: the revolution that just ended (c->cur) decides what the next
 * one is. `whole` = it ran gap to gap with every tooth seen. */
static void cam_at_gap(crank_t *c, int whole)
{
    int next = -1;                   /* the coming revolution's number, if known */
    int missed = 0;
    if (!whole) {
        c->prev_ok = 0;
        c->rev ^= 1;
        return;                      /* lose() has already dropped the phase */
    }
    if (c->learned) {
        if (sig_match(c->cur, c->mark))
            next = 0;
        else if (sig_match(c->cur, c->other))
            next = 1;
        if (next < 0) {
            missed = 1;
            c->clean = 0;
            /* a wheel never confirmed by a clean cycle may have been learned
             * from noise: forget it at once. A confirmed one rides out a
             * stray edge, and is forgotten only if the misses go on. */
            if (!c->proven || ++c->miss >= CRANK_CAM_MISS)
                c->learned = 0;
        } else if (++c->clean >= 2) {
            c->clean = 2;
            c->proven = 1;
            c->miss = 0;
        }
    }
    if (!c->learned && c->prev_ok && !missed) {
        int m = sig_marker(c->cur, c->prev);
        if (m >= 0) {
            c->mark = m ? c->cur : c->prev;
            c->other = m ? c->prev : c->cur;
            c->learned = 1;
            c->proven = c->miss = c->clean = 0;
            next = m ? 0 : 1;
        }
    }
    if (next < 0) {
        c->phased = 0;
        c->rev ^= 1;
    } else {
        /* the revolution that ended should have been the other one: if the
         * count disagrees, either it or the phase is wrong -- stop
         * injecting until the cam agrees */
        int agrees = !c->phased || c->rev == (uint8_t)(next ^ 1);
        c->rev = (uint8_t)next;
        c->phased = (uint8_t)(c->synced && agrees);
    }
    c->prev = c->cur;
    c->prev_ok = (uint8_t)!missed;   /* never learn from a revolution that missed */
}

void crank_edge(crank_t *c, uint32_t t_us)
{
    if (!c->have) {
        c->have = 1;
        c->last_us = t_us;
        return;
    }
    uint32_t period = t_us - c->last_us;
    if (period > CRANK_TIMEOUT_US) {
        /* after a pause, the old period is no reference: start afresh, or
         * the glitch filter below would reject real teeth for seconds */
        lose(c, CRANK_F_TIMEOUT);
        c->prev_period = c->nper = c->head = c->gap_seen = c->count = c->prev_gap = 0;
        c->last_us = t_us;
        return;
    }
    /* A real tooth cannot arrive in under half the previous tooth's time
     * (per 6 deg): that is noise, and counting it would read as overspeed. */
    uint32_t tooth_prev = c->prev_gap ? c->prev_period / 3 : c->prev_period;
    if (period < tooth_prev / 2)
        return;     /* ponytail: glitches dropped silently; count them if a DTC is wanted */
    int gap = c->prev_period && period > c->prev_period + c->prev_period / 2;

    c->per[c->head] = period;
    c->deg[c->head] = gap ? 18 : 6;
    c->head = (c->head + 1) % CRANK_WIN;
    if (c->nper < CRANK_WIN)
        c->nper++;

    if (gap) {
        int in_place = c->gap_seen && c->count == EDGES - 1;
        if (!in_place)
            lose(c, CRANK_F_GAP);
        else if (!c->synced)
            c->synced = 1;
        c->gap_seen = 1;
        c->count = 0;
        cam_at_gap(c, in_place);
        c->cur.n = c->cur.first = c->cur.last = 0;
    } else if (++c->count >= EDGES) {         /* the gap should have come */
        lose(c, CRANK_F_GAP);
        c->gap_seen = 0;
    }
    c->last_us = t_us;
    c->prev_period = period;
    c->prev_gap = (uint8_t)gap;
}

void crank_cam(crank_t *c, uint32_t t_us)
{
    (void)t_us;
    if (c->cur.n == 0)
        c->cur.first = c->count;
    c->cur.last = c->count;
    if (c->cur.n < 255)
        c->cur.n++;
}

void crank_poll(crank_t *c, uint32_t t_us)
{
    /* signed: a poll timestamped just before the last edge is not a timeout */
    if (c->synced && (int32_t)(t_us - c->last_us) > (int32_t)CRANK_TIMEOUT_US)
        lose(c, CRANK_F_TIMEOUT);
}

#endif

int crank_synced(const crank_t *c) { return c->synced; }
int crank_phased(const crank_t *c) { return c->phased; }
uint8_t crank_fault(const crank_t *c) { return c->fault; }
uint32_t crank_last_us(const crank_t *c) { return c->last_us; }

#ifndef ECU_MODEL
float crank_rpm(const crank_t *c)
{
    if (c->nper < CRANK_WIN)
        return 0;
    uint32_t us = 0, deg = 0;
    for (int i = 0; i < CRANK_WIN; i++) {
        us += c->per[i];
        deg += c->deg[i];
    }
    return (float)deg / (float)us * 1e6f / 6.0f;
}

float crank_angle(const crank_t *c) { return c->rev * 360.0f + c->count * 6.0f; }

float crank_next_angle(const crank_t *c)
{
    return crank_angle(c) + (c->count == EDGES - 1 ? 18.0f : 6.0f);
}

float crank_us_per_deg(const crank_t *c)
{
    float rpm = crank_rpm(c);
    return rpm > 0 ? 1e6f / (rpm * 6.0f) : 0;
}
#endif
