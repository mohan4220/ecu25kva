/* Engine-side fault diagnosis: the conditions (diag.h). Pure: no state,
 * no time; ecu.c debounces each one with deb_step. */
#include "diag.h"

/* spn, fmi, debounce ms, healing ms. Sheet: the 20 kVA DSM sheet's own
 * figure; here: chosen for this set. All calibration. */
const diag_def_t diag_def[DG_N] = {
    [DG_EGR_OPEN]       = { 2791, 5, 200, 130 },    /* sheet: 20 / 13 loops */
    [DG_EGR_STUCK_OPEN] = { 2791, 0, 1000, 200 },   /* sheet 20 loops; here 1 s */
    [DG_EGR_STUCK_SHUT] = { 2791, 7, 1000, 200 },   /* sheet FMI 31; 7 is J1939's "not responding" */
    [DG_MU_OPEN]        = { 1347, 5, 500, 0 },      /* sheet: actu_Ckt_faultDelay 500 */
    [DG_MU_OVERCUR]     = { 1347, 6, 500, 0 },
    [DG_RAIL_DEV]       = { 157, 7, 2000, 1000 },   /* here */
    [DG_SPD_HIGH]       = { 190, 16, 2000, 1000 },  /* here: the sheet gives no warning delay */
    [DG_SPD_ERRATIC]    = { 190, 8, 2000, 0 },      /* here */
    [DG_OIL_PLAUS]      = { 100, 2, 2000, 0 },      /* sheet 500 ms before cranking; here 2 s */
    [DG_BAT_HIGH]       = { 168, 16, 10000, 0 },    /* 25 kVA DSE: 10 s (the sheet's was 5 s) */
    [DG_BAT_LOW]        = { 168, 18, 10000, 0 },    /* 25 kVA DSE: 10 s */
    [DG_CLT_WARN]       = { 110, 16, 2000, 0 },     /* sheet: 602/16, 2 s */
    [DG_CLT_STOP]       = { 110, 0, 2000, 0 },      /* sheet: 110/0, 2 s */
    [DG_CLT_LEVEL]      = { 111, 18, 5000, 1000 },  /* here: 5 s, past sloshing */
};

static float absf(float x) { return x < 0 ? -x : x; }

void diag_cond(const diag_in_t *in, uint8_t c[DG_N])
{
    uint8_t bat_known = in->v_bat >= DG_BAT_MEASURED_V;
    /* the EGR checks need the engine running, the stall guard not holding
     * the bridge off, and a battery the bridge can work from (unknown
     * counts as fine: production may not measure it) */
    uint8_t egr = in->running && !in->egr_off &&
                  (!bat_known || (in->v_bat >= DG_BAT_EGR_LO && in->v_bat <= DG_BAT_EGR_HI));
    float d = absf(in->egr_duty);
    c[DG_EGR_OPEN] = egr && d > DG_EGR_DRIVE && in->i_egr_f <= DG_EGR_OPEN_A;
    c[DG_EGR_STUCK_OPEN] = egr && in->egr_pos_ok && d < DG_EGR_COAST && in->egr_pos > DG_EGR_POS_PCT;
    c[DG_EGR_STUCK_SHUT] = egr && in->egr_pos_ok && in->egr_duty >= DG_EGR_HARD
                           && in->egr_pos < DG_EGR_POS_PCT;

    /* the metering valve: only where ISNS_MU is measured */
    c[DG_MU_OPEN] = in->i_mu_valid && DG_MU_DRIVEN(in->mu_duty, in->v_bat) && in->i_mu < DG_MU_OPEN_A;
    c[DG_MU_OVERCUR] = in->i_mu_valid && in->i_mu > DG_MU_MAX_A;

    float dev = absf(in->rail_set - in->rail_bar);
    c[DG_RAIL_DEV] = in->running && in->rail_ok && dev > DG_RAIL_DEV_BAR
                     && dev > DG_RAIL_DEV_FRAC * in->rail_set;

    c[DG_SPD_HIGH] = in->running && in->rpm > DG_SPD_HIGH_RPM;
    /* the sheet's own version also fires at standstill ("Freq <= 100"):
     * here only the half that means something, oil pressure says turning */
    c[DG_SPD_ERRATIC] = in->ign_on && in->stopped && in->oil_ok && in->oil_kpa > DG_OIL_RUN_KPA;
    c[DG_OIL_PLAUS] = in->ign_on && in->stopped && in->oil_ok && in->oil_kpa > DG_OIL_STOP_KPA
                      && in->oil_kpa <= DG_OIL_RUN_KPA;

    c[DG_BAT_HIGH] = in->ign_on && bat_known
                     && in->v_bat > (in->bat_high_act ? DG_BAT_HIGH_RET_V : DG_BAT_HIGH_V);
    /* running only: cranking pulls any battery below 10 V */
    c[DG_BAT_LOW] = in->running && bat_known
                    && in->v_bat < (in->bat_low_act ? DG_BAT_LOW_RET_V : DG_BAT_LOW_V);
    /* coolant: only from a good sensor (a faulted one reads its default) */
    c[DG_CLT_WARN] = in->ign_on && in->clt_ok
                     && in->clt_c > (in->clt_warn_act ? DG_CLT_WARN_RET_C : DG_CLT_WARN_C);
    c[DG_CLT_STOP] = in->ign_on && in->clt_ok
                     && in->clt_c > (in->clt_stop_act ? DG_CLT_STOP_RET_C : DG_CLT_STOP_C);
    c[DG_CLT_LEVEL] = in->ign_on && in->clt_low;
}
