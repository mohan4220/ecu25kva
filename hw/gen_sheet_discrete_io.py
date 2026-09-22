#!/usr/bin/env python3
"""discrete_io sheet: switch inputs, the supervised trip loop, relay drivers.

Six input channels and two outputs. Three blocks back it:
discrete_input.cir, trip_module_sense.cir, relay_driver.cir.

ONE PIN ASSIGNMENT IS CORRECTED HERE, and it is not a preference.
docs/pinmap.md assigns the trip-module sense to PTD6 as a "GPIO input".
trip_module_sense.cir designs a THREE-STATE supervised loop and checks
the three bands with real margins:

    healthy (contact closed)   2.863 - 2.954 V
    tripped (Rt in circuit)    0.310 - 2.068 V
    wire fault                 0.000 V

A GPIO reads two states. It can separate healthy from not-healthy and
nothing else -- which discards exactly the distinction the bleed resistor
exists to create, and a supervised loop that cannot report a cut wire is
an unsupervised loop with extra parts. The channel moves to PTB0
(ADC0_SE4), which is free, bonded out on the 144-LQFP, and Hi-Z with no
pull at reset. PTD6 returns to the spare pool.
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


def clamped_input(sh, x0, y, in_net, out_net, label, pullup=None):
    """discrete_input.cir's front-end: 47k series, 68k to ground, 220 nF,
    and a 3.0 V zener. The zener does the clamping and the 47k sets what
    it has to sink -- (40 - 3) / 47k = 787 uA at the top of the input
    range, which is why the series element is not a token value."""
    sh.hlabel(in_net, x0, y, shape="input")
    chain = Rail(sh, y)
    chain.to(x0)

    # Optional pull-up, for the two channels whose switch is a contact to
    # ground rather than a feed. Placed BEFORE the 47k so a battery short
    # on the harness still meets the clamp chain rather than the pull-up.
    if pullup:
        sh.place("Device:R", "R", x0 + 16.0, y - 18.0, pullup,
                 fields={"Source": "pull-up for a switch-to-ground contact "
                                   "(pinmap sec.1.4)",
                         "Note": "Open contact leaves the divider at "
                                 "5 * 115/125 * 68/115 = 2.72 V, under the "
                                 "3.0 V zener knee, so it reads high "
                                 "without the clamp conducting. Closed "
                                 "contact pulls it to 0 V."})
        a = pin_xy(*PINS["Device:R"]["1"], x0 + 16.0, y - 18.0, 0)
        b = pin_xy(*PINS["Device:R"]["2"], x0 + 16.0, y - 18.0, 0)
        t, bo = (a, b) if a[1] < b[1] else (b, a)
        rx, ry = chain.to(x0 + 16.0, tap=True)
        sh.wire(rx, ry, bo[0], bo[1])
        sh.wire(t[0], t[1], t[0], t[1] - 6.35)
        sh.hlabel("5V_MAIN", t[0], t[1] - 6.35, shape="input",
                  rot=90)

    sx = x0 + 34.0
    sh.place("Device:R", "R", sx, y, "47k", rot=90,
             fields={"Source": "discrete_input.cir R5",
                     "Note": "Sets the zener's worst-case sink current: "
                             "(40 - 3) / 47k = 787 uA at the top of the "
                             "6-40 V input range"})
    ra = pin_xy(*PINS["Device:R"]["1"], sx, y, 90)
    rb = pin_xy(*PINS["Device:R"]["2"], sx, y, 90)
    r_in, r_out = (ra, rb) if ra[0] < rb[0] else (rb, ra)
    rx, ry = chain.to(r_in[0])
    node = Rail(sh, y)
    node.to(r_out[0])

    vshunt(sh, "Device:R", "R", x0 + 54.0, y + 18.0, "68k",
           {"Source": "discrete_input.cir R6",
            "Note": "With the 47k above, a 115k divider -- but the zener "
                    "is what sets the clamped level, not this ratio"}, node)
    vshunt(sh, "Device:C", "C", x0 + 70.0, y + 18.0, "220nF",
           {"Source": "discrete_input.cir C1 -- debounce and EMI",
            "Note": "68k * 220 nF = 15 ms, long against contact bounce and "
                    "short against anything the engine does"}, node)
    # Zener: cathode to the signal, anode to ground.
    vshunt(sh, "Device:D_Zener", "D", x0 + 86.0, y + 18.0, "3.0V",
           {"Source": "discrete_input.cir D1",
            "Note": "Clamps the MCU pin at 3.0 V across the whole 6-40 V "
                    "input range. Cathode to the signal."}, node, rot=270)

    node.to(x0 + 108.0)
    sh.hlabel(out_net, x0 + 108.0, y, shape="output")
    sh.text(label, x0, y - 9.0, size=1.6)


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


def relay(sh, x0, y, gate_net, out_net, label):
    """relay_driver.cir: low-side switch, coil to battery, flyback diode."""
    sh.text(label, x0, y - 26.0, size=1.6)
    # The coil itself is off-sheet -- it lives in the harness. What this
    # board carries is the switch, the flyback path and the gate network.
    dx = x0 + 30.0
    sh.place("Device:D", "D", dx, y - 18.0, "100V 1A fast", rot=270,
             fields={"Source": "relay_driver.cir D1",
                     "Note": "Without it, interrupting 84 mA in a 1.2 H "
                             "coil has nowhere to go -- relay_driver.cir's "
                             "second branch is that case. Cathode to "
                             "battery.",
                     "Vr": "100 V class, per transient_clamp's rail rating"})
    da = pin_xy(*PINS["Device:D"]["1"], dx, y - 18.0, 270)
    db = pin_xy(*PINS["Device:D"]["2"], dx, y - 18.0, 270)
    d_k, d_a = (da, db) if da[1] < db[1] else (db, da)
    # Straight in at the cathode's own height -- drawn to the diode's
    # centre line, this wire ran diagonally to a pin 3.81 mm above it.
    sh.wire(x0, d_k[1], d_k[0], d_k[1])
    sh.hlabel("VBAT_PROT", x0, d_k[1], shape="input")

    drain = Rail(sh, y)
    drain.to(d_a[0])
    sh.wire(d_a[0], d_a[1], d_a[0], y)
    drain.to(x0 + 14.0, tap=True)
    sh.hlabel(out_net, x0 + 14.0, y, shape="output")
    drain.x = None
    drain.to(d_a[0])

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
                             "is clamped by its own flyback diode at "
                             "Vbat + Vf. Recheck if a relay FET with large "
                             "Crss is chosen."})
    a = pin_xy(*PINS["Device:R"]["1"], px, qg[1] + 16.0, 0)
    b = pin_xy(*PINS["Device:R"]["2"], px, qg[1] + 16.0, 0)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    sh.wire(px, qg[1], t[0], t[1])
    gnd_below(sh, bo[0], bo[1])


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
        "TRIP SENSE MOVES FROM PTD6 TO PTB0 (ADC0_SE4). docs/pinmap.md "
        "assigns it as a GPIO input; trip_module_sense.cir designs a "
        "THREE-STATE supervised loop and\n"
        "checks the three bands with real margins -- healthy 2.863-2.954 V, "
        "tripped 0.310-2.068 V, wire fault 0.000 V. A GPIO reads two "
        "states. It separates healthy\n"
        "from not-healthy and nothing else, which discards exactly the "
        "distinction the bleed resistor exists to create: a supervised "
        "loop that cannot report a cut\n"
        "wire is an unsupervised loop with extra parts. PTB0 is free, "
        "bonded out on the 144-LQFP, and Hi-Z with no pull at reset. "
        "PTD6 returns to the spare pool.\n"
        "\n"
        "The 1.2 Mohm bleed resistor that makes the tripped band is "
        "INSIDE the trip module, across its contact -- it is not on this "
        "board and is not drawn here. It is\n"
        "also INFERRED rather than measured (trip_module_sense.cir says "
        "so), so the band edges above move if the real part differs.",
        40.0, 340.0, size=1.6)
    sh.text(
        "THE FIVE SWITCH INPUTS ARE NPN BUFFERS, NOT CLAMPS (22 Sep 2026, "
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
    sh = Sheet("Discrete I/O: switch inputs, trip loop, relay drivers",
               paper="A2",
               comments=[
                   "Generated by hw/gen_sheet_discrete_io.py -- do not hand-edit until it is retired",
                   "Inputs: NPN buffers (discrete_input.cir), inverted. Trip loop: trip_module_sense.cir. Outputs: relay_driver.cir",
                   "Trip sense moved PTD6 -> PTB0: a GPIO cannot read a three-state loop",
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
        (320.0, 180.0, "TRIP_LOOP", "TRIP_SENSE", None,
         "NEW pin -- supervised trip loop -> PTB0 (ADC0_SE4), not PTD6"),
    ]
    for x0, y, innet, outnet, pu, label in rows:
        if innet == "TRIP_LOOP":
            # The trip loop is ANALOG (three bands on an ADC) and its
            # healthy band IS the clamp level -- it keeps the clamped
            # front end. LOWV-CLAMP residual; it also has no pin yet.
            clamped_input(sh, x0, y, innet, outnet, label, pullup=pu)
        else:
            buffered_input(sh, x0, y, innet, outnet, label, pullup=pu)
    # The sheet's one HIERARCHICAL 3V3_MCU, for the pad pull-ups.
    sh.wire(460.0, 226.0, 466.0, 226.0)
    sh.hlabel("3V3_MCU", 460.0, 226.0, shape="input", rot=180)
    sh.label("3V3_MCU", 466.0, 226.0)

    relay(sh, 60.0, 255.0, "RLY_MAIN", "RLY_MAIN_OUT",
          "ECU pin 50 -- main relay, low side <- PTD13")
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
