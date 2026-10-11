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

#endif
