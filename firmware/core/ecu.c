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
#include "eol.h"
#include "service.h"
#include "isotp.h"
#include "link.h"

#define SPN_PROGRAM 628u             /* program memory */
#define FMI_CALIBRATION 13u          /* out of calibration: no end-of-line record */

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
static uint8_t save_req, save_now, saved_once;
static uint16_t ign_off_ms;          /* ignition low this long: a real ignition-off */
static uint32_t last_save_s;
static rec_t rec;
static uint32_t ms;
static uint16_t ign_low_ms;          /* ignition low with the engine stopped */
static ecu_can bam[J1939_BAM_MAX];   /* TP.DT packets still to send */
static ecu_can tx[J1939_BAM_MAX];    /* scratch for building a response */
static uint8_t pend_dm1, pend_dm2, pend_dm4, pend_hours;
static uint8_t bam_n, bam_i;
static uint8_t bam_wait;             /* ms to the next TP.DT */
static uint16_t under_ms, over_ms;   /* underspeed: ms below its floor, ms back above */
/* the service link: one UDS core behind USB framing and CAN channel 2 */
static svc_t svc;
static eol_record eol;               /* the working record; ecu_eol_image hands it out */
static uint8_t eol_ok;               /* a good record was loaded or written */
static isotp_t can2;
static link_rx_t usb_rx;
static uint8_t svc_req[ISOTP_MAX], svc_rsp[SVC_RESP_MAX];
static uint8_t stopped;              /* engine stopped, as the service link means it */
static uint32_t now_us;              /* the last tick's time */

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
    int r = log_dtc_set(&img, spn, fmi, img.c.ecu_s, &s);
    if (r == 1)
        save_req = 1;
    if (r)
        event(io, EV_DTC_SET, (uint16_t)spn);
}

