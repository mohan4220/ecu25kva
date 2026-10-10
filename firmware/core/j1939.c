#include <string.h>
#include "j1939.h"

uint32_t j1939_id(uint8_t prio, uint32_t pgn, uint8_t sa)
{
    return (uint32_t)prio << 26 | pgn << 8 | sa;
}

static void blank(ecu_can *f, uint8_t prio, uint32_t pgn)
{
    f->id = j1939_id(prio, pgn, J1939_SA);
    f->len = 8;
    memset(f->data, 0xFF, 8);
}

static uint8_t byte_clamp(float x) { return x < 0 ? 0 : x > 250 ? 250 : (uint8_t)(x + 0.5f); }

void j1939_eec1(ecu_can *f, float rpm)
{
    blank(f, 3, 61444);
    float r = rpm < 0 ? 0 : rpm > 8031 ? 8031 : rpm;
    uint16_t raw = (uint16_t)(r / 0.125f + 0.5f);
    f->data[3] = raw & 0xFF;
    f->data[4] = raw >> 8;
}

void j1939_et1(ecu_can *f, float clt_c, int valid)
{
    blank(f, 6, 65262);
    if (valid)
        f->data[0] = byte_clamp(clt_c + 40);
}

void j1939_eflp1(ecu_can *f, float oil_kpa, int valid)
{
    blank(f, 6, 65263);
    if (valid)
        f->data[3] = byte_clamp(oil_kpa / 4);
}

int j1939_dm1(ecu_can *out, int max, const faults_t *t, uint8_t lamps)
{
    uint8_t buf[2 + 4 * 8];
    int n = 2;
    buf[0] = lamps;
    buf[1] = 0xFF;
    for (int i = 0; i < t->n; i++) {
        const fault_t *d = &t->f[i];
        buf[n++] = d->spn & 0xFF;
        buf[n++] = (d->spn >> 8) & 0xFF;
        buf[n++] = (uint8_t)(((d->spn >> 11) & 0xE0) | (d->fmi & 0x1F));
        buf[n++] = d->oc & 0x7F;
    }
    if (t->n == 0) {                  /* no active faults: an all-zero DTC */
        memset(buf + 2, 0, 4);
        n = 6;
    }
    if (n <= 8) {
        if (max < 1)
            return 0;
        blank(out, 6, 65226);
        memcpy(out->data, buf, n);
        return 1;
    }
    int pk = (n + 6) / 7;             /* BAM: TP.CM then TP.DT packets */
    if (max < 1 + pk)
        return 0;
    blank(&out[0], 7, 0xECFF);
    uint8_t cm[8] = { 32, n & 0xFF, n >> 8, pk, 0xFF, 0xCA, 0xFE, 0x00 };
    memcpy(out[0].data, cm, 8);
    for (int p = 0; p < pk; p++) {
        ecu_can *f = &out[1 + p];
        blank(f, 7, 0xEBFF);
        f->data[0] = p + 1;
        int left = n - 7 * p;
        memcpy(f->data + 1, buf + 7 * p, left < 7 ? left : 7);
    }
    return 1 + pk;
}
