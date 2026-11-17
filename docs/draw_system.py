#!/usr/bin/env python3
"""The whole ECU on one page: every block's circuit with its real reference
designators and values, joined by named nets (same name = same wire).
For redrawing by hand. Production board (hw/), values from its netlist.

    .venv/bin/python docs/draw_system.py

Writes docs/pdf/ECU-System-Circuit.pdf (A0 landscape) and the panels as
SVG in docs/system/. Repeated channels are drawn once, with a table giving
every copy's parts. Decoupling capacitors that only sit across a supply
are listed under each panel, not drawn.
"""
import html
import subprocess
import sys
from pathlib import Path

import schemdraw
import schemdraw.elements as elm

HERE = Path(__file__).resolve().parent
OUTDIR = HERE / "system"
PDF = HERE / "pdf" / "ECU-System-Circuit.pdf"
sys.path.insert(0, str(HERE))
import build_pdf as B  # noqa: E402  (Chrome, the renderer)

schemdraw.use("svg")
FS = 11


def new():
    d = schemdraw.Drawing(show=False)
    d.config(unit=2.4, fontsize=FS, lw=1.3)
    return d


def IC(*a, **k):
    """an IC box, always upright (it would otherwise turn with the last line)"""
    return elm.Ic(*a, **k).theta(0)


def tw(name):
    """a flag wide enough for its name"""
    return max(1.6, 0.2 * len(name) + 0.7)


def tag(d, name, at=None, side="right"):
    t = elm.Tag(width=tw(name)).label(name, fontsize=FS - 0.5)
    t = t.right() if side == "right" else t.left()
    if at is not None:
        t = t.at(at)
    d += t
    return t


def svg(d):
    data = d.get_imagedata("svg")
    return data.decode() if isinstance(data, bytes) else data


# ------------------------------------------------------------------ panels
# Conventions: series parts run left to right with their label on top;
# a part to ground hangs down from a dot with its label on its right
# ("bottom" for a down-going element); a series FET is rotated so its
# drain is on the left and its gate points down; same flag name = same wire.

def new():
    d = schemdraw.Drawing(show=False)
    d.config(unit=3, fontsize=FS, lw=1.3)
    return d


def gap(d, n=1.2):
    d += elm.Line().right().length(n)


def shunt(d, e, label, side="bottom"):
    """From the current point down to ground; the pen returns to the point."""
    d += (p := elm.Dot())
    d += e.down().label(label, side, ofst=0.2)
    d += elm.Ground()
    d.here = p.start
    return p


def note(d, at, text, valign="top"):
    d += elm.Label().at(at).label(text, fontsize=FS - 1, halign="left", valign=valign)


def series_pfet(d, label, gate_label):
    d += (q := elm.PFet(bulk=True).theta(-90).anchor("drain").label(label, "right", ofst=0.25))
    d += elm.Resistor().down().at(q.gate).length(2.2).label(gate_label, "bottom", ofst=0.2)
    d += elm.Ground()
    d.here = q.source
    return q


def power_input():
    d = new()
    d += elm.Dot(open=True).label("J1001-04\nV_BAT_1R", "left")
    d += (p04 := elm.Dot())
    gap(d, 0.8)
    d += elm.Fuse().right().label("F101\n5 A (0437005)", "top")
    gap(d, 0.8)
    d += elm.Inductor2().right().label("L101\n7447709220", "top")
    gap(d, 1.4)
    shunt(d, elm.Capacitor(), "C101, C102\n2 × 2.2 µF")
    gap(d, 2.4)
    d += elm.Inductor2().right().label("L102 744314047\n(R101 120 Ω across)", "top")
    gap(d, 1.4)
    shunt(d, elm.Zener().reverse(), "D101\nSMCJ43CA\n43 V TVS")
    gap(d, 2.6)
    series_pfet(d, "Q101 SQD50P08-25L\nreverse battery", "R103 47k\n(D102 12 V\nzener G–S)")
    gap(d, 2.6)
    shunt(d, elm.Schottky().reverse(), "D103\nSS20PH102")
    gap(d, 3.6)
    d += (n4 := elm.Dot())
    d += (q2 := elm.NFet().theta(0).anchor("drain"))
    d += elm.Ground().at(q2.source)
    note(d, (q2.gate[0] + 0.9, q2.gate[1] - 0.2), valign="center", text=
         "Q102 IPD90N10S4-06\nnegative clamp, driven by\nU101 TLV3201 → U102 UCC27517A\n(R104 10k, R105 499k,\nR106 536k, R107 10k)")
    d.here = n4.start
    d += elm.Line().right().length(8.5)
    tag(d, "VBAT_PROT")
    # pin 04 again: the injector feed (pin 06 / EGR is the same circuit)
    d += elm.Line().down().at(p04.start).length(9)
    d += (p04b := elm.Dot())
    d.here = p04b.start
    gap(d, 0.8)
    shunt(d, elm.Zener().reverse(), "D105\nSMCJ43CA")
    gap(d, 3.0)
    series_pfet(d, "Q103 SQM120P10-10m1L", "R108 47k\n(D106 12 V G–S)")
    gap(d, 2.6)
    shunt(d, elm.Capacitor(), "C107, C108\n2 × 2.2 µF\nD107 SS20PH102")
    gap(d, 2.6)
    d += elm.Inductor2().right().label("L103\nXAL1510-103 (10 µH)", "top")
    gap(d, 1.4)
    shunt(d, elm.Capacitor(polar=True), "C111, C112 2 × 82 µF\n+ R110/R111 0.68 Ω\n  with C113/C114")
    gap(d, 4.5)
    tag(d, "VBAT_INJ")
    return svg(d)


