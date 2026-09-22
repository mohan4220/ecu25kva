#!/usr/bin/env python3
"""injector sheet: the boost rail, two bank high sides, three low sides.

Three blocks back this sheet: boost_converter.cir, injector_boost.cir,
injector_turnoff.cir.

injector_boost.cir is the argument for the whole stage. A common-rail
solenoid is 200 uH and 0.5 ohm, and the needle does not lift until
current reaches about 18 A. From the battery that takes 439 us; from a
100 V rail it takes 38 us. At a 1 ms injection that is the difference
between spending 44% of the event lifting the needle and spending 4%.

TWO THINGS THIS SHEET DECIDES that the blocks left open, because they
are wiring questions and a netlist is where wiring gets decided.

  WHERE THE HOLD CURRENT COMES FROM. boost_converter.cir measured that
  supplying hold from the boost rail costs 28x the peak phase's charge
  and collapses the rail, so hold has to come from the battery -- but it
  did not say through what. TWO HIGH-SIDE SWITCHES PER BANK onto a
  common node: one from the boost rail for the peak phase, one from the
  battery for hold, plus D_fw from GROUND to that node. Hold chopping
  happens on the HIGH side and the coil freewheels through D_fw, which
  is exactly the circuit injector_turnoff.cir models and spends a
  paragraph of its header justifying.

  THAT IS A CORRECTION, MADE 21 SEPTEMBER 2026. The first version of
  this sheet used a plain diode-OR from VBAT_PROT to the bank node and
  chopped the LOW side for hold, on the argument that it needed no extra
  MCU pin. It is wrong three ways, and the third is what found it --
  trying to choose a gate driver for it. See high_side()'s own docstring
  for all three. The short version: a bank node held at 12.8 V by a
  diode cannot be chopped for hold, leaves connector pins 03 and 05
  permanently live through that diode, and never swings low enough for a
  bootstrap capacitor to charge.

  IT COSTS TWO MCU PINS, PTB5 and PTA17, both FTM0 channels like the
  five injector pins already allocated -- so the whole stage stays on
  one timer and its edges stay phase-locked. docs/pinmap.md sec.1.5
  carries the correction.

  WHERE THE CURRENT-SENSE SHUNTS GO. docs/pinmap.md sec.1.6 calls the
  per-bank split INFERRED and says outright: "Settle by choosing the
  shunt placement when the injector driver sheet is drawn." Settled
  here as LOW-SIDE and GROUND-REFERENCED, shared per bank: cylinders 1
  and 3 fire 240 crank degrees apart and never overlap, so one shunt in
  their common source return is unambiguous, and it reads the same
  current a high-side shunt would -- without needing an amplifier whose
  common-mode range reaches 100 V.

AND ONE THING THIS SHEET FINDS. Spec sec.4's fail-safe requirement names
all six driver gates including 03/05, and supervisor.cir sized a
ground-referenced clamp for them. A ground-referenced clamp cannot
service a HIGH-SIDE gate -- see the sheet note.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import schlib
from schlib import Sheet, Rail, pin_xy, PINS

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "injector.kicad_sch")
ICPINS = json.load(open(os.path.join(HW, "lib", "ic_pins.json")))
BOOST = "ecu25kva:TPS40210"
DRIVER = "ecu25kva:AUIRS2181S"
GND_DROP = 7.62
QP = PINS["Device:Q_NMOS_GSD"]

# Device:Q_NMOS_GSD at rot=0: gate LEFT at (x-5.08, y), drain UP at
# (x+2.54, y-5.08), source DOWN at (x+2.54, y+5.08). Every wire off it is
# then orthogonal, which rot=270 does not give -- that orientation puts
# drain and source side by side and every connection to a rail above or
# below comes out diagonal.
def fet_pins(x, y):
    return (pin_xy(*QP["1"], x, y, 0),      # G
            pin_xy(*QP["3"], x, y, 0),      # D
            pin_xy(*QP["2"], x, y, 0))      # S


def ic_pin(part, num, x, y):
    dx, dy = ICPINS[part][str(num)]
    return pin_xy(dx, dy, x, y, 0)


def stub(sh, pin, dx, name):
    """A short horizontal wire off an IC pin, ending in a local label.

    The controller's ten pins each want their own passive network, and
    routing ten networks into a 2.54 mm pin pitch produces wires that
    cross other pins' stubs. Labels do the joining instead: the networks
    sit in their own block below, each on a stub carrying the same name.
    """
    ex = pin[0] + dx
    sh.wire(pin[0], pin[1], ex, pin[1])
    sh.label(name, ex, pin[1], rot=180 if dx < 0 else 0)
    return ex


def to_gnd(sh, x, y, libid, prefix, value, label, fields, rot=0):
    """One two-terminal part from a labelled net down to ground."""
    sh.wire(x, y, x, y - 6.0)
    sh.label(label, x, y - 6.0, rot=90)
    rail = Rail(sh, y)
    rail.to(x)
    vshunt(sh, libid, prefix, x, y + 14.0, value, fields, rail, rot=rot)


def series_chain(sh, y, x0, left_label, parts, right_label, hlabel_in=False):
    """A horizontal string of two-terminal parts between two named nets."""
    if hlabel_in:
        sh.hlabel(left_label, x0, y, shape="input")
    else:
        sh.label(left_label, x0, y, rot=180)
    rail = Rail(sh, y)
    rail.to(x0)
    for i, (libid, prefix, value, fields) in enumerate(parts):
        px = x0 + 40.0 + i * 40.0
        sh.place(libid, prefix, px, y, value, rot=90, fields=fields)
        a = pin_xy(*PINS[libid]["1"], px, y, 90)
        b = pin_xy(*PINS[libid]["2"], px, y, 90)
        l, r = (a, b) if a[0] < b[0] else (b, a)
        rail.to(l[0])
        rail = Rail(sh, y)
        rail.to(r[0])
    rail.to(x0 + 40.0 + len(parts) * 40.0 - 10.0)
    sh.label(right_label, x0 + 40.0 + len(parts) * 40.0 - 10.0, y)


def gnd_below(sh, x, y):
    sh.wire(x, y, x, y + GND_DROP)
    sh.gnd(x, y + GND_DROP)


def vshunt(sh, libid, prefix, x, y, value, fields, rail, rot=0):
    sh.place(libid, prefix, x, y, value, rot=rot, fields=fields)
    a = pin_xy(*PINS[libid]["1"], x, y, rot)
    b = pin_xy(*PINS[libid]["2"], x, y, rot)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    rx, ry = rail.to(t[0], tap=True)
    sh.wire(rx, ry, t[0], t[1])
    gnd_below(sh, bo[0], bo[1])


def diode_up(sh, x, y_lo, value, fields, label_top, drop=14.0):
    """A diode standing on a rail, conducting UPWARD into a labelled net.

    rot=270 puts the cathode at the top and the anode at the bottom, so
    the part sits above the rail it drains into that net.
    """
    sh.place("Device:D", "D", x, y_lo - drop, value, rot=270, fields=fields)
    k = pin_xy(*PINS["Device:D"]["1"], x, y_lo - drop, 270)
    a = pin_xy(*PINS["Device:D"]["2"], x, y_lo - drop, 270)
    sh.wire(a[0], a[1], a[0], y_lo)
    sh.wire(k[0], k[1], k[0], k[1] - 6.0)
    sh.label(label_top, k[0], k[1] - 6.0)
    return a


def diode_down(sh, x, y_lo, value, fields, label_top, drop=14.0):
    """A diode standing above a rail, conducting DOWN into it.

    rot=90 is the other way round -- anode at the top, cathode at the
    bottom -- which is what a supply diode feeding a node looks like.
    """
    sh.place("Device:D", "D", x, y_lo - drop, value, rot=90, fields=fields)
    k = pin_xy(*PINS["Device:D"]["1"], x, y_lo - drop, 90)
    a = pin_xy(*PINS["Device:D"]["2"], x, y_lo - drop, 90)
    sh.wire(k[0], k[1], k[0], y_lo)
    sh.wire(a[0], a[1], a[0], a[1] - 14.0)
    sh.hlabel(label_top, a[0], a[1] - 14.0, shape="input", rot=90)


def gate_network(sh, gp, gate_name, kill=True):
    """The fail-safe gate network spec sec.4 requires on all six gates.

    470 ohm is supervisor.cir claim 6: the largest standard pulldown that
    still holds the gate below Vgs(th) = 1.0 V against Miller coupling at
    Crss = 500 pF. 10k -- the value normally reached for -- fails even at
    the low end of memo 11's own Crss envelope.
    """
    gx, gy = gp
    sh.wire(gx, gy, gx - 20.0, gy)
    sh.label(gate_name, gx - 20.0, gy, rot=180)

    px = gx - 40.0
    sh.place("Device:R", "R", px, gy + 18.0, "470R",
             fields={"Source": "supervisor.cir claim 6; bom_requirements "
                               "GATE-PULLDOWN",
                     "Note": "Largest standard value holding the gate under "
                             "Vgs(th)=1.0 V at Crss=500 pF.",
                     "Cost": "21.3 mA per gate at 10 V; 1.28 W across all six"})
    pa = pin_xy(*PINS["Device:R"]["1"], px, gy + 18.0, 0)
    pb = pin_xy(*PINS["Device:R"]["2"], px, gy + 18.0, 0)
    p_top, p_bot = (pa, pb) if pa[1] < pb[1] else (pb, pa)
    sh.wire(px, gy, p_top[0], p_top[1])
    sh.label(gate_name, px, gy, rot=180)
    gnd_below(sh, p_bot[0], p_bot[1])

    if not kill:
        return
    kx = px - 30.0
    sh.place("Device:Q_NMOS_GSD", "Q", kx, gy + 18.0, "2N7002BK",
             footprint="Package_TO_SOT_SMD:SOT-23",
             fields={"MPN": "2N7002BK",
                     "Source": "supervisor.cir -- the kill FET",
                     "Note": "In parallel with the 470 ohm pulldown, not "
                             "instead of it. Ron 5 ohm dominates the "
                             "pulldown by ~2000x -- modelled kill time "
                             "23 ns, with no MCU involvement at all, which "
                             "is what makes it work against a HUNG MCU and "
                             "not only a reset one."})
    kg, kd, ks = fet_pins(kx, gy + 18.0)
    sh.wire(kd[0], kd[1], kd[0], gy)
    sh.label(gate_name, kd[0], gy, rot=180)
    gnd_below(sh, ks[0], ks[1])
    sh.wire(kg[0], kg[1], kg[0] - 15.0, kg[1])
    sh.hlabel("GATE_KILL", kg[0] - 15.0, kg[1], shape="input", rot=180)


def boost_rail(sh):
    """The reservoir, the bleed, and the converter that is not drawn."""
    y = 48.0
    sh.text("BOOST RAIL -- 100 V reservoir for the injector peak phase",
            40.0, 32.0, size=1.8)
    sh.label("BOOST_100V", 40.0, y)
    rail = Rail(sh, y)
    rail.to(40.0)
    vshunt(sh, "Device:C_Polarized", "C", 80.0, y + 20.0, "47uF 150V",
           {"Source": "boost_converter.cir Ca",
            "Note": "The converter cannot deliver 18 A -- it delivers a "
                    "trickle and this capacitor delivers the pulse. "
                    "342 uC per peak phase gives 7.3 V of droop, so the "
                    "rail sags to 92.7 V. Its job is to be much larger "
                    "than 13.5 V, not to be exactly 100 V.",
            "Vr": "150 V class: 100 V setpoint plus the recirculation "
                  "bump, same margin logic transient_clamp used"}, rail)
    vshunt(sh, "Device:R", "R", 120.0, y + 20.0, "22k 1W",
           {"Source": "boost_converter.cir arrangement C; "
                      "bom_requirements BOOST-BLEED",
            "Note": "The charger regulates from BELOW only -- 50 mA while "
                    "the rail is under setpoint, nothing above it. Without "
                    "this resistor ANY excursion above 100 V is permanent: "
                    "three hold-cutoff recirculation events stack to "
                    "106.4 V and stay there.",
            "Sizing": "one 100 uC event is 2.14 V on 47 uF; above setpoint "
                      "the charger is off so the whole 4.55 mA discharges "
                      "it in 21.4 ms, against 26.67 ms between cylinders",
            "Cost": "455 mW burned continuously whenever the rail is up"},
           rail)
    rail.to(160.0)
    sh.text("the converter that feeds this rail is drawn at the foot of "
            "the sheet -- TPS40210-Q1, VBAT_PROT to BOOST_100V",
            180.0, 40.0, size=1.6)


def high_side(sh, bx, bank, boost_net, bat_net, out_net, tag, note):
    """One bank's high side: TWO switches, a freewheel diode, a bleed.

    CORRECTED 21 September 2026. The first version of this sheet fed the
    bank node from VBAT_PROT through a plain diode-OR and let the LOW
    side chop for hold. That is wrong in three separate ways, and the
    third one is what found it -- trying to choose a gate driver.

      1  IT CANNOT REGULATE HOLD. With the battery on a diode, the only
         switch in the loop is the low side, and when the low side opens
         the coil's current has nowhere to go but the recirculation
         diode into the 100 V boost rail. That is a FAST decay against
         -87 V, which is turn-off, not chopping. Hold needs a slow
         freewheel around the coil.
      2  IT LEAVES PINS 03 AND 05 PERMANENTLY LIVE. A diode from the
         battery to a connector pin means a harness short to ground
         draws current whenever the battery is connected, with no switch
         anywhere to stop it.
      3  THE GATE DRIVER CANNOT BE BOOTSTRAPPED. A bootstrap capacitor
         charges when the switch node goes LOW. With the battery diode
         holding the bank node at 12.8 V it never does, so the boost
         high side's floating supply can never refresh. This was
         invisible until a part had to be chosen for it.

    What replaces it is what injector_turnoff.cir already models and
    what peak-and-hold drivers actually do: TWO high-side switches onto
    a common bank node -- one from the boost rail for the peak phase,
    one from the battery for hold -- plus D_fw from GROUND to that node,
    which is the freewheel path the block's header spends a paragraph
    explaining it had to add. Hold chopping then happens on the HIGH
    side, the node swings to -0.7 V on every off-time, and the bootstrap
    charges.

    Both switches have their SOURCE on the bank node, so one floating
    supply referenced to that node serves both gates.

    THE BATTERY SWITCH NEEDS A SERIES BLOCKING DIODE and would with
    either polarity of FET: an N-channel's body diode points source to
    drain, so with the bank node at 100 V during the peak phase it would
    dump the boost rail into the battery. The diode goes on the DRAIN
    side, which leaves the FET's own Vds near zero in that state rather
    than leaving a node floating.
    """
    ry = 105.0
    sh.text(f"bank {bank}", bx, 56.0, size=1.6)

    rail = Rail(sh, ry)
    rail.to(bx + 20.0)

    def switch(qx, gate_name, value, fields):
        gp, dp, sp = fet_pins(qx, 85.0)
        sh.place("Device:Q_NMOS_GSD", "Q", qx, 85.0, value, fields=fields)
        # The gate-source resistor lands on the bank rail to the LEFT of
        # the FET's source, so the rail has to be extended to that point
        # FIRST -- Rail only ever moves right, and taking the source tap
        # first left both 470 ohm resistors with a dangling lower pin on
        # a page that plotted correctly.
        gx = qx - 25.0
        rail.to(gx, tap=True)
        rail.to(sp[0], tap=True)
        sh.wire(sp[0], sp[1], sp[0], ry)
        sh.wire(gp[0], gp[1], gx, gp[1])
        sh.label(gate_name, gx, gp[1], rot=180)
        # Gate to SOURCE, not gate to ground: the source of a high-side
        # N-FET swings with the bank node. supervisor.cir sized 470 ohm
        # against Miller coupling; the divider is the same, only its
        # reference moves.
        sh.place("Device:R", "R", gx, 95.0, "470R",
                 fields={"Source": "supervisor.cir claim 6, referenced to "
                                   "SOURCE rather than to ground",
                         "Note": "A pulldown to GROUND here would hold Vgs "
                                 "at minus the bank voltage and fight the "
                                 "driver on every edge."})
        ra = pin_xy(*PINS["Device:R"]["1"], gx, 95.0, 0)
        rb = pin_xy(*PINS["Device:R"]["2"], gx, 95.0, 0)
        r_top, r_bot = (ra, rb) if ra[1] < rb[1] else (rb, ra)
        sh.wire(gx, gp[1], r_top[0], r_top[1])
        sh.wire(r_bot[0], r_bot[1], gx, ry)
        return dp

    # -- the boost switch: peak phase only --------------------------
    dp = switch(bx + 60.0, tag + "_BOOST_GATE", "150V N-ch, 18A peak",
                {"Source": "injector_boost.cir -- the 100 V branch; "
                           "injector_turnoff.cir Shs",
                 "Note": note,
                 "Vds": "150 V class against a 100 V rail the "
                        "recirculation bump can push above setpoint"})
    sh.wire(dp[0], dp[1], dp[0], dp[1] - 14.0)
    sh.label("BOOST_100V", dp[0], dp[1] - 14.0)

    # -- the battery switch: hold chopping --------------------------
    dp = switch(bx + 150.0, tag + "_BAT_GATE", "60V N-ch, 18A",
                {"Source": "boost_converter.cir arrangement A -- hold "
                           "current comes from the BATTERY",
                 "Note": "Chops for hold. 60 V class, not 150 V: the "
                         "series blocking diode above it holds off the "
                         "boost rail, so this FET's own Vds stays near "
                         "zero during the peak phase.",
                 "Vds": "60 V"})
    diode_down(sh, dp[0], dp[1], "150V 20A ultrafast",
               {"Tag": "INJ-RECIRC",
                "Note": "BLOCKING, not freewheeling. Without it the "
                        "battery FET's own body diode -- source to drain "
                        "on an N-channel -- dumps the 100 V boost rail "
                        "into the battery every peak phase. Reverse "
                        "stress is 100 - 13.5 = 86.5 V, so 150 V class "
                        "like the rest of that rail."},
               "VBAT_PROT", drop=16.0)

    # -- the freewheel path hold chopping needs ----------------------
    fx = bx + 200.0
    sh.place("Device:D", "D", fx, ry + 14.0, "150V 20A ultrafast",
             rot=270,
             fields={"Tag": "INJ-RECIRC",
                     "Source": "injector_turnoff.cir D_fw",
                     "Note": "Anode to GROUND, cathode to the bank node. "
                             "This is the slow freewheel that makes hold "
                             "CHOPPING possible: with the boost switch "
                             "off the coil's current circulates through "
                             "the low side and back through here, "
                             "decaying only against I*R and two diode "
                             "drops. It is also why the node reaches "
                             "-0.7 V, which is what lets a bootstrap "
                             "capacitor charge."})
    k = pin_xy(*PINS["Device:D"]["1"], fx, ry + 14.0, 270)
    a = pin_xy(*PINS["Device:D"]["2"], fx, ry + 14.0, 270)
    rx, _ = rail.to(fx, tap=True)
    sh.wire(fx, ry, k[0], k[1])
    gnd_below(sh, a[0], a[1])

    vshunt(sh, "Device:R", "R", bx + 230.0, ry + 18.0, "100k",
           {"Note": "Bleed. With both high sides off and the low sides "
                    "off, nothing else defines this node -- leakage "
                    "through the boost switch would float a connector "
                    "pin toward 100 V. 128 uA at 12.8 V is the price."},
           rail)
    rail.to(bx + 262.0)
    sh.hlabel(out_net, bx + 262.0, ry, shape="output")

    for net, name, dy in ((boost_net, tag + "_BOOST_DRV_IN", 0.0),
                          (bat_net, tag + "_BAT_DRV_IN", 10.0)):
        sh.hlabel(net, bx, 62.0 + dy, shape="input")
        sh.wire(bx, 62.0 + dy, bx + 30.0, 62.0 + dy)
        sh.label(name, bx + 30.0, 62.0 + dy)


def low_side(sh, qx, ctrl_net, out_net, gate_name, drv_in, cyl):
    """One cylinder's low side. Returns the source pin for the bank shunt."""
    qy = 195.0
    gp, dp, sp = fet_pins(qx, qy)
    sh.place("Device:Q_NMOS_GSD", "Q", qx, qy, "150V N-ch, 18A peak",
             fields={"Source": "injector_turnoff.cir Sls (Ron 20 mOhm)",
                     "Note": f"Cylinder {cyl}. Independent per channel -- "
                             "the high side is bank-shared, the low side "
                             "selects which injector in the bank fires.",
                     "Vds": "150 V class: at turn-off this drain is driven "
                            "above the 100 V boost rail by the "
                            "recirculation diode's own drop"})
    drain = Rail(sh, 170.0)
    drain.to(dp[0])
    sh.wire(dp[0], dp[1], dp[0], 170.0)
    drain.to(dp[0] + 14.0, tap=True)
    diode_up(sh, dp[0] + 14.0, 170.0, "150V 20A ultrafast",
             {"Source": "injector_turnoff.cir Drc -- the diode memo 10 "
                        "recommends and the one this block exists to add",
              "Note": "Low side back into the boost reservoir. NOT a "
                      "Zener active clamp across the FET (Nexperia "
                      "AN50003 rates repetitive active clamp "
                      "reliability-'Questionable', gate-oxide wear-out) "
                      "and NOT a freewheel to battery (too slow -- the "
                      "same problem the boost rail exists to fix on the "
                      "opening side).",
              "Peak": "28.7 W instantaneous during turn-off, ~8x the 3.6 W "
                      "average across all 9 events/second -- the pulse "
                      "sizes this part, the average never would"},
             "BOOST_100V")
    drain.to(dp[0] + 32.0)
    sh.hlabel(out_net, dp[0] + 32.0, 170.0, shape="output")

    gate_network(sh, gp, gate_name)
    sh.hlabel(ctrl_net, gp[0] - 85.0, 178.0, shape="input")
    sh.wire(gp[0] - 85.0, 178.0, gp[0] - 55.0, 178.0)
    sh.label(drv_in, gp[0] - 55.0, 178.0)
    return sp


