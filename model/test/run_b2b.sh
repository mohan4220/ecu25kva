#!/bin/sh
# Back-to-back test: every generated model against its hand-written C.
# -ffp-contract=off so neither side fuses a*b+c differently: the PI loops
# then agree to the last bit; the tables to a unit or two in the last
# place (Simulink's interpolation orders its arithmetic differently).
#
# The compiler: $CC if set, else cc, else the project's zig (Windows has
# no cc; zig.exe is called directly, as verify.sh does).
cd "$(dirname "$0")/../../firmware" || exit 1
ZIG=../.venv/Lib/site-packages/ziglang/zig.exe
if [ -z "$CC" ]; then
    if command -v cc >/dev/null 2>&1; then CC=cc
    elif [ -x "$ZIG" ]; then CC="$ZIG cc"
    else echo "run_b2b.sh: no C compiler (set CC)"; exit 1; fi
fi
EXE=; case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) EXE=.exe ;; esac
OUT="${TMPDIR:-/tmp}/b2b$EXE"
GI=$(for d in gen/*/; do printf -- "-I%s " "$d"; done)
$CC -std=c99 -Wall -Wextra -O2 -ffp-contract=off -Icore $GI -o "$OUT" \
    ../model/test/b2b.c core/govern.c core/rail.c core/inject.c core/safety.c \
    core/mode.c core/crank.c core/sensors.c core/j1939.c core/actuate.c core/nvm.c core/log.c gen/*/*.c -lm && "$OUT"
