#include <stddef.h>
#include <string.h>
#include "nvm.h"

/* CRC-32 (zlib's): continue `crc` over more bytes; start from 0 */
uint32_t nvm_crc32_more(uint32_t crc, const void *p, uint32_t len)
{
    const uint8_t *b = p;
    uint32_t c = ~crc;
    while (len--) {
        c ^= *b++;
        for (int k = 0; k < 8; k++)
            c = c >> 1 ^ (0xEDB88320u & -(c & 1));
    }
    return ~c;
}

uint32_t nvm_crc32(const void *p, uint32_t len) { return nvm_crc32_more(0, p, len); }

/* CRC of the whole image with its crc field taken as zero */
static uint32_t image_crc(const void *p)
{
    static nvm_image tmp;               /* background only: not reentrant */
    memcpy(&tmp, p, sizeof tmp);
    tmp.h.crc = 0;
    return nvm_crc32(&tmp, sizeof tmp);
}

void nvm_fresh(nvm_image *m)
{
    memset(m, 0, sizeof *m);
    m->h.magic = NVM_MAGIC;
    m->h.version = NVM_VERSION;
    m->h.len = sizeof *m;
}

int nvm_valid(const void *p, uint32_t len)
{
    nvm_hdr h;
    if (!p || len != sizeof(nvm_image))
        return 0;
    memcpy(&h, p, sizeof h);            /* the host's buffer may be unaligned */
    return h.magic == NVM_MAGIC && h.version == NVM_VERSION && h.len == sizeof(nvm_image)
        && h.crc == image_crc(p);
}

static uint32_t seq_of(const void *p)
{
    nvm_hdr h;
    memcpy(&h, p, sizeof h);
    return h.seq;
}

int nvm_pick(const void *a, const void *b, uint32_t len)
{
    int va = nvm_valid(a, len), vb = nvm_valid(b, len);
    if (va && vb)
        return seq_of(b) > seq_of(a);
    return va ? 0 : vb ? 1 : -1;
}

void nvm_seal(nvm_image *m)
{
    m->h.seq++;
    m->h.crc = 0;
    m->h.crc = nvm_crc32(m, sizeof *m);
}