def bank_shunt(sh, sources, x_shunt, sense_net, note):
    """One ground-referenced shunt for a bank's shared source return."""
    y = 240.0
    rail = Rail(sh, y)
    rail.to(sources[0][0])
    for sx, sy in sources:
        rx, ry = rail.to(sx, tap=(sx != sources[-1][0]))
        sh.wire(sx, sy, sx, y)
    vshunt(sh, "Device:R", "R", x_shunt, y + 20.0, "5mOhm 2W 1%",
           {"Source": "settled on this sheet -- docs/pinmap.md sec.1.6 "
                      "asked for the placement",
            "Note": note,
            "Signal": "90 mV at the 18 A peak, 50 mV at the 10 A hold -- "
                      "too small for the ADC directly, so the amplifier "
                      "is not optional",
            "Power": "1.62 W at peak, but ~1.25% duty per cylinder at "
                     "1500 rpm"}, rail)
    rail.to(x_shunt + 40.0)
    sh.label(sense_net, x_shunt + 40.0, y)


def boost_stage(sh):
    """The converter that makes BOOST_100V, chosen 21 September 2026.

    TPS40210-Q1, and the number that chose it is tOFF(min) = 200 ns max
    (TI SLVS861F Table 6.6). A boost needs 94.1% duty at the 6 V cranking
    corner, and at 150 kHz that off-time floor allows 97.0%. Most
    wide-input boost controllers in this class switch at 2.2 MHz, where
    the same 200 ns caps duty at 56% -- below even the 86.6% the rail
    needs at a NOMINAL 13.5 V battery. Switching slower is the
    requirement here, which is the opposite of the usual direction.

    THE RATING THAT DOES NOT FIT. VDD absolute maximum is 52 V (Table
    6.1) and VBAT_PROT reaches 73.3 V for about 50 us on ISO 7637-2
    pulse 2a -- 1.41x over. The same shape of finding that took
    DRV8873-Q1 off the EGR bridge, and solvable here for a reason that
    did not apply there: VDD draws 2.5 mA plus gate charge, not motor
    current, so 47 ohm and a 43 V zener hold it inside the rating
    through the pulse. 43 V is chosen so the clamp stays OUT of
    conduction during the 40 V load dump, which lasts 400 ms rather than
    50 us and would otherwise cook it.

    The POWER stage is untouched by that: the inductor and FET see the
    rail directly and are 150 V class for it, the same class the
    injector switches already carry.

    All of it is checked in run_sim.py under boost_converter -- not with
    a switching model, which this block deliberately does not have, but
    as executable arithmetic on the datasheet's own ratings.
    """
    sh.text("BOOST CONVERTER -- TPS40210-Q1, 6-40 V in, 100 V out at "
            "50 mA average. The reservoir above delivers the pulse; this "
            "delivers the trickle.", 40.0, 414.0, size=2.0)

    # ---- power path ------------------------------------------------
    py = 455.0
    sh.hlabel("VBAT_PROT", 40.0, py, shape="input")
    pw = Rail(sh, py)
    pw.to(40.0)
    vshunt(sh, "Device:C", "C", 75.0, py + 18.0, "4.7uF 100V",
           {"Note": "Input bulk. 100 V class because it sits on "
                    "VBAT_PROT, which reaches 73.3 V on pulse 2a -- the "
                    "same rule every other battery-connected part on this "
                    "board is held to."}, pw)
    sh.place("Device:L", "L", 115.0, py, "330uH 3A", rot=90,
             fields={"Source": "sized here -- boost_converter.cir models "
                               "the converter as an average current and "
                               "has no inductor",
                     "Note": "At 150 kHz and 13.5 V in, ripple is 0.24 A "
                             "on a 0.44 A average -- continuous "
                             "conduction with room. Saturation rating is "
                             "set by the current limit above it, not by "
                             "the operating current: 82 mOhm sense "
                             "against a 120-180 mV threshold trips "
                             "somewhere in 1.46-2.20 A.",
                     "DCR": "<=0.2 ohm -- 0.2 W at the 1 A cranking corner"})
    la = pin_xy(*PINS["Device:L"]["1"], 115.0, py, 90)
    lb = pin_xy(*PINS["Device:L"]["2"], 115.0, py, 90)
    l_l, l_r = (la, lb) if la[0] < lb[0] else (lb, la)
    pw.to(l_l[0])

    sw = Rail(sh, py)
    sw.to(l_r[0])
    sw.to(155.0, tap=True)
    diode_up(sh, 155.0, py, "150V 2A ultrafast",
             {"Note": "The boost diode. Reverse voltage is the output, "
                      "100 V, so this is 150 V class like everything else "
                      "on that rail. Average current is the output's "
                      "50 mA; PEAK is the inductor's 1.06 A at the "
                      "cranking corner, and the peak is what sizes it.",
              "Vr": "150 V"}, "BOOST_100V", drop=18.0)

    qx, qy = 195.0, 472.0
    gp, dp, sp = fet_pins(qx, qy)
    sh.place("Device:Q_NMOS_GSD", "Q", qx, qy, "150V N-ch, logic-level",
             fields={"Source": "sized here -- see the sheet note",
                     "Note": "Grounded source, which is what TPS40210-Q1 "
                             "requires. LOGIC-LEVEL is not optional: at "
                             "the 6 V cranking dip VDD is 5.7 V and the "
                             "part's internal 8 V regulator is in "
                             "dropout, so the gate gets about 5.7 V, not "
                             "8 V. Rds(on) must be specified at "
                             "Vgs = 4.5 V.",
                     "Vds": "150 V",
                     "Qg": "<=25 nC -- it sets the 3.75 mA of gate-drive "
                           "current the VDD series resistor has to pass"})
    sw.to(dp[0], tap=True)
    sh.wire(dp[0], dp[1], dp[0], py)
    sw.to(230.0)
    sh.label("SW_BOOST", 230.0, py)

    sns = Rail(sh, 492.0)
    sns.to(sp[0])
    sh.wire(sp[0], sp[1], sp[0], 492.0)
    vshunt(sh, "Device:R", "R", sp[0], 492.0 + 16.0, "82mOhm 1%",
           {"Source": "TPS40210-Q1 Table 6.5, VISNS(oc) 120-180 mV",
            "Note": "Current limit lands in 1.46-2.20 A across the "
                    "threshold's own tolerance, against a 1.06 A peak at "
                    "the cranking corner -- 38% margin at the ADVERSE "
                    "end of the threshold, which is the end that matters.",
            "Power": "1.06^2 * 82 mOhm = 92 mW"}, sns)
    sns.to(230.0)
    sh.label("ISNS_BOOST", 230.0, 492.0)
    sh.wire(gp[0], gp[1], 170.0, gp[1])
    sh.label("GDRV_BOOST", 170.0, gp[1], rot=180)

    # ---- the controller --------------------------------------------
    ux, uy = 310.0, 472.0
    sh.place(BOOST, "U", ux, uy, "TPS40210",
             footprint="Package_SO:HVSSOP-10-1EP_3x3mm_P0.5mm_EP1.57x1.88mm",
             fields={"Source": "TI SLVS861F (Aug 2008, rev. Jun 2020)",
                     "Note": "Chosen on tOFF(min) = 200 ns max, which is "
                             "what makes 94.1% duty reachable at the 6 V "
                             "cranking corner. VDD abs max is 52 V and "
                             "the rail reaches 73.3 V -- see the clamp.",
                     "Fsw": "150 kHz, set by RC: 365k and 330 pF against "
                            "the datasheet's own 182k/330pF = 300 kHz"})
    for num, name, dx in (("10", "VDD_BOOST", -22.0), ("1", "RC_BOOST", -30.0),
                          ("2", "SS_BOOST", -38.0), ("3", "EN_BOOST", -46.0)):
        stub(sh, ic_pin("TPS40210", num, ux, uy), dx, name)
    for num, name, dx in (("8", "GDRV_BOOST", 22.0), ("7", "ISNS_BOOST", 30.0),
                          ("5", "FB_BOOST", 38.0), ("4", "COMP_BOOST", 46.0),
                          ("9", "BP_BOOST", 54.0)):
        stub(sh, ic_pin("TPS40210", num, ux, uy), dx, name)
    g = ic_pin("TPS40210", "6", ux, uy)
    gnd_below(sh, g[0], g[1])

    # ---- everything that returns to ground -------------------------
    cy = 528.0
    cluster = [
        (440.0, "Device:C", "C", "1uF 100V", "VDD_BOOST", 0,
         {"Note": "VDD bypass, INSIDE the 47 ohm. 100 V class anyway -- "
                  "it is one resistor away from a 73.3 V rail."}),
        # rot=270 puts the CATHODE at the top. At rot=0 a zener is
        # HORIZONTAL, both pins share a y, and to_gnd's top/bottom pick
        # is then arbitrary -- which is how the first netlist came back
        # with the clamp's anode on VDD and its cathode on ground, on a
        # page that plotted correctly.
        (480.0, "Device:D_Zener", "D", "43V 1W", "VDD_BOOST", 270,
         {"Tag": "BOOST-VDD-CLAMP",
          "Note": "Cathode to VDD. 43 V, not 39 V, so it stays OUT of "
                  "conduction during the 400 ms 40 V load dump and only "
                  "works during the 50 us pulse -- 645 mA, 1.39 mJ. A "
                  "lower clamp would sit in conduction for 400 ms at "
                  "0.8 W instead."}),
        (520.0, "Device:C", "C", "330pF", "RC_BOOST", 0,
         {"Source": "TPS40210-Q1 -- with 365k to VDD this sets 150 kHz",
          "Note": "The datasheet's own reference point is 182k/330pF = "
                  "300 kHz, so keeping C and doubling R halves it."}),
        (560.0, "Device:C", "C", "100nF", "SS_BOOST", 0,
         {"Note": "Soft start. Also the overcurrent retry timer -- the "
                  "part discharges this pin on a fault and restarts."}),
        (600.0, "Device:R", "R", "10k", "EN_BOOST", 0,
         {"Source": "TPS40210-Q1 Table 6.5 -- DIS/EN has a 1 MOhm "
                    "internal pulldown and the pin is ACTIVE HIGH",
          "Note": "Pulled down rather than left floating, so the enable "
                  "state is asserted by copper. Same treatment the CAN "
                  "transceivers' STB gets, and for the same reason: a "
                  "GPIO can take it later."}),
        (640.0, "Device:C", "C", "1uF", "BP_BOOST", 0,
         {"Source": "TPS40210-Q1 pin table -- 1 uF from BP to GND",
          "Note": "The internal 8 V regulator's reservoir, and the "
                  "gate driver's charge source."}),
        (680.0, "Device:R", "R", "7.06k 1%", "FB_BOOST", 0,
         {"Source": "TPS40210-Q1 VFB = 700 mV (686-714 mV over temp)",
          "Note": "With 998k above: 0.700 * (998000+7060)/7060 = 99.7 V. "
                  "The reference's own +/-2% over temperature moves that "
                  "+/-2 V, which the 65-115 V envelope absorbs."}),
    ]
    for x, libid, prefix, value, label, rot, fields in cluster:
        to_gnd(sh, x, cy, libid, prefix, value, label, fields, rot=rot)

    # ---- the series strings ----------------------------------------
    series_chain(
        sh, 556.0, 40.0, "VBAT_PROT",
        [("Device:R", "R", "47R 1W",
          {"Tag": "BOOST-VDD-CLAMP",
           "Note": "The other half of the clamp. Small enough that 6.25 mA "
                   "drops only 0.29 V, so VDD is 5.71 V at the cranking "
                   "dip against a 4.5 V UVLO ceiling; large enough that "
                   "the zener sees 645 mA and not more during pulse 2a."})],
        "VDD_BOOST", hlabel_in=True)
    series_chain(
        sh, 574.0, 40.0, "VDD_BOOST",
        [("Device:R", "R", "365k 1%",
          {"Source": "TPS40210-Q1 -- RC resistor returns to VDD, not to "
                     "a rail of its own",
           "Note": "365k with 330 pF gives 150 kHz. Frequency line "
                   "regulation is specified -20%/+7% over 4.5-52 V, "
                   "which is why the duty margin is quoted at the "
                   "datasheet's MAXIMUM off-time and not its typical."})],
        "RC_BOOST")
    series_chain(
        sh, 556.0, 240.0, "BOOST_100V",
        [("Device:R", "R", "499k 1%",
          {"Note": "Two in series, not one. 100 V across a single 1206 "
                   "is inside its rating but not by much; splitting it "
                   "halves the voltage per part and the power with it."}),
         ("Device:R", "R", "499k 1%", {"Note": "Second half of the pair."})],
        "FB_BOOST")
    series_chain(
        sh, 574.0, 240.0, "COMP_BOOST",
        [("Device:R", "R", "10k",
          {"Note": "STARTING POINT, NOT A RESULT. See the sheet note."}),
         ("Device:C", "C", "6.8nF",
          {"Note": "Zero at 2.3 kHz, below the 17.3 kHz right-half-plane "
                   "zero a boost puts at (1-D)^2 * Rload / (2*pi*L). "
                   "STARTING POINT -- see the sheet note."})],
        "FB_BOOST")

    sh.text(
        "THE COMPENSATION VALUES ARE A STARTING POINT AND THE SHEET SAYS "
        "SO. Rcomp 10k and Ccomp 6.8 nF put the error amplifier's zero at "
        "2.3 kHz, below the right-half-plane zero a boost\n"
        "converter puts at (1-D)^2 * Rload / (2*pi*L) = 17.3 kHz at "
        "13.5 V in -- which is the constraint that actually bounds "
        "crossover, and it MOVES with duty cycle, so the cranking corner "
        "is the hard one.\n"
        "Everything else on this sheet traces to a datasheet number or a "
        "simulation result. These two do not, and cannot: a current-mode "
        "boost's loop depends on the inductor's real DCR, the\n"
        "capacitor's real ESR and the FET's real switching behaviour. "
        "They are bench measurements. What is defensible now is the "
        "TOPOLOGY and the starting values; the loop gets measured.\n"
        "\n"
        "NOT DRAWN, and deliberately: no output capacitor appears here, "
        "because the 47 uF reservoir at the top of this sheet IS the "
        "output capacitor. Its 22k bleed is the only thing that can\n"
        "take charge OFF this rail -- a boost converter cannot pull its "
        "own output down, which is the same one-sided regulation "
        "boost_converter.cir's arrangement C measures.",
        420.0, 442.0, size=1.6)


