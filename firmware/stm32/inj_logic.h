/* The injector stage's sequencing, with no hardware in it, so the PC can
 * test it against a coil model (firmware/stm32/test_inj.c).
 *
 * One injection at a time (cylinders fire 240 degrees apart and the
 * longest pulse is a few ms, so they never overlap; one that would is
 * refused and counted). For each:
 *
 *   START  low side on, the bank's BOOST high side on: the current
 *          climbs at ~0.5 A/us from 100 V.
 *   PEAK   at INJ_PEAK_A (ADC1 watchdog), boost high side off: the coil
 *          freewheels through D_fw with the low side still on.
 *   HOLD   the BATTERY high side chops between INJ_HOLD_LO_A and
 *          INJ_HOLD_HI_A, each crossing an ADC1 watchdog event.
 *   END    at start + dur: every gate off; the current recirculates
 *          into the boost reservoir (injector_turnoff.cir).
 *
 * Safety, independent of the core: no peak within INJ_PEAK_MAX_US ends
 * the injection (a broken sense must not hold 100 V on a coil); over
 * INJ_OVER_A in any phase ends it; no injection is longer than
 * INJ_CAP_US; a start found more than INJ_LATE_US late is skipped. */
#ifndef INJ_LOGIC_H
#define INJ_LOGIC_H

#include <stdint.h>

#define INJ_NCYL 3

/* gate bits */
enum { G_LS1 = 1, G_LS2 = 2, G_LS3 = 4, G_HS_A = 8, G_HS_B = 16, G_HS_A_BAT = 32, G_HS_B_BAT = 64 };

/* what the current watchdog should look for next */
enum { W_OFF, W_ABOVE, W_BELOW };

enum { PH_IDLE, PH_PEAK, PH_DECAY, PH_HOLD_ON };

typedef struct {
    uint32_t start, end;              /* end = start + dur, capped */
    uint8_t pending;                  /* a command not yet started */
} inj_slot;

typedef struct {
    inj_slot slot[INJ_NCYL];
    int8_t active;                    /* cylinder being injected, -1 none */
    uint8_t phase;
    uint32_t end, peak_by;            /* of the active injection */
    uint8_t gates;                    /* the gate bits to drive */
    uint8_t watch;                    /* W_*: the watchdog's direction */
    uint8_t bank;                     /* 0 A, 1 B: which shunt the ADC reads */
    uint16_t lvl;                     /* the watchdog's level, ADC counts */
    /* the levels, ADC counts (inj_set_levels) */
    uint16_t c_peak, c_lo, c_hi, c_over;
    /* counters, for the bench and the logs */
    uint32_t n_done, n_late, n_overlap, n_peak_timeout, n_over, n_capped;
} inj_t;

void inj_init(inj_t *s);
void inj_set_levels(inj_t *s, float vdda);            /* amps to counts at this VDDA */
/* A new command for cylinder k (ecu_inj semantics: dur 0 cancels one not
 * yet started; one already open runs to its end). */
void inj_command(inj_t *s, int k, uint32_t start_us, uint32_t dur_us);
/* The next time inj_timer must run; 0 = nothing to wait for. *t set. */
int  inj_next(const inj_t *s, uint32_t *t);
/* Timer due at `now`: starts, ends, the peak timeout. */
void inj_timer(inj_t *s, uint32_t now);
/* The ADC watchdog saw the current cross `lvl` in direction `watch`. */
void inj_cross(inj_t *s, uint32_t now);
/* Over-current: everything off. */
void inj_over(inj_t *s);

int inj_bank_of(int k);                               /* cylinder 1, 3: bank A (0); 2: B (1) */

#endif
