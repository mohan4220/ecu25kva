#!/usr/bin/env python3
"""Generate the KiCad project skeleton for the genset ECU.

Why a generator and not a hand-drawn root sheet: the sheet list, the
sheet-to-simulation-block mapping and the BOM requirement tags all have to
stay in step with sim/blocks/ and docs/bom_requirements.md, and a root
sheet edited by hand drifts from them silently. This script is the single
place that list lives. Re-running it rewrites ONLY the root sheet and any
child sheet that does not exist yet -- a child sheet with content in it is
never touched, so schematic work done in Eeschema is safe.

KiCad 7 (.kicad_sch, version 20230121). Checked against the installed
kicad-cli 7.0.11.
"""
import json
import os
import re
import sys
import uuid

HW = os.path.dirname(os.path.abspath(__file__))
PROJECT = "ecu25kva"

# Sheet order is signal order: power in, rails, brain, then outputs,
# inputs, comms, and finally the connector everything lands on.
SHEETS = [
    ("power_input", "Power input and transient protection",
     "emi_filter, transient_clamp, load_dump, negative_pulses, reverse_battery",
     "TVS, NEG-CLAMP"),
    ("rails", "Buck pre-regulator, 3V3 and 5V_SENSOR rails",
     "buck_preregulator, mcu_pdn, sensor_rail",
     "PDN-BULK, SENSOR-PTC"),
    ("mcu", "S32K148, supervisor and fail-safe gating",
     "supervisor, mcu_pdn",
     "GATE-PULLDOWN"),
    ("injector", "Injector drive: boost rail, high sides, low sides",
     "boost_converter, injector_boost, injector_turnoff",
     ""),
    ("metering_egr", "Fuel metering unit and EGR actuator",
     "metering_unit_pwm, egr_hbridge",
     "MU-ISENSE, EGR-DRIVER"),
    ("sensors_analog", "Analog sensor front-ends",
     "sensor_ratiometric, sensor_differential, ntc_frontend, battery_sense",
     ""),
    ("speed_inputs", "Crank VR conditioner and cam front-end",
     "vr_conditioner, cam_frontend",
     ""),
    ("discrete_io", "Switch inputs, trip-module sense, relay drivers",
     "discrete_input, trip_module_sense, relay_driver",
     ""),
    ("can", "Dual CAN, J1939 250 kbit/s",
     "can_termination",
     "CAN-TERM"),
    ("connector", "94-way Bosch connector and harness mapping",
     "",
     ""),
]

# The root sheet is the only place the ten pages are joined to each
# other. Until 21 Sep 2026 its sheet symbols carried NO hierarchical
# pins, which meant every sheet's netlist was correct and the project
# had none: a name on two sheets was two nets, and nothing compared
# them. Sizing the symbols to their pin counts is why this is A2 rather
# than A3 -- the mcu and connector sheets export 39 and 40 nets each.
PAPER = "A2"
COL_X = (45.0, 215.0, 385.0)
COL_Y0, COL_GAP = 28.0, 26.0
SHEET_W, SHEET_H = 101.6, 25.4
PIN_PITCH = 2.54
STUB = 12.7

# Which column each sheet lands in, in signal order down each column.
LAYOUT = (("power_input", "rails", "mcu", "injector"),
          ("metering_egr", "sensors_analog", "speed_inputs", "discrete_io"),
          ("can", "connector"))


def u():
    return str(uuid.uuid4())


# KiCad's own shape vocabulary for hierarchical pins and labels. A
# sheet pin's shape has to agree with the child's hierarchical label or
# ERC objects, so the pins are read OUT of the children rather than
# declared here -- there is no second list to drift.
SHAPES = ("input", "output", "bidirectional", "tri_state", "passive")


def child_nets(name):
    """Every hierarchical label in a child sheet, with its shape.

    Returns [(net, shape), ...] sorted by name. A name that appears more
    than once in one child with DIFFERENT shapes falls back to passive:
    the child is internally inconsistent about direction and the root
    sheet is not the place to invent an answer.
    """
    path = os.path.join(HW, f"{name}.kicad_sch")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        text = f.read()
    seen = {}
    for m in re.finditer(r'\(hierarchical_label "([^"]+)" \(shape (\w+)\)',
                         text):
        net, shape = m.group(1), m.group(2)
        if shape not in SHAPES:
            shape = "passive"
        if net in seen and seen[net] != shape:
            seen[net] = "passive"
        else:
            seen.setdefault(net, shape)
    return sorted(seen.items())


def sheet_height(nets):
    per_side = (len(nets) + 1) // 2
    return max(SHEET_H, (per_side + 1) * PIN_PITCH)


