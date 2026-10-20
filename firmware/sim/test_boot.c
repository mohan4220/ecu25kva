/* Unit tests for firmware/boot against a simulated flash. `make test` runs them. */
#include <stdio.h>
#include <string.h>
#include "boot.h"
#include "service.h"
#include "nvm.h"

static int fails;
#define CHECK(c) do { if (!(c)) { fails++; \
    printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #c); } } while (0)

/* ---- a simulated flash: erased is 0xFF, writes are whole 8-byte words,
 * and a power cut makes every write from the k-th on fail ---- */
#define APP_BASE BOOT_SIZE
#define APP_SIZE 0x20000u
static uint8_t flash[APP_BASE + APP_SIZE];
static int writes, cut_at = -1;
static uint32_t last_write;

static int f_erase(uint32_t a, uint32_t n)
{
    if (a + n > sizeof flash)
        return -1;
    memset(flash + a, 0xFF, n);
    return 0;
}

static int f_write(uint32_t a, const uint8_t *p, uint32_t n)
{
    if (cut_at >= 0 && writes >= cut_at)
        return -1;                      /* powered off */
    if (a % 8 || n % 8 || a + n > sizeof flash)
        return -1;
    for (uint32_t i = 0; i < n; i++)
        flash[a + i] &= p[i];           /* flash only clears bits */
    writes++;
    last_write = a;
    return 0;
}

static int f_read(uint32_t a, uint8_t *p, uint32_t n)
{
    if (a + n > sizeof flash)
        return -1;
    memcpy(p, flash + a, n);
    return 0;
}

static const boot_flash F = { f_erase, f_write, f_read, APP_BASE, APP_SIZE };

static boot_t b;
static uint8_t rsp[SVC_RESP_MAX];
static uint32_t now;

static uint16_t req(const uint8_t *q, uint16_t n)
{
    now += 10;
    return boot_handle(&b, q, n, rsp, now, now * 1000u + 3);
}
#define REQ(...) req((const uint8_t[]){ __VA_ARGS__ }, sizeof((const uint8_t[]){ __VA_ARGS__ }))

static int nrc(uint16_t n, uint8_t sid, uint8_t code)
{
    return n == 3 && rsp[0] == 0x7F && rsp[1] == sid && rsp[2] == code;
}

static void be32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16); p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v;
}

static void power_on(uint16_t hw_rev)
{
    cut_at = -1;
    boot_init(&b, &F, hw_rev);
}

static void unlock(void)
{
    CHECK(REQ(0x10, 0x02) == 6 && rsp[0] == 0x50);
    CHECK(REQ(0x27, 0x01) == 6);
    uint32_t seed = rsp[2] | rsp[3] << 8 | rsp[4] << 16 | (uint32_t)rsp[5] << 24, k = svc_key(seed);
    CHECK(REQ(0x27, 0x02, (uint8_t)k, (uint8_t)(k >> 8), (uint8_t)(k >> 16), (uint8_t)(k >> 24)) == 2);
}

static uint16_t erase(uint32_t a, uint32_t n)
{
    uint8_t q[12] = { 0x31, 0x01, 0xFF, 0x00 };
    be32(q + 4, a);
    be32(q + 8, n);
    return req(q, 12);
}

static uint16_t download(uint32_t a, uint32_t n)
{
    uint8_t q[11] = { 0x34, 0x00, 0x44 };
    be32(q + 3, a);
    be32(q + 7, n);
    return req(q, 11);
}

static uint16_t check(uint32_t crc, uint32_t sw, uint16_t lo, uint16_t hi)
{
    uint8_t q[16] = { 0x31, 0x01, 0xFF, 0x01 };
    be32(q + 4, crc);
    be32(q + 8, sw);
    q[12] = (uint8_t)(lo >> 8); q[13] = (uint8_t)lo; q[14] = (uint8_t)(hi >> 8); q[15] = (uint8_t)hi;
    return req(q, 16);
}

static uint8_t image[40000];

