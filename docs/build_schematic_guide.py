#!/usr/bin/env python3
"""Build docs/pdf/ECU-Schematic-Guide.pdf: docs/schematic-guide.md with the
KiCad schematics plotted fresh and placed after the text that explains them.

    .venv/bin/python docs/build_schematic_guide.py

A line `<!-- sheet prod N -->` (or `proto N`) in the guide puts page N of
that schematic set there. The text between markers is printed with the
same renderer and print rules as the rest of the book (build_pdf.py); the
sheets are plotted by kicad-cli from hw/ecu25kva.kicad_sch and
prototype/prototype.kicad_sch, so the PDF cannot drift from the schematics.

Also refreshes docs/pdf/ECU-Schematics.pdf (production, all sheets) and
writes docs/pdf/ECU-Schematics-Prototype.pdf.

Needs Chrome (as build_pdf.py) and KiCad 10's kicad-cli: on PATH, or KICAD_CLI,
or the Windows default install.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import build_pdf as B  # noqa: E402
from pypdf import PdfReader, PdfWriter  # noqa: E402

GUIDE = HERE / "schematic-guide.md"
OUT = HERE / "pdf" / "ECU-Schematic-Guide.pdf"
SETS = {"prod": ROOT / "hw" / "ecu25kva.kicad_sch",
        "proto": ROOT / "prototype" / "prototype.kicad_sch"}
SHEET_NAMES = {
    "prod": ["Root: the sheet hierarchy", "Power input", "Rails", "MCU (S32K148) and supervisor",
             "Injector stage", "Metering valve and EGR bridge", "Analog sensors", "Speed inputs",
             "Discrete inputs and relays", "CAN", "Connector (Bosch 94-pin)"],
    "proto": ["Prototype root", "Power input", "Rails", "MCU (STM32G474)", "Injector stage",
              "Metering valve and EGR bridge", "Analog sensors", "Speed inputs",
              "Discrete inputs and relays", "CAN", "Lab I/O: terminals and test points"],
}
MARK = re.compile(r"^<!-- sheet (prod|proto) (\d+) -->\s*$", re.M)


def kicad_cli():
    for c in (os.environ.get("KICAD_CLI"), shutil.which("kicad-cli"),
              os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\bin\kicad-cli.exe"),
              "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"):
        if c and os.path.exists(c):
            return c
    sys.exit("kicad-cli not found: install KiCad 10 or set KICAD_CLI")


def plot(cli, sch, out):
    env = dict(os.environ)
    env.setdefault("KICAD_SYMBOL_DIR", os.path.expandvars(r"%USERPROFILE%\opt\kicad7-libs\kicad-symbols-7.0.11"))
    r = subprocess.run([cli, "sch", "export", "pdf", "-o", str(out), str(sch)],
                       capture_output=True, text=True, env=env)
    if r.returncode or not out.exists():
        sys.exit(f"kicad-cli failed on {sch.name}:\n{r.stdout}{r.stderr}")
    return PdfReader(str(out))


def text_pdf(md, n, work):
    """One chunk of the guide, printed like the rest of the book."""
    body = B.md_to_body(md)
    page = (f"<title>Schematic guide</title>{B.FONTS}<style>{B.PRINT_CSS}</style>"
            f'<article class="doc"><p class="docmeta">docs/schematic-guide.md</p>{body}</article>')
    pdf = work / f"text_{n:02d}.pdf"
    B.render(page, pdf, work)
    return PdfReader(str(pdf))


def main():
    if not B.CHROME:
        sys.exit("no Chrome/Chromium found -- it is the renderer")
    cli = kicad_cli()
    work = Path(tempfile.mkdtemp(prefix="schguide_"))
    try:
        sheets = {k: plot(cli, v, work / f"{k}.pdf") for k, v in SETS.items()}
        for k, name in (("prod", "ECU-Schematics.pdf"), ("proto", "ECU-Schematics-Prototype.pdf")):
            w = PdfWriter()
            for p in sheets[k].pages:
                w.add_page(p)
            w.write(str(HERE / "pdf" / name))

        src = GUIDE.read_text(encoding="utf-8")
        w = PdfWriter()
        pos, n, current = 0, 0, None
        for m in list(MARK.finditer(src)) + [None]:
            chunk = src[pos:m.start()] if m else src[pos:]
            if chunk.strip():
                heading = re.search(r"^#{1,3} (.+)$", chunk, re.M)
                first = len(w.pages)
                for p in text_pdf(chunk, n, work).pages:
                    w.add_page(p)
                if heading:
                    current = w.add_outline_item(heading.group(1).strip(), first)
                n += 1
            if m:
                k, i = m.group(1), int(m.group(2))
                if i > len(sheets[k].pages):
                    sys.exit(f"{GUIDE.name}: {k} has {len(sheets[k].pages)} sheets, not {i}")
                w.add_page(sheets[k].pages[i - 1])
                label = ("Production" if k == "prod" else "Prototype") + " schematic: " + SHEET_NAMES[k][i - 1]
                w.add_outline_item(label, len(w.pages) - 1, parent=current if k == "prod" else None)
                pos = m.end()
        OUT.parent.mkdir(exist_ok=True)
        w.write(str(OUT))
        print(f"{OUT.relative_to(ROOT)}: {len(w.pages)} pages "
              f"({len(sheets['prod'].pages)} production + {len(sheets['proto'].pages)} prototype sheets)")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
