#!/bin/sh
# Back-to-back test: every generated model against its hand-written C.
# -ffp-contract=off so neither side fuses a*b+c differently: the PI loops
# then agree to the last bit; the tables to a unit or two in the last
# place (Simulink's interpolation orders its arithmetic differently).
cd "$(dirname "$0")/../../firmware" || exit 1
CC=${CC:-cc}
GI=$(for d in gen/*/; do printf -- "-I%s " "$d"; done)
$CC -std=c99 -Wall -Wextra -O2 -ffp-contract=off -Icore $GI -o "${TMPDIR:-/tmp}/b2b" \
    ../model/test/b2b.c core/govern.c core/rail.c core/inject.c core/safety.c \
    core/mode.c core/crank.c gen/*/*.c -lm && "${TMPDIR:-/tmp}/b2b"
