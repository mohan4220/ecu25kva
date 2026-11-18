"""The prototype PCB as a printed drawing set: docs/pdf/ECU-PCB-Prototype.pdf.

A3 landscape pages, the board at 1:1:
  1  cover: board facts, layer stack, 3D view of the top
  2  floor plan: where each circuit block sits, coloured by schematic sheet
  3  connections between blocks: every net that leaves its block
  4  terminals: every connector pin and its net
  5  top assembly (silkscreen + fab), 6 all copper layers together
  7-10  the four copper layers, F.Cu, In1.Cu, In2.Cu, B.Cu
  11 3D views of the bottom and at an angle

Everything comes from prototype/prototype.kicad_pcb: kicad-cli plots the
layers and renders the 3D views; KiCad's own Python (pcbnew) reads the
footprints, blocks and nets. Run with the repo's Python:

    CHROME=... .venv/Scripts/python.exe docs/draw_pcb.py

Needs KiCad 10 (kicad-cli and its python.exe, found as build_schematic_guide
finds kicad-cli, or set KICAD_CLI / KICAD_PYTHON) and Chrome (as build_pdf).
"""
import html
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BOARD = ROOT / "prototype" / "prototype.kicad_pcb"
OUTDIR = HERE / "pcb"
PDF = HERE / "pdf" / "ECU-PCB-Prototype.pdf"

# schematic sheet -> (panel number on ECU-System-Circuit.pdf, title, colour)
BLOCKS = {
    "power_input": ("1", "Power input", "#e67e22"),
    "rails": ("2", "Rails", "#d4ac0d"),
    "mcu_stm32": ("3", "MCU STM32G474 + kill path", "#4f6d7a"),
    "injector": ("4", "Injector stage", "#c0392b"),
    "metering_egr": ("5", "Metering valve + EGR bridge", "#8e44ad"),
    "sensors_analog": ("6", "Analog sensors", "#29a19c"),
    "speed_inputs": ("7", "Speed inputs", "#2e86de"),
    "discrete_io": ("8", "Discrete inputs + relays", "#27ae60"),
    "can": ("9", "CAN", "#6d4c41"),
    "lab_io": ("10", "Lab terminals (prototype only)", "#7f8c8d"),
}


# ------------------------------------------------------------- KiCad side

def dump(board, out):
    """Runs under KiCad's python: write footprints and nets as JSON."""
    import pcbnew
    b = pcbnew.LoadBoard(str(board))
    mm = pcbnew.ToMM
    bb = b.GetBoardEdgesBoundingBox()
    data = {"board": [mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetWidth()), mm(bb.GetHeight())],
            "fps": [], "tracks": 0, "vias": 0, "zones": len(list(b.Zones())),
            "nets": b.GetNetCount(), "layers": b.GetCopperLayerCount(),
            "thickness": mm(b.GetDesignSettings().GetBoardThickness())}
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            data["vias"] += 1
        else:
            data["tracks"] += 1
    for fp in b.GetFootprints():
        try:
            r = fp.GetBoundingBox(False, False)
        except TypeError:
            r = fp.GetBoundingBox()
        sheet = fp.GetSheetname().strip("/").split("/")[0] or "root"
        pads = [[p.GetNumber(), p.GetNetname()] for p in fp.Pads()]
        data["fps"].append({
            "ref": fp.GetReference(), "value": fp.GetValue(), "sheet": sheet,
            "side": "B" if fp.GetLayer() == pcbnew.B_Cu else "F",
            "x": mm(fp.GetPosition().x), "y": mm(fp.GetPosition().y),
            "bbox": [mm(r.GetX()), mm(r.GetY()), mm(r.GetWidth()), mm(r.GetHeight())],
            "pads": pads})
    Path(out).write_text(json.dumps(data), encoding="utf-8")


# ------------------------------------------------------------- tools

def find(env, names):
    for c in [os.environ.get(env)] + names:
        if c and (shutil.which(c) or Path(c).exists()):
            return shutil.which(c) or c
    sys.exit(f"not found: {names[0]} (set {env})")


KDIR = os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\bin")


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"failed: {' '.join(map(str, cmd))}\n{r.stdout}{r.stderr}")


def plot_svg(cli, layers, out, bw=False):
    cmd = [cli, "pcb", "export", "svg", "--mode-single", "-l", ",".join(layers),
           "--page-size-mode", "2", "--exclude-drawing-sheet", "--drill-shape-opt", "1",
           "-o", out, BOARD]
    if bw:
        cmd.insert(5, "--black-and-white")
    run(cmd)
    # keep the real size (mm) but let CSS scale it
    s = out.read_text(encoding="utf-8")
    return s[s.index("<svg"):]


