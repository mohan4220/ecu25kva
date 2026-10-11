/* State machine and scheduling. Module state lives here, in statics:
 * one ECU per process, re-initialised by ecu_init. */
#include <string.h>
#include "ecu.h"
#include "crank.h"
#include "sensors.h"
#include "govern.h"
#include "rail.h"
#include "inject.h"
#include "safety.h"
#include "j1939.h"
#include "nvm.h"
#include "log.h"

#define RUN_RPM 400.0f               /* CRANK -> RUN once phased and above this */
#define WDG_TOGGLE_MS 5              /* WDI falling edge every 10 ms */
#define BAM_GAP_MS 50                /* J1939-21: 50-200 ms between TP.DT packets */

static crank_t crank;
static sens_t sens;
static gov_t gov;
static rail_t rail;
static faults_t faults;
static nvm_image img;                /* live: the tick updates it */
static nvm_image out;                /* sealed copy the host writes */
static uint32_t bg_ms;               /* ms at the last ecu_background */
static uint8_t save_req, save_now, saved_once, ign_prev;
static uint32_t last_save_s;
static rec_t rec;
static uint32_t ms;
static uint16_t ign_low_ms;          /* ignition low with the engine stopped */
static ecu_can bam[J1939_BAM_MAX];   /* TP.DT packets still to send */
static ecu_can tx[J1939_BAM_MAX];    /* scratch for building a response */
static uint8_t pend_dm2, pend_dm4, pend_hours;
static uint8_t bam_n, bam_i;
static uint8_t bam_wait;             /* ms to the next TP.DT */

static void event(ecu_io *io, uint8_t code, uint16_t arg)
{
    log_event(&img, img.c.ecu_s, code, arg, (uint16_t)io->rpm);
}

static int fault_active(uint32_t spn, uint8_t fmi)
{
    for (int i = 0; i < faults.n; i++)
        if (faults.f[i].spn == spn && faults.f[i].fmi == fmi)
            return 1;
    return 0;
}

/* Every fault goes through these two: the active table (DM1) and the
 * stored history (DTC memory) never disagree. */
static void fault_raise(ecu_io *io, uint32_t spn, uint8_t fmi)
{
    if (fault_active(spn, fmi))
        return;
    faults_set(&faults, spn, fmi);
    log_snap s = { io->rpm, io->fuel_mg / FUEL_RATED_MG, io->fuel_mg, sens.val[S_RAIL],
                   sens.val[S_CLT], sens.val[S_OIL], io->v_bat, io->state };
    if (log_dtc_set(&img, spn, fmi, img.c.ecu_s, &s))
        save_req = 1;
    event(io, EV_DTC_SET, (uint16_t)spn);
}

static void fault_drop(ecu_io *io, uint32_t spn, uint8_t fmi)
{
    if (!fault_active(spn, fmi))
        return;
    faults_clear(&faults, spn, fmi);
    log_dtc_inactive(&img, spn, fmi);
    event(io, EV_DTC_CLEAR, (uint16_t)spn);
}

static int queue(ecu_io *io, const ecu_can *f)
{
    if (io->can_n < ECU_CANQ) {
        io->can[io->can_n++] = *f;
        return 1;
    }
    io->can_drops++;
    return 0;
}

/* Back to OFF with every module fresh. Injection seq numbers survive so
 * the host never sees a repeated seq as "no new command". */
static void reset_all(ecu_io *io)
{
    crank_reset(&crank);
    sens_reset(&sens);
    gov_reset(&gov, 0, 0);
    rail_reset(&rail);
    memset(&faults, 0, sizeof faults);
    log_dtc_all_inactive(&img);         /* the latch clears; the history stays */
    ign_low_ms = 0;
    bam_n = bam_i = 0;
    pend_dm2 = pend_dm4 = pend_hours = 0;
    inject_cancel(io->inj);
    io->meter_duty = METER_CLOSED;
    io->state = ECU_OFF;
    io->fault_n = io->synced = 0;
    io->rpm = io->fuel_mg = 0;
}

