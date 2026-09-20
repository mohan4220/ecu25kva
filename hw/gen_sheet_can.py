#!/usr/bin/env python3
"""can sheet: two J1939 channels, split-terminated.

Both channels are real -- spec §2.5 -- and both are populated. Channel 1
carries engine speed to the fitted DSE4522, which is the reason the
fail-safe work exists: that controller takes speed from THIS ECU over
CAN, and its own fuel relay was measured to signal only, not remove
power.

TWO THINGS ON THIS SHEET ARE DESIGN DECISIONS RATHER THAN CONVENTION,
and both come from can_termination.cir:

  Split termination, not a single 120 ohm. The two are IDENTICAL
  differentially -- which is why a schematic label cannot tell them
  apart -- and differ only in common mode, where the split version
  gives noise a path to ground through the midpoint capacitor while
  leaving the differential signal untouched. On a genset sharing a loom
  with contactors and an alternator that is worth more than on a truck.
  Measured: 30 ohm common-mode at 10 MHz against >500 kohm, a factor of
  16562.

  Thin-film resistors, 0.1% and 50 ppm/degC. Ordinary thick-film runs
  100-200 ppm/degC, and at 200 ppm over the full -40/+125 range the
  differential impedance reaches 123.95 ohm against J1939's own 120 --
  which the standard specifies, so missing it is a real finding rather
  than a rounding argument. The specified part lands at 121.10 ohm with
  BOTH tolerance mechanisms stacked adversely.

WHETHER THIS NODE SHOULD TERMINATE AT ALL is a separate question and it
is not settled. J1939 terminates the two ENDS of a backbone, not every
node. Channel 1 is almost certainly a two-node link to the DSE4522, in
which case both ends terminate and this is right. Channel 2's topology
is not established. Both terminations are therefore drawn as FIT
OPTIONS, and the note on the page says so.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import schlib
from schlib import Sheet, Rail, pin_xy, PINS

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "can.kicad_sch")
ICPINS = json.load(open(os.path.join(HW, "lib", "ic_pins.json")))
XCVR = "ecu25kva:TCAN1042HGV"
FP = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
GND_DROP = 7.62


def ic_pin(part, num, x, y):
    dx, dy = ICPINS[part][str(num)]
    return pin_xy(dx, dy, x, y, 0)


def gnd_below(sh, x, y):
    sh.wire(x, y, x, y + GND_DROP)
    sh.gnd(x, y + GND_DROP)


def decouple(sh, x, y, rail_net, value="100nF", note=""):
    """A bypass cap from a named rail down to ground."""
    sh.place("Device:C", "C", x, y, value,
             fields={"Source": note or f"{rail_net} bypass"})
    a = pin_xy(*PINS["Device:C"]["1"], x, y, 0)
    b = pin_xy(*PINS["Device:C"]["2"], x, y, 0)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    sh.wire(t[0], t[1], t[0], t[1] - 6.35)
    sh.label(rail_net, t[0], t[1] - 6.35, rot=90)
    gnd_below(sh, bo[0], bo[1])


def channel(sh, n, ux, uy):
    """One transceiver plus its split termination."""
    P = {k: ic_pin("TCAN1042HGV", num, ux, uy) for k, num in
         (("TXD", 1), ("RXD", 4), ("STB", 8),
          ("CANH", 7), ("CANL", 6), ("VCC", 3), ("VIO", 5), ("GND", 2))}
    sh.place(XCVR, "U", ux, uy, "TCAN1042HGV", footprint=FP,
             fields={"MPN": "TCAN1042HGVDRQ1",
                     "Source": "memo 07 sec.10; TI SLLSES9D Table 6-1",
                     "Note": "H = +/-70 V bus fault, V = VIO pin so the "
                             "logic side sits at 3V3 and needs no level "
                             "shifter"})

    # ---- logic side ----
    # TXD, RXD and STB leave the part on a 2.54 mm pitch, which is not
    # enough vertical room for three label texts side by side. The stubs
    # are staggered so each label sits clear of its neighbours.
    for name, net, shape, reach in (("TXD", f"CAN{n}_TX", "input", 20.32),
                                    ("RXD", f"CAN{n}_RX", "output", 33.02)):
        px, py = P[name]
        sh.wire(px, py, px - reach, py)
        sh.hlabel(net, px - reach, py, shape=shape, rot=180)
    # STB is active high; pulled low for normal operation. Brought to a
    # resistor rather than tied at the pin so a GPIO can take it later.
    sx, sy = P["STB"]
    sh.wire(sx, sy, sx - 12.7, sy)
    sh.place("Device:R", "R", sx - 12.7, sy + 14.0, "10k",
             fields={"Source": "TCAN1042 Table 6-1 -- STB is ACTIVE HIGH, "
                               "so normal operation is STB low",
                     "Note": "Pulled down rather than tied, so a GPIO can "
                             "take standby control later. The pin map has "
                             "no channel for it today."})
    a = pin_xy(*PINS["Device:R"]["1"], sx - 12.7, sy + 14.0, 0)
    b = pin_xy(*PINS["Device:R"]["2"], sx - 12.7, sy + 14.0, 0)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    sh.wire(sx - 12.7, sy, t[0], t[1])
    gnd_below(sh, bo[0], bo[1])
    sh.label(f"CAN{n}_STB", sx - 12.7, sy, rot=180)

    # ---- supplies ----
    vx, vy = P["VCC"]
    sh.wire(vx, vy, vx, vy - 8.0)
    sh.label("5V_MAIN", vx, vy - 8.0, rot=90)
    ix, iy = P["VIO"]
    sh.wire(ix, iy, ix, iy - 8.0)
    sh.label("3V3_MCU", ix, iy - 8.0, rot=90)
    gx, gy = P["GND"]
    gnd_below(sh, gx, gy)
    decouple(sh, ux - 34.0, uy - 26.0, "5V_MAIN",
             note="TCAN1042 VCC bypass")
    decouple(sh, ux - 20.0, uy - 26.0, "3V3_MCU",
             note="TCAN1042 VIO bypass")

    # ---- bus side: split termination ----
    # CANH and CANL leave the part 2.54 mm apart, which is not room for
    # two 7.62 mm resistors between them -- the first version placed them
    # on top of each other and channel 1's termination came back as two
    # unconnected pins. So the pair is fanned out to a usable spacing
    # first, and the network is built between those levels.
    hx, hy = P["CANH"]
    lx2, ly2 = P["CANL"]
    tx = hx + 30.0
    top_y = uy - 16.0
    bot_y = uy + 16.0
    sh.wire(hx, hy, hx + 12.0, hy)
    sh.wire(hx + 12.0, hy, hx + 12.0, top_y)
    sh.wire(lx2, ly2, lx2 + 8.0, ly2)
    sh.wire(lx2 + 8.0, ly2, lx2 + 8.0, bot_y)
    hrail = Rail(sh, top_y)
    hrail.to(hx + 12.0)
    lrail = Rail(sh, bot_y)
    lrail.to(lx2 + 8.0)

    midy = uy
    sh.place("Device:R", "R", tx, (top_y + midy) / 2.0, "60R0",
             fields={"Source": "can_termination.cir Rah; bom_requirements "
                               "CAN-TERM",
                     "Note": "THIN-FILM, 0.1% initial, 50 ppm/degC. "
                             "Thick-film at 200 ppm/degC reaches 123.95 ohm "
                             "over -40/+125 against J1939's own 120.",
                     "Fit": "FIT OPTION -- see the note on termination"})
    ah = pin_xy(*PINS["Device:R"]["1"], tx, (top_y + midy) / 2.0, 0)
    bh = pin_xy(*PINS["Device:R"]["2"], tx, (top_y + midy) / 2.0, 0)
    h_t, h_b = (ah, bh) if ah[1] < bh[1] else (bh, ah)
    rx, ry = hrail.to(tx, tap=True)
    sh.wire(rx, ry, h_t[0], h_t[1])

    sh.place("Device:R", "R", tx, (midy + bot_y) / 2.0, "60R0",
             fields={"Source": "can_termination.cir Ral; bom_requirements "
                               "CAN-TERM",
                     "Note": "Matched pair with the resistor above -- both "
                             "shift together, which is the LESS adverse "
                             "tempco direction and still misses at 200 ppm",
                     "Fit": "FIT OPTION"})
    al = pin_xy(*PINS["Device:R"]["1"], tx, (midy + bot_y) / 2.0, 0)
    bl = pin_xy(*PINS["Device:R"]["2"], tx, (midy + bot_y) / 2.0, 0)
    l_t, l_b = (al, bl) if al[1] < bl[1] else (bl, al)
    # Split at the midpoint so the capacitor meets an ENDPOINT, not a
    # mid-span -- see schlib.Rail.
    sh.wire(h_b[0], h_b[1], tx, midy)
    sh.wire(tx, midy, l_t[0], l_t[1])
    sh.junction(tx, midy)
    rx, ry = lrail.to(tx, tap=True)
    sh.wire(l_b[0], l_b[1], rx, ry)

    # The midpoint capacitor IS the split termination.
    cx = tx + 18.0
    sh.wire(tx, midy, cx, midy)
    sh.place("Device:C", "C", cx, midy + 12.0, "4.7nF",
             fields={"Source": "can_termination.cir Csh -- the midpoint "
                               "capacitor IS the split termination",
                     "Note": "Shunts common mode to ground (30 ohm at "
                             "10 MHz) while leaving the differential "
                             "signal untouched, because the midpoint is a "
                             "virtual ground for differential drive. Still "
                             "138 ohm at the 250 kbit/s bit rate, so it "
                             "does not load the bus."})
    ca = pin_xy(*PINS["Device:C"]["1"], cx, midy + 12.0, 0)
    cb = pin_xy(*PINS["Device:C"]["2"], cx, midy + 12.0, 0)
    c_t, c_b = (ca, cb) if ca[1] < cb[1] else (cb, ca)
    sh.wire(cx, midy, c_t[0], c_t[1])
    gnd_below(sh, c_b[0], c_b[1])

    # ---- out to the connector ----
    for rail, net, py in ((hrail, f"CAN{n}_H", top_y),
                          (lrail, f"CAN{n}_L", bot_y)):
        rail.to(tx + 48.0)
        sh.hlabel(net, tx + 48.0, py, shape="bidirectional")


def notes(sh):
    sh.text(
        "TERMINATION IS A FIT OPTION ON BOTH CHANNELS, and that is a real "
        "open question rather than caution.\n"
        "J1939 terminates the two ENDS of a backbone, not every node. "
        "Channel 1 is almost certainly a two-node link to the fitted "
        "DSE4522 -- which takes engine speed from\n"
        "this ECU over CAN -- so both ends terminate and fitting it here "
        "is right. Channel 2's harness topology is not established. "
        "Fitting 120 ohm at a mid-bus node\n"
        "over-terminates the backbone and costs signal amplitude at every "
        "other node on it, so the resistors are drawn but flagged, and the "
        "decision is the harness's,\n"
        "not this board's.",
        40.0, 215.0, size=1.6)
    sh.text(
        "WHY SPLIT AND NOT ONE RESISTOR -- can_termination.cir. Both "
        "topologies are 120 ohm differentially and measure IDENTICAL "
        "there, which is why a schematic\n"
        "label cannot tell them apart. They differ only in common mode: a "
        "single 120 ohm connects CANH to CANL and nothing else, so "
        "common-mode noise -- both wires\n"
        "swinging together against chassis, which is what an alternator "
        "and contactors produce -- sees an open circuit and stays on the "
        "bus. Measured at 10 MHz:\n"
        "30 ohm for the split network against more than 500 kohm for the "
        "single resistor, a factor of 16562. At the 250 kbit/s bit rate "
        "the midpoint is still 138 ohm,\n"
        "so it shunts the noise without loading the signal.",
        40.0, 255.0, size=1.6)


def build():
    schlib.verify_pins()
    sh = Sheet("CAN: two J1939 channels, split-terminated", paper="A3",
               comments=[
                   "Generated by hw/gen_sheet_can.py -- do not hand-edit until it is retired",
                   "Termination: can_termination.cir + bom_requirements CAN-TERM",
                   "Thin-film 0.1% / 50 ppm -- thick-film misses J1939's 120 ohm at temperature",
                   "Termination is a FIT OPTION on both channels -- see the note",
               ])
    channel(sh, 1, 150.0, 68.0)
    channel(sh, 2, 150.0, 170.0)
    notes(sh)
    return sh


if __name__ == "__main__":
    print(build().write(OUT, force="--force" in sys.argv))
