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

THE OP-AMPS ARE NOT A CHOSEN PART. OPAMP_GENERIC carries function only,
with placeholder pin numbers and no footprint -- see its comment in
hw/gen_symbols.py. What is specified is the requirement:
sensor_differential.cir's own tolerance note tried the argument down to
60 dB CMRR and found it still holds, so 60 dB is the floor. 0.1%
discrete resistors give about 48 dB and do not clear it; a matched
network at 0.05% ratio, or a difference amplifier with the network
on-die, does.
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
OPAMP = "ecu25kva:OPAMP_GENERIC"
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
    """Difference stage: 26k in, 16k feedback, so gain is 16/26.

    The gain is the same 16/26 the ratiometric divider uses, reached a
    different way -- which is the point. Both put a 0-5 V sensor inside
    VREFH; only this one rejects the sensor return's own offset.
    """
    sh.text(label, x0, y - 22.0, size=1.6)
    ux, uy = x0 + 78.0, y
    sh.place(OPAMP, "U", ux, uy, "OPAMP_GENERIC",
             fields={"Source": "sensor_differential.cir Bd",
                     "Note": note,
                     "Requirement": "single 5 V, rail-to-rail in/out, "
                                    "network matched for >=60 dB CMRR"})
    inp = ic_pin("OPAMP_GENERIC", 3, ux, uy)
    inn = ic_pin("OPAMP_GENERIC", 2, ux, uy)
    out = ic_pin("OPAMP_GENERIC", 1, ux, uy)
    vp = ic_pin("OPAMP_GENERIC", 5, ux, uy)
    vn = ic_pin("OPAMP_GENERIC", 4, ux, uy)
    sh.wire(vp[0], vp[1], vp[0], vp[1] - 7.0)
    sh.label("5V_MAIN", vp[0], vp[1] - 7.0, rot=90)
    gnd_below(sh, vn[0], vn[1])

    # Signal leg into IN+, with 26k series and 16k to ground.
    sh.hlabel(sig_net, x0, inp[1], shape="input")
    sig = Rail(sh, inp[1])
    sig.to(x0)
    sh.place("Device:R", "R", x0 + 26.0, inp[1], "26k", rot=90,
             fields={"Source": "sensor_differential.cir -- input leg",
                     "Note": "26k in, 16k feedback: gain 16/26, the same "
                             "ratio the ratiometric divider uses"})
    a = pin_xy(*PINS["Device:R"]["1"], x0 + 26.0, inp[1], 90)
    b = pin_xy(*PINS["Device:R"]["2"], x0 + 26.0, inp[1], 90)
    r_in, r_out = (a, b) if a[0] < b[0] else (b, a)
    sig.to(r_in[0])
    mid = Rail(sh, inp[1])
    mid.to(r_out[0])
    vshunt(sh, "Device:R", "R", x0 + 50.0, inp[1] + 18.0, "16k",
           {"Source": "sensor_differential.cir -- IN+ leg to ground"}, mid)
    mid.to(inp[0])

    # Sensor-return leg into IN-, with the matching 26k and the 16k as
    # feedback. Matching these two ratios is what CMRR actually is.
    sh.hlabel(gnd_net, x0, inn[1] + 22.0, shape="input")
    ret = Rail(sh, inn[1] + 22.0)
    ret.to(x0)
    sh.place("Device:R", "R", x0 + 26.0, inn[1] + 22.0, "26k", rot=90,
             fields={"Source": "sensor_differential.cir -- return leg",
                     "Note": "MATCHED to the input leg's 26k. The pair's "
                             "ratio match IS the CMRR -- 0.1% discretes "
                             "give about 48 dB against a 60 dB floor."})
    a = pin_xy(*PINS["Device:R"]["1"], x0 + 26.0, inn[1] + 22.0, 90)
    b = pin_xy(*PINS["Device:R"]["2"], x0 + 26.0, inn[1] + 22.0, 90)
    g_in, g_out = (a, b) if a[0] < b[0] else (b, a)
    ret.to(g_in[0])
    sh.wire(g_out[0], g_out[1], inn[0] - 10.0, g_out[1])
    sh.wire(inn[0] - 10.0, g_out[1], inn[0] - 10.0, inn[1])
    sh.wire(inn[0] - 10.0, inn[1], inn[0], inn[1])

    # Feedback 16k from OUT back to IN-.
    fy = inn[1] - 20.0
    sh.place("Device:R", "R", ux, fy, "16k", rot=90,
             fields={"Source": "sensor_differential.cir -- feedback",
                     "Note": "MATCHED to the IN+ leg's 16k"})
    a = pin_xy(*PINS["Device:R"]["1"], ux, fy, 90)
    b = pin_xy(*PINS["Device:R"]["2"], ux, fy, 90)
    f_l, f_r = (a, b) if a[0] < b[0] else (b, a)
    sh.wire(inn[0] - 10.0, inn[1], inn[0] - 10.0, fy)
    sh.junction(inn[0] - 10.0, inn[1])
    sh.wire(inn[0] - 10.0, fy, f_l[0], f_l[1])
    sh.wire(f_r[0], f_r[1], out[0] + 8.0, fy)
    sh.wire(out[0] + 8.0, fy, out[0] + 8.0, out[1])

    node = Rail(sh, out[1])
    node.to(out[0])
    node.to(out[0] + 8.0, tap=True)
    adc_tail(sh, node, out[0] + 24.0, out[1], out_net)


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
        "OP-AMPS: FUNCTION DRAWN, PART NOT CHOSEN. OPAMP_GENERIC has "
        "placeholder pin numbers and no footprint, deliberately -- placing "
        "a real symbol here would assert a\n"
        "choice nobody has made. The requirement IS specified: single 5 V "
        "supply, rail-to-rail input and output, and a difference network "
        "matched well enough for 60 dB\n"
        "CMRR, which is the floor sensor_differential.cir's own tolerance "
        "note tried and found the argument still holds at. The netlist "
        "models 80 dB and marks it INFERRED.\n"
        "0.1% discrete resistors give roughly 48 dB and do NOT clear that "
        "floor. A matched network at 0.05% ratio, or a difference "
        "amplifier with the network on-die, does --\n"
        "so this is a resistor-network decision as much as an amplifier "
        "one. Five channels is two quad packages.\n"
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
        "BARO (PTD18) is an onboard sensor, new per spec sec.7 deviation "
        "#2. No part is chosen, so nothing is drawn for it -- it needs a "
        "device with its own footprint,\n"
        "supply and output type, none of which follow from the pin "
        "assignment alone.",
        40.0, 390.0, size=1.6)


def build():
    schlib.verify_pins()
    sh = Sheet("Analog sensor front-ends", paper="A2",
               comments=[
                   "Generated by hw/gen_sheet_sensors_analog.py -- do not hand-edit until it is retired",
                   "battery_sense.cir / sensor_ratiometric.cir / sensor_differential.cir / ntc_frontend.cir",
                   "Differential where the sensor return is SHARED; single-ended where it is dedicated",
                   "Op-amps are a placeholder symbol -- requirement is >=60 dB CMRR, part not chosen",
               ])
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
    notes(sh)
    return sh


if __name__ == "__main__":
    print(build().write(OUT, force="--force" in sys.argv))
