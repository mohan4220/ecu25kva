#!/usr/bin/env python3
"""rails sheet: LM5164 buck to 5 V, TLV767 LDO to 3V3, PTC sensor distribution.

Three stages, and each one's values come from a simulation block:

  buck        buck_preregulator.cir -- 33 uH, 47 uF/10 mOhm, 400 kHz
  3V3 LDO     constrained by the supervisor on the mcu sheet
  5V_SENSOR   sensor_rail.cir -- a TPS7B4253-Q1 per sensor group behind
              a TPS48110-Q1 overvoltage cut-off (decisions log 4, 7)

TWO PART DECISIONS ARE TAKEN HERE, both replacing entries in research
memo 07's BOM table that were explicitly marked as representative or
class-typical rather than chosen. The reasoning for each sits beside its
symbol in hw/gen_symbols.py; the short version:

  LM5164      memo 07 sec.4 names a 60 V TPS54360B-Q1. transient_clamp
              .cir now carries a PASSING check reading "60 V-class parts
              are NO LONGER viable downstream" -- the TVS standoff went
              to 43 V so the part stops conducting during a normal
              clamped dump, which put the pulse 2a clamp at 73.3 V. The
              suite has been checking every rating against the LM5164's
              100 V VIN all along; the BOM was never reconciled with it.

  TLV76733    memo 07 sec.6 names TLV1117-33QDCYRQ1 as representative,
              "class pricing, not fetched". The supervisor choice on the
              mcu sheet made 3V3 accuracy load-bearing -- outside
              3.143-3.459 V the board resets itself -- so the LDO now has
              to be specified, not sampled. TLV767-Q1 is 1% over load and
              temperature: 3.267-3.333 V, ~125 mV margin at each end.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import schlib
from schlib import Sheet, Rail, pin_xy, r2, PINS

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "rails.kicad_sch")

BUCK = "ecu25kva:LM5164"
LDO = "ecu25kva:TLV76733"
# Ground symbols go just below the part that needs them. An earlier
# version sent every one of them to a single page-wide GND_Y, which drew
# wires from the sensor distribution at the bottom of the page back up
# past the buck -- correct netlist, unreadable page.
GND_DROP = 7.62
# Symbol-local pin offsets, written by hw/gen_symbols.py when it draws the
# symbols. Read rather than re-derived: computing the body height from the
# pin counts here is how every LDO pin first landed millimetres from its
# own wire while the page still plotted as if connected.
ICPINS = json.load(open(os.path.join(HW, "lib", "ic_pins.json")))


def ic_pin(part, num, x, y):
    dx, dy = ICPINS[part][str(num)]
    return pin_xy(dx, dy, x, y, 0)


def vpart(sh, libid, prefix, x, y, value, fields, top_net=None,
          bot_net=None, to_gnd=False, rail=None, tap=True):
    """A vertical part. `rail` is a schlib.Rail this part taps off.

    Never wire to a rail's middle -- see schlib.Rail for why that plots
    correctly and nets incorrectly.
    """
    ref = sh.place(libid, prefix, x, y, value, fields=fields)
    a = pin_xy(*PINS[libid]["1"], x, y, 0)
    b = pin_xy(*PINS[libid]["2"], x, y, 0)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    if rail is not None:
        rx, ry = rail.to(t[0], tap=tap)
        sh.wire(rx, ry, t[0], t[1])
    if top_net:
        sh.wire(t[0], t[1], t[0], t[1] - 5.08)
        sh.label(top_net, t[0], t[1] - 5.08, rot=90)
    if to_gnd:
        sh.wire(bo[0], bo[1], bo[0], bo[1] + GND_DROP)
        sh.gnd(bo[0], bo[1] + GND_DROP)
    elif bot_net:
        sh.wire(bo[0], bo[1], bo[0], bo[1] + 5.08)
        sh.label(bot_net, bo[0], bo[1] + 5.08, rot=90)
    return t, bo


def join_mid(sh, top_pin, bot_pin):
    """Join two series parts and return the tap point between them.

    The joining wire is SPLIT at that point, so a third wire arriving
    there meets an endpoint rather than a mid-span -- see schlib.Rail.
    Every divider on this sheet taps its own midpoint, so every one of
    them needs this.
    """
    mx = top_pin[0]
    my = r2((top_pin[1] + bot_pin[1]) / 2)
    sh.wire(top_pin[0], top_pin[1], mx, my)
    sh.wire(mx, my, bot_pin[0], bot_pin[1])
    sh.junction(mx, my)
    return mx, my


def buck(sh):
    """LM5164 in its constant-on-time configuration."""
    ux, uy = 150.0, 85.0
    P = {n: ic_pin("LM5164", num, ux, uy) for n, num in
         (("VIN", 2), ("EN", 3), ("RON", 4), ("FB", 5),
          ("PGOOD", 6), ("BST", 7), ("SW", 8), ("GND", 1))}
    L = {n: P[n] for n in ("VIN", "EN", "RON", "FB")}
    R = {n: P[n] for n in ("SW", "BST", "PGOOD")}
    lx, rx = L["VIN"][0], R["SW"][0]

    sh.place(BUCK, "U", ux, uy, "LM5164",
             footprint="Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm",
             fields={"MPN": "LM5164DDAR",
                     "Source": "TI SNVSAU4D; buck_preregulator.cir",
                     "Note": "Replaces memo 07's 60 V TPS54360B-Q1 -- the "
                             "43 V TVS standoff puts the pulse 2a clamp at "
                             "73.3 V and transient_clamp.cir says 60 V-class "
                             "parts are no longer viable downstream"})
    gx, gy = P["GND"]
    sh.wire(gx, gy, gx, gy + 5.08)
    sh.gnd(gx, gy + 5.08)

    # ---- input ----
    vy = L["VIN"][1]
    sh.hlabel("VBAT_PROT", 40.0, vy, shape="input")
    vin = Rail(sh, vy)
    vin.to(40.0)
    # Two 2.2 uF 100 V: 4.7 uF at 100 V is not in KEMET's automotive
    # X7R range, and VIN sees 73.3 V.
    for cx in (60.0, 74.0):
        vpart(sh, "Device:C", "C", cx, vy + 20, "2.2uF 100V",
              {"Source": "buck input bypass -- LM5164 datasheet sec.4, "
                         "'short, low impedance paths' to VIN; one of two"},
              to_gnd=True, rail=vin)

    # ---- EN/UVLO divider: turn-on at 6.0 V, the spec's own input floor ----
    # EN/UVLO rises at 1.5 V typ, and the pin is rated to 100 V so the
    # divider is for programming the threshold, not for protecting it.
    #   1.5 = 6.0 * R2/(R1+R2)  ->  R2/(R1+R2) = 0.25
    #   75k / 24.9k gives 0.249, i.e. turn-on at 6.02 V
    ex = 86.0
    t1, b1 = vpart(sh, "Device:R", "R", ex, vy + 16, "75k",
                   {"Source": "EN/UVLO top -- turn-on at 6.02 V, the spec's "
                              "6 V cranking-dip floor"}, rail=vin)
    vin.to(lx)
    t2, b2 = vpart(sh, "Device:R", "R", ex, vy + 34, "24.9k",
                   {"Source": "EN/UVLO bottom"}, to_gnd=True)
    mx, my = join_mid(sh, b1, t2)
    ey = L["EN"][1]
    sh.wire(lx, ey, ex + 9.0, ey)
    sh.wire(ex + 9.0, ey, ex + 9.0, my)
    sh.wire(ex + 9.0, my, mx, my)

    # ---- RON: sets the on-time, and with it the switching frequency ----
    # The datasheet's own tON table (sec.5.5) is linear in RON/VIN:
    # at VIN = 12 V, RON = 25 k gives 830 ns, so K = 830*12/25 = 398 ns.V/k.
    # For 400 kHz at 5 V out, tON = Vout/(Vin*f), so RON = tON*Vin/K is
    # 31.4 k at BOTH 13.5 V and 40 V -- the VIN feedforward is what keeps
    # the frequency fixed across the input range. E96 value 31.6 k.
    #
    # This reproduces buck_preregulator.cir's own gate timings exactly:
    # 925 ns at 13.5 V and 312.5 ns at 40 V. The netlist picked those from
    # D = Vout/Vin; the datasheet arrives at them from RON. They agree.
    ry = L["RON"][1]
    rx_ron = 120.0
    ron_rail = Rail(sh, ry)
    ron_rail.to(lx)
    vpart(sh, "Device:R", "R", rx_ron, ry + 26, "31.6k",
          {"Source": "LM5164 sec.5.5 tON table -- 400 kHz at 5 V out across "
                     "the whole 6-40 V input range; matches "
                     "buck_preregulator.cir's 925 ns / 312.5 ns gate timings"},
          to_gnd=True, rail=ron_rail, tap=False)

    # ---- FB, SW, BST as local nets ----
    fy = L["FB"][1]
    sh.wire(lx, fy, lx - 10.16, fy)
    sh.label("FB_5V", lx - 10.16, fy, rot=180)
    for name, (px, py) in (("SW", R["SW"]), ("BST", R["BST"])):
        sh.wire(px, py, px + 10.16, py)
        sh.label(name, px + 10.16, py)
    # PGOOD is open-drain and needs a pullup. Brought out as a net rather
    # than tied off: the pin map has no channel for it, so it is available
    # and unassigned, which is a fact worth showing rather than hiding.
    py = R["PGOOD"][1]
    pg = Rail(sh, py)
    pg.to(R["PGOOD"][0])
    vpart(sh, "Device:R", "R", R["PGOOD"][0] + 10.16, py + 15, "100k",
          {"Source": "LM5164 sec.4 -- PGOOD is open-drain, 10k-100k pullup"},
          bot_net="5V_MAIN", rail=pg, tap=False)
    sh.label("PGOOD_5V", R["PGOOD"][0] + 10.16, py)

    # ---- BST capacitor: the datasheet specifies the part, not a range ----
    bx = 210.0
    sh.label("BST", bx, 46.0, rot=180)
    sh.wire(bx, 46.0, bx, 50.0)
    sh.place("Device:C", "C", bx, 56.0, "2.2nF/50V X7R",
             fields={"Source": "LM5164 sec.4 pin 7 -- 'a high-quality 2.2nF "
                               "50V X7R ceramic capacitor between BST and "
                               "SW'. A specified part, not a range."})
    a = pin_xy(*PINS["Device:C"]["1"], bx, 56.0, 0)
    b = pin_xy(*PINS["Device:C"]["2"], bx, 56.0, 0)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    sh.wire(bx, 50.0, t[0], t[1])
    sh.wire(bo[0], bo[1], bo[0], bo[1] + 4.0)
    sh.label("SW", bo[0], bo[1] + 4.0, rot=90)

    # ---- output filter ----
    oy = 85.0
    sh.label("SW", 265.0, oy, rot=180)
    sh.wire(265.0, oy, 272.0, oy)
    sh.place("Device:L", "L", 284.0, oy, "33uH", rot=90,
             fields={"Source": "buck_preregulator.cir L1 -- sized by ripple "
                               "at the 40 V worst case, not at nominal"})
    la = pin_xy(*PINS["Device:L"]["1"], 284.0, oy, 90)
    lb = pin_xy(*PINS["Device:L"]["2"], 284.0, oy, 90)
    l_in, l_out = (la, lb) if la[0] < lb[0] else (lb, la)
    sh.wire(272.0, oy, l_in[0], oy)
    out = Rail(sh, oy)
    out.to(l_out[0])
    vpart(sh, "Device:C", "C", 310.0, oy + 22, "47uF/10mOhm",
          {"Source": "buck_preregulator.cir C1/Re1 -- 47 uF with 10 mOhm ESR; "
                     "the ESR is part of the value, it sets the ripple"},
          to_gnd=True, rail=out)
    vpart(sh, "Device:C", "C", 332.0, oy + 22, "100nF",
          {"Source": "high-frequency bypass at the buck output"},
          to_gnd=True, rail=out)

    # ---- feedback divider: 1.2 V reference, so 5 V needs 3.167:1 ----
    #   Vout = 1.2 * (1 + R1/R2); 38.3k / 12.1k gives 5.00 V on E96 values.
    fx = 380.0
    out.to(356.0, tap=True)
    # HIERARCHICAL, not local. 5V_MAIN is a board rail -- the CAN
    # transceivers' VCC, the five difference amplifiers and the discrete
    # inputs' pull-ups all run off it -- and a local label stops at this
    # sheet's edge. It was a local label until 21 Sep 2026, so the
    # project netlist had FOUR separate nets called 5V_MAIN and three of
    # them had no regulator on them. Each sheet's own netlist was correct.
    sh.hlabel("5V_MAIN", 356.0, oy, shape="output")
    t1, b1 = vpart(sh, "Device:R", "R", fx, oy + 16, "38.3k",
                   {"Source": "FB top -- LM5164 VREF is 1.2 V (1.181-1.218, "
                              "+/-1.5%), so 5 V needs 1 + R1/R2 = 4.167"},
                   rail=out, tap=False)
    t2, b2 = vpart(sh, "Device:R", "R", fx, oy + 34, "12.1k",
                   {"Source": "FB bottom"}, to_gnd=True)
    fx2, fmid = join_mid(sh, b1, t2)
    sh.wire(fx2, fmid, fx2 + 12.0, fmid)
    sh.label("FB_5V", fx2 + 12.0, fmid)


def ldo(sh):
    """TLV767-Q1 fixed 3.3 V, and the window it has to live inside."""
    ux, uy = 170.0, 200.0
    P = {n: ic_pin("TLV76733", num, ux, uy) for n, num in
         (("IN", 8), ("EN", 5), ("OUT", 1), ("SNS", 3),
          ("NC2", 2), ("NC7", 7), ("GND4", 4), ("GND6", 6))}
    L = {n: P[n] for n in ("IN", "EN")}
    R = {n: P[n] for n in ("OUT", "SNS")}
    lx, rx = L["IN"][0], R["OUT"][0]

    sh.place(LDO, "U", ux, uy, "TLV76733",
             footprint="Package_SON:VSON-8-1EP_3x3mm_P0.65mm_EP1.65x2.4mm",
             fields={"MPN": "TLV76733QWDRBRQ1",
                     "Source": "TI SBVS381A, fixed version (Figure 5-2)",
                     "Note": "1% over load AND temperature -> 3.267-3.333 V, "
                             "inside the TPS3850G33 window of 3.143-3.459 V "
                             "with ~125 mV at each end"})
    # Both ground pins -- the datasheet says "All ground pins must be
    # grounded" -- joined to one symbol.
    g4, g6 = P["GND4"], P["GND6"]
    gy = max(g4[1], g6[1]) + 6.35
    for g in (g4, g6):
        sh.wire(g[0], g[1], g[0], gy)
    sh.wire(g4[0], gy, g6[0], gy)
    # The ground symbol goes at an END of that wire. Dropping it in the
    # middle is the mid-span case again, and it left both GND pins on a
    # private two-pin net called Net-(U2-GND-Pad4).
    left = min(g4[0], g6[0])
    sh.wire(left, gy, left, gy + 5.08)
    sh.gnd(left, gy + 5.08)

    iy = L["IN"][1]
    sh.label("5V_MAIN", 60.0, iy, rot=180)
    inr = Rail(sh, iy)
    inr.to(60.0)
    vpart(sh, "Device:C", "C", 90.0, iy + 20, "1uF",
          {"Source": "TLV767 sec.5 -- input capacitor, close to IN and GND"},
          to_gnd=True, rail=inr)
    # EN has an internal pullup; tied to IN so the regulator is always on.
    ey = L["EN"][1]
    inr.to(120.0, tap=True)
    sh.wire(120.0, iy, 120.0, ey)
    sh.wire(120.0, ey, lx, ey)
    inr.to(lx)

    oy = R["OUT"][1]
    outr = Rail(sh, oy)
    outr.to(rx)
    vpart(sh, "Device:C", "C", 235.0, oy + 22, "10uF",
          {"Source": "TLV767 sec.5 -- output capacitor"},
          to_gnd=True, rail=outr)
    # SNS is the fixed version's sense pin and must not float -- the
    # datasheet says so outright. Tied to OUT rather than routed to the
    # load, since the load is the decoupling network on the mcu sheet.
    sy = R["SNS"][1]
    outr.to(260.0, tap=True)
    sh.wire(260.0, oy, 260.0, sy)
    sh.wire(260.0, sy, rx, sy)
    outr.to(290.0)
    sh.hlabel("3V3_MCU", 290.0, oy, shape="output")


def _stub(sh, pin, dx, net):
    """A short horizontal wire off a pin, ending in a net label."""
    sh.wire(pin[0], pin[1], pin[0] + dx, pin[1])
    sh.label(net, pin[0] + dx, pin[1], rot=180 if dx < 0 else 0)


def _down(sh, pin, net=None):
    """A short wire down off a pin, to ground or to a label."""
    sh.wire(pin[0], pin[1], pin[0], pin[1] + 5.08)
    if net is None:
        sh.gnd(pin[0], pin[1] + 5.08)
    else:
        sh.label(net, pin[0], pin[1] + 5.08, rot=270)


def sensor_rail(sh):
    """5V_SENSOR: a TPS7B4253-Q1 per group behind a TPS48110-Q1 cut-off.

    Decisions log sections 4 and 7; checked in sensor_rail.cir. Replaces
    the three PTCs (F201-F203) of SENSOR-PTC.
    """
    # ---- rail monitor first, so its references keep their numbers ----
    # 10k/15k from the 5 V rail gives 3.0 V at nominal and 3.08 V at the
    # rail's own high corner -- inside VREFH.
    mx = 540.0
    mon_y = 300.0
    sh.label("5V_MAIN", 500.0, mon_y, rot=180)
    mrail = Rail(sh, mon_y)
    mrail.to(500.0)
    t1, b1 = vpart(sh, "Device:R", "R", mx, mon_y + 16.0, "10k",
                   {"Source": "5V rail monitor top -- pinmap PTC14, the "
                              "ratiometric-correction channel"},
                   rail=mrail, tap=False)
    t2, b2 = vpart(sh, "Device:R", "R", mx, mon_y + 34.0, "15k",
                   {"Source": "5V rail monitor bottom -- 0.6 ratio gives "
                              "3.0 V at a 5.0 V rail, inside VREFH"},
                   to_gnd=True)
    mx2, mmid = join_mid(sh, b1, t2)
    sh.wire(mx2, mmid, mx2 + 14.0, mmid)
    sh.hlabel("SENSOR_5V_MON", mx2 + 14.0, mmid, shape="output")

    sh.text("5V_SENSOR -- TPS48110-Q1 overvoltage cut-off (opens above "
            "40.5-42.1 V, closed through the 40 V dump) feeding one "
            "TPS7B4253-Q1 tracker per sensor group. sensor_rail.cir.",
            40.0, 282.0, size=1.6)

    # ---- the cut-off FET: drain on VBAT_PROT, source on VSNS ----
    qx, qy = 215.0, 318.0
    sh.place("Device:Q_NMOS_GDS", "Q", qx, qy, "IPD90N10S4-06",
             footprint="Package_TO_SOT_SMD:TO-252-2",
             fields={"MPN": "IPD90N10S4-06",
                     "Source": "sensor_rail.cir -- the board's 100 V "
                               "N-FET, one part number fewer",
                     "Note": "Opened by the TPS48110-Q1 for pulse 2a. Its "
                             "gate network also makes it a source "
                             "follower for fast edges: VSNS peaks about "
                             "22 V while the rail clamps at 73 V."})
    qp = PINS["Device:Q_NMOS_GDS"]
    _stub(sh, pin_xy(*qp["1"], qx, qy, 0), -7.62, "OVC_GATE")
    _stub(sh, pin_xy(*qp["2"], qx, qy, 0), 7.62, "VBAT_PROT")
    _stub(sh, pin_xy(*qp["3"], qx, qy, 0), 7.62, "VSNS")

    # ---- the controller ----
    ux, uy = 120.0, 318.0
    sh.place("ecu25kva:TPS48110", "U", ux, uy, "TPS48110",
             footprint="ecu25kva:TI_DGX0019A_VSSOP-19_3x5.1mm_P0.5mm",
             fields={"MPN": "TPS48110AQDGXRQ1",
                     "Source": "TI SLUSEE5E -- decisions log 7",
                     "Note": "Used only for its OV cut-off. Current sense, "
                             "remote temperature and the fault flags are "
                             "tied off as Table 5-1 says to."})
    P = lambda n: ic_pin("TPS48110", n, ux, uy)  # noqa: E731
    for n in (20, 18, 17, 19):                   # VS, CS+, CS-, ISCP
        _stub(sh, P(n), -7.62, "OVC_VS")
    for n in (1, 3):                             # EN/UVLO, INP
        _stub(sh, P(n), -7.62, "5V_MAIN")
    _stub(sh, P(2), -7.62, "OVC_OV")
    _stub(sh, P(15), 7.62, "OVC_PU")
    _stub(sh, P(14), 7.62, "OVC_GATE")           # PD straight to the gate
    _stub(sh, P(12), 7.62, "OVC_BST")
    _stub(sh, P(13), 7.62, "VSNS")               # SRC
    _stub(sh, P(7), 7.62, "GND")                 # IMON, unused
    for n in (6, 8, 9, 10):                      # GND, IWRN, TMR, DIODE
        _down(sh, P(n))

    # ---- its passives, along the bottom ----
    py = 360.0
    vpart(sh, "Device:R", "R", 50.0, py, "100R",
          {"Source": "sensor_rail.cir -- with the 22 nF, holds VS/CS to a "
                     "few V/us against the 60 V/us limit"},
          top_net="VBAT_PROT", bot_net="OVC_VS")
    vpart(sh, "Device:C", "C", 62.0, py, "22nF",
          {"Source": "SLUSEE5E -- 22 nF minimum on VS"},
          top_net="OVC_VS", to_gnd=True)
    vpart(sh, "Device:R", "R", 78.0, py, "340k 0.1%",
          {"Source": "sensor_rail.cir -- OV divider top: trips 40.52-"
                     "42.08 V against OV 1.16-1.20 V"},
          top_net="VBAT_PROT", bot_net="OVC_OV")
    vpart(sh, "Device:R", "R", 90.0, py, "10k 0.1%",
          {"Source": "OV divider bottom. 0.1% because 1% would put the "
                     "lowest trip at 39.8 V, inside the 40 V dump"},
          top_net="OVC_OV", to_gnd=True)
    vpart(sh, "Device:R", "R", 106.0, py, "100k",
          {"Source": "SLUSEE5E Eq. 3, R1 -- with 22 nF, 0.16 A inrush "
                     "into 47 uF"},
          top_net="OVC_PU", bot_net="OVC_GATE")
    vpart(sh, "Device:C", "C", 118.0, py, "22nF",
          {"Source": "SLUSEE5E Figure 8-6, C1 -- gate to ground. Also why "
                     "the FET follows rather than passes a fast edge"},
          top_net="OVC_GATE", bot_net="OVC_C1R")
    vpart(sh, "Device:R", "R", 130.0, py, "10R",
          {"Source": "SLUSEE5E Figure 8-6, R2 -- damps C1"},
          top_net="OVC_C1R", to_gnd=True)
    vpart(sh, "Device:C", "C", 146.0, py, "1uF",
          {"Source": "SLUSEE5E -- BST to SRC, above the FET's gate "
                     "charge (0.1 uF minimum)"},
          top_net="OVC_BST", bot_net="VSNS")
    vpart(sh, "Device:C_Polarized", "C", 240.0, py, "47uF 63V",
          {"Source": "sensor_rail.cir -- hold-up on VSNS; checked at 33 uF "
                     "aged",
           "Note": "Not MLCC -- chosen separately, AEC-Q200, 125 C"},
          top_net="VSNS", to_gnd=True)

    # ---- one tracker per group ----
    for i, grp in enumerate("ABC"):
        tx, ty = 300.0 + i * 70.0, 318.0
        sh.place("ecu25kva:TPS7B4253", "U", tx, ty, "TPS7B4253",
                 footprint="ecu25kva:TI_DDA0008J_HSOIC-8_EP2.95x4.9_Mask2.6x3.2",
                 fields={"MPN": "TPS7B4253QDDARQ1",
                         "Source": "TI SLVSCP3D -- decisions log 4",
                         "Note": f"Group {grp}: tracks 5V_MAIN to +/-4 mV, "
                                 "limits at 301-520 mA, OUT survives "
                                 "-1..45 V"})
        T = lambda n: ic_pin("TPS7B4253", n, tx, ty)  # noqa: E731
        _stub(sh, T(8), -5.08, "VSNS")
        _stub(sh, T(5), -5.08, "5V_MAIN")
        out = f"5V_SENSOR_{grp}"
        _stub(sh, T(1), 5.08, out)
        _stub(sh, T(4), 5.08, out)              # FB to OUT: VOUT = VADJ
        for n in (3, 6, 9):                     # GND, GND, thermal pad
            _down(sh, T(n))
        cy = 360.0
        vpart(sh, "Device:C", "C", tx - 12.0, cy, "100nF",
              {"Source": "SLVSCP3D -- IN capacitor, close to the pins"},
              top_net="VSNS", to_gnd=True)
        vpart(sh, "Device:C", "C", tx, cy, "100nF",
              {"Source": "SLVSCP3D -- ADJ capacitor, close to the pins"},
              top_net="5V_MAIN", to_gnd=True)
        vpart(sh, "Device:C", "C", tx + 12.0, cy, "10uF 50V",
              {"Source": "SLVSCP3D -- 10-500 uF on OUT. 50 V: this pin "
                         "faces the harness, and a short to battery is "
                         "survived at 24 V and the 40 V dump"},
              top_net=out, to_gnd=True)
        # the sheet pin, above the tracker where nothing else is drawn
        sh.wire(tx + 5.0, 293.0, tx + 20.0, 293.0)
        sh.label(out, tx + 5.0, 293.0, rot=180)
        sh.hlabel(out, tx + 20.0, 293.0, shape="output")


def notes(sh):
    sh.text(
        "TWO PARTS CHOSEN HERE, both replacing research memo 07 entries that "
        "were marked representative rather than chosen:\n"
        "  LM5164      memo 07 sec.4 names a 60 V TPS54360B-Q1. "
        "transient_clamp.cir now carries a PASSING check that reads "
        "\"60 V-class parts are NO LONGER\n"
        "              viable downstream\" -- raising the TVS standoff to "
        "43 V, so the part stops conducting during a NORMAL clamped dump, "
        "put the pulse 2a clamp\n"
        "              at 73.3 V. Every rating check in the suite has been "
        "written against the LM5164's own -0.3 V / 100 V VIN limits all "
        "along; the BOM was\n"
        "              simply never reconciled with it. A 60 V buck here is "
        "a part that fails the first pulse 2a event.\n"
        "  TLV76733    memo 07 sec.6 names TLV1117-33QDCYRQ1, explicitly "
        "\"class pricing, not fetched\". The supervisor chosen on the mcu "
        "sheet made 3V3\n"
        "              accuracy load-bearing: outside 3.143-3.459 V the "
        "board resets itself. TLV767-Q1 is 1% over load AND temperature, "
        "giving 3.267-3.333 V.",
        40, 150, size=1.6)
    sh.text(
        "RATIOMETRIC MONITOR: the divider taps 5V_MAIN, and every sensor "
        "group's tracker follows 5V_MAIN to +/-4 mV (0.08%) at any load up "
        "to 300 mA.\n"
        "So one tap now corrects all three groups. With the PTCs it "
        "could not: each dropped about 150 mV (3%) downstream of the tap.",
        40, 255, size=1.6)
    sh.text(
        "PGOOD_5V is brought out and left unassigned. The LM5164 asserts it "
        "open-drain; the pin map has no channel for it. Available, not "
        "wired to anything -- shown rather than hidden.",
        40, 390, size=1.6)


def build():
    schlib.verify_pins()
    sh = Sheet("Rails: buck, 3V3 LDO, 5V sensor distribution", paper="A2",
               comments=[
                   "Generated by hw/gen_sheet_rails.py -- do not hand-edit until it is retired",
                   "Buck values: buck_preregulator.cir. 5V_SENSOR: sensor_rail.cir, decisions log 4 and 7",
                   "LM5164 replaces memo 07's 60 V TPS54360B-Q1 -- see the note on the page",
                   "3V3 must stay inside 3.143-3.459 V or the supervisor resets the board",
               ],
               ref_base=schlib.REF_BASE["rails"])
    buck(sh)
    ldo(sh)
    sensor_rail(sh)
    notes(sh)
    return sh


if __name__ == "__main__":
    print(build().write(OUT, force="--force" in sys.argv))
