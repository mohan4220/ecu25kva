/* Rail pressure: PI on the metering-unit duty, to a setpoint that follows
 * fuel.
 * METER_NC 0: normally open, more duty = less flow, full duty stops it.
 * The old ECU's recording shows exactly that (field evidence 2026-10-14
 * sec. 3a: current falls as pressure rises, and rises to stop the engine).
 * Confirm with the valve's part number. With a normally-open valve, losing
 * the drive means full flow, so the trip module must act on the injector
 * supply, not the valve's (decisions log 11, 14). */
#ifndef RAIL_H
#define RAIL_H

#define METER_NC 0                   /* measured behaviour: see above */
#define METER_CLOSED (METER_NC ? 0.0f : 1.0f)   /* duty that stops flow */
#define RAIL_KP 0.002f               /* calibration, duty/bar */
#define RAIL_KI 0.01f                /* calibration, duty/(bar*s) */
#define RAIL_OPEN_LIMP 0.3f          /* calibration: fixed opening while the rail sensor is faulted */
#define RAIL_DUTY_LIMP (METER_NC ? RAIL_OPEN_LIMP : 1.0f - RAIL_OPEN_LIMP)

typedef struct { float integ; } rail_t;

void  rail_reset(rail_t *r);
float rail_set_bar(float fuel_mg);
float rail_step(rail_t *r, float set_bar, float rail_bar, float dt_s);

#endif