static void fault_drop(ecu_io *io, uint32_t spn, uint8_t fmi)
{
    if (!fault_active(spn, fmi))
        return;
    faults_clear(&faults, spn, fmi);
    if (log_dtc_inactive(&img, spn, fmi))
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
    under_ms = over_ms = 0;
    bam_n = bam_i = 0;
    pend_dm1 = pend_dm2 = pend_dm4 = pend_hours = 0;
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
    save_req = save_now = saved_once = 0;
    svc_init(&svc, 0);
    isotp_init(&can2, ECU_CAN2_RESP);
    memset(&usb_rx, 0, sizeof usb_rx);
    eol_default(&eol);                  /* until ecu_eol_load: SPN 628 */
    eol_ok = 0;
    sens_trim(eol.gain, eol.offset);
    stopped = 1;
    now_us = 0;
    io->usb_in_n = 0;
    io->usb_out_n = 0;
    io->can2_n = 0;
    io->eol_save = io->boot_req = io->reset_req = 0;
    io->session = SES_DEFAULT;
    ign_off_ms = 0;
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

/* Armed in RUN once the setpoint ramp from the start has finished. A
 * warning only: the engine keeps governing (spec: the DSE decides). */
static void underspeed(ecu_io *io, float rpm)
{
    int armed = io->state == ECU_RUN && gov.set >= gov_setpoint(gov.fuel, io->droop_sw) - 1.0f;
    if (!armed) {
        under_ms = over_ms = 0;
        fault_drop(io, SPN_SPEED, FMI_LOW_MODERATE);
        return;
    }
    under_ms = rpm < UNDERSPEED_RPM ? (uint16_t)(under_ms + (under_ms < UNDERSPEED_MS)) : 0;
    over_ms = rpm > UNDERSPEED_CLEAR_RPM ? (uint16_t)(over_ms + (over_ms < UNDERSPEED_CLEAR_MS)) : 0;
    if (under_ms >= UNDERSPEED_MS)
        fault_raise(io, SPN_SPEED, FMI_LOW_MODERATE);
    else if (over_ms >= UNDERSPEED_CLEAR_MS)
        fault_drop(io, SPN_SPEED, FMI_LOW_MODERATE);
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
        l |= ((faults.f[i].spn == SPN_SPEED && faults.f[i].fmi != FMI_LOW_MODERATE)
              || faults.f[i].spn == SPN_POS)
             ? LAMP_RED | LAMP_PROTECT        /* shutdown: the DSE stops only on Protect */
             : LAMP_AMBER;
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
        pend_dm1 = 1;
    }
    if (ms % 10000 == 0 || pend_hours) {   /* HOURS: on request, and every 10 s (U4) */
        j1939_hours(&f, img.c.engine_s);
        queue(io, &f);
        pend_hours = 0;
    }
    /* DM1 first: a tool polling DM2/DM4 must never starve the controller of faults */
    if (pend_dm1 && send_tp(io, tx, j1939_dm1(tx, J1939_BAM_MAX, &faults, lamps())))
        pend_dm1 = 0;
    if (!pend_dm1 && pend_dm2 && send_tp(io, tx, j1939_dm2(tx, J1939_BAM_MAX, &img)))
        pend_dm2 = 0;
    if (!pend_dm1 && pend_dm4 && send_tp(io, tx, j1939_dm4(tx, J1939_BAM_MAX, &img)))
        pend_dm4 = 0;
    if (bam_i < bam_n && --bam_wait == 0) {
        if (queue(io, &bam[bam_i])) {   /* a full queue retries next ms: no packet lost */
            bam_i++;
            bam_wait = BAM_GAP_MS;
        } else {
            bam_wait = 1;
        }
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

/* ---- the service link ---- */

static void pump_can2(ecu_io *io)
{
    ecu_can f;
    while (io->can2_n < ECU_CANQ && isotp_next(&can2, &f))
        io->can2[io->can2_n++] = f;
}

static void put16(uint8_t *p, uint32_t v) { p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v; }

static uint16_t eol_changed(ecu_io *io, uint16_t n)
{
    eol_seal(&eol);
    eol_ok = (uint8_t)eol_valid(&eol);
    if (eol_ok)
        fault_drop(io, SPN_PROGRAM, FMI_CALIBRATION);
    sens_trim(eol.gain, eol.offset);
    io->eol_save = 1;
    return n;
}

static uint16_t read_id(ecu_io *io, uint16_t id, uint8_t *r)
{
    uint8_t *d = r + 3;
    switch (id) {
    case 0xF18C: memcpy(d, eol.serial, 16); return 16;
    case 0xF191: put16(d, eol.hw_rev); return 2;
    case 0xF18B: put16(d, eol.build_date >> 16); put16(d + 2, eol.build_date); return 4;
    case 0xF195: put16(d, ECU_SW_VERSION); return 2;
    case 0xF180: put16(d, io->boot_ver); return 2;
    case 0x0100: memcpy(d, eol.gain, 24); memcpy(d + 24, eol.offset, 24); return 48;   /* LE floats */
    case 0x0101: d[0] = eol.station; d[1] = eol.passed; d[2] = eol.locked; return 3;
    default: return 0;
    }
}

/* Writes and routines: extended session, unlocked, engine stopped. */
static uint8_t may_change(const svc_t *s)
{
    return s->session != SES_EXTENDED ? NRC_SESSION : !s->unlocked ? NRC_SECURITY
         : !s->stopped ? NRC_CONDITIONS : 0;
}

static uint16_t write_id(ecu_io *io, const uint8_t *q, uint16_t n, uint8_t *r)
{
    uint16_t id = (uint16_t)(q[1] << 8 | q[2]);
    const uint8_t *d = q + 3;
    uint16_t m = (uint16_t)(n - 3);
    if (eol.locked)
        return svc_nrc(r, 0x2E, NRC_CONDITIONS);
    switch (id) {
    case 0xF18C:
        if (m < 1 || m > 16)
            return svc_nrc(r, 0x2E, NRC_LENGTH);
        memset(eol.serial, 0, 16);
        memcpy(eol.serial, d, m);
        break;
    case 0xF191:
        if (m != 2)
            return svc_nrc(r, 0x2E, NRC_LENGTH);
        eol.hw_rev = (uint16_t)(d[0] << 8 | d[1]);
        break;
    case 0xF18B:
        if (m != 4)
            return svc_nrc(r, 0x2E, NRC_LENGTH);
        eol.build_date = (uint32_t)d[0] << 24 | (uint32_t)d[1] << 16 | (uint32_t)d[2] << 8 | d[3];
        break;
    case 0x0100: {
        float g[EOL_N], o[EOL_N];
        if (m != 48)
            return svc_nrc(r, 0x2E, NRC_LENGTH);
        memcpy(g, d, 24);
        memcpy(o, d + 24, 24);
        if (!eol_trims_ok(g, o))
            return svc_nrc(r, 0x2E, NRC_RANGE);
        memcpy(eol.gain, g, 24);
        memcpy(eol.offset, o, 24);
        break;
    }
    case 0x0101:                        /* station, passed; the lock is a routine */
        if (m != 2)
            return svc_nrc(r, 0x2E, NRC_LENGTH);
        eol.station = d[0];
        eol.passed = d[1] != 0;
        break;
    default:
        return svc_nrc(r, 0x2E, NRC_RANGE);
    }
    r[0] = 0x6E;
    r[1] = q[1];
    r[2] = q[2];
    return eol_changed(io, 3);
}

static uint16_t app_extra(svc_t *s, const uint8_t *q, uint16_t n, uint8_t *r)
{
    ecu_io *io = s->ctx;
    uint8_t why;
    switch (q[0]) {
    case 0x22: {                        /* readable in any session, engine running too */
        if (n != 3)
            return svc_nrc(r, 0x22, NRC_LENGTH);
        uint16_t m = read_id(io, (uint16_t)(q[1] << 8 | q[2]), r);
        if (!m)
            return svc_nrc(r, 0x22, NRC_RANGE);
        r[0] = 0x62;
        r[1] = q[1];
        r[2] = q[2];
        return (uint16_t)(m + 3);
    }
    case 0x2E:
        if (n < 4)
            return svc_nrc(r, 0x2E, NRC_LENGTH);
        if ((why = may_change(s)))
            return svc_nrc(r, 0x2E, why);
        return write_id(io, q, n, r);
    case 0x31: {
        if (n != 4)
            return svc_nrc(r, 0x31, NRC_LENGTH);
        if (q[1] != 0x01)
            return svc_nrc(r, 0x31, NRC_SUBFUNC);
        uint16_t id = (uint16_t)(q[2] << 8 | q[3]);
        if (id != 0xF000 && id != 0xF001)
            return svc_nrc(r, 0x31, NRC_RANGE);
        if ((why = may_change(s)))
            return svc_nrc(r, 0x31, why);
        eol.locked = id == 0xF000;
        if (id == 0xF001)
            event(io, EV_EOL_UNLOCK, 0);    /* a rework: on record */
        memcpy(r, (const uint8_t[]){ 0x71, 0x01, q[2], q[3] }, 4);
        return eol_changed(io, 4);
    }
    default:
        return svc_nrc(r, q[0], NRC_NOT_SUPPORTED);
    }
}

static uint16_t serve(ecu_io *io, const uint8_t *q, uint16_t n)
{
    svc.ctx = io;
    uint16_t m = svc_handle(&svc, q, n, svc_rsp, ms, now_us, stopped, app_extra);
    if (svc.prog_req)
        io->boot_req = 1;
    if (svc.reset_req)
        io->reset_req = 1;
    svc.prog_req = svc.reset_req = 0;
    io->session = svc.session;
    return m;
}

void ecu_can2_rx(ecu_io *io, const ecu_can *f)
{
    uint16_t n;
    if (f->id != ECU_CAN2_REQ)
        return;
    if (isotp_rx(&can2, f, svc_req, &n)) {
        uint16_t m = serve(io, svc_req, n);
        if (m)
            isotp_send(&can2, svc_rsp, m);
    }
    pump_can2(io);
}

static void usb_poll(ecu_io *io)
{
    uint16_t n;
    for (uint8_t i = 0; i < io->usb_in_n; i++) {
        if (!link_feed(&usb_rx, io->usb_in[i], svc_req, &n))
            continue;
        uint16_t m = serve(io, svc_req, n);
        if (m && io->usb_out_n + m + 5u <= ECU_USB_OUT)   /* else the tester retries */
            io->usb_out_n = (uint16_t)(io->usb_out_n + link_frame(svc_rsp, m, io->usb_out + io->usb_out_n));
    }
    io->usb_in_n = 0;
}

void ecu_eol_load(ecu_io *io, const void *a, const void *b)
{
    (void)io;
    int pick = eol_pick(a, b);
    if (pick < 0) {
        eol_default(&eol);
        eol_ok = 0;
    } else {
        memcpy(&eol, pick ? b : a, sizeof eol);
        eol_ok = 1;
    }
    sens_trim(eol.gain, eol.offset);
}

const void *ecu_eol_image(uint32_t *len)
{
    *len = sizeof eol;
    return &eol;
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
    /* debounced: a bouncing contact must not flood the event log */
    if (io->ignition)
        ign_off_ms = 0;
    else if (ign_off_ms < IGN_OFF_MS && ++ign_off_ms == IGN_OFF_MS)
        event(io, EV_IGN_OFF, 0);

    /* rpm decays to 0 once edges stop, rather than holding the last value.
     * Signed: an edge interrupt may stamp a time just after this tick's. */
    float rpm = crank.have && (int32_t)(t_us - crank_last_us(&crank)) <= (int32_t)CRANK_TIMEOUT_US
                    ? crank_rpm(&crank) : 0;

    now_us = t_us;
    stopped = (io->state == ECU_OFF || io->state == ECU_WAIT || io->state == ECU_SHUTDOWN)
              && (!crank.have || (int32_t)(t_us - crank_last_us(&crank)) > ECU_STOPPED_MS * 1000);
    svc_tick(&svc, ms, stopped);
    io->session = svc.session;
    pump_can2(io);

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

    if (!eol_ok)
        fault_raise(io, SPN_PROGRAM, FMI_CALIBRATION);
    crank_poll(&crank, t_us);
    const float v[S_N] = { io->v_clt, io->v_oil, io->v_rail, io->v_boost, io->v_egr };
    sens_step_1ms(&sens, v, io->v_5v);
    mirror_sensor_faults(io);

    io->rpm = rpm;
    check(io, rpm);
    underspeed(io, rpm);

    if (io->state == ECU_RUN)
        gov_step(&gov, rpm, io->droop_sw, 0.001f);
    if (io->state == ECU_CRANK || io->state == ECU_RUN)
        io->meter_duty = sens.fmi[S_RAIL] ? RAIL_DUTY_LIMP
            : rail_step(&rail, rail_set_bar(io->state == ECU_RUN ? gov.fuel : FUEL_START_MG),
                        sens.val[S_RAIL], 0.001f);
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
    if (io->reset_cause == 1) {
        /* a hang is the evidence most worth keeping: save it, but through
         * the rate limit, so a boot loop cannot wear the flash out */
        img.c.wdg_resets++;
        save_req = saved_once = 1;
        last_save_s = img.c.ecu_s;
    }
    event(io, EV_POWER_ON, io->reset_cause);
    out = img;
}

const void *ecu_nvm_live(void) { return &img; }

void ecu_background(ecu_io *io)
{
    bg_ms = ms;
    usb_poll(io);
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
