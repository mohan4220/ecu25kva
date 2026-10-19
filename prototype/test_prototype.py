#!/usr/bin/env python3
"""Every prototype test, assert-based.
Run: .venv/bin/python prototype/test_prototype.py [test_name ...]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(HERE, "..", "hw"))


# -- Task 1: pin assignment ------------------------------------------------
def test_pindata_parses():
    from stm32_pins import PINDATA
    assert len(PINDATA) >= 86, len(PINDATA)
    assert "ADC1_IN1" in PINDATA["PA0"]["signals"]


def test_assign_valid():
    import stm32_pins
    assert stm32_pins.check() == [], stm32_pins.check()


def test_gate_pins_float():
    import stm32_pins
    assert "TIM8_CH1" in stm32_pins.PINDATA["PA15"]["signals"]
    bad = dict(stm32_pins.ASSIGN, INJ_LS_1=("PA15", "TIM8_CH1"))
    bad["JTAG_TDI"] = ("PB4", "GPIO_Input")   # free PA15 so only the rule fires
    probs = stm32_pins.check(bad)
    assert any("INJ_LS_1" in p for p in probs), probs


def test_adc_count():
    from stm32_pins import ASSIGN
    adc = {f for _, f in ASSIGN.values() if f.startswith("ADC")}
    assert len(adc) == 17, sorted(adc)


# -- Task 2: the STM32 sheet ------------------------------------------------
def _hlabels(text):
    import re
    return set(re.findall(r'\(hierarchical_label "([^"]+)"', text))


def _label_points(text):
    import re
    return {(float(x), float(y)) for x, y in re.findall(
        r'\((?:hierarchical_label|label) "[^"]+"(?: \(shape \w+\))? '
        r'\(at ([-\d.]+) ([-\d.]+)', text)}


def test_stock_pins():
    from symbols import stock_pins
    p = stock_pins("MCU_ST_STM32G4:STM32G474VETx")
    assert len(p) == 100
    assert p["20"][3] == "PA0"          # LQFP-100 position 20 (ST's XML)


def test_mcu_labels():
    import gen_sheet_mcu_stm32
    prod = _hlabels(open(os.path.join(HERE, "..", "hw", "mcu.kicad_sch")).read())
    assert len(prod) == 42
    got = _hlabels(gen_sheet_mcu_stm32.build().render())
    assert got == prod | {"BOOST_MON"}, (got ^ (prod | {"BOOST_MON"}))


def test_mcu_every_assigned_pin_wired():
    import gen_sheet_mcu_stm32 as g
    from stm32_pins import ASSIGN
    pts = _label_points(g.build().render())
    for sig, (pin, _) in ASSIGN.items():
        end = g.pin_end(pin)
        assert end in pts, (sig, pin, end)


def test_mcu_supplies():
    import gen_sheet_mcu_stm32 as g
    from symbols import stock_pins
    text = g.build().render()
    for num, (_, _, _, name) in stock_pins(g.MCU).items():
        if name.startswith(("VDD", "VSS", "VREF", "VBAT")):
            x, y = g.pin_at(num)
            assert f"(xy {x} {y})" in text, (num, name)


def test_pdn_stm32():
    """The prototype's decoupling (6 x 100 nF + 4.7 uF + production's bulk
    pair) stays under mcu_pdn.cir's own 100 mOhm target at both ends of
    the bulk pair's ESR band, to 100 MHz (the model's validity limit)."""
    import pathlib
    import tempfile
    sys.path.insert(0, os.path.join(HERE, "..", "sim", "lib"))
    import ngrun
    cir = pathlib.Path(HERE, "sim", "mcu_pdn_stm32.cir").read_text()
    wd = pathlib.Path(tempfile.mkdtemp(prefix="pdn_stm32_"))
    ngrun.run(cir, wd)
    d = ngrun.read_wrdata(wd / "mcu_pdn_stm32.dat", ["f", "cold", "warm"])
    for k in ("cold", "warm"):
        peak = max(d[k])
        assert peak < 0.100, (k, peak)
        print(f"  {k}: peak {peak * 1000:.1f} mOhm")


# -- Task 3: lab terminals --------------------------------------------------
def test_lab_labels():
    import gen_sheet_lab_io
    prod = _hlabels(open(os.path.join(HERE, "..", "hw",
                                      "connector.kicad_sch")).read())
    assert len(prod) == 40
    got = _hlabels(gen_sheet_lab_io.build().render())
    assert got == prod | {"TRIP_LOOP"}, got ^ (prod | {"TRIP_LOOP"})


def test_lab_power_ground():
    import gen_sheet_lab_io as g
    gnd = [(ref, pos) for ref, nets in g.TERMINALS.items()
           for pos, net in enumerate(nets, 1) if net == "GND"]
    assert len(gnd) >= 3, gnd
    assert sum(ref == "J1002" for ref, _ in gnd) == 2, gnd


# -- Task 4: the whole schematic --------------------------------------------
def _git(*args):
    import subprocess
    return subprocess.run(["git", *args], cwd=os.path.join(HERE, ".."),
                          capture_output=True, text=True).stdout


def test_hw_untouched():
    import gen_prototype
    before = _git("status", "--porcelain", "hw/")
    gen_prototype.main()
    assert _git("status", "--porcelain", "hw/") == before


def test_production_items_kept():
    import importlib
    import gen_prototype
    for name in gen_prototype.PROD:
        sh = importlib.import_module(f"gen_sheet_{name}").build()
        text = open(os.path.join(HERE, f"{name}.kicad_sch")).read()
        missing = [it for it in sh.items if it not in text]
        assert not missing, (name, len(missing), missing[0][:200])


def test_netlist_gate():
    import check_prototype
    assert check_prototype.main() == 0


def test_tp_nets():
    """Every test point and the BOOST_MON divider land on their nets."""
    import tempfile
    import additions
    import pcb_rules as pr
    with tempfile.TemporaryDirectory() as td:
        _, nets = pr.read_netlist(pr.export_netlist(
            td, root=os.path.join(HERE, "prototype.kicad_sch")))
    on = {r: n.split("/")[-1] for n, v in nets.items() for r, p, _ in v
          if r.startswith("TP")}
    want = {ref: net for ref, (_, net, _) in additions.TEST_POINTS.items()}
    assert on == want, {k: (on.get(k), want.get(k)) for k in want
                        if on.get(k) != want[k]}
    mon = [n for n in nets if n.endswith("BOOST_MON")]
    assert len(mon) == 1 and len(nets[mon[0]]) >= 4, nets.get(mon[0])


# -- Task 5: placement ------------------------------------------------------
BOARD = os.path.join(HERE, "prototype.kicad_pcb")


def test_usb_pads():
    """Every netlist pin of the USB-C receptacle is a pad of its footprint
    (a 14-pin symbol on a 16-pad footprint)."""
    import re
    import tempfile
    import pcb_rules as pr
    with tempfile.TemporaryDirectory() as td:
        comps, nets = pr.read_netlist(pr.export_netlist(
            td, root=os.path.join(HERE, "prototype.kicad_sch")))
    lib, name = comps["J302"]["footprint"].split(":")
    mod = open(os.path.join(pr.FOOTPRINT_DIR, lib + ".pretty",
                            name + ".kicad_mod")).read()
    import proto_rules
    ren = proto_rules.PAD_RENAME.get("J302", {})
    pads = {ren.get(p, p) for p in re.findall(r'\(pad "([^"]*)"', mod)}
    pins = {p for v in nets.values() for r, p, _ in v if r == "J302"}
    assert pins and pins <= pads, pins - pads


def test_placement_clean():
    import check_pcb
    import proto_rules
    assert check_pcb.main(board=BOARD, rules=proto_rules,
                          parity_ok=proto_rules.PARITY_OK,
                          placeholders=("D806",)) == 0


# -- Task 6: routing --------------------------------------------------------
def test_power_nets_poured():
    """Every PWR_HI / HV100 / RTN / PWR_LOOM net has filled copper: the
    high currents ride pours, not tracks. Outer layers, or In2 where the
    power router drew the bar at double width for 1 oz copper."""
    import re
    import tempfile
    import proto_rules as pr
    with tempfile.TemporaryDirectory() as td:
        _, nets = pr.read_netlist(pr.export_netlist(td, pr.ROOT_SCH))
    want = {n for n, c in pr.ASSIGN.items() if n in nets
            and c in ("PWR_HI", "HV100", "RTN", "PWR_LOOM")} | {"GND"}
    text = open(BOARD).read()
    filled = set()
    for z in re.split(r"\n\t\(zone", text)[1:]:
        net = re.search(r'\(net_name "([^"]*)"\)', z) or \
            re.search(r'\(net "([^"]*)"\)', z)
        if net and re.search(r'\(filled_polygon\s*\(layer "(?:[FB]|In2)\.Cu"\)', z):
            filled.add(net.group(1))
    assert want <= filled, sorted(want - filled)


def test_power_pours_connect():
    """Owner, 16 Oct: pours carry the current. With every routed track
    removed (vias kept), the power parts' pads on each net must still be
    joined, by pour copper alone: no thin track carries load current."""
    import json
    import re
    import subprocess
    import tempfile
    import proto_rules as pr
    text = open(BOARD).read()
    power = set()
    for b in re.split(r"\n\t\(footprint ", text)[1:]:
        name = b.split('"')[1].split(":")[-1]
        ref = re.search(r'\(property "Reference" "([^"]+)"', b).group(1)
        val = re.search(r'\(property "Value" "([^"]*)"', b).group(1)
        if pr.POWER_PART.search(name) or (ref.startswith("R") and "mOhm" in val):
            power.add(ref)
    stripped = re.sub(r"\n\t\((?:segment|arc)\b.*?\n\t\)", "", text, flags=re.S)
    with tempfile.TemporaryDirectory() as d:
        brd = os.path.join(d, "p.kicad_pcb")
        open(brd, "w").write(stripped)
        r = subprocess.run([pr.KICAD_PY, os.path.join(HERE, "gen_board.py"),
                            "clusters", brd], capture_output=True, text=True)
    groups = json.loads(r.stdout.strip().splitlines()[-1])
    bad = []
    for net, gs in groups.items():
        if net != "GND" and pr.ASSIGN.get(net) not in pr.POUR_CLASSES:
            continue
        hold = [g for g in gs if any(k.split(".")[0] in power for k in g)]
        if len(hold) > 1:
            bad.append(f"{net}: {len(hold)} islands, " + " | ".join(
                ",".join(g[:3]) for g in hold[:3]))
    assert not bad, f"{len(bad)} power pads joined only by tracks: {bad[:4]}"


def test_no_necks():
    """No pour run keeps less than NECK_MIN of its width filled away from
    its own pads (necks(), the same judge finish_pass uses), so no track
    or via the router added has pinched a pour."""
    import subprocess
    import proto_rules as pr
    r = subprocess.run([pr.KICAD_PY, os.path.join(HERE, "gen_board.py"), "necks"],
                       capture_output=True, text=True, env={**os.environ, "BOARD": BOARD})
    assert r.stdout.strip().splitlines()[-1:] == ["no necks"], r.stdout[-500:] + r.stderr[-500:]


def test_inputs_committed():
    """The router input and the power router's runs, which these tests
    read, are committed: a fresh clone runs every test."""
    for f in ("power.json", "prototype.dsn"):
        ign = _git("check-ignore", os.path.join("prototype", "build", f))
        assert not ign.strip(), f"prototype/build/{f} is gitignored"


def test_track_power_widths():
    """A power-class net with no pour rides tracks: every one of them is
    wide enough for the net's TRACK_AMPS on its own layer, and no such net
    is missing from the table."""
    import re
    import proto_rules as pr
    text = open(BOARD).read()
    poured = set(re.findall(r'\n\t\(zone\n\t\t\(net "([^"]*)"\)', text))
    want = {n for n, c in pr.ASSIGN.items() if c in pr.POUR_CLASSES} - poured
    tracks = re.findall(r'\n\t\(segment\n.*?\(width ([\d.]+)\)\n\t\t\(layer "([^"]+)"\)'
                        r'\n.*?\(net "([^"]*)"\)', text, flags=re.S)
    want &= {n for _, _, n in tracks}
    assert want <= set(pr.TRACK_AMPS), sorted(want - set(pr.TRACK_AMPS))
    cu = dict(pr.STACKUP)
    thin = {}
    for w, layer, net in tracks:
        if net in pr.TRACK_AMPS:
            need = pr.width_mm(pr.TRACK_AMPS[net], cu[layer], layer in ("F.Cu", "B.Cu"))
            if float(w) < need - 1e-6:
                thin.setdefault((net, layer, need), []).append(float(w))
    assert not thin, {k: (len(v), min(v)) for k, v in thin.items()}


def test_router_sees_pours():
    """Freerouting loads a DSN plane as a conduction area that is no
    obstacle to other nets, so it would route signals across the pours.
    In its input each pour run is a fixed wire and every pour via fixed:
    copper it must route around and may not rip up."""
    import collections
    import json
    import re
    dsn = open(os.path.join(HERE, "build", "prototype.dsn")).read()
    routes = json.load(open(os.path.join(HERE, "build", "power.json")))["routes"]
    fixed = collections.Counter(n.strip('"') for n in re.findall(
        r'\(wire \(path \S+ \d+ [^)]*\)\(net ("[^"]+"|\S+?)\)\(type fix\)', dsn))
    short = {n: (fixed[n], sum(a != b for _, a, b, _ in r["segs"]))
             for n, r in routes.items()
             if fixed[n] < sum(a != b for _, a, b, _ in r["segs"])}
    assert not short, f"pour runs not fixed in the router input: {short}"
    loose = re.findall(r"\(via [^\n]*\(type route\)", dsn)
    assert not loose, f"{len(loose)} vias the router may rip up"
    # L2 is the ground plane, never cut: the router put tracks on it (run
    # 3, INJ_HS_A 46 mm), and no layer setting stops it without blocking
    # the vias through it. So the router sees three layers, and ground,
    # already joined to the plane by its own vias, as a one-pin net
    assert "In1.Cu" not in dsn, "the router can route on In1.Cu"
    gnd = re.search(r"\(net GND\s*\(pins([^()]*)\)", dsn)
    assert gnd and len(gnd.group(1).split()) == 1, "the router routes GND"


def test_pour_copper_clean():
    """The copper gen_board lays itself (pour bars, their vias, the GND
    floods) breaks no rule: same-net bars overlap at distinct priorities,
    every pour via joins two layers and clears every hole and other net,
    ground floods leave no islands."""
    import json
    import subprocess
    import tempfile
    import proto_rules as pr
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([pr.KICAD_CLI, "pcb", "drc", "--format", "json",
                        "-o", os.path.join(d, "r.json"), BOARD], capture_output=True)
        rep = json.load(open(os.path.join(d, "r.json")))
    ours = ("zones_intersect", "hole_to_hole", "via_dangling")
    bad = [v["description"] for v in rep["violations"] if v["type"] in ours]
    bad += [v["description"] for v in rep["violations"] if v["type"] == "clearance"
            and all(i["description"].startswith(("Via", "Pad", "Zone")) for i in v["items"])]
    # every ground pad reaches the L2 plane through its own via, so ground
    # is never left to the signal router
    bad += [" / ".join(i["description"] for i in v["items"])
            for v in rep["unconnected_items"]
            if any("[GND]" in i["description"] for i in v["items"])]
    assert not bad, f"{len(bad)} faults in the pours' own copper: {bad[:4]}"


def test_routed():
    import check_pcb
    import proto_rules
    assert check_pcb.main(board=BOARD, rules=proto_rules,
                          parity_ok=proto_rules.PARITY_OK,
                          placeholders=("D806",), require_routed=True) == 0


# -- Task 7: fab files ------------------------------------------------------
def test_fab_files():
    import csv
    import glob
    fab = os.path.join(HERE, "fab")
    gbr = glob.glob(os.path.join(fab, "gerbers", "*.g*"))
    assert len(gbr) >= 9, sorted(map(os.path.basename, gbr))
    assert glob.glob(os.path.join(fab, "gerbers", "*.drl")), "no drill file"
    text = open(BOARD).read()
    placed = text.count('\n\t(footprint "')
    smd_tht = len(list(csv.reader(open(os.path.join(fab, "positions.csv"))))) - 1
    assert 0 < smd_tht <= placed, (smd_tht, placed)
    rows = list(csv.DictReader(open(os.path.join(fab, "bom.csv"))))
    refs = sum(len(r["Refs"].split(",")) for r in rows)
    assert refs >= smd_tht, (refs, smd_tht)


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(n for n in globals() if n.startswith("test_"))
    for n in names:
        globals()[n]()
        print("ok", n)
    print("prototype ok")
