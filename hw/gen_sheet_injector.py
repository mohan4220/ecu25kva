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
  did not say through what. It is a DIODE-OR, not a second switched
  rail: D2/D4 from VBAT_PROT to each bank node, anode on the battery.
  During the peak phase the bank sits near 100 V and they are reverse
  biased; when the high-side FET stops conducting, the coil pulls the
  bank node down and they supply it at 13.5 V. That works with the ONE
  control pin per bank the pin map allocates (PTC0/PTC1), with no extra
  MCU pin and no sequencing logic.

  This also settles a diode injector_turnoff.cir had to invent. Its
  header explains at length why node "hi" needs a path from ground when
  both switches open -- D_fw, which it calls "standard supporting
  infrastructure". With the battery diode-OR drawn, that path already
  exists and returns to 13.5 V instead of 0 V, so the same part does
  both jobs. The cost is honest: the turn-off clamp is then about
  86.5 V rather than the bare 100 V the block modelled, so turn-off
  takes roughly 41.6 us instead of 34 us.

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
import schlib
from schlib import Sheet, Rail, pin_xy, PINS

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "injector.kicad_sch")
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
    sh.place("Device:Q_NMOS_GSD", "Q", kx, gy + 18.0, "60V small-signal",
             fields={"Source": "supervisor.cir -- the kill FET",
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
    sh.text("the converter is NOT drawn -- it sits between VBAT_PROT and "
            "BOOST_100V; see the note at the foot of the sheet",
            180.0, 48.0, size=1.6)


def high_side(sh, qx, bank, ctrl_net, out_net, gate_name, drv_in,
              ctrl_x, note):
    """One bank's high side: boost FET, battery diode-OR, gate network."""
    qy = 85.0
    ry = 105.0
    gp, dp, sp = fet_pins(qx, qy)
    sh.place("Device:Q_NMOS_GSD", "Q", qx, qy,
             "150V N-ch, bootstrapped high side",
             fields={"Source": "injector_boost.cir -- the 100 V branch; "
                               "injector_turnoff.cir Shs",
                     "Note": note,
                     "Vds": "150 V class against a 100 V rail that the "
                            "recirculation bump can push above setpoint"})
    sh.wire(dp[0], dp[1], dp[0], dp[1] - 14.0)
    sh.label("BOOST_100V", dp[0], dp[1] - 14.0)

    rail = Rail(sh, ry)
    rail.to(qx - 20.0)
    # Gate-SOURCE resistor, not gate-ground. See the sheet note.
    sh.place("Device:R", "R", qx - 20.0, (qy + ry) / 2.0, "470R",
             fields={"Source": "supervisor.cir claim 6, referenced to "
                               "SOURCE rather than to ground",
                     "Note": "Across gate and source, because the source "
                             "of a high-side N-FET swings to 100 V. Same "
                             "Miller-coupling divider supervisor.cir "
                             "sized; a pulldown to GROUND here would hold "
                             "Vgs at minus the source voltage and fight "
                             "the driver on every edge."})
    ra = pin_xy(*PINS["Device:R"]["1"], qx - 20.0, (qy + ry) / 2.0, 0)
    rb = pin_xy(*PINS["Device:R"]["2"], qx - 20.0, (qy + ry) / 2.0, 0)
    r_top, r_bot = (ra, rb) if ra[1] < rb[1] else (rb, ra)
    sh.wire(gp[0], gp[1], qx - 20.0, gp[1])
    sh.label(gate_name, qx - 20.0, gp[1])
    sh.wire(qx - 20.0, gp[1], r_top[0], r_top[1])
    sh.wire(r_bot[0], r_bot[1], qx - 20.0, ry)

    rx, ry2 = rail.to(sp[0], tap=True)
    sh.wire(sp[0], sp[1], sp[0], ry2)
    rail.to(sp[0] + 28.0, tap=True)
    diode_down(sh, sp[0] + 28.0, ry,
               "150V 20A ultrafast",
               {"Source": "settled on this sheet -- see the module "
                          "docstring",
                "Note": "Anode on the battery. Reverse biased while the "
                        "bank sits near 100 V; supplies the hold current "
                        "at 13.5 V once the high-side FET stops "
                        "conducting. Also the return path the coil needs "
                        "at full turn-off, which is the job "
                        "injector_turnoff.cir's D_fw does to ground."},
               "VBAT_PROT")
    rail.to(sp[0] + 60.0)
    sh.hlabel(out_net, sp[0] + 60.0, ry, shape="output")

    sh.hlabel(ctrl_net, ctrl_x, 62.0, shape="input")
    sh.wire(ctrl_x, 62.0, ctrl_x + 30.0, 62.0)
    sh.label(drv_in, ctrl_x + 30.0, 62.0)
    sh.text(f"bank {bank}", qx - 34.0, 70.0, size=1.6)


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
        "The two high sides cannot use it. The source of a high-side "
        "N-FET swings to the boost rail, so a pulldown to GROUND would "
        "hold Vgs at minus the source voltage and fight the\n"
        "driver on every edge, and a kill FET referenced to ground cannot "
        "short a gate that is floating 100 V up. What is drawn instead is "
        "the 470 ohm across GATE and SOURCE -- the\n"
        "same Miller-coupling divider supervisor.cir sized, just "
        "referenced to the terminal it has to be referenced to -- and the "
        "kill path moves into the driver: GATE_KILL must reach the\n"
        "high-side driver's own shutdown input. That is a REQUIREMENT ON "
        "THE UNCHOSEN PART, recorded against the driver rather than "
        "drawn, and it is the sixth finding of the shape this\n"
        "project keeps turning up: a document and an executable file "
        "agreeing with each other and both wrong about a case neither "
        "modelled.",
        40.0, 295.0, size=1.6)
    sh.text(
        "PARTS NOT CHOSEN ON THIS SHEET. Five gate drivers and two "
        "current-sense amplifiers, on the same named-net treatment "
        "power_input gives its two controller gates.\n"
        "\n"
        "  LOW-SIDE DRIVERS (LS1/LS2/LS3_DRV_IN -> *_GATE).  Output "
        "impedance <= 25 ohm, from supervisor.cir claim 2: the 470 ohm "
        "pulldown is not a perturbation on the driver, it is the\n"
        "  bottom half of a divider with it, and at 100 ohm the gate "
        "reaches 8.25 V instead of 10 V. 3.3 V logic in (PTC2/PTC3/PTB4, "
        "FTM0_CH2/3/4), ~10 V out.\n"
        "  HIGH-SIDE DRIVERS (HSA/HSB_DRV_IN -> HSA/HSB_GATE).  Same "
        "output impedance, but referenced to a source that swings to "
        "100 V, so bootstrapped or isolated, rated above the\n"
        "  rail, AND carrying a shutdown input for GATE_KILL per the note "
        "above. Supplied from VBAT_PROT and therefore rated for its "
        "73.3 V worst case.\n"
        "  CURRENT-SENSE AMPLIFIERS (ISNS_INJ_A/B_SENSE -> PTC15 / "
        "PTD19).  Ground-referenced -- that is the whole reason the "
        "shunts went low-side -- gain about 33 to put 90 mV at\n"
        "  full scale near 3.0 V, and bandwidth enough to resolve a 38 us "
        "ramp to peak, so 100 kHz or better. A Kelvin tap at the shunt "
        "pad, not a via into the ground pour: 90 mV sits\n"
        "  on a return carrying 18 A and a few milliohms of pour between "
        "pad and reference is the whole signal.",
        40.0, 352.0, size=1.6)
    sh.text(
        "THE BOOST CONVERTER ITSELF IS NOT DRAWN. boost_converter.cir "
        "models it as an average charging current and says so: 'no "
        "inductor, no switch, no control loop.' That is enough to\n"
        "size the reservoir and it is not enough to draw a converter, so "
        "what is on this sheet is the part the block DID size -- the "
        "47 uF reservoir, its 150 V class, and the bleed -- with\n"
        "VBAT_PROT and BOOST_100V naming the two ends of the stage "
        "nobody has chosen. What it has to do: 50 mA average from "
        "VBAT_PROT into a 100 V setpoint, which recovers the\n"
        "7.3 V peak-phase droop in 6.8 ms against the 26.67 ms between "
        "cylinders at 1500 rpm.",
        40.0, 400.0, size=1.6)


def build():
    schlib.verify_pins()
    sh = Sheet("Injector drive: boost rail, high sides, low sides",
               paper="A2",
               comments=[
                   "Generated by hw/gen_sheet_injector.py -- do not hand-edit until it is retired",
                   "boost_converter.cir / injector_boost.cir / injector_turnoff.cir",
                   "Hold current arrives through a battery DIODE-OR, not a second switched rail",
                   "Shunts settled LOW-SIDE and per-bank -- docs/pinmap.md 1.6 asked for the placement",
               ],
               ref_base=schlib.REF_BASE["injector"])
    boost_rail(sh)

    high_side(sh, 210.0, "A (cyl 1+3)", "INJ_HS_A", "INJ_A_03", "HSA_GATE",
              "HSA_DRV_IN", 150.0,
              "Bank-shared: cylinders 1 and 3 fire 240 crank degrees "
              "apart and never overlap, which is what lets one switch "
              "serve both.")
    high_side(sh, 420.0, "B (cyl 2)", "INJ_HS_B", "INJ_B_05", "HSB_GATE",
              "HSB_DRV_IN", 360.0,
              "One cylinder in this bank. Kept as a separate switch "
              "rather than merged, because merging would put all three "
              "injectors behind one failure.")

    sh.text("GATE_KILL reaches the two high sides through the driver's "
            "own SHUTDOWN input, not through a clamp -- a ground-"
            "referenced kill FET cannot short a gate\n"
            "that floats 100 V up. Nothing is drawn for it here because "
            "the driver is not chosen; see the note at the foot of the "
            "sheet.", 150.0, 128.0, size=1.6)

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