def rails():
    d = new()
    tag(d, "VBAT_PROT", side="left")
    gap(d, 1.2)
    shunt(d, elm.Capacitor(), "C201, C202\n2 × 2.2 µF")
    gap(d, 2.4)
    d += (u := IC(pins=[elm.IcPin(name="VIN", side="left"), elm.IcPin(name="SW", side="right"),
                           elm.IcPin(name="FB", side="right")],
                     size=(3.4, 2.4), label="U201\nLM5164").anchor("VIN"))
    d += elm.Line().right().at(u.SW).length(0.8)
    d += elm.Inductor2().right().label("L201\n7447714330", "top")
    gap(d, 1.4)
    shunt(d, elm.Capacitor(), "C204\n47 µF")
    gap(d, 2.2)
    d += (o2 := elm.Dot())
    d += elm.Resistor().down().label("R205\n38.3k", "bottom")
    d += elm.Dot().label("FB", "left")
    d += elm.Resistor().down().label("R206\n12.1k", "bottom")
    d += elm.Ground()
    d += elm.Line().right().at(u.FB).length(0.6)
    d += elm.Label().label("FB", "right")
    d.here = o2.start
    gap(d, 2.4)
    tag(d, "5V_MAIN")
    # 3.3 V
    d += elm.Tag(width=tw("5V_MAIN")).left().at((0, -9)).label("5V_MAIN")
    d.here = (0, -9)
    gap(d, 1.2)
    d += (l := IC(pins=[elm.IcPin(name="IN", side="left"), elm.IcPin(name="OUT", side="right")],
                     size=(3.8, 2.2), label="U202\nTLV76733").anchor("IN"))
    d.here = l.OUT
    gap(d, 1.2)
    shunt(d, elm.Capacitor(), "C207\n10 µF")
    gap(d, 2.4)
    tag(d, "3V3_MCU (1 %)")
    # sensor 5 V
    d += elm.Tag(width=tw("VBAT_PROT")).left().at((0, -15)).label("VBAT_PROT")
    d.here = (0, -15)
    gap(d, 1.4)
    d += (q := elm.NFet().theta(-90).anchor("drain").label("Q201\nIPD90N10S4-06", "right", ofst=0.25))
    note(d, (q.gate[0] - 1.5, q.gate[1] - 0.4), "gate: U203 TPS48110,\nopens above ≈ 41 V\n(OV R210 340k / R211 10k)")
    d.here = q.source
    gap(d, 1.6)
    shunt(d, elm.Capacitor(), "C211 47 µF\n(VSNS)")
    gap(d, 2.6)
    d += (t := IC(pins=[elm.IcPin(name="IN", side="left"), elm.IcPin(name="ADJ", side="bottom"),
                           elm.IcPin(name="OUT", side="right")],
                     size=(4.8, 2.6), label="U204, U205, U206\nTPS7B4253").anchor("IN"))
    d.here = t.OUT
    gap(d, 1.2)
    shunt(d, elm.Capacitor(), "C214, C217, C220\n10 µF 50 V")
    gap(d, 3.2)
    tag(d, "5V_SENSOR_A / B / C")
    d += elm.Line().down().at(t.ADJ).length(0.8)
    d += elm.Line().right().length(0.6)
    d += elm.Tag(width=tw("5V_MAIN (reference)")).right().label("5V_MAIN (reference)")
    # monitor
    d += elm.Tag(width=tw("5V_MAIN")).left().at((0, -22)).label("5V_MAIN")
    d.here = (0, -22)
    d += elm.Resistor().right().label("R207\n10k", "top")
    d += (m := elm.Dot())
    d += elm.Resistor().down().label("R208\n15k", "bottom")
    d += elm.Ground()
    d.here = m.start
    gap(d, 2)
    tag(d, "SENSOR_5V_MON (3.0 V at 5 V)")
    return svg(d)


