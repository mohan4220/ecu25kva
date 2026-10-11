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