def render(cli, out, side="top", rotate=None, zoom="1.35"):
    if out.exists():
        return
    cmd = [cli, "pcb", "render", "--side", side, "--quality", "high", "-w", "3000", "-h", "2000",
           "--background", "opaque", "--zoom", zoom, "-o", out, BOARD]
    if rotate:
        cmd[5:5] = ["--rotate", rotate, "--perspective"]
    run(cmd)


# ------------------------------------------------------------- pages

def floorplan_svg(d):
    bx, by, bw, bh = d["board"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{bw}mm" height="{bh}mm" '
           f'viewBox="{bx} {by} {bw} {bh}" style="background:#f7f7f2">',
           f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="none" stroke="#222" stroke-width="0.6"/>']
    groups = {}
    for f in d["fps"]:
        groups.setdefault(f["sheet"], []).append(f)
        x, y, w, h = f["bbox"]
        col = BLOCKS.get(f["sheet"], ("", "", "#999"))[2]
        op = "0.85" if f["side"] == "F" else "0.35"
        dash = '' if f["side"] == "F" else ' stroke-dasharray="0.6,0.4"'
        out.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{col}" '
                   f'fill-opacity="{op}" stroke="#222" stroke-width="0.08"{dash}/>')
        if w * h > 60 or f["ref"].startswith(("J", "U")):
            fs = 1.6 if w * h > 60 else 1.1
            out.append(f'<text x="{x + w / 2:.2f}" y="{y + h / 2 + fs / 3:.2f}" font-size="{fs}" '
                       f'text-anchor="middle" font-family="Arial" fill="#000">{html.escape(f["ref"])}</text>')
    # block names at the centre of mass of each block, on a white tab
    for sheet, fps in groups.items():
        if sheet == "lab_io":
            continue
        n, title, col = BLOCKS.get(sheet, ("?", sheet, "#999"))
        cx = sum(f["x"] for f in fps) / len(fps)
        cy = sum(f["y"] for f in fps) / len(fps)
        label = f"{n}  {title}"
        w = 1.9 * len(label) + 4
        out.append(f'<rect x="{cx - w / 2:.1f}" y="{cy - 3.4:.1f}" width="{w:.1f}" height="5.2" rx="1" '
                   f'fill="#fff" fill-opacity="0.92" stroke="{col}" stroke-width="0.6"/>')
        out.append(f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="3.2" font-weight="bold" text-anchor="middle" '
                   f'font-family="Arial" fill="{col}">{html.escape(label)}</text>')
    out.append("</svg>")
    return "".join(out)


def connector_nets(d):
    rows = []
    for f in sorted(d["fps"], key=lambda f: f["ref"]):
        if not f["ref"].startswith("J"):
            continue
        for num, net in sorted(f["pads"], key=lambda p: (len(p[0]), p[0])):
            rows.append((f["ref"], f["value"], num, net.lstrip("/") or "(not connected)"))
    return rows


