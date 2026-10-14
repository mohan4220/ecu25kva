#!/usr/bin/env python3
"""Project footprints: stock ones renumbered, and ones KiCad 7 lacks, drawn.

A footprint's pad numbers have to match its symbol's pin numbers, and
KiCad has no pin-to-pad map to fix a mismatch afterwards. Several stock
power packages number their pads for a different symbol than the one a
two-terminal part uses here:

    TO-277A (SMPC)   stock: 1, 2 = anode leads, 3 = cathode tab
                     Device:D / D_Schottky: 1 = K, 2 = A
    SOT-23 zener     BZX84-Q: 1 = anode, 2 = n.c., 3 = cathode
                     Device:D_Zener: 1 = K, 2 = A

Drawing the SS20PH102HM3 with the stock pads would have put the cathode
on the two small leads and the anode on the tab -- the same class of
error as a GSD FET symbol on a TO-252 footprint (see schlib.PINS).

So each footprint here is the stock one, copied byte for byte except for
its name and the pad numbers in REMAP. Unnumbered pads (paste
apertures) are left alone. Re-run after a KiCad library update.
"""
import os
import re

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "lib", "ecu25kva.pretty")
STOCK = os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints")

# new name: (stock library, stock footprint, {stock pad: new pad})
REMAP = {
    "TO-277A_K1_A2": ("Package_TO_SOT_SMD", "TO-277A",
                      {"3": "1", "1": "2", "2": "2"}),
    # SOT-23 zeners (BZX84-Q): pin 1 anode, 2 n.c., 3 cathode.
    "SOT-23_Zener_K1_A2": ("Package_TO_SOT_SMD", "SOT-23",
                           {"3": "1", "1": "2", "2": "3"}),
}


def derive(name, lib, fp, padmap):
    src = open(os.path.join(STOCK, lib + ".pretty", fp + ".kicad_mod")).read()
    out = re.sub(r'^\(footprint "[^"]+"', f'(footprint "{name}"', src, count=1)
    out = out.replace(f'(value "{fp}"', f'(value "{name}"')
    out = re.sub(r'\(property "Value" "[^"]*"',
                 f'(property "Value" "{name}"', out)

    # Stock files write pad numbers both quoted and bare: (pad "1" ...)
    # in TO-277A, (pad 1 ...) in SOT-23.
    pad_re = r'\(pad (?:"([^"]*)"|([^\s")]+))'

    def pad(m):
        num = m.group(1) if m.group(1) is not None else m.group(2)
        return f'(pad "{padmap.get(num, num)}"'
    found = {m.group(1) if m.group(1) is not None else m.group(2)
             for m in re.finditer(pad_re, src)}
    out, n = re.subn(pad_re, pad, out)
    moved = sum(1 for k in padmap if k in found)
    if moved != len(padmap):
        raise SystemExit(f"{fp}: expected pads {sorted(padmap)} in the "
                         "stock footprint -- has the library changed?")
    with open(os.path.join(OUT, name + ".kicad_mod"), "w") as f:
        f.write(out)
    return n


# -------------------------------------------------------------- drawn
# Packages KiCad 7 has no land pattern for, drawn from the maker's own
# recommended layout. Each entry: description, body (w, h) for the fab
# outline, pads, and whether pad 1 gets a silkscreen marker. A pad is
# (number, x, y, w, h, layers); layers "cu" is copper with paste and
# mask, "cu-only" copper alone (its mask and paste are separate "" pads,
# for a solder-mask-defined thermal pad), "tht-<drill>" a plated hole.
# An optional fifth entry is a note printed on silkscreen and fab.
CU = '"F.Cu" "F.Paste" "F.Mask"'
LAYERS = {"cu": CU, "cu-only": '"F.Cu"', "mask": '"F.Mask"',
          "paste": '"F.Paste"', "tht": '"*.Cu" "*.Mask"'}


def gullwing(n_side, pitch, span, w, h, skip=()):
    """Pins 1..n down the left, n+1..2n up the right, numbered the JEDEC
    way; pitch along y, pad centres at x = +/-span/2."""
    pads = []
    y0 = -(n_side - 1) * pitch / 2
    for i in range(n_side):
        for num, x, y in ((i + 1, -span / 2, y0 + i * pitch),
                          (2 * n_side - i, span / 2, y0 + i * pitch)):
            if num not in skip:
                pads.append((str(num), x, y, w, h, "cu"))
    return pads


