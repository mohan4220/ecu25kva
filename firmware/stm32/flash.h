#ifndef FLASH_H
#define FLASH_H
#include <stdint.h>

/* Dual-bank only (option bit DBANK, set from the factory on the 512 KiB
 * part): 2 KiB pages, 8-byte programming. 0 ok, -1 error. */
int  flash_dual_bank(void);
int  flash_erase(uint32_t addr, uint32_t len);          /* whole pages covering [addr, addr+len) */
int  flash_write(uint32_t addr, const void *p, uint32_t len);   /* addr 8-aligned; tail padded 0xFF */
void flash_flush_caches(void);
/* One page, toggling WDT_KICK every `half` CPU cycles while it waits
 * (bank 1 from RAM, interrupts off). For the bootloader. */
int  flash_erase_page_kick(uint32_t addr, volatile uint32_t *kick_t, uint32_t half);

/* The same, as a job the main loop advances without blocking it for
 * more than a few ms (a page erase is 22 ms typical, 40 max). The data
 * is copied in at the start, so the caller may change its own. */
typedef struct {
    uint32_t addr, len, pos;
    uint8_t buf[4096];
    uint8_t state, ok;
} flash_job;

void flash_job_start(flash_job *j, uint32_t addr, const void *p, uint32_t len);
int  flash_job_step(flash_job *j);      /* 1 while busy; 0 done (j->ok says how) */

#endif
