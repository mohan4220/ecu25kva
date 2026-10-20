/* The service link's UDS (ISO 14229) core, shared by the application
 * and the bootloader: sessions, seed-key security, tester present, ECU
 * reset. Everything else goes to the caller's `extra` handler.
 * Not proof against a determined attacker (spec 2026-10-17 sec. 12). */
#ifndef SERVICE_H
#define SERVICE_H

#include <stdint.h>

/* The owner keeps the same 16 bytes in a file for the laptop tool.
 * Override per build with -DSEC_SECRET_BYTES=... */
#ifndef SEC_SECRET_BYTES
#define SEC_SECRET_BYTES 'E', 'C', 'U', '2', '5', 'K', 'V', 'A', \
                         '-', 's', 'e', 'r', 'v', 'i', 'c', 'e'
#endif
#define SEC_SECRET { SEC_SECRET_BYTES }

#define SVC_SESSION_MS 5000u            /* a non-default session ends this long after a message */
#define SVC_LOCK_MS 10000u              /* three wrong keys lock security access this long */
#define SVC_TRIES 3
#define SVC_RESP_MAX 64                 /* every response fits; callers' buffers are this big */

enum { SES_DEFAULT = 1, SES_PROGRAMMING = 2, SES_EXTENDED = 3 };
enum { NRC_SUBFUNC = 0x12, NRC_LENGTH = 0x13, NRC_CONDITIONS = 0x22, NRC_SEQUENCE = 0x24,
       NRC_RANGE = 0x31, NRC_SECURITY = 0x33, NRC_KEY = 0x35, NRC_TRIES = 0x36,
       NRC_PROGRAMMING = 0x72, NRC_NOT_SUPPORTED = 0x11, NRC_SESSION = 0x7F };

typedef struct svc svc_t;
typedef uint16_t (*svc_extra)(svc_t *s, const uint8_t *req, uint16_t n, uint8_t *resp);

struct svc {
    uint8_t session, unlocked, in_boot;
    uint8_t seed_out, bad_keys, locked_out;
    uint8_t stopped;                    /* engine stopped, as of the last call */
    uint8_t prog_req, reset_req;        /* the host's to act on, then clear */
    uint32_t seed, last_ms, lock_ms;
    void *ctx;                          /* the extra handler's own state */
};

void     svc_init(svc_t *s, int in_boot);
uint32_t svc_key(uint32_t seed);
uint16_t svc_nrc(uint8_t *resp, uint8_t sid, uint8_t code);
uint16_t svc_handle(svc_t *s, const uint8_t *req, uint16_t n, uint8_t *resp,
                    uint32_t ms, uint32_t us, int engine_stopped, svc_extra extra);
void     svc_tick(svc_t *s, uint32_t ms, int engine_stopped);   /* timeout, engine turning */
int      svc_unlocked(const svc_t *s);
uint8_t  svc_session(const svc_t *s);

#endif
