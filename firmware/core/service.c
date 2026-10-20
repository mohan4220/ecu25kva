#include <string.h>
#include "service.h"
#include "ecu.h"

static const uint8_t secret[16] = SEC_SECRET;

static uint32_t since(uint32_t now, uint32_t then)
{
    return (now + ECU_MS_WRAP - then) % ECU_MS_WRAP;
}

static void to_default(svc_t *s)
{
    s->session = SES_DEFAULT;
    s->unlocked = s->seed_out = 0;
}

void svc_init(svc_t *s, int in_boot)
{
    void *ctx = s->ctx;
    memset(s, 0, sizeof *s);
    s->ctx = ctx;
    s->in_boot = (uint8_t)in_boot;
    to_default(s);
}

/* SipHash-2-4 (Aumasson and Bernstein, 2012): a keyed hash for short
 * messages. Not CRC-32: that is affine, and one sniffed seed and key
 * would give the key for every seed. */
#define ROTL(x, b) (uint64_t)(((x) << (b)) | ((x) >> (64 - (b))))
#define SIPROUND do { \
        v0 += v1; v1 = ROTL(v1, 13); v1 ^= v0; v0 = ROTL(v0, 32); \
        v2 += v3; v3 = ROTL(v3, 16); v3 ^= v2; \
        v0 += v3; v3 = ROTL(v3, 21); v3 ^= v0; \
        v2 += v1; v1 = ROTL(v1, 17); v1 ^= v2; v2 = ROTL(v2, 32); } while (0)

static uint64_t le64(const uint8_t *p, uint32_t n)
{
    uint64_t x = 0;
    for (uint32_t i = 0; i < n; i++)
        x |= (uint64_t)p[i] << (8 * i);
    return x;
}

uint64_t siphash24(const uint8_t key[16], const uint8_t *m, uint32_t n)
{
    uint64_t k0 = le64(key, 8), k1 = le64(key + 8, 8);
    uint64_t v0 = 0x736f6d6570736575ull ^ k0, v1 = 0x646f72616e646f6dull ^ k1;
    uint64_t v2 = 0x6c7967656e657261ull ^ k0, v3 = 0x7465646279746573ull ^ k1;
    uint32_t i = 0;
    for (; i + 8 <= n; i += 8) {
        uint64_t w = le64(m + i, 8);
        v3 ^= w;
        SIPROUND; SIPROUND;
        v0 ^= w;
    }
    uint64_t b = (uint64_t)n << 56 | le64(m + i, n - i);
    v3 ^= b;
    SIPROUND; SIPROUND;
    v0 ^= b;
    v2 ^= 0xff;
    SIPROUND; SIPROUND; SIPROUND; SIPROUND;
    return v0 ^ v1 ^ v2 ^ v3;
}

uint32_t svc_key(uint32_t seed)
{
    const uint8_t b[4] = { (uint8_t)seed, (uint8_t)(seed >> 8), (uint8_t)(seed >> 16), (uint8_t)(seed >> 24) };
    return (uint32_t)siphash24(secret, b, 4);
}

uint16_t svc_nrc(uint8_t *resp, uint8_t sid, uint8_t code)
{
    resp[0] = 0x7F;
    resp[1] = sid;
    resp[2] = code;
    return 3;
}

void svc_tick(svc_t *s, uint32_t ms, int engine_stopped)
{
    if (s->locked_out && since(ms, s->lock_ms) >= SVC_LOCK_MS)
        s->locked_out = 0, s->bad_keys = 0;
    if (s->session == SES_DEFAULT)
        return;
    if (since(ms, s->last_ms) > SVC_SESSION_MS || !engine_stopped)
        to_default(s);
}

