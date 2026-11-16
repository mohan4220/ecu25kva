/* The bootloader on the prototype: firmware/boot/boot.c's host (firmware
 * guide sec. 14 item 13, sec. 16). 32 KiB at 0x08000000.
 *
 * At reset, still on the 16 MHz HSI: read and clear the stay flag, read
 * the hardware revision from the end-of-line record, and if boot_decide
 * says so jump to the application with the chip as reset left it (only
 * the watchdog pin touched). Otherwise bring up the clock, CAN channel 2
 * and USB, and serve the service link until a 0x11 reset.
 *
 * While it runs the engine cannot: every gate low (pins_safe), the
 * metering valve off, the main relay not held. The watchdog is fed from
 * the main loop and from inside every flash wait.
 *
 * Erase is lazy. The tool's erase (FF00) covers the whole 464 KiB area,
 * which takes ~5 s and the tool waits 2 s for a reply. So the request
 * erases only the header's page at once (the old image is gone the moment
 * it answers, as boot.c requires) and marks the rest; each page is erased
 * just before the first write into it. */
#include <string.h>
#include "hw.h"
#include "can.h"
#include "flash.h"
#include "usb.h"
#include "boot.h"
#include "eol.h"
#include "isotp.h"
#include "link.h"

__attribute__((section(".boot_info"), used))
const boot_info_t boot_info = { BOOT_INFO_MAGIC, BOOT_VERSION, 0 };

static volatile uint32_t kick_t;
static volatile uint32_t ms;
extern volatile uint32_t ecc_hits;

static void kick(void)
{
    uint32_t half = SystemCoreClock / 200u;          /* 5 ms: a falling edge every 10 ms */
    if (DWT->CYCCNT - kick_t >= half) {
        GPIOC->ODR ^= 1u << 11;
        kick_t = DWT->CYCCNT;
    }
}

/* ---- the flash, for boot.c ---- */
#define NPAGES (APP_SIZE / FLASH_PAGE)
static uint8_t pending[(NPAGES + 7) / 8];

static int page_index(uint32_t a) { return (int)((a - APP_BASE) / FLASH_PAGE); }

static int erase_now(uint32_t a)
{
    int i = page_index(a);
    pending[i / 8] &= (uint8_t)~(1u << (i % 8));
    return flash_erase_page_kick(APP_BASE + (uint32_t)i * FLASH_PAGE, &kick_t, SystemCoreClock / 200u);
}

static int f_erase(uint32_t a, uint32_t n)
{
    if (a < APP_BASE || n == 0 || a - APP_BASE + n > APP_SIZE)
        return -1;
    for (uint32_t p = a & ~(FLASH_PAGE - 1u); p < a + n; p += FLASH_PAGE) {
        int i = page_index(p);
        pending[i / 8] |= (uint8_t)(1u << (i % 8));
    }
    return erase_now(a);                             /* the first page, with the header, now */
}

static int f_write(uint32_t a, const uint8_t *p, uint32_t n)
{
    if (a < APP_BASE || a - APP_BASE + n > APP_SIZE || (a & 7u))
        return -1;
    for (uint32_t pg = a & ~(FLASH_PAGE - 1u); pg < a + n; pg += FLASH_PAGE) {
        int i = page_index(pg);
        if ((pending[i / 8] >> (i % 8) & 1u) && erase_now(pg))
            return -1;
    }
    for (uint32_t at = 0; at < n; at += 64) {        /* 8 double words, then the watchdog */
        uint32_t k = n - at < 64 ? n - at : 64;
        if (flash_write(a + at, p + at, k))
            return -1;
        kick();
    }
    return 0;
}

static int f_read(uint32_t a, uint8_t *p, uint32_t n)
{
    if (a < APP_BASE || a - APP_BASE + n > APP_SIZE)
        return -1;
    uint32_t e = ecc_hits;
    memcpy(p, (const void *)(uintptr_t)a, n);
    kick();
    return ecc_hits == e ? 0 : -1;
}

static const boot_flash F = { f_erase, f_write, f_read, APP_BASE, APP_SIZE };

