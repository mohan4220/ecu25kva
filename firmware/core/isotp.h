/* ISO-TP (ISO 15765-2) framing for the service link on CAN channel 2:
 * single, first, consecutive and flow-control frames, block size 0,
 * STmin 0, messages up to 4095 bytes. No hardware: the caller passes
 * received frames in and sends what isotp_next hands out. */
#ifndef ISOTP_H
#define ISOTP_H

#include <stdint.h>
#include "ecu.h"

#define ISOTP_MAX 4095
#define ISOTP_PAD 0xAA

enum { ISOTP_IDLE, ISOTP_FIRST, ISOTP_WAIT_FC, ISOTP_SENDING };

typedef struct isotp {
    uint32_t tx_id;
    uint8_t tx[ISOTP_MAX];
    uint16_t tx_len, tx_pos;
    uint8_t tx_state, tx_sn;
    uint8_t rx[ISOTP_MAX];
    uint16_t rx_len, rx_pos;
    uint8_t rx_active, rx_sn, fc_due;
} isotp_t;

void isotp_init(isotp_t *t, uint32_t tx_id);
int  isotp_send(isotp_t *t, const uint8_t *msg, uint16_t len);   /* 0 ok, -1 busy or bad length */
int  isotp_rx(isotp_t *t, const ecu_can *f, uint8_t *msg, uint16_t *len);  /* 1: a message in msg */
int  isotp_next(isotp_t *t, ecu_can *out);                        /* 1: send *out */

#endif
