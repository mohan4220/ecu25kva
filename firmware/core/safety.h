/* Trip decision and the active-fault table that DM1 reports. */
#ifndef SAFETY_H
#define SAFETY_H

#include <stdint.h>

#define OVERSPEED_RPM 1650.0f        /* below the DSE4522's 1680 / 1710 rpm trips */
#define SPN_SPEED 190u
#define SPN_POS 636u

enum { TRIP_NONE, TRIP_OVERSPEED, TRIP_SYNC, TRIP_IGN };

typedef struct { uint32_t spn; uint8_t fmi, oc; } fault_t;
typedef struct { fault_t f[8]; uint8_t n; } faults_t;

int  safety_check(float rpm, uint8_t crank_fault, uint8_t ignition, int running);
void faults_set(faults_t *t, uint32_t spn, uint8_t fmi);
void faults_clear(faults_t *t, uint32_t spn, uint8_t fmi);

#endif
