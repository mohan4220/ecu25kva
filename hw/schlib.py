#!/usr/bin/env python3
"""Minimal KiCad 7 schematic writer.

Enough to place symbols, wire them, label nets and expose hierarchical
pins -- which is all the ECU sheets need. Not a general KiCad library.

WHY GENERATE SCHEMATICS AT ALL. The component values on these sheets are
not free choices; almost every one traces to a check in sim/blocks/ or a
tag in docs/bom_requirements.md. A hand-drawn sheet holds those values as
text nobody re-derives, and they drift the moment a simulation moves --
which has already happened three times in this project with the
reverse-battery FET's voltage class alone. Generated sheets carry the
provenance in the part's own fields, so a value and the reason for it
travel together.

Eeschema can still edit these freely. Generation is the starting point,
not a lock: hw/gen_project.py refuses to overwrite a sheet that has
content, and the same rule applies here.

Symbol definitions are copied out of the installed KiCad libraries into
each sheet's own (lib_symbols) block, which is what KiCad expects -- a
schematic caches every symbol it uses rather than referencing the library
at open time.
"""
import os
import re
import uuid

KICAD_SYMS = "/usr/share/kicad/symbols"
LOCAL_SYMS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")

_CACHE = {}


def _lib_path(lib):
    p = os.path.join(LOCAL_SYMS, f"{lib}.kicad_sym")
    return p if os.path.exists(p) else os.path.join(KICAD_SYMS,
                                                    f"{lib}.kicad_sym")


def _extract(text, start):
    """Return the balanced s-expression beginning at index `start`.

    Quote-aware: a parenthesis inside a string is not a delimiter, and a
    backslash escapes the next character. Without that, any symbol whose
    description contains a bracket truncates silently.
    """
    depth, i, in_str = 0, start, False
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise ValueError("unbalanced s-expression")


def symbol_def(libid):
    """Pull one symbol out of its library, renamed to its full LIB:NAME id."""
    if libid in _CACHE:
        return _CACHE[libid]
    lib, name = libid.split(":", 1)
    path = _lib_path(lib)
    with open(path) as f:
        text = f.read()
    m = re.search(r'^  \(symbol "' + re.escape(name) + r'"[ \n]', text,
                  re.M)
    if not m:
        raise KeyError(f"{libid} not found in {path}")
    body = _extract(text, m.start() + 2)
    # Inside a schematic the symbol is keyed by "Lib:Name", and its child
    # units keep their own bare-name prefix.
    body = body.replace(f'(symbol "{name}"', f'(symbol "{libid}"', 1)
    _CACHE[libid] = body
    return body


def pin_xy(lx, ly, x, y, rot):
    """Where a symbol pin actually lands on the page.

    Symbol-local coordinates are y-up; the schematic page is y-down.
    Rotation is counter-clockwise IN THE SYMBOL'S OWN y-up frame, so:

        rx = lx*cos(t) - ly*sin(t)        (rotate in y-up)
        ry = lx*sin(t) + ly*cos(t)
        px = X + rx,  py = Y - ry         (then flip to page y-down)

    Derived rather than recalled, because the first version of this
    function had 90 and 270 the other way round and nothing complained:
    the parts still looked placed, the wires still met their endpoints,
    and the only symptom was in the exported netlist, where the negative
    clamp Schottky came out with its CATHODE on ground -- a diode
    connected backwards on a page that plots correctly.
    """
    rot %= 360
    if rot == 0:
        return (x + lx, y - ly)
    if rot == 90:
        return (x - ly, y - lx)
    if rot == 180:
        return (x - lx, y + ly)
    if rot == 270:
        return (x + ly, y + lx)
    raise ValueError(f"unsupported rotation {rot}")