def between(sh, x, y, libid, prefix, value, top, bot, fields, rot=0):
    """A vertical two-terminal part between two labelled nets."""
    sh.place(libid, prefix, x, y, value, rot=rot, fields=fields)
    a = pin_xy(*PINS[libid]["1"], x, y, rot)
    b = pin_xy(*PINS[libid]["2"], x, y, rot)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    sh.wire(t[0], t[1], t[0], t[1] - 5.0)
    sh.label(top, t[0], t[1] - 5.0, rot=90)
    sh.wire(bo[0], bo[1], bo[0], bo[1] + 5.0)
    sh.label(bot, bo[0], bo[1] + 5.0, rot=270)


def input_kill(sh, x, y, node):
    """The kill clamp, moved to the driver's LOGIC input.

    A ground-referenced FET cannot short a high-side gate floating 100 V
    up, which is the finding this sheet already carries. The driver's HIN
    pin IS ground-referenced, so the same supervisor.cir kill FET goes
    there instead, behind a 1k from the MCU: when GATE_KILL asserts, HIN
    is pulled low against a hung MCU driving it high, and HO follows
    within the driver's 330 ns maximum turn-off delay.
    """
    kg, kd, ks = fet_pins(x, y)
    sh.place("Device:Q_NMOS_GSD", "Q", x, y, "2N7002BK",
             footprint="Package_TO_SOT_SMD:SOT-23",
             fields={"MPN": "2N7002BK",
                     "Source": "supervisor.cir -- the kill FET, moved to "
                               "the driver's logic input",
                     "Note": "Pulls HIN low against a hung MCU driving it "
                             "high through the 1k. Slower than the "
                             "low-side gate clamp -- 330 ns max driver "
                             "turn-off against 23 ns -- and that is "
                             "acceptable because it is not the path the "
                             "fail-safe argument rests on: the low sides "
                             "are in SERIES with every coil, and killing "
                             "any one stops that cylinder's current."})
    sh.wire(kd[0], kd[1], kd[0], kd[1] - 5.0)
    sh.label(node, kd[0], kd[1] - 5.0, rot=90)
    gnd_below(sh, ks[0], ks[1])
    sh.wire(kg[0], kg[1], kg[0] - 12.0, kg[1])
    sh.hlabel("GATE_KILL", kg[0] - 12.0, kg[1], shape="input", rot=180)


