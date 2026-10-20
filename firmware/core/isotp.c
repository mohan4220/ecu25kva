#include <string.h>
#include "isotp.h"

void isotp_init(isotp_t *t, uint32_t tx_id)
{
    memset(t, 0, sizeof *t);
    t->tx_id = tx_id;
}

int isotp_send(isotp_t *t, const uint8_t *msg, uint16_t len)
{
    if (t->tx_state != ISOTP_IDLE || len == 0 || len > ISOTP_MAX)
        return -1;
    memcpy(t->tx, msg, len);
    t->tx_len = len;
    t->tx_pos = 0;
    t->tx_state = ISOTP_FIRST;
    return 0;
}

static void frame(isotp_t *t, ecu_can *out)
{
    out->id = t->tx_id;
    out->len = 8;
    memset(out->data, ISOTP_PAD, 8);
}

int isotp_next(isotp_t *t, ecu_can *out)
{
    if (t->fc_due) {                    /* continue to send: everything, no gap */
        frame(t, out);
        out->data[0] = 0x30;
        out->data[1] = 0;
        out->data[2] = 0;
        t->fc_due = 0;
        return 1;
    }
    if (t->tx_state == ISOTP_FIRST) {
        frame(t, out);
        if (t->tx_len <= 7) {
            out->data[0] = (uint8_t)t->tx_len;
            memcpy(&out->data[1], t->tx, t->tx_len);
            t->tx_state = ISOTP_IDLE;
        } else {
            out->data[0] = (uint8_t)(0x10 | t->tx_len >> 8);
            out->data[1] = (uint8_t)t->tx_len;
            memcpy(&out->data[2], t->tx, 6);
            t->tx_pos = 6;
            t->tx_sn = 1;
            t->tx_state = ISOTP_WAIT_FC;
        }
        return 1;
    }
    if (t->tx_state == ISOTP_SENDING) {
        frame(t, out);
        uint16_t n = (uint16_t)(t->tx_len - t->tx_pos);
        if (n > 7)
            n = 7;
        out->data[0] = (uint8_t)(0x20 | t->tx_sn);
        memcpy(&out->data[1], &t->tx[t->tx_pos], n);
        t->tx_pos = (uint16_t)(t->tx_pos + n);
        t->tx_sn = (uint8_t)((t->tx_sn + 1) & 15);
        if (t->tx_pos >= t->tx_len)
            t->tx_state = ISOTP_IDLE;
        return 1;
    }
    return 0;
}

int isotp_rx(isotp_t *t, const ecu_can *f, uint8_t *msg, uint16_t *len)
{
    if (f->len < 1)
        return 0;
    const uint8_t *d = f->data;
    /* a new single or first frame is a new request: a reply still waiting
     * for its flow control (lost, or the tester unplugged) is abandoned,
     * or every later send would find the link busy for good */
    if ((d[0] >> 4) <= 1 && t->tx_state == ISOTP_WAIT_FC)
        t->tx_state = ISOTP_IDLE;
    switch (d[0] >> 4) {
    case 0: {                           /* single frame: replaces any reception */
        uint8_t n = d[0] & 15;
        if (n == 0 || n > 7 || n + 1 > f->len)
            return 0;
        t->rx_active = 0;
        memcpy(msg, &d[1], n);
        *len = n;
        return 1;
    }
    case 1: {                           /* first frame */
        uint16_t n = (uint16_t)((d[0] & 15) << 8 | d[1]);
        if (n < 8 || f->len < 8)
            return 0;
        memcpy(t->rx, &d[2], 6);
        t->rx_len = n;
        t->rx_pos = 6;
        t->rx_sn = 1;
        t->rx_active = 1;
        t->fc_due = 1;
        return 0;
    }
    case 2: {                           /* consecutive frame */
        if (!t->rx_active)
            return 0;
        if ((d[0] & 15) != t->rx_sn) {  /* lost or out of order: drop the message */
            t->rx_active = 0;
            return 0;
        }
        uint16_t n = (uint16_t)(t->rx_len - t->rx_pos);
        if (n > 7)
            n = 7;
        if (n + 1 > f->len) {
            t->rx_active = 0;
            return 0;
        }
        memcpy(&t->rx[t->rx_pos], &d[1], n);
        t->rx_pos = (uint16_t)(t->rx_pos + n);
        t->rx_sn = (uint8_t)((t->rx_sn + 1) & 15);
        if (t->rx_pos < t->rx_len)
            return 0;
        t->rx_active = 0;
        memcpy(msg, t->rx, t->rx_len);
        *len = t->rx_len;
        return 1;
    }
    case 3:                             /* flow control for our first frame */
        if (t->tx_state == ISOTP_WAIT_FC) {
            uint8_t fs = d[0] & 15;
            if (fs == 0)
                t->tx_state = ISOTP_SENDING;
            else if (fs == 2)           /* overflow: the receiver cannot take it */
                t->tx_state = ISOTP_IDLE;
        }
        return 0;
    default:
        return 0;
    }
}
