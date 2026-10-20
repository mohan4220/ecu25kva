/* The end-of-line record: what the factory writes into each unit once,
 * locked once written. Two copies in their own flash sector, apart from
 * the persistent image (spec 2026-10-17 sec. 6). */
#ifndef EOL_H
#define EOL_H

#include <stdint.h>

#define EOL_MAGIC 0xE01Du
#define EOL_VERSION 1u
#define EOL_GAIN_MIN 0.9f
#define EOL_GAIN_MAX 1.1f
#define EOL_OFFSET_MAX 0.1f             /* volts, either sign */
#define EOL_N 6                         /* clt, oil, rail, boost, egr, 5 V ref */

typedef struct {
    uint16_t magic, version;            /* 0xE01D, 1 */
    char     serial[16];                /* ASCII, zero-padded */
    uint16_t hw_rev;                    /* e.g. 0x0100 = rev 1.0 (2 pad bytes follow) */
    uint32_t build_date;                /* yyyymmdd */
    float    gain[EOL_N], offset[EOL_N];
    uint8_t  station, passed, locked, spare;
    uint32_t crc;                       /* CRC-32 over everything above */
} eol_record;                           /* 84 bytes */

void eol_default(eol_record *r);        /* gain 1, offset 0, unsealed */
int  eol_trims_ok(const float gain[EOL_N], const float offset[EOL_N]);
int  eol_valid(const eol_record *r);
void eol_seal(eol_record *r);
int  eol_pick(const eol_record *a, const eol_record *b);   /* 0 a, 1 b, -1 neither good */

#endif
