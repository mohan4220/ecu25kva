/* Trip decision and the active-fault table that DM1 reports. */
#ifndef SAFETY_H
#define SAFETY_H

#include <stdint.h>

#define OVERSPEED_RPM 1650.0f        /* below the DSE4522's 1680 / 1710 rpm trips */
#define SPN_SPEED 190u
#define SPN_POS 636u
#define SPN_CLT 110u                 /* coolant temperature: 110/0 shuts the set down (log 35) */
/* J1939 has no SPN for an injector boost rail: the first of the
 * proprietary range (520192-524287). Red, a shutdown. */
#define SPN_BOOST_RAIL 520192u
#define FMI_HIGH_SEVERE 0u           /* data valid but above normal, most severe */

/* Underspeed: a warning in DM1 (amber), never a shutdown; the DSE's own
 * under-frequency settings decide. 1350 is 90 % of 1500 and the load-step
 * scenario's own floor. Tuning knobs. */
#define UNDERSPEED_RPM 1350.0f
#define UNDERSPEED_CLEAR_RPM 1400.0f
#define UNDERSPEED_MS 3000
#define UNDERSPEED_CLEAR_MS 1000
#define FMI_LOW_MODERATE 18u

/* TRIP_STOP: pin 25, the GCU's stop / emergency switch (Bosch I_S_STST).
 * Appended, so the logged reason codes of the others do not move. */
/* TRIP_BOOST: the injector boost rail over BOOST_OV_V (12 Nov 2026). */
enum { TRIP_NONE, TRIP_OVERSPEED, TRIP_SYNC, TRIP_IGN, TRIP_STOP, TRIP_BOOST };

typedef struct { uint32_t spn; uint8_t fmi, oc; } fault_t;
#define FAULTS_MAX 16                /* active at once; DM1 carries them all (BAM) */
typedef struct { fault_t f[FAULTS_MAX]; uint8_t n; } faults_t;

int  safety_check(float rpm, uint8_t crank_fault, uint8_t ignition, int running);
void faults_set(faults_t *t, uint32_t spn, uint8_t fmi);
void faults_clear(faults_t *t, uint32_t spn, uint8_t fmi);
/* DM1's lamps for the active faults (j1939.h LAMP_*): red and Protect for
 * a shutdown -- overspeed (190/0), crank position lost (636/any), the boost
 * rail over its limit (520192/0), coolant too hot (110/0); amber for any
 * other. The DSE4522 shuts the set down only on Protect (decisions log 35,
 * 41). With ECU_MODEL: model/ecu_lamps.slx. */
uint8_t fault_lamps(const faults_t *t);

#endif