def sheet_symbol(name, fname, desc, blocks, tags, x, y, nets):
    """One hierarchical sheet symbol, with a pin per net the child exports."""
    h = sheet_height(nets)

    def prop(key, val, idx, dy, justify, hide=False):
        hd = " hide" if hide else ""
        return (f'    (property "{key}" "{val}" (id {idx}) (at {x} {y + dy:.2f} 0)\n'
                f'      (effects (font (size 1.27 1.27)) (justify {justify})'
                f'{hd})\n    )')
    parts = [
        f'  (sheet (at {x} {y}) (size {SHEET_W} {h:.2f}) (fields_autoplaced)',
        '    (stroke (width 0.1524) (type solid))',
        '    (fill (color 0 0 0 0.0000))',
        f'    (uuid {u()})',
        prop("Sheetname", name, 0, -0.7112, "left bottom"),
        prop("Sheetfile", fname, 1, h + 0.5588, "left top"),
        prop("Description", desc, 2, 0, "left", hide=True),
        prop("SimBlocks", blocks, 3, 0, "left", hide=True),
        prop("BomTags", tags, 4, 0, "left", hide=True),
    ]
    half = (len(nets) + 1) // 2
    stubs = []
    for i, (net, shape) in enumerate(nets):
        left = i < half
        j = i if left else i - half
        py = y + PIN_PITCH * (j + 1)
        px = x if left else x + SHEET_W
        # Angle 180 puts the pin on the LEFT edge pointing out to the
        # left; 0 puts it on the right edge pointing right.
        parts.append(
            f'    (pin "{net}" {shape} (at {px:.2f} {py:.2f} '
            f'{180 if left else 0})\n'
            f'      (effects (font (size 1.27 1.27)) '
            f'(justify {"left" if left else "right"}))\n'
            f'      (uuid {u()})\n    )')
        ex = px - STUB if left else px + STUB
        stubs.append(
            f'  (wire (pts (xy {px:.2f} {py:.2f}) (xy {ex:.2f} {py:.2f}))\n'
            f'    (stroke (width 0) (type default))\n    (uuid {u()})\n  )')
        # The label on the stub is what actually joins the sheets: two
        # stubs anywhere on this page carrying the same label are one
        # net. Routing 162 pins as wires would be unreadable and would
        # not connect anything the labels do not.
        stubs.append(
            f'  (label "{net}" (at {ex:.2f} {py:.2f} '
            f'{180 if left else 0})\n'
            f'    (effects (font (size 1.27 1.27)) '
            f'(justify {"right" if left else "left"}))\n'
            f'    (uuid {u()})\n  )')
    parts.append('  )')
    return "\n".join(parts), stubs


# The eighteen nets that reach only one pin. Kept here rather than only
# in hw/check_netlist.py so the page itself says what is open -- a
# reader looking at the root sheet should not have to run a script to
# find out which ends are loose.
OPEN_ITEMS = """WHAT THIS SHEET IS FOR, AND WHAT IT LEAVES OPEN

This page is the only place the ten sheets are joined. Each sheet symbol carries one hierarchical pin per net its
child exports, and each pin carries a stub with a label: two labels anywhere on this page with the same name are
one net. Until 21 September 2026 the symbols carried no pins at all, which meant every sheet's own netlist was
correct and the project had none -- a name on two sheets was two nets and nothing compared them. hw/check_netlist.py
now exports the whole hierarchy and checks it, the way sim/run_sim.py checks the component values.

113 named nets carry two or more pins. EIGHTEEN reach exactly one, every one of them a recorded open item:

  DRIVERS AND AMPLIFIERS NOT CHOSEN (9)   INJ_HS_A  INJ_HS_B  INJ_LS_1  INJ_LS_2  INJ_LS_3  MU_PWM
                                          ISNS_INJ_A  ISNS_INJ_B  ISNS_MU
      The far end of each is a gate driver or a current-sense amplifier. Requirements are drawn on the sheets that
      own them -- output impedance <= 25 ohm, ground-referenced sense, 73.3 V rail rating -- and no part is guessed.

  POWER INPUT'S TWO CONTROLLER GATES (2)  VBAT_REV_GATE  NCLAMP_GATE
      Ideal-diode controller and negative-clamp comparator. The comparator's propagation delay is the last
      unmodelled term in the negative-pulse chain.

  THE EGR BRIDGE (5)                      EGR_IN1  EGR_IN2  ISNS_EGR  EGR_HIGH_59  EGR_LOW_81
      Blocked on a rail rating, not a missing idea: VBAT_PROT reaches 73.3 V on ISO 7637-2 pulse 2a and integrated
      automotive H-bridges cap out at 40-45 V as a class. Needs a bridge gate driver above 73.3 V that still decodes
      DIR/PWM. Connector pins 59 and 81 are real and wired; the driver is not chosen.

  NO PART, AND NO PIN (2)                 BARO  TRIP_LOOP
      BARO is an onboard barometric sensor with no part chosen. TRIP_LOOP is a NEW signal -- not on the OEM wiring
      diagram at all -- so it needs one of the 50 unconfirmed connector pins. So does GND: the diagram shows pin 21
      as the battery positive feed and no battery negative anywhere. Both wait on the connector part number and the
      OEM pin list, or on continuity measurement at the machine."""


