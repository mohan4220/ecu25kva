/* FDCAN1 and FDCAN2 in classic CAN. The message RAM layout is the fixed
 * one of the STM32G4 (RM0440 sec. 44.3.3; ST's HAL SRAMCAN_*): per
 * instance 28 standard filters, 8 extended, 3-deep RX FIFO 0 and 1, a
 * 3-entry TX event FIFO and a 3-entry TX FIFO, 18-word elements. No
 * filters: everything goes to RX FIFO 0 and the core picks (it ignores
 * what is not its own). Kernel clock PCLK1 = 170 MHz.
 *
 *   250 kbit/s: 17 per tq, 40 tq, sample point 87.5 % (J1939-11), SJW 3
 *   1 Mbit/s:   10 per tq, 17 tq, sample point 88.2 %, SJW 2 */
#include <string.h>
#include "hw.h"
#include "can.h"

#define RAM_SIZE 0x350u
#define RF0_OFS 0x0B0u
#define TFQ_OFS 0x278u
#define ELEM 72u
#define XTD (1u << 30)
#define RTR (1u << 29)

typedef struct {
    FDCAN_GlobalTypeDef *r;
    uint32_t ram;
    int ext;                                    /* 29-bit identifiers */
    can_rx_fn rx;
    ecu_can *q;
    uint8_t *qn;
    uint32_t lost;
    uint32_t off_ms;
} can_t;

static can_t C[2];

void can_init(int ch, can_rx_fn rx, ecu_can *q, uint8_t *qn)
{
    can_t *c = &C[ch];
    c->r = ch ? FDCAN2 : FDCAN1;
    c->ram = SRAMCAN_BASE + (uint32_t)ch * RAM_SIZE;
    c->ext = ch == 0;
    c->rx = rx;
    c->q = q;
    c->qn = qn;

    RCC->CCIPR = (RCC->CCIPR & ~RCC_CCIPR_FDCANSEL) | 2u << RCC_CCIPR_FDCANSEL_Pos;   /* PCLK1 */
    RCC->APB1ENR1 |= RCC_APB1ENR1_FDCANEN;
    (void)RCC->APB1ENR1;
    if (ch == 0) {
        pin_mode(P_CAN1_RX, PM_AF, AF_FDCAN);
        pin_mode(P_CAN1_TX, PM_AF, AF_FDCAN);
    } else {
        pin_mode(P_CAN2_RX, PM_AF, AF_FDCAN);
        pin_mode(P_CAN2_TX, PM_AF, AF_FDCAN);
    }

    FDCAN_GlobalTypeDef *r = c->r;
    r->CCCR &= ~FDCAN_CCCR_CSR;
    r->CCCR |= FDCAN_CCCR_INIT;
    while (!(r->CCCR & FDCAN_CCCR_INIT)) {}
    r->CCCR |= FDCAN_CCCR_CCE;
    FDCAN_CONFIG->CKDIV = 0;                    /* /1, shared by all instances */
    r->CCCR &= ~(FDCAN_CCCR_FDOE | FDCAN_CCCR_BRSE | FDCAN_CCCR_DAR | FDCAN_CCCR_TEST
               | FDCAN_CCCR_MON | FDCAN_CCCR_ASM | FDCAN_CCCR_TXP);
    if (ch == 0)
        r->NBTP = (3u - 1u) << FDCAN_NBTP_NSJW_Pos | (17u - 1u) << FDCAN_NBTP_NBRP_Pos
                | (34u - 1u) << FDCAN_NBTP_NTSEG1_Pos | (5u - 1u) << FDCAN_NBTP_NTSEG2_Pos;
    else
        r->NBTP = (2u - 1u) << FDCAN_NBTP_NSJW_Pos | (10u - 1u) << FDCAN_NBTP_NBRP_Pos
                | (14u - 1u) << FDCAN_NBTP_NTSEG1_Pos | (2u - 1u) << FDCAN_NBTP_NTSEG2_Pos;
    /* no filters; non-matching standard and extended frames to FIFO 0;
     * remote frames rejected */
    r->RXGFC = FDCAN_RXGFC_RRFS | FDCAN_RXGFC_RRFE;
    r->TXBC = 0;                                /* TX FIFO mode */
    for (uint32_t a = c->ram; a < c->ram + RAM_SIZE; a += 4)
        *(volatile uint32_t *)a = 0;
    r->ILS = 0;                                 /* every group on line 0 */
    r->IE = FDCAN_IE_RF0NE | FDCAN_IE_RF0LE;
    r->ILE = FDCAN_ILE_EINT0;
    r->CCCR &= ~FDCAN_CCCR_INIT;                /* clears CCE too */
    irq_on(ch ? FDCAN2_IT0_IRQn : FDCAN1_IT0_IRQn, PRIO_CORE);
}