static uint16_t hw_rev(void)
{
    eol_record a, b;
    uint32_t e = ecc_hits;
    memcpy(&a, (const void *)EOL_A, sizeof a);
    memcpy(&b, (const void *)EOL_B, sizeof b);
    if (ecc_hits != e)
        return 0;
    int k = eol_pick(&a, &b);
    return k < 0 ? 0 : (k ? b.hw_rev : a.hw_rev);
}

static void jump(void)
{
    const uint32_t *v = (const uint32_t *)APP_VECTORS;
    __disable_irq();
    SysTick->CTRL = 0;
    for (int i = 0; i < 8; i++) {
        NVIC->ICER[i] = 0xFFFFFFFFu;
        NVIC->ICPR[i] = 0xFFFFFFFFu;
    }
    SCB->VTOR = APP_VECTORS;
    __set_MSP(v[0]);
    __DSB();
    __ISB();
    __enable_irq();
    ((void (*)(void))v[1])();
    for (;;) {}
}

/* ---- the service link ---- */
static boot_t B;
static isotp_t tp;
static link_rx_t lrx;
static ecu_can can2q[ECU_CANQ];
static uint8_t can2n;
static uint8_t req[ISOTP_MAX], rsp[SVC_RESP_MAX], frame[SVC_RESP_MAX + 5];

#define RXQ 64
static ecu_can rxq[RXQ];
static volatile uint32_t rx_head, rx_tail;

static void can_rx(const ecu_can *f)                 /* FDCAN2 interrupt: queue it only */
{
    if (f->id != ECU_CAN2_REQ || rx_head - rx_tail >= RXQ)
        return;
    rxq[rx_head % RXQ] = *f;
    __DMB();
    rx_head++;
}

static int reset_due;

static void serve(const uint8_t *q, uint16_t n, int on_can)
{
    uint16_t m = boot_handle(&B, q, n, rsp, ms, ms * 1000u);
    if (!m)
        return;
    if (on_can) {
        isotp_send(&tp, rsp, m);
    } else {
        uint16_t k = link_frame(rsp, m, frame);
        usb_from_core(frame, k);
    }
    if (rsp[0] == 0x51)                              /* ECU reset: run the image if it is good */
        reset_due = 1;
}

static void pump_can(void)
{
    uint32_t m = irq_save();                         /* can_pump also runs in the FDCAN interrupt */
    ecu_can f;
    while (can2n < ECU_CANQ && isotp_next(&tp, &f))
        can2q[can2n++] = f;
    can_pump(1);
    irq_restore(m);
}

void SysTick_Handler(void) { ms++; usb_ms = ms; }

int main(void)
{
    pins_safe();                                     /* every gate low; WDT_KICK an output */
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    kick_t = DWT->CYCCNT;

    int stay = SHARED->stay == STAY_MAGIC;
    SHARED->stay = 0;
    uint16_t rev = hw_rev();
    if (boot_decide(&F, stay, rev) == 1)
        jump();

    clock_init();
    systick_1ms(PRIO_CORE);
    boot_init(&B, &F, rev);
    isotp_init(&tp, ECU_CAN2_RESP);
    can_init(1, can_rx, can2q, &can2n);
    usb_init();

    uint32_t reset_ms = 0;
    uint8_t buf[64];
    for (;;) {
        kick();
        while (rx_tail != rx_head) {                 /* CAN channel 2, ISO-TP */
            ecu_can f = rxq[rx_tail % RXQ];
            __DMB();
            rx_tail++;
            uint16_t n;
            if (isotp_rx(&tp, &f, req, &n))
                serve(req, n, 1);
            pump_can();
        }
        pump_can();
        usb_task();                                  /* USB, the link.h framing */
        uint16_t got = usb_to_core(buf, sizeof buf);
        for (uint16_t i = 0; i < got; i++) {
            uint16_t n;
            if (link_feed(&lrx, buf[i], req, &n))
                serve(req, n, 0);
        }
        /* the bootloader's own blink: two quick flashes a second */
        uint32_t t = ms % 1000u;
        pin_set(P_LED, t < 80u || (t >= 200u && t < 280u));
        if (reset_due) {
            if (!reset_ms)
                reset_ms = ms + 50u;
            if ((int32_t)(ms - reset_ms) >= 0 && ((usb_tx_idle() && can2n == 0) || (int32_t)(ms - reset_ms) > 500))
                NVIC_SystemReset();
        }
    }
}