def driver_cell(sh, cx, cy, tag, hin_src, lin, ho, vs, lo):
    """One AUIRS2181S and its five supporting parts."""
    sh.place(DRIVER, "U", cx, cy, "AUIRS2181S",
             footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
             fields={"Source": "Infineon AUIRS2181(4)S datasheet, 10 Jan "
                               "2014 -- 'Piezo / common rail Injection' is "
                               "its first listed application",
                     "Note": f"HO drives {ho}, referenced to {vs}. "
                             + (f"LO drives {lo}." if lo else
                                "LO is spare -- LIN tied low."),
                     "Why": "NO cross-conduction interlock: the high and "
                            "low switches here are in SERIES with the "
                            "coil and must both be on to fire it"})

    def pin(n):
        return ic_pin("AUIRS2181S", n, cx, cy)

    stub(sh, pin("1"), -12.0, f"{tag}_HIN")
    if lin:
        stub(sh, pin("2"), -12.0, lin)
    else:
        # Out past the COM stub's end before it drops. Dropping at -6 ran
        # the ground tie straight down through the VCC and COM stubs: no
        # connection in KiCad, since a crossing mid-span never connects,
        # but a page that reads as if the spare input were tied to VCC.
        lp = pin("2")
        sh.wire(lp[0], lp[1], lp[0] - 30.0, lp[1])
        gnd_below(sh, lp[0] - 30.0, lp[1])
    stub(sh, pin("5"), -20.0, "12V_GATE")
    cp = pin("3")
    sh.wire(cp[0], cp[1], cp[0] - 26.0, cp[1])
    gnd_below(sh, cp[0] - 26.0, cp[1])
    stub(sh, pin("8"), 12.0, f"{tag}_VB")
    stub(sh, pin("7"), 20.0, ho)
    stub(sh, pin("6"), 28.0, vs)
    if lo:
        stub(sh, pin("4"), 36.0, lo)

    ny = cy + 36.0
    series_chain(
        sh, cy + 20.0, cx - 58.0, hin_src,
        [("Device:R", "R", "1k",
          {"Note": "Between the MCU and HIN, so the kill FET below can "
                   "override a hung MCU driving high: 3.3 mA into the "
                   "FET, not a fight between two push-pull outputs."})],
        f"{tag}_HIN")
    input_kill(sh, cx + 30.0, ny, f"{tag}_HIN")
    between(sh, cx - 44.0, ny, "Device:D", "D", "200V 1A fast",
            "12V_GATE", f"{tag}_VB", rot=90,
            fields={"Note": "Bootstrap diode -- the driver has none "
                            "built in. Blocks VB, which rides 12 V above "
                            "a bank node that reaches ~102 V: 200 V "
                            "class. It charges whenever the bank node "
                            "swings low: every hold off-time through "
                            "D_fw, and between injections through the "
                            "100k bleed."})
    between(sh, cx - 26.0, ny, "Device:C", "C", "1uF 25V",
            f"{tag}_VB", vs,
            fields={"Note": "Bootstrap capacitor. A 60 nC gate over the "
                            "38 us peak phase, plus 150 uA of IQBS, "
                            "droops it 66 mV. Refreshed on every hold "
                            "off-time, so even a 3 ms main injection "
                            "never runs it down."})
    to_gnd(sh, cx - 8.0, ny - 6.0, "Device:C", "C", "1uF 25V", "12V_GATE",
           {"Note": "VCC bypass, at the pin."})