def injector():
    d = new()
    # ---- the boost converter
    tag(d, "VBAT_INJ", side="left")
    gap(d, 1)
    d += elm.Inductor2().right().label("L401\n7447709151", "top")
    d += (sw := elm.Dot())
    d += elm.Diode().right().label("D401\nVS-2EMH02", "top")
    gap(d, 1.4)
    shunt(d, elm.Capacitor(polar=True), "C401 + C420\n2 × 82 µF in series\n(R401, R435 11k\nbalance)")
    gap(d, 3.4)
    d += (b2 := elm.Dot())
    d += elm.Resistor().down().label("R407 + R408\n2 × 499k", "bottom")
    d += elm.Dot().label("FB", "left")
    d += elm.Resistor().down().label("R404\n7.06k", "bottom")
    d += elm.Ground()
    d.here = b2.start
    gap(d, 3.0)
    d += (b3 := elm.Dot())
    d += elm.Zener().down().reverse().label("D417\nBZG03C110\n110 V", "bottom")
    d += elm.Resistor().down().label("R436\n470 Ω", "bottom")
    d += (en := elm.Dot().label("DIS/EN", "left"))
    d += elm.Resistor().down().label("R403 470 Ω\n(D419 5V1\nclamp)", "bottom")
    d += elm.Ground()
    d.here = en.start
    d += elm.Line().right().length(1.2)
    d += elm.Diode().right().reverse().label("D418\nBAT54Q", "top")
    d += elm.Resistor().right().label("R437\n100 Ω", "top")
    tag(d, "BOOST_DIS (MCU)")
    d.here = b3.start
    gap(d, 3.0)
    tag(d, "BOOST_100V  99.7 V")
    d += (q401 := elm.NFet().theta(0).reverse().anchor("drain").at(sw.start).label("Q401\nDMN15H310SK3", "right", ofst=0.2))
    d += (isn := elm.Dot().at(q401.source).label("ISNS", "right"))
    d += elm.Resistor().down().label("R402\n62 mΩ", "bottom")
    d += elm.Ground()
    d += elm.Line().left().at(q401.gate).length(1.0)
    d += elm.Line().down().length(1.4)
    d += elm.Line().left().length(1.6)
    d += (ub := IC(pins=[elm.IcPin(name="DIS/EN", side="right"), elm.IcPin(name="FB", side="right"),
                         elm.IcPin(name="ISNS", side="right"), elm.IcPin(name="GDRV", side="right")],
                   size=(3.4, 4.6), pinspacing=1.1, label="U401\nTPS40210\n150 kHz").anchor("GDRV"))
    for pin in ("ISNS", "FB", "DIS/EN"):
        d += elm.Line().right().at(getattr(ub, pin)).length(0.6)
        d += elm.Tag(width=tw(pin)).right().label(pin)
    note(d, (-3.5, -11.5), "U401: RC R406 365k / C405 330 pF · COMP R409 10k / C408 6.8 nF ·\n"
         "SS C406 100 nF · VDD from VDD_BOOST (Q418/Q419 follower, D415 39 V) or the battery (R405, D402 36 V)")
    # ---- bank A and cylinder 1
    x0, y0 = 0, -17.5
    d += (qa := elm.NFet().theta(0).reverse().at((x0, y0)).anchor("drain")
          .label("Q408\nSQM85N15-19\npeak (100 V)", "right", ofst=0.2))
    d += elm.Line().up().at(qa.drain).length(0.8)
    d += elm.Tag(width=tw("BOOST_100V")).up().label("BOOST_100V")
    d += elm.Resistor().left().at(qa.gate).length(2).label("R419\n470 Ω", "top")
    d += elm.Tag(width=tw("HO_A (U402)")).left().label("HO_A (U402)")
    d += elm.Line().down().at(qa.source).length(1.0)
    d += (na := elm.Dot().label("INJ_A_03 (pin 03)", "left"))
    d += elm.Line().right().length(3.0)
    d += (fw := elm.Dot())
    d += elm.Line().right().length(3.4)
    d += (qb := elm.NFet().theta(0).reverse().anchor("source")
          .label("Q409\nIPD90N10S4-06\nhold (battery)", "right", ofst=0.2))
    d += elm.Resistor().left().at(qb.gate).length(2).label("R420\n470 Ω", "top")
    d += elm.Tag(width=tw("HO_B (U403)")).left().label("HO_B (U403)")
    d += elm.Line().up().at(qb.drain).length(0.6)
    d += elm.Diode().up().reverse().label("D408\nVS-16EDH02", "bottom")
    d += elm.Tag(width=tw("VBAT_INJ")).up().label("VBAT_INJ")
    d += elm.Diode().down().reverse().at(fw.start).label("D409\nVS-16EDH02\nfreewheel", "bottom")
    d += elm.Ground()
    d.here = na.start
    d += elm.Line().down().length(0.8)
    d += elm.Inductor2().down().label("injector 1\n(off-board)", "top")
    d += (nls := elm.Dot().label("pin 73", "right"))
    d += (ql := elm.NFet().theta(0).reverse().anchor("drain")
          .label("Q412 SQM85N15-19\ncyl 1 low side", "right", ofst=0.2))
    d += elm.Resistor().left().at(ql.gate).length(2).label("R425 470 Ω\n(kill: Q413)", "bottom")
    d += elm.Tag(width=tw("LO_1 (U402)")).left().label("LO_1 (U402)")
    d += elm.Line().down().at(ql.source).length(0.8)
    d += (sh := elm.Dot())
    d += elm.Resistor().down().label("R428\n5 mΩ 2 W", "bottom")
    d += elm.Ground()
    d.here = sh.start
    d += elm.Line().right().length(4.5)
    d += (op := elm.Opamp().flip().anchor("in2").label("U406\nINA181A1 ×20", "top", ofst=0.3))
    d.here = op.out
    gap(d, 0.8)
    tag(d, "ISNS_INJ_A (0.1 V/A)")
    # recirculation: low-side node back to the boost rail
    d.here = nls.start
    d += elm.Line().left().length(5.0)
    d += elm.Diode().up().label("D412\nVS-16EDH02\nrecirculation", "top")
    d += elm.Line().up().length(0.4)
    d += elm.Tag(width=tw("BOOST_100V")).left().label("BOOST_100V")
    # the driver, wired by name
    d += (u := IC(pins=[elm.IcPin(name="LIN", side="left"), elm.IcPin(name="HIN", side="left"),
                        elm.IcPin(name="LO", side="right"), elm.IcPin(name="VS", side="right"),
                        elm.IcPin(name="HO", side="right"), elm.IcPin(name="VB", side="top")],
                  size=(4.2, 4.2), pinspacing=1.4, label="U402\nAUIRS2181S").at((22, -19.5)))
    d += elm.Line().left().at(u.HIN).length(0.8)
    d += elm.Resistor().left().label("R410 1k", "top")
    d += elm.Tag(width=tw("INJ_HS_A (MCU)")).left().label("INJ_HS_A (MCU)")
    d += elm.Line().left().at(u.LIN).length(0.8)
    d += elm.Resistor().left().label("R412 1k", "bottom")
    d += elm.Tag(width=tw("INJ_LS_1 (MCU)")).left().label("INJ_LS_1 (MCU)")
    for pin, name in (("HO", "HO_A"), ("VS", "INJ_A_03"), ("LO", "LO_1")):
        d += elm.Line().right().at(getattr(u, pin)).length(0.8)
        d += elm.Tag(width=tw(name)).right().label(name)
    d += elm.Line().up().at(u.VB).length(0.6)
    d += elm.Label().label("VB: bootstrap D403 + C409 1 µF from 12V_GATE", fontsize=FS - 1,
                           halign="center", valign="bottom")
    return svg(d)


