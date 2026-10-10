/* The whole firmware interface: one struct of inputs and outputs, four
 * entry points. The PC simulator and the S32K148 port both fill the
 * inputs and read the outputs; nothing here touches hardware. */
#ifndef ECU_H
#define ECU_H

#include <stddef.h>
#include <stdint.h>

#define ECU_NCYL 3
#define ECU_CANQ 16
#define ECU_MS_WRAP 3600000u         /* the ms counter wraps hourly; every period divides it */
#define IGN_OFF_MS 500               /* ignition low this long, engine stopped, clears SHUTDOWN */

typedef enum { ECU_OFF, ECU_WAIT, ECU_CRANK, ECU_RUN, ECU_SHUTDOWN } ecu_state;

typedef struct { uint32_t id; uint8_t len; uint8_t data[8]; } ecu_can;

/* One injection command per cylinder, as a timer output-compare runs it.
 * seq increments on every change, including a cancel (dur_us 0): a
 * consumer that watches seq alone sees everything. A cancel stops a
 * command not yet started; one already open runs to its end. */
typedef struct { uint32_t start_us, dur_us, seq; } ecu_inj;

typedef struct {
    /* inputs (host writes) */
    float v_clt, v_oil, v_rail, v_boost, v_egr, v_5v;
    uint8_t ignition, droop_sw;
    /* outputs (host reads) */
    ecu_inj inj[ECU_NCYL];
    float meter_duty;            /* 0..1, normally open: more duty, less flow */
    uint8_t wdg;                 /* WDI pin level */
    ecu_can can[ECU_CANQ];
    uint8_t can_n;               /* host reads can[0..can_n), then sets can_n = 0 */
    uint16_t can_drops;
    /* status */
    uint8_t state, fault_n, synced;
    float rpm, fuel_mg, rail_bar, clt_c, oil_kpa;
} ecu_io;

void ecu_init(ecu_io *io);
void ecu_crank_edge(ecu_io *io, uint32_t t_us);   /* falling edge of a tooth */
void ecu_cam_edge(ecu_io *io, uint32_t t_us);
void ecu_tick_1ms(ecu_io *io, uint32_t t_us);      /* slow loops, CAN, safety */
size_t ecu_io_size(void);

#endif
