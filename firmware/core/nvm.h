/* The persistent image: everything that must survive power-off, in one
 * struct of at most 4096 bytes (the S32K148's FlexRAM emulated EEPROM).
 * The host keeps two slots and writes them alternately; the newest slot
 * with a good CRC wins at load, so a torn write loses one save at most. */
#ifndef NVM_H
#define NVM_H

#include <stdint.h>

#define NVM_MAGIC 0xEC25u
#define NVM_VERSION 1u               /* bump on any layout change */
#define NVM_DTCS 16
#define NVM_EVENTS 64
#define REC_PRE 100                  /* trip recorder: 2 s before at 20 ms */
#define REC_POST 50                  /* and 1 s after */

typedef struct { uint16_t magic, version; uint32_t seq, len, crc; } nvm_hdr;

typedef struct {
    uint32_t ecu_s, engine_s, starts;          /* powered s, running s */
    uint16_t trips_overspeed, trips_sync, trips_other, wdg_resets;
    uint32_t band_s[5];                        /* running s at <25, <50, <75, <=100, >100 % load */
    uint32_t spare[2];
} nvm_counters;

typedef struct {                               /* 24 B */
    uint32_t spn;
    uint8_t fmi, status, oc, vbat_q;           /* status: bit0 active, bit1 used, bits4-7 state */
    uint32_t first_s, last_s;
    uint16_t rpm, rail_bar;                    /* freeze frame, first occurrence */
    uint8_t load_pct, fuel_q, clt_p40, oil_q;  /* fuel 0.25 mg, coolant +40, oil 4 kPa, vbat 0.2 V */
} nvm_dtc;

typedef struct { uint32_t t_s; uint8_t code, spare; uint16_t arg, rpm, spare2; } nvm_event;   /* 12 B */

typedef struct { uint16_t rpm; uint8_t fuel_q, state; uint16_t rail_bar; } rec_sample;       /* 6 B */

typedef struct {
    uint32_t t_s;
    uint8_t reason, n_pre, n_post, spare;
    rec_sample s[REC_PRE + REC_POST];
} rec_trip;

typedef struct {
    nvm_hdr h;
    nvm_counters c;
    nvm_dtc dtc[NVM_DTCS];
    nvm_event ev[NVM_EVENTS];
    uint8_t ev_head, ev_n, rec_next, spare;
    rec_trip rec[2];
} nvm_image;

uint32_t nvm_crc32(const void *p, uint32_t len);
uint32_t nvm_crc32_more(uint32_t crc, const void *p, uint32_t len);
void nvm_fresh(nvm_image *m);
int  nvm_valid(const void *p, uint32_t len);
int  nvm_pick(const void *a, const void *b, uint32_t len);   /* 0 = a, 1 = b, -1 = neither */
void nvm_seal(nvm_image *m);                                 /* seq++, CRC */

#endif
