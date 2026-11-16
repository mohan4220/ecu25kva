#include "inj_logic.h"
#include "board.h"

static const uint8_t ls_bit[INJ_NCYL] = { G_LS1, G_LS2, G_LS3 };
static const uint8_t boost_bit[2] = { G_HS_A, G_HS_B };
static const uint8_t bat_bit[2] = { G_HS_A_BAT, G_HS_B_BAT };

static int before(uint32_t a, uint32_t b) { return (int32_t)(a - b) < 0; }

int inj_bank_of(int k) { return k == 1 ? 1 : 0; }

void inj_init(inj_t *s)
{
    *s = (inj_t){ 0 };
    s->active = -1;
    inj_set_levels(s, VDDA_NOM);
}

static uint16_t counts(float amps, float vdda)
{
    float c = amps / A_PER_V_INJ / vdda * 4095.0f + 0.5f;
    return (uint16_t)(c > 4095.0f ? 4095.0f : c);
}

void inj_set_levels(inj_t *s, float vdda)
{
    s->c_peak = counts(INJ_PEAK_A, vdda);
    s->c_lo = counts(INJ_HOLD_LO_A, vdda);
    s->c_hi = counts(INJ_HOLD_HI_A, vdda);
    s->c_over = counts(INJ_OVER_A, vdda);
}

static void finish(inj_t *s)
{
    s->gates = 0;
    s->watch = W_OFF;
    s->phase = PH_IDLE;
    s->active = -1;
}

void inj_command(inj_t *s, int k, uint32_t start_us, uint32_t dur_us)
{
    if (k < 0 || k >= INJ_NCYL)
        return;
    inj_slot *q = &s->slot[k];
    if (dur_us == 0) {                  /* cancel: only what has not started */
        q->pending = 0;
        return;
    }
    if (dur_us > INJ_CAP_US) {
        dur_us = INJ_CAP_US;
        s->n_capped++;
    }
    q->start = start_us;
    q->end = start_us + dur_us;
    q->pending = 1;
}

int inj_next(const inj_t *s, uint32_t *t)
{
    int any = 0;
    uint32_t best = 0;
    if (s->active >= 0) {
        best = s->end;
        any = 1;
        if (s->phase == PH_PEAK && before(s->peak_by, best))
            best = s->peak_by;
    }
    for (int k = 0; k < INJ_NCYL; k++)
        if (s->slot[k].pending && (!any || before(s->slot[k].start, best))) {
            best = s->slot[k].start;
            any = 1;
        }
    *t = best;
    return any;
}

static void begin(inj_t *s, int k, uint32_t now)
{
    inj_slot *q = &s->slot[k];
    q->pending = 0;
    if (s->active >= 0) {               /* never two at once */
        s->n_overlap++;
        return;
    }
    if ((int32_t)(now - q->start) > (int32_t)INJ_LATE_US || !before(now, q->end)) {
        s->n_late++;
        return;
    }
    int b = inj_bank_of(k);
    s->active = (int8_t)k;
    s->bank = (uint8_t)b;
    s->end = q->end;
    s->peak_by = now + INJ_PEAK_MAX_US;
    s->phase = PH_PEAK;
    s->gates = (uint8_t)(ls_bit[k] | boost_bit[b]);
    s->watch = W_ABOVE;
    s->lvl = s->c_peak;
}

void inj_timer(inj_t *s, uint32_t now)
{
    /* the end, and the peak timeout, of what is running */
    if (s->active >= 0) {
        if (!before(now, s->end)) {
            s->n_done++;
            finish(s);
        } else if (s->phase == PH_PEAK && !before(now, s->peak_by)) {
            s->n_peak_timeout++;
            finish(s);
        }
    }
    /* starts that are due, earliest first */
    for (;;) {
        int pick = -1;
        for (int k = 0; k < INJ_NCYL; k++)
            if (s->slot[k].pending && !before(now, s->slot[k].start) &&
                (pick < 0 || before(s->slot[k].start, s->slot[pick].start)))
                pick = k;
        if (pick < 0)
            break;
        begin(s, pick, now);
    }
}

void inj_cross(inj_t *s, uint32_t now)
{
    (void)now;
    if (s->active < 0)
        return;
    int b = s->bank;
    switch (s->phase) {
    case PH_PEAK:                       /* reached the peak: let it fall */
        if (s->watch != W_ABOVE)
            return;
        s->gates = (uint8_t)(s->gates & ~boost_bit[b]);
        s->phase = PH_DECAY;
        s->watch = W_BELOW;
        s->lvl = s->c_lo;
        break;
    case PH_DECAY:                      /* below the band: battery on */
        if (s->watch != W_BELOW)
            return;
        s->gates = (uint8_t)(s->gates | bat_bit[b]);
        s->phase = PH_HOLD_ON;
        s->watch = W_ABOVE;
        s->lvl = s->c_hi;
        break;
    case PH_HOLD_ON:                    /* above the band: battery off */
        if (s->watch != W_ABOVE)
            return;
        s->gates = (uint8_t)(s->gates & ~bat_bit[b]);
        s->phase = PH_DECAY;
        s->watch = W_BELOW;
        s->lvl = s->c_lo;
        break;
    default:
        break;
    }
}

void inj_over(inj_t *s)
{
    if (s->active < 0)
        return;
    s->n_over++;
    finish(s);
}
