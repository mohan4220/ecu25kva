#!/usr/bin/env python3
"""Project-level schematic checks. The counterpart to sim/run_sim.py.

sim/run_sim.py guards the component VALUES -- every one traces to a
block. Nothing guarded the CONNECTIVITY, and for most of phase 2 there
was none to guard: hw/ecu25kva.kicad_sch's sheet symbols carried no
hierarchical pins, so the ten sheets were ten separate schematics that
happened to use the same net names. Each sheet's own netlist was
correct and the project had no netlist at all.

This script exports the whole hierarchy through kicad-cli and checks it.
The rule it enforces that matters most is the same one run_sim.py has:
an exemption is not a pass. Every single-pin net has to be listed below
WITH ITS REASON, and a net that stops being single-pin has to be removed
from the list or this fails. An open item that quietly closes is as much
a drift as one that quietly opens.
"""
import collections
import os
import re
import subprocess
import sys
import tempfile

HW = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HW, "ecu25kva.kicad_sch")

# A net with one pin is a net whose other end is a part nobody has
# chosen, a pin nobody has identified, or a circuit nobody has drawn.
# Each is a real open item recorded elsewhere; none is a wiring mistake.
EXPECTED_OPEN = {
    # (Closed 21-22 Sep 2026: the eight gate-driver ends, AUIRS2181S on
    # every injector gate and the metering gate; and the three
    # current-sense ends, INA181A1-Q1.)
    # (power_input's two gates closed 22 Sep 2026: Q1 a P-FET with a
    #  passive gate network, Q2 a TLV3201-Q1 + UCC27517A-Q1 pair.)
    # -- the EGR bridge, blocked on a >73.3 V DIR/PWM gate driver --
    "/EGR_IN1": "EGR bridge not drawn -- blocked on a rail rating",
    "/EGR_IN2": "EGR bridge not drawn -- blocked on a rail rating",
    "/ISNS_EGR": "EGR bridge not drawn -- blocked on a rail rating",
    "/EGR_HIGH_59": "EGR bridge not drawn; the connector pin is real",
    "/EGR_LOW_81": "EGR bridge not drawn; the connector pin is real",
    # -- no part, and no pin --
    "/BARO": "onboard barometric sensor: no part chosen",
    "/TRIP_LOOP": "no connector pin -- not on the OEM diagram, needs one "
                  "of the 50 unconfirmed",
}

# Nets that must span more than one sheet, because a rail that does not
# is a rail that got disconnected by a rename.
MUST_SPAN = ("GND", "/VBAT_PROT", "/3V3_MCU", "/5V_MAIN", "/12V_GATE")

# Supply pins that legitimately have no capacitor across them: the pin is
# a return, or the "supply" is a bootstrap node whose capacitor IS the
# thing being bootstrapped and is already counted elsewhere.
NO_DECOUPLING_NEEDED = {
    ("U201", "7"): "LM5164 BST -- the bootstrap capacitor is the net",
}

# The global rails reach every sheet, so "is this sheet connected?" is
# trivially yes if you count them. A sheet attached to the rest of the
# board by GND ALONE is a sheet whose signals never left -- one level up
# from the local-label bug that made 5V_MAIN four nets. So the
# connectivity check excludes these and asks again.
GLOBAL_RAILS = {"GND", "/3V3_MCU", "/5V_MAIN", "/VBAT_PROT", "/12V_GATE",
                "/5V_SENSOR_A", "/5V_SENSOR_B", "/5V_SENSOR_C"}


class Fail(Exception):
    pass


def export_netlist(path):
    r = subprocess.run(
        ["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
         "-o", path, ROOT], capture_output=True, text=True)
    if r.returncode != 0:
        raise Fail(f"kicad-cli failed:\n{r.stdout}\n{r.stderr}")
    noise = (r.stdout + r.stderr).strip()
    if "annotation errors" in noise:
        raise Fail("kicad-cli reports annotation errors -- two parts share "
                   "a reference. schlib.REF_BASE gives each sheet its own "
                   "hundred; a sheet missing its ref_base= is the usual "
                   "cause.")
    return open(path).read()