def gate_rail(sh):
    """12V_GATE: the supply every gate driver on the board runs from.

    The board had no rail between 5 V and 40 V, and AUIRS2181S needs
    10-20 V on VCC (UVLO+ 9.8 V max). THE SOURCE IS THE BOOST RAIL, and
    the reason is cranking: a regulator from VBAT_PROT cannot make 12 V
    from a 6-9 V cranking battery, and a gate rail that collapses during
    cranking means no injection exactly when the engine needs it most.
    BOOST_100V is the one rail on the board already designed to hold up
    from 6 V -- that is what TPS40210-Q1 was chosen for.

    NOT THE LM5164, although it is already on the board: its VIN absolute
    maximum is 100 V (TI datasheet 5.1), and BOOST_100V sits at 99.7 V
    nominal and ~102 V with the reference tolerance and a recirculation
    bump. A discrete follower instead, because the load is tiny: five
    drivers' quiescent current plus gate charge is about 3 mA, designed
    for 5 mA.

    FAILURE DIRECTION IS THE SAFE ONE. If the boost stops, 12V_GATE
    collapses, every driver drops into UVLO and holds its outputs low,
    and every gate on the board turns off.
    """
    sh.text("12V_GATE -- gate-drive supply for every driver on the board, "
            "from the boost rail so it survives cranking", 610.0, 350.0,
            size=1.8)
    series_chain(
        sh, 362.0, 610.0, "BOOST_100V",
        [("Device:R", "R", "47k",
          {"Note": "Zener bias, split in two so neither resistor carries "
                   "the full 87 V. 0.87 mA total."}),
         ("Device:R", "R", "47k", {"Note": "Second half."})],
        "BASE_12V")
    to_gnd(sh, 610.0, 392.0, "Device:D_Zener", "D", "13V", "BASE_12V",
           {"Note": "Sets 12V_GATE: 13 V - one Vbe - the drop in the "
                    "limit resistor = 12.1 V at 5 mA."}, rot=270)

    qx, qy = 760.0, 382.0
    sh.place("Device:Q_NPN_BCE", "Q", qx, qy, "NPN 160V, DPAK",
             fields={"Note": "Pass transistor. 88 V across it at 5 mA is "
                             "0.44 W; into a short, the limit below holds "
                             "it to 11.6 mA and 1.16 W. Vceo >= 160 V -- "
                             "the collector sits on a rail that reaches "
                             "~102 V, and a shorted output puts all of it "
                             "across the part.",
                     "Class": "AEC-Q101, Vceo >= 160 V, DPAK"})
    b = pin_xy(*PINS["Device:Q_NPN_BCE"]["1"], qx, qy, 0)
    c = pin_xy(*PINS["Device:Q_NPN_BCE"]["2"], qx, qy, 0)
    e = pin_xy(*PINS["Device:Q_NPN_BCE"]["3"], qx, qy, 0)
    sh.wire(c[0], c[1], c[0], c[1] - 6.0)
    sh.label("BOOST_100V", c[0], c[1] - 6.0, rot=90)
    stub(sh, b, -10.0, "BASE_12V")
    sh.wire(e[0], e[1], e[0], e[1] + 6.0)
    sh.label("Q1E_12V", e[0], e[1] + 6.0, rot=270)

    q2x = 810.0
    sh.place("Device:Q_NPN_BCE", "Q", q2x, qy, "NPN small-signal",
             fields={"Note": "Current limit. Conducts when the drop across "
                             "the 56 ohm reaches one Vbe -- 0.65 V / 56 = "
                             "11.6 mA -- and steals the pass transistor's "
                             "base drive. Without it a shorted 12V_GATE "
                             "gets hFE x the full bias current from a "
                             "100 V rail."})
    b2 = pin_xy(*PINS["Device:Q_NPN_BCE"]["1"], q2x, qy, 0)
    c2 = pin_xy(*PINS["Device:Q_NPN_BCE"]["2"], q2x, qy, 0)
    e2 = pin_xy(*PINS["Device:Q_NPN_BCE"]["3"], q2x, qy, 0)
    sh.wire(c2[0], c2[1], c2[0], c2[1] - 6.0)
    sh.label("BASE_12V", c2[0], c2[1] - 6.0, rot=90)
    stub(sh, b2, -10.0, "Q1E_12V")
    sh.wire(e2[0], e2[1], e2[0], e2[1] + 6.0)
    sh.label("12V_GATE", e2[0], e2[1] + 6.0, rot=270)

    series_chain(
        sh, 412.0, 640.0, "Q1E_12V",
        [("Device:R", "R", "56R",
          {"Note": "The limit's sense resistor. 0.28 V drop at the 5 mA "
                   "design load."})],
        "12V_GATE")
    to_gnd(sh, 720.0, 412.0, "Device:C", "C", "10uF 25V", "12V_GATE",
           {"Note": "Holds the rail through each driver's gate-charge "
                    "pulse."})
    sh.wire(760.0, 420.0, 790.0, 420.0)
    sh.label("12V_GATE", 760.0, 420.0, rot=180)
    sh.hlabel("12V_GATE", 790.0, 420.0, shape="output")


