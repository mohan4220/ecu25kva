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
    # (The EGR bridge's five ends closed 22 Sep 2026: discrete, two
    #  AUIRS2184S, coast asserted by copper on a shared shutdown.)
    # (/TRIP_LOOP closed 8 Nov 2026: the trip loop had no Bosch pin and
    #  was removed; the trip module opens the main relay's coil feed.)
}

# Open items at the connector that no single-pin rule can see. The power
# ground was one until 8 Nov 2026, when Bosch's terminal diagram put it
# on pins 01/02 (G_G_BAT1/2); POWER_GROUND below now checks it is there.
GND_SENSOR_ONLY = {"8", "30", "44"}
BOUNDARY_OPEN = {}

# Bosch's power scheme (refs/bosch-pinout-md1cs162.md, decisions log 18).
POWER_GROUND = {"1", "2"}

# Nets that must span more than one sheet, because a rail that does not
# is a rail that got disconnected by a rename.
MUST_SPAN = ("GND", "/VBAT_PROT", "/3V3_MCU", "/5V_MAIN", "/12V_GATE")

# Pins that must never share a net: the TPS3850's ~WDO and ~RESET.
MUST_SEPARATE = ((("U302", "8"), ("U302", "9")),)

# A watchdog timeout asserts WDO only, never RESET (TPS3850 SBVS301B
# sec.7.3.6.3), so WDO reaches the gate kill only through a Schottky
# from RESET (anode) to WDO (cathode): WDO low pulls RESET low, the MCU
# resets and GATE_KILL rises; RESET low leaves WDO alone. Separating the
# two nets on 15 Oct 2026 cut that path, and nothing noticed until the
# final review of the prototype branch (17 Oct).
WDO_KILL = (("U302", "9"), ("U302", "8"))       # (RESET, WDO)

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


def pr_ohms(value):
    """'100k' -> 1e5, '4.7k' -> 4700, '0R' -> 0; anything else -> 0."""
    m = re.match(r"^([\d.]+)\s*([RkKM]?)", value or "")
    if not m:
        return 0.0
    return float(m.group(1)) * {"": 1, "R": 1, "k": 1e3, "K": 1e3, "M": 1e6}[m.group(2)]