# Symbol-local pin coordinates, read out of the installed libraries
# rather than remembered. Checked by hw/gen_sheet_power_input.py's own
# self-test against schlib.symbol_def().
PINS = {
    "Device:R": {"1": (0, 3.81), "2": (0, -3.81)},
    "Device:C": {"1": (0, 3.81), "2": (0, -3.81)},
    "Device:L": {"1": (0, 3.81), "2": (0, -3.81)},
    "Device:Fuse": {"1": (0, 3.81), "2": (0, -3.81)},
    "Device:Polyfuse": {"1": (0, 3.81), "2": (0, -3.81)},
    "Device:C_Polarized": {"1": (0, 3.81), "2": (0, -3.81)},
    # Keyed by pin NUMBER, not name -- a diode's pins are numbered 1/2
    # and named K/A, and keying on the name silently finds nothing.
    "Device:D": {"1": (-3.81, 0), "2": (3.81, 0)},            # 1=K  2=A
    "Device:D_Zener": {"1": (-3.81, 0), "2": (3.81, 0)},      # 1=K  2=A
    "Device:D_TVS": {"1": (-3.81, 0), "2": (3.81, 0)},        # 1=A1 2=A2
    "Device:D_Schottky": {"1": (-3.81, 0), "2": (3.81, 0)},   # 1=K  2=A
    "Device:Q_NMOS_GSD": {"1": (-5.08, 0),                    # G
                          "2": (2.54, -5.08),                 # S
                          "3": (2.54, 5.08)},                 # D
    "Device:Q_NPN_BCE": {"1": (-5.08, 0),                     # B
                         "2": (2.54, 5.08),                   # C
                         "3": (2.54, -5.08)},                 # E
}


def verify_pins():
    """Check PINS against the installed libraries. Called by every sheet
    generator before it draws anything -- a wrong offset here produces
    wires that look connected and are not."""
    bad = []
    for libid, want in PINS.items():
        body = symbol_def(libid)
        got = {}
        for m in re.finditer(
                r'\(pin \w+ \w+ \(at ([-\d.]+) ([-\d.]+) (\d+)\) '
                r'\(length ([\d.]+)\)\s*\n\s*\(name "[^"]*"[^\n]*\n'
                r'\s*\(number "([^"]+)"', body):
            got[m.group(5)] = (float(m.group(1)), float(m.group(2)))
        for num, xy in want.items():
            if got.get(num) != xy:
                bad.append((libid, num, xy, got.get(num)))
    if bad:
        raise SystemExit(f"PINS disagrees with the installed library: {bad}")
    return len(PINS)


def r2(v):
    """Round a page coordinate to 2 decimals.

    Symbol pins are written with %.2f, so a wire endpoint carrying full
    float precision lands a fraction of a micron away and KiCad treats
    the two as different points. The schematic plots correctly, the wire
    visibly touches the pin, and the netlist says "unconnected" -- which
    is exactly how the rails sheet came out with an unconnected input
    capacitor on a wire drawn straight to it. Every coordinate this
    module emits goes through here.
    """
    return round(float(v), 2)


def esc(s):
    """Escape a string for a KiCad s-expression.

    Newlines MUST become the two-character escape. KiCad 7's parser
    rejects a literal newline inside a quoted string outright -- the
    file balances, every element looks well formed, and the whole
    schematic fails to load with "Failed to load schematic file" and no
    line number, which is a long way to travel for a missing backslash.
    Escaped here rather than at each call site, because the caller that
    gets it wrong is whichever one is written next.
    """
    # Built with chr() rather than literals: this function is nothing
    # but backslashes, and writing them as escapes in a generator that
    # itself writes generators is how the bug it fixes got here.
    out = s.replace(chr(92), chr(92) * 2)          # backslash
    out = out.replace(chr(34), chr(92) + chr(34))  # double quote
    out = out.replace(chr(10), chr(92) + "n")      # newline -> \n
    out = out.replace(chr(13), "")                 # drop CR
    return out


def _u():
    return str(uuid.uuid4())


def _eff(size=1.27, justify=None, hide=False):
    j = f" (justify {justify})" if justify else ""
    h = " hide" if hide else ""
    return f"(effects (font (size {size} {size})){j}{h})"


