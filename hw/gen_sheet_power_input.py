#!/usr/bin/env python3
"""power_input sheet: EMI filter, fuse, TVS, reverse-battery FET, negative clamp.

Stage order is spec sec.4's:  EMI filter -> fuse -> TVS -> reverse-battery
FET -> buck VIN.

Every value on this sheet comes from a simulation block or a BOM tag, and
each part carries its source in a hidden `Source` field so the value and
the reason for it travel together. The EMI filter's topology and values
are emi_filter.cir's, element for element.

BOTH GATES ARE DRIVEN (this docstring said otherwise until 15 Oct 2026):

  Q1 gate  VBAT_REV_GATE   passive: 47k to ground, zener gate-to-source.
                           Q1 became a P-FET on 22 Sep 2026 and needs no
                           controller (see the note at Q1).
  Q2 gate  NCLAMP_GATE     TLV3201-Q1 comparator into a UCC27517A-Q1
                           driver, chosen 22 Sep 2026 (neg_clamp_control).

The same passive P-FET topology protects the pin 04 and pin 06 feeds
(Q103, Q104; decisions log 5b).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import schlib
from schlib import Sheet, Rail, pin_xy, PINS

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "power_input.kicad_sch")
ICPINS = json.load(open(os.path.join(HW, "lib", "ic_pins.json")))

RAIL = 80.0        # the battery rail runs straight across at this y
SHUNT = 100.0      # shunt parts sit here, between rail and ground
GND_Y = 125.0


def series(sh, libid, prefix, x, value, fields):
    """A part in the rail: rotated 90 so its pins land on RAIL."""
    ref = sh.place(libid, prefix, x, RAIL, value, rot=90, fields=fields)
    p = PINS[libid]
    a = pin_xy(*p["1"], x, RAIL, 90)
    b = pin_xy(*p["2"], x, RAIL, 90)
    return ref, min(a[0], b[0]), max(a[0], b[0])


def shunt(sh, libid, prefix, x, value, fields, y=SHUNT, rot=0, to_gnd=True):
    """A part from the rail down to ground."""
    ref = sh.place(libid, prefix, x, y, value, rot=rot, fields=fields)
    p = PINS[libid]
    a = pin_xy(*p["1"], x, y, rot)
    b = pin_xy(*p["2"], x, y, rot)
    top, bot = (a, b) if a[1] < b[1] else (b, a)
    sh.wire(top[0], RAIL, top[0], top[1])
    if to_gnd:
        sh.wire(bot[0], bot[1], bot[0], GND_Y)
        sh.gnd(bot[0], GND_Y)
    return ref, top, bot


def _gnd_below(sh, x, y):
    sh.wire(x, y, x, y + 7.62)
    sh.gnd(x, y + 7.62)


def _ic(sh, part, x, y):
    def p(n):
        d = ICPINS[part][n]
        return pin_xy(d[0], d[1], x, y, 0)
    return p


def _stub(sh, pin, dx, name):
    sh.wire(pin[0], pin[1], pin[0] + dx, pin[1])
    sh.label(name, pin[0] + dx, pin[1], rot=180 if dx < 0 else 0)


def _up(sh, pin, name, hier=False):
    sh.wire(pin[0], pin[1], pin[0], pin[1] - 6.0)
    if hier:
        sh.hlabel(name, pin[0], pin[1] - 6.0, shape="input", rot=90)
    else:
        sh.label(name, pin[0], pin[1] - 6.0, rot=90)


def _to_gnd(sh, x, y, libid, prefix, value, label, fields, rot=0):
    sh.wire(x, y, x, y - 6.0)
    sh.label(label, x, y - 6.0, rot=90)
    sh.place(libid, prefix, x, y + 14.0, value, rot=rot, fields=fields)
    a = pin_xy(*PINS[libid]["1"], x, y + 14.0, rot)
    b = pin_xy(*PINS[libid]["2"], x, y + 14.0, rot)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    sh.wire(x, y, t[0], t[1])
    _gnd_below(sh, bo[0], bo[1])


def _series(sh, y, x0, left, libid, prefix, value, right, fields):
    sh.label(left, x0, y, rot=180)
    px = x0 + 30.0
    sh.place(libid, prefix, px, y, value, rot=90, fields=fields)
    a = pin_xy(*PINS[libid]["1"], px, y, 90)
    b = pin_xy(*PINS[libid]["2"], px, y, 90)
    l, r = (a, b) if a[0] < b[0] else (b, a)
    sh.wire(x0, y, l[0], y)
    sh.wire(r[0], y, px + 30.0, y)
    sh.label(right, px + 30.0, y)


def neg_clamp_control(sh):
    """The comparator and driver behind NCLAMP_GATE, chosen 22 Sep 2026.

    THIS CLAMP IS A LOW-SIDE IDEAL DIODE -- anode ground, cathode VIN --
    and the thresholds say so: ENGAGE when VIN < -100 mV, RELEASE when
    VIN > -5 mV. The release threshold is the one that matters. The first
    model released above +0.12 V, and at the end of every negative pulse
    the returning source drove current back through the still-on clamp at
    1.35 A x 5 mOhm = 6.7 mV -- below release, so it latched on and shorted
    the source. run_sim.py checked only the clamp's minimum and reported it
    resolved; a recovery check found it. -5 mV nominal puts the worst case,
    with TLV3201-Q1's 5 mV offset and every resistor at its tolerance,
    still at or below zero: the clamp lets go before reverse current can
    exceed about 1 A, and cannot latch.

    Both thresholds sit BELOW ground, and a single-supply comparator has
    no negative reference to compare against. So the sense node is lifted
    instead: 10k from VIN and 499k from 5V_MAIN put it at
    0.9804 x VIN + 98.2 mV, which maps -100 mV at VIN to 0 V at the
    comparator. The reference on IN+ is then ground when the output is
    low, and 91.6 mV when it is high -- 10k to ground and 536k from the
    output -- which is the -6.8 mV release, still below zero with the
    comparator's full 5 mV offset against it. Both come off 5V_MAIN, so its
    tolerance cancels.

    SUPPLIES, and the order they die in, is the safety argument:
      comparator  5V_MAIN   -- dead whenever VIN is too low to run the
                               buck, so it CANNOT hold the clamp on at
                               power-up and short the incoming battery.
      driver      12V_GATE  -- from the boost reservoir, held up for
                               ~400 ms after VBAT_PROT collapses, so the
                               clamp keeps its gate drive through a whole
                               pulse. In UVLO its output is held LOW.
    """
    sh.text("NEGATIVE-CLAMP CONTROL -- TLV3201-Q1 comparator into a "
            "UCC27517A-Q1 driver. Engage VIN < -100 mV, release VIN > -6.8 mV.",
            30.0, 192.0, size=1.6)
    cx, cy = 130.0, 210.0
    sh.place("ecu25kva:TLV3201", "U", cx, cy, "TLV3201",
             footprint="Package_TO_SOT_SMD:SOT-353_SC-70-5",
             fields={"Source": "TI SBOS856A -- tPD 50 ns max, push-pull, no "
                               "phase inversion beyond the rails",
                     "Note": "IN- is the lifted sense node; IN+ carries the "
                             "hysteresis. Output HIGH engages the clamp."})
    cp = _ic(sh, "TLV3201", cx, cy)
    _stub(sh, cp("3"), -12.0, "NCL_REF")
    _stub(sh, cp("4"), -22.0, "NCL_SENSE")
    _stub(sh, cp("1"), 14.0, "NCL_OUT")
    _up(sh, cp("5"), "5V_MAIN", hier=True)
    g = cp("2"); _gnd_below(sh, g[0], g[1])

    dx, dy = 250.0, 210.0
    sh.place("ecu25kva:UCC27517A", "U", dx, dy, "UCC27517A",
             footprint="Package_TO_SOT_SMD:SOT-23-5",
             fields={"Source": "TI UCC27517A-Q1 -- 4 A, tD1 23 ns max at "
                               "12 V, output LOW in UVLO",
                     "Note": "Between the comparator and the clamp FET "
                             "because the comparator's 52 mA would take "
                             "about half a microsecond to charge the "
                             "FET's gate; 4 A takes nanoseconds."})
    dp = _ic(sh, "UCC27517A", dx, dy)
    _stub(sh, dp("3"), -12.0, "NCL_OUT")
    q = dp("4")
    sh.wire(q[0], q[1], q[0] - 6.0, q[1])
    _gnd_below(sh, q[0] - 6.0, q[1])
    _stub(sh, dp("5"), 14.0, "NCLAMP_GATE")
    _up(sh, dp("1"), "12V_GATE", hier=True)
    g = dp("2"); _gnd_below(sh, g[0], g[1])

    _series(sh, 238.0, 30.0, "VBAT_PROT", "Device:R", "R", "10k 1%",
            "NCL_SENSE",
            {"Note": "Sense series resistor. Also limits current into the "
                     "comparator input when VIN is 73.3 V (via the clamp "
                     "diode) or -0.5 V (the datasheet allows 10 mA beyond "
                     "the rails; this is under 100 uA)."})
    _series(sh, 254.0, 30.0, "5V_MAIN", "Device:R", "R", "499k 1%",
            "NCL_SENSE",
            {"Note": "Lifts the sense node by 98.2 mV, so VIN = -100 mV "
                     "arrives at the comparator as 0 V and no negative "
                     "reference is needed."})
    _series(sh, 270.0, 30.0, "NCL_OUT", "Device:R", "R", "536k 1%",
            "NCL_REF",
            {"Note": "Hysteresis. With the 10k below: IN+ = 0 V with the "
                     "output low, 91.6 mV with it high -- the -6.8 mV "
                     "release, which stays below zero even with the "
                     "comparator's full 5 mV offset against it. 523k "
                     "sat at +0.5 mV worst case."})
    _to_gnd(sh, 160.0, 238.0, "Device:R", "R", "10k 1%", "NCL_REF",
            {"Note": "Reference to ground."})
    # Upper half only: the sense node must be free to go BELOW ground,
    # which is the whole signal, so A1 is left open.
    ncl = schlib.Rail(sh, 238.0)
    ncl.to(170.0)
    sh.label("NCL_SENSE", 170.0, 238.0, rot=180)
    schlib.rail_clamp(sh, ncl, 190.0, 238.0, "5V_MAIN",
                      {"Tag": "VR-CLAMP",
                       "Note": "Common pin on the sense node, K2 to "
                               "5V_MAIN: holds the comparator input inside "
                               "its rail when VIN is at 73.3 V. A1 OPEN -- "
                               "the lower diode would clamp the negative "
                               "excursion the comparator exists to see. "
                               "Leakage lifts the sense node, which makes "
                               "the clamp release EARLIER, the safe "
                               "direction."}, to_gnd=False)
    _to_gnd(sh, 300.0, 238.0, "Device:C", "C", "100nF", "5V_MAIN",
            {"Note": "Comparator bypass."})
    _to_gnd(sh, 340.0, 238.0, "Device:C", "C", "1uF 25V", "12V_GATE",
            {"Note": "Driver bypass -- it sources 4 A peak into the clamp "
                     "FET's gate."})


def power_feed(sh, ry, pin_net, rail_net, title, load_note):
    """One high-current feed: TVS -> reverse P-FET -> Schottky -> bulk.

    POWER-PATH, decided 8 Oct 2026 (docs/decisions-log.md 2a): the
    injector and EGR loads leave pin 21 for pins 04 and 06, each fused
    10 A in the loom. Same protection as pin 21 less what these loads do
    not need -- no EMI inductor (a 22 uH part carrying 10 A is what this
    move removes) and no active negative clamp (that exists for the
    buck's -0.3 V pins; switch and bridge FETs ride the Schottky's
    -0.5 V). Checked in sim/blocks/power_path.cir.
    """
    sh.text(title, 30.0, ry - 12.0, size=1.6)
    sh.hlabel(pin_net, 30.0, ry, shape="input")
    rail = Rail(sh, ry)
    rail.to(30.0)

    def vshunt(libid, prefix, x, value, fields, rot):
        y = ry + 20.0
        sh.place(libid, prefix, x, y, value, rot=rot, fields=fields)
        a = pin_xy(*PINS[libid]["1"], x, y, rot)
        b = pin_xy(*PINS[libid]["2"], x, y, rot)
        top, bot = (a, b) if a[1] < b[1] else (b, a)
        sh.wire(top[0], ry, top[0], top[1])
        _gnd_below(sh, bot[0], bot[1])

    rail.to(60.0, tap=True)
    vshunt("Device:D_TVS", "D", 60.0, "SMCJ43CA",
           {"Source": "transient_clamp.cir, load_dump.cir -- the pin-21 "
                      "TVS, same pulses on this pin",
            "Rotation": "bidirectional -- orientation not significant"}, 90)

    # P-FET, drain to the pin, source to the load: rot 90 as Q1.
    qx, qy = 100.0, ry + 2.54
    qp = PINS["Device:Q_PMOS_GDS"]
    sh.place("Device:Q_PMOS_GDS", "Q", qx, qy, "SQM120P10-10m1L", rot=90,
             footprint="Package_TO_SOT_SMD:TO-263-2",
             fields={
                 "MPN": "SQM120P10-10m1L",
                 "Source": "power_path.cir -- Vishay doc 76943 Rev. A",
                 "Note": "Reverse-battery block, passive gate as Q1 on "
                         "pin 21. " + load_note,
                 "Rds_on": "10.1 mOhm max at -10 V, 20.5 mOhm at 175 C, "
                           "15.0 mOhm at -4.5 V; RthJA 40 C/W"})
    qd = pin_xy(*qp["2"], qx, qy, 90)
    qs = pin_xy(*qp["3"], qx, qy, 90)
    qg = pin_xy(*qp["1"], qx, qy, 90)
    assert abs(qd[1] - ry) < 0.01 and abs(qs[1] - ry) < 0.01, (qd, qs)
    rail.to(qd[0])

    gy = qg[1] + 5.0
    sh.wire(qg[0], qg[1], qg[0], gy)
    sh.label(rail_net + "_GATE", qg[0], gy, rot=180)
    sh.place("Device:R", "R", qg[0], gy + 12.0, "47k",
             fields={"Note": "Gate to ground, as Q1: Vgs = -V(rail), on "
                             "whenever the load side is positive."})
    ra = pin_xy(*PINS["Device:R"]["1"], qg[0], gy + 12.0, 0)
    rb = pin_xy(*PINS["Device:R"]["2"], qg[0], gy + 12.0, 0)
    r_top, r_bot = (ra, rb) if ra[1] < rb[1] else (rb, ra)
    sh.wire(qg[0], gy, r_top[0], r_top[1])
    _gnd_below(sh, r_bot[0], r_bot[1])
    sh.junction(qg[0], gy)

    out = Rail(sh, ry)
    out.to(qs[0])
    zx = qx + 25.0
    out.to(zx, tap=True)
    sh.place("Device:D_Zener", "D", zx, ry + 6.0, "12V", rot=270,
             fields={"Note": "Cathode to SOURCE, anode to GATE: clamps "
                             "Vgs at -12 V against the +/-20 V rating."})
    zk = pin_xy(*PINS["Device:D_Zener"]["1"], zx, ry + 6.0, 270)
    za = pin_xy(*PINS["Device:D_Zener"]["2"], zx, ry + 6.0, 270)
    sh.wire(zx, ry, zk[0], zk[1])
    sh.wire(za[0], za[1], za[0], gy)
    sh.wire(za[0], gy, qg[0], gy)

    out.to(150.0, tap=True)
    vshunt("Device:D_Schottky", "D", 150.0, "100V 20A",
           {"Source": "negative_pulses.cir Dneg1 -- pin 21's backstop, "
                      "the same pulse 1 on this pin",
            "Note": "Cathode to the rail, anode to ground. Holds the rail "
                    "at about -0.5 V while the FET turns off."}, 270)
    for cx in (170.0, 185.0):
        out.to(cx, tap=True)
        vshunt("Device:C", "C", cx, "2.2uF 100V",
               {"Note": "Rail bulk at the feed. 100 V class: the rail "
                        "reaches 73.3 V on pulse 2a."}, 0)
    out.to(205.0)
    sh.label(rail_net + "_IN", 205.0, ry)


def feed_filter(sh, ry, rail_net):
    """The feed's conducted-emissions filter: 10 uH, two bulk cans and two
    R-C dampers (sim/blocks/feed_emi.cir; decisions log 10). Placed after
    every other part on the sheet so their references keep their numbers.
    """
    x0 = 225.0
    sh.label(rail_net + "_IN", x0, ry)
    sh.place("Device:L", "L", x0 + 15.0, ry, "10uH 16A", rot=90,
             fields={"Source": "feed_emi.cir Lf",
                     "Note": "Unfiltered, this feed is 33-48 dB over CISPR "
                             "25 Class 5. Rated 55 V across the winding; "
                             "pulse 2a puts 48.7 V across it."})
    la = pin_xy(*PINS["Device:L"]["1"], x0 + 15.0, ry, 90)
    lb = pin_xy(*PINS["Device:L"]["2"], x0 + 15.0, ry, 90)
    ll, lr = (la, lb) if la[0] < lb[0] else (lb, la)
    sh.wire(x0, ry, ll[0], ll[1])
    out = Rail(sh, ry)
    out.to(lr[0])

    def shunt(libid, prefix, x, y, value, fields, top_net=None):
        sh.place(libid, prefix, x, y, value, fields=fields)
        a = pin_xy(*PINS[libid]["1"], x, y, 0)
        b = pin_xy(*PINS[libid]["2"], x, y, 0)
        return (a, b) if a[1] < b[1] else (b, a)

    hxc = {"Source": "feed_emi.cir HXC",
           "Note": "Bulk: takes the chopping and PWM ripple so the inductor "
                   "carries DC. 1.05x on ripple at EGR stall, 25 kHz."}
    for x in (x0 + 35.0, x0 + 55.0):
        out.to(x, tap=True)
        t, bo = shunt("Device:C_Polarized", "C", x, ry + 20.0, "82uF 80V", hxc)
        sh.wire(x, ry, t[0], t[1])
        _gnd_below(sh, bo[0], bo[1])
    for i, x in enumerate((x0 + 75.0, x0 + 95.0)):
        out.to(x, tap=True)
        mid = f"{rail_net}_D{i + 1}"
        t, bo = shunt("Device:R", "R", x, ry + 10.0, "0R68 1206",
                      {"Source": "feed_emi.cir Rd",
                       "Note": "Damper. Holds the filter's output impedance "
                               "to 0.64 ohm aged, under the hold loop's and "
                               "boost's -0.94 ohm at 9 V. A resistor, not a "
                               "wet capacitor's ESR, which rises 8x cold."})
        sh.wire(x, ry, t[0], t[1])
        sh.wire(bo[0], bo[1], bo[0], bo[1] + 3.0)
        sh.label(mid, bo[0], bo[1] + 3.0)
        ct, cb = shunt("Device:C_Polarized", "C", x, ry + 24.0, "82uF 80V",
                       {"Source": "feed_emi.cir damper", "Note":
                        "Damper capacitor, in series with the 0.68 ohm above"})
        sh.wire(ct[0], ct[1], ct[0], bo[1] + 3.0)
        _gnd_below(sh, cb[0], cb[1])
    out.to(x0 + 115.0)
    sh.hlabel(rail_net, x0 + 115.0, ry, shape="output")


def build():
    schlib.verify_pins()
    sh = Sheet("Power input and transient protection", paper="A2",
               comments=[
                   "Generated by hw/gen_sheet_power_input.py -- do not hand-edit until it is retired",
                   "EMI filter values are emi_filter.cir element for element",
                   "TVS and clamp: docs/bom_requirements.md tags TVS, NEG-CLAMP",
                   "Q1: P-FET, passive gate. Q2: comparator + driver, a low-side ideal diode that MUST release",
               ],
               ref_base=schlib.REF_BASE["power_input"])

    # ---- input from the connector sheet ----
    sh.hlabel("VBAT_IN", 30, RAIL, shape="input")
    sh.wire(30, RAIL, 48.19, RAIL)

    # ---- fuse ----
    # 5 A since 8 Oct 2026. It was 20 A, "matching the OEM harness fuse
    # 8F1 class", while every load on the board ran through it; POWER-PATH
    # left it the electronics only, 2.95 A as an upper bound.
    _, _, f_r = series(sh, "Device:Fuse", "F", 52, "5A",
                       {"Source": "run_sim.py emi_filter (pin 21 load), "
                                  "transient_clamp and negative_pulses "
                                  "(pulse I2t)",
                       })

    # ---- EMI filter, first stage ----
    _, l1_l, l1_r = series(sh, "Device:L", "L", 80, "22uH",
                           {"Source": "emi_filter.cir L1 -- RDC and "
                                      "self-resonance modelled"})
    sh.wire(f_r, RAIL, l1_l, RAIL)

    # C1 is two 2.2 uF 100 V parts: 4.7 uF at 100 V is not in KEMET's
    # automotive X7R range, and this node sees 73.3 V. emi_filter.cir
    # models the pair (4.4 uF, ESR and ESL halved).
    for cx in (92, 108):
        shunt(sh, "Device:C", "C", cx, "2.2uF 100V",
              {"Source": "emi_filter.cir C1 -- one of two in parallel",
               "ESR": "5 mOhm max each"})
    sh.wire(l1_r, RAIL, 92, RAIL)
    sh.wire(92, RAIL, 108, RAIL)
    sh.junction(92, RAIL)
    sh.junction(108, RAIL)
    sh.label("VBAT_EMI1", 92, RAIL)

    # ---- EMI filter, second stage: Lf damped by Rf in parallel ----
    _, lf_l, lf_r = series(sh, "Device:L", "L", 138, "0.47uH",
                           {"Source": "emi_filter.cir Lf -- RDC and "
                                      "self-resonance modelled"})
    sh.wire(108, RAIL, lf_l, RAIL)
    # Rf sits above the rail, across Lf -- the damping that stops the
    # second stage ringing with C2.
    rf_y = RAIL - 15.24
    sh.place("Device:R", "R", 138, rf_y, "120R",
             rot=90, fields={"Source": "emi_filter.cir Rf -- damps Lf"})
    ra = pin_xy(*PINS["Device:R"]["1"], 138, rf_y, 90)
    rb = pin_xy(*PINS["Device:R"]["2"], 138, rf_y, 90)
    for px in (min(ra[0], rb[0]), max(ra[0], rb[0])):
        sh.wire(px, rf_y, px, RAIL)
        sh.junction(px, RAIL)

    shunt(sh, "Device:C", "C", 170, "100nF",
          {"Source": "emi_filter.cir C2 -- ESR 20 mOhm, ESL 0.5 nH modelled",
           "ESR": "20 mOhm max"})
    sh.wire(lf_r, RAIL, 170, RAIL)
    sh.junction(170, RAIL)

    # ---- damping leg: Cd in series with Rd, both to ground ----
    cd_ref, cd_top, cd_bot = shunt(
        sh, "Device:C", "C", 198, "1uF",
        {"Source": "emi_filter.cir Cd -- damping leg, series with Rd"},
        y=SHUNT - 3.81, to_gnd=False)
    rd_y = SHUNT + 11.43
    sh.place("Device:R", "R", 198, rd_y, "2R2",
             fields={"Source": "emi_filter.cir Rd -- damping leg"})
    rda = pin_xy(*PINS["Device:R"]["1"], 198, rd_y, 0)
    rdb = pin_xy(*PINS["Device:R"]["2"], 198, rd_y, 0)
    rtop, rbot = (rda, rdb) if rda[1] < rdb[1] else (rdb, rda)
    sh.wire(cd_bot[0], cd_bot[1], rtop[0], rtop[1])
    sh.label("EMI_DAMP", cd_bot[0], cd_bot[1], rot=180)
    sh.wire(rbot[0], rbot[1], rbot[0], GND_Y)
    sh.gnd(rbot[0], GND_Y)
    sh.wire(170, RAIL, 198, RAIL)
    sh.junction(198, RAIL)

    # ---- TVS ----
    shunt(sh, "Device:D_TVS", "D", 232, "SMCJ43CA",
          {"Source": "bom_requirements TVS; load_dump.cir, transient_clamp.cir",
           "MPN": "SMCJ43CA",
           "Note": "43 V standoff clears the 40 V clamped dump; "
                   "1500 W package clamps pulse 2a at 73.3 V vs the buck's 100 V max",
           "Rotation": "bidirectional -- orientation not significant"},
          rot=90)
    sh.wire(198, RAIL, 232, RAIL)
    sh.junction(232, RAIL)
    # A label attaches only if it sits EXACTLY on the wire. Offsetting it
    # for looks detaches it silently: the net keeps its auto-generated
    # name and the schematic reads as connected while the netlist says
    # otherwise. Every label on this sheet is therefore on a wire point.
    sh.label("VBAT_CLAMPED", 240, RAIL)

    # ---- reverse-battery FET: P-CHANNEL, drain to battery, source to load --
    # CORRECTED 22 Sep 2026. reverse_battery.cir has always modelled this
    # stage as "a P-FET held on by a controller that watches the
    # polarity" -- its own header says so, and its switch model closes on
    # positive input polarity. This sheet drew an N-FET with a controller
    # gate left undriven. Another document and executable file
    # disagreeing, found by trying to choose the controller:
    #
    #   The node this FET sits on swings from +73.3 V (pulse 2a, after the
    #   TVS) to -47.8 V (pulse 1, the bidirectional TVS's negative clamp,
    #   which is bidirectional precisely so a reversed battery does not
    #   forward-bias it). No controller IC checked spans that:
    #     LM74700-Q1  ANODE -65 V to +65 V  -- positive side short by 8.3 V
    #     LM5050-1-Q1 IN -0.3 V to +100 V   -- negative side short by 47.5 V,
    #                 and IN draws 320 uA, so a series resistor to protect
    #                 it would corrupt its 20 mV drain-source sense.
    #
    # A P-FET needs no controller: gate to ground through a resistor, a
    # zener gate-to-source. Vgs = -V(load), so it is on whenever the load
    # side is positive and off when it is pulled to zero -- which IS the
    # block's switch model, with no IC ratings on that 121 V swing to
    # violate. What it gives up is recorded on the page.
    q1y = RAIL + 2.54
    # rot 90 puts DRAIN on the left (battery) and SOURCE on the right
    # (load), gate below. The P-channel body diode runs drain to source,
    # so this is the orientation that conducts forward and blocks a
    # reversed battery.
    sh.place("Device:Q_PMOS_GDS", "Q", 268, q1y, "SQD50P08-25L", rot=90,
             footprint="Package_TO_SOT_SMD:TO-252-2",
             fields={
                 "MPN": "SQD50P08-25L",
                 "Source": "reverse_battery.cir path B -- modelled as a "
                           "P-FET all along",
                 "Note": "Drain to battery, source to load. |Vds| worst "
                         "case is 47.8 V, blocking pulse 1 with the load "
                         "side clamped near zero; 80 V class anyway, by "
                         "the board's own rail rule.",
                 "Rds_on": "31 mOhm max at -4.5 V (Vishay SQD50P08-25L; "
                           "req. <=40): 0.16 V at 5 A "
                           "against reverse_battery.cir's 0.3 V "
                           "requirement, and specified at -4.5 V because "
                           "at a 6 V cranking dip that is all the gate "
                           "gets"})
    qp = PINS["Device:Q_PMOS_GSD"]
    q1s = pin_xy(*qp["2"], 268, q1y, 90)
    q1d = pin_xy(*qp["3"], 268, q1y, 90)
    q1g = pin_xy(*qp["1"], 268, q1y, 90)
    sh.wire(232, RAIL, q1d[0], q1d[1])

    # Gate network. The zener clamps Vgs: without it the gate would sit
    # 73.3 V below the source during pulse 2a.
    gy = q1g[1] + 5.0
    sh.wire(q1g[0], q1g[1], q1g[0], gy)
    sh.label("VBAT_REV_GATE", q1g[0], gy, rot=180)
    sh.place("Device:R", "R", q1g[0], gy + 12.0, "47k",
             fields={"Note": "Gate to ground. Carries (73.3 - 12) / 47k = "
                             "1.3 mA through pulse 2a, 32 uA at 13.5 V. "
                             "With Ciss it also sets the turn-off time "
                             "when the load side is pulled to zero -- "
                             "tens of microseconds, which is why the "
                             "negative clamp is sized for this FET "
                             "staying ON through a whole pulse."})
    ra = pin_xy(*PINS["Device:R"]["1"], q1g[0], gy + 12.0, 0)
    rb = pin_xy(*PINS["Device:R"]["2"], q1g[0], gy + 12.0, 0)
    r_top, r_bot = (ra, rb) if ra[1] < rb[1] else (rb, ra)
    sh.wire(q1g[0], gy, r_top[0], r_top[1])
    sh.wire(r_bot[0], r_bot[1], r_bot[0], GND_Y)
    sh.gnd(r_bot[0], GND_Y)
    sh.junction(q1g[0], gy)

    zx = 286.0
    sh.place("Device:D_Zener", "D", zx, RAIL + 6.0, "12V", rot=270,
             fields={"Note": "Cathode to SOURCE, anode to GATE: clamps Vgs "
                             "at -12 V, inside a P-FET's +/-20 V rating, "
                             "whatever the rail does."})
    zk = pin_xy(*PINS["Device:D_Zener"]["1"], zx, RAIL + 6.0, 270)
    za = pin_xy(*PINS["Device:D_Zener"]["2"], zx, RAIL + 6.0, 270)
    sh.wire(za[0], za[1], za[0], gy)
    sh.wire(za[0], gy, q1g[0], gy)
    # The rail is split at the zener's tap -- a wire landing mid-span on
    # another wire does not connect in KiCad 7.
    sh.wire(q1s[0], q1s[1], zx, RAIL)
    sh.wire(zx, RAIL, zk[0], zk[1])
    sh.junction(zx, RAIL)
    q1d = (zx, RAIL)

    # ---- negative clamp: Schottky backstop in parallel with an active FET --
    sh.wire(q1d[0], q1d[1], 305, RAIL)
    shunt(sh, "Device:D_Schottky", "D", 305, "100V 20A",
          {"Source": "bom_requirements NEG-CLAMP (backstop); "
                     "negative_pulses.cir Dneg1",
           "Note": "Carries 13.58 A peak / 14.5 mJ on ISO 7637-2 pulse 1. "
                   "Instant, passive -- holds the node while the comparator "
                   "decides. Cathode to VIN, anode to ground.",
           "Vr": "100 V class. It was 60 V until 22 Sep 2026: rated for "
                 "the negative pulse it exists to catch, and not for pulse "
                 "2a pushing the SAME node to +73.3 V in reverse.",
           "Ipk": "13.58 A measured"},
          rot=270)
    sh.junction(305, RAIL)

    q2y = SHUNT
    q2 = sh.place("Device:Q_NMOS_GDS", "Q", 340, q2y, "IPD90N10S4-06",
                  footprint="Package_TO_SOT_SMD:TO-252-2",
                  fields={
                      "MPN": "IPD90N10S4-06",
                      "Source": "bom_requirements NEG-CLAMP; "
                                "negative_pulses.cir Scl1",
                      "Note": "Active clamp. 15 A through 5 mOhm is 75 mV, "
                              "against a -0.3 V rating no junction device "
                              "can meet (0.367 V junction + 0.180 V bulk).",
                      "Vds": "100 V class. It was 40 V until 22 Sep 2026 -- "
                             "sized for the negative pulses it clamps, with "
                             "its drain on a node pulse 2a drives to "
                             "+73.3 V. 40 V had zero margin on the load "
                             "dump alone.",
                      "Rds_on": "6.7 mOhm max at Vgs = 10 V (Infineon "
                                "IPD90N10S4-06). Gate from UCC27517A on "
                                "12V_GATE, so the 10 V point is the one "
                                "that applies; +/-20 V Vgs"})
    q2s = pin_xy(*qp["2"], 340, q2y, 0)
    q2d = pin_xy(*qp["3"], 340, q2y, 0)
    q2g = pin_xy(*qp["1"], 340, q2y, 0)
    sh.wire(q2d[0], q2d[1], q2d[0], RAIL)
    sh.junction(q2d[0], RAIL)
    sh.wire(305, RAIL, q2d[0], RAIL)
    sh.wire(q2s[0], q2s[1], q2s[0], GND_Y)
    sh.gnd(q2s[0], GND_Y)
    sh.wire(q2g[0], q2g[1], q2g[0] - 15.24, q2g[1])
    sh.label("NCLAMP_GATE", q2g[0] - 15.24, q2g[1])

    # ---- output to the rails sheet ----
    sh.wire(q2d[0], RAIL, 380, RAIL)
    sh.hlabel("VBAT_PROT", 380, RAIL, shape="output")
    sh.label("VBAT_PROT", 364, RAIL)

    neg_clamp_control(sh)

    # ---- POWER-PATH: the high-current feeds, after every pin-21 part so
    # the existing references keep their numbers ----
    power_feed(sh, 300.0, "V_BAT_1R", "VBAT_INJ",
               "PIN 04 -> VBAT_INJ: injector hold switches and the boost "
               "converter input. 10 A loom fuse.",
               "Injector: 10.98 A peak, 3.8 A RMS -- Tj 117 C at a 105 C "
               "board.")
    power_feed(sh, 360.0, "V_BAT_2R", "VBAT_EGR",
               "PIN 06 -> VBAT_EGR: the EGR H-bridge. 10 A loom fuse.",
               "EGR: 6.4 A stall, continuous -- Tj 139 C at a 105 C board, "
               "155 C while cranking.")
    # ---- their conducted-emissions filters, after everything else ----
    feed_filter(sh, 300.0, "VBAT_INJ")
    feed_filter(sh, 360.0, "VBAT_EGR")

    # ---- the note that makes the decisions visible ----
    sh.text(
        "GATE DRIVE -- both power-path gates are driven:\\n"
        "  VBAT_REV_GATE   Q1 is a P-FET: 47k gate to ground, zener "
        "gate-to-source. No controller needed.\\n"
        "  NCLAMP_GATE     Q2 (negative clamp): TLV3201-Q1 comparator into a "
        "UCC27517A-Q1 driver.\\n"
        "                  Engage below -100 mV, release above -5 mV "
        "(see neg_clamp_control).\\n"
        "Keep U102 at Q2's gate with a short return to Q2's source: the "
        "clamp's speed is the gate loop's.",
        30, 150, size=1.6)
    sh.text(
        "Stage order is spec sec.4: EMI filter -> fuse -> TVS -> "
        "reverse-battery FET -> buck VIN.\\n"
        "EMI filter values are emi_filter.cir element for element. Every "
        "part carries its source in a hidden Source field.",
        30, 175, size=1.6)
    return sh


if __name__ == "__main__":
    sh = build()
    force = "--force" in sys.argv
    print(sh.write(OUT, force=force))