def bosch94_placeholder():
    """J1001 as read off the old ECU's connector face (field evidence
    2026-10-13 sec. 2): pins 1-6 large, two staggered rows of three at
    one end; pins 7-94 in four rows of 22 either side of a central rib.
    Pitch, row spacing and drills are ASSUMED (2.5 mm); measure first."""
    x0 = -36.0
    pads = []
    for i in range(6):                  # 1, 3, 5 top row; 2, 4, 6 bottom
        pads.append((str(i + 1), x0 + 2.5 * i, -3.75 if i % 2 == 0 else 3.75,
                     2.8, 5.0, "tht-1.6"))
    for row, y in enumerate((-6.25, -3.75, 3.75, 6.25)):
        for i in range(22):
            pads.append((str(7 + 22 * row + i), x0 + 20 + 2.5 * i, y,
                         1.6, 1.6, "tht-1.0"))
    return pads


DRAWN = {
    # The harness header. Only the pin NUMBERS are known to be right.
    "Bosch_94_PLACEHOLDER": (
        "PLACEHOLDER for the 94-way Bosch header (mates 1 928 405 063): "
        "6 large + 4 x 22, geometry assumed. DO NOT FABRICATE",
        (76.0, 16.0), bosch94_placeholder(), False,
        "PLACEHOLDER - DO NOT FABRICATE"),
    # TI SLVSCP3D p.25, DDA0008J: 8 x 1.55 x 0.6 at 1.27, rows 5.4 apart;
    # thermal pad 2.95 x 4.9 copper, 2.6 x 3.2 solder-mask-defined
    # opening and stencil (0.125 mm). TI's optional thermal vias are
    # left to layout.
    "TI_DDA0008J_HSOIC-8_EP2.95x4.9_Mask2.6x3.2": (
        "TI DDA0008J PowerPAD SOIC-8, 3.9x4.9 mm, P1.27 mm, land pattern "
        "per SLVSCP3D (TPS7B4253-Q1) p.25", (3.9, 4.9),
        gullwing(4, 1.27, 5.4, 1.55, 0.6) + [
            ("9", 0, 0, 2.95, 4.9, "cu-only"),
            ("", 0, 0, 2.6, 3.2, "mask"),
            ("", 0, 0, 2.6, 3.2, "paste")], True),
    # TI DGX0019A (4226944/A), as printed in the TPS4811-Q1 datasheet:
    # 20 positions at 0.5, 1.45 x 0.3 pads, rows 4.4 apart, position 16
    # empty. No exposed pad.
    "TI_DGX0019A_VSSOP-19_3x5.1mm_P0.5mm": (
        "TI DGX0019A VSSOP-19 (20 positions, 16 removed), 3x5.1 mm, "
        "P0.5 mm, land pattern per 4226944/A", (3.0, 5.1),
        gullwing(10, 0.5, 4.4, 1.45, 0.3, skip={16}), True),
    # Vishay 95604 TO-263AC (SMPD) mounting pad layout: tab 10.66 x 8.38,
    # leads 2.03 x 3.05 at 5.08, overall 13.33-15.33 (14.33 used), with
    # the body placed from the outline: 2.8 mm of lead below it, the tab
    # 1.0 mm above, lead tips 0.5 mm inside their pads. The
    # tab is the cathode and both leads are the anode (VS-16EDH02HM3),
    # so Device:D's 1 = K, 2 = A lands on tab = 1, leads = 2.
    "Vishay_SMPD_TO-263AC_K1_A2": (
        "Vishay SMPD (TO-263AC), tab = cathode = 1, both leads = anode = 2, "
        "per Vishay doc 95604", (10.0, 8.79, -0.535),
        [("1", 0, -2.975, 10.66, 8.38, "cu"),
         ("2", -2.54, 5.64, 2.03, 3.05, "cu"),
         ("2", 2.54, 5.64, 2.03, 3.05, "cu")], False),
    # Wurth 7447714330 (WE-PD 1050) recommended land pattern: two pads
    # 3.5 x 2.0, 7.0 inner gap, 11.0 outer. No vias or sensitive traces
    # underneath, per the datasheet.
    "L_Wuerth_WE-PD-1050": (
        "Wurth WE-PD 1050 shielded power inductor, 10x10 mm, land pattern "
        "per 7447714330 datasheet. No vias or sensitive traces underneath",
        (10.0, 10.0),
        [("1", 0, -4.5, 3.5, 2.0, "cu"), ("2", 0, 4.5, 3.5, 2.0, "cu")],
        False),
}


def r2(v):
    return round(v + 0.0, 3)


