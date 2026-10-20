/* USB framing for the service link (prototype): 0x55, length (2 bytes
 * LE), payload, CRC-16/CCITT of the payload (2 bytes LE). A bad CRC or a
 * length over LINK_MAX drops the message; the receiver then hunts for
 * the next 0x55. */
#ifndef LINK_H
#define LINK_H

#include <stdint.h>

#define LINK_SYNC 0x55
#define LINK_MAX 4095

typedef struct link_rx {
    uint8_t buf[LINK_MAX];
    uint16_t len, pos, crc;
    uint8_t state;
} link_rx_t;

uint16_t crc16_ccitt(const uint8_t *p, uint16_t n);       /* poly 0x1021, init 0xFFFF */
uint16_t link_frame(const uint8_t *msg, uint16_t n, uint8_t *out);   /* returns n + 5 */
int link_feed(link_rx_t *r, uint8_t byte, uint8_t *msg, uint16_t *len);   /* 1: a message in msg */

#endif
