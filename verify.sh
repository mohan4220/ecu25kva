#!/usr/bin/env bash
# verify.sh -- run every check in the project, and say which failed.
#
#   ./verify.sh            circuits, schematics, firmware (both builds),
#                          the model's back-to-back test, the scenarios,
#                          the service tool
#   ./verify.sh --boards   also the KiCad board checks (production and
#                          prototype: DRC, parity, routing). Slow.
#   ./verify.sh --matlab   also rebuild nothing, but simulate model/ecu_app
#                          in Simulink (needs MATLAB with Stateflow)
#
# Any step that fails is listed at the end, and the exit code is non-zero.
# Run it before every commit that touches firmware/, model/ or hw/.
cd "$(dirname "$0")" || exit 1
ROOT=$(pwd)

BOARDS=0; MATLAB=0
for a in "$@"; do
    case "$a" in
        --boards) BOARDS=1 ;;
        --matlab) MATLAB=1 ;;
        *) echo "usage: $0 [--boards] [--matlab]"; exit 2 ;;
    esac
done

# --- tools: the venv's python, a C compiler, KiCad's python
if [ -x .venv/bin/python ]; then PY=$ROOT/.venv/bin/python; else PY=$ROOT/.venv/Scripts/python.exe; fi
ZIG=$ROOT/.venv/Lib/site-packages/ziglang/zig.exe
if [ -n "$CC" ]; then CCMD="$CC"
elif [ -x "$ZIG" ]; then CCMD="$ZIG cc"     # Windows: zig directly; python -m ziglang hides errors
else CCMD=cc; fi
EXT=so; EXE=; case "$(uname -s)" in
    Darwin) EXT=dylib ;;
    MINGW*|MSYS*|CYGWIN*) EXT=dll; EXE=.exe ;;
esac
if [ "$EXT" = dll ]; then
    KICAD_BIN=${KICAD_BIN:-/c/Users/$USERNAME/AppData/Local/Programs/KiCad/10.0/bin}
    export PATH="$KICAD_BIN:$PATH"
    export NGSPICE_LIB=${NGSPICE_LIB:-$KICAD_BIN/ngspice.dll}
    # the schematics are drawn against KiCad 7.0.11's symbols (HANDOFF)
    export KICAD_SYMBOL_DIR=${KICAD_SYMBOL_DIR:-C:/Users/$USERNAME/opt/kicad7-libs/kicad-symbols-7.0.11}
    export KICAD10_SYMBOL_DIR=${KICAD10_SYMBOL_DIR:-$KICAD_SYMBOL_DIR}
    export KICAD_FOOTPRINT_DIR=${KICAD_FOOTPRINT_DIR:-$KICAD_BIN/../share/kicad/footprints}
    KPY=$KICAD_BIN/python.exe
else
    KPY=${KICAD_PY:-python3}
fi
export PYTHONUTF8=1
OUT=$(mktemp -d); trap 'rm -rf "$OUT"' EXIT
FAILED=()

step() {   # step "name" command...
    local name=$1; shift
    printf '%-44s ' "$name"
    if "$@" > "$OUT/log" 2>&1; then
        echo ok
    else
        echo FAIL
        tail -15 "$OUT/log" | sed 's/^/    /'
        FAILED+=("$name")
    fi
}

FW=$ROOT/firmware
GI=$(for d in "$FW"/gen/*/; do printf -- "-I%s " "$d"; done)
CF="-std=c99 -Wall -Wextra -Werror -O2"

unit_ref()   { $CCMD $CF -I"$FW/core" -o "$OUT/t_ref$EXE" "$FW/sim/test_core.c" "$FW"/core/*.c -lm && "$OUT/t_ref$EXE"; }
unit_model() { $CCMD $CF -DECU_MODEL -I"$FW/core" $GI -o "$OUT/t_mod$EXE" "$FW/sim/test_core.c" "$FW"/core/*.c "$FW"/gen/*/*.c -lm && "$OUT/t_mod$EXE"; }
boot()       { $CCMD $CF -I"$FW/core" -I"$FW/boot" -o "$OUT/t_boot$EXE" "$FW/sim/test_boot.c" "$FW/boot/boot.c" \
                 "$FW/core/service.c" "$FW/core/nvm.c" "$FW/core/isotp.c" "$FW/core/link.c" && "$OUT/t_boot$EXE"; }