void ecu_init(ecu_io *io)
{
    memset(io->inj, 0, sizeof io->inj);
    io->wdg = 0;
    io->can_n = 0;
    io->can_drops = 0;
    io->nvm_save = io->nvm_slot = 0;
    ms = bg_ms = 0;
    save_req = save_now = saved_once = ign_prev = 0;
    rec_reset(&rec);
    reset_all(io);
}

/* Latch SHUTDOWN. Called again while already shut down, it still records
 * the fault (an engine that overspeeds after an ignition-off stop). */
static void trip(ecu_io *io, int why)
{
    if (why == TRIP_OVERSPEED)
        fault_raise(io, SPN_SPEED, 0);
    else if (why == TRIP_SYNC)
        fault_raise(io, SPN_POS, 2);
    if (io->state != ECU_SHUTDOWN) {     /* count and log the transition, once */
        event(io, EV_SHUTDOWN, (uint16_t)why);
        if (why == TRIP_OVERSPEED)
            img.c.trips_overspeed++;
        else if (why == TRIP_SYNC)
            img.c.trips_sync++;
        if (why == TRIP_OVERSPEED || why == TRIP_SYNC)   /* not normal stops: they would */
            rec_trigger(&rec, &img, img.c.ecu_s, (uint8_t)why);  /* overwrite real trips */
        save_req = 1;
    }
    io->state = ECU_SHUTDOWN;
    inject_cancel(io->inj);
    io->meter_duty = METER_CLOSED;
}

static void check(ecu_io *io, float rpm)
{
    int why = safety_check(rpm, crank_fault(&crank), io->ignition, io->state == ECU_RUN);
    if (why != TRIP_NONE && !(why == TRIP_IGN && io->state == ECU_SHUTDOWN))
        trip(io, why);
}

void ecu_crank_edge(ecu_io *io, uint32_t t_us)
{
    if (io->state == ECU_OFF)
        return;
    if (io->state == ECU_WAIT) {
        io->state = ECU_CRANK;
        event(io, EV_CRANK, 0);
    }
    uint8_t fault_before = crank_fault(&crank);
    crank_edge(&crank, t_us);
    /* a fault raised by this very edge (a lost or extra tooth) also skews
     * this edge's rpm: diagnose it as the sensor, not as overspeed */
    int fresh = !fault_before && crank_fault(&crank) && io->state == ECU_RUN;
    if (fresh)
        trip(io, TRIP_SYNC);
    if (crank_fault(&crank) && io->state == ECU_CRANK) {
        crank_reset(&crank);            /* not yet running: just resync */
        crank_edge(&crank, t_us);
    }
    float rpm = crank_rpm(&crank);
    io->rpm = rpm;
    io->synced = (uint8_t)crank_synced(&crank);
    if (!fresh)                         /* this edge's rpm is not to be trusted */
        check(io, rpm);

    if (io->state == ECU_CRANK && crank_phased(&crank) && rpm >= RUN_RPM) {
        io->state = ECU_RUN;
        gov_reset(&gov, FUEL_START_MG, rpm);
        img.c.starts++;
        event(io, EV_RUN, 0);
        save_req = 1;
    }
    if ((io->state == ECU_CRANK || io->state == ECU_RUN) && crank_phased(&crank)) {
        float fuel = io->state == ECU_RUN ? gov.fuel : FUEL_START_MG;
        inject_edge(&crank, fuel, sens.val[S_RAIL], io->inj);
    }
}

void ecu_cam_edge(ecu_io *io, uint32_t t_us)
{
    if (io->state != ECU_OFF)
        crank_cam(&crank, t_us);
}

static void mirror_sensor_faults(ecu_io *io)
{
    for (int i = 0; i < S_N; i++) {
        for (uint8_t fmi = 3; fmi <= 4; fmi++)
            if (sens.fmi[i] != fmi)
                fault_drop(io, sens_spn[i], fmi);
        if (sens.fmi[i])
            fault_raise(io, sens_spn[i], sens.fmi[i]);
    }
}