def _text_block(body, x, y, size=1.6):
    """A text element. KiCad 7 rejects a literal newline inside a quoted
    string outright -- the file balances, every element looks well formed,
    and the whole schematic fails to load with no line number."""
    esc = body.replace(chr(92), chr(92) * 2).replace(chr(34),
                                                     chr(92) + chr(34))
    esc = esc.replace(chr(10), chr(92) + "n").replace(chr(13), "")
    return (f'  (text "{esc}" (at {x} {y} 0)\n'
            f'    (effects (font (size {size} {size})) (justify left))\n'
            f'    (uuid {u()})\n  )')


def root_notes():
    # A text block renders VERTICALLY CENTRED on its anchor, so a
    # 30-line note reaches 15 lines above y.
    return _text_block(OPEN_ITEMS, 22.0, 340.0)


def write_root():
    body = [f'(kicad_sch (version 20230121) (generator ecu25kva_gen)',
            f'  (uuid {u()})',
            f'  (paper "{PAPER}")',
            '  (title_block',
            '    (title "Genset ECU -- 25 kVA Kirloskar 3GK550ETA 4SR1")',
            '    (company "ecu25kva")',
            '    (comment 1 "Root sheet -- generated by hw/gen_project.py")',
            '    (comment 2 "Every sheet maps to blocks in sim/blocks/ and tags in docs/bom_requirements.md")',
            '  )',
            '  (lib_symbols)']
    meta = {n: (d, b, t) for n, d, b, t in SHEETS}
    stubs, placed = [], 0
    for col, names in enumerate(LAYOUT):
        y = COL_Y0
        for name in names:
            desc, blocks, tags = meta[name]
            nets = child_nets(name)
            sym, st = sheet_symbol(name, f"{name}.kicad_sch", desc, blocks,
                                   tags, COL_X[col], y, nets)
            body.append(sym)
            stubs.extend(st)
            y += sheet_height(nets) + COL_GAP
            placed += 1
    assert placed == len(SHEETS), f"{placed} sheets placed, {len(SHEETS)} defined"
    body.extend(stubs)
    body.append(root_notes())
    body.append('  (sheet_instances')
    body.append('    (path "/" (page "1"))')
    body.append('  )')
    body.append(')')
    path = os.path.join(HW, f"{PROJECT}.kicad_sch")
    with open(path, "w") as f:
        f.write("\n".join(body) + "\n")
    return path


def write_child(name, desc):
    """Create an empty child sheet, but NEVER overwrite one with content."""
    path = os.path.join(HW, f"{name}.kicad_sch")
    if os.path.exists(path):
        if os.path.getsize(path) > 400:
            return path, "kept (has content)"
        return path, "kept"
    with open(path, "w") as f:
        f.write(f'''(kicad_sch (version 20230121) (generator ecu25kva_gen)
  (uuid {u()})
  (paper "{PAPER}")
  (title_block
    (title "{desc}")
    (company "ecu25kva")
    (comment 1 "Sheet: {name}")
  )
  (lib_symbols)
  (sheet_instances
    (path "/" (page "1"))
  )
)
''')
    return path, "created"


def write_project():
    path = os.path.join(HW, f"{PROJECT}.kicad_pro")
    if os.path.exists(path):
        return path, "kept"
    pro = {
        "board": {"design_settings": {}},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": f"{PROJECT}.kicad_pro", "version": 1},
        "net_settings": {"classes": [{"name": "Default", "clearance": 0.2,
                                      "track_width": 0.25}]},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [],
        "text_variables": {},
    }
    with open(path, "w") as f:
        json.dump(pro, f, indent=2)
    return path, "created"


def write_sym_lib_table():
    """Point the project at its own symbol library.

    The S32K148 has no symbol in KiCad 7's stock libraries (checked: no
    S32K anywhere under /usr/share/kicad/symbols). Several other parts
    here are specified by property rather than by part number, so they
    need project-local symbols too.
    """
    path = os.path.join(HW, "sym-lib-table")
    if os.path.exists(path):
        return path, "kept"
    with open(path, "w") as f:
        f.write('(sym_lib_table\n'
                '  (lib (name "ecu25kva")(type "KiCad")'
                '(uri "${KIPRJMOD}/lib/ecu25kva.kicad_sym")'
                '(options "")(descr "Project symbols -- parts with no stock '
                'KiCad symbol, S32K148 included"))\n)\n')
    return path, "created"


if __name__ == "__main__":
    print(f"root      {write_root()}")
    for p, s in (write_project(), write_sym_lib_table()):
        print(f"{s:9} {p}")
    for name, desc, _, _ in SHEETS:
        p, s = write_child(name, desc)
        print(f"{s:9} {os.path.basename(p)}")