def metering_egr():
    d = new()
    # ---- metering valve, low-side PWM with current sense
    d += elm.Tag(width=tw("battery, via the main relay")).left().label("battery, via the main relay")
    d.here = (0, 0)
    d += elm.Inductor2().down().label("metering valve\n≈ 10 Ω, 30 mH\n(off-board)", "top", ofst=0.2)
    d += (mr := elm.Dot().label("pin 88 MU_RETURN", "left"))
    d += (q := elm.NFet().theta(0).reverse().anchor("drain").label("Q501\nIPD90N10S4-06", "right", ofst=0.2))
    d += elm.Resistor().left().at(q.gate).length(2).label("R502 470 Ω\n(kill: Q502)", "bottom")
    d += elm.Tag(width=tw("LO (U502)")).left().label("LO (U502)")
    d += elm.Line().down().at(q.source).length(0.8)
    d += (s := elm.Dot())
    d += elm.Resistor().down().label("R501\n50 mΩ", "bottom")
    d += elm.Ground()
    d.here = s.start
    d += elm.Line().right().length(4)
    d += (op := elm.Opamp().flip().anchor("in2").label("U501\nINA181A1 ×20", "top", ofst=0.3))
    d.here = op.out
    gap(d, 0.8)
    tag(d, "ISNS_MU (1 V/A)")
    d.here = mr.start
    d += elm.Line().right().length(5.5)
    d += elm.Diode().up().label("D501\nVS-3ECH02\nfreewheel", "bottom")
    d += elm.Tag(width=tw("VBAT_PROT")).up().label("VBAT_PROT")
    d += (u := IC(pins=[elm.IcPin(name="LIN", side="left"), elm.IcPin(name="LO", side="right")],
                     size=(4.6, 2), label="U502\nAUIRS2181S").at((-1, -14)))
    d += elm.Line().left().at(u.LIN).length(0.8)
    d += elm.Tag(width=tw("MU_PWM (MCU)")).left().label("MU_PWM (MCU)")
    d += elm.Line().right().at(u.LO).length(0.8)
    d += elm.Tag(width=tw("LO")).right().label("LO")
    # ---- EGR H-bridge
    x0 = 22
    d += elm.Tag(width=tw("VBAT_EGR")).left().at((x0, 0)).label("VBAT_EGR")
    d.here = (x0, 0)
    gap(d, 1.5)
    d += (t1 := elm.Dot())
    d += (qah := elm.NFet().theta(0).reverse().anchor("drain").label("Q503", "right", ofst=0.2))
    d += elm.Line().left().at(qah.gate).length(0.6)
    d += elm.Tag(width=tw("HO_A (U504)")).left().label("HO_A (U504)")
    d += elm.Line().down().at(qah.source).length(0.6)
    d += (ma := elm.Dot().label("pin 59", "left"))
    d += (qal := elm.NFet().theta(0).reverse().anchor("drain").label("Q504", "right", ofst=0.2))
    d += elm.Line().left().at(qal.gate).length(0.6)
    d += elm.Tag(width=tw("LO_A (U504)")).left().label("LO_A (U504)")
    d += elm.Line().down().at(qal.source).length(0.6)
    d += (bot := elm.Dot())
    d.here = t1.start
    gap(d, 9)
    d += (t2 := elm.Dot())
    d += (qbh := elm.NFet().theta(0).anchor("drain").label("Q505", "left", ofst=0.2))
    d += elm.Line().right().at(qbh.gate).length(0.6)
    d += elm.Tag(width=tw("HO_B (U505)")).right().label("HO_B (U505)")
    d += elm.Line().down().at(qbh.source).length(0.6)
    d += (mb := elm.Dot().label("pin 81", "right"))
    d += (qbl := elm.NFet().theta(0).anchor("drain").label("Q506", "left", ofst=0.2))
    d += elm.Line().right().at(qbl.gate).length(0.6)
    d += elm.Tag(width=tw("LO_B (U505)")).right().label("LO_B (U505)")
    d += elm.Line().down().at(qbl.source).length(0.6)
    d += elm.Line().left().tox(bot.start)
    d += elm.Line().right().at(ma.start).length(1.5)
    d += elm.Inductor2().right().label("EGR motor (off-board)", "top")
    d += elm.Line().right().tox(mb.start)
    d += elm.Resistor().down().at(bot.start).label("R507\n20 mΩ 1 W", "bottom")
    d += elm.Ground()
    note(d, (x0 - 1, -11), "Q503–Q506: IPD90N10S4-06 (100 V), gates R503–R506 470 Ω\n"
         "U504 drives leg A (Q503/Q504) from EGR_IN1, U505 leg B from EGR_IN2 (AUIRS2184S)\n"
         "~SD of both = EGR_SD: R508 1k from EGR_EN, R509 10k down, kill Q507\n"
         "EN high: IN1 IN2 = 1 0 forward, 0 1 reverse, 0 0 brake · EN low: COAST (safe)\n"
         "R507 → U503 INA181A1 → ISNS_EGR (0.4 V/A, 6.4 A stall)")
    return svg(d)


