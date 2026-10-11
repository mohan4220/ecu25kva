/* What the ECU writes into the persistent image: events, counters, and
 * (later in this file) DTC memory and the trip recorder. */
#ifndef LOG_H
#define LOG_H

#include "nvm.h"

enum { EV_POWER_ON = 1, EV_IGN_ON, EV_IGN_OFF, EV_CRANK, EV_RUN, EV_SHUTDOWN,
       EV_DTC_SET, EV_DTC_CLEAR, EV_DM3_CLEAR, EV_NVM_RESET };

void log_event(nvm_image *m, uint32_t t_s, uint8_t code, uint16_t arg, uint16_t rpm);
const nvm_event *log_event_at(const nvm_image *m, int back);   /* 0 = newest */
int  log_second(nvm_image *m, int running, float load_frac);   /* 1 = an hour of running just completed */

/* DTC memory: one entry per SPN+FMI, freeze frame from the first occurrence */
typedef struct { float rpm, load_frac, fuel_mg, rail_bar, clt_c, oil_kpa, v_bat; uint8_t state; } log_snap;
#define DTC_ACTIVE 0x01
#define DTC_USED 0x02
#define DTC_OC_MAX 126

int  log_dtc_set(nvm_image *m, uint32_t spn, uint8_t fmi, uint32_t t_s, const log_snap *s); /* 1 = first */
void log_dtc_inactive(nvm_image *m, uint32_t spn, uint8_t fmi);
void log_dtc_all_inactive(nvm_image *m);
int  log_dm3_clear(nvm_image *m);
const nvm_dtc *log_dtc_find(const nvm_image *m, uint32_t spn, uint8_t fmi);

#endif