def gate_drivers(sh):
    """Four AUIRS2181S: every injector gate, and one spare low side."""
    sh.text("GATE DRIVERS -- AUIRS2181S x4. Each pairs one high side with "
            "one low side; the pairing is by package, not by circuit.",
            600.0, 150.0, size=1.8)
    driver_cell(sh, 660.0, 172.0, "UA1", "HSA_BOOST_DRV_IN", "LS1_DRV_IN",
                "HSA_BOOST_GATE", "INJ_A_03", "LS1_GATE")
    driver_cell(sh, 775.0, 172.0, "UA2", "HSA_BAT_DRV_IN", "LS3_DRV_IN",
                "HSA_BAT_GATE", "INJ_A_03", "LS3_GATE")
    driver_cell(sh, 660.0, 262.0, "UB1", "HSB_BOOST_DRV_IN", "LS2_DRV_IN",
                "HSB_BOOST_GATE", "INJ_B_05", "LS2_GATE")
    driver_cell(sh, 775.0, 262.0, "UB2", "HSB_BAT_DRV_IN", None,
                "HSB_BAT_GATE", "INJ_B_05", None)


def sense_amp(sh, cx, cy, in_label, out_net, note, supply_hier=True):
    """INA181A1-Q1 across a ground-referenced shunt.

    IN- goes to GND, and that is a LAYOUT instruction the netlist cannot
    carry: it must be a Kelvin tap at the shunt's own ground pad, not a
    via into the pour, because tens of millivolts of signal sit on a
    return carrying the full load current and a few milliohms of pour
    between pad and amplifier is the whole signal.
    """
    import json as _json
    geom = _json.load(open(os.path.join(HW, "lib", "ic_pins.json")))["INA181A1"]

    def p(n):
        return pin_xy(geom[n][0], geom[n][1], cx, cy, 0)

    sh.place("ecu25kva:INA181A1", "U", cx, cy, "INA181A1",
             footprint="Package_TO_SOT_SMD:SOT-23-6",
             fields={"Source": "TI SLYS018F -- gain 20, 350 kHz, VCM "
                               "-0.2 V to 26 V, offset +/-150 uV at VCM=0",
                     "Note": note,
                     "Layout": "IN- is a KELVIN tap at the shunt's ground "
                               "pad, not a via into the pour"})
    a = p("3")
    sh.wire(a[0], a[1], a[0] - 14.0, a[1])
    sh.label(in_label, a[0] - 14.0, a[1], rot=180)
    b = p("4")
    sh.wire(b[0], b[1], b[0] - 6.0, b[1])
    sh.wire(b[0] - 6.0, b[1], b[0] - 6.0, b[1] + 8.0)
    sh.gnd(b[0] - 6.0, b[1] + 8.0)
    for n in ("2", "5"):
        q = p(n)
        sh.wire(q[0], q[1], q[0], q[1] + 7.62)
        sh.gnd(q[0], q[1] + 7.62)
    v = p("6")
    sh.wire(v[0], v[1], v[0], v[1] - 6.0)
    if supply_hier:
        sh.hlabel("3V3_MCU", v[0], v[1] - 6.0, shape="input", rot=90)
    else:
        sh.label("3V3_MCU", v[0], v[1] - 6.0, rot=90)
    o = p("1")
    sh.wire(o[0], o[1], o[0] + 14.0, o[1])
    sh.hlabel(out_net, o[0] + 14.0, o[1], shape="output")
    # Bypass beside it, on the same supply name.
    bx = cx + 24.0
    sh.wire(bx, cy - 16.0, bx, cy - 10.0)
    sh.label("3V3_MCU", bx, cy - 16.0, rot=90)
    sh.place("Device:C", "C", bx, cy - 5.0, "100nF",
             fields={"Note": "At the VS pin."})
    ca = pin_xy(*PINS["Device:C"]["1"], bx, cy - 5.0, 0)
    cb = pin_xy(*PINS["Device:C"]["2"], bx, cy - 5.0, 0)
    ct, cbo = (ca, cb) if ca[1] < cb[1] else (cb, ca)
    sh.wire(bx, cy - 10.0, ct[0], ct[1])
    sh.wire(cbo[0], cbo[1], cbo[0], cbo[1] + 7.62)
    sh.gnd(cbo[0], cbo[1] + 7.62)