def sensors():
    d = new()

    def row(y, pin, first, mid_shunts, last, out):
        nonlocal d
        d += elm.Dot(open=True).at((0, y)).label(pin, "left")
        d.here = (0, y)
        if first:
            d += first
        for k, (e, lab) in enumerate(mid_shunts):
            gap(d, 1.4 if k == 0 else 2.8)
            shunt(d, e, lab)
        gap(d, 2.2)
        d += last
        tag(d, out)

    # differential: drawn once (coolant)
    d += elm.Dot(open=True).label("pin 33\nCOOLANT_T_IN", "left")
    gap(d, 1.2)
    d += (op := elm.Opamp().flip().anchor("in2").label("U602 INA592\ngain 1/2", "top", ofst=0.3))
    d += elm.Line().left().at(op.in1).length(1.2)
    d += elm.Dot(open=True).label("pin 34 (SGND_34)", "left")
    d.here = op.out
    d += elm.Resistor().right().label("R612\n1k", "top")
    shunt(d, elm.Capacitor(), "C606 22 nF\nD605 BAV199\nclamp")
    gap(d, 2.4)
    d += elm.Resistor().right().label("R613\n1k", "top")
    tag(d, "COOLANT_T → ADC")
    row(-8, "pin 35\nRAIL_P_IN", elm.Resistor().right().label("R607\n10k", "top"),
        [(elm.Resistor(), "R608\n16k"), (elm.Capacitor(), "C603 22 nF\nD603")],
        elm.Resistor().right().label("R609\n1k", "top"), "RAIL_P  (×16/26)")
    row(-15, "V_BAT_1R\n(pin 04)", elm.Resistor().right().label("R601\n120k", "top"),
        [(elm.Resistor(), "R602\n10k"), (elm.Capacitor(), "C601 22 nF\nD601")],
        elm.Resistor().right().label("R603\n1k", "top"), "V_BAT_1R_SNS  (×10/130)")
    row(-22, "pin 09\nSYNC_IN", elm.Resistor().right().label("R622\n22k", "top"),
        [(elm.Resistor(), "R623\n10k"), (elm.Capacitor(), "C616 22 nF\nD609")],
        elm.Resistor().right().label("R624\n1k", "top"), "SYNC  (×10/32)")
    return svg(d)


def speed():
    d = new()
    d += elm.Dot(open=True).label("pin 52\nCRANK_HI", "left")
    d += elm.Resistor().right().label("R701\n4.7k", "top")
    gap(d, 1.2)
    hi = shunt(d, elm.Capacitor(), "C701 1 nF\nD702 clamp")
    gap(d, 2.4)
    d += (cmp := elm.Opamp().flip().anchor("in2").label("U701 TLV3201\nzero-cross", "bottom", ofst=0.3))
    d.here = cmp.out
    gap(d, 1.2)
    d += (o := elm.Dot())
    gap(d, 1.2)
    tag(d, "CRANK_EDGE")
    d += elm.Line().up().at(o.start).length(2.2)
    d += elm.Resistor().left().tox(hi.start[0] + 1.4).label("R705 33k (hysteresis)", "top")
    d += elm.Line().left().tox(hi.start[0] + 1.2)
    d += elm.Line().down().toy(hi.start[1])
    d += elm.Dot(open=True).at((0, -5)).label("pin 74\nCRANK_LO", "left")
    d += elm.Resistor().right().label("R702\n4.7k", "top")
    gap(d, 1.2)
    shunt(d, elm.Capacitor(), "C702 1 nF\nD703 clamp")
    d += elm.Line().right().tox(cmp.in1[0] - 0.8)
    d += elm.Line().up().toy(cmp.in1[1])
    d += elm.Line().right().tox(cmp.in1[0])
    note(d, (0, -9.2), "D701 SMAJ48CA across pins 52/74 · bias: R703, R704 100k from each side to VR_BIAS\n"
         "(R706 / R707 2.2k divider, C704 1 µF) · gives edges from 0.21 V at cranking to 20 V running")
    d += elm.Dot(open=True).at((0, -14)).label("pin 46\nCAM_FREQ", "left")
    gap(d, 1.6)
    d += (cm := elm.Dot())
    d += elm.Resistor().up().label("R708 10k\nto 5V_SENSOR_C", "top")
    d.here = cm.start
    shunt(d, elm.Resistor(), "R709 16k\n(C705 22 nF, D704)")
    gap(d, 2.6)
    d += elm.Resistor().right().label("R710\n1k", "top")
    tag(d, "CAM_EDGE")
    return svg(d)


def discrete():
    d = new()
    d += elm.Dot(open=True).label("pin 71\nIGNITION", "left")
    d += elm.Resistor().right().label("R807\n10k", "top")
    gap(d, 1.2)
    shunt(d, elm.Resistor(), "R808\n4.7k")
    gap(d, 2.0)
    shunt(d, elm.Capacitor(), "C803 4.7 µF\nD803 BAV199")
    gap(d, 2.4)
    d += (q := elm.BjtNpn(circle=True).anchor("base").label("Q803\nPMBT3904", "right"))
    d += elm.Ground().at(q.emitter)
    d += elm.Line().up().at(q.collector).length(0.8)
    d += (c := elm.Dot())
    d += elm.Resistor().up().label("R809 10k\nto 3V3_MCU", "top")
    d.here = c.start
    gap(d, 2)
    tag(d, "IN_IGNITION (low = on)")
    # main relay hold + ignition wake
    d += elm.Dot(open=True).at((0, -9)).label("RLY_MAIN\n(MCU)", "left")
    gap(d, 0.8)
    d += (u := IC(pins=[elm.IcPin(name="A", side="left"), elm.IcPin(name="Y", side="right")],
                     size=(3.4, 2), label="U801\nAHCT1G125").anchor("A"))
    d.here = u.Y
    gap(d, 1.2)
    shunt(d, elm.Resistor(), "R830\n10k")
    gap(d, 1.2)
    d += (qm := elm.NFet().theta(0).reverse().anchor("gate").label("Q809\nPMV280ENEA", "right", ofst=0.2))
    d += elm.Ground().at(qm.source)
    d += elm.Line().up().at(qm.drain).length(0.8)
    d += (rd := elm.Dot())
    gap(d, 5)
    d += (w := elm.Dot())
    d += elm.Line().up().length(1.6)
    d += elm.Line().right().length(1)
    tag(d, "pin 50 → main relay coil")
    d += (qw := elm.NFet().theta(0).anchor("drain").at(w.start).label("Q810\nPMV280ENEA\n(wake)", "left", ofst=0.2))
    d += elm.Ground().at(qw.source)
    d += elm.Resistor().right().at(qw.gate).length(2.2).label("R832\n10k", "top")
    d += elm.Tag(width=tw("pin 71 (ignition)")).right().label("pin 71 (ignition)")
    note(d, (0.2, -15), "Q810 closes the relay from the ignition alone, even with the MCU in reset;\n"
         "R831 22k and D810 12 V on its gate · D809 SMAJ48CA on pin 50\n"
         "buzzer: U802 → Q811 PMV280ENEA → pin 69, D811 VS-1EMH02 flyback")
    return svg(d)