def crossing_nets(d):
    nets = {}
    for f in d["fps"]:
        for _, net in f["pads"]:
            if net:
                nets.setdefault(net, set()).add(f["sheet"])
    rows = []
    for net, sheets in sorted(nets.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(sheets) < 2:
            continue
        rows.append((net.lstrip("/"), sorted(sheets, key=lambda s: int(BLOCKS.get(s, ("99",))[0]))))
    return rows


def chip(sheet):
    n, title, col = BLOCKS.get(sheet, ("?", sheet, "#999"))
    return f'<span class="chip" style="background:{col}">{n}</span>'


CSS = """
@page { size: 420mm 297mm; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: 'Segoe UI', Arial, sans-serif; color: #111; }
.page { width: 420mm; height: 297mm; padding: 10mm 12mm 26mm; position: relative; page-break-after: always;
        overflow: hidden; }
.page:last-child { page-break-after: auto; }
h1 { font-size: 22pt; margin: 0 0 2mm; }
h2 { font-size: 15pt; margin: 0 0 2mm; }
p { font-size: 10pt; margin: 0 0 2mm; line-height: 1.35; }
.tb { position: absolute; left: 12mm; right: 12mm; bottom: 8mm; height: 14mm; border: 0.5mm solid #222;
      display: grid; grid-template-columns: 2.2fr 1.6fr 1fr 0.8fr; font-size: 9pt; }
.tb div { border-left: 0.3mm solid #222; padding: 1.2mm 2mm; }
.tb div:first-child { border-left: none; }
.tb b { display: block; font-size: 11pt; }
.board { display: block; margin: 0 auto; }
.board svg { width: 300mm; height: auto; display: block; margin: 0 auto; border: 0.2mm solid #bbb; }
.fit svg { width: auto; height: 205mm; }
.cols { columns: 3; column-gap: 6mm; font-size: 8pt; }
.cols4 { columns: 4; column-gap: 5mm; font-size: 7.6pt; }
table { border-collapse: collapse; width: 100%; }
td, th { border-bottom: 0.2mm solid #ccc; padding: 0.35mm 1mm; text-align: left; vertical-align: top; }
th { background: #eee; }
tr { break-inside: avoid; }
.chip { display: inline-block; min-width: 4.2mm; padding: 0 0.8mm; border-radius: 1mm; color: #fff;
        font-weight: 700; text-align: center; margin-right: 0.6mm; font-size: 7pt; }
.legend span { display: inline-block; margin: 0 4mm 1mm 0; font-size: 9.5pt; }
.legend i { display: inline-block; width: 4mm; height: 4mm; vertical-align: -0.7mm; margin-right: 1mm;
            border: 0.2mm solid #222; }
.grid2 { display: grid; grid-template-columns: 1.35fr 1fr; gap: 8mm; }
.facts td { font-size: 10pt; padding: 0.8mm 1.5mm; }
img { max-width: 100%; display: block; }
"""


def title_block(n, total, name, scale="1:1"):
    return (f"<div class='tb'><div><b>Genset ECU 25 kVA: prototype PCB</b>{html.escape(name)}</div>"
            f"<div>prototype/prototype.kicad_pcb<br>STM32G474 · 4 layers · Bosch MD1CS162 circuits</div>"
            f"<div>Scale {scale} on A3<br>units mm</div><div>Sheet {n} of {total}</div></div>")


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--dump":
        dump(sys.argv[2], sys.argv[3])
        return
    sys.path.insert(0, str(HERE))
    import build_pdf as B
    if not B.CHROME:
        sys.exit("no Chrome/Chromium found -- it is the renderer")
    cli = find("KICAD_CLI", ["kicad-cli", os.path.join(KDIR, "kicad-cli.exe")])
    kpy = find("KICAD_PYTHON", [os.path.join(KDIR, "python.exe")])
    OUTDIR.mkdir(exist_ok=True)
    js = OUTDIR / "board.json"
    run([kpy, __file__, "--dump", BOARD, js])
    d = json.loads(js.read_text(encoding="utf-8"))

    edge = "Edge.Cuts"
    svgs = {
        "top": plot_svg(cli, ["F.Silkscreen", "F.Fab", edge], OUTDIR / "top_assembly.svg", bw=True),
        "all": plot_svg(cli, ["B.Cu", "In2.Cu", "F.Cu", edge], OUTDIR / "all_copper.svg"),
    }
    copper = [("F.Cu", "Top copper: most signal tracks, the battery, boost and injector pours, and a ground pour around them"),
              ("In1.Cu", "Inner 1: one solid ground plane (GND only, no tracks)"),
              ("In2.Cu", "Inner 2: signal tracks, plus battery (VBAT_PROT, V_BAT_1R) and injector pours"),
              ("B.Cu", "Bottom copper, seen through from the top: signals, and pours doubling the high-current paths")]
    for lay, _ in copper:
        svgs[lay] = plot_svg(cli, [lay, edge], OUTDIR / f"{lay.replace('.', '_')}.svg")
    for name, side, rot in (("3d_top.png", "top", None), ("3d_bottom.png", "bottom", None),
                            ("3d_angle.png", "top", "-40,0,-25")):
        render(cli, OUTDIR / name, side, rot)

    pages = []
    names = ["Cover", "Floor plan: the circuit blocks", "Connections between blocks",
             "Terminals and connector pins", "Top assembly", "All copper layers together"] + \
            [c[0] for c in copper] + ["3D views"]
    total = len(names)
    tb = lambda: title_block(len(pages) + 1, total, names[len(pages)])  # noqa: E731

    # 1 cover
    bx, by, bw, bh = d["board"]
    counts = {}
    for f in d["fps"]:
        counts[f["sheet"]] = counts.get(f["sheet"], 0) + 1
    blocks = "".join(f"<tr><td>{chip(s)} {html.escape(BLOCKS[s][1])}</td><td>{counts.get(s, 0)}</td></tr>"
                     for s in sorted(BLOCKS, key=lambda s: int(BLOCKS[s][0])))
    facts = [("Board", f"{bw:.0f} × {bh:.0f} mm, {d['thickness']:.1f} mm FR-4 (Tg 170)"),
             ("Copper", f"{d['layers']} layers: outer 2 oz, inner 1 oz"),
             ("Stack-up", "F.Cu signal + power · In1.Cu solid GND · In2.Cu signal + power · B.Cu signal + power"),
             ("Parts", f"{len(d['fps'])} footprints"),
             ("Routing", f"{d['tracks']} tracks, {d['vias']} vias, {d['zones']} copper pours, {d['nets']} nets, "
                         "0 unrouted"),
             ("Fab files", "prototype/fab/: Gerbers, drill, BOM, positions"),
             ("Circuits", "the production circuits (Bosch MD1CS162 pinout); prototype MCU STM32G474, "
                          "screw terminals instead of the 94-pin connector")]
    ft = "".join(f"<tr><td><b>{k}</b></td><td>{html.escape(v)}</td></tr>" for k, v in facts)
    pages.append(f"<div class='page'><h1>Genset ECU (25 kVA): the prototype PCB, every circuit, routed</h1>"
                 f"<p>Drawing set made from the KiCad board. The block numbers match the panels of "
                 f"<b>ECU-System-Circuit.pdf</b> (the circuit with values) and the sheets of "
                 f"<b>ECU-Schematics-Prototype.pdf</b>.</p><div class='grid2'>"
                 f"<div><img src='3d_top.png'></div><div><table class='facts'>{ft}</table><br>"
                 f"<h2>Blocks</h2><table class='facts'><tr><th>block</th><th>parts</th></tr>{blocks}</table>"
                 f"</div></div>{tb()}</div>")

    # 2 floor plan
    leg = "".join(f"<span><i style='background:{c}'></i>{n} {html.escape(t)}</span>"
                  for n, t, c in sorted(BLOCKS.values(), key=lambda v: int(v[0])))
    pages.append(f"<div class='page'><h2>Floor plan: where each circuit sits</h2>"
                 f"<p class='legend'>{leg}</p><p>Each part is drawn as its outline, coloured by its schematic "
                 f"sheet; every part is on the top side. Grey: the lab screw terminals J1001–J1009. High current (power input, injector, "
                 f"metering/EGR) stays on the left near its terminals; the MCU and the analog front ends sit "
                 f"on the right, away from the switching loops.</p>"
                 f"<div class='board'>{floorplan_svg(d)}</div>{tb()}</div>")

    # 3 connections between blocks
    cr = crossing_nets(d)
    rows = "".join(f"<tr><td>{html.escape(n)}</td><td>{''.join(chip(s) for s in ss)}</td></tr>" for n, ss in cr)
    pages.append(f"<div class='page'><h2>Connections between blocks ({len(cr)} nets)</h2>"
                 f"<p>Every net that joins two or more blocks, and the blocks it joins (numbers as on the floor "
                 f"plan). These are the named wires of ECU-System-Circuit.pdf; on the board they are the tracks "
                 f"of sheets 7–10. Nets inside one block are not listed.</p>"
                 f"<div class='cols4'><table><tr><th>net</th><th>blocks</th></tr>{rows}</table></div>{tb()}</div>")

    # 4 terminals
    cn = connector_nets(d)
    rows = "".join(f"<tr><td>{r}</td><td>{p}</td><td>{html.escape(n)}</td></tr>" for r, _, p, n in cn)
    vals = sorted({(r, v) for r, v, _, _ in cn})
    pages.append(f"<div class='page'><h2>Terminals and connector pins</h2>"
                 f"<p>Connectors: {html.escape(', '.join(r if r == v else f'{r} {v}' for r, v in vals))}. "
                 f"J1001–J1009 are the lab screw terminals (prototype only; production uses the Bosch "
                 f"94-pin J1001).</p>"
                 f"<div class='cols4'><table><tr><th>ref</th><th>pin</th><th>net</th></tr>{rows}</table></div>"
                 f"{tb()}</div>")

    # 5, 6 assembly
    pages.append(f"<div class='page'><h2>Top assembly: silkscreen and part outlines (every part is on "
                 f"this side)</h2>"
                 f"<div class='board'>{svgs['top']}</div>{tb()}</div>")
    pages.append(f"<div class='page'><h2>All copper layers together: every connection on the board</h2>"
                 f"<p>F.Cu red (the red background is its ground pour), In2.Cu orange, B.Cu blue. In1.Cu, the solid "
                 f"ground plane, is "
                 f"left out so the tracks show. All {len(d['fps'])} parts are on the top side; the bottom carries "
                 f"copper only.</p><div class='board'>{svgs['all']}</div>{tb()}</div>")
    # 7-10 copper
    for lay, what in copper:
        pages.append(f"<div class='page'><h2>{lay}: {html.escape(what)}</h2>"
                     f"<div class='board'>{svgs[lay]}</div>{tb()}</div>")
    # 11 3D
    pages.append(f"<div class='page'><h2>3D views</h2><div class='grid2'><img src='3d_angle.png'>"
                 f"<img src='3d_bottom.png'></div>{tb()}</div>")

    page = f"<title>ECU prototype PCB</title><style>{CSS}</style>{''.join(pages)}"
    (OUTDIR / "pcb.html").write_text(page, encoding="utf-8")
    B.render(page, PDF, OUTDIR)
    print(f"{PDF.relative_to(ROOT)} written ({total} sheets); plots in {OUTDIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