def draw(name, descr, body, pads, pin1, note=None):
    bw, bh, by = (body + (0.0,))[:3]
    # Courtyard: 0.25 mm round everything, IPC-7351 nominal.
    xs = [abs(x) + w / 2 for _, x, _, w, _, _ in pads] + [bw / 2]
    ys = [abs(y) + h / 2 for _, _, y, _, h, _ in pads] + [abs(by) + bh / 2]
    cx, cy = r2(max(xs) + 0.25), r2(max(ys) + 0.25)
    out = [f'(footprint "{name}" (version 20221018) (generator pcbnew)',
           '  (layer "F.Cu")', f'  (descr "{descr}")',
           f'  (tags "{name}")',
           '  (attr through_hole)' if any(p[5].startswith("tht")
                                          for p in pads) else '  (attr smd)',
           f'  (fp_text reference "REF**" (at 0 {r2(-cy - 1)}) '
           '(layer "F.SilkS")\n    (effects (font (size 1 1) '
           '(thickness 0.15))))',
           f'  (fp_text value "{name}" (at 0 {r2(cy + 1)}) (layer "F.Fab")'
           '\n    (effects (font (size 1 1) (thickness 0.15))))',
           '  (fp_text user "${REFERENCE}" (at 0 0) (layer "F.Fab")\n'
           '    (effects (font (size 0.8 0.8) (thickness 0.12))))']
    for layer in (("F.SilkS", "F.Fab") if note else ()):
        out.append(f'  (fp_text user "{note}" (at 0 {r2(cy + 2.5)}) '
                   f'(layer "{layer}")\n    (effects (font (size 1.5 1.5) '
                   '(thickness 0.25))))')

    def rect(x1, y1, x2, y2, layer, wd):
        out.append(f'  (fp_rect (start {r2(x1)} {r2(y1)}) (end {r2(x2)} '
                   f'{r2(y2)}) (stroke (width {wd}) (type solid)) '
                   f'(fill none) (layer "{layer}"))')

    def line(x1, y1, x2, y2):
        out.append(f'  (fp_line (start {r2(x1)} {r2(y1)}) (end {r2(x2)} '
                   f'{r2(y2)}) (stroke (width 0.12) (type solid)) '
                   '(layer "F.SilkS"))')
    rect(-bw / 2, by - bh / 2, bw / 2, by + bh / 2, "F.Fab", 0.1)
    rect(-cx, -cy, cx, cy, "F.CrtYd", 0.05)
    # Silkscreen: the body's top and bottom edges, clear of the pads,
    # plus a pin-1 tick where there is a pin 1 to find.
    sy = bh / 2 + 0.12
    if not any(abs(y) + h / 2 > sy - 0.2 for _, _, y, _, h, _ in pads):
        line(-bw / 2, -sy, bw / 2, -sy)
        line(-bw / 2, sy, bw / 2, sy)
    if pin1:
        _, x1, y1, w1, _, _ = pads[0]
        line(x1 - w1 / 2, y1 - 0.6, x1 + w1 / 2, y1 - 0.6)
    for num, x, y, w, h, lay in pads:
        if lay.startswith("tht"):
            out.append(f'  (pad "{num}" thru_hole oval (at {r2(x)} {r2(y)}) '
                       f'(size {r2(w)} {r2(h)}) (drill {lay[4:]}) '
                       f'(layers {LAYERS["tht"]}))')
            continue
        shape = ("rect" if lay != "cu" else "roundrect")
        # Corner radius 25% of the short side, capped at 0.25 mm
        # (IPC-7351C) so a large tab is not rounded off.
        rat = round(min(0.25, 0.25 / min(w, h)), 4)
        rr = f" (roundrect_rratio {rat})" if shape == "roundrect" else ""
        out.append(f'  (pad "{num}" smd {shape} (at {r2(x)} {r2(y)}) '
                   f'(size {r2(w)} {r2(h)}) (layers {LAYERS[lay]}){rr})')
    out.append(")")
    with open(os.path.join(OUT, name + ".kicad_mod"), "w") as f:
        f.write("\n".join(out) + "\n")
    return len(pads)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, (lib, fp, padmap) in REMAP.items():
        # The derived files are KiCad 7 format. A newer stock library
        # would rewrite them in a format KiCad 7 cannot open.
        head = open(os.path.join(STOCK, lib + ".pretty",
                                 fp + ".kicad_mod")).read(200)
        v = re.search(r"\(version (\d+)\)", head)
        if v and int(v.group(1)) > 20221018:
            print(f"{name}: skipped -- stock library is newer than KiCad 7")
            continue
        n = derive(name, lib, fp, padmap)
        print(f"{name}: from {lib}:{fp}, {n} pads, renumbered {padmap}")
    for name, spec in DRAWN.items():
        print(f"{name}: drawn, {draw(name, *spec)} pads")
