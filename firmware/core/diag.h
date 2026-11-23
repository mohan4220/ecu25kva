/* Engine-side fault diagnosis (decisions log 24).
 *
 * Taken from the 20 kVA set's DSM sheet (docs/research/dsm-20kva.md) and
 * adapted to this set: the 20 kVA engine has a fuel rack, this one a
 * common rail, so its rack faults become the metering valve's and the
 * rail's. Standard J1939 codes throughout, so the DSE4522 shows the right
 * text. Everything here is AMBER: a warning, the engine keeps running;
 * the shutdowns stay where they were (overspeed, sync, boost, stop) and
 * the DSE keeps oil, coolant, fuel level, charging and crank attempts.
 *
 * Every number below is FROM THE 20 KVA SHEET OR CHOSEN HERE, not yet
 * confirmed on the 25 kVA engine: calibration, to be checked on the bench.
 * The sheet counts its EGR debounces in task loops; they are read here as
 * a 10 ms loop, and the valve-stuck ones lengthened to 1 s (a spring
 * return takes longer than 200 ms).
 *
 * diag_cond is pure: it turns one tick's measurements into one condition
 * per fault. ecu.c steps a debounce (mode.h deb_step) per fault and
 * raises or drops the DTC. */
#ifndef DIAG_H
#define DIAG_H

#include <stdint.h>

enum {
    DG_EGR_OPEN,        /* 2791/5   bridge driven, no current: open load */
    DG_EGR_STUCK_OPEN,  /* 2791/0   coasting, the valve still open */
    DG_EGR_STUCK_SHUT,  /* 2791/7   driven open hard, the valve still shut */
    DG_MU_OPEN,         /* 1347/5   metering valve driven, no coil current */
    DG_MU_OVERCUR,      /* 1347/6   metering valve coil over current */
    DG_RAIL_DEV,        /* 157/7    rail pressure not following its target */
    DG_SPD_HIGH,        /* 190/16   speed high: the warning below the trip */
    DG_SPD_ERRATIC,     /* 190/8    oil pressure says turning, no crank teeth */
    DG_OIL_PLAUS,       /* 100/2    oil pressure with the engine stopped */
    DG_BAT_HIGH,        /* 168/16   battery high */
    DG_BAT_LOW,         /* 168/18   battery low while running: charging lost */
    DG_CLT_WARN,        /* 110/16   coolant hot: warning (decisions log 35) */
    DG_CLT_STOP,        /* 110/0    coolant too hot: red + Protect, the DSE shuts down */
    DG_CLT_LEVEL,       /* 111/18   coolant level low (pin 43) */
    DG_N
};

typedef struct { uint32_t spn; uint8_t fmi; uint16_t deb_ms, heal_ms; } diag_def_t;
extern const diag_def_t diag_def[DG_N];

/* thresholds (20 kVA sheet unless marked "here" or "25 kVA"; decisions log 35) */
#define DG_EGR_DRIVE 0.20f           /* |duty| above: driven (CAL_EGR_Open_PWM_Th 20 %) */
#define DG_EGR_OPEN_A 0.10f          /* filtered current at or below: open (0.1 A) */
#define DG_EGR_I_ALPHA 0.05f         /* here: current filter per 1 ms, tau 20 ms over the PWM */
#define DG_EGR_COAST 0.05f           /* |duty| below: commanded shut (stuck_abv_PWM 5 %) */
#define DG_EGR_HARD 0.90f            /* duty at or above: driven open hard (95 % on the 20 kVA;
                                      * here 90 %, as this bridge stops at EGR_DUTY_MAX 0.95) */
#define DG_EGR_POS_PCT 35.0f         /* EGR_stuck_Pos_thres 35 % */
#define DG_BAT_EGR_LO 10.0f          /* EGR diagnosed only inside 10..15 V (EGR_loBatt/High_batt) */
#define DG_BAT_EGR_HI 15.0f
#define DG_MU_EXPECT_A 0.25f         /* here: the coil must carry current once even the highest
                                      * coil (MU_R_HI) would draw this at the duty and battery:
                                      * a fixed 20 % duty missed a cold 1.85 ohm coil, which
                                      * runs a loaded set at 15 % (decisions log 34) */