/* The tool's whole sequence. 0 = every step positive, else the step that failed. */
static int flash_image(const uint8_t *img, uint32_t n, uint16_t lo, uint16_t hi)
{
    unlock();
    if (!(erase(APP_BASE, APP_SIZE) == 4 && rsp[0] == 0x71)) return 1;
    if (!(download(APP_BASE + BOOT_HDR, n) == 4 && rsp[0] == 0x74)) return 2;
    uint8_t q[2 + BOOT_BLOCK];
    uint8_t ctr = 1;
    for (uint32_t at = 0; at < n; at += BOOT_BLOCK, ctr++) {
        uint32_t m = n - at < BOOT_BLOCK ? n - at : BOOT_BLOCK;
        q[0] = 0x36;
        q[1] = ctr;
        memcpy(q + 2, img + at, m);
        if (!(req(q, (uint16_t)(m + 2)) == 2 && rsp[0] == 0x76 && rsp[1] == ctr)) return 3;
    }
    if (!(REQ(0x37) == 1 && rsp[0] == 0x77)) return 4;
    if (!(check(nvm_crc32(img, n), 0x00010002, lo, hi) == 5 && rsp[0] == 0x71 && rsp[4] == 0)) return 5;
    return 0;
}

static void fill(uint8_t *p, uint32_t n, uint32_t seed)
{
    for (uint32_t i = 0; i < n; i++) {
        seed = seed * 1103515245u + 12345u;
        p[i] = (uint8_t)(seed >> 16);
    }
}

static void test_boot_decide(void)
{
    memset(flash, 0xFF, sizeof flash);
    CHECK(boot_decide(&F, 0, 0x0100) == 0);                   /* blank: stay */
    power_on(0x0100);
    fill(image, sizeof image, 1);
    CHECK(flash_image(image, sizeof image, 0x0100, 0x01FF) == 0);
    CHECK(boot_decide(&F, 0, 0x0100) == 1);                   /* good: jump */
    CHECK(boot_decide(&F, 1, 0x0100) == 0);                   /* stay flag */
    CHECK(boot_decide(&F, 0, 0x0200) == 0);                   /* hardware outside 0x0100..0x01FF */
    CHECK(boot_decide(&F, 0, 0x00FF) == 0);
    flash[APP_BASE + BOOT_HDR + 100] ^= 0x01;                  /* a bit flipped in the image */
    CHECK(boot_decide(&F, 0, 0x0100) == 0);
}

static void test_boot_bounds(void)
{
    memset(flash, 0x5A, sizeof flash);                         /* the bootloader's own bytes */
    static uint8_t before[APP_BASE];
    memcpy(before, flash, APP_BASE);
    power_on(0x0100);
    unlock();
    CHECK(nrc(erase(0, 0x100), 0x31, 0x31));                   /* the bootloader's area */
    CHECK(nrc(erase(APP_BASE - 8, 16), 0x31, 0x31));           /* straddles it */
    CHECK(nrc(erase(APP_BASE, APP_SIZE + 8), 0x31, 0x31));     /* past the end */
    CHECK(erase(APP_BASE, APP_SIZE) == 4);
    CHECK(nrc(download(0x100, 64), 0x34, 0x31));               /* write below the application */
    CHECK(nrc(download(APP_BASE, 64), 0x34, 0x31));            /* the header is the check's alone */
    CHECK(nrc(download(APP_BASE + BOOT_HDR, APP_SIZE), 0x34, 0x31));
    CHECK(memcmp(before, flash, APP_BASE) == 0);
}

static void test_boot_locked(void)
{
    memset(flash, 0xFF, sizeof flash);
    power_on(0x0100);
    CHECK(nrc(erase(APP_BASE, APP_SIZE), 0x31, 0x7F));         /* default session */
    CHECK(REQ(0x10, 0x02) == 6);
    CHECK(nrc(erase(APP_BASE, APP_SIZE), 0x31, 0x33));         /* not unlocked */
    CHECK(nrc(download(APP_BASE + BOOT_HDR, 64), 0x34, 0x33));
    CHECK(REQ(0x22, 0xF1, 0x80) == 5 && rsp[0] == 0x62 && (rsp[3] << 8 | rsp[4]) == BOOT_VERSION);
    CHECK(REQ(0x22, 0xFD, 0x00) == 11);                        /* where the application goes */
    CHECK((uint32_t)(rsp[3] << 24 | rsp[4] << 16 | rsp[5] << 8 | rsp[6]) == APP_BASE);
    CHECK((uint32_t)(rsp[7] << 24 | rsp[8] << 16 | rsp[9] << 8 | rsp[10]) == APP_SIZE);
    CHECK(boot_state_size() == sizeof(boot_t));
}

static void test_boot_flash_ok(void)
{
    memset(flash, 0xFF, sizeof flash);
    power_on(0x0100);
    fill(image, sizeof image, 2);
    CHECK(flash_image(image, sizeof image, 0x0100, 0x0100) == 0);
    CHECK(memcmp(flash + APP_BASE + BOOT_HDR, image, sizeof image) == 0);
    CHECK(boot_decide(&F, 0, 0x0100) == 1);
    CHECK(REQ(0x22, 0xF1, 0x95) == 7 && rsp[3] == 0 && rsp[4] == 1 && rsp[5] == 0 && rsp[6] == 2);
    CHECK(REQ(0x11, 0x01) == 2 && b.svc.reset_req == 1);
}