def can():
    d = new()
    d += (u := IC(pins=[elm.IcPin(name="STB", side="left"), elm.IcPin(name="RXD", side="left"),
                           elm.IcPin(name="TXD", side="left"), elm.IcPin(name="CANL", side="right"),
                           elm.IcPin(name="CANH", side="right")],
                     size=(3.2, 4.6), pinspacing=2.2, label="U901\nTCAN1042HGV\n5 V / 3.3 V"))
    d += elm.Line().left().at(u.TXD).length(0.8)
    d += elm.Tag(width=tw("CAN1_TX (MCU)")).left().label("CAN1_TX (MCU)")
    d += elm.Line().left().at(u.RXD).length(0.8)
    d += elm.Tag(width=tw("CAN1_RX (MCU)")).left().label("CAN1_RX (MCU)")
    d += elm.Line().left().at(u.STB).length(0.8)
    d += elm.Resistor().down().length(1.6).label("R901\n10k", "bottom")
    d += elm.Ground()
    d += elm.Line().right().at(u.CANH).length(2)
    d += (h := elm.Dot())
    d += elm.Line().right().length(2.4)
    tag(d, "pin 55 CAN1_H")
    d += elm.Line().right().at(u.CANL).length(2)
    d += (l := elm.Dot())
    d += elm.Line().right().length(2.4)
    tag(d, "pin 77 CAN1_L")
    my = (h.start[1] + l.start[1]) / 2
    d += elm.Resistor().down().at(h.start).toy(my).label("R902\n60.0 Ω", "top")
    d += (m := elm.Dot())
    d += elm.Resistor().down().toy(l.start[1]).label("R903\n60.0 Ω", "top")
    d += elm.Capacitor().right().at(m.start).length(2).label("C903\n4.7 nF", "top")
    d += elm.Ground()
    note(d, (-4, l.start[1] - 4.5), "split termination: 120 Ω across the bus, its midpoint\n"
         "to ground through 4.7 nF · thin film, 0.1 %, 50 ppm/°C\n"
         "CAN2 is identical: U902, R905 / R906, C906, R904 → pins 87 / 86\n"
         "CAN1 = J1939 to the DSE4522, 250 kbit/s · CAN2 = service, 1 Mbit/s")
    return svg(d)


def mcu():
    d = new()
    d += (u := IC(pins=[elm.IcPin(name="WDI", side="left"), elm.IcPin(name="WDO", side="left"),
                           elm.IcPin(name="RESET", side="right"), elm.IcPin(name="CWD", side="bottom"),
                           elm.IcPin(name="CRST", side="bottom")],
                     size=(5.6, 3.6), pinspacing=1.4, label="U302\nTPS3850G33"))
    d += elm.Line().left().at(u.WDI).length(0.8)
    d += elm.Tag(width=tw("WDT_KICK (MCU)")).left().label("WDT_KICK (MCU)")
    d += elm.Line().left().at(u.WDO).length(0.8)
    d += elm.Tag(width=tw("WDT_FAULT (MCU)")).left().label("WDT_FAULT (MCU)")
    d += elm.Capacitor().down().at(u.CWD).length(1.6).label("C302\n10 nF", "top")
    d += elm.Ground()
    d += elm.Capacitor().down().at(u.CRST).length(1.6).label("C301\n10 nF", "bottom")
    d += elm.Ground()
    d += elm.Line().right().at(u.RESET).length(1.4)
    d += (r := elm.Dot().label("~RESET", "top"))
    d += elm.Resistor().right().label("R307\n100k", "top")
    d += (kg := elm.Dot().label("KILL_GATE", "top"))
    gap(d, 3.0)
    d += (q1 := elm.NFet().theta(0).reverse().anchor("gate").label("Q301\n2N7002BK", "right", ofst=0.2))
    d += elm.Ground().at(q1.source)
    d += elm.Line().up().at(q1.drain).length(0.8)
    d += (gk := elm.Dot())
    d += elm.Resistor().up().label("R305 47k to VBAT_PROT\n(D301 12 V clamp)", "top")
    d.here = gk.start
    gap(d, 2)
    tag(d, "GATE_KILL → every power gate")
    d += elm.Line().down().at(kg.start).length(5.5)
    d += (q2 := elm.NFet().theta(0).reverse().anchor("drain").label("Q302\n2N7002BK", "right", ofst=0.2))
    d += elm.Ground().at(q2.source)
    d += elm.Line().left().at(q2.gate).length(1.6)
    d += elm.Tag(width=tw("SW_STOP (pin 25)")).left().label("SW_STOP (pin 25)")
    note(d, (-5, -9.5), "WDO → WDT_FAULT (R302 10k up) and through D302 BAT54Q → ~RESET (R301 10k up)\n"
         "Normal: ~RESET high → Q301 on → GATE_KILL low: gates may switch\n"
         "Reset, watchdog or stop switch → Q301 off → GATE_KILL high → all gates off\n"
         "U301: S32K148 (prototype: STM32G474) · bulk C313 150 µF + R306 22 mΩ · kick every 10 ms")
    return svg(d)


# ------------------------------------------------------------------ the page

