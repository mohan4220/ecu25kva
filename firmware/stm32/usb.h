#ifndef USB_H
#define USB_H
#include <stdint.h>

/* The prototype's service port (J302): a CDC-ACM virtual serial port
 * carrying the link.h framing. TinyUSB runs in the main loop (usb_task);
 * the core's side runs in the 1 ms tick (usb_to_core / usb_from_core).
 * Two single-producer, single-consumer rings join them. */
void usb_init(void);
void usb_task(void);                                         /* main loop */
uint16_t usb_to_core(uint8_t *dst, uint16_t max);            /* tick: bytes received */
void usb_from_core(const uint8_t *src, uint16_t n);          /* tick: bytes to send */
int  usb_tx_idle(void);                                      /* nothing left to send */
extern volatile uint32_t usb_ms;                             /* for TinyUSB's clock */

#endif
