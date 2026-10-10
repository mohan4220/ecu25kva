#include <string.h>
#include "crank.h"

#define EDGES (CRANK_TEETH - 2)      /* 58 real teeth: edges 0..57 */

void crank_reset(crank_t *c) { memset(c, 0, sizeof *c); }

static void lose(crank_t *c, uint8_t why)
{
    if (c->synced)
        c->fault = why;
    c->synced = c->phased = 0;
}

void crank_edge(crank_t *c, uint32_t t_us)
{
    if (!c->have) {
        c->have = 1;
        c->last_us = t_us;
        return;
    }
    uint32_t period = t_us - c->last_us;
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
        if (c->cam_pending) {
            /* the cam belongs in rev 1; seen in rev 0 while phased, either
             * it or the phase is wrong: stop injecting until a cam agrees */
            int agrees = !c->phased || c->rev == 1;
            c->rev = 0;
            c->cam_pending = 0;
            c->phased = (uint8_t)(c->synced && agrees);
        } else {
            c->rev ^= 1;
        }
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
    c->cam_pending = 1;
}

void crank_poll(crank_t *c, uint32_t t_us)
{
    /* signed: a poll timestamped just before the last edge is not a timeout */
    if (c->synced && (int32_t)(t_us - c->last_us) > (int32_t)CRANK_TIMEOUT_US)
        lose(c, CRANK_F_TIMEOUT);
}

int crank_synced(const crank_t *c) { return c->synced; }
int crank_phased(const crank_t *c) { return c->phased; }
uint8_t crank_fault(const crank_t *c) { return c->fault; }
uint32_t crank_last_us(const crank_t *c) { return c->last_us; }

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
