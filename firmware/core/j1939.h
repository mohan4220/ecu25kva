/* J1939 frames to the DSE4522 (J1939-71 standard set; the exact set the
 * DSE expects is open item U4). */
#ifndef J1939_H
#define J1939_H

#include "ecu.h"
#include "safety.h"
#include "nvm.h"

#define J1939_SA 234
#define LAMP_RED 0x10                /* DM1 byte 1: red stop lamp on */
#define LAMP_AMBER 0x04              /* DM1 byte 1: amber warning lamp on */
#define LAMP_PROTECT 0x01            /* DM1 byte 1: engine protect lamp on (the DSE shuts down on it) */

uint32_t j1939_id(uint8_t prio, uint32_t pgn, uint8_t sa);
void j1939_eec1(ecu_can *f, float rpm);
void j1939_et1(ecu_can *f, float clt_c, int valid);
void j1939_eflp1(ecu_can *f, float oil_kpa, int valid);
int  j1939_dm1(ecu_can *out, int max, const faults_t *t, uint8_t lamps);

#define PGN_DM2 65227u
#define PGN_DM3 65228u
#define PGN_DM4 65229u
#define PGN_HOURS 65253u
#define J1939_BAM_MAX 48             /* frames: TP.CM + up to 47 TP.DT (DM4 needs 42) */

/* n <= 8: one frame; else a BAM (TP.CM then TP.DT). Returns frames, 0 if > max. */
int  j1939_tp(ecu_can *out, int max, uint8_t prio, uint32_t pgn, const uint8_t *buf, int n);
int  j1939_dm2(ecu_can *out, int max, const nvm_image *m);   /* previously active DTCs */
int  j1939_dm4(ecu_can *out, int max, const nvm_image *m);   /* freeze frames */
void j1939_hours(ecu_can *f, uint32_t engine_s);
uint32_t j1939_request_pgn(const ecu_can *f, uint8_t sa);    /* 0 unless a request to sa or global */

#endif
