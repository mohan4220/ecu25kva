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

/* ---- engine mode: OFF -> WAIT -> CRANK -> RUN, any -> SHUTDOWN, RESET -> OFF ----
 * TICK, every 1 ms: OFF -> WAIT with the ignition on; in SHUTDOWN it times
 * the ignition cycle (low for IGN_OFF_MS with the engine stopped, then on)
 * and goes to OFF when it completes -- ecu.c then resets everything else.
 * TOOTH: WAIT -> CRANK. RUN_OK: CRANK -> RUN, phased and at RUN_RPM. */
enum { MODE_TICK = 1, MODE_TOOTH, MODE_RUN_OK, MODE_TRIP, MODE_RESET };
uint8_t mode_cmd(uint8_t cmd, uint8_t ignition, uint8_t phased, float rpm);   /* the new ECU_* state */

/* ---- boost rail over BOOST_OV_V for BOOST_OV_MS: trip once, latched ---- */
void boostg_reset(void);
void boostg_step(float v_rail, uint8_t shut, uint8_t *dis, uint8_t *trip);

/* ---- boost rail warnings: held high, or low while fuelling. Debounced
 * BOOST_HIGH_MS / BOOST_LOW_MS each way; v_rail 0 = not measured ---- */
void boostm_reset(void);
void boostm_step(float v_rail, uint8_t fuelling, uint8_t *hi_raise, uint8_t *hi_drop,
                 uint8_t *lo_raise, uint8_t *lo_drop);

/* ---- EGR stall: coast, retry, lock out after EGR_STALL_TRIES ---- */
void egrg_reset(void);
void egrg_step(float i_egr, uint8_t *off, uint8_t *raise);

/* ---- water in fuel: WIF_MS each way. Reset only at ecu_init ---- */
void wifg_reset(void);
void wifg_step(uint8_t wif, uint8_t *raise, uint8_t *drop);

/* ---- underspeed warning, armed once the start ramp is done ---- */
void underg_reset(void);
void underg_step(float rpm, uint8_t armed, uint8_t *raise, uint8_t *drop);

/* ---- speed states (decisions log 23, the 20 kVA set's cascade): what the
 * governor aims for. OFF until RUN; IDLE holds GOV_IDLE_RPM for idle_ms
 * (0 = no idle: straight on); OPERATING ramps to and regulates the rated
 * setpoint; STEADY once within SPD_BAND_RPM of it for SPD_STEADY_MS, and
 * back to OPERATING beyond twice the band. ---- */
#define SPD_IDLE_MS 0u               /* calibration: warm-up idle; 0 = none (the DSE decides) */
#define SPD_BAND_RPM 15.0f
#define SPD_STEADY_MS 1000
enum { SPD_OFF, SPD_IDLE, SPD_OPERATING, SPD_STEADY };
void spdst_reset(void);
void spdst_step(uint8_t running, float rpm, float target, uint32_t idle_ms,
                uint8_t *idle, uint8_t *state);

/* ---- a fault's debounce and healing (decisions log 24): one instance per
 * diagnosis in diag.h. CLEAR until the condition has held deb_ms ticks,
 * then ACTIVE until it has been absent heal_ms ticks (0: at once); a tick
 * the other way restarts the count. Unlike the guards above it has many
 * instances, so its state is the caller's. ---- */
#ifdef ECU_MODEL
#include "ecu_deb.h"
typedef struct { uint8_t act; RT_MODEL_ecu_deb_T m; DW_ecu_deb_T dw; } deb_t;
#else
typedef struct { uint16_t n; uint8_t act; } deb_t;
#endif
void    deb_reset(deb_t *d);
uint8_t deb_step(deb_t *d, uint8_t cond, uint16_t deb_ms, uint16_t heal_ms);   /* 1 = active */

/* ---- main relay: held with the ignition, then the after-run ---- */
void relay_reset(void);
void relay_step(uint8_t ignition, uint8_t stopped, uint8_t written,
                uint8_t *relay, uint8_t *afterrun, uint8_t *save);

#endif
