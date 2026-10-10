/* Rail pressure: PI on the metering-unit duty.
 * METER_NC 1: normally closed, more duty = more flow. This matches the
 * parent spec's trip design, where removing the unit's supply stops fuel.
 * The real valve is not yet identified; a normally-open one is METER_NC 0,
 * and then the trip module's contacts must move (decisions log 11). */
#ifndef RAIL_H
#define RAIL_H

#define METER_NC 1                   /* assumed: see above */
#define METER_CLOSED (METER_NC ? 0.0f : 1.0f)   /* duty that stops flow */
#define RAIL_SET_BAR 1000.0f         /* placeholder */
#define RAIL_KP 0.002f               /* calibration, duty/bar */
#define RAIL_KI 0.01f                /* calibration, duty/(bar*s) */
#define RAIL_DUTY_LIMP 0.3f          /* calibration: fixed duty while the rail sensor is faulted */

typedef struct { float integ; } rail_t;

void  rail_reset(rail_t *r);
float rail_step(rail_t *r, float rail_bar, float dt_s);

#endif