b2b()        { $CCMD -std=c99 -Wall -Wextra -O2 -ffp-contract=off -I"$FW/core" $GI -o "$OUT/b2b$EXE" \
                 "$ROOT/model/test/b2b.c" "$FW/core/govern.c" "$FW/core/rail.c" "$FW/core/inject.c" \
                 "$FW/core/safety.c" "$FW/core/mode.c" "$FW/core/crank.c" "$FW"/gen/*/*.c -lm && "$OUT/b2b$EXE"; }
libs()       { mkdir -p "$FW/sim/build" &&
               $CCMD $CF -I"$FW/core" -shared -fPIC -o "$FW/sim/build/libecu.$EXT" "$FW"/core/*.c -lm &&
               $CCMD $CF -DECU_MODEL -I"$FW/core" $GI -shared -fPIC -o "$FW/sim/build/libecu_model.$EXT" "$FW"/core/*.c "$FW"/gen/*/*.c -lm &&
               $CCMD $CF -I"$FW/core" -I"$FW/boot" -shared -fPIC -o "$FW/sim/build/libboot.$EXT" "$FW/boot/boot.c" \
                 "$FW/core/service.c" "$FW/core/nvm.c" "$FW/core/isotp.c" "$FW/core/link.c"; }
sil_ref()    { (cd "$FW/sim" && "$PY" run_sil.py | tee /dev/stderr | grep -q "16/16 scenarios pass"); }
sil_model()  { (cd "$FW/sim" && ECU_LIB=libecu_model "$PY" run_sil.py | tee /dev/stderr | grep -q "16/16 scenarios pass"); }
service()    { (cd "$FW/sim" && "$PY" test_service.py); }
circuits()   { "$PY" sim/run_sim.py | tee /dev/stderr | grep -qE "^ +([0-9]+)/\1 blocks pass"; }
netlist()    { "$PY" hw/check_netlist.py | tee /dev/stderr | grep -q "schematic connectivity OK"; }
proto_sch()  { "$PY" prototype/check_prototype.py | tee /dev/stderr | grep -q "schematic connectivity OK"; }
schlib()     { "$PY" hw/test_schlib.py; }
pins()       { "$PY" prototype/stm32_pins.py; }
pcb()        { "$KPY" hw/check_pcb.py | tee /dev/stderr | grep -q "ALL PASS"; }
proto_pcb()  { (cd prototype && "$PY" -c "
import test_prototype as T, sys
names = sorted((n for n in dir(T) if n.startswith('test_')), key=lambda n: T.__dict__[n].__code__.co_firstlineno)
bad = []
for n in names:
    try: T.__dict__[n]()
    except Exception as e: bad.append(n); print('FAIL', n, e)
print(len(names) - len(bad), '/', len(names)); sys.exit(1 if bad else 0)"); }
simulink()   { (cd model && matlab -batch "addpath(pwd, fullfile(pwd,'lib'), fullfile(pwd,'test')); sim_ecu_app"); }

echo "== circuits and schematics"
step "circuit blocks (run_sim)" circuits
step "production netlist" netlist
step "symbol library" schlib
step "prototype schematic" proto_sch
step "prototype MCU pins" pins
echo "== firmware"
step "unit tests, hand-written build" unit_ref
step "unit tests, model-generated build" unit_model
step "bootloader tests" boot
step "models against hand-written C (b2b)" b2b
step "SIL libraries" libs
step "16 scenarios, hand-written build" sil_ref
step "16 scenarios, model-generated build" sil_model
step "service tool" service
if [ $BOARDS = 1 ]; then
    echo "== boards"
    step "production board (check_pcb)" pcb
    step "prototype board (26 tests)" proto_pcb
fi
if [ $MATLAB = 1 ]; then
    echo "== Simulink"
    step "ecu_app closed loop" simulink
fi

echo
if [ ${#FAILED[@]} -eq 0 ]; then
    echo "ALL PASS"
else
    echo "FAILED: ${FAILED[*]}"
    exit 1
fi