def notes(sh):
    sh.text(
        "A GROUND-REFERENCED KILL CLAMP CANNOT SERVICE A HIGH-SIDE GATE, "
        "and spec sec.4's fail-safe list names pins 03/05 alongside the "
        "four low-side gates as though it could. The\n"
        "three low sides here get exactly the network supervisor.cir "
        "sized and docs/pinmap.md sec.2 confirmed pin by pin: a 470 ohm "
        "pulldown to ground, plus a small-signal FET that\n"
        "shorts the gate to ground when GATE_KILL asserts, with no MCU "
        "involvement -- which is what makes it work against a hung MCU "
        "and not only a reset one.\n"
        "\n"
        "The FOUR high sides cannot use it -- two per bank since the 21 Sep correction. The source of a high-side "
        "N-FET swings to the boost rail, so a pulldown to GROUND would "
        "hold Vgs at minus the source voltage and fight the\n"
        "driver on every edge, and a kill FET referenced to ground cannot "
        "short a gate that is floating 100 V up. What is drawn instead is "
        "the 470 ohm across GATE and SOURCE -- the\n"
        "same Miller-coupling divider supervisor.cir sized, just "
        "referenced to the terminal it has to be referenced to -- and the "
        "kill path moves into the driver: GATE_KILL must reach the\n"
        "high-side driver's LOGIC INPUT. AUIRS2181S has no shutdown "
        "pin, so the same kill FET sits on HIN behind a 1k from the "
        "MCU -- the one ground-referenced point in that path. That is "
        "drawn in the gate-driver block, and it is the sixth finding of "
        "the shape this\n"
        "project keeps turning up: a document and an executable file "
        "agreeing with each other and both wrong about a case neither "
        "modelled.",
        40.0, 295.0, size=1.6)
    sh.text(
        "GATE DRIVERS: AUIRS2181S x4, chosen 21 Sep 2026. Its first "
        "listed application is 'Piezo / common rail Injection', and "
        "three properties decided it, each against a part\n"
        "that failed on it. NO CROSS-CONDUCTION INTERLOCK: in a half "
        "bridge HO and LO together is shoot-through, but here the high "
        "and low switches are in SERIES with the coil\n"
        "and must BOTH be on to fire it -- UCC27282-Q1 and UCC27712-Q1 "
        "have interlock and could not fire an injector at all. 600 V "
        "OFFSET, against UCC27211A-Q1's 120 V HB\n"
        "absolute maximum, which the bank node plus 12 V clears by 4 V. "
        "VS OPERATIONAL TO -5 V, against UCC27211A-Q1's -1 V HS DC "
        "minimum, which D_fw violates on every hold\n"
        "off-time at 1.0-1.3 V. Each package pairs one high side with "
        "one low side; the pairing is by package, not by circuit, and "
        "UB2's low side is spare.\n"
        "\n"
        "12V_GATE: the board had no rail between 5 V and 40 V, and the "
        "drivers need 10-20 V. It is made from the BOOST rail, because "
        "a regulator from the battery cannot make\n"
        "12 V from a 6-9 V cranking battery -- and a gate rail that "
        "collapses during cranking means no injection exactly when the "
        "engine needs it. Not the LM5164 already on\n"
        "the board: its VIN absolute maximum is 100 V and this rail sits "
        "at ~102 V. A discrete follower with a current limit, for a "
        "~3 mA load. If the boost stops, every driver\n"
        "drops into UVLO and every gate turns off -- the failure runs "
        "the safe way.\n"
        "\n"
        "STILL NOT CHOSEN: the two current-sense amplifiers "
        "(ISNS_INJ_A/B_SENSE -> PTC15 / PTD19). Ground-referenced -- "
        "that is why the shunts went low-side -- gain about 33,\n"
        "100 kHz or better, and a Kelvin tap at the shunt pad.",
        40.0, 352.0, size=1.6)
    sh.text(
        "THE BOOST CONVERTER IS NOW DRAWN, AND THE PART WAS CHOSEN ON "
        "ONE NUMBER: tOFF(min) = 200 ns max, TI SLVS861F Table 6.6. A "
        "boost needs 94.1% duty at the 6 V cranking\n"
        "corner, and at 150 kHz that off-time floor allows 97.0%. Most "
        "wide-input boost controllers in this class switch at 2.2 MHz, "
        "where the same 200 ns caps duty at 56% -- below even the\n"
        "86.6% the rail needs at a nominal 13.5 V battery. Switching "
        "SLOWER is the requirement here, which runs the opposite way to "
        "the usual 'higher frequency, smaller magnetics'.\n"
        "\n"
        "THE RATING THAT DOES NOT FIT, and it is the third time this "
        "board has hit it. VDD absolute maximum is 52 V (Table 6.1) and "
        "VBAT_PROT reaches 73.3 V for about 50 us on ISO\n"
        "7637-2 pulse 2a -- over by 1.41x. Same shape as DRV8873-Q1's "
        "40 V VM, which took that part off the EGR bridge. It is "
        "solvable here for a reason that did not apply there: VDD\n"
        "draws 2.5 mA plus gate charge, not a motor's current, so 47 ohm "
        "and a 43 V zener hold the pin inside its rating through the "
        "pulse. 43 V rather than 39 V so the clamp stays OUT\n"
        "of conduction during the 40 V load dump, which lasts 400 ms "
        "instead of 50 us and would otherwise sit it at 0.8 W. The "
        "POWER stage is untouched: the inductor and FET see the\n"
        "rail directly and are 150 V class for it. All of this is "
        "checked in run_sim.py under boost_converter -- not with a "
        "switching model, which that block deliberately does not\n"
        "have, but as executable arithmetic on the datasheet's own "
        "ratings, the same treatment transient_clamp.cir gives the "
        "73.3 V rail.",
        40.0, 400.0, size=1.6)


