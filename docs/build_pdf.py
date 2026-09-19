#!/usr/bin/env python3
"""Build the whole project as PDFs -- one per document, plus one bible.

    .venv/bin/python docs/build_pdf.py

Everything lands in docs/pdf/. The per-document PDFs are for sending
someone a single memo; ECU-Bible.pdf is every document in reading order
behind a cover page, bookmarked so the PDF reader's outline pane works
as the table of contents.

How it works, and why this way:

  Markdown documents are converted to HTML here, then printed. The
  handbook pages are already HTML and are printed as they stand -- a
  temporary copy with print.css injected, never an edit to the source.
  So there is exactly one description of each document in the repo, and
  the PDF cannot drift from the page.

  Chrome is the renderer. It is the only engine on this machine that
  handles the handbook's inline SVG schematics, CSS custom properties
  and flex layout correctly; wkhtmltopdf's ancient WebKit does not, and
  neither pandoc nor LibreOffice sees the CSS at all.

  Chrome follows the viewer's colour scheme, and the handbook ships a
  dark theme. A PDF has no viewer preference, so each temporary copy
  stamps data-theme="light" on the root element before rendering -- the
  same attribute a reader's theme toggle would set.
"""
import html
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import markdown
from pypdf import PdfWriter

DOCS = pathlib.Path(__file__).resolve().parent
ROOT = DOCS.parent
OUT = DOCS / "pdf"
PRINT_CSS = (DOCS / "print.css").read_text()

CHROME = shutil.which("google-chrome") or shutil.which("chromium") \
    or shutil.which("chromium-browser")

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Archivo:wght@500;600;700&family=JetBrains+Mono:wght@400;500;700&'
    'family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">'
)

# Reading order. This is the order of the bible and of the cover's contents
# list: the two documents you read to understand the machine, then the spec
# that binds the design, then the research the spec rests on, then the plan.
#   (output stem, source path relative to docs/, title, one-line gloss)
BOOK = [
    ("00-status", "status.md", "Build Status",
     "What is done, what is not, and what each gap is waiting on"),
    ("01-handbook", "handbook/index.html", "Field Handbook",
     "The machine, its interface, the circuits in narrative, and how to run it"),
    ("02-sensors", "handbook/sensors.html", "Sensor Reference",
     "Every sensor: what it measures, how we read it, what we do with it"),
    ("03-circuits", "handbook/circuits.html", "Circuit Reference",
     "Every circuit block: schematic, reasoning, simulated result, limits"),
    ("04-spec", "superpowers/specs/2026-09-13-ecu-reconciled-spec-design.md",
     "Reconciled Specification",
     "Binding source of truth -- pin map, power, deviations, unknowns"),
    ("05-engine", "research/01-engine-identity.md", "Memo 01 -- Engine Identity",
     "Which engine this actually is, established from five hardware constraints"),
    ("06-gcu", "research/02-kg640c-gcu.md", "Memo 02 -- KG640C Controller",
     "What the existing genset controller does, and what it needs from us"),
    ("07-connector", "research/03-ecu-connector.md", "Memo 03 -- ECU Connector",
     "The 94-pin connector: candidates, sourcing, and what stays unconfirmed"),
    ("08-injector", "research/04-injector-drive.md", "Memo 04 -- Injector Drive",
     "Bank sharing proved safe, and the drive envelope it has to hit"),
    ("09-mcu", "research/05-mcu-selection.md", "Memo 05 -- MCU Selection",
     "Why the S32K148, and the timing argument that actually binds"),
    ("10-standards", "research/06-standards.md", "Memo 06 -- Standards & Law",
     "ISO, CISPR and the CPCB IV+ certification position"),
    ("11-bom", "research/07-bom-sourcing.md", "Memo 07 -- BOM & Sourcing",
     "Costed bill of materials, India sourcing, single-source flags"),
    ("12-inspection", "research/08-engine-inspection-brief.md",
     "Memo 08 -- Engine Inspection Brief",
     "The measurements to take at the machine, grouped by machine state"),
    ("13-frontends", "research/09-resistive-sensor-frontends.md",
     "Memo 09 -- Resistive Sensor Front-Ends",
     "How DSE and SEDEMAC build temperature inputs, and what transfers"),
    ("15-turnoff", "research/10-injector-turnoff.md",
     "Memo 10 -- Injector Turn-Off",
     "What production drivers do with the coil energy, and the circuit to build"),
    ("16-supervisor", "research/11-supervisor-and-fail-safe-outputs.md",
     "Memo 11 -- Supervisor & Fail-Safe Outputs",
     "Watchdog, brownout, and what the outputs do while the MCU is in reset"),
    ("14-plan", "superpowers/plans/2026-09-13-phase1-research.md",
     "Phase 1 Research Plan",
     "The plan the eight memos were written against"),
]

# ---------------------------------------------------------------- markdown

MD_EXT = ["tables", "fenced_code", "sane_lists", "attr_list", "def_list",
          "toc", "md_in_html"]

# python-markdown has no task-list or strikethrough extension in core, and
# both appear throughout these documents: the inspection brief is a tick-box
# checklist, and the spec shows superseded reasoning struck through rather
# than deleting it.
TASK = re.compile(r"<li>\s*\[([ xX])\]\s*")
STRIKE = re.compile(r"~~(.+?)~~", re.S)