static void test_boot_header_last(void)
{
    memset(flash, 0xFF, sizeof flash);
    power_on(0x0100);
    fill(image, sizeof image, 3);
    unlock();
    CHECK(erase(APP_BASE, APP_SIZE) == 4);
    CHECK(download(APP_BASE + BOOT_HDR, sizeof image) == 4);
    uint8_t q[2 + BOOT_BLOCK] = { 0x36, 1 };
    memcpy(q + 2, image, BOOT_BLOCK);
    CHECK(req(q, sizeof q) == 2);
    CHECK(nrc(check(0, 1, 0, 0xFFFF), 0x31, 0x24));             /* before the transfer is complete */
    power_on(0x0100);
    CHECK(flash_image(image, sizeof image, 0, 0xFFFF) == 0);
    CHECK(last_write == APP_BASE);                              /* the header's magic, last of all */
    uint32_t magic;
    memcpy(&magic, flash + APP_BASE, 4);
    CHECK(magic == IMG_MAGIC);
    power_on(0x0100);
    unlock();
    CHECK(erase(APP_BASE, APP_SIZE) == 4);
    CHECK(download(APP_BASE + BOOT_HDR, sizeof image) == 4);
    for (uint32_t at = 0, c = 1; at < sizeof image; at += BOOT_BLOCK, c++) {
        uint32_t m = sizeof image - at < BOOT_BLOCK ? sizeof image - at : BOOT_BLOCK;
        q[1] = (uint8_t)c;
        memcpy(q + 2, image + at, m);
        req(q, (uint16_t)(m + 2));
    }
    CHECK(REQ(0x37) == 1);
    CHECK(nrc(check(nvm_crc32(image, sizeof image) ^ 1, 1, 0, 0xFFFF), 0x31, 0x72));   /* wrong CRC */
    CHECK(boot_decide(&F, 0, 0x0100) == 0);                     /* and no header written */
}

static void test_boot_power_cut_every_write(void)
{
    static uint8_t old[40000];
    fill(old, sizeof old, 4);
    fill(image, sizeof image, 5);
    memset(flash, 0xFF, sizeof flash);
    power_on(0x0100);
    CHECK(flash_image(old, sizeof old, 0, 0xFFFF) == 0);
    writes = 0;
    power_on(0x0100);
    CHECK(flash_image(image, sizeof image, 0, 0xFFFF) == 0);
    int total = writes;
    CHECK(total > 40);
    for (int k = 0; k < total; k++) {
        power_on(0x0100);
        writes = 0;
        cut_at = k;
        flash_image(image, sizeof image, 0, 0xFFFF);            /* fails from write k on */
        CHECK(boot_decide(&F, 0, 0x0100) == 0);                 /* the next reset stays */
        power_on(0x0100);
        CHECK(flash_image(image, sizeof image, 0, 0xFFFF) == 0);   /* and the rerun works */
        CHECK(boot_decide(&F, 0, 0x0100) == 1);
    }
    CHECK(memcmp(flash + APP_BASE + BOOT_HDR, image, sizeof image) == 0);
}

static void test_boot_bad_sequence(void)
{
    memset(flash, 0xFF, sizeof flash);
    power_on(0x0100);
    fill(image, sizeof image, 6);
    unlock();
    CHECK(erase(APP_BASE, APP_SIZE) == 4);
    CHECK(download(APP_BASE + BOOT_HDR, sizeof image) == 4);
    uint8_t q[2 + BOOT_BLOCK] = { 0x36, 1 };
    memcpy(q + 2, image, BOOT_BLOCK);
    CHECK(req(q, sizeof q) == 2);
    CHECK(req(q, sizeof q) == 2 && rsp[1] == 1);               /* a repeat of the last: no rewrite */
    q[1] = 3;
    CHECK(nrc(req(q, sizeof q), 0x36, 0x24));                  /* block 2 skipped */
    CHECK(nrc(REQ(0x37), 0x37, 0x24));                          /* not all of it arrived */
}

int main(void)
{
    test_boot_decide();
    test_boot_bounds();
    test_boot_locked();
    test_boot_flash_ok();
    test_boot_header_last();
    test_boot_power_cut_every_write();
    test_boot_bad_sequence();
    printf("boot %s: %d failure(s)\n", fails ? "FAIL" : "ok", fails);
    return fails != 0;
}
