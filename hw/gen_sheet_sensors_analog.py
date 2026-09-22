#!/usr/bin/env python3
"""sensors_analog sheet: the eight analog channels and the two battery rails.

Four blocks back this sheet: battery_sense.cir, sensor_ratiometric.cir,
sensor_differential.cir, ntc_frontend.cir.

Every channel ends the same way -- a 22 nF filter and a 3.3 V zener at
the MCU pin -- because every channel arrives from the harness and the
S32K148's ADC input is the thing being protected. What differs is the
front end, and the difference is not cosmetic:

  DIVIDER        battery rails. 120k/10k puts 40 V at 3.077 V, inside
                 VREFH. The 75k/10k the earlier artifacts used reaches
                 4.7 V at the same input, which is over range -- it is
                 drawn in battery_sense.cir as the rejected version.

  RATIOMETRIC    rail pressure, which has its own dedicated sensor
                 ground. 10k/16k scales a 0-5 V sensor to 0-3.077 V.

  DIFFERENTIAL   every channel that SHARES a sensor ground return with
                 another sensor. sensor_differential.cir is the argument
                 for it: with 20 mA down a 1 ohm corroded return, a
                 single-ended reading is wrong by the whole ground
                 offset while a differential one rejects it. The ratio
                 measured there is 90x.

THE DIFFERENCE AMPLIFIERS ARE TI INA592, chosen 22 Sep 2026, in their
native G = 1/2 configuration. They replace an OPAMP_GENERIC placeholder
and a discrete 26k/16k network that could not meet the requirement:
sensor_differential.cir's own tolerance note tried the argument down to
60 dB CMRR, and 0.1% discrete resistors give about 48 dB. The INA592's
matched network is on-die, 88 dB minimum. With that figure in the block
instead of an inferred 80 dB, the differential front-end beats
single-ended by 394x referred to the sensor, up from 90x.

Not AEC-Q100 -- no qualified difference amplifier with a differential
G = 1/2 turned up -- and that is recorded on each part.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import schlib
from schlib import Sheet, Rail, pin_xy, PINS

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "sensors_analog.kicad_sch")
ICPINS = json.load(open(os.path.join(HW, "lib", "ic_pins.json")))
GND_DROP = 7.62


def ic_pin(part, num, x, y):
    dx, dy = ICPINS[part][str(num)]
    return pin_xy(dx, dy, x, y, 0)


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


def adc_tail(sh, node, x, y, out_net):
    """The 22 nF + 3.3 V zener every channel ends with."""
    vshunt(sh, "Device:C", "C", x, y + 18.0, "22nF",
           {"Source": "sensor_ratiometric.cir C1",
            "Note": "With the 16k below it, 0.35 ms -- fast against the "
                    "engine and slow against anything the harness picks up"},
           node)
    vshunt(sh, "Device:D_Zener", "D", x + 16.0, y + 18.0, "3.3V",
           {"Source": "sensor_ratiometric.cir D1",
            "Note": "Cathode to the signal. The ADC pin is what is being "
                    "protected; everything on this sheet arrives from the "
                    "harness."},
           node, rot=270)
    node.to(x + 38.0)
    sh.hlabel(out_net, x + 38.0, y, shape="output")


def divider_channel(sh, x0, y, in_net, out_net, rtop, rbot, label, src):
    """A resistive divider straight off a harness line."""
    sh.text(label, x0, y - 9.0, size=1.6)
    sh.hlabel(in_net, x0, y, shape="input")
    chain = Rail(sh, y)
    chain.to(x0)
    sx = x0 + 30.0
    sh.place("Device:R", "R", sx, y, rtop, rot=90,
             fields={"Source": src,
                     "Note": "120k/10k puts 40 V at 3.077 V, inside VREFH. "
                             "The 75k/10k version reaches 4.7 V at the same "
                             "input -- battery_sense.cir draws it as the "
                             "rejected one."})
    ra = pin_xy(*PINS["Device:R"]["1"], sx, y, 90)
    rb = pin_xy(*PINS["Device:R"]["2"], sx, y, 90)
    r_in, r_out = (ra, rb) if ra[0] < rb[0] else (rb, ra)
    chain.to(r_in[0])
    node = Rail(sh, y)
    node.to(r_out[0])
    vshunt(sh, "Device:R", "R", x0 + 50.0, y + 18.0, rbot,
           {"Source": src}, node)
    adc_tail(sh, node, x0 + 66.0, y, out_net)


def ratiometric_channel(sh, x0, y, in_net, out_net, label):
    """0-5 V sensor with its own dedicated ground return."""
    sh.text(label, x0, y - 9.0, size=1.6)
    sh.hlabel(in_net, x0, y, shape="input")
    chain = Rail(sh, y)
    chain.to(x0)
    sx = x0 + 30.0
    sh.place("Device:R", "R", sx, y, "10k", rot=90,
             fields={"Source": "sensor_ratiometric.cir R1",
                     "Note": "10k/16k scales 0-5 V to 0-3.077 V. Firmware "
                             "divides out the measured rail (SENSOR_5V_MON) "
                             "so sensor drift and rail drift cancel."})
    ra = pin_xy(*PINS["Device:R"]["1"], sx, y, 90)
    rb = pin_xy(*PINS["Device:R"]["2"], sx, y, 90)
    r_in, r_out = (ra, rb) if ra[0] < rb[0] else (rb, ra)
    chain.to(r_in[0])
    node = Rail(sh, y)
    node.to(r_out[0])
    vshunt(sh, "Device:R", "R", x0 + 50.0, y + 18.0, "16k",
           {"Source": "sensor_ratiometric.cir R2"}, node)
    adc_tail(sh, node, x0 + 66.0, y, out_net)


def differential_channel(sh, x0, y, sig_net, gnd_net, out_net, label, note):
    """INA592 difference amplifier, G = 1/2, chosen 22 Sep 2026.

    Replaces an OPAMP_GENERIC placeholder and a discrete 26k/16k network
    that the sheet's own note said could not reach the requirement: 60 dB
    CMRR is the floor sensor_differential.cir tried, and 0.1% discrete
    resistors give about 48 dB. The matched network is now on-die --
    88 dB minimum -- and the gain is the part's native 1/2, which puts a
    0.5-4.5 V sensor at 0.25-2.25 V, inside VREFH.

    A 1k between the amplifier and the ADC tail, which the old design
    did not have: the amplifier runs from 5 V and can swing to 4.78 V on
    a harness fault, and the 3.3 V zener at the pin then conducts
    (4.78 - 3.3) / 1k = 1.5 mA instead of the amplifier's full short-
    circuit current.
    """
    sh.text(label, x0, y - 34.0, size=1.6)
    ux, uy = x0 + 60.0, y

    def p(n):
        return ic_pin("INA592", n, ux, uy)

    sh.place("ecu25kva:INA592", "U", ux, uy, "INA592",
             footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
             fields={"Source": "TI SBOS914F; sensor_differential.cir Bd",
                     "Note": note,
                     "CMRR": "88 dB min at G = 1/2, against a 60 dB floor",
                     "Qualification": "NOT AEC-Q100 -- no qualified "
                                      "difference amplifier with a "
                                      "differential G = 1/2 was found"})
    ip, im = p(3), p(2)
    sh.hlabel(sig_net, x0, ip[1], shape="input")
    sh.wire(x0, ip[1], ip[0], ip[1])
    sh.hlabel(gnd_net, x0, im[1], shape="input")
    sh.wire(x0, im[1], im[0], im[1])
    for n in (4, 1):
        q = p(n)
        gnd_below(sh, q[0], q[1])
    vp = p(7)
    sh.wire(vp[0], vp[1], vp[0], vp[1] - 6.0)
    sh.hlabel("5V_MAIN", vp[0], vp[1] - 6.0, shape="input", rot=90)

    # OUT and SENSE join -- the G = 1/2 configuration.
    op, sp = p(6), p(5)
    jx = op[0] + 6.0
    node = Rail(sh, op[1])
    node.to(op[0])
    node.to(jx, tap=True)
    sh.wire(sp[0], sp[1], jx, sp[1])
    sh.wire(jx, sp[1], jx, op[1])
    rx = op[0] + 22.0
    sh.place("Device:R", "R", rx, op[1], "1k", rot=90,
             fields={"Note": "Limits the pin zener to 1.5 mA if the "
                             "amplifier rails at 4.78 V on a harness fault."})
    a = pin_xy(*PINS["Device:R"]["1"], rx, op[1], 90)
    b = pin_xy(*PINS["Device:R"]["2"], rx, op[1], 90)
    l, r = (a, b) if a[0] < b[0] else (b, a)
    node.to(l[0])
    tail = Rail(sh, op[1])
    tail.to(r[0])
    adc_tail(sh, tail, rx + 18.0, op[1], out_net)

    # Supply bypass, below and clear of every signal wire.
    cx = op[0] + 14.0
    sh.wire(cx, uy + 8.0, cx, uy + 12.19)
    sh.label("5V_MAIN", cx, uy + 8.0, rot=90)
    sh.place("Device:C", "C", cx, uy + 16.0, "100nF",
             fields={"Note": "At V+. Found missing on the old op-amps by "
                             "check_netlist.py's decoupling audit."})
    gnd_below(sh, cx, uy + 19.81)


def excitation(sh):
    """5V_SENSOR leaves this board on five connector pins."""
    y = 300.0
    sh.text("5V_SENSOR excitation -- three PTC-protected groups from the "
            "rails sheet, out to five connector pins", 40.0, y - 10.0,
            size=1.6)
    groups = [("5V_SENSOR_A", ["EXC_BOOST_11", "EXC_EGR_15"]),
              ("5V_SENSOR_B", ["EXC_OIL_39", "EXC_RAIL_32"]),
              ("5V_SENSOR_C", ["EXC_CAM_45"])]
    x = 40.0
    for grp, pins in groups:
        sh.hlabel(grp, x, y, shape="input")
        rail = Rail(sh, y)
        rail.to(x)
        for i, pin in enumerate(pins):
            rail.to(x + 30.0 + i * 34.0, tap=(i < len(pins) - 1))
            sh.hlabel(pin, x + 30.0 + i * 34.0, y, shape="output")
        x += 130.0


def baro(sh):
    """Onboard barometric sensor, spec sec.7 deviation #2 -- on purpose.

    "Added on-PCB behind a vented port; costs nothing in harness terms
    and improves fuelling correction." NXP MPXHZ6115A, 15-115 kPa,
    VOUT = VS x (0.009 x P - 0.095). Supplied from 5V_MAIN, which
    SENSOR_5V_MON already measures, so the reading is ratiometric-
    correctable with no new channel: sea level (101.3 kPa) reads 4.08 V at
    the sensor and 2.51 V at the pin, 2000 m (80 kPa) 1.92 V.

    No zener at the MCU pin, unlike every other channel on this sheet:
    those arrive from the harness, this never leaves the board, and 10k/16k
    holds even a 5.25 V supply's full-scale output to 3.10 V.
    """
    sx, sy = 190.0, 100.0
    sh.text("BARO -- onboard, spec sec.7 deviation #2. NXP MPXHZ6115A "
            "behind a vented port -> PTD18 (ADC1_SE16)", 160.0, 64.0,
            size=1.6)
    geom = ICPINS["MPXHZ6115A"]

    def p(n):
        return pin_xy(geom[n][0], geom[n][1], sx, sy, 0)

    sh.place("ecu25kva:MPXHZ6115A", "U", sx, sy, "MPXHZ6115A",
             footprint="Sensor_Pressure:Freescale_98ARH99066A",
             fields={"Source": "NXP MPXA6115A series data sheet Rev. 7.3 "
                               "-- Table 1 pins, Figure 6 transfer function",
                     "Note": "Needs a VENTED PORT in the enclosure -- a "
                             "mechanical requirement, not a schematic one. "
                             "Media-resistant gel (Z) variant.",
                     "Qualification": "AEC-Q100 NOT stated in the retrieved "
                                      "datasheet. Infineon KP236 is listed "
                                      "automotive-qualified (40-115 kPa) but "
                                      "its datasheet did not resolve; it is "
                                      "a footprint change, not a drop-in."})
    vs = p("2")
    sh.wire(vs[0], vs[1], vs[0], vs[1] - 6.0)
    sh.label("5V_MAIN", vs[0], vs[1] - 6.0, rot=90)
    g = p("3")
    gnd_below(sh, g[0], g[1])
    # Bypass, per the datasheet's own Figure 1.
    sh.wire(sx - 20.0, sy - 20.0, sx - 20.0, sy - 26.0)
    sh.label("5V_MAIN", sx - 20.0, sy - 26.0, rot=90)
    sh.place("Device:C", "C", sx - 20.0, sy - 14.0, "100nF",
             fields={"Source": "MPXA6115A data sheet Figure 1"})
    ca = pin_xy(*PINS["Device:C"]["1"], sx - 20.0, sy - 14.0, 0)
    cb = pin_xy(*PINS["Device:C"]["2"], sx - 20.0, sy - 14.0, 0)
    ct, cbo = (ca, cb) if ca[1] < cb[1] else (cb, ca)
    sh.wire(sx - 20.0, sy - 20.0, ct[0], ct[1])
    gnd_below(sh, cbo[0], cbo[1])

    vo = p("4")
    chain = Rail(sh, vo[1])
    chain.to(vo[0])
    rx = vo[0] + 18.0
    sh.place("Device:R", "R", rx, vo[1], "10k", rot=90,
             fields={"Note": "10k/16k, the same ratio every 5 V channel on "
                             "this sheet uses. Loads the sensor 0.18 mA "
                             "against its 0.5 mA source rating."})
    a = pin_xy(*PINS["Device:R"]["1"], rx, vo[1], 90)
    b = pin_xy(*PINS["Device:R"]["2"], rx, vo[1], 90)
    l, r = (a, b) if a[0] < b[0] else (b, a)
    chain.to(l[0])
    node = Rail(sh, vo[1])
    node.to(r[0])
    vshunt(sh, "Device:R", "R", rx + 20.0, vo[1] + 18.0, "16k",
           {"Note": "Bottom of the divider."}, node)
    vshunt(sh, "Device:C", "C", rx + 38.0, vo[1] + 18.0, "22nF",
           {"Note": "With 6.15k Thevenin, 1.2 kHz -- the sensor's own "
                    "response time is 1 ms and ambient pressure moves in "
                    "minutes."}, node)
    node.to(rx + 58.0)
    sh.hlabel("BARO", rx + 58.0, vo[1], shape="output")


def notes(sh):
    sh.text(
        "WHY FIVE CHANNELS ARE DIFFERENTIAL AND ONE IS NOT. The split "
        "follows the harness, not the sensor. Boost pressure and coolant "
        "temperature SHARE connector pin 34\n"
        "as their return; EGR position and oil pressure share pin 36. Rail "
        "pressure has pin 08 to itself. A shared return carries both "
        "sensors' current, so its own resistance\n"
        "appears as an offset on both readings -- sensor_differential.cir "
        "puts 20 mA down a 1 ohm corroded return and measures a "
        "single-ended reading wrong by the whole\n"
        "offset while the differential one rejects it, a ratio of 90x. A "
        "dedicated return does not have that problem, so rail pressure "
        "gets the simpler front end.\n"
        "\n"
        "The block states the consequence as a harness requirement, which "
        "is the useful form: single-ended is only acceptable if contact "
        "resistance is maintained below a\n"
        "figure nobody is going to maintain over a genset's life in an "
        "Indian monsoon.",
        40.0, 340.0, size=1.6)
    sh.text(
        "DIFFERENCE AMPLIFIERS: TI INA592 at its native G = 1/2, chosen "
        "22 Sep 2026. The requirement was >=60 dB CMRR -- the floor "
        "sensor_differential.cir tried -- and 0.1% discrete\n"
        "resistors give about 48 dB, so the network had to be matched "
        "on-die: 88 dB minimum. G = 1/2 puts a 0.5-4.5 V sensor at "
        "0.25-2.25 V; output reaches within 220 mV of\n"
        "each rail. A 1k before each ADC tail limits the pin zener to "
        "1.5 mA if an amplifier rails on a harness fault. NOT AEC-Q100: "
        "no qualified G = 1/2 difference amplifier\n"
        "was found, and INA2132's 'G = 1/2' is a single-ended "
        "attenuator, not a difference stage.\n"
        "\n"
        "BOOST TEMPERATURE (PTA3, connector pin 79) is drawn differential "
        "like its neighbours, but U2 is still open: whether that element "
        "is a ratiometric sensor or a bare\n"
        "NTC is unmeasured. ntc_frontend.cir already chose between the two "
        "NTC options if it turns out to be one -- a 2.2k pull-up to 5 V, "
        "not a 100 uA current source,\n"
        "because the source needs 5.9 V of compliance at -40 C and the "
        "rail is 5 V. That is a populate-time change to this channel, not "
        "a redesign.\n"
        "\n"
        "BARO (PTD18) is drawn: NXP MPXHZ6115A, spec sec.7 deviation #2, "
        "on-PCB behind a vented port. AEC-Q100 is not stated in its "
        "retrieved datasheet; Infineon KP236 is the\n"
        "qualified alternative whose datasheet did not resolve -- a "
        "footprint change if chosen.",
        40.0, 390.0, size=1.6)


def build():
    schlib.verify_pins()
    sh = Sheet("Analog sensor front-ends", paper="A2",
               comments=[
                   "Generated by hw/gen_sheet_sensors_analog.py -- do not hand-edit until it is retired",
                   "battery_sense.cir / sensor_ratiometric.cir / sensor_differential.cir / ntc_frontend.cir",
                   "Differential where the sensor return is SHARED; single-ended where it is dedicated",
                   "Difference amplifiers are INA592 at G = 1/2: 88 dB CMRR min against a 60 dB floor",
               ],
               ref_base=schlib.REF_BASE["sensors_analog"])
    divider_channel(sh, 40.0, 40.0, "V_BAT_1R", "V_BAT_1R_SNS", "120k", "10k",
                    "ECU pin 04 -- battery rail 1 -> PTA0 (ADC0_SE0)",
                    "battery_sense.cir R3/R4")
    divider_channel(sh, 40.0, 95.0, "V_BAT_2R", "V_BAT_2R_SNS", "120k", "10k",
                    "ECU pin 06 -- battery rail 2 -> PTA2 (ADC1_SE0)",
                    "battery_sense.cir R3/R4")
    ratiometric_channel(sh, 40.0, 150.0, "RAIL_P_IN", "RAIL_P",
                        "ECU pin 35 -- rail pressure, DEDICATED return pin 08 "
                        "-> PTA16 (ADC1_SE13)")

    diffs = [
        (330.0, 45.0, "BOOST_P_IN", "SGND_34", "BOOST_P",
         "ECU pin 41 -- boost pressure, return SHARED on pin 34 -> PTA1",
         "Shares connector pin 34 with coolant temperature"),
        (330.0, 110.0, "COOLANT_T_IN", "SGND_34", "COOLANT_T",
         "ECU pin 33 -- coolant temperature, return SHARED on pin 34 -> PTA6",
         "Shares connector pin 34 with boost pressure"),
        (330.0, 175.0, "EGR_POS_IN", "SGND_36", "EGR_POS",
         "ECU pin 37 -- EGR position, return SHARED on pin 36 -> PTA15",
         "Shares connector pin 36 with oil pressure"),
        (330.0, 240.0, "OIL_P_IN", "SGND_36", "OIL_P",
         "ECU pin 80 -- oil pressure, return SHARED on pin 36 -> PTA7",
         "Shares connector pin 36 with EGR position"),
        # Left column, under rail pressure. At x0 = 620 this channel ran
        # off an A2 page: a differential channel is about 155 mm wide by
        # the time the ADC tail is on it, and 620 + 155 is past 594.
        (40.0, 228.0, "BOOST_T_IN", "SGND_34", "BOOST_T",
         "ECU pin 79 -- boost temperature -> PTA3.  U2 OPEN: sensor type "
         "unmeasured",
         "U2 open -- drawn differential like its neighbours. If it turns "
         "out to be a bare NTC, ntc_frontend.cir's 2.2k pull-up replaces "
         "the input leg; that is a populate change, not a redesign."),
    ]
    for x0, y, sig, gnd, out, label, note in diffs:
        differential_channel(sh, x0, y, sig, gnd, out, label, note)

    excitation(sh)
    baro(sh)
    notes(sh)
    return sh


if __name__ == "__main__":
    print(build().write(OUT, force="--force" in sys.argv))
