/* The engine state machine, and the protections that keep their own time.
 *
 * Each is a small machine with its own state, stepped by ecu.c, which
 * turns its outputs into DTCs, trips and pins. ECU_MODEL builds take each
 * from a Stateflow chart in model/ (firmware/gen/, via model_glue.c);
 * mode.c is the hand-written reference. */
#ifndef MODE_H
#define MODE_H

#include <stdint.h>

#define RUN_RPM 400.0f               /* CRANK -> RUN once phased and above this */

/* ---- engine mode: OFF -> WAIT -> CRANK -> RUN, any -> SHUTDOWN, RESET -> OFF ---- */
enum { MODE_IGN_ON = 1, MODE_TOOTH, MODE_RUN_OK, MODE_TRIP, MODE_RESET };
uint8_t mode_cmd(uint8_t cmd, uint8_t phased, float rpm);   /* returns the new ECU_* state */

/* ---- boost rail over BOOST_OV_V for BOOST_OV_MS: trip once, latched ---- */
void boostg_reset(void);
void boostg_step(float v_rail, uint8_t shut, uint8_t *dis, uint8_t *trip);

/* ---- EGR stall: coast, retry, lock out after EGR_STALL_TRIES ---- */
void egrg_reset(void);
void egrg_step(float i_egr, uint8_t *off, uint8_t *raise);

/* ---- water in fuel: WIF_MS each way. Reset only at ecu_init ---- */
void wifg_reset(void);
void wifg_step(uint8_t wif, uint8_t *raise, uint8_t *drop);

/* ---- underspeed warning, armed once the start ramp is done ---- */
void underg_reset(void);
void underg_step(float rpm, uint8_t armed, uint8_t *raise, uint8_t *drop);

/* ---- main relay: held with the ignition, then the after-run ---- */
void relay_reset(void);
void relay_step(uint8_t ignition, uint8_t stopped, uint8_t written,
                uint8_t *relay, uint8_t *afterrun, uint8_t *save);

#endif