static uint16_t session(svc_t *s, const uint8_t *q, uint16_t n, uint8_t *r)
{
    if (n != 2)
        return svc_nrc(r, 0x10, NRC_LENGTH);
    uint8_t sub = q[1] & 0x7F;
    if (sub == SES_EXTENDED || sub == SES_PROGRAMMING) {
        if (!s->stopped)
            return svc_nrc(r, 0x10, NRC_CONDITIONS);
        /* the application leaves for the bootloader only unlocked; the
         * bootloader unlocks inside its programming session */
        if (sub == SES_PROGRAMMING && !s->in_boot && !s->unlocked)
            return svc_nrc(r, 0x10, NRC_SECURITY);
    } else if (sub != SES_DEFAULT) {
        return svc_nrc(r, 0x10, NRC_SUBFUNC);
    }
    if (sub == SES_DEFAULT || (sub == SES_EXTENDED && s->session == SES_DEFAULT))
        s->unlocked = s->seed_out = 0;
    if (sub == SES_PROGRAMMING && !s->in_boot)
        s->prog_req = 1;
    s->session = sub;
    if (q[1] & 0x80)
        return 0;
    r[0] = 0x50;
    r[1] = sub;
    r[2] = 0x00, r[3] = 0x32;           /* P2 50 ms */
    r[4] = 0x01, r[5] = 0xF4;           /* P2* 500 x 10 ms */
    return 6;
}

static uint16_t security(svc_t *s, const uint8_t *q, uint16_t n, uint8_t *r, uint32_t ms, uint32_t us)
{
    if (n < 2)
        return svc_nrc(r, 0x27, NRC_LENGTH);
    if (s->session == SES_DEFAULT)
        return svc_nrc(r, 0x27, NRC_SESSION);
    if (s->locked_out)
        return svc_nrc(r, 0x27, NRC_TRIES);
    if (q[1] == 0x01) {
        if (n != 2)
            return svc_nrc(r, 0x27, NRC_LENGTH);
        uint32_t x = us ^ (ms * 2654435761u) ^ (s->seed * 0x9E3779B9u + 0x7F4A7C15u);
        s->seed = x ? x : 1;
        s->seed_out = 1;
        r[0] = 0x67;
        r[1] = 0x01;
        for (int i = 0; i < 4; i++)
            r[2 + i] = (uint8_t)(s->seed >> 8 * i);
        return 6;
    }
    if (q[1] == 0x02) {
        if (n != 6)
            return svc_nrc(r, 0x27, NRC_LENGTH);
        if (!s->seed_out)
            return svc_nrc(r, 0x27, NRC_SEQUENCE);
        s->seed_out = 0;
        uint32_t k = q[2] | q[3] << 8 | q[4] << 16 | (uint32_t)q[5] << 24;
        if (k != svc_key(s->seed)) {
            if (++s->bad_keys >= SVC_TRIES) {
                s->locked_out = 1;
                s->lock_ms = ms;
                return svc_nrc(r, 0x27, NRC_TRIES);
            }
            return svc_nrc(r, 0x27, NRC_KEY);
        }
        s->bad_keys = 0;
        s->unlocked = 1;
        r[0] = 0x67;
        r[1] = 0x02;
        return 2;
    }
    return svc_nrc(r, 0x27, NRC_SUBFUNC);
}

uint16_t svc_handle(svc_t *s, const uint8_t *q, uint16_t n, uint8_t *r,
                    uint32_t ms, uint32_t us, int engine_stopped, svc_extra extra)
{
    svc_tick(s, ms, engine_stopped);
    s->last_ms = ms;
    s->stopped = (uint8_t)(engine_stopped != 0);
    if (n == 0)
        return 0;
    switch (q[0]) {
    case 0x10:
        return session(s, q, n, r);
    case 0x27:
        return security(s, q, n, r, ms, us);
    case 0x3E:
        if (n != 2 || (q[1] & 0x7F))
            return svc_nrc(r, 0x3E, n != 2 ? NRC_LENGTH : NRC_SUBFUNC);
        if (q[1] & 0x80)
            return 0;
        r[0] = 0x7E;
        r[1] = 0x00;
        return 2;
    case 0x11:
        if (n != 2)
            return svc_nrc(r, 0x11, NRC_LENGTH);
        if ((q[1] & 0x7F) != 0x01)
            return svc_nrc(r, 0x11, NRC_SUBFUNC);
        if (!s->stopped)                /* a reset stops injection: never on a running set */
            return svc_nrc(r, 0x11, NRC_CONDITIONS);
        s->reset_req = 1;
        if (q[1] & 0x80)
            return 0;
        r[0] = 0x51;
        r[1] = 0x01;
        return 2;
    default:
        return extra ? extra(s, q, n, r) : svc_nrc(r, q[0], NRC_NOT_SUPPORTED);
    }
}

int svc_unlocked(const svc_t *s) { return s->unlocked; }
uint8_t svc_session(const svc_t *s) { return s->session; }