static uint8_t lamps(void)
{
    uint8_t l = 0;
    for (int i = 0; i < faults.n; i++)
        l |= (faults.f[i].spn == SPN_SPEED || faults.f[i].spn == SPN_POS) ? LAMP_RED : LAMP_AMBER;
    return l;
}

/* Send frames built by j1939_tp: a single frame at once; a BAM's TP.CM
 * now and its TP.DT packets BAM_GAP_MS apart. One BAM at a time
 * (J1939-21); returns 0 if one is already in flight. */
static int send_tp(ecu_io *io, const ecu_can *f, int n)
{
    if (n <= 0)
        return 1;
    if (n > 1 && bam_i < bam_n)
        return 0;
    int sent = queue(io, &f[0]);
    if (n > 1 && sent) {                /* no TP.CM, no TP.DT: never half a message */
        memcpy(bam, &f[1], (size_t)(n - 1) * sizeof bam[0]);
        bam_n = (uint8_t)(n - 1);
        bam_i = 0;
        bam_wait = BAM_GAP_MS;
    }
    return 1;
}

static void send_can(ecu_io *io)
{
    ecu_can f;
    if (ms % 20 == 0) {
        j1939_eec1(&f, io->rpm);
        queue(io, &f);
    }
    if (ms % 500 == 0) {
        j1939_eflp1(&f, sens.val[S_OIL], !sens.fmi[S_OIL]);
        queue(io, &f);
    }
    if (ms % 1000 == 0) {
        j1939_et1(&f, sens.val[S_CLT], !sens.fmi[S_CLT]);
        queue(io, &f);
        send_tp(io, tx, j1939_dm1(tx, J1939_BAM_MAX, &faults, lamps()));
    }
    if (ms % 10000 == 0 || pend_hours) {   /* HOURS: on request, and every 10 s (U4) */
        j1939_hours(&f, img.c.engine_s);
        queue(io, &f);
        pend_hours = 0;
    }
    if (pend_dm2 && send_tp(io, tx, j1939_dm2(tx, J1939_BAM_MAX, &img)))
        pend_dm2 = 0;
    if (pend_dm4 && send_tp(io, tx, j1939_dm4(tx, J1939_BAM_MAX, &img)))
        pend_dm4 = 0;
    if (bam_i < bam_n && --bam_wait == 0) {
        queue(io, &bam[bam_i++]);
        bam_wait = BAM_GAP_MS;
    }
}

void ecu_can_rx(ecu_io *io, const ecu_can *f)
{
    switch (j1939_request_pgn(f, J1939_SA)) {
    case PGN_DM2: pend_dm2 = 1; break;
    case PGN_DM4: pend_dm4 = 1; break;
    case PGN_HOURS: pend_hours = 1; break;
    case PGN_DM3:
        /* ponytail: no J1939-21 ACK; add one if U4 shows the DSE waits for it */
        event(io, EV_DM3_CLEAR, (uint16_t)log_dm3_clear(&img));
        save_req = 1;
        break;
    default: break;
    }
}

