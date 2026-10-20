#include <stddef.h>
#include <string.h>
#include "eol.h"
#include "nvm.h"

typedef char eol_size_check[sizeof(eol_record) == 84 ? 1 : -1];

void eol_default(eol_record *r)
{
    memset(r, 0, sizeof *r);
    r->magic = EOL_MAGIC;
    r->version = EOL_VERSION;
    for (int i = 0; i < EOL_N; i++)
        r->gain[i] = 1.0f;
}

int eol_trims_ok(const float gain[EOL_N], const float offset[EOL_N])
{
    for (int i = 0; i < EOL_N; i++)     /* written so that NaN fails */
        if (!(gain[i] >= EOL_GAIN_MIN && gain[i] <= EOL_GAIN_MAX)
            || !(offset[i] >= -EOL_OFFSET_MAX && offset[i] <= EOL_OFFSET_MAX))
            return 0;
    return 1;
}

static uint32_t crc_of(const eol_record *r)
{
    return nvm_crc32(r, offsetof(eol_record, crc));
}

int eol_valid(const eol_record *r)
{
    return r && r->magic == EOL_MAGIC && r->version == EOL_VERSION
        && r->crc == crc_of(r) && eol_trims_ok(r->gain, r->offset);
}

void eol_seal(eol_record *r)
{
    r->crc = crc_of(r);
}

/* The host writes copy a, then copy b: when both are good and differ, a
 * power cut fell between them and a is the newer. */
int eol_pick(const eol_record *a, const eol_record *b)
{
    return eol_valid(a) ? 0 : eol_valid(b) ? 1 : -1;
}
