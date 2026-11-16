#ifndef CAN_H
#define CAN_H
#include <stdint.h>
#include "ecu.h"

/* ch 0: FDCAN1, J1939 to the DSE4522, 250 kbit/s, 29-bit (pins 55/77).
 * ch 1: FDCAN2, the service link, 1000 kbit/s, 11-bit (pins 87/86).
 *
 * Transmit straight from the core's queue (ecu_io can[] / can2[]): what
 * the hardware FIFO takes is removed from the front, the rest stays for
 * the next call. The core only appends, so a long ISO-TP response is
 * paced by the bus, never dropped. */
typedef void (*can_rx_fn)(const ecu_can *f);

void can_init(int ch, can_rx_fn rx, ecu_can *q, uint8_t *qn);
void can_pump(int ch);                          /* at the core's priority */
int  can_bus_off(int ch);
uint32_t can_rx_lost(int ch);

#endif
