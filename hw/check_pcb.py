#!/usr/bin/env python3
"""Check the generated board against the schematic and pcb_rules.

Run: .venv/bin/python hw/check_pcb.py [--board path/to/x.kicad_pcb]
A --board copy needs its .kicad_pro and .kicad_dru beside it, same name.
Exit status 1 on any FAIL. Unrouted connections are counted, not failed.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_rules as pr  # noqa: E402

DRC_NAMED = ("clearance", "courtyards_overlap", "copper_edge_clearance",
             "hole_clearance")
# Schematic-parity differences that are expected: the two parts whose
# footprint comes from gen_pcb's PLACEHOLDER map, not the schematic.
PARITY_OK = {("footprint_symbol_mismatch", "J1001"),
             ("footprint_symbol_mismatch", "D806")}


def read_board(path):
    """-> {ref: {"nets": set, "fab": [text on F.Fab]}}"""
    text = open(path).read()
    fps = {}
    for block in re.split(r"\n\t\(footprint ", text)[1:]:
        block = re.split(r"\n\t\((?!\t)", block)[0]     # up to the next item
        ref = re.search(r'\(property "Reference" "([^"]+)"', block).group(1)
        fab = re.findall(r'\(fp_text user "([^"]*)"\s*\(at[^\n]*\)\s*'
                         r'\(layer "F\.Fab"\)', block)
        path = re.search(r'\(path "([^"]*)"\)', block)
        fps[ref] = {"nets": set(re.findall(r'\(net "([^"]*)"\)', block)),
                    "fab": fab, "path": path.group(1) if path else ""}
    return fps


def drc(board):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "drc.json")
        r = subprocess.run([pr.KICAD_CLI, "pcb", "drc", "--format", "json",
                            "--severity-all", "--schematic-parity",
                            "-o", out, board],
                           capture_output=True, text=True)
        if not os.path.exists(out):
            raise SystemExit(f"kicad-cli drc failed:\n{r.stdout}\n{r.stderr}")
        rep = json.load(open(out))
    # Parity is reported at every severity; DRC counts errors only.
    rep["violations"] = [v for v in rep["violations"]
                         if v["severity"] == "error"]
    return rep


def main():
    board = os.path.join(pr.HW, "ecu25kva.kicad_pcb")
    if "--board" in sys.argv:
        board = sys.argv[sys.argv.index("--board") + 1]
    base = os.path.splitext(board)[0]
    failed = 0

    def check(label, ok, detail=""):
        nonlocal failed
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))

    with tempfile.TemporaryDirectory() as d:
        comps, nets = pr.read_netlist(pr.export_netlist(d))
    fps = read_board(board)

    check("footprints", len(fps) == len(comps) and set(fps) == set(comps),
          f"{len(fps)} on the board, {len(comps)} in the schematic; "
          f"differ: {sorted(set(fps) ^ set(comps))[:10]}")
    # KiCad's parity check falls back to matching by reference, so it
    # misses a stale link; Update PCB from Schematic does not.
    stale = sorted(r for r in fps if r in comps and fps[r]["path"] != comps[r]["path"])
    check("footprints linked to their symbols (path)", not stale,
          f"{len(stale)} stale: {stale[:10]}")
    for ref in ("J1001", "D806"):
        fab = fps.get(ref, {}).get("fab", [])
        check(f"{ref} flagged PLACEHOLDER on F.Fab",
              any("PLACEHOLDER" in t for t in fab), str(fab))

    on_board = set().union(*(f["nets"] for f in fps.values()))
    missing = sorted(set(nets) - on_board)
    check("nets", not missing, f"{len(nets)} in the schematic; missing "
          f"{missing[:10]}")

    pro = json.load(open(base + ".kicad_pro"))["net_settings"]
    patterns = {p["pattern"]: p["netclass"] for p in pro["netclass_patterns"]}
    assign, unclassified, stale = pr.classify(set(nets), pr.power_nets(comps, nets))
    wrong = sorted(n for n, c in assign.items() if patterns.get(n) != c)
    check("classes in the project file", not wrong, f"wrong or missing: {wrong[:10]}")
    check("power nets all classified", not unclassified, str(unclassified))
    check("no stale class assignments", not stale, str(stale))

    classes = {c["name"]: c for c in pro["classes"]}
    bad = [n for n, c in pr.CLASSES.items()
           if n not in classes or classes[n]["track_width"] != c["track_width"]
           or classes[n]["clearance"] != c["clearance"]]
    check("class widths and clearances", not bad, str(bad))
    for n in [n for n, c in pr.CLASSES.items() if c.get("amps")]:
        print(f"      {n:8} {pr.CLASSES[n]['amps']:>5} A -> "
              f"{pr.CLASSES[n]['track_width']} mm outer")

    # kicad-cli drops a rules file it cannot parse without a word, so
    # prove it is the one pcb_rules generates.
    dru = base + ".kicad_dru"
    check("custom rules file is pcb_rules.DRU",
          os.path.exists(dru) and open(dru).read() == pr.DRU)

    def items(vs):
        return "; ".join(v["description"] + ": " + " / ".join(
            i["description"] for i in v["items"]) for v in vs[:3])

    rep = drc(board)
    for kind in DRC_NAMED:
        hits = [v for v in rep["violations"] if v["type"] == kind]
        check(f"DRC {kind}", not hits, items(hits))
    other = [v for v in rep["violations"] if v["type"] not in DRC_NAMED]
    check("DRC, every other error (shorts, mask bridges ...)", not other,
          items(other))
    parity = [v for v in rep.get("schematic_parity", [])
              if (v["type"], v["items"][0]["description"].split()[-1])
              not in PARITY_OK]
    check("schematic parity (nets per pad, fields, footprints)", not parity,
          f"{len(parity)}: {items(parity)}")
    print(f"INFO  unrouted connections: {len(rep.get('unconnected_items', []))}")

    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