def build():
    schlib.verify_pins()
    sh = Sheet("Injector drive: boost converter, boost rail, high sides, low sides",
               paper="A1",
               comments=[
                   "Generated by hw/gen_sheet_injector.py -- do not hand-edit until it is retired",
                   "boost_converter.cir / injector_boost.cir / injector_turnoff.cir",
                   "Hold current arrives through a SECOND high-side switch per bank -- corrected 21 Sep 2026",
                   "Boost controller TPS40210-Q1, chosen on its 200 ns off-time: 150 kHz reaches 94% duty at cranking",
                   "Shunts settled LOW-SIDE and per-bank -- docs/pinmap.md 1.6 asked for the placement",
               ],
               ref_base=schlib.REF_BASE["injector"])
    boost_rail(sh)
    boost_stage(sh)
    gate_drivers(sh)
    gate_rail(sh)
    sh.text("CURRENT SENSE -- INA181A1-Q1 per bank, gain 20", 705.0, 452.0, size=1.6)
    sense_amp(sh, 755.0, 478.0, "ISNS_INJ_A_SENSE", "ISNS_INJ_A",
              "Bank A. 5 mOhm x 18 A x 20 = 1.80 V at the peak, 1.00 V at the 10 A hold -- and headroom to 3.28 V, so a fault up to 32.8 A is MEASURED, not clipped. -> PTC15 (ADC0_SE13).")
    sense_amp(sh, 755.0, 540.0, "ISNS_INJ_B_SENSE", "ISNS_INJ_B",
              "Bank B. Same scaling. On ADC1 while bank A is on ADC0, so the two can be sampled simultaneously. -> PTD19 (ADC1_SE17).", supply_hier=False)

    high_side(sh, 190.0, "A (cyl 1+3)", "INJ_HS_A", "INJ_HS_A_BAT",
              "INJ_A_03", "HSA",
              "Bank-shared: cylinders 1 and 3 fire 240 crank degrees "
              "apart and never overlap, which is what lets one switch "
              "serve both.")
    high_side(sh, 520.0, "B (cyl 2)", "INJ_HS_B", "INJ_HS_B_BAT",
              "INJ_B_05", "HSB",
              "One cylinder in this bank. Kept as a separate switch "
              "rather than merged, because merging would put all three "
              "injectors behind one failure.")

    sh.text("GATE_KILL reaches the four high sides at the drivers' HIN "
            "inputs, not at the gates -- a ground-referenced kill FET "
            "cannot short a gate\n"
            "floating 100 V up, but HIN is ground-referenced. See the "
            "gate-driver block on the right.", 150.0, 128.0, size=1.6)

    s1 = low_side(sh, 130.0, "INJ_LS_1", "INJ_LS1_73", "LS1_GATE",
                  "LS1_DRV_IN", 1)
    s3 = low_side(sh, 300.0, "INJ_LS_3", "INJ_LS3_07", "LS3_GATE",
                  "LS3_DRV_IN", 3)
    s2 = low_side(sh, 470.0, "INJ_LS_2", "INJ_LS2_29", "LS2_GATE",
                  "LS2_DRV_IN", 2)

    bank_shunt(sh, [s1, s3], 200.0, "ISNS_INJ_A_SENSE",
               "Bank A, cylinders 1 and 3 sharing one return. They fire "
               "240 crank degrees apart, so only one is ever conducting "
               "and the shared shunt is unambiguous -- the same fact that "
               "lets the high side be bank-shared.")
    bank_shunt(sh, [s2], 500.0, "ISNS_INJ_B_SENSE",
               "Bank B, cylinder 2 alone. Drawn as its own shunt rather "
               "than merged with bank A's, so the two ADC channels the "
               "pin map allocates (PTC15 / PTD19, one per ADC instance "
               "for simultaneous sampling) stay independent.")
    notes(sh)
    return sh


if __name__ == "__main__":
    print(build().write(OUT, force="--force" in sys.argv))