PANELS = [
    ("power", "1  Power input", "Battery to the protected rail. Survives load dump (TVS 43 V), reverse battery (P-FET) "
     "and negative spikes (clamp). Pin 06 (EGR feed) is the same circuit as the injector feed: "
     "D108, Q104 SQM120P10, D109/D110, C109/C110, L104 10 µH, C115–C118 → VBAT_EGR.",
     power_input, "C103 100 nF · C104 1 µF + R102 2.2 Ω damper · C105, C106 · EMI filter values from emi_filter.cir"),
    ("rails", "2  Rails", "5 V from the buck, 3.3 V from the LDO, three 5 V sensor supplies behind an over-voltage "
     "cut-off. SENSOR_5V_MON = 5V_MAIN through R207 10k / R208 15k.",
     rails, "U201: UVLO R201 75k / R202 24.9k, RON R203 31.6k, BST C203 2.2 nF, PGOOD R204 100k · "
     "U203: R209 100 Ω, R212 100k, R213 10 Ω, C208/C209 22 nF, C210 1 µF · C211 47 µF, C214/C217/C220 10 µF 50 V"),
    ("mcu", "3  MCU, supervisor and the kill path", "If the MCU hangs, resets or the stop switch is pressed, "
     "GATE_KILL forces every injector, metering and EGR gate off in hardware.",
     mcu, "C303–C312 100 nF across 3V3_MCU · SET0/SET1 R303/R304 0 Ω · J301 SWD"),
    ("inj", "4  Injector stage", "100 V boost (TPS40210) for the 18 A peak, battery for the 9–11 A hold. "
     "Drawn: bank A and cylinder 1. 110 V zener stops the boost in hardware; the MCU can stop it with BOOST_DIS.",
     injector, "12V_GATE (gate drivers) = follower from BOOST_100V: Q406 PZTA42, Q407 PMBT3904, R416/R417 3.3k, "
     "R414/R415 47k, D407 13 V, R418 56 Ω, C417 10 µF · VDD_BOOST: Q418/Q419, R430/R431 7.5k, D415 39 V, "
     "D416, R405 180 Ω, D402 36 V · bootstraps D403–D406 + C409–C416 1 µF · HIN kill Q402–Q405, series R410–R413 1k"),
    ("meter", "5  Metering valve and EGR bridge", "Metering: low-side PWM at 1 kHz with current sense (closed loop). "
     "EGR: four 100 V FETs, AUIRS2184 per leg; EN low = coast (safe).",
     metering_egr, "EGR drivers U504/U505 AUIRS2184S (IN from EGR_IN1/IN2), gates R503–R506 470 Ω, "
     "bootstraps D502/D503 + C504/C506 1 µF · ~SD = EGR_SD: R508 1k from EGR_EN, R509 10k down, kill Q507 · "
     "U503 INA181A1 on R507 → ISNS_EGR (0.4 V/A)"),
    ("sens", "6  Analog sensors", "Drawn once each: a differential channel, the ratiometric rail channel and a "
     "battery divider. Every channel ends 1k → 22 nF + BAV199 clamp → 1k → ADC.",
     sensors, "Baro U606 MPXHZ6115A → R620 10k / R621 16k, C615 → BARO · SYNC pin 09: R622 22k / R623 10k, "
     "C616, D609, R624 1k · V_BAT_2R (pin 06): R604 120k / R605 10k, C602, D602, R606 1k"),
    ("speed", "7  Speed inputs", "Crank VR → zero-cross comparator with hysteresis (edges from 0.21 V at cranking). "
     "Cam Hall open-collector → divider to 3.3 V.", speed, "C703 100 nF across U701"),
    ("disc", "8  Discrete inputs and relays", "Drawn: ignition input and the main relay. Every input is the same "
     "NPN buffer: pad LOW = input active.", discrete, "C809, C810 100 nF"),
    ("can", "9  CAN", "Two TCAN1042HGV transceivers, split termination 60 Ω + 60 Ω with 4.7 nF to ground.",
     can, "C901, C902, C904, C905 100 nF"),
]

REPEATS = {
    "inj": ("Bank and cylinder paths", ["path", "high side (peak)", "high side (hold)", "driver", "low side", "recirc.", "shunt / amp"],
            [["bank A, cyl 1 (pin 03, 73)", "Q408", "Q409, D408", "U402 / U403", "Q412 (kill Q413)", "D412", "R428 / U406"],
             ["bank A, cyl 3 (pin 03, 07)", "Q408", "Q409, D408", "U403", "Q414 (kill Q415)", "D413", "R428 / U406"],
             ["bank B, cyl 2 (pin 05, 29)", "Q410", "Q411, D410", "U404 / U405", "Q416 (kill Q417)", "D414", "R429 / U407"]]),
    "sens": ("Differential channels (INA592, gain 1/2)", ["signal", "pin (return)", "amp", "series", "clamp node", "to MCU"],
             [["boost pressure", "41 (34)", "U601", "R610 1k", "C604, D604", "R611 1k → BOOST_P"],
              ["coolant", "33 (34)", "U602", "R612 1k", "C606, D605", "R613 1k → COOLANT_T"],
              ["EGR position", "37 (36)", "U603", "R614 1k", "C608, D606", "R615 1k → EGR_POS"],
              ["oil pressure", "80 (36)", "U604", "R616 1k", "C610, D607", "R617 1k → OIL_P"],
              ["boost temp.", "79 (34)", "U605", "R618 1k", "C612, D608", "R619 1k → BOOST_T"]]),
    "disc": ("Input channels (NPN buffer, inverted)", ["input", "pin", "series", "pull-up (harness)", "base R ‖ C", "NPN", "pad pull-up"],
             [["ignition", "71", "R807 10k", "—", "R808 4.7k ‖ C803", "Q803", "R809 10k"],
              ["water in fuel", "21", "R818 10k", "—", "R819 4.7k ‖ C806", "Q806", "R820 10k"],
              ["audio abort", "20", "R801 10k", "—", "R802 4.7k ‖ C801", "Q801", "R803 10k"],
              ["override start/stop", "24", "R804 10k", "—", "R805 4.7k ‖ C802", "Q802", "R806 10k"],
              ["coolant switch", "43", "R811 10k", "R810 10k", "R812 4.7k ‖ C804", "Q804", "R813 10k"],
              ["droop switch", "23", "R815 10k", "R814 10k", "R816 4.7k ‖ C805", "Q805", "R817 10k"],
              ["diagnosis", "14", "R822 10k", "R821 10k", "R823 4.7k ‖ C807", "Q807", "R824 10k"],
              ["stop switch", "25", "R826 10k", "R825 10k", "R827 4.7k ‖ C808", "Q808", "R828 10k"]]),
}

