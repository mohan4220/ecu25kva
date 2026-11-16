/* Flash, after ST's HAL (FLASH_Program_DoubleWord, FLASH_PageErase,
 * FLASH_FlushCaches) and RM0440 sec. 5.3.7-5.3.8. Bank 2 is erased and
 * written while code runs from bank 1 without stalling it. */
#include <string.h>
#include "hw.h"
#include "flash.h"

#define SR_ERR (FLASH_SR_OPERR | FLASH_SR_PROGERR | FLASH_SR_WRPERR | FLASH_SR_PGAERR \
              | FLASH_SR_SIZERR | FLASH_SR_PGSERR | FLASH_SR_MISERR | FLASH_SR_FASTERR \
              | FLASH_SR_RDERR | FLASH_SR_OPTVERR)

int flash_dual_bank(void) { return (FLASH->OPTR & FLASH_OPTR_DBANK) != 0; }

static void unlock(void)
{
    if (FLASH->CR & FLASH_CR_LOCK) {
        FLASH->KEYR = 0x45670123u;
        FLASH->KEYR = 0xCDEF89ABu;
    }
}

static void lock(void) { FLASH->CR |= FLASH_CR_LOCK; }

static int busy(void) { return (FLASH->SR & FLASH_SR_BSY) != 0; }

static int result(void)
{
    uint32_t sr = FLASH->SR;
    FLASH->SR = sr & (SR_ERR | FLASH_SR_EOP);
    return (sr & SR_ERR) ? -1 : 0;
}

void flash_flush_caches(void)
{
    if (FLASH->ACR & FLASH_ACR_ICEN) {
        FLASH->ACR &= ~FLASH_ACR_ICEN;
        FLASH->ACR |= FLASH_ACR_ICRST;
        FLASH->ACR &= ~FLASH_ACR_ICRST;
        FLASH->ACR |= FLASH_ACR_ICEN;
    }
    if (FLASH->ACR & FLASH_ACR_DCEN) {
        FLASH->ACR &= ~FLASH_ACR_DCEN;
        FLASH->ACR |= FLASH_ACR_DCRST;
        FLASH->ACR &= ~FLASH_ACR_DCRST;
        FLASH->ACR |= FLASH_ACR_DCEN;
    }
}

static int page_ok(uint32_t a) { return a >= FLASH_BASE_ADDR && a < FLASH_BASE_ADDR + 0x80000u; }

/* start erasing the page holding a; returns at once */
static int erase_start(uint32_t a)
{
    if (!page_ok(a) || !flash_dual_bank())
        return -1;
    uint32_t page = (a - FLASH_BASE_ADDR) / FLASH_PAGE;
    while (busy()) {}
    FLASH->SR = SR_ERR | FLASH_SR_EOP;
    FLASH->CR = (FLASH->CR & ~(FLASH_CR_PNB | FLASH_CR_BKER | FLASH_CR_PG | FLASH_CR_PER))
              | FLASH_CR_PER | (page % 128u) << FLASH_CR_PNB_Pos | (page >= 128u ? FLASH_CR_BKER : 0u);
    FLASH->CR |= FLASH_CR_STRT;
    return 0;
}

static int erase_end(void)
{
    int r = result();
    FLASH->CR &= ~(FLASH_CR_PER | FLASH_CR_PNB | FLASH_CR_BKER);
    return r;
}

static int dword(uint32_t a, const uint8_t *p)
{
    uint32_t lo, hi;
    memcpy(&lo, p, 4);
    memcpy(&hi, p + 4, 4);
    while (busy()) {}
    FLASH->SR = SR_ERR | FLASH_SR_EOP;
    FLASH->CR |= FLASH_CR_PG;
    *(volatile uint32_t *)a = lo;
    __ISB();
    *(volatile uint32_t *)(a + 4) = hi;
    while (busy()) {}
    int r = result();
    FLASH->CR &= ~FLASH_CR_PG;
    return r;
}

int flash_erase(uint32_t addr, uint32_t len)
{
    int r = 0;
    unlock();
    for (uint32_t a = addr & ~(FLASH_PAGE - 1u); a < addr + len && !r; a += FLASH_PAGE) {
        r = erase_start(a);
        if (!r) {
            while (busy()) {}
            r = erase_end();
        }
    }
    lock();
    flash_flush_caches();
    return r;
}