def export_netlist(path, root=ROOT):
    r = subprocess.run(
        ["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
         "-o", path, root], capture_output=True, text=True)
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
    for m in re.finditer(r'\(comp\s+\(ref "([^"]+)"\)\s*\(value "([^"]*)"\)',
                         text):
        comps[m.group(1)] = m.group(2)
    nets = []
    i = text.index("(nets")
    for b in re.split(r'\n\s*\(net\s', text[i:])[1:]:
        name = re.search(r'\(name "([^"]*)"\)', b).group(1)
        pins = re.findall(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', b)
        nets.append((name, pins))
    return comps, nets


def child_labels(name, folder=HW):
    p = os.path.join(folder, f"{name}.kicad_sch")
    return set(re.findall(r'\(hierarchical_label "([^"]+)"', open(p).read()))


def root_pins(root=ROOT):
    """{sheet name: {pin names}} as the ROOT sheet declares them."""
    text = open(root).read()
    out = {}
    for m in re.finditer(r'\(sheet \(at [^\n]*\n(?:(?!\n  \(sheet ).)*?'
                         r'\(property "Sheetname" "([^"]+)"'
                         r'(?:(?!\n  \(sheet ).)*', text, re.S):
        out[m.group(1)] = set(re.findall(r'\(pin "([^"]+)" \w+ \(at',
                                         m.group(0)))
    return out


def main(root=ROOT, expected_open=None, boundary_open=None,
         connector_ref="J1001", bosch_power=True, bosch_pins=None):
    """Defaults are production's. The prototype passes its own root and
    open items; the power-ground boundary check runs only while a
    boundary item is open."""
    expected_open = EXPECTED_OPEN if expected_open is None else expected_open
    boundary_open = BOUNDARY_OPEN if boundary_open is None else boundary_open
    checks, failed = [], 0

    def check(label, ok, detail=""):
        nonlocal failed
        checks.append((ok, label, detail))
        if not ok:
            failed += 1

    with tempfile.TemporaryDirectory() as td:
        text = export_netlist(os.path.join(td, "p.net"), root)
    comps, nets = parse(text)

    check(f"project netlist exports and annotates cleanly "
          f"({len(comps)} components)", True)

    dup = [r for r, c in collections.Counter(
        re.findall(r'\(comp\s+\(ref "([^"]+)"\)', text)).items() if c > 1]
    check("every reference is unique across all ten sheets",
          not dup, f"duplicates: {dup}" if dup else "")

    named = [(n, p) for n, p in nets if not n.startswith("unconnected-")]
    multi = [n for n, p in named if len(p) > 1]
    single = {n for n, p in named if len(p) < 2}
    check(f"{len(multi)} named nets carry two or more pins", len(multi) > 100)

    unexplained = sorted(single - set(expected_open))
    check("every single-pin net is a recorded open item",
          not unexplained, f"not in EXPECTED_OPEN: {unexplained}")

    gnd_j = set()
    for n, p in nets:
        if n == "GND":
            gnd_j = {pin for ref, pin in p if ref == connector_ref}
    if boundary_open:
        check("power ground is a recorded open item: GND reaches the "
              "connector only through sensor grounds",
              gnd_j == GND_SENSOR_ONLY,
              f"GND connector pins now {sorted(gnd_j, key=int)} -- if a "
              "power ground was added, retire BOUNDARY_OPEN['power ground']")

    stale = sorted(set(expected_open) - single)
    check("no stale exemptions -- an open item that closed must leave "
          "EXPECTED_OPEN", not stale, f"no longer single-pin: {stale}")

    by_sheet = collections.defaultdict(set)
    for m in re.finditer(r'\(comp\s+\(ref "([^"]+)"\).*?'
                         r'\(sheetpath\s+\(names "([^"]*)"', text, re.S):
        by_sheet[m.group(2)].add(m.group(1))
    check(f"components land on {len(by_sheet)} sheet paths",
          len(by_sheet) >= 10, f"paths: {sorted(by_sheet)}")

    declared = root_pins(root)
    for name in sorted(declared):
        want = child_labels(name, os.path.dirname(root))
        have = declared[name]
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
        r'\(comp\s+\(ref "([^"]+)"\).*?\(sheetpath\s+\(names "([^"]*)"',
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
    # Whitespace-tolerant: KiCad 10's kicad-cli writes each element on
    # its own tab-indented line, KiCad 7 wrote them inline. The inline-only
    # pattern found no parts under KiCad 10 and passed on "0 pins" -- a
    # check that cannot see anything must fail, so supplies > 0 is part of
    # it now (8 Nov 2026).
    starts = [m.start() for m in re.finditer(r'\(libpart\s+\(lib ', text)]
    starts.append(text.index("(nets"))
    lib = {}
    for a, b in zip(starts, starts[1:]):
        chunk = text[a:b]
        part = re.search(r'\(part "([^"]+)"\)', chunk).group(1)
        lib[part] = dict((n, (nm, ty)) for n, nm, ty in re.findall(
            r'\(pin\s+\(num "([^"]+)"\)\s+\(name "([^"]*)"\)\s+'
            r'\(type "([^"]+)"\)',
            chunk))
    part_of = dict(re.findall(
        r'\(comp\s+\(ref "([^"]+)"\).*?\(libsource\s+\(lib "[^"]*"\)\s*'
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
          supplies > 0 and not undecoupled,
          f"undecoupled: {undecoupled}" if supplies else
          "no power_in pins parsed -- the netlist format changed")

    # Two open-drain outputs on one net is a wired-OR nobody chose. The
    # supervisor's RESET and WDO were exactly that until 15 Oct 2026:
    # their pullups sat 2.54 mm apart in one column, and one's lead wire
    # ran through the other's pin. Firmware then could not tell a
    # watchdog trip from a rail trip, which is what WDO is for.
    for a, b in MUST_SEPARATE:
        na, nb = net_of.get(a), net_of.get(b)
        check(f"{a[0]} pin {a[1]} and pin {b[1]} are separate nets",
              na is not None and na != nb, f"both on {na}")

    rst, wdo = (net_of.get(p) for p in WDO_KILL)
    path = [r for r, part in part_of.items() if part == "D_Schottky"
            and net_of.get((r, "2")) == rst and net_of.get((r, "1")) == wdo]
    check(f"a watchdog fault reaches the gate kill: a Schottky from "
          f"{rst} to {wdo}", bool(path) and rst != wdo, f"diodes: {path}")

    # -- STOP_KILL (10 Nov 2026): pin 25, the force shutdown, kills the
    # gates in hardware. The inverter (the NMOS whose drain is GATE_KILL)
    # takes its gate from ~RESET through >= 47k, and an NMOS on SW_STOP
    # pulls that gate to ground: no firmware, no MCU reset.
    def ends(name):
        return [n for n in set(net_of.values()) if n.split("/")[-1] == name]
    nmos = [r for r, part in part_of.items() if part == "Q_NMOS_GSD"]
    kill = ends("GATE_KILL")
    inv = [r for r in nmos if net_of.get((r, "3")) in kill]
    kg = net_of.get((inv[0], "1")) if len(inv) == 1 else None
    iso = [r for r, part in part_of.items() if part == "R" and kg and rst
           and {net_of.get((r, "1")), net_of.get((r, "2"))} == {kg, rst}
           and pr_ohms(comps.get(r, "")) >= 47e3]
    stop = ends("SW_STOP")
    pull = [r for r in nmos if kg and net_of.get((r, "1")) in stop
            and net_of.get((r, "3")) == kg and net_of.get((r, "2")) == "GND"]
    check("pin 25 kills the gates in hardware: an NMOS on SW_STOP pulls "
          "the GATE_KILL inverter's gate low, isolated from ~RESET by >= 47k",
          kg is not None and kg != rst and bool(iso) and bool(pull),
          f"inverter {inv}, its gate {kg}, resistor {iso}, puller {pull}")

    for rail in MUST_SPAN:
        hit = [p for n, p in named if n == rail]
        n_pins = len(hit[0]) if hit else 0
        check(f"{rail} spans the project ({n_pins} pins)", n_pins > 5)

    # -- POWER-PATH (8 Oct 2026): the high-current loads left pin 21 --
    # Each feed must leave its own reverse FET and reach its own loads,
    # and VBAT_PROT must not reach them any more. On the injector sheet
    # VBAT_PROT keeps exactly one job: the boost controller's START-UP
    # feed (180 ohm into VDD_BAT, then a Schottky). Once running, the
    # controller runs from its own output (BOOST-SLOPE).
    pins_of = dict(named)
    for rail, load_sheet in (("/VBAT_INJ", "injector"),
                             ("/VBAT_EGR", "metering_egr")):
        # Since 8 Oct 2026 the FET drives {rail}_IN, and a filter
        # inductor joins it to the rail (feed_emi.cir).
        pins = pins_of.get(rail, [])
        raw = pins_of.get("/power_input" + rail + "_IN", [])
        fet = [r for r, _ in raw if comps.get(r) == "SQM120P10-10m1L"
               and sheet_of.get(r) == "power_input"]
        coil = [r for r, _ in pins if comps.get(r) == "XAL1510-103MED"
                and r in {q for q, _ in raw}]
        loads = [r for r, _ in pins if sheet_of.get(r) == load_sheet]
        check(f"{rail} runs from its own reverse FET, through its filter "
              f"inductor, to the {load_sheet} sheet ({len(loads)} load "
              "pins)", len(fet) == 1 and len(coil) == 1 and loads,
              f"FET {fet}, inductor {coil}, loads {loads}")
    prot = pins_of.get("/VBAT_PROT", [])
    egr_on_prot = [r for r, _ in prot if sheet_of.get(r) == "metering_egr"
                   and comps.get(r) == "IPD90N10S4-06"]
    inj_on_prot = [f"{r} {comps.get(r)}" for r, _ in prot
                   if sheet_of.get(r) == "injector"
                   and comps.get(r) != "180R 1W"]
    check("VBAT_PROT no longer feeds the EGR bridge or the injector power "
          "stage", not egr_on_prot and not inj_on_prot,
          f"EGR FETs {egr_on_prot}, injector parts {inj_on_prot}")

    # -- Bosch power (8 Nov 2026, decisions log 18) --------------------
    # No permanent feed: pin 71 wakes, pin 50 closes the main relay, the
    # relay feeds 04/06, 01/02 are ground. Each line below is a way the
    # schematic could quietly keep the old KOEL wiring.
    if bosch_power:
        # Bosch pin -> (ref, pad). Production: the 94-way itself. The
        # prototype passes its screw-terminal positions.
        where = bosch_pins or {p: (connector_ref, p) for p in
                               ("1", "2", "4", "21", "50", "71")}
        jnet = {pin: net_of.get(where[pin]) for pin in where}
        check("power ground: GND reaches connector pins 01 and 02 "
              "(G_G_BAT1/2)", all(jnet[p] == "GND" for p in POWER_GROUND),
              f"pins 01/02 on {jnet['1']} / {jnet['2']}")
        feed = pins_of.get(jnet["4"], [])
        # The 5 A fuse is the only fuse on power_input (its value field
        # carries the MPN once assign_passives has run).
        fuse = [r for r, _ in feed if r.startswith("F")
                and sheet_of.get(r) == "power_input"]
        check("the electronics feed (5 A fuse) runs from pin 04, the main "
              "relay's contact", len(fuse) == 1, f"pin 04 net {jnet['4']}: "
              f"fuses {fuse}")
        p21 = pins_of.get(jnet["21"], [])
        power21 = [r for r, _ in p21 if r[0] in "FLQ"
                   or sheet_of.get(r) == "power_input"]
        check("pin 21 is an input (water in fuel), not a supply",
              jnet["21"] == "/IN_WIF_H" and not power21,
              f"pin 21 net {jnet['21']}, power parts {power21}")
        p50 = pins_of.get(jnet["50"], [])
        sneak = [r for r, _ in p50 if r.startswith("D") and any(
            net_of.get((r, k)) not in (jnet["50"], "GND") for k in ("1", "2"))]
        check("no diode from pin 50 to a supply: its coil is on Term. 30, "
              "so one would power the board through it", not sneak,
              f"diodes {sneak}")
        fets = [r for r, k in p50 if r.startswith("Q") and k == "3"]
        wake = [r for r in fets if any(
            rr.startswith("R") and net_of.get((rr, other)) == jnet["71"]
            for rr, kk in pins_of.get(net_of.get((r, "1")), [])
            for other in ("1", "2") if other != kk)]
        check("pin 50 has two drivers, one gated from pin 71 (wake)",
              len(fets) == 2 and len(wake) == 1,
              f"FETs on pin 50 {fets}, gated from pin 71 {wake}")

    # Every chip R and C is packaged by assign_passives.py. One without a
    # footprint is a part added or re-valued since the map was built.
    fp_of = dict(re.findall(r'\(comp\s+\(ref "([^"]+)"\)\s*\n\s*\(value '
                            r'"[^"]*"\)\s*\(footprint "([^"]*)"\)', text))
    bare = sorted(r for r, v in comps.items()
                  if re.match(r"^[RC]\d", r) and not fp_of.get(r))
    check("every chip resistor and capacitor is packaged -- re-run "
          "assign_passives.py after adding or re-valuing one", not bare,
          f"no footprint: {bare}")

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
    print(f"  {len(expected_open) + len(boundary_open)} open items, each "
          "named and none silent:")
    for k, v in list(expected_open.items()) + list(boundary_open.items()):
        print(f"    {k}: {v}")
    print("  schematic connectivity OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fail as e:
        print(f"  FAIL  {e}")
        sys.exit(1)
