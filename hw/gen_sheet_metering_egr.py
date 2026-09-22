#!/usr/bin/env python3
"""metering_egr sheet: the fuel metering unit low side, and the EGR bridge.

ONE HALF IS DRAWN AND ONE IS BLOCKED, and the reason is worth reading
before the schematic.

The metering unit is a discrete low-side N-FET on ECU pin 88's return,
with the 50 mOhm shunt that metering_unit_pwm.cir's closed-loop finding
put there, a freewheel diode, and the fail-safe gate network
supervisor.cir sized. Every one of those is specified. The only open item
is the gate driver itself, left on a named net the way power_input leaves
its two controller gates.

The EGR bridge is NOT drawn. It lost its candidate part on 20 Sep 2026
while this sheet was being laid out:

  TI DRV8873-Q1 is an automotive H-bridge with exactly the PH/EN decoded
  interface bom_requirements' EGR-DRIVER tag asks for -- one input pair
  that cannot express both legs of a diagonal conducting at once, which
  is the whole requirement egr_hbridge.cir's 270 A shoot-through
  produced. It is AEC-Q100 grade 1, 10 A peak, with per-half-bridge
  current sense on IPROPI1/IPROPI2 that would have fed PTD22 directly.

  Its VM absolute maximum is 40 V (SLVSDY7B sec.6.1).

  VBAT_PROT reaches 40.0 V for 400 ms on a suppressed load dump and
  73.3 V for about 50 us on ISO 7637-2 pulse 2a. An absolute maximum is
  absolute: the part is out of spec at the dump with zero margin, and at
  2a by 1.8x.

That is not a fact about one part. It is a fact about the rail, and it
applies to the injector high sides, the relay drivers and this bridge
alike -- which is why transient_clamp.cir now carries the rating as
enforced checks rather than as a sentence in a comment. The practical
consequence is that integrated automotive H-bridges and smart switches,
which cap out at 40-45 V as a class, are excluded from anything
battery-connected on this board. The EGR bridge goes discrete for the
same reason memo 12 sent the injector drivers discrete.

What it now needs is a bridge GATE DRIVER rated above 73.3 V that still
decodes DIR/PWM internally. No such part has been checked against a
retrieved datasheet, and this project does not guess parts into copper.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import schlib
from schlib import Sheet, Rail, pin_xy, r2, PINS

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "metering_egr.kicad_sch")
ICPINS = json.load(open(os.path.join(HW, "lib", "ic_pins.json")))
GND_DROP = 7.62
QP = PINS["Device:Q_NMOS_GSD"]


def gnd_below(sh, x, y):
    sh.wire(x, y, x, y + GND_DROP)
    sh.gnd(x, y + GND_DROP)


def metering(sh):
    """Pin 88's low side: FET, freewheel, shunt, and the fail-safe gate."""
    dy = 110.0          # drain rail -- the coil's return
    sy = 150.0          # source node, above the shunt

    # ---- the coil, off-sheet: one end on fused battery, one end here ----
    sh.hlabel("MU_RETURN", 40.0, dy, shape="output")
    drain = Rail(sh, dy)
    drain.to(40.0)

    # Freewheel. Same argument as the relay driver: interrupting ~1.35 A
    # in 30 mH with no path destroys the switch. Here it also sets how
    # fast current decays in the off-time, and so sets the ripple.
    fx = 80.0
    sh.place("Device:D", "D", fx, dy - 20.0, "100V 3A fast",
             rot=270,
             fields={"Source": "metering_unit_pwm.cir DFW",
                     "Note": "Cathode to battery, anode to the drain. "
                             "Sets the off-time decay, and with it the "
                             "ripple -- not just a protection part.",
                     "Vr": "100 V class, per transient_clamp's rail rating"})
    da = pin_xy(*PINS["Device:D"]["1"], fx, dy - 20.0, 270)
    db = pin_xy(*PINS["Device:D"]["2"], fx, dy - 20.0, 270)
    d_lo, d_hi = (da, db) if da[1] > db[1] else (db, da)
    rx, ry = drain.to(fx, tap=True)
    sh.wire(rx, ry, d_lo[0], d_lo[1])
    sh.wire(d_hi[0], d_hi[1], d_hi[0], d_hi[1] - 10.16)
    sh.hlabel("VBAT_PROT", d_hi[0], d_hi[1] - 10.16, shape="input", rot=90)

    # ---- the switch ----
    # rot=0, not 270: at 270 the drain and source sit side by side and
    # every wire to a rail above or below comes out DIAGONAL. The page
    # plotted that way from 20 Sep until the injector sheet found the
    # same bug; the netlist was always right, the drawing was not.
    qx = 127.46
    drain.to(qx + 2.54)
    sh.place("Device:Q_NMOS_GSD", "Q", qx, dy + 20.0, "100V logic-level N-ch",
             rot=0,
             fields={"Source": "metering_unit_pwm.cir NSW (Ron 25 mOhm); "
                               "rail class from transient_clamp.cir",
                     "Note": "100 V class because it sits on VBAT_PROT, "
                             "which reaches 73.3 V on ISO 7637-2 pulse 2a",
                     "Rds_on": "25 mOhm modelled"})
    # rot 0: drain up, source down, gate to the left.
    qd = pin_xy(*QP["3"], qx, dy + 20.0, 0)
    qs = pin_xy(*QP["2"], qx, dy + 20.0, 0)
    qg = pin_xy(*QP["1"], qx, dy + 20.0, 0)
    sh.wire(qd[0], dy, qd[0], qd[1])
    src = Rail(sh, qs[1])
    src.to(qs[0])

    # ---- the sense shunt: a schematic part, not a firmware detail ----
    shx = qs[0]
    sh.place("Device:R", "R", shx, qs[1] + 20.0, "50mOhm 1%",
             fields={"Source": "bom_requirements MU-ISENSE; "
                               "metering_unit_pwm.cir Rsh4",
                     "Note": "33.75 mV at the 0.675 A setpoint -- too small "
                             "for the S32K148 ADC at useful resolution, so "
                             "the amplifier below is not optional",
                     "Power": "0.675 A^2 * 50 mOhm = 23 mW nominal"})
    sa = pin_xy(*PINS["Device:R"]["1"], shx, qs[1] + 20.0, 0)
    sb = pin_xy(*PINS["Device:R"]["2"], shx, qs[1] + 20.0, 0)
    s_top, s_bot = (sa, sb) if sa[1] < sb[1] else (sb, sa)
    sh.wire(qs[0], qs[1], s_top[0], s_top[1])
    gnd_below(sh, s_bot[0], s_bot[1])
    # The amplifier senses ACROSS the shunt. Its low reference is the
    # shunt's own ground pad, which is electrically GND -- so it is not a
    # separate net and is not drawn as one. What it IS is a layout
    # constraint: a Kelvin tap at the pad, not a via into the ground
    # pour, because 33.75 mV sits on a return carrying up to 1.35 A and a
    # few milliohms of pour between the pad and the amplifier's reference
    # is the whole signal.
    sh.wire(s_top[0], s_top[1], s_top[0] + 25.4, s_top[1])
    sh.label("ISNS_MU_SENSE", s_top[0] + 25.4, s_top[1])
    sense_amp(sh, 222.0, s_top[1] + 4.0, "ISNS_MU_SENSE", "ISNS_MU",
              "50 mOhm x 0.675 A x 20 = 675 mV at the setpoint, 844 ADC counts. Same part and gain as the injector channels, so the board carries one sense-amp part number. -> PTC16 (ADC0_SE14).")

    # ---- the fail-safe gate network ----
    # supervisor.cir sized this: 470 ohm is the largest standard pulldown
    # that still holds the gate below Vgs(th) = 1.0 V against Miller
    # coupling at Crss = 500 pF. 10k -- the value normally reached for --
    # fails even at the low end of the memo's own Crss envelope.
    gx = qg[0] - 20.32
    sh.wire(qg[0], qg[1], gx, qg[1])
    sh.label("MU_GATE", gx, qg[1], rot=180)

    px = gx - 15.24
    sh.place("Device:R", "R", px, qg[1] + 18.0, "470R",
             fields={"Source": "supervisor.cir claim 6; bom_requirements "
                               "GATE-PULLDOWN",
                     "Note": "Largest standard value holding the gate under "
                             "Vgs(th)=1.0 V at Crss=500 pF. 10k fails even "
                             "at the low end of memo 11's own envelope.",
                     "Cost": "21.3 mA per gate at 10 V; 1.28 W across all six"})
    pa = pin_xy(*PINS["Device:R"]["1"], px, qg[1] + 18.0, 0)
    pb = pin_xy(*PINS["Device:R"]["2"], px, qg[1] + 18.0, 0)
    p_top, p_bot = (pa, pb) if pa[1] < pb[1] else (pb, pa)
    sh.wire(px, qg[1], p_top[0], p_top[1])
    sh.label("MU_GATE", px, qg[1], rot=180)
    gnd_below(sh, p_bot[0], p_bot[1])

    # The kill transistor, in parallel with the pulldown. GATE_KILL comes
    # from the supervisor's inverting stage on the mcu sheet and is
    # asserted HIGH on fault, so this FET shorts the gate to source
    # without any MCU involvement at all -- that is what lets it work
    # against a hung MCU rather than only a reset one.
    kx = px - 28.0
    sh.place("Device:Q_NMOS_GSD", "Q", kx, qg[1] + 18.0, "60V small-signal",
             fields={"Source": "supervisor.cir -- the kill FET; memo 11 "
                               "'Recommendation: the circuit to build'",
                     "Note": "In parallel with the 470 ohm pulldown, not "
                             "instead of it. Ron 5 ohm dominates the "
                             "pulldown by ~2000x, which is why the modelled "
                             "kill time is 23 ns."})
    kd = pin_xy(*QP["3"], kx, qg[1] + 18.0, 0)
    ks = pin_xy(*QP["2"], kx, qg[1] + 18.0, 0)
    kg = pin_xy(*QP["1"], kx, qg[1] + 18.0, 0)
    sh.wire(kd[0], kd[1], kd[0], qg[1])
    sh.label("MU_GATE", kd[0], qg[1], rot=180)
    gnd_below(sh, ks[0], ks[1])
    sh.wire(kg[0], kg[1], kg[0] - 15.24, kg[1])
    sh.hlabel("GATE_KILL", kg[0] - 15.24, kg[1], shape="input", rot=180)

    # ---- what drives the gate ----------------------------------------
    # AUIRS2181S, chosen 21 Sep 2026 for the injector stage and used here
    # for its LOW side only, so the whole board carries one gate-driver
    # part number. The high side is tied off: HIN low, VS to COM, VB to
    # VCC, HO unconnected.
    sh.hlabel("MU_PWM", 40.0, 235.0, shape="input")
    sh.wire(40.0, 235.0, 62.0, 235.0)
    sh.label("MU_DRV_IN", 62.0, 235.0)

    dx, dy = 250.0, 222.0
    sh.place("ecu25kva:AUIRS2181S", "U", dx, dy, "AUIRS2181S",
             footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
             fields={"Source": "Infineon AUIRS2181(4)S datasheet",
                     "Note": "LOW side only. The same part as the four "
                             "injector drivers, so the board carries one "
                             "gate-driver part number rather than two.",
                     "Rout": "~8-11 ohm from the datasheet's 1.4/1.8 A "
                             "minimum short-circuit current at 15 V -- "
                             "inside supervisor.cir claim 2's 25 ohm "
                             "ceiling, so the 470 ohm pulldown takes the "
                             "gate to 11.7 V rather than dividing it down"})

    def dpin(n):
        dxy = ICPINS["AUIRS2181S"][n]
        return pin_xy(dxy[0], dxy[1], dx, dy, 0)

    def dstub(n, ddx, name):
        pp = dpin(n)
        sh.wire(pp[0], pp[1], pp[0] + ddx, pp[1])
        sh.label(name, pp[0] + ddx, pp[1], rot=180 if ddx < 0 else 0)

    dstub("2", -14.0, "MU_DRV_IN")
    dstub("4", 14.0, "MU_GATE")
    dstub("5", -22.0, "12V_GATE")
    dstub("8", 14.0, "12V_GATE")
    for n, ddx in (("1", -8.0), ("3", -30.0)):
        pp = dpin(n)
        sh.wire(pp[0], pp[1], pp[0] + ddx, pp[1])
        gnd_below(sh, pp[0] + ddx, pp[1])
    pp = dpin("6")
    sh.wire(pp[0], pp[1], pp[0] + 22.0, pp[1])
    gnd_below(sh, pp[0] + 22.0, pp[1])

    # 12V_GATE arrives from the injector sheet, where it is made from the
    # boost rail so it survives cranking.
    # One hierarchical label on the bypass stub. A stub from the
    # hierarchical label to a differently-named local one would only be
    # an alias -- the injector sheet's GATE_KILL/HS_DRV_SD lesson -- and
    # the local "12V_GATE" labels on the driver pins merge with this by
    # name.
    crail = Rail(sh, 272.0)
    sh.wire(240.0, 266.0, 240.0, 272.0)
    sh.hlabel("12V_GATE", 240.0, 266.0, shape="input", rot=90)
    crail.to(240.0)
    sh.place("Device:C", "C", 240.0, 286.0, "1uF 25V",
             fields={"Note": "VCC bypass at the driver pin."})
    ca = pin_xy(*PINS["Device:C"]["1"], 240.0, 286.0, 0)
    cb = pin_xy(*PINS["Device:C"]["2"], 240.0, 286.0, 0)
    c_top, c_bot = (ca, cb) if ca[1] < cb[1] else (cb, ca)
    sh.wire(240.0, 272.0, c_top[0], c_top[1])
    gnd_below(sh, c_bot[0], c_bot[1])
    sh.text(
        "MU_GATE IS DRIVEN BY AN AUIRS2181S, low side only -- the same "
        "part as the four injector drivers, so the board carries one "
        "gate-driver part number. What it had to be, from\n"
        "supervisor.cir claim 2: output impedance <= 25 ohm, because the "
        "470 ohm pulldown is the bottom half of a divider with it. The "
        "datasheet's 1.4/1.8 A minimum short-circuit\n"
        "current at 15 V puts it at roughly 8-11 ohm, so the gate "
        "reaches 11.7 V rather than being divided down. VCC is 12V_GATE, "
        "made on the injector sheet from the boost\n"
        "rail so that it survives cranking.",
        40.0, 255.0, size=1.5)
    sh.text(
        "ISNS_MU_SENSE goes to a current-sense amplifier, also not chosen. "
        "50 mOhm at the 0.675 A setpoint is 33.75 mV, measured ACROSS the "
        "shunt -- the\n"
        "amplifier's low reference is the shunt's own ground pad, which is "
        "electrically GND and so is not a separate net. It IS a layout "
        "constraint: a Kelvin tap\n"
        "at the pad, not a via into the ground pour, because 33.75 mV sits "
        "on a return carrying up to 1.35 A and a few milliohms of pour "
        "between pad and\n"
        "reference is the whole signal.\n"
        "Output goes to PTC16 (ADC0_SE14). The loop is closed in firmware: "
        "PTD10 carries the PWM, PTC16 reads the current back. That is "
        "arrangement the pin map\n"
        "already assumes, and it is why metering_unit_pwm.cir models the "
        "regulator as hysteretic rather than as a fixed duty.",
        40.0, 300.0, size=1.5)


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