int flash_write(uint32_t addr, const void *p, uint32_t len)
{
    if (addr & 7u)
        return -1;
    const uint8_t *b = p;
    int r = 0;
    unlock();
    for (uint32_t at = 0; at < len && !r; at += 8) {
        uint8_t w[8];
        memset(w, 0xFF, 8);
        memcpy(w, b + at, len - at < 8 ? len - at : 8);
        r = dword(addr + at, w);
    }
    lock();
    flash_flush_caches();
    return r;
}

/* ---- erasing while feeding the watchdog (the bootloader) ----
 * A bank-1 page erase stalls every fetch from bank 1 for 22-40 ms, longer
 * than the TPS3850's 20 ms window. So that wait runs from RAM, interrupts
 * off, toggling WDT_KICK (PC11) itself every `half` cycles. It touches
 * registers only: nothing in flash may be called from it. */
__attribute__((section(".ramfunc"), noinline))
static void ram_erase_wait(volatile uint32_t *kick_t, uint32_t half)
{
    FLASH->CR |= FLASH_CR_STRT;
    while (FLASH->SR & FLASH_SR_BSY) {
        if (DWT->CYCCNT - *kick_t >= half) {
            GPIOC->ODR ^= 1u << 11;
            *kick_t = DWT->CYCCNT;
        }
    }
}

int flash_erase_page_kick(uint32_t addr, volatile uint32_t *kick_t, uint32_t half)
{
    if (!page_ok(addr) || !flash_dual_bank())
        return -1;
    uint32_t page = (addr - FLASH_BASE_ADDR) / FLASH_PAGE;
    unlock();
    while (busy()) {}
    FLASH->SR = SR_ERR | FLASH_SR_EOP;
    FLASH->CR = (FLASH->CR & ~(FLASH_CR_PNB | FLASH_CR_BKER | FLASH_CR_PG | FLASH_CR_PER))
              | FLASH_CR_PER | (page % 128u) << FLASH_CR_PNB_Pos | (page >= 128u ? FLASH_CR_BKER : 0u);
    void (*volatile wait_fn)(volatile uint32_t *, uint32_t) = ram_erase_wait;   /* a long call */
    if (page < 128u) {
        uint32_t m = irq_save();
        wait_fn(kick_t, half);
        irq_restore(m);
    } else {
        FLASH->CR |= FLASH_CR_STRT;
        while (busy()) {
            if (DWT->CYCCNT - *kick_t >= half) {
                GPIOC->ODR ^= 1u << 11;
                *kick_t = DWT->CYCCNT;
            }
        }
    }
    int r = erase_end();
    lock();
    flash_flush_caches();
    return r;
}

/* ---- the job ---- */
enum { J_IDLE, J_ERASE, J_ERASING, J_WRITE, J_DONE };

void flash_job_start(flash_job *j, uint32_t addr, const void *p, uint32_t len)
{
    if (len > sizeof j->buf)
        len = sizeof j->buf;
    memcpy(j->buf, p, len);
    j->addr = addr;
    j->len = len;
    j->pos = 0;
    j->ok = 0;
    /* the job never touches bank 1: the code runs there */
    j->state = (addr >= FLASH_BANK2 && (addr & (FLASH_PAGE - 1u)) == 0) ? J_ERASE : J_DONE;
}

int flash_job_step(flash_job *j)
{
    switch (j->state) {
    case J_ERASE:                       /* the next page */
        unlock();
        if (erase_start(j->addr + j->pos)) {
            j->state = J_DONE;
            break;
        }
        j->state = J_ERASING;
        return 1;
    case J_ERASING:
        if (busy())
            return 1;
        if (erase_end()) {
            j->state = J_DONE;
            break;
        }
        j->pos += FLASH_PAGE;
        if (j->pos < j->len)
            j->state = J_ERASE;
        else {
            j->pos = 0;
            j->state = J_WRITE;
        }
        return 1;
    case J_WRITE:                       /* 32 double words (~3 ms) per call */
        for (int i = 0; i < 32 && j->pos < j->len; i++, j->pos += 8) {
            uint8_t w[8];
            memset(w, 0xFF, 8);
            uint32_t n = j->len - j->pos < 8 ? j->len - j->pos : 8;
            memcpy(w, j->buf + j->pos, n);
            if (dword(j->addr + j->pos, w)) {
                j->state = J_DONE;
                lock();
                flash_flush_caches();
                return 0;
            }
        }
        if (j->pos < j->len)
            return 1;
        j->ok = 1;
        j->state = J_DONE;
        break;
    default:
        return 0;
    }
    lock();
    flash_flush_caches();
    return 0;
}
