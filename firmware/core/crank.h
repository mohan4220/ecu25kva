/* 60-2 crank wheel and 1-per-cycle cam decoder.
 * Edge n after the gap sits at n*6 deg of its revolution. The revolution
 * after the one holding the cam edge is rev 0; cycle angle = rev*360 + n*6. */
#ifndef CRANK_H
#define CRANK_H

#include <stdint.h>

#define CRANK_TEETH 60
#define CRANK_TDC1_DEG 90.0f         /* calibration: cycle angle of cyl 1 firing TDC */
#define CRANK_TIMEOUT_US 50000u      /* no edge this long while synced = sync loss */
#define CRANK_WIN 6                  /* periods averaged for rpm */

enum { CRANK_F_NONE, CRANK_F_GAP, CRANK_F_TIMEOUT };

typedef struct {
    uint32_t last_us, prev_period;
    uint32_t per[CRANK_WIN];         /* last periods, us */
    uint8_t deg[CRANK_WIN];          /* their widths, deg (18 for the gap) */
    uint8_t nper, head;
    uint8_t have, count, gap_seen, synced, phased, rev, cam_pending, fault;
} crank_t;

void  crank_reset(crank_t *c);
void  crank_edge(crank_t *c, uint32_t t_us);
void  crank_cam(crank_t *c, uint32_t t_us);
void  crank_poll(crank_t *c, uint32_t t_us);
int   crank_synced(const crank_t *c);
int   crank_phased(const crank_t *c);
float crank_rpm(const crank_t *c);
float crank_angle(const crank_t *c);
float crank_next_angle(const crank_t *c);   /* unwrapped: may be 720 */
float crank_us_per_deg(const crank_t *c);
uint32_t crank_last_us(const crank_t *c);
uint8_t crank_fault(const crank_t *c);

#endif
