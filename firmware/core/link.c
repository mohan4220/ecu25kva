#include <string.h>
#include "link.h"

enum { HUNT, LEN_LO, LEN_HI, DATA, CRC_LO, CRC_HI };

uint16_t crc16_ccitt(const uint8_t *p, uint16_t n)
{
    uint16_t c = 0xFFFF;
    while (n--) {
        c ^= (uint16_t)(*p++ << 8);
        for (int k = 0; k < 8; k++)
            c = (uint16_t)(c & 0x8000 ? c << 1 ^ 0x1021 : c << 1);
    }
    return c;
}

uint16_t link_frame(const uint8_t *msg, uint16_t n, uint8_t *out)
{
    uint16_t c = crc16_ccitt(msg, n);
    out[0] = LINK_SYNC;
    out[1] = (uint8_t)n;
    out[2] = (uint8_t)(n >> 8);
    memcpy(&out[3], msg, n);
    out[3 + n] = (uint8_t)c;
    out[4 + n] = (uint8_t)(c >> 8);
    return (uint16_t)(n + 5);
}

/* ponytail: after a bad frame the hunt starts at the next byte, not back
 * inside the dropped one; a frame hidden inside garbage is lost too */
int link_feed(link_rx_t *r, uint8_t b, uint8_t *msg, uint16_t *len)
{
    switch (r->state) {
    case HUNT:
        if (b == LINK_SYNC)
            r->state = LEN_LO;
        return 0;
    case LEN_LO:
        r->len = b;
        r->state = LEN_HI;
        return 0;
    case LEN_HI:
        r->len = (uint16_t)(r->len | b << 8);
        r->pos = 0;
        r->state = r->len == 0 || r->len > LINK_MAX ? HUNT : DATA;
        return 0;
    case DATA:
        r->buf[r->pos++] = b;
        if (r->pos == r->len)
            r->state = CRC_LO;
        return 0;
    case CRC_LO:
        r->crc = b;
        r->state = CRC_HI;
        return 0;
    default:
        r->state = HUNT;
        r->crc = (uint16_t)(r->crc | b << 8);
        if (r->crc != crc16_ccitt(r->buf, r->len))
            return 0;
        memcpy(msg, r->buf, r->len);
        *len = r->len;
        return 1;
    }
}
