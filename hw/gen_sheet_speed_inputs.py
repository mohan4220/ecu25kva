#!/usr/bin/env python3
"""speed_inputs sheet: the crank VR conditioner and the cam front-end.

Two blocks back this sheet: vr_conditioner.cir and cam_frontend.cir.
They are the two engine-position inputs, and they are drawn together
because the firmware uses them together -- crank for angle and speed, cam
for cylinder identification -- but their front ends have nothing in
common, because their sensors have nothing in common.

  CRANK   a variable-reluctance coil beside a 60-tooth wheel. It makes
          its own voltage by induction, so amplitude tracks speed: about
          20 V peak at 1500 rpm and about 2 V peak while cranking at
          150 rpm. A 10:1 swing, with the SMALL end being the one you
          need to start the engine. vr_conditioner.cir is the argument
          for a zero-cross comparator over a fixed threshold: the fixed
          one, sized sensibly for the running engine at 5 V, produces
          edges at 1500 rpm and NONE at cranking speed -- an ECU that
          works perfectly on the bench and will not start the machine.

  CAM     a 3-pin digital Hall sensor with an open-collector output,
          excited from 5V_SENSOR. Nothing to condition; the problem is
          the opposite one, that its output swing is 5 V and PTB3 is a
          3.3 V pin.

DERIVED ON THIS SHEET, not carried over from the block: the hysteresis
network's component values, the clamp diode class, and the bias
generator. vr_conditioner.cir models the comparator as a hysteretic
switch with Vh = 0.2 V -- an ideal element with no input current, no
supply rail and no clamp. Turning that into parts is what the sheet
does, and one of the three answers is not the obvious one. See CLAMP
LEAKAGE below.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import schlib
from schlib import Sheet, Rail, pin_xy, PINS

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "speed_inputs.kicad_sch")
ICPINS = json.load(open(os.path.join(HW, "lib", "ic_pins.json")))
COMP = "ecu25kva:COMPARATOR_GENERIC"
GND_DROP = 7.62


def ic_pin(part, num, x, y):
    dx, dy = ICPINS[part][str(num)]
    return pin_xy(dx, dy, x, y, 0)


def gnd_below(sh, x, y):
    sh.wire(x, y, x, y + GND_DROP)
    sh.gnd(x, y + GND_DROP)


def vshunt(sh, libid, prefix, x, y, value, fields, rail, rot=0):
    """A two-terminal part hanging off a horizontal rail down to ground."""
    sh.place(libid, prefix, x, y, value, rot=rot, fields=fields)
    a = pin_xy(*PINS[libid]["1"], x, y, rot)
    b = pin_xy(*PINS[libid]["2"], x, y, rot)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    rx, ry = rail.to(t[0], tap=True)
    sh.wire(rx, ry, t[0], t[1])
    gnd_below(sh, bo[0], bo[1])


def series_r(sh, x, y, value, fields, rail_in):
    """A horizontal resistor in a rail. Returns the rail that leaves it."""
    sh.place("Device:R", "R", x, y, value, rot=90, fields=fields)
    a = pin_xy(*PINS["Device:R"]["1"], x, y, 90)
    b = pin_xy(*PINS["Device:R"]["2"], x, y, 90)
    left, right = (a, b) if a[0] < b[0] else (b, a)
    rail_in.to(left[0])
    out = Rail(sh, y)
    out.to(right[0])
    return out


def vstub(sh, x, y, dy, text, rail=None):
    """A short vertical wire off a rail (or off a point) ending in a local
    label. Labels are placed exactly on a wire endpoint -- a label offset
    from its wire for looks detaches silently and the netlist never says
    so."""
    if rail is not None:
        x, y = rail.to(x, tap=True)
    sh.wire(x, y, x, y + dy)
    sh.label(text, x, y + dy)
    return (x, y + dy)


def vrail_r(sh, x, y_node, y_part, value, fields, rail, label, y_label):
    """A vertical resistor from a rail up or down to a labelled net.

    Used for the two bias resistors, which cannot both reach one drawn
    VR_BIAS wire: the HI leg sits above the LO leg, so a single wire
    between them would have to cross the other leg's rail. Two stubs
    carrying the SAME label are one net and cross nothing.
    """
    sh.place("Device:R", "R", x, y_part, value, fields=fields)
    a = pin_xy(*PINS["Device:R"]["1"], x, y_part, 0)
    b = pin_xy(*PINS["Device:R"]["2"], x, y_part, 0)
    top, bot = (a, b) if a[1] < b[1] else (b, a)
    near, far = (bot, top) if y_part > y_node else (top, bot)
    rx, ry = rail.to(x, tap=True)
    sh.wire(rx, ry, near[0], near[1])
    sh.wire(far[0], far[1], far[0], y_label)
    sh.label(label, far[0], y_label)


# ---------------------------------------------------------------------
# Crank: variable reluctance, ECU pins 52 (High), 74 (Low), 30 (shield)
# ---------------------------------------------------------------------
# THE HYSTERESIS NETWORK, derived here rather than asserted.
#
# vr_conditioner.cir's comparator is `SW(Vt=0 Vh=0.2)`. Vh is a model
# parameter; in parts it is a positive-feedback resistor from the output
# back to IN+, and the window it makes is
#
#     Vwindow = Vswing * Rth / (Rth + Rfb)
#
# where Rth is what the IN+ node looks back into. With the 4.7 k series
# resistor and the 100 k bias resistor (through the bias generator's own
# 1.1 k), Rth = 4.7k || 101.1k = 4.489 k. Against Rfb = 33 k on a 3.3 V
# push-pull output:
#
#     Vwindow = 3.3 * 4489 / (4489 + 33000) = 0.395 V,  i.e. +/-198 mV
#
# which is the +/-200 mV the block modelled, to three digits, from
# E24 values. That matters because the block's own TOLERANCE section
# found the failure point sits almost exactly AT Vh: a cranking signal
# that never leaves the hysteresis window cannot flip the comparator at
# all, whatever its amplitude margin. The measured floor was 0.21 V of
# signal against a 2 V nominal estimate -- roughly a decade of headroom,
# and this network keeps it.
#
# The sensor coil's own DC resistance adds to the 4.7 k and WIDENS the
# window: at a 1 k coil, Rth = 5.7k || 101.1k = 5.395 k and the window
# becomes +/-232 mV. That moves the amplitude floor from 0.21 V to about
# 0.25 V, still an order of magnitude below the 2 V estimate.
def crank(sh):
    y_hi, y_lo = 70.0, 115.0
    ux, uy = 250.0, 71.27
    sh.text("CRANK -- variable reluctance, ECU pins 52 / 74, shield 30 "
            "-> zero-cross comparator -> PTB2 (FTM1_CH0)", 40.0, 34.0,
            size=1.8)

    sh.place(COMP, "U", ux, uy, "COMPARATOR_GENERIC",
             fields={"Source": "vr_conditioner.cir -- ZCSW",
                     "Requirement": "single 3.3 V supply, PUSH-PULL "
                                    "rail-to-rail output, mid-rail input "
                                    "common-mode, prop delay <=1 us",
                     "Note": "Part NOT chosen -- placeholder pin numbers, "
                             "no footprint. The output swing sets the "
                             "hysteresis window, so an open-drain part "
                             "would make the window depend on its pull-up "
                             "and its VOL."})
    inp = ic_pin("COMPARATOR_GENERIC", 3, ux, uy)
    inn = ic_pin("COMPARATOR_GENERIC", 2, ux, uy)
    out = ic_pin("COMPARATOR_GENERIC", 1, ux, uy)
    vp = ic_pin("COMPARATOR_GENERIC", 5, ux, uy)
    vn = ic_pin("COMPARATOR_GENERIC", 4, ux, uy)
    sh.wire(vp[0], vp[1], vp[0], vp[1] - 6.0)
    sh.label("3V3_MCU", vp[0], vp[1] - 6.0)
    gnd_below(sh, vn[0], vn[1])

    # ---- the pair comes in, is clamped differentially, then per leg ----
    sh.hlabel("CRANK_HI_52", 40.0, y_hi, shape="input")
    sh.hlabel("CRANK_LO_74", 40.0, y_lo, shape="input")
    hi, lo = Rail(sh, y_hi), Rail(sh, y_lo)
    hi.to(40.0)
    lo.to(40.0)

    tx, ty = 62.0, (y_hi + y_lo) / 2.0
    sh.place("Device:D_TVS", "D", tx, ty, "SMAJ48CA", rot=90,
             fields={"Tag": "VR-CLAMP",
                     "Note": "Bidirectional, across the pair. Standoff has "
                             "to clear the signal itself: VR amplitude is "
                             "proportional to speed, about 20 V peak at "
                             "1500 rpm, so a part that clamps at 24 V "
                             "would clip a runaway engine's own crank "
                             "signal -- the one time the ECU most needs to "
                             "keep counting teeth. 48 V clears 3600 rpm."})
    ta = pin_xy(*PINS["Device:D_TVS"]["1"], tx, ty, 90)
    tb = pin_xy(*PINS["Device:D_TVS"]["2"], tx, ty, 90)
    t_top, t_bot = (ta, tb) if ta[1] < tb[1] else (tb, ta)
    hx, hy = hi.to(tx, tap=True)
    sh.wire(hx, hy, t_top[0], t_top[1])
    lx, ly = lo.to(tx, tap=True)
    sh.wire(lx, ly, t_bot[0], t_bot[1])

    legs = []
    for rail, y, name in ((hi, y_hi, "HI"), (lo, y_lo, "LO")):
        node = series_r(
            sh, 85.0, y, "4.7k",
            {"Source": "vr_conditioner.cir Rsr/Rsc (1k) -- raised to 4.7k",
             "Note": "MATCHED to the other leg. Three jobs at once: it "
                     "limits clamp-diode current on a 20 V signal "
                     "(3.4 mA) and on a 40 V overspeed one (7.7 mA), it "
                     "is the R of the input filter, and it is most of "
                     "the Rth that sets the hysteresis window. The block "
                     "used 1k because none of those three exist in an "
                     "ideal-switch model."}, rail)
        vshunt(sh, "Device:C", "C", 110.0, y + 18.0, "1nF",
               {"Note": "With Rth = 4.489k, fc = 35.5 kHz -- 23.6x above "
                        "the 1500 Hz tooth rate at rated speed and 237x "
                        "above the 150 Hz cranking rate. MATCHED to the "
                        "other leg: a mismatch here converts common-mode "
                        "harness noise into differential noise at exactly "
                        "the frequencies the filter exists to remove."},
               node)
        # Low-leakage clamp to the rails. See CLAMP LEAKAGE in notes().
        sh.place("Device:D", "D", 155.0, y - 14.0, "BAV199 (upper half)",
                 rot=270,
                 fields={"Tag": "VR-CLAMP",
                         "Note": "Anode to the signal, cathode to 3V3_MCU. "
                                 "LOW LEAKAGE is the binding spec, not "
                                 "forward drop -- see the sheet note."})
        ua = pin_xy(*PINS["Device:D"]["1"], 155.0, y - 14.0, 270)  # K, top
        ub = pin_xy(*PINS["Device:D"]["2"], 155.0, y - 14.0, 270)  # A, bottom
        sh.place("Device:D", "D", 175.0, y + 14.0, "BAV199 (lower half)",
                 rot=270,
                 fields={"Tag": "VR-CLAMP",
                         "Note": "Anode to ground, cathode to the signal."})
        la = pin_xy(*PINS["Device:D"]["1"], 175.0, y + 14.0, 270)  # K, top
        lb = pin_xy(*PINS["Device:D"]["2"], 175.0, y + 14.0, 270)  # A, bottom
        nx, ny = node.to(155.0, tap=True)
        sh.wire(nx, ny, ub[0], ub[1])
        sh.wire(ua[0], ua[1], ua[0], ua[1] - 6.0)
        sh.label("3V3_MCU", ua[0], ua[1] - 6.0)
        nx, ny = node.to(175.0, tap=True)
        sh.wire(nx, ny, la[0], la[1])
        gnd_below(sh, lb[0], lb[1])
        legs.append(node)

    hi_node, lo_node = legs

    # Bias. Both legs are pulled to VR_BIAS through 100k, which is what
    # makes a FLOATING coil sit at mid-rail instead of needing a
    # comparator whose common-mode range reaches below ground.
    vrail_r(sh, 130.0, y_hi, 56.0, "100k",
            {"Note": "MATCHED to the LO leg's 100k. With the sensor "
                     "disconnected both legs sit at VR_BIAS, the two "
                     "inputs are equal, and the comparator stays latched "
                     "where the hysteresis left it -- no edges at all, "
                     "which is the correct shape for a lost-sensor "
                     "fault: the MCU sees loss of speed rather than a "
                     "plausible wrong speed."},
            hi_node, "VR_BIAS", 46.0)
    vrail_r(sh, 130.0, y_lo, 129.0, "100k",
            {"Note": "MATCHED to the HI leg's 100k."},
            lo_node, "VR_BIAS", 139.0)

    # Into the comparator. HI goes straight in; LO jogs up to IN-, which
    # sits 2.54 mm below IN+.
    hi_node.to(228.0, tap=True)
    hi_node.to(inp[0])
    lo_node.to(224.76)
    sh.wire(224.76, y_lo, 224.76, inn[1])
    sh.wire(224.76, inn[1], inn[0], inn[1])

    # Positive feedback: this resistor IS the block's Vh parameter.
    fy = 48.0
    sh.place("Device:R", "R", ux, fy, "33k", rot=90,
             fields={"Source": "vr_conditioner.cir -- Vh=0.2 in parts",
                     "Note": "3.3 V * 4489 / (4489 + 33000) = 0.395 V, "
                             "i.e. +/-198 mV, against the +/-200 mV the "
                             "block modelled. Positive feedback to IN+, "
                             "not IN- -- to IN- it is negative feedback "
                             "and the comparator oscillates at every "
                             "crossing instead of snapping through it."})
    fa = pin_xy(*PINS["Device:R"]["1"], ux, fy, 90)
    fb = pin_xy(*PINS["Device:R"]["2"], ux, fy, 90)
    f_l, f_r = (fa, fb) if fa[0] < fb[0] else (fb, fa)
    sh.wire(228.0, y_hi, 228.0, fy)
    sh.wire(228.0, fy, f_l[0], f_l[1])
    sh.wire(f_r[0], f_r[1], 272.0, fy)
    sh.wire(272.0, fy, 272.0, out[1])

    oute = Rail(sh, out[1])
    oute.to(out[0])
    oute.to(272.0, tap=True)
    oute.to(310.0)
    sh.hlabel("CRANK_EDGE", 310.0, out[1], shape="output")

    # Comparator decoupling.
    dec = Rail(sh, 100.0)
    dec.to(300.0)
    sh.wire(300.0, 100.0, 300.0, 94.0)
    # The sheet's one HIERARCHICAL 3V3_MCU. The comparator's supply, both
    # upper clamp diodes and the bias divider all carry the name as local
    # labels, which makes them one net WITHIN this sheet and nothing
    # beyond it -- /speed_inputs/3V3_MCU, five pins and no regulator.
    sh.hlabel("3V3_MCU", 300.0, 94.0, shape="input", rot=90)
    vshunt(sh, "Device:C", "C", 300.0, 110.0, "100nF",
           {"Note": "At the comparator's own supply pin. A comparator "
                    "snapping a 3.3 V output through 200 mV of hysteresis "
                    "is a current step on the rail, and that step arriving "
                    "back at IN+ through the supply is how a clean "
                    "crossing turns into a burst of them."}, dec)


def bias_generator(sh):
    """VR_BIAS: mid-rail, deliberately low impedance."""
    x = 60.0
    sh.text("VR_BIAS -- mid-rail reference for the floating VR coil",
            40.0, 165.0, size=1.6)
    sh.place("Device:R", "R", x, 181.0, "2.2k",
             fields={"Note": "2.2k/2.2k, not 10k/10k. The feedback "
                             "resistor's current (about 44 uA) returns "
                             "into this node, and 10k/10k's 5k source "
                             "impedance would move VR_BIAS 220 mV when "
                             "the output switches -- comparable to the "
                             "whole hysteresis window. It is a "
                             "COMMON-MODE shift, so it cancels in the "
                             "comparison, but it is not worth relying on "
                             "cancellation for 0.75 mA of quiescent "
                             "current."})
    a = pin_xy(*PINS["Device:R"]["1"], x, 181.0, 0)
    b = pin_xy(*PINS["Device:R"]["2"], x, 181.0, 0)
    r1t, r1b = (a, b) if a[1] < b[1] else (b, a)
    sh.wire(x, 171.0, r1t[0], r1t[1])
    sh.label("3V3_MCU", x, 171.0)

    node_y = 193.0
    sh.wire(r1b[0], r1b[1], x, node_y)
    sh.place("Device:R", "R", x, 203.0, "2.2k",
             fields={"Note": "MATCHED to the upper 2.2k -- VR_BIAS only "
                             "has to be stable and shared, not accurate. "
                             "Both comparator inputs ride on it, so an "
                             "error in it is common-mode."})
    a = pin_xy(*PINS["Device:R"]["1"], x, 203.0, 0)
    b = pin_xy(*PINS["Device:R"]["2"], x, 203.0, 0)
    r2t, r2b = (a, b) if a[1] < b[1] else (b, a)
    sh.wire(x, node_y, r2t[0], r2t[1])
    sh.junction(x, node_y)
    gnd_below(sh, r2b[0], r2b[1])

    rail = Rail(sh, node_y)
    rail.to(x)
    vshunt(sh, "Device:C", "C", 85.0, node_y + 16.0, "1uF",
           {"Note": "Holds VR_BIAS through the output's switching edge. "
                    "With the 1.1k source impedance the node's own corner "
                    "is 145 Hz, far below the 1500 Hz tooth rate, so the "
                    "reference does not follow the signal."}, rail)
    rail.to(110.0)
    sh.label("VR_BIAS", 110.0, node_y)


def shield(sh):
    sh.hlabel("SHIELD_30", 330.0, 175.0, shape="input")
    sh.wire(330.0, 175.0, 345.0, 175.0)
    gnd_below(sh, 345.0, 175.0)
    # One text element, not two: a text block renders VERTICALLY CENTRED
    # on its anchor, so two separate blocks four millimetres apart put
    # the second line above the first.
    sh.text("ECU pin 30 -- crank sensor shield, terminated at THIS end "
            "only. Grounding both ends makes the shield a second "
            "conductor\n"
            "between two grounds that differ by the injector return "
            "current, and that current then flows down the shield "
            "around the\n"
            "pair it is there to protect.", 330.0, 165.0, size=1.6)


# ---------------------------------------------------------------------
# Cam: digital Hall, ECU pins 45 (5 V) / 46 (signal) / 44 (ground)
# ---------------------------------------------------------------------
# Drawn exactly as cam_frontend.cir validates it, including the part that
# looks like an omission: there is no series resistor between the divider
# node and PTB3. The node IS the harness line, and the 10k pull-up is
# what limits fault current into it -- network C of that block runs a
# 40 V short on the signal line and measures 3.669 mA clamped at 3.308 V.
def cam(sh):
    y = 250.0
    sh.text("CAM -- digital Hall, ECU pins 45 / 46 / 44 -> PTB3 "
            "(FTM1_CH1).  CORRECTS the front-end spec sec.4 specifies "
            "literally", 40.0, 232.0, size=1.8)
    sh.hlabel("EXC_CAM_45", 40.0, y, shape="input")
    exc = Rail(sh, y)
    exc.to(40.0)
    node = series_r(
        sh, 70.0, y, "10k",
        {"Source": "cam_frontend.cir R1",
         "Note": "Two parts at once: the open-collector sensor's required "
                 "pull-up AND the top half of the divider into the 3.3 V "
                 "domain. Fed from the same PTC-protected group C node "
                 "that excites the sensor, so a short takes the pull-up "
                 "and the excitation down together rather than leaving a "
                 "pull-up energising a dead sensor."}, exc)
    node.to(95.0)
    sh.hlabel("CAM_FREQ_46", 95.0, y, shape="input")
    vshunt(sh, "Device:R", "R", 120.0, y + 18.0, "16k",
           {"Source": "cam_frontend.cir R2",
            "Note": "10k/16k: 5.00 V -> 3.077 V, and 4.50 V (sensor_rail."
                    "cir's own fault floor for a healthy group) -> "
                    "2.769 V. Both inside [2.31 V logic-high floor, "
                    "3.6 V Vih abs-max]."}, node)
    vshunt(sh, "Device:C", "C", 145.0, y + 18.0, "22nF",
           {"Source": "cam_frontend.cir C1",
            "Note": "fc = 1176 Hz against a 12.5 Hz cam fundamental at "
                    "rated speed -- 94x, or 31x if the target turns out "
                    "to carry 3 lobes rather than 1. The lobe count is "
                    "not recorded anywhere in this repo; the margin "
                    "survives either."}, node)
    vshunt(sh, "Device:D_Zener", "D", 170.0, y + 18.0, "3.3V",
           {"Source": "cam_frontend.cir D1",
            "Note": "Cathode to the signal. 3.077 V nominal sits 0.22 V "
                    "clear of the knee, so it does not touch the signal "
                    "-- it is there for a harness short, where it clamps "
                    "at 3.308 V and 3.669 mA."}, node, rot=270)
    node.to(200.0)
    sh.hlabel("CAM_EDGE", 200.0, y, shape="output")

    sh.hlabel("CAM_GND_44", 40.0, 282.0, shape="input")
    sh.wire(40.0, 282.0, 55.0, 282.0)
    gnd_below(sh, 55.0, 282.0)


def notes(sh):
    sh.text(
        "CLAMP LEAKAGE IS THE BINDING SPEC, WHICH INVERTS THE RULE THIS "
        "PROJECT USED ON THE POWER PATH. Every earlier clamp on this "
        "board was chosen for forward drop -- the negative-clamp\n"
        "Schottky's 0.547 V at 15 A decomposes into junction and bulk "
        "terms and that decomposition is what ruled out paralleling "
        "junction devices. Here the forward drop does not matter at all: "
        "these diodes\n"
        "conduct only on a fault, into a 4.7k series resistor that is "
        "already doing the limiting. What matters is what they do when "
        "they are OFF.\n"
        "\n"
        "A reverse-biased diode's leakage flows out of the 4.489k Thevenin "
        "at the input node and appears as an offset voltage there. The "
        "hysteresis window is +/-198 mV, so:\n"
        "\n"
        "    BAT54S-class Schottky   ~2 uA at 25 C, and Schottky leakage "
        "rises roughly 100x to 125 C   ->  ~200 uA  ->  0.90 V of offset.\n"
        "                            That is 4.5x the whole hysteresis "
        "window. The comparator latches and the engine has no speed "
        "signal at temperature.\n"
        "    BAV199-class low-leakage silicon   5 nA max at 25 C, under "
        "1 uA at 125 C   ->  under 4.5 mV of offset, 2% of the window.\n"
        "\n"
        "The two clamp diodes are biased symmetrically (both reverse-"
        "biased by 1.65 V from VR_BIAS) so their leakages partly cancel, "
        "and both legs are matched so what survives is partly\n"
        "common-mode -- but a design whose speed input depends on "
        "cancellation between two diodes' hot leakage is not one to "
        "defend. The requirement is stated instead: reverse leakage at or "
        "below\n"
        "1 uA at 125 C. vr_conditioner.cir does NOT model this -- its "
        "comparator is an ideal switch with no input network at all, so "
        "no clamp, no leakage and no offset exist in it. This is\n"
        "the sheet finding something the block could not.",
        40.0, 313.0, size=1.6)
    sh.text(
        "WHY THE CAM FRONT-END ON THIS SHEET IS NOT THE ONE THE SPEC "
        "ASKS FOR. Spec sec.4 and docs/pinmap.md sec.1.3 both give pin "
        "46's front end as \"Pull-up to 5V_SENSOR -> timer capture\":\n"
        "the Hall output pulled to 5 V and taken straight into PTB3. NXP "
        "S32K1xx Data Sheet Rev. 15, Table 17, puts Vih max at VDD + 0.3 "
        "V, about 3.6 V at VDD = 3.3 V, so a full 5 V swing is\n"
        "not a guaranteed valid logic level. Table 1 does allow -0.8 to "
        "+5.8 V on any I/O pin, but only while respecting the +/-3 mA "
        "injection limit, and the datasheet's own words are that\n"
        "\"functional operation at the maximum values is not guaranteed\" "
        "-- a stress margin, not a design basis for a pin that would sit "
        "at 5 V once per cam revolution for the machine's\n"
        "running life. The 16k to ground turns it into the same 10k/16k "
        "divider the ratiometric sensor channels already use. It costs "
        "one resistor.\n"
        "\n"
        "This was found by writing cam_frontend.cir, which pinmap sec.4 "
        "asked for by name before this sheet was drawn: no block had ever "
        "simulated a cam front-end -- vr_conditioner.cir covers the\n"
        "crank and there was no cam equivalent -- so a 5 V swing on a 3.3 "
        "V pin had never been checked. Fourth finding of the same shape "
        "in this project: a document and an executable file\n"
        "disagreeing, with nothing comparing them.",
        40.0, 357.0, size=1.6)
    sh.text(
        "PARTS NOT CHOSEN ON THIS SHEET: the comparator "
        "(COMPARATOR_GENERIC -- placeholder pins, no footprint) and the "
        "cam Hall sensor itself, which is U8 on the unknowns register and\n"
        "needs the machine. The comparator's requirement is unusually "
        "easy, and deliberately so: biasing the floating coil to VR_BIAS "
        "means the inputs never leave mid-rail, so no part is needed\n"
        "whose common-mode range includes ground -- the usual hard "
        "constraint on a zero-cross detector. Single 3.3 V supply, "
        "push-pull rail-to-rail output, propagation delay at or below "
        "1 us\n"
        "(0.009 crank degrees at rated speed on a 60-tooth wheel). Input "
        "offset voltage is a non-issue against a 198 mV window.",
        40.0, 393.0, size=1.6)


def build():
    schlib.verify_pins()
    sh = Sheet("Crank VR conditioner and cam front-end", paper="A2",
               comments=[
                   "Generated by hw/gen_sheet_speed_inputs.py -- do not hand-edit until it is retired",
                   "vr_conditioner.cir / cam_frontend.cir",
                   "Zero-cross with +/-198 mV hysteresis: a fixed threshold cannot see a 2 V cranking signal",
                   "Clamp diodes specified by REVERSE LEAKAGE, not forward drop -- see the sheet note",
               ],
               ref_base=schlib.REF_BASE["speed_inputs"])
    crank(sh)
    bias_generator(sh)
    shield(sh)
    cam(sh)
    notes(sh)
    return sh


if __name__ == "__main__":
    print(build().write(OUT, force="--force" in sys.argv))