#define DG_MU_R_HI 6.91f             /* = MU_R_HI (actuate.h): 5 ohm at +125 C */
#define DG_MU_DRIVEN(duty, vb) ((duty) * (vb) / DG_MU_R_HI > DG_MU_EXPECT_A)
#define DG_MU_OPEN_A 0.05f           /* here: at most this with the coil driven: open */
#define DG_MU_MAX_A 3.0f             /* here: above anything legitimate -- the loop holds at most
                                      * 1.8 A (closed); under ISNS_MU's 3.3 A range. Feedforward
                                      * alone runs only once the measurement is distrusted, and
                                      * then the cold low coil can reach 1.8*3.75/1.85 = 3.65 A */
#define DG_RAIL_DEV_BAR 150.0f       /* here: off target by more than this ... */
#define DG_RAIL_DEV_FRAC 0.25f       /* ... and this fraction of the target */
#define DG_SPD_HIGH_RPM 1590.0f      /* high_speed_warning_limit 1590 */
#define DG_OIL_RUN_KPA 200.0f        /* LOP_lower_limit 200: an engine turning makes this */
#define DG_OIL_STOP_KPA 100.0f       /* preCrankLOP_lim 100 */
/* Battery: THE 25 kVA SET'S OWN DSE4522 settings (refs/GP3.314.01.0.PR-
 * DSE4522-config.pdf, "Plant Battery"; decisions log 35), which replace
 * the 20 kVA sheet's 14.8 / 11.9 V: warning above 15.0 V, back below
 * 14.5; warning below 9.5 V, back above 10.0; 10 s delay each. */
#define DG_BAT_HIGH_V 15.0f
#define DG_BAT_HIGH_RET_V 14.5f
#define DG_BAT_LOW_V 9.5f
#define DG_BAT_LOW_RET_V 10.0f
#define DG_BAT_MEASURED_V 1.0f       /* here: v_bat below this is "not measured" */
/* Coolant (decisions log 35). The 25 kVA set's DSE has its coolant alarms
 * at 150 / 200 degC, so it never acts: the engine relies on the ECU's
 * Protect lamp, on which the DSE shuts down. Limits: KOEL's, from the 20
 * kVA sheet (602/16 100 degC, 110/0 104 degC), chosen by the owner for
 * the 25 kVA on 23 Nov 2026 until its own are known. Returns 2 degC
 * below, so a reading on the line does not chatter. */
#define DG_CLT_WARN_C 100.0f
#define DG_CLT_WARN_RET_C 98.0f
#define DG_CLT_STOP_C 104.0f
#define DG_CLT_STOP_RET_C 102.0f

typedef struct {
    uint8_t running;                 /* state RUN */
    uint8_t ign_on;                  /* any state but OFF */
    uint8_t stopped;                 /* no crank tooth for ECU_STOPPED_MS */
    float rpm, v_bat;
    /* EGR */
    float egr_duty, i_egr_f, egr_pos; /* duty -1..1, filtered A, % open */
    uint8_t egr_pos_ok, egr_off;     /* position sensor good; the stall guard holds it off */
    /* metering valve and rail */
    float mu_duty, i_mu;             /* the coil's duty (energised fraction) and current */
    uint8_t i_mu_valid;
    float rail_set, rail_bar;
    uint8_t rail_ok;                 /* rail sensor good */
    /* oil */
    float oil_kpa;
    uint8_t oil_ok;
    /* battery faults already active: their return levels apply */
    uint8_t bat_high_act, bat_low_act;
    /* coolant: temperature (pin 33) and the level switch (pin 43) */
    float clt_c;
    uint8_t clt_ok, clt_low, clt_warn_act, clt_stop_act;
} diag_in_t;

void diag_cond(const diag_in_t *in, uint8_t cond[DG_N]);

#endif
