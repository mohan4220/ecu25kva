#include <string.h>
#include "hw.h"
#include "usb.h"
#include "tusb.h"

volatile uint32_t usb_ms;

#define RING 2048u                          /* a power of two */
typedef struct {
    uint8_t b[RING];
    volatile uint32_t head, tail;           /* head: producer; tail: consumer */
} ring_t;

static ring_t rx, tx;
static uint32_t rx_drops, tx_drops;

static uint32_t used(const ring_t *r) { return r->head - r->tail; }

static uint32_t put(ring_t *r, const uint8_t *p, uint32_t n)
{
    uint32_t room = RING - used(r), k = n < room ? n : room;
    for (uint32_t i = 0; i < k; i++)
        r->b[(r->head + i) & (RING - 1u)] = p[i];
    __DMB();
    r->head += k;
    return k;
}

static uint32_t get(ring_t *r, uint8_t *p, uint32_t max)
{
    uint32_t k = used(r) < max ? used(r) : max;
    for (uint32_t i = 0; i < k; i++)
        p[i] = r->b[(r->tail + i) & (RING - 1u)];
    __DMB();
    r->tail += k;
    return k;
}

uint32_t tusb_time_millis_api(void) { return usb_ms; }

void usb_init(void)
{
    clock_usb48();
    RCC->APB1ENR1 |= RCC_APB1ENR1_USBEN;
    (void)RCC->APB1ENR1;
    NVIC_SetPriority(USB_HP_IRQn, PRIO_USB);
    NVIC_SetPriority(USB_LP_IRQn, PRIO_USB);
    NVIC_SetPriority(USBWakeUp_IRQn, PRIO_USB);
    tusb_rhport_init_t init = { .role = TUSB_ROLE_DEVICE, .speed = TUSB_SPEED_AUTO };
    tusb_init(0, &init);
}

void USB_HP_IRQHandler(void) { tud_int_handler(0); }
void USB_LP_IRQHandler(void) { tud_int_handler(0); }
void USBWakeUp_IRQHandler(void) { tud_int_handler(0); }

void usb_task(void)
{
    uint8_t buf[64];
    tud_task();
    /* host -> ring */
    while (tud_cdc_available()) {
        uint32_t room = RING - used(&rx);
        if (room == 0)
            break;
        uint32_t n = tud_cdc_read(buf, room < sizeof buf ? room : sizeof buf);
        if (!n)
            break;
        rx_drops += n - put(&rx, buf, n);
    }
    /* ring -> host */
    while (used(&tx) && tud_cdc_connected()) {
        uint32_t room = tud_cdc_write_available();
        if (room == 0)
            break;
        uint32_t n = get(&tx, buf, room < sizeof buf ? room : sizeof buf);
        tud_cdc_write(buf, n);
    }
    tud_cdc_write_flush();
}

uint16_t usb_to_core(uint8_t *dst, uint16_t max) { return (uint16_t)get(&rx, dst, max); }

void usb_from_core(const uint8_t *src, uint16_t n) { tx_drops += n - put(&tx, src, n); }

int usb_tx_idle(void) { return used(&tx) == 0; }

/* ---- descriptors: pid.codes' test VID/PID, fine for a prototype on a
 * bench; a product needs its own. ---- */
static const tusb_desc_device_t dev = {
    .bLength = sizeof(tusb_desc_device_t),
    .bDescriptorType = TUSB_DESC_DEVICE,
    .bcdUSB = 0x0200,
    .bDeviceClass = TUSB_CLASS_MISC,
    .bDeviceSubClass = MISC_SUBCLASS_COMMON,
    .bDeviceProtocol = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor = 0x1209,
    .idProduct = 0x0001,
    .bcdDevice = 0x0100,
    .iManufacturer = 1,
    .iProduct = 2,
    .iSerialNumber = 3,
    .bNumConfigurations = 1,
};

const uint8_t *tud_descriptor_device_cb(void) { return (const uint8_t *)&dev; }

enum { ITF_CDC, ITF_CDC_DATA, ITF_N };
#define EP_NOTIF 0x81
#define EP_OUT 0x02
#define EP_IN 0x82
#define CONFIG_LEN (TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN)

static const uint8_t config[] = {
    TUD_CONFIG_DESCRIPTOR(1, ITF_N, 0, CONFIG_LEN, 0x00, 100),
    TUD_CDC_DESCRIPTOR(ITF_CDC, 4, EP_NOTIF, 8, EP_OUT, EP_IN, 64),
};

const uint8_t *tud_descriptor_configuration_cb(uint8_t index)
{
    (void)index;
    return config;
}

/* by string index: 0 language, 1 maker, 2 product, 3 serial, 4 the CDC interface */
static const char *const strs[] = { 0, "ecu25kva", "Genset ECU prototype (STM32G474)", 0, "Service link" };

const uint16_t *tud_descriptor_string_cb(uint8_t index, uint16_t langid)
{
    (void)langid;
    static uint16_t d[1 + 32];
    char serial[25];
    const char *s;
    if (index == 0) {
        d[1] = 0x0409;
        d[0] = (uint16_t)(TUSB_DESC_STRING << 8 | 4);
        return d;
    }
    if (index == 3) {                       /* the chip's 96-bit unique ID */
        const uint32_t *uid = (const uint32_t *)UID_BASE;
        static const char hx[] = "0123456789ABCDEF";
        for (int w = 0; w < 3; w++)
            for (int i = 0; i < 8; i++)
                serial[w * 8 + i] = hx[uid[w] >> (28 - 4 * i) & 15u];
        serial[24] = 0;
        s = serial;
    } else if (index < sizeof strs / sizeof strs[0] && strs[index]) {
        s = strs[index];
    } else {
        return 0;
    }
    uint8_t n = (uint8_t)strlen(s);
    if (n > 32)
        n = 32;
    for (uint8_t i = 0; i < n; i++)
        d[1 + i] = (uint8_t)s[i];
    d[0] = (uint16_t)(TUSB_DESC_STRING << 8 | (2 * n + 2));
    return d;
}
