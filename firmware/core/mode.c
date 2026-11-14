/* The hand-written reference for mode.h (ECU_MODEL off). Each machine
 * moved here from ecu.c unchanged in behaviour; the Stateflow charts in
 * model/ reproduce them tick for tick. */
#ifndef ECU_MODEL

#include "mode.h"
#include "ecu.h"
#include "safety.h"
#include "govern.h"

/* ---- engine mode ---- */
static uint8_t st = ECU_OFF;
static uint16_t low_ms;              /* in SHUTDOWN: ignition low, engine stopped, this long */

uint8_t mode_cmd(uint8_t cmd, uint8_t ignition, uint8_t phased, float rpm)
{
    switch (cmd) {
    case MODE_RESET:  st = ECU_OFF; break;
    case MODE_TRIP:
        if (st != ECU_SHUTDOWN)
            low_ms = 0;
        st = ECU_SHUTDOWN;
        break;
    case MODE_TICK:
        if (st == ECU_OFF && ignition) {
            st = ECU_WAIT;
        } else if (st == ECU_SHUTDOWN) {
            /* the latch clears only on a real ignition cycle: low for
             * IGN_OFF_MS with the engine stopped, then high. A contact
             * bounce does nothing. */
            if (ignition) {
                if (low_ms >= IGN_OFF_MS)
                    st = ECU_OFF;
                low_ms = 0;
            } else {
                low_ms = rpm == 0 ? (uint16_t)(low_ms + (low_ms < IGN_OFF_MS)) : 0;
            }
        }
        break;
    case MODE_TOOTH:  if (st == ECU_WAIT) st = ECU_CRANK; break;
    case MODE_RUN_OK: if (st == ECU_CRANK && phased && rpm >= RUN_RPM) st = ECU_RUN; break;
    default: break;
    }
    return st;
}

/* ---- boost guard ---- */
static uint16_t boost_ov_ms;
static uint8_t boost_ov;

void boostg_reset(void) { boost_ov_ms = 0; boost_ov = 0; }

void boostg_step(float v_rail, uint8_t shut, uint8_t *dis, uint8_t *trip)
{
    *trip = 0;
    if (v_rail > BOOST_OV_V) {
        if (boost_ov_ms < BOOST_OV_MS && ++boost_ov_ms == BOOST_OV_MS && !boost_ov) {
            boost_ov = 1;
            *trip = 1;
        }
    } else {
        boost_ov_ms = 0;
    }
    *dis = boost_ov || shut;
}

/* ---- boost rail warnings ---- */
static uint16_t bh_on, bh_off, bl_on, bl_off;

void boostm_reset(void) { bh_on = bh_off = bl_on = bl_off = 0; }

static void debounce(uint8_t cond, uint16_t ms, uint16_t *on, uint16_t *off,
                     uint8_t *raise, uint8_t *drop)
{
    *on = cond ? (uint16_t)(*on + (*on < ms)) : 0;
    *off = cond ? 0 : (uint16_t)(*off + (*off < ms));
    *raise = *on >= ms;
    *drop = !*raise && *off >= ms;
}

void boostm_step(float v_rail, uint8_t fuelling, uint8_t *hi_raise, uint8_t *hi_drop,
                 uint8_t *lo_raise, uint8_t *lo_drop)
{
    debounce(v_rail > BOOST_HIGH_V, BOOST_HIGH_MS, &bh_on, &bh_off, hi_raise, hi_drop);
    debounce(fuelling && v_rail > 0 && v_rail < BOOST_LOW_V, BOOST_LOW_MS,
             &bl_on, &bl_off, lo_raise, lo_drop);
}

/* ---- EGR stall guard ---- */
static uint16_t egr_hot_ms, egr_cool_ms;
static uint8_t egr_stalls, egr_off;

void egrg_reset(void) { egr_hot_ms = egr_cool_ms = 0; egr_stalls = egr_off = 0; }

void egrg_step(float i_egr, uint8_t *off, uint8_t *raise)
{
    *raise = 0;
    if (i_egr > EGR_STALL_A)
        egr_hot_ms = (uint16_t)(egr_hot_ms + (egr_hot_ms < EGR_STALL_MS));
    else if (egr_hot_ms)
        egr_hot_ms--;
    if (egr_cool_ms)
        egr_cool_ms--;
    if (egr_hot_ms >= EGR_STALL_MS && !egr_off) {
        egr_hot_ms = 0;
        egr_cool_ms = EGR_COOL_MS;
        if (egr_stalls < EGR_STALL_TRIES)
            egr_stalls++;
        *raise = 1;
    }
    egr_off = egr_stalls >= EGR_STALL_TRIES || egr_cool_ms > 0;
    *off = egr_off;
}

/* ---- water in fuel ---- */
static uint16_t wif_on_ms, wif_off_ms;

void wifg_reset(void) { wif_on_ms = wif_off_ms = 0; }

void wifg_step(uint8_t wif, uint8_t *raise, uint8_t *drop)
{
    wif_on_ms = wif ? (uint16_t)(wif_on_ms + (wif_on_ms < WIF_MS)) : 0;
    wif_off_ms = wif ? 0 : (uint16_t)(wif_off_ms + (wif_off_ms < WIF_MS));
    *raise = wif_on_ms >= WIF_MS;
    *drop = !*raise && wif_off_ms >= WIF_MS;
}

/* ---- underspeed ---- */
static uint16_t under_ms, over_ms;

void underg_reset(void) { under_ms = over_ms = 0; }

void underg_step(float rpm, uint8_t armed, uint8_t *raise, uint8_t *drop)
{
    *raise = *drop = 0;
    if (!armed) {
        under_ms = over_ms = 0;
        *drop = 1;
        return;
    }
    under_ms = rpm < UNDERSPEED_RPM ? (uint16_t)(under_ms + (under_ms < UNDERSPEED_MS)) : 0;
    over_ms = rpm > UNDERSPEED_CLEAR_RPM ? (uint16_t)(over_ms + (over_ms < UNDERSPEED_CLEAR_MS)) : 0;
    if (under_ms >= UNDERSPEED_MS)
        *raise = 1;
    else if (over_ms >= UNDERSPEED_CLEAR_MS)
        *drop = 1;
}

/* ---- main relay ---- */
static uint8_t relay_on, relay_after;
static uint16_t afterrun_ms;

void relay_reset(void) { relay_on = relay_after = 0; afterrun_ms = 0; }

void relay_step(uint8_t ignition, uint8_t stopped, uint8_t written,
                uint8_t *relay, uint8_t *afterrun, uint8_t *save)
{
    *save = 0;
    if (ignition) {
        relay_on = 1;
        relay_after = 0;
        afterrun_ms = 0;
    } else if (relay_on) {
        if (!relay_after) {
            relay_after = 1;
            *save = 1;
            written = 0;                /* the save it just asked for is pending */
        }
        if (afterrun_ms < AFTERRUN_MAX_MS)
            afterrun_ms++;
        if ((stopped && written) || afterrun_ms >= AFTERRUN_MAX_MS) {
            relay_on = 0;               /* the board loses its supply here */
            relay_after = 0;
        }
    }
    *relay = relay_on;
    *afterrun = relay_after;
}

#endif
