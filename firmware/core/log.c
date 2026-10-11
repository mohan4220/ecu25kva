#include <string.h>
#include "log.h"

#define SAVE_RUN_S 3600u             /* hourly save of the counters while running */

void log_event(nvm_image *m, uint32_t t_s, uint8_t code, uint16_t arg, uint16_t rpm)
{
    nvm_event *e = &m->ev[m->ev_head];
    e->t_s = t_s;
    e->code = code;
    e->arg = arg;
    e->rpm = rpm;
    e->spare = 0;
    e->spare2 = 0;
    m->ev_head = (uint8_t)((m->ev_head + 1) % NVM_EVENTS);
    if (m->ev_n < NVM_EVENTS)
        m->ev_n++;
}

const nvm_event *log_event_at(const nvm_image *m, int back)
{
    if (back < 0 || back >= m->ev_n)
        return 0;
    return &m->ev[(m->ev_head - 1 - back + 2 * NVM_EVENTS) % NVM_EVENTS];
}

int log_second(nvm_image *m, int running, float load_frac)
{
    m->c.ecu_s++;
    if (!running)
        return 0;
    m->c.engine_s++;
    int band = load_frac < 0.25f ? 0 : load_frac < 0.5f ? 1 : load_frac < 0.75f ? 2
             : load_frac <= 1.0f ? 3 : 4;
    m->c.band_s[band]++;
    return m->c.engine_s % SAVE_RUN_S == 0;
}

static uint8_t q8(float x)          /* round and clamp to a byte */
{
    return x <= 0 ? 0 : x >= 255 ? 255 : (uint8_t)(x + 0.5f);
}

static uint16_t q16(float x)
{
    return x <= 0 ? 0 : x >= 65535 ? 65535 : (uint16_t)(x + 0.5f);
}

static nvm_dtc *find(nvm_image *m, uint32_t spn, uint8_t fmi)
{
    for (int i = 0; i < NVM_DTCS; i++)
        if ((m->dtc[i].status & DTC_USED) && m->dtc[i].spn == spn && m->dtc[i].fmi == fmi)
            return &m->dtc[i];
    return 0;
}

const nvm_dtc *log_dtc_find(const nvm_image *m, uint32_t spn, uint8_t fmi)
{
    return find((nvm_image *)m, spn, fmi);
}

/* a free entry, else the previously active one seen longest ago */
static nvm_dtc *slot_for_new(nvm_image *m)
{
    nvm_dtc *best = 0;
    for (int i = 0; i < NVM_DTCS; i++) {
        nvm_dtc *d = &m->dtc[i];
        if (!(d->status & DTC_USED))
            return d;
        if (!(d->status & DTC_ACTIVE) && (!best || d->last_s < best->last_s))
            best = d;
    }
    return best;
}

int log_dtc_set(nvm_image *m, uint32_t spn, uint8_t fmi, uint32_t t_s, const log_snap *s)
{
    nvm_dtc *d = find(m, spn, fmi);
    if (d) {
        if (d->oc < DTC_OC_MAX)
            d->oc++;
        d->last_s = t_s;
        d->status |= DTC_ACTIVE;
        return 0;
    }
    d = slot_for_new(m);
    if (!d)
        return 0;
    memset(d, 0, sizeof *d);
    d->spn = spn;
    d->fmi = fmi;
    d->status = (uint8_t)(DTC_USED | DTC_ACTIVE | (s->state & 0x0F) << 4);
    d->oc = 1;
    d->first_s = d->last_s = t_s;
    d->rpm = q16(s->rpm);
    d->rail_bar = q16(s->rail_bar);
    d->load_pct = q8(s->load_frac * 100);
    d->fuel_q = q8(s->fuel_mg / 0.25f);
    d->clt_p40 = q8(s->clt_c + 40);
    d->oil_q = q8(s->oil_kpa / 4);
    d->vbat_q = q8(s->v_bat / 0.2f);
    return 1;
}

void log_dtc_inactive(nvm_image *m, uint32_t spn, uint8_t fmi)
{
    nvm_dtc *d = find(m, spn, fmi);
    if (d)
        d->status &= (uint8_t)~DTC_ACTIVE;
}

void log_dtc_all_inactive(nvm_image *m)
{
    for (int i = 0; i < NVM_DTCS; i++)
        m->dtc[i].status &= (uint8_t)~DTC_ACTIVE;
}

int log_dm3_clear(nvm_image *m)
{
    int n = 0;
    for (int i = 0; i < NVM_DTCS; i++)
        if ((m->dtc[i].status & DTC_USED) && !(m->dtc[i].status & DTC_ACTIVE)) {
            memset(&m->dtc[i], 0, sizeof m->dtc[i]);
            n++;
        }
    return n;
}

void rec_reset(rec_t *r)
{
    memset(r, 0, sizeof *r);
    r->slot = -1;
}

int rec_push(rec_t *r, nvm_image *m, rec_sample s)
{
    int done = 0;
    if (r->slot >= 0) {
        rec_trip *t = &m->rec[r->slot];
        t->s[t->n_pre + t->n_post++] = s;
        if (--r->post_left == 0) {
            r->slot = -1;
            done = 1;
        }
    }
    r->ring[r->head] = s;
    r->head = (uint8_t)((r->head + 1) % REC_PRE);
    if (r->n < REC_PRE)
        r->n++;
    return done;
}

void rec_trigger(rec_t *r, nvm_image *m, uint32_t t_s, uint8_t reason)
{
    r->slot = (int8_t)m->rec_next;
    m->rec_next ^= 1;
    rec_trip *t = &m->rec[r->slot];
    memset(t, 0, sizeof *t);
    t->t_s = t_s;
    t->reason = reason;
    t->n_pre = r->n;
    for (int i = 0; i < r->n; i++)        /* oldest first */
        t->s[i] = r->ring[(r->head - r->n + i + REC_PRE) % REC_PRE];
    r->post_left = REC_POST;
}
