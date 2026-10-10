/* J1939 frames to the DSE4522 (J1939-71 standard set; the exact set the
 * DSE expects is open item U4). */
#ifndef J1939_H
#define J1939_H

#include "ecu.h"
#include "safety.h"

#define J1939_SA 234
#define LAMP_RED 0x10                /* DM1 byte 1: red stop lamp on */
#define LAMP_AMBER 0x04              /* DM1 byte 1: amber warning lamp on */

uint32_t j1939_id(uint8_t prio, uint32_t pgn, uint8_t sa);
void j1939_eec1(ecu_can *f, float rpm);
void j1939_et1(ecu_can *f, float clt_c, int valid);
void j1939_eflp1(ecu_can *f, float oil_kpa, int valid);
int  j1939_dm1(ecu_can *out, int max, const faults_t *t, uint8_t lamps);

#endif
