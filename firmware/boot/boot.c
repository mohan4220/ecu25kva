#include <string.h>
#include "boot.h"
#include "nvm.h"

static uint32_t be32(const uint8_t *p)
{
    return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3];
}

static int read_hdr(const boot_flash *f, img_hdr *h)
{
    return f->read(f->app_base, (uint8_t *)h, sizeof *h) == 0;
}

/* CRC of `len` image bytes as they sit in flash */
static int image_crc(const boot_flash *f, uint32_t len, uint32_t *crc)
{
    uint8_t buf[256];
    uint32_t c = 0;
    for (uint32_t at = 0; at < len; at += sizeof buf) {
        uint32_t n = len - at < sizeof buf ? len - at : (uint32_t)sizeof buf;
        if (f->read(f->app_base + BOOT_HDR + at, buf, n))
            return 0;
        c = nvm_crc32_more(c, buf, n);
    }
    *crc = c;
    return 1;
}

int boot_decide(const boot_flash *f, int stay, uint16_t hw_rev)
{
    img_hdr h;
    uint32_t crc;
    if (stay || !read_hdr(f, &h))
        return 0;
    if (h.magic != IMG_MAGIC || h.hver != IMG_HVER || h.len == 0 || h.len > f->app_size - BOOT_HDR)
        return 0;
    if (hw_rev < h.hw_min || hw_rev > h.hw_max)
        return 0;
    return image_crc(f, h.len, &crc) && crc == h.crc;
}

void boot_init(boot_t *b, const boot_flash *f, uint16_t hw_rev)
{
    memset(b, 0, sizeof *b);
    b->f = f;
    b->hw_rev = hw_rev;
    b->svc.ctx = b;
    svc_init(&b->svc, 1);
}

/* [a, a + n) inside the application area, with no wrap-around */
static int in_app(const boot_flash *f, uint32_t a, uint32_t n)
{
    return n > 0 && a >= f->app_base && a - f->app_base <= f->app_size
        && n <= f->app_size - (a - f->app_base);
}

static uint16_t erase(boot_t *b, const uint8_t *q, uint16_t n, uint8_t *r)
{
    if (n != 12)
        return svc_nrc(r, 0x31, NRC_LENGTH);
    uint32_t a = be32(q + 4), len = be32(q + 8);
    if (!in_app(b->f, a, len))
        return svc_nrc(r, 0x31, NRC_RANGE);
    b->dl_active = b->dl_done = 0;
    if (b->f->erase(a, len))
        return svc_nrc(r, 0x31, NRC_PROGRAMMING);
    b->erased = 1;
    memcpy(r, (const uint8_t[]){ 0x71, 0x01, 0xFF, 0x00 }, 4);
    return 4;
}

/* The transfer is complete and its CRC is what the tool sent: only now
 * the header, its magic last, so a cut anywhere before leaves none. */
static uint16_t check(boot_t *b, const uint8_t *q, uint16_t n, uint8_t *r)
{
    if (n != 16)
        return svc_nrc(r, 0x31, NRC_LENGTH);
    if (!b->dl_done)
        return svc_nrc(r, 0x31, NRC_SEQUENCE);
    uint32_t crc;
    if (!image_crc(b->f, b->dl_len, &crc) || crc != be32(q + 4))
        return svc_nrc(r, 0x31, NRC_PROGRAMMING);
    union { img_hdr h; uint8_t b[BOOT_HDR]; } u;
    memset(u.b, 0xFF, sizeof u.b);
    u.h = (img_hdr){ IMG_MAGIC, IMG_HVER, b->dl_len, crc, be32(q + 8),
                     (uint16_t)(q[12] << 8 | q[13]), (uint16_t)(q[14] << 8 | q[15]) };
    const boot_flash *f = b->f;
    if (f->write(f->app_base + 8, u.b + 8, BOOT_HDR - 8) || f->write(f->app_base, u.b, 8))
        return svc_nrc(r, 0x31, NRC_PROGRAMMING);
    b->dl_done = b->erased = 0;
    memcpy(r, (const uint8_t[]){ 0x71, 0x01, 0xFF, 0x01, 0x00 }, 5);
    return 5;
}

static uint16_t download(boot_t *b, const uint8_t *q, uint16_t n, uint8_t *r)
{
    if (n != 11 || q[2] != 0x44)
        return svc_nrc(r, 0x34, NRC_LENGTH);
    uint32_t a = be32(q + 3), len = be32(q + 7);
    /* data only: the header's room is the check routine's alone */
    if (a != b->f->app_base + BOOT_HDR || !in_app(b->f, a, len))
        return svc_nrc(r, 0x34, NRC_RANGE);
    if (!b->erased)
        return svc_nrc(r, 0x34, NRC_CONDITIONS);
    b->dl_addr = a;
    b->dl_len = len;
    b->dl_pos = 0;
    b->ctr = 0;
    b->dl_active = 1;
    b->dl_done = 0;
    uint16_t max = BOOT_BLOCK + 2;
    memcpy(r, (const uint8_t[]){ 0x74, 0x20, (uint8_t)(max >> 8), (uint8_t)max }, 4);
    return 4;
}