PINS = [("01, 02", "GND (power return)"), ("03 / 05", "INJ_A / INJ_B (bank high sides)"),
        ("04", "V_BAT_1R: electronics + injectors"), ("06", "V_BAT_2R: EGR"), ("07, 29, 73", "injector low sides 3, 2, 1"),
        ("09", "SYNC (GCU, analog)"), ("11, 15 / 32, 39 / 45", "5V_SENSOR_A / B / C"), ("14", "diagnosis switch"),
        ("20, 21, 23, 24, 25", "audio abort, water in fuel, droop, override, stop"), ("33 / 41 / 79", "coolant / boost P / boost T (return 34)"),
        ("35 (08)", "rail pressure (own return)"), ("37 / 80", "EGR position / oil P (return 36)"), ("43", "coolant switch"),
        ("46, 44", "cam (Hall)"), ("50", "main relay hold"), ("52, 74, 30", "crank VR +, −, shield"),
        ("55, 77", "CAN1 J1939"), ("59, 81", "EGR motor"), ("69", "buzzer relay"), ("71", "ignition (wake)"),
        ("86, 87", "CAN2 service"), ("88", "metering valve return")]


def table(title, head, rows):
    h = "".join(f"<th>{html.escape(x)}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<p class='tt'>{html.escape(title)}</p><table><tr>{h}</tr>{b}</table>"


CSS = """
@page { size: 841mm 1189mm; margin: 10mm; }   /* A0 portrait */
* { box-sizing: border-box; }
body { margin: 0; width: 1169mm; zoom: 0.7; font-family: 'Segoe UI', Arial, sans-serif; color: #111; }
h1 { font-size: 30pt; margin: 0 0 2mm; }
.sub { font-size: 13pt; margin: 0 0 5mm; color: #333; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5mm; }
.panel { border: 0.6mm solid #333; border-radius: 3mm; padding: 4mm; break-inside: avoid; }
.panel h2 { font-size: 16pt; margin: 0 0 1.5mm; }
.panel p { font-size: 10.5pt; margin: 0 0 2mm; line-height: 1.35; }
.panel .notes { font-size: 9.5pt; color: #333; border-top: 0.3mm solid #999; padding-top: 1.5mm; margin-top: 2mm; }
.panel svg { max-width: 100%; height: auto; display: block; margin: 2mm auto; }
.wide { grid-column: span 2; }
table { border-collapse: collapse; font-size: 9pt; width: 100%; margin-top: 1mm; }
th, td { border: 0.25mm solid #888; padding: 0.6mm 1.2mm; text-align: left; }
th { background: #eee; }
.tt { font-weight: 600; font-size: 10pt; margin: 2mm 0 0.5mm; }
.legend { font-size: 10.5pt; }
"""


def main():
    OUTDIR.mkdir(exist_ok=True)
    cells = []
    order = ["power", "mcu", "can", "inj", "meter", "rails", "sens", "speed", "disc"]
    by = {p[0]: p for p in PANELS}
    for key in order:
        _, title, intro, fn, notes = by[key]
        s = fn()
        (OUTDIR / f"{key}.svg").write_text(s, encoding="utf-8")
        rep = table(*REPEATS[key]) if key in REPEATS else ""
        wide = " wide" if key in ("power", "inj", "meter") else ""
        cells.append(f"<div class='panel{wide}'><h2>{html.escape(title)}</h2><p>{html.escape(intro)}</p>"
                     f"{s}{rep}<p class='notes'>Also on this sheet: {html.escape(notes)}</p></div>")
    pins = table("Connector J1001 (Bosch 94-pin, MD1CS162 pinout): the pins used", ["pin", "net"], PINS)
    cells.append(f"<div class='panel'><h2>10  Connector and how to read this page</h2>"
                 f"<p class='legend'><b>Same name = same wire.</b> A flag such as <b>VBAT_PROT</b> in one panel is "
                 f"connected to every other flag with that name. Values are the production netlist's "
                 f"(hw/, 17 Nov 2026). Prototype: the same circuits; MCU STM32G474, screw terminals instead of J1001.</p>"
                 f"{pins}</div>")
    page = (f"<title>ECU system circuit</title><style>{CSS}</style>"
            f"<h1>Genset ECU (25 kVA) — the whole circuit on one page</h1>"
            f"<p class='sub'>Every block with its real designators and values, joined by named nets. "
            f"Kirloskar 3GK550ETA 4SR1 · Bosch MD1CS162 pinout · 4-layer board · drawn from docs/draw_system.py</p>"
            f"<div class='grid'>{''.join(cells)}</div>")
    work = OUTDIR
    (work / "system.html").write_text(page, encoding="utf-8")
    if not B.CHROME:
        sys.exit("no Chrome/Chromium found -- it is the renderer")
    B.render(page, PDF, work)
    print(f"{PDF.relative_to(HERE.parent)} written; panels in {OUTDIR.relative_to(HERE.parent)}/")


if __name__ == "__main__":
    main()
