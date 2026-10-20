/* What the ECU writes into the persistent image: events, counters, and
 * (later in this file) DTC memory and the trip recorder. */
#ifndef LOG_H
#define LOG_H

#include "nvm.h"

enum { EV_POWER_ON = 1, EV_IGN_ON, EV_IGN_OFF, EV_CRANK, EV_RUN, EV_SHUTDOWN,
       EV_DTC_SET, EV_DTC_CLEAR, EV_DM3_CLEAR, EV_NVM_RESET, EV_EOL_UNLOCK };

void log_event(nvm_image *m, uint32_t t_s, uint8_t code, uint16_t arg, uint16_t rpm);
const nvm_event *log_event_at(const nvm_image *m, int back);   /* 0 = newest */
int  log_second(nvm_image *m, int running, float load_frac);   /* 1 = an hour of running just completed */

/* DTC memory: one entry per SPN+FMI, freeze frame from the first occurrence */
typedef struct { float rpm, load_frac, fuel_mg, rail_bar, clt_c, oil_kpa, v_bat; uint8_t state; } log_snap;
#define DTC_ACTIVE 0x01
#define DTC_USED 0x02
#define DTC_SET_LOGGED 0x04          /* set already logged this ignition cycle */
#define DTC_CLR_LOGGED 0x08          /* clear already logged this ignition cycle */
#define DTC_OC_MAX 126

/* 1 = first occurrence ever, 2 = first this ignition cycle (log it), 0 = neither.
 * Logging once per cycle keeps a flapping sensor from flooding the event log. */
int  log_dtc_set(nvm_image *m, uint32_t spn, uint8_t fmi, uint32_t t_s, const log_snap *s);
int  log_dtc_inactive(nvm_image *m, uint32_t spn, uint8_t fmi);   /* 1 = first clear this cycle */
void log_dtc_all_inactive(nvm_image *m);      /* also starts a new cycle for logging */
int  log_dm3_clear(nvm_image *m);
const nvm_dtc *log_dtc_find(const nvm_image *m, uint32_t spn, uint8_t fmi);

/* Trip recorder: a RAM ring always recording; a trip copies the last
 * REC_PRE samples into the older image slot and adds REC_POST more. */
typedef struct {
    rec_sample ring[REC_PRE];
    uint8_t head, n, post_left;
    int8_t slot;                     /* image slot being filled, -1 none */
} rec_t;

void rec_reset(rec_t *r);
int  rec_push(rec_t *r, nvm_image *m, rec_sample s);   /* 1 = a recording just completed */
void rec_trigger(rec_t *r, nvm_image *m, uint32_t t_s, uint8_t reason);

#endif