static uint16_t transfer(boot_t *b, const uint8_t *q, uint16_t n, uint8_t *r)
{
    if (!b->dl_active)
        return svc_nrc(r, 0x36, NRC_SEQUENCE);
    if (n < 3 || n > BOOT_BLOCK + 2)
        return svc_nrc(r, 0x36, NRC_LENGTH);
    if (q[1] == b->ctr && b->dl_pos) {  /* a repeat of the last block: already written */
        r[0] = 0x76;
        r[1] = q[1];
        return 2;
    }
    if (q[1] != (uint8_t)(b->ctr + 1))
        return svc_nrc(r, 0x36, NRC_SEQUENCE);
    uint32_t m = n - 2u;
    if (m > b->dl_len - b->dl_pos || !in_app(b->f, b->dl_addr + b->dl_pos, m))
        return svc_nrc(r, 0x36, NRC_RANGE);
    uint8_t buf[BOOT_BLOCK];
    uint32_t w = (m + 7u) & ~7u;        /* whole words, padded as erased flash */
    memset(buf, 0xFF, w);
    memcpy(buf, q + 2, m);
    if (b->f->write(b->dl_addr + b->dl_pos, buf, w)) {
        b->dl_active = 0;
        return svc_nrc(r, 0x36, NRC_PROGRAMMING);
    }
    b->dl_pos += m;
    b->ctr = q[1];
    r[0] = 0x76;
    r[1] = q[1];
    return 2;
}

static uint16_t boot_extra(svc_t *s, const uint8_t *q, uint16_t n, uint8_t *r)
{
    boot_t *b = s->ctx;
    if (q[0] == 0x22) {
        if (n != 3)
            return svc_nrc(r, 0x22, NRC_LENGTH);
        uint16_t id = (uint16_t)(q[1] << 8 | q[2]);
        memcpy(r, (const uint8_t[]){ 0x62, q[1], q[2] }, 3);
        if (id == 0xF180) {
            r[3] = (uint8_t)(BOOT_VERSION >> 8);
            r[4] = (uint8_t)BOOT_VERSION;
            return 5;
        }
        if (id == 0xFD00) {             /* the application area, so the tool knows no chip */
            for (int i = 0; i < 4; i++) {
                r[3 + i] = (uint8_t)(b->f->app_base >> (24 - 8 * i));
                r[7 + i] = (uint8_t)(b->f->app_size >> (24 - 8 * i));
            }
            return 11;
        }
        if (id == 0xF195) {             /* the application's, from a good header; else 0 */
            img_hdr h;
            uint32_t v = boot_decide(b->f, 0, b->hw_rev) && read_hdr(b->f, &h) ? h.sw_ver : 0;
            for (int i = 0; i < 4; i++)
                r[3 + i] = (uint8_t)(v >> (24 - 8 * i));
            return 7;
        }
        return svc_nrc(r, 0x22, NRC_RANGE);
    }
    if (q[0] != 0x31 && q[0] != 0x34 && q[0] != 0x36 && q[0] != 0x37)
        return svc_nrc(r, q[0], NRC_NOT_SUPPORTED);
    if (s->session != SES_PROGRAMMING)
        return svc_nrc(r, q[0], NRC_SESSION);
    if (!s->unlocked)
        return svc_nrc(r, q[0], NRC_SECURITY);
    switch (q[0]) {
    case 0x31: {
        if (n < 4 || q[1] != 0x01)
            return svc_nrc(r, 0x31, n < 4 ? NRC_LENGTH : NRC_SUBFUNC);
        uint16_t id = (uint16_t)(q[2] << 8 | q[3]);
        return id == 0xFF00 ? erase(b, q, n, r) : id == 0xFF01 ? check(b, q, n, r)
             : svc_nrc(r, 0x31, NRC_RANGE);
    }
    case 0x34:
        return download(b, q, n, r);
    case 0x36:
        return transfer(b, q, n, r);
    default:                            /* 0x37 */
        if (n != 1)
            return svc_nrc(r, 0x37, NRC_LENGTH);
        if (!b->dl_active || b->dl_pos != b->dl_len)
            return svc_nrc(r, 0x37, NRC_SEQUENCE);
        b->dl_active = 0;
        b->dl_done = 1;
        r[0] = 0x77;
        return 1;
    }
}

size_t boot_state_size(void) { return sizeof(boot_t); }

/* While in the bootloader the engine cannot run: it is always stopped. */
uint16_t boot_handle(boot_t *b, const uint8_t *req, uint16_t n, uint8_t *resp, uint32_t ms, uint32_t us)
{
    b->svc.ctx = b;
    return svc_handle(&b->svc, req, n, resp, ms, us, 1, boot_extra);
}