class Rail:
    """A horizontal net drawn as consecutive segments.

    A wire ENDPOINT landing mid-span on another wire DOES NOT CONNECT in
    KiCad 7's netlister -- not even with an explicit junction element in
    the file. Interactively, Eeschema splits the underlying wire when you
    drop a junction on it; a generated file has no such split, so the two
    wires cross without meeting. The page plots exactly as intended and
    the netlist reports every tapped part as unconnected.

    Found on the rails sheet, where a single wire from the input
    hierarchical label to the buck's VIN pin had the input capacitor, the
    UVLO divider and the RON resistor all tapped off its middle, and all
    three came back unconnected.

    So: one segment per interval, every tap at a segment boundary. This
    is the only thing in the project allowed to draw a multi-tap rail.
    """

    def __init__(self, sheet, y):
        self.sh = sheet
        self.y = y
        self.x = None

    def to(self, x, tap=False):
        """Extend the rail to x. `tap` marks a point where something else
        joins, which is where a junction dot belongs."""
        if self.x is not None and r2(x) != r2(self.x):
            self.sh.wire(self.x, self.y, x, self.y)
            if tap:
                self.sh.junction(x, self.y)
        self.x = x
        return (x, self.y)


# Every sheet's reference designators start at its own hundred, which
# is how a ten-sheet project stays annotated without a human pass in
# Eeschema. Each generator allocated R1, C1, U1 independently until
# 21 Sep 2026, so the project-wide netlist came out of kicad-cli with
# "schematic has annotation errors" and ten different parts called R1 --
# each sheet's own netlist was correct and the project's was not. This
# is KiCad's own sheet-number x 100 convention, done at generation time.
REF_BASE = {
    "power_input": 100, "rails": 200, "mcu": 300, "injector": 400,
    "metering_egr": 500, "sensors_analog": 600, "speed_inputs": 700,
    "discrete_io": 800, "can": 900, "connector": 1000,
}


