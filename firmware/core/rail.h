/* Rail pressure: PI on the metering-unit duty. The unit is normally open
 * (inlet metering), so more duty means less flow: duty rises with
 * pressure above setpoint. */
#ifndef RAIL_H
#define RAIL_H

#define RAIL_SET_BAR 1000.0f         /* placeholder */
#define RAIL_KP 0.002f               /* calibration, duty/bar */
#define RAIL_KI 0.01f                /* calibration, duty/(bar*s) */
#define RAIL_DUTY_LIMP 0.3f          /* calibration: fixed duty while the rail sensor is faulted */

typedef struct { float integ; } rail_t;

void  rail_reset(rail_t *r);
float rail_step(rail_t *r, float rail_bar, float dt_s);

#endif
