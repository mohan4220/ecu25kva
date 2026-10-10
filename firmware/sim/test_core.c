/* Unit tests for firmware/core. `make test` builds and runs them. */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "ecu.h"

static int fails;
#define CHECK(c) do { if (!(c)) { fails++; \
    printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #c); } } while (0)

static void test_io_size(void)
{
    ecu_io io;
    memset(&io, 0, sizeof io);
    CHECK(ecu_io_size() == sizeof(ecu_io));
    ecu_init(&io);
    CHECK(io.state == ECU_OFF);
}

int main(void)
{
    test_io_size();
    printf("%s: %d failure(s)\n", fails ? "FAIL" : "ok", fails);
    return fails != 0;
}