def parse(text):
    comps = {}
    for m in re.finditer(r'\(comp \(ref "([^"]+)"\)\s*\n\s*\(value "([^"]*)"\)',
                         text):
        comps[m.group(1)] = m.group(2)
    nets = []
    i = text.index("(nets")
    for b in re.split(r'\n    \(net ', text[i:])[1:]:
        name = re.search(r'\(name "([^"]*)"\)', b).group(1)
        pins = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', b)
        nets.append((name, pins))
    return comps, nets


def child_labels(name):
    p = os.path.join(HW, f"{name}.kicad_sch")
    return set(re.findall(r'\(hierarchical_label "([^"]+)"', open(p).read()))


def root_pins():
    """{sheet name: {pin names}} as the ROOT sheet declares them."""
    text = open(ROOT).read()
    out = {}
    for m in re.finditer(r'\(sheet \(at [^\n]*\n(?:(?!\n  \(sheet ).)*?'
                         r'\(property "Sheetname" "([^"]+)"'
                         r'(?:(?!\n  \(sheet ).)*', text, re.S):
        out[m.group(1)] = set(re.findall(r'\(pin "([^"]+)" \w+ \(at',
                                         m.group(0)))
    return out


def main():
    checks, failed = [], 0

    def check(label, ok, detail=""):
        nonlocal failed
        checks.append((ok, label, detail))
        if not ok:
            failed += 1

    with tempfile.TemporaryDirectory() as td:
        text = export_netlist(os.path.join(td, "p.net"))
    comps, nets = parse(text)

    check(f"project netlist exports and annotates cleanly "
          f"({len(comps)} components)", True)

    dup = [r for r, c in collections.Counter(
        re.findall(r'\(comp \(ref "([^"]+)"\)', text)).items() if c > 1]
    check("every reference is unique across all ten sheets",
          not dup, f"duplicates: {dup}" if dup else "")

    named = [(n, p) for n, p in nets if not n.startswith("unconnected-")]
    multi = [n for n, p in named if len(p) > 1]
    single = {n for n, p in named if len(p) < 2}
    check(f"{len(multi)} named nets carry two or more pins", len(multi) > 100)

    unexplained = sorted(single - set(EXPECTED_OPEN))
    check("every single-pin net is a recorded open item",
          not unexplained, f"not in EXPECTED_OPEN: {unexplained}")

    stale = sorted(set(EXPECTED_OPEN) - single)
    check("no stale exemptions -- an open item that closed must leave "
          "EXPECTED_OPEN", not stale, f"no longer single-pin: {stale}")

    by_sheet = collections.defaultdict(set)
    for m in re.finditer(r'\(comp \(ref "([^"]+)"\).*?'
                         r'\(sheetpath \(names "([^"]*)"', text, re.S):
        by_sheet[m.group(2)].add(m.group(1))
    check(f"components land on {len(by_sheet)} sheet paths",
          len(by_sheet) >= 10, f"paths: {sorted(by_sheet)}")

    declared = root_pins()
    for name in sorted(declared):
        want, have = child_labels(name), declared[name]
        check(f"root sheet exposes every net {name} exports "
              f"({len(want)})", want <= have, f"missing: {sorted(want - have)}")

    # -- sheet-local nets wearing a project-wide name --------------
    # A local label stops at its sheet's edge. Name one after a board
    # rail and the sheet gets a private copy with no regulator on it,
    # while its own netlist stays perfectly correct. That is how
    # 5V_MAIN came to be FOUR nets and 3V3_MCU three.
    root_names = {n.lstrip("/") for n, _ in named if n.count("/") <= 1}
    shadow = sorted(n for n, _ in named
                    if n.count("/") >= 2 and n.rsplit("/", 1)[1] in root_names)
    check("no sheet-local net shadows a project-wide net name",
          not shadow, f"local copies of a global name: {shadow}")

    # -- sheet-to-sheet signal paths --------------------------------
    sheet_of = dict(re.findall(
        r'\(comp \(ref "([^"]+)"\).*?\(sheetpath \(names "([^"]*)"',
        text, re.S))
    sheet_of = {r: p.strip("/") for r, p in sheet_of.items()}
    all_sheets = set(sheet_of.values())
    crossing, linked = 0, set()
    for n, pins in named:
        if n in GLOBAL_RAILS:
            continue
        ss = {sheet_of[r] for r, _ in pins}
        if len(ss) > 1:
            crossing += 1
            linked |= ss
    stranded = sorted(all_sheets - linked)
    check(f"every sheet carries a signal to another sheet "
          f"({crossing} nets cross a boundary, rails excluded)",
          not stranded,
          f"attached by global rails only: {stranded}")

    # -- decoupling -------------------------------------------------
    # Walks every power_in pin and asks whether a capacitor sits on the
    # same net. It found the five difference amplifiers on
    # sensors_analog with nothing across their supply -- the only
    # undecoupled supply pins on the board, and invisible to every
    # simulation block because sensor_differential.cir models an ideal
    # amplifier with no supply pin at all.
    starts = [m.start() for m in re.finditer(r'    \(libpart \(lib ', text)]
    starts.append(text.index("(nets"))
    lib = {}
    for a, b in zip(starts, starts[1:]):
        chunk = text[a:b]
        part = re.search(r'\(part "([^"]+)"\)', chunk).group(1)
        lib[part] = dict((n, (nm, ty)) for n, nm, ty in re.findall(
            r'\(pin \(num "([^"]+)"\) \(name "([^"]*)"\) \(type "([^"]+)"\)',
            chunk))
    part_of = dict(re.findall(
        r'\(comp \(ref "([^"]+)"\).*?\(libsource \(lib "[^"]*"\) '
        r'\(part "([^"]+)"\)', text, re.S))
    net_of = {(r, p): n for n, pins in named for r, p in pins}
    cap_nets = {net_of[(r, p)] for n, pins in named for r, p in pins
                if r.startswith("C")}
    undecoupled, supplies = [], 0
    for ref, part in sorted(part_of.items()):
        for num, (pname, ptype) in lib.get(part, {}).items():
            if ptype != "power_in":
                continue
            net = net_of.get((ref, num))
            if net is None or net == "GND" or pname in ("VSS", "VREFL",
                                                        "GND", "V-"):
                continue
            if (ref, num) in NO_DECOUPLING_NEEDED:
                continue
            supplies += 1
            if net not in cap_nets:
                undecoupled.append(f"{ref} pin {num} ({pname}) on {net}")
    check(f"every supply pin has a capacitor on its net ({supplies} pins)",
          not undecoupled, f"undecoupled: {undecoupled}")

    for rail in MUST_SPAN:
        hit = [p for n, p in named if n == rail]
        n_pins = len(hit[0]) if hit else 0
        check(f"{rail} spans the project ({n_pins} pins)", n_pins > 5)

    with_fp = len(re.findall(r'\(footprint "[^"]+"\)', text))
    checks.append((None, f"footprints assigned: {with_fp} of {len(comps)} "
                         f"-- phase 3 input, not a schematic gate", ""))

    for ok, label, detail in checks:
        mark = "    " if ok is None else ("PASS" if ok else "FAIL")
        # Detail is the failure's evidence, so it prints only on failure --
        # a PASS line ending in "missing: []" is noise that trains the
        # reader to skip the column the FAIL lines need them to read.
        print(f"  {mark}  {label}" + (f"\n          {detail}"
                                      if detail and ok is False else ""))
    print()
    if failed:
        print(f"  {failed} check(s) FAILED")
        return 1
    print(f"  {len(EXPECTED_OPEN)} open items, each named and none silent")
    print("  schematic connectivity OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fail as e:
        print(f"  FAIL  {e}")
        sys.exit(1)
