#include "safety.h"
#include "j1939.h"

#ifndef ECU_MODEL    /* else generated: model/ecu_safety.slx */
int safety_check(float rpm, uint8_t crank_fault, uint8_t ignition, int running)
{
    if (rpm > OVERSPEED_RPM)
        return TRIP_OVERSPEED;
    if (running && crank_fault)
        return TRIP_SYNC;
    if (!ignition)
        return TRIP_IGN;
    return TRIP_NONE;
}

uint8_t fault_lamps(const faults_t *t)
{
    uint8_t l = 0;
    for (int i = 0; i < t->n; i++)
        l |= ((t->f[i].spn == SPN_SPEED && t->f[i].fmi == 0)
              || t->f[i].spn == SPN_POS
              || (t->f[i].spn == SPN_BOOST_RAIL && t->f[i].fmi == FMI_HIGH_SEVERE)
              || (t->f[i].spn == SPN_CLT && t->f[i].fmi == 0))   /* coolant: log 35 */
             ? LAMP_RED | LAMP_PROTECT        /* shutdown: the DSE stops only on Protect */
             : LAMP_AMBER;
    return l;
}
#endif

static int find(const faults_t *t, uint32_t spn, uint8_t fmi)
{
    for (int i = 0; i < t->n; i++)
        if (t->f[i].spn == spn && t->f[i].fmi == fmi)
            return i;
    return -1;
}

/* ponytail: occurrence count is always 1; real counting needs NVM (S32K148 port) */
void faults_set(faults_t *t, uint32_t spn, uint8_t fmi)
{
    if (find(t, spn, fmi) >= 0 || t->n >= FAULTS_MAX)
        return;
    t->f[t->n++] = (fault_t){ spn, fmi, 1 };
}

void faults_clear(faults_t *t, uint32_t spn, uint8_t fmi)
{
    int i = find(t, spn, fmi);
    if (i < 0)
        return;
    for (t->n--; i < t->n; i++)
        t->f[i] = t->f[i + 1];
}
