#!/usr/bin/env python3
"""discrete_io sheet: switch inputs, relay drivers, the ignition wake.

Eight input channels and two outputs, all on Bosch pins
(refs/bosch-pinout-md1cs162.md). Three blocks back it:
discrete_input.cir, relay_driver.cir, main_relay.cir.

The Bosch pinout, 8 Nov 2026 (decisions log sec.18), changed three
things here:

  - Pin 50's driver gets a second FET, gated from pin 71, so the
    ignition closes the main relay in hardware. Under Bosch's wiring
    the relay's contact is the board's only supply.
  - Pin 50's flyback diode to VBAT_PROT became a TVS to ground. The
    coil sits on Term. 30, so that diode fed the board through the coil
    with the relay open, and held the relay in (main_relay.cir B).
  - The supervised trip loop is gone: it had no Bosch pin. Pins 21
    (water in fuel), 14 (diagnosis request) and 25 (stop switch) are
    new inputs, on the same NPN buffer as the others.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import schlib
from schlib import Sheet, Rail, pin_xy, PINS
import json

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "discrete_io.kicad_sch")
GND_DROP = 7.62
QP = PINS["Device:Q_NMOS_GSD"]
ICPINS = json.load(open(os.path.join(HW, "lib", "ic_pins.json")))


def ic_pin(part, num, x, y):
    dx, dy = ICPINS[part][str(num)]
    return pin_xy(dx, dy, x, y, 0)


def gnd_below(sh, x, y):
    sh.wire(x, y, x, y + GND_DROP)
    sh.gnd(x, y + GND_DROP)


def vshunt(sh, libid, prefix, x, y, value, fields, rail, rot=0):
    """A part from a rail down to ground."""
    sh.place(libid, prefix, x, y, value, rot=rot, fields=fields)
    a = pin_xy(*PINS[libid]["1"], x, y, rot)
    b = pin_xy(*PINS[libid]["2"], x, y, rot)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    rx, ry = rail.to(t[0], tap=True)
    sh.wire(rx, ry, t[0], t[1])
    gnd_below(sh, bo[0], bo[1])


def buffered_input(sh, x0, y, in_net, out_net, label, pullup=None):
    """discrete_input.cir since 22 Sep 2026: an NPN buffer, not a clamp.

    IN -> 10k -> base; 4.7k and 4.7 uF base to ground; BAV199-Q lower
    diode holds the base above -1 V on reverse battery; PMBT3904-Q
    collector is the MCU pad, pulled to 3V3_MCU by 10k. The pad never
    leaves 0..3.3 V whatever the harness does, and nothing on it is a
    clamp that has to conduct. LOGIC IS INVERTED: pad low = input high
    (for a contact-to-ground channel: contact OPEN)."""
    sh.hlabel(in_net, x0, y, shape="input")
    chain = Rail(sh, y)
    chain.to(x0)
    if pullup:
        # Harness side, as before: a battery short meets the 10k input
        # resistor, not the MCU.
        sh.place("Device:R", "R", x0 + 16.0, y - 18.0, pullup,
                 fields={"Source": "pull-up for a switch-to-ground contact "
                                   "(pinmap sec.1.4)",
                         "Note": "Contact open: 5 V through this and the "
                                 "10k input resistor saturates the buffer "
                                 "(discrete_input.cir, hFE 30 at -40 C). "
                                 "Contact closed: 0.5 mA wetting current."})
        a = pin_xy(*PINS["Device:R"]["1"], x0 + 16.0, y - 18.0, 0)
        b = pin_xy(*PINS["Device:R"]["2"], x0 + 16.0, y - 18.0, 0)
        t, bo = (a, b) if a[1] < b[1] else (b, a)
        rx, ry = chain.to(x0 + 16.0, tap=True)
        sh.wire(rx, ry, bo[0], bo[1])
        sh.wire(t[0], t[1], t[0], t[1] - 6.35)
        sh.label("5V_MAIN", t[0], t[1] - 6.35)

    sx = x0 + 34.0
    sh.place("Device:R", "R", sx, y, "10k", rot=90,
             fields={"Source": "discrete_input.cir R1",
                     "Note": "10k, not 100k: 1.1 mA of wetting current "
                             "through a closed contact at 12 V. Non-gold "
                             "contacts at 0.1 mA oxidise open in the "
                             "field."})
    ra = pin_xy(*PINS["Device:R"]["1"], sx, y, 90)
    rb = pin_xy(*PINS["Device:R"]["2"], sx, y, 90)
    r_in, r_out = (ra, rb) if ra[0] < rb[0] else (rb, ra)
    chain.to(r_in[0])
    base = Rail(sh, y)
    base.to(r_out[0])
    sh.label(out_net + "_B", r_out[0], y)
    vshunt(sh, "Device:R", "R", x0 + 50.0, y + 18.0, "4.7k",
           {"Source": "discrete_input.cir R2",
            "Note": "Holds the base off: a harness floating at 1 V reads "
                    "inactive even with a typical part at 125 C"}, base)
    vshunt(sh, "Device:C", "C", x0 + 62.0, y + 18.0, "4.7uF",
           {"Source": "discrete_input.cir C1",
            "Note": "(10k || 4.7k) x 4.7 uF = 15 ms debounce"}, base)
    schlib.rail_clamp(sh, base, x0 + 88.0, y, None,
                      {"Source": "discrete_input.cir Dneg",
                       "Note": "Lower diode only (K2 open): base above "
                               "-1 V on -24 V reverse battery, inside the "
                               "transistor's VEBO of 6 V"})
    qx = x0 + 110.0
    qp = PINS["Device:Q_NPN_BEC"]
    bpin = pin_xy(*qp["1"], qx, y, 0)
    cpin = pin_xy(*qp["3"], qx, y, 0)
    epin = pin_xy(*qp["2"], qx, y, 0)
    base.to(bpin[0])
    sh.place("Device:Q_NPN_BEC", "Q", qx, y, "PMBT3904-Q",
             footprint="Package_TO_SOT_SMD:SOT-23",
             fields={"MPN": "PMBT3904-Q",
                     "Note": "Buffer. 6 V input saturates it with hFE 30 "
                             "at -40 C (pad 0.03 V); SOT-23 B-E-C"})
    gnd_below(sh, epin[0], epin[1])
    ky = y - 12.0
    sh.wire(cpin[0], cpin[1], cpin[0], ky)
    ry = ky - 12.0
    sh.place("Device:R", "R", cpin[0], ry, "10k",
             fields={"Source": "discrete_input.cir Rpu",
                     "Note": "Pad pull-up to its own rail -- the pad sees "
                             "0..3.3 V and nothing else"})
    pa = pin_xy(*PINS["Device:R"]["1"], cpin[0], ry, 0)
    pb = pin_xy(*PINS["Device:R"]["2"], cpin[0], ry, 0)
    pt, pbo = (pa, pb) if pa[1] < pb[1] else (pb, pa)
    sh.wire(cpin[0], ky, pbo[0], pbo[1])
    sh.junction(cpin[0], ky)
    sh.wire(pt[0], pt[1], pt[0], pt[1] - 3.81)
    sh.label("3V3_MCU", pt[0], pt[1] - 3.81)
    sh.wire(cpin[0], ky, x0 + 130.0, ky)
    sh.hlabel(out_net, x0 + 130.0, ky, shape="output")
    sh.text(label + "\nINVERTED: pad LOW = input active", x0 + 152.0,
            ky - 2.0, size=1.6)


def relay(sh, x0, y, gate_net, out_net, label, clamp="diode",
          wake_net=None):
    """relay_driver.cir: low-side switch, coil to battery.

    clamp="diode": flyback diode to VBAT_PROT (the buzzer relay, whose
    coil sits on the main-relay line and dies with the board).
    clamp="tvs": TVS drain to ground (the main relay). Its coil sits on
    Term. 30, always live, and a diode to VBAT_PROT would power the
    board through the coil with the relay open -- main_relay.cir part B.
    wake_net: a second FET in parallel, gated from the ignition, so the
    relay closes in hardware before the MCU has power (main_relay.cir
    part A)."""
    sh.text(label, x0, y - 26.0, size=1.6)
    # The coil itself is off-sheet -- it lives in the harness. What this
    # board carries is the switch, the turn-off clamp and the gate network.
    dx = x0 + 30.0
    drain = Rail(sh, y)
    if clamp == "diode":
        sh.place("Device:D", "D", dx, y - 18.0, "100V 1A fast", rot=270,
                 fields={"Source": "relay_driver.cir D1",
                         "Note": "Without it, interrupting 84 mA in a 1.2 H "
                                 "coil has nowhere to go -- relay_driver.cir's "
                                 "second branch is that case. Cathode to "
                                 "battery. Safe here only because this coil "
                                 "is fed from the main-relay line, which "
                                 "dies with VBAT_PROT.",
                         "Vr": "100 V class, per transient_clamp's rail "
                               "rating"})
        da = pin_xy(*PINS["Device:D"]["1"], dx, y - 18.0, 270)
        db = pin_xy(*PINS["Device:D"]["2"], dx, y - 18.0, 270)
        d_k, d_a = (da, db) if da[1] < db[1] else (db, da)
        # Straight in at the cathode's own height -- drawn to the diode's
        # centre line, this wire ran diagonally to a pin 3.81 mm above it.
        sh.wire(x0, d_k[1], d_k[0], d_k[1])
        sh.hlabel("VBAT_PROT", x0, d_k[1], shape="input")
        drain.to(d_a[0])
        sh.wire(d_a[0], d_a[1], d_a[0], y)
    if clamp == "diode":
        drain.to(x0 + 14.0, tap=True)
        sh.hlabel(out_net, x0 + 14.0, y, shape="output")
        drain.x = None
        drain.to(dx)
    else:
        drain.to(x0 + 14.0)
        sh.hlabel(out_net, x0 + 14.0, y, shape="output")

    qx = x0 + 52.0
    sh.place("Device:Q_NMOS_GSD", "Q", qx, y + 16.0, "PMV280ENEA",
             rot=270, footprint="Package_TO_SOT_SMD:SOT-23",
             fields={"Source": "relay_driver.cir S1 (Ron 50 mOhm); "
                               "Nexperia PMV280ENEA datasheet",
                     "MPN": "PMV280ENEA",
                     "Note": "100 V class because the drain sits on "
                             "VBAT_PROT. Coil current is only 13.5/160 = "
                             "84 mA, so Rds(on) is not the constraint -- "
                             "the voltage class is.",
                     "Vgs": "Driven at 4.4 V min by the AHCT buffer: Rds(on) "
                            "432 mOhm max at 4.5 V, 36 mV at 84 mA. +/-20 V "
                            "Vgs, Vth 1.3-2.7 V. AEC-Q101."})
    qd = pin_xy(*QP["3"], qx, y + 16.0, 270)
    qs = pin_xy(*QP["2"], qx, y + 16.0, 270)
    qg = pin_xy(*QP["1"], qx, y + 16.0, 270)
    drain.to(qd[0])
    sh.wire(qd[0], y, qd[0], qd[1])
    gnd_below(sh, qs[0], qs[1])

    # The gate run is SPLIT at the pulldown's tap, not drawn as one wire
    # with the resistor meeting its middle -- see schlib.Rail. Drawn as
    # one wire, both relay pulldowns came back unconnected.
    px = qg[0] - 10.16
    sh.wire(qg[0], qg[1], px, qg[1])
    sh.wire(px, qg[1], qg[0] - 20.32, qg[1])
    sh.junction(px, qg[1])
    sh.label(gate_net + "_G", qg[0], qg[1], rot=180)
    # The buffer sits a row below, clear of the drain rail.
    sh.wire(qg[0] - 20.32, qg[1], qg[0] - 20.32, qg[1] + 30.48)
    buffer_5v(sh, qg[0] - 20.32, qg[1] + 30.48, gate_net)
    # Gate pulldown: holds the FET off while 5V_MAIN is absent and the
    # buffer's output is undefined.
    sh.place("Device:R", "R", px, qg[1] + 16.0, "10k",
             fields={"Source": "gate pulldown -- PTD13/PTD14 are Hi-Z with "
                               "no pull at reset",
                     "Note": "10k, NOT the 470 ohm supervisor.cir sized for "
                             "the six driver gates. That figure came from "
                             "Miller coupling at Crss = 500 pF on a node "
                             "swinging to a 100 V boost rail. A relay drain "
                             "is clamped by its own flyback diode or TVS, "
                             "under 60 V. Recheck if a relay FET with large "
                             "Crss is chosen."})
    a = pin_xy(*PINS["Device:R"]["1"], px, qg[1] + 16.0, 0)
    b = pin_xy(*PINS["Device:R"]["2"], px, qg[1] + 16.0, 0)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    sh.wire(px, qg[1], t[0], t[1])
    gnd_below(sh, bo[0], bo[1])
    if clamp == "tvs":
        # TVS from the drain DOWN to ground, right of the FET, clear of
        # the buffer and its gate run.
        tx, ty = qx + 16.0, y + 16.0
        sh.place("Device:D_TVS", "D", tx, ty, "SMAJ48CA", rot=90,
                 fields={"Source": "main_relay.cir part C",
                                                  "Note": "Replaces the flyback diode to VBAT_PROT, "
                                 "which made a sneak path: coil on Term. 30, "
                                 "diode into the board, 22.8 mA through the "
                                 "coil with the relay OFF (2.7x its release "
                                 "current) and the board at 9.1 V. Bosch: "
                                 "pin 50 has no freewheeling diode; it "
                                 "belongs in the relay.",
                         "Rating": "48 V standoff clears the 40 V clamped "
                                   "dump; 53-59 V peak at turn-off against "
                                   "the FET's 100 V; 4.9 mJ per release",
                         "Rotation": "bidirectional -- orientation not "
                                     "significant"})
        ta = pin_xy(*PINS["Device:D_TVS"]["1"], tx, ty, 90)
        tb = pin_xy(*PINS["Device:D_TVS"]["2"], tx, ty, 90)
        t_top, t_bot = (ta, tb) if ta[1] < tb[1] else (tb, ta)
        drain.to(tx, tap=True)
        sh.wire(tx, y, t_top[0], t_top[1])
        gnd_below(sh, t_bot[0], t_bot[1])
    if wake_net:
        wake(sh, drain, qx + 90.0, y, wake_net, gate_net)


def wake(sh, drain, qx, y, in_net, gate_net):
    """The ignition closes the main relay in hardware (main_relay.cir A).

    A second PMV280ENEA in parallel with the MCU's, gated from pin 71
    through 10k / 22k with a 12 V zener. Ignition on: Vgs 5.5 V at 8 V
    in, the relay closes, 04/06 come up and the board boots. Ignition
    off: this FET lets go and the relay stays closed only while the MCU
    holds RLY_MAIN -- the after-run that stops the engine and saves the
    fault memory before the board drops its own supply."""
    sh.place("Device:Q_NMOS_GSD", "Q", qx, y + 16.0, "PMV280ENEA",
             rot=270, footprint="Package_TO_SOT_SMD:SOT-23",
             fields={"Source": "main_relay.cir part A",
                     "MPN": "PMV280ENEA",
                     "Note": "WAKE: in parallel with the MCU-driven FET. "
                             "The board has no supply until this closes "
                             "the relay -- Bosch wiring has no permanent "
                             "feed. Same part as the MCU's FET."})
    qd = pin_xy(*QP["3"], qx, y + 16.0, 270)
    qs = pin_xy(*QP["2"], qx, y + 16.0, 270)
    qg = pin_xy(*QP["1"], qx, y + 16.0, 270)
    drain.to(qd[0])
    sh.wire(qd[0], y, qd[0], qd[1])
    gnd_below(sh, qs[0], qs[1])

    # Gate node: a short run left of the gate, then down to the divider.
    gn = Rail(sh, qg[1])
    gn.to(qg[0])
    sh.label(gate_net + "_WAKE", qg[0], qg[1], rot=180)
    zx, rx = qg[0] - 8.0, qg[0] - 18.0
    gn.to(zx, tap=True)
    gn.to(rx)
    sh.place("Device:D_Zener", "D", zx, qg[1] + 14.0, "12V", rot=270,
             fields={"Source": "main_relay.cir Dz",
                     "Note": "Cathode to the gate: 12.0 V on pulse 2a "
                             "against the +/-20 V rating; -0.7 V reversed."})
    za = pin_xy(*PINS["Device:D_Zener"]["1"], zx, qg[1] + 14.0, 270)
    zb = pin_xy(*PINS["Device:D_Zener"]["2"], zx, qg[1] + 14.0, 270)
    zt, zbo = (za, zb) if za[1] < zb[1] else (zb, za)
    sh.wire(zx, qg[1], zt[0], zt[1])
    gnd_below(sh, zbo[0], zbo[1])
    sh.place("Device:R", "R", rx, qg[1] + 14.0, "22k",
             fields={"Source": "main_relay.cir Rg",
                     "Note": "Holds the gate off with the ignition open; "
                             "with the 10k, Vgs 5.5 V at 8 V and 9.9 V at "
                             "14.4 V, under the zener."})
    ra = pin_xy(*PINS["Device:R"]["1"], rx, qg[1] + 14.0, 0)
    rb = pin_xy(*PINS["Device:R"]["2"], rx, qg[1] + 14.0, 0)
    rt, rbo = (ra, rb) if ra[1] < rb[1] else (rb, ra)
    sh.wire(rx, qg[1], rt[0], rt[1])
    gnd_below(sh, rbo[0], rbo[1])
    # Series resistor in from the left, on the gate run's own height.
    sx = rx - 16.0
    sh.place("Device:R", "R", sx, qg[1], "10k", rot=90,
             fields={"Source": "main_relay.cir Rs",
                     "Note": "2.8 mA and 78 mW on the 40 V clamped dump; "
                             "6.1 mA for pulse 2a's 50 us."})
    sa = pin_xy(*PINS["Device:R"]["1"], sx, qg[1], 90)
    sb = pin_xy(*PINS["Device:R"]["2"], sx, qg[1], 90)
    sl, sr = (sa, sb) if sa[0] < sb[0] else (sb, sa)
    sh.wire(sr[0], qg[1], rx, qg[1])
    sh.junction(rx, qg[1])
    sh.wire(sl[0], qg[1], sl[0] - 12.0, qg[1])
    sh.hlabel(in_net, sl[0] - 12.0, qg[1], shape="input", rot=180)


def buffer_5v(sh, yx, yy, gate_net):
    """The relay FET's gate at 5 V, not 3.3 V. Every 100 V automotive
    small-signal FET looked at (PMV280ENEA, DMN10H220LQ, BSS123N) is
    specified at Vgs = 4.5 V and no lower, with a threshold up to
    2.5-2.8 V that rises further when cold -- 0.5 V of overdrive from a
    3.3 V pin is not a guarantee. An AHCT buffer on 5V_MAIN reads the
    GPIO on TTL thresholds (VIH 2 V) and drives 4.4 V minimum. Its
    output Y lands on (yx, yy)."""
    lib = "ecu25kva:AHCT1G125"
    ux, uy = yx - 15.24, yy + 1.27
    sh.place(lib, "U", ux, uy, "SN74AHCT1G125-Q1",
             footprint="Package_TO_SOT_SMD:SOT-23-5",
             fields={"Source": "TI SN74AHCT1G125-Q1 datasheet, sec.5.3 / "
                               "5.5 -- VIH 2 V, VOH 4.4 V at VCC 4.5 V",
                     "MPN": "CAHCT1G125QDBVRQ1"})
    a = ic_pin("AHCT1G125", 2, ux, uy)
    oe = ic_pin("AHCT1G125", 1, ux, uy)
    vcc = ic_pin("AHCT1G125", 5, ux, uy)
    gnd = ic_pin("AHCT1G125", 3, ux, uy)
    # OE is active low: tied to ground, the buffer always drives.
    sh.wire(oe[0], oe[1], oe[0] - 2.54, oe[1])
    gnd_below(sh, oe[0] - 2.54, oe[1])
    gnd_below(sh, gnd[0], gnd[1])
    # Supply rail high enough that the capacitor and its ground clear
    # the body; the capacitor hangs to the LEFT, above the A input.
    ry = vcc[1] - 17.78
    sh.wire(vcc[0], vcc[1], vcc[0], ry)
    dec = Rail(sh, ry)
    dec.to(vcc[0])
    vshunt(sh, "Device:C", "C", vcc[0] - 12.7, ry + 3.81, "100nF",
           {"Note": "At the buffer's own VCC pin"}, dec)
    dec.to(vcc[0] - 25.4)
    sh.label("5V_MAIN", vcc[0] - 25.4, ry, rot=180)
    # Input: the GPIO, with a pulldown -- PTD13/PTD14 are Hi-Z with no
    # pull at reset, and a floating CMOS input is neither state.
    inp = Rail(sh, a[1])
    inp.to(a[0])
    inp.to(a[0] - 10.16, tap=True)
    inp.to(a[0] - 20.32)
    sh.hlabel(gate_net, a[0] - 20.32, a[1], shape="input", rot=180)
    sh.place("Device:R", "R", a[0] - 10.16, a[1] + 16.0, "100k",
             fields={"Source": "input pulldown -- relay OFF from reset "
                               "until firmware drives the pin"})
    r1 = pin_xy(*PINS["Device:R"]["1"], a[0] - 10.16, a[1] + 16.0, 0)
    r2_ = pin_xy(*PINS["Device:R"]["2"], a[0] - 10.16, a[1] + 16.0, 0)
    t, bo = (r1, r2_) if r1[1] < r2_[1] else (r2_, r1)
    sh.wire(a[0] - 10.16, a[1], t[0], t[1])
    gnd_below(sh, bo[0], bo[1])


def notes(sh):
    sh.text(
        "BOSCH WIRING (terminal diagram 0 462 YU4 15D, decisions log sec.18). "
        "The ECU has NO permanent battery feed: pin 71 (ignition) wakes it,\n"
        "pin 50 closes the main relay, and the relay's contact feeds pins "
        "04/06, the board's only supply. Q-WAKE closes the relay in hardware "
        "from pin 71,\n"
        "so the board can come up at all; the MCU then holds RLY_MAIN through "
        "the after-run (stop, save fault memory) and releases it last.\n"
        "\n"
        "PIN 50 HAS A TVS, NOT A FLYBACK DIODE. Its coil sits on Term. 30, "
        "always live. A diode from the drain to VBAT_PROT powered the board "
        "THROUGH THE COIL\n"
        "with the relay open: 22.8 mA in the coil (2.7x its release current) "
        "and the board at 9.1 V (main_relay.cir part B). The relay could "
        "never drop out.\n"
        "Bosch marks pin 50 'not equipped with freewheeling diode'. The "
        "buzzer relay keeps its diode: its coil is on the main-relay line "
        "and dies with VBAT_PROT.\n"
        "\n"
        "NO TRIP LOOP. It had no Bosch pin. The overspeed trip module "
        "(external) opens the main relay's coil feed, which drops the "
        "board with everything else.\n"
        "Pin 21 is the WATER-IN-FUEL input, active high from the main-relay "
        "line through the sensor's switch, open (reads inactive) with no "
        "water.",
        40.0, 340.0, size=1.6)
    sh.text(
        "THE EIGHT SWITCH INPUTS ARE NPN BUFFERS, NOT CLAMPS (22 Sep 2026, "
        "LOWV-CLAMP). The 47k/68k/3.0 V-zener front end needed a clamp "
        "that conducts CONTINUOUSLY over 6-40 V, and none\n"
        "fits the pad's ratings: a 3.0 V zener leaks at uA (soft knee), a "
        "rail clamp parks the pad at 3.9 V, a shunt reference draws 35 uA "
        "of bias the cranking-dip input cannot supply.\n"
        "Here the pad sees only its own 10k pull-up or a saturated "
        "PMBT3904-Q. Checked at the WORST corner, not typical: hFE 30 at "
        "-40 C still pulls the pad to 0.03 V from a 6 V input;\n"
        "a typical part at 125 C does not turn on below 1.3 V. 10k input "
        "resistors give 1.1 mA of contact wetting current at 12 V.\n"
        "\n"
        "LOGIC IS INVERTED -- pad LOW = input active (contact-to-ground "
        "channels: contact OPEN). FAILURE MODES, for firmware plausibility "
        "checks: transistor open or pull-up shorted\n"
        "-> pad stuck HIGH (reads inactive); C-E short -> pad stuck LOW "
        "(reads active). One polarity cannot make every channel fail safe; "
        "the safe state per channel belongs in the\n"
        "firmware spec. The trip loop keeps its clamped ANALOG front end: "
        "its healthy band is the clamp level (LOWV-CLAMP residual).",
        40.0, 392.0, size=1.6)


def build():
    schlib.verify_pins()
    sh = Sheet("Discrete I/O: switch inputs, relay drivers, ignition wake",
               paper="A1",
               comments=[
                   "Generated by hw/gen_sheet_discrete_io.py -- do not hand-edit until it is retired",
                   "Inputs: NPN buffers (discrete_input.cir), inverted. Outputs: relay_driver.cir, main_relay.cir",
                   "Bosch pinout (refs/bosch-pinout-md1cs162.md): pin 71 wakes, pin 50 holds, pin 21 is water-in-fuel",
                   "Relay FETs are 100 V class -- VBAT_PROT reaches 73.3 V on pulse 2a",
               ],
               ref_base=schlib.REF_BASE["discrete_io"])
    rows = [
        (40.0, 60.0, "IN_AUDIO_ABORT_H", "IN_AUDIO_ABORT", None,
         "ECU pin 20 -- audio abort, active high -> PTD11"),
        (40.0, 120.0, "IN_OVERRIDE_SS_H", "IN_OVERRIDE_SS", None,
         "ECU pin 24 -- override start/stop, active high -> PTD12"),
        (40.0, 180.0, "IN_IGNITION_H", "IN_IGNITION", None,
         "ECU pin 71 -- ignition, active high -> PTD16"),
        (320.0, 60.0, "SW_COOLANT_C", "SW_COOLANT", "10k",
         "ECU pin 43 -- coolant switch, contact to ground -> PTD5"),
        (320.0, 120.0, "SW_DROOP_C", "SW_DROOP", "10k",
         "ECU pin 23 -- droop switch, contact to ground -> PTD7"),
        # Bosch pins, 8 Nov 2026 (decisions log sec.18).
        (320.0, 180.0, "IN_WIF_H", "IN_WIF", None,
         "ECU pin 21 -- water in fuel, active high -> PTD6"),
        (600.0, 60.0, "SW_DIAG_C", "SW_DIAG", "10k",
         "ECU pin 14 -- diagnosis request, contact to ground -> PTD8"),
        (600.0, 120.0, "SW_STOP_C", "SW_STOP", "10k",
         "ECU pin 25 -- stop / emergency switch, contact to ground -> PTD9"),
    ]
    for x0, y, innet, outnet, pu, label in rows:
        buffered_input(sh, x0, y, innet, outnet, label, pullup=pu)
    # The sheet's one HIERARCHICAL 3V3_MCU, for the pad pull-ups.
    sh.wire(460.0, 226.0, 466.0, 226.0)
    sh.hlabel("3V3_MCU", 460.0, 226.0, shape="input", rot=180)
    sh.label("3V3_MCU", 466.0, 226.0)

    relay(sh, 60.0, 255.0, "RLY_MAIN", "RLY_MAIN_OUT",
          "ECU pin 50 -- main relay, low side <- PTD13, woken by pin 71",
          clamp="tvs", wake_net="IN_IGNITION_H")
    relay(sh, 260.0, 255.0, "RLY_BUZZER", "RLY_BUZZER_OUT",
          "ECU pin 69 -- buzzer relay, low side <- PTD14")
    # The sheet's one HIERARCHICAL 5V_MAIN: both relay buffers carry the
    # name as a local label, which alone would make it a sheet-local net.
    sh.wire(460.0, 236.0, 466.0, 236.0)
    sh.hlabel("5V_MAIN", 460.0, 236.0, shape="input", rot=180)
    sh.label("5V_MAIN", 466.0, 236.0)
    notes(sh)
    return sh


if __name__ == "__main__":
    print(build().write(OUT, force="--force" in sys.argv))
