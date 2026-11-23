/* 60-2 crank wheel and a cam decoder that learns the cam wheel.
 * Edge n after the gap sits at n*6 deg of its revolution; cycle angle =
 * rev*360 + n*6.
 *
 * The cam wheel's segment count is not known (decisions log 29, 39), so
 * the decoder does not assume one. Each crank revolution's cam edges are
 * summed up as a signature: how many, the tooth of the first and of the
 * last. Two whole revolutions whose signatures differ teach it the wheel;
 * the MARKER revolution is the one with more cam edges (with equal counts,
 * the earlier first edge, then the earlier last edge). The revolution
 * after the marker is rev 0. On a one-segment wheel that is exactly the
 * old rule: the revolution after the one holding the cam edge is rev 0.
 * On another wheel CRANK_TDC1_DEG is set at bring-up against this rule.
 *
 * A revolution that matches neither signature drops the phase. A wheel not
 * yet confirmed by a whole clean cycle is forgotten at its first miss (it
 * may have been learned from noise); a confirmed one after two misses with
 * no clean cycle between. A missed revolution is never learned from. A wheel whose two revolutions look alike
 * never phases: the engine is not injected rather than injected 360 deg
 * out. */
#ifndef CRANK_H
#define CRANK_H

#include <stdint.h>

#define CRANK_TEETH 60
#define CRANK_TDC1_DEG 90.0f         /* calibration: cycle angle of cyl 1 firing TDC */
#define CRANK_TIMEOUT_US 50000u      /* no edge this long while synced = sync loss */
#define CRANK_WIN 6                  /* periods averaged for rpm */
#define CRANK_CAM_TOL 2              /* teeth: a cam edge may move this far and still match */
#define CRANK_CAM_MISS 2             /* misses before a whole clean cycle: forget the wheel */

enum { CRANK_F_NONE, CRANK_F_GAP, CRANK_F_TIMEOUT };

typedef struct { uint8_t n, first, last; } crank_sig;   /* one revolution's cam edges */

typedef struct {
    uint32_t last_us, prev_period;
    uint32_t per[CRANK_WIN];         /* last periods, us */
    uint8_t deg[CRANK_WIN];          /* their widths, deg (18 for the gap) */
    uint8_t nper, head;
    uint8_t have, count, gap_seen, synced, phased, rev, fault, prev_gap;
    crank_sig cur, prev, mark, other;   /* this rev so far; the last whole rev; the learned wheel */
    uint8_t prev_ok, learned, proven, miss, clean;
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