void ecu_tick_1ms(ecu_io *io, uint32_t t_us)
{
    if (++ms >= ECU_MS_WRAP)
        ms = 0;
    /* kick only while the main loop is alive: a hung loop under live
     * interrupts must stop the kicks so the supervisor resets the MCU */
    if (ms % WDG_TOGGLE_MS == 0 && (ms + ECU_MS_WRAP - bg_ms) % ECU_MS_WRAP < ECU_BG_MS)
        io->wdg ^= 1;
    if (ms % 1000 == 0 && log_second(&img, io->state == ECU_RUN, io->fuel_mg / FUEL_RATED_MG))
        save_req = 1;
    if (ign_prev && !io->ignition)
        event(io, EV_IGN_OFF, 0);
    ign_prev = io->ignition;

    /* rpm decays to 0 once edges stop, rather than holding the last value.
     * Signed: an edge interrupt may stamp a time just after this tick's. */
    float rpm = crank.have && (int32_t)(t_us - crank_last_us(&crank)) <= (int32_t)CRANK_TIMEOUT_US
                    ? crank_rpm(&crank) : 0;

    if (io->state == ECU_SHUTDOWN) {
        /* the latch clears only on a real ignition cycle: low for IGN_OFF_MS
         * with the engine stopped, then high. A contact bounce does nothing. */
        if (io->ignition) {
            if (ign_low_ms >= IGN_OFF_MS)
                reset_all(io);
            ign_low_ms = 0;
        } else {
            ign_low_ms = rpm == 0 ? (uint16_t)(ign_low_ms + (ign_low_ms < IGN_OFF_MS)) : 0;
        }
    }
    if (io->state == ECU_OFF) {
        if (!io->ignition)
            return;
        io->state = ECU_WAIT;
        event(io, EV_IGN_ON, 0);
    }

    crank_poll(&crank, t_us);
    const float v[S_N] = { io->v_clt, io->v_oil, io->v_rail, io->v_boost, io->v_egr };
    sens_step_1ms(&sens, v, io->v_5v);
    mirror_sensor_faults(io);

    io->rpm = rpm;
    check(io, rpm);

    if (io->state == ECU_RUN)
        gov_step(&gov, rpm, io->droop_sw, 0.001f);
    if (io->state == ECU_CRANK || io->state == ECU_RUN)
        io->meter_duty = sens.fmi[S_RAIL] ? RAIL_DUTY_LIMP : rail_step(&rail, sens.val[S_RAIL], 0.001f);
    else
        io->meter_duty = METER_CLOSED;

    send_can(io);

    if (ms % 20 == 0) {
        rec_sample x = { (uint16_t)(io->rpm + 0.5f), (uint8_t)(io->fuel_mg / 0.25f + 0.5f),
                         io->state, (uint16_t)(sens.val[S_RAIL] + 0.5f) };
        if (rec_push(&rec, &img, x))
            save_now = 1;               /* a finished trip recording saves at once */
    }

    io->fuel_mg = io->state == ECU_RUN ? gov.fuel : io->state == ECU_CRANK ? FUEL_START_MG : 0;
    io->rail_bar = sens.val[S_RAIL];
    io->clt_c = sens.val[S_CLT];
    io->oil_kpa = sens.val[S_OIL];
    io->fault_n = faults.n;
    io->synced = (uint8_t)crank_synced(&crank);
}

size_t ecu_io_size(void) { return sizeof(ecu_io); }

void ecu_nvm_load(ecu_io *io, const void *slot_a, const void *slot_b, uint32_t len)
{
    int pick = nvm_pick(slot_a, slot_b, len);
    if (pick < 0) {
        nvm_fresh(&img);
        event(io, EV_NVM_RESET, 0);
    } else {
        memcpy(&img, pick ? slot_b : slot_a, sizeof img);
        log_dtc_all_inactive(&img);     /* after power-up nothing is active until seen again */
    }
    if (io->reset_cause == 1)
        img.c.wdg_resets++;
    event(io, EV_POWER_ON, io->reset_cause);
    out = img;
}

const void *ecu_nvm_live(void) { return &img; }

void ecu_background(ecu_io *io)
{
    bg_ms = ms;
    if (io->nvm_save)                   /* the host has not finished the last write */
        return;
    /* strict: whole seconds, so ">" is what guarantees at least SAVE_GAP_S */
    int due = save_now || (save_req && (!saved_once || img.c.ecu_s - last_save_s > SAVE_GAP_S));
    if (!due)
        return;
    /* ponytail: on the S32K148 this copy needs the tick masked; on the PC nothing preempts it */
    out = img;
    nvm_seal(&out);
    img.h.seq = out.h.seq;
    io->nvm_slot = (uint8_t)(out.h.seq & 1);
    io->nvm_save = 1;
    save_req = save_now = 0;
    saved_once = 1;
    last_save_s = img.c.ecu_s;
}

const void *ecu_nvm_image(uint32_t *len)
{
    *len = sizeof out;
    return &out;
}