def md_to_body(text):
    """Markdown to an HTML fragment, with the two missing inline forms."""
    text = STRIKE.sub(lambda m: f"<del>{m.group(1)}</del>", text)
    body = markdown.markdown(text, extensions=MD_EXT)
    return TASK.sub(
        lambda m: '<li><input type="checkbox" disabled'
                  + (' checked' if m.group(1).lower() == "x" else '') + "> ",
        body)


def md_page(src, title):
    """A full printable page built around one Markdown document."""
    body = md_to_body(src.read_text())
    # The document's own <h1> is its title; the eyebrow above it says where
    # the file lives, so a printed page can be traced back to the repo.
    rel = src.relative_to(ROOT)
    return (f"<title>{html.escape(title)}</title>{FONTS}"
            f"<style>{PRINT_CSS}</style>"
            f'<article class="doc"><p class="docmeta">{html.escape(str(rel))}</p>'
            f"{body}</article>")


# ---------------------------------------------------------------- html prep

def html_page(src):
    """An existing handbook page, with print rules and a forced light theme.

    The source file is never modified. print.css is appended after the
    page's own <style>, so its @media print block wins on specificity ties,
    and the theme stamp runs before first paint.
    """
    return (src.read_text()
            + f"<style>{PRINT_CSS}</style>"
            + '<script>document.documentElement.dataset.theme="light"</script>')


# ---------------------------------------------------------------- cover

def cover_page():
    items = "".join(
        f"<li><b>{html.escape(t)}</b><br><span style='color:var(--ink-3)'>"
        f"{html.escape(g)}</span></li>"
        for _, _, t, g in BOOK)
    return f"""<title>Genset ECU -- Complete Documentation</title>{FONTS}
<style>{PRINT_CSS}</style>
<article class="doc cover">
  <div class="top">
    <p class="eyebrow">Kirloskar 3GK550ETA 4SR1 &middot; GK3.8703 &middot; 25 kVA</p>
    <h1>Replacement Engine Control Unit</h1>
    <p class="sub">Complete documentation: the machine, the circuits, the
      specification, and the research all of it rests on.</p>
  </div>
  <div class="mid">
    <p>This replaces the <b>Engine Control Unit</b> block on page 1 of the
      Kirloskar troubleshooting wiring diagram, manual 08-GP3-60-001. Every
      pin, signal and colour in these pages was read out of that document
      or measured in simulation; where something is inferred rather than
      confirmed, it says so on the line.</p>
    <p>The engine has not been inspected yet. Of twelve items on the unknowns
      register, two are answered by inference and none is confirmed &mdash;
      every confirmation needs the machine. The CPCB IV+ certification
      position in Memo 06 is a decision for the machine's owners, not an
      engineering
      conclusion. <b>Read that memo before fitting anything.</b></p>
  </div>
  <div class="contents">
    <h2>Contents</h2>
    <ol>{items}</ol>
  </div>
  <div class="foot">
    <span>Genset ECU project</span>
    <span>{len(BOOK)} documents</span>
  </div>
</article>"""


# ---------------------------------------------------------------- render

def render(source_html, pdf_path, workdir):
    """Print one HTML string to PDF with headless Chrome."""
    page = workdir / (pdf_path.stem + ".html")
    page.write_text(source_html)
    cmd = [
        CHROME, "--headless", "--disable-gpu", "--no-sandbox",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        # Web fonts are fetched over the network. Virtual time lets the
        # page finish loading them before the snapshot, instead of
        # printing the fallback stack and racing the request.
        "--virtual-time-budget=12000",
        f"--print-to-pdf={pdf_path}",
        page.as_uri(),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not pdf_path.exists():
        sys.exit(f"chrome failed on {pdf_path.name}:\n{r.stderr[-2000:]}")


def main():
    if CHROME is None:
        sys.exit("no Chrome/Chromium found -- it is the renderer")
    OUT.mkdir(exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix="ecu-pdf-"))
    built = []

    cover = OUT / "00-cover.pdf"
    render(cover_page(), cover, work)
    print(f"  {'00-cover':<16} cover")

    for stem, rel, title, _ in BOOK:
        src = DOCS / rel
        if not src.exists():
            sys.exit(f"missing source: {src}")
        page = html_page(src) if src.suffix == ".html" else md_page(src, title)
        pdf = OUT / f"{stem}.pdf"
        render(page, pdf, work)
        built.append((pdf, title))
        print(f"  {stem:<16} {title}")

    # One file, bookmarked. append()'s outline_item makes each document a
    # top-level entry in the reader's outline pane -- which is the table of
    # contents that actually gets used, the printed one on the cover being
    # for the paper copy.
    bible = OUT / "ECU-Bible.pdf"
    w = PdfWriter()
    w.append(cover)
    for pdf, title in built:
        w.append(str(pdf), outline_item=title)
    w.write(bible)
    w.close()

    shutil.rmtree(work, ignore_errors=True)
    pages = len(__import__("pypdf").PdfReader(bible).pages)
    print(f"\n{len(built)} documents -> {OUT}")
    print(f"ECU-Bible.pdf  {pages} pages")


if __name__ == "__main__":
    main()