def egr_blocked(sh):
    """The EGR half, and why there is nothing drawn in it yet."""
    sh.text(
        "EGR BRIDGE -- NOT DRAWN. Blocked 20 Sep 2026 on a rail rating, "
        "not on a missing idea.",
        320.0, 70.0, size=2.2)
    sh.text(
        "TI DRV8873-Q1 was the candidate and it fits the functional "
        "requirement exactly: an automotive H-bridge with the PH/EN "
        "decoded interface\n"
        "bom_requirements' EGR-DRIVER tag asks for -- one input pair that "
        "cannot express both legs of a diagonal conducting at once, which "
        "is the\n"
        "requirement egr_hbridge.cir's 270 A shoot-through produced. "
        "AEC-Q100 grade 1, 10 A peak, per-half-bridge current sense on "
        "IPROPI1/IPROPI2\n"
        "that would have fed PTD22 directly.\n"
        "\n"
        "Its VM absolute maximum is 40 V (SLVSDY7B sec.6.1).\n"
        "\n"
        "VBAT_PROT reaches 40.0 V for 400 ms on a suppressed load dump and "
        "73.3 V for about 50 us on ISO 7637-2 pulse 2a. An absolute "
        "maximum is\n"
        "absolute: out of spec at the dump with zero margin, and at 2a by "
        "1.8x.\n"
        "\n"
        "THIS IS A FACT ABOUT THE RAIL, NOT ABOUT ONE PART. It applies to "
        "the injector high sides, the relay drivers and this bridge alike. "
        "transient_clamp.cir\n"
        "now carries it as enforced checks rather than as a sentence in a "
        "comment, so the next driver sheet fails the suite instead of "
        "rediscovering it.\n"
        "\n"
        "Consequence: integrated automotive H-bridges and smart switches "
        "cap out at 40-45 V as a class and are excluded from anything "
        "battery-connected\n"
        "here. The EGR bridge goes discrete, for the same reason memo 12 "
        "sent the injector drivers discrete. What it needs is a bridge "
        "GATE DRIVER rated\n"
        "above 73.3 V that still decodes DIR/PWM internally. No such part "
        "has been checked against a retrieved datasheet, and this project "
        "does not guess\n"
        "parts into copper.\n"
        "\n"
        "Unblocked by: one datasheet. The four bridge FETs, the shunt, the "
        "gate pulldowns and the kill transistors are all already specified "
        "and will draw\n"
        "the same way the metering unit's do on the left of this sheet.",
        # KiCad centres a multi-line text block VERTICALLY on its anchor,
        # so a twenty-line block reaches ten lines above this y as well as
        # ten below. The heading above sat inside it before that was
        # noticed.
        320.0, 135.0, size=1.5)


def build():
    schlib.verify_pins()
    sh = Sheet("Fuel metering unit and EGR actuator", paper="A2",
               comments=[
                   "Generated by hw/gen_sheet_metering_egr.py -- do not hand-edit until it is retired",
                   "Metering unit: metering_unit_pwm.cir + bom_requirements MU-ISENSE, GATE-PULLDOWN",
                   "EGR half NOT drawn -- blocked on a battery-rail rating, see the note",
                   "Nothing battery-connected on this board may be rated below 80 V",
               ],
               ref_base=schlib.REF_BASE["metering_egr"])
    metering(sh)
    egr_blocked(sh)
    return sh


if __name__ == "__main__":
    print(build().write(OUT, force="--force" in sys.argv))
