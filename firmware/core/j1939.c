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

int j1939_tp(ecu_can *out, int max, uint8_t prio, uint32_t pgn, const uint8_t *buf, int n)
{
    if (n <= 8) {
        if (max < 1)
            return 0;
        blank(out, prio, pgn);
        memcpy(out->data, buf, (size_t)n);
        return 1;
    }
    int pk = (n + 6) / 7;
    if (max < 1 + pk)
        return 0;
    blank(&out[0], 7, 0xECFF);           /* TP.CM BAM to global */
    uint8_t cm[8] = { 32, (uint8_t)(n & 0xFF), (uint8_t)(n >> 8), (uint8_t)pk, 0xFF,
                      (uint8_t)(pgn & 0xFF), (uint8_t)(pgn >> 8 & 0xFF), (uint8_t)(pgn >> 16) };
    memcpy(out[0].data, cm, 8);
    for (int p = 0; p < pk; p++) {
        ecu_can *f = &out[1 + p];
        blank(f, 7, 0xEBFF);
        f->data[0] = (uint8_t)(p + 1);
        int left = n - 7 * p;
        memcpy(f->data + 1, buf + 7 * p, (size_t)(left < 7 ? left : 7));
    }
    return 1 + pk;
}

static int put_dtc(uint8_t *b, uint32_t spn, uint8_t fmi, uint8_t oc)
{
    b[0] = spn & 0xFF;
    b[1] = (spn >> 8) & 0xFF;
    b[2] = (uint8_t)(((spn >> 11) & 0xE0) | (fmi & 0x1F));
    b[3] = oc & 0x7F;
    return 4;
}

int j1939_dm1(ecu_can *out, int max, const faults_t *t, uint8_t lamps)
{
    uint8_t buf[2 + 4 * 8] = { lamps, 0xFF };
    int n = 2;
    for (int i = 0; i < t->n; i++)
        n += put_dtc(buf + n, t->f[i].spn, t->f[i].fmi, t->f[i].oc);
    if (t->n == 0)                       /* no active faults: an all-zero DTC */
        n += put_dtc(buf + n, 0, 0, 0);
    return j1939_tp(out, max, 6, 65226, buf, n);
}

int j1939_dm2(ecu_can *out, int max, const nvm_image *m)
{
    uint8_t buf[2 + 4 * NVM_DTCS] = { 0x00, 0xFF };
    int n = 2;
    for (int i = 0; i < NVM_DTCS; i++) {
        const nvm_dtc *d = &m->dtc[i];
        if ((d->status & 0x02) && !(d->status & 0x01))   /* used, not active */
            n += put_dtc(buf + n, d->spn, d->fmi, d->oc);
    }
    if (n == 2)
        n += put_dtc(buf + n, 0, 0, 0);
    return j1939_tp(out, max, 6, PGN_DM2, buf, n);
}

/* J1939-73 DM4: per DTC a length byte, the DTC, then torque mode, boost,
 * speed, % load, coolant, vehicle speed; our manufacturer bytes follow:
 * rail bar (2), oil 4 kPa, battery 0.2 V, state. */
int j1939_dm4(ecu_can *out, int max, const nvm_image *m)
{
    uint8_t buf[18 * NVM_DTCS];
    int n = 0;
    for (int i = 0; i < NVM_DTCS; i++) {
        const nvm_dtc *d = &m->dtc[i];
        if (!(d->status & 0x02))
            continue;
        uint16_t raw = (uint16_t)(d->rpm * 8u);
        uint8_t *b = buf + n;
        b[0] = 17;
        put_dtc(b + 1, d->spn, d->fmi, d->oc);
        b[5] = 0xFF;
        b[6] = 0xFF;
        b[7] = raw & 0xFF;
        b[8] = raw >> 8;
        b[9] = d->load_pct;
        b[10] = d->clt_p40;
        b[11] = b[12] = 0xFF;
        b[13] = d->rail_bar & 0xFF;
        b[14] = d->rail_bar >> 8;
        b[15] = d->oil_q;
        b[16] = d->vbat_q;
        b[17] = d->status >> 4;
        n += 18;
    }
    if (n == 0) {                        /* nothing stored: an empty record */
        memset(buf, 0, 5);
        n = 5;
    }
    return j1939_tp(out, max, 6, PGN_DM4, buf, n);
}

void j1939_hours(ecu_can *f, uint32_t engine_s)
{
    blank(f, 6, PGN_HOURS);
    uint32_t raw = engine_s / 180;       /* 0.05 h per bit */
    for (int i = 0; i < 4; i++)
        f->data[i] = (uint8_t)(raw >> (8 * i));
}

uint32_t j1939_request_pgn(const ecu_can *f, uint8_t sa)
{
    uint8_t pf = (uint8_t)(f->id >> 16), da = (uint8_t)(f->id >> 8);
    if (pf != 0xEA || (da != sa && da != 0xFF) || f->len < 3)
        return 0;
    return (uint32_t)f->data[0] | (uint32_t)f->data[1] << 8 | (uint32_t)f->data[2] << 16;
}
