/* The bootloader core: decide at reset whether to run the application,
 * and program it over the service link (spec 2026-10-17 sec. 7). The
 * flash, the stay flag and the jump are the host's. */
#ifndef BOOT_H
#define BOOT_H

#include <stddef.h>
#include <stdint.h>
#include "service.h"

#define BOOT_SIZE 0x8000u              /* the bootloader's own area: never erased or written */
#define BOOT_VERSION 0x0100u           /* UDS 0xF180 */
#define BOOT_HDR 64u                   /* the image header's room at app_base; data after it */
#define BOOT_BLOCK 1024u               /* data bytes per 0x36 */
#define IMG_MAGIC 0x1A6EC25u
#define IMG_HVER 1u

typedef struct { uint32_t magic, hver, len, crc, sw_ver; uint16_t hw_min, hw_max; } img_hdr;

/* The application area only. A write is whole 8-byte words. 0 ok. */
typedef struct {
    int (*erase)(uint32_t a, uint32_t n);
    int (*write)(uint32_t a, const uint8_t *p, uint32_t n);
    int (*read)(uint32_t a, uint8_t *p, uint32_t n);
    uint32_t app_base, app_size;
} boot_flash;

typedef struct {
    svc_t svc;
    const boot_flash *f;
    uint16_t hw_rev;                   /* from the end-of-line record */
    uint8_t erased, dl_active, dl_done, ctr;
    uint32_t dl_addr, dl_len, dl_pos;
} boot_t;

void     boot_init(boot_t *b, const boot_flash *f, uint16_t hw_rev);
int      boot_decide(const boot_flash *f, int stay, uint16_t hw_rev);    /* 1 jump, 0 stay */
uint16_t boot_handle(boot_t *b, const uint8_t *req, uint16_t n, uint8_t *resp, uint32_t ms, uint32_t us);
size_t   boot_state_size(void);        /* for the PC simulator's binding */

#endif