static void rx_drain(can_t *c)
{
    FDCAN_GlobalTypeDef *r = c->r;
    while (r->RXF0S & FDCAN_RXF0S_F0FL) {
        uint32_t gi = (r->RXF0S & FDCAN_RXF0S_F0GI) >> FDCAN_RXF0S_F0GI_Pos;
        const volatile uint32_t *e = (const volatile uint32_t *)(c->ram + RF0_OFS + gi * ELEM);
        uint32_t w0 = e[0], w1 = e[1], d0 = e[2], d1 = e[3];
        r->RXF0A = gi;
        int xtd = (w0 & XTD) != 0;
        if (xtd != c->ext || (w0 & RTR))
            continue;
        ecu_can f;
        f.id = xtd ? (w0 & 0x1FFFFFFFu) : (w0 >> 18 & 0x7FFu);
        uint32_t dlc = w1 >> 16 & 15u;
        f.len = (uint8_t)(dlc > 8 ? 8 : dlc);
        for (int i = 0; i < 4; i++) {
            f.data[i] = (uint8_t)(d0 >> (8 * i));
            f.data[4 + i] = (uint8_t)(d1 >> (8 * i));
        }
        c->rx(&f);
    }
}

void can_pump(int ch)
{
    can_t *c = &C[ch];
    FDCAN_GlobalTypeDef *r = c->r;
    /* bus-off: the controller sets INIT; rejoin (it waits 128 x 11 recessive bits itself) */
    if ((r->CCCR & FDCAN_CCCR_INIT) && (r->PSR & FDCAN_PSR_BO))
        r->CCCR &= ~FDCAN_CCCR_INIT;
    uint8_t n = *c->qn, sent = 0;
    while (sent < n && !(r->TXFQS & FDCAN_TXFQS_TFQF)) {
        uint32_t pi = (r->TXFQS & FDCAN_TXFQS_TFQPI) >> FDCAN_TXFQS_TFQPI_Pos;
        volatile uint32_t *e = (volatile uint32_t *)(c->ram + TFQ_OFS + pi * ELEM);
        const ecu_can *f = &c->q[sent];
        uint8_t len = f->len > 8 ? 8 : f->len;
        uint8_t d[8] = { 0 };
        memcpy(d, f->data, len);
        e[0] = c->ext ? (XTD | (f->id & 0x1FFFFFFFu)) : (f->id & 0x7FFu) << 18;
        e[1] = (uint32_t)len << 16;
        e[2] = (uint32_t)d[0] | (uint32_t)d[1] << 8 | (uint32_t)d[2] << 16 | (uint32_t)d[3] << 24;
        e[3] = (uint32_t)d[4] | (uint32_t)d[5] << 8 | (uint32_t)d[6] << 16 | (uint32_t)d[7] << 24;
        r->TXBAR = 1u << pi;
        sent++;
    }
    if (sent) {
        memmove(c->q, c->q + sent, (size_t)(n - sent) * sizeof c->q[0]);
        *c->qn = (uint8_t)(n - sent);
    }
    /* more waiting: wake when the FIFO empties */
    if (*c->qn)
        r->IE |= FDCAN_IE_TFEE;
    else
        r->IE &= ~FDCAN_IE_TFEE;
}

static void isr(int ch)
{
    can_t *c = &C[ch];
    uint32_t ir = c->r->IR;
    c->r->IR = ir;
    if (ir & FDCAN_IR_RF0L)
        c->lost++;
    if (ir & (FDCAN_IR_RF0N | FDCAN_IR_RF0L))
        rx_drain(c);
    can_pump(ch);                       /* a request just answered, or the FIFO emptied */
}

void FDCAN1_IT0_IRQHandler(void) { isr(0); }
void FDCAN2_IT0_IRQHandler(void) { isr(1); }

int can_bus_off(int ch) { return (C[ch].r->PSR & FDCAN_PSR_BO) != 0; }
uint32_t can_rx_lost(int ch) { return C[ch].lost; }
