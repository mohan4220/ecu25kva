#!/usr/bin/env python3
"""Build the whole prototype schematic into prototype/.

The eight production sheets come from their own generators' build(),
with additions.apply() on top; mcu and connector are replaced by
mcu_stm32 and lab_io. The root is hw/gen_project.py's, pointed here by
its module globals, so production and prototype share one root writer.
Nothing is written into hw/ (test_hw_untouched).

Run: .venv/bin/python prototype/gen_prototype.py
"""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(HERE, "..", "hw"))
import additions  # noqa: E402
import gen_project  # noqa: E402
import gen_sheet_lab_io  # noqa: E402
import gen_sheet_mcu_stm32  # noqa: E402

PROD = ("power_input", "rails", "injector", "metering_egr",
        "sensors_analog", "speed_inputs", "discrete_io", "can")
REPLACED = {
    "mcu": ("mcu_stm32", "STM32G474VET6, supervisor, USB-C, debug (prototype)"),
    "connector": ("lab_io", "Lab terminals and bridge header (prototype)"),
}
OPEN_ITEMS = """PROTOTYPE ROOT SHEET

The eight production sheets are built by their own generators in hw/; this project only adds test points and the
BOOST_MON divider (prototype/additions.py). mcu is replaced by mcu_stm32 (STM32G474VET6) and connector by lab_io
(screw terminals). Production open items 5.1 (power ground) and 5.2 (TRIP_LOOP) are closed here by terminals
J1002 and J1007, so prototype/check_prototype.py expects no open items at all."""


def lib_tables():
    with open(os.path.join(HERE, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (lib (name "ecu25kva")(type "KiCad")'
                '(uri "${KIPRJMOD}/../hw/lib/ecu25kva.kicad_sym")(options "")'
                '(descr "Production project symbols"))\n)\n')
    with open(os.path.join(HERE, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table\n  (lib (name "ecu25kva")(type "KiCad")'
                '(uri "${KIPRJMOD}/../hw/lib/ecu25kva.pretty")(options "")'
                '(descr "Production project footprints"))\n)\n')


def main():
    for name in PROD:
        sh = importlib.import_module(f"gen_sheet_{name}").build()
        additions.apply(name, sh)
        sh.write(os.path.join(HERE, f"{name}.kicad_sch"), force=True)
    gen_sheet_mcu_stm32.build().write(gen_sheet_mcu_stm32.OUT, force=True)
    gen_sheet_lab_io.build().write(gen_sheet_lab_io.OUT, force=True)

    gen_project.HW = HERE
    gen_project.PROJECT = "prototype"
    gen_project.SHEETS = [(REPLACED[n][0], REPLACED[n][1], b, t)
                          if n in REPLACED else (n, d, b, t)
                          for n, d, b, t in gen_project.SHEETS]
    gen_project.LAYOUT = tuple(tuple(REPLACED.get(n, (n,))[0] for n in col)
                               for col in gen_project.LAYOUT)
    gen_project.OPEN_ITEMS = OPEN_ITEMS
    gen_project.write_root()
    gen_project.write_project()
    lib_tables()
    print(f"prototype schematic written: {len(gen_project.SHEETS)} sheets")


if __name__ == "__main__":
    main()