class Sheet:
    """One .kicad_sch page."""

    def __init__(self, title, paper="A3", comments=(), ref_base=0):
        self.title = title
        self.paper = paper
        self.comments = list(comments)
        self.ref_base = ref_base
        self.items = []
        self.libs = {}
        self.refs = {}
        self.instances = []

    # -- placement ---------------------------------------------------
    def place(self, libid, ref_prefix, x, y, value, rot=0, unit=1,
              fields=None, mirror=None, footprint="", datasheet="~",
              ref=None):
        """Drop a symbol. `fields` become extra properties on the part --
        this is where a value's provenance goes (which .cir file, which
        BOM tag), so it travels with the schematic.

        Property ids 0-3 are RESERVED by KiCad for Reference, Value,
        Footprint and Datasheet, in that order. Custom fields therefore
        start at 4. Starting them at 2 does not error -- it silently
        renames the first custom field to "Footprint" and the second to
        "Datasheet", which is how a netlist export came out with
        `(footprint "emi_filter.cir C1 -- ESR 5 mOhm...")`.
        """
        self.libs[libid] = symbol_def(libid)
        # Pass `ref` explicitly to put several symbols on the SAME
        # component -- which is how a multi-unit part works. Allocating a
        # fresh reference per unit instead gives six separate one-unit
        # components that happen to share a footprint, and the netlist
        # says so: U1A, U2B, U3C rather than U1 units A-F.
        if ref is None:
            n = self.refs.get(ref_prefix, self.ref_base) + 1
            self.refs[ref_prefix] = n
            ref = f"{ref_prefix}{n}"
        else:
            # An explicit reference still has to advance the counter, or
            # the next auto-allocated part of the same prefix collides
            # with it -- six MCU units pinned to U1 left the counter at
            # zero and the supervisor was also numbered U1.
            m = re.fullmatch(re.escape(ref_prefix) + r"(\d+)", ref)
            if m:
                self.refs[ref_prefix] = max(
                    self.refs.get(ref_prefix, self.ref_base), int(m.group(1)))
        uid = _u()
        mir = f"\n    (mirror {mirror})" if mirror else ""
        # A power symbol's reference (#PWR01, ...) is noise on the page --
        # KiCad hides it by convention and so does this.
        hide_ref = ref_prefix.startswith("#")
        props = [
            f'    (property "Reference" "{ref}" (id 0) (at {x} {y - 5.08} 0)\n'
            f'      {_eff(hide=hide_ref)}\n    )',
            f'    (property "Value" "{esc(value)}" (id 1) (at {x} {y + 5.08} 0)\n'
            f'      {_eff()}\n    )',
            f'    (property "Footprint" "{footprint}" (id 2) (at {x} {y} 0)\n'
            f'      {_eff(hide=True)}\n    )',
            f'    (property "Datasheet" "{datasheet}" (id 3) (at {x} {y} 0)\n'
            f'      {_eff(hide=True)}\n    )',
        ]
        idx = 4
        for k, v in (fields or {}).items():
            props.append(
                f'    (property "{k}" "{esc(str(v))}" (id {idx}) (at {x} {y} 0)\n'
                f'      {_eff(hide=True)}\n    )')
            idx += 1
        self.items.append(
            f'  (symbol (lib_id "{libid}") (at {r2(x)} {r2(y)} {rot}) '
            f'(unit {unit}){mir}\n'
            f'    (in_bom yes) (on_board yes) (fields_autoplaced)\n'
            f'    (uuid {uid})\n' + "\n".join(props) + "\n  )")
        self.instances.append((uid, ref, value, unit))
        return ref

    # -- connectivity ------------------------------------------------
    def wire(self, x1, y1, x2, y2):
        self.items.append(
            f'  (wire (pts (xy {r2(x1)} {r2(y1)}) (xy {r2(x2)} {r2(y2)}))\n'
            f'    (stroke (width 0) (type default))\n    (uuid {_u()})\n  )')

    def junction(self, x, y):
        self.items.append(
            f'  (junction (at {r2(x)} {r2(y)}) (diameter 0) (color 0 0 0 0)\n'
            f'    (uuid {_u()})\n  )')

    def label(self, text, x, y, rot=0):
        self.items.append(
            f'  (label "{esc(text)}" (at {r2(x)} {r2(y)} {rot})\n'
            f'    {_eff(justify="left bottom")}\n    (uuid {_u()})\n  )')

    def hlabel(self, text, x, y, shape="passive", rot=0, justify=None):
        # A label's justification is read in the label's OWN rotated
        # frame, so a 180-degree label justified "left" puts its text back
        # across the wire it sits on. The connector sheet has 41 of them
        # in a column and it showed up there first.
        if justify is None:
            justify = "right" if rot % 360 == 180 else "left"
        self.items.append(
            f'  (hierarchical_label "{esc(text)}" (shape {shape}) '
            f'(at {r2(x)} {r2(y)} {rot})\n'
            f'    {_eff(justify=justify)}\n    (uuid {_u()})\n  )')

    def gnd(self, x, y):
        self.place("power:GND", "#PWR", x, y, "GND")

    def text(self, body, x, y, size=1.27):
        self.items.append(
            f'  (text "{esc(body)}" (at {r2(x)} {r2(y)} 0)\n'
            f'    {_eff(size=size, justify="left")}\n    (uuid {_u()})\n  )')

    # -- output ------------------------------------------------------
    def render(self):
        out = ['(kicad_sch (version 20230121) (generator ecu25kva_gen)',
               f'  (uuid {_u()})',
               f'  (paper "{self.paper}")',
               '  (title_block',
               f'    (title "{esc(self.title)}")',
               '    (company "ecu25kva")']
        for i, c in enumerate(self.comments[:4], start=1):
            out.append(f'    (comment {i} "{esc(c)}")')
        out.append('  )')
        out.append('  (lib_symbols')
        for _, body in sorted(self.libs.items()):
            out.append("\n".join("  " + ln for ln in body.splitlines()))
        out.append('  )')
        out.extend(self.items)
        out.append('  (sheet_instances')
        out.append('    (path "/" (page "1"))')
        out.append('  )')
        out.append(')')
        return "\n".join(out) + "\n"

    def write(self, path, force=False):
        if os.path.exists(path) and os.path.getsize(path) > 400 and not force:
            return f"kept (has content): {path}"
        with open(path, "w") as f:
            f.write(self.render())
        return f"wrote: {path}"
