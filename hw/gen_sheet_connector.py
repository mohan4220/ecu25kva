#!/usr/bin/env python3
"""connector sheet: the 94-way ECU harness connector and what lands on it.

This sheet has no simulation block behind it because it is not a circuit.
It is the boundary, and its job is to be checkable against the machine:
every pin the wiring diagram shows, wired to the net the sheet that owns
that signal already named, and every pin it does not show left visibly
empty rather than quietly filled in.

WHAT IS KNOWN. refs/ecu-pinout-extracted.md was read off
GP3.8703.C4.pdf, Kirloskar's own field wiring diagram. It gives a 94-pin
connector (page 4) and shows 44 of those pins. It is a troubleshooting
document and says what it leaves out: "Power grounds, unused pins and
internal-only pins are not shown."

WHAT THAT LEAVES. 50 pins with no function, and among them -- this is
the finding, not a caveat -- THE POWER GROUND. The diagram shows pin 21
as the battery positive feed and shows no battery negative anywhere.
Every ground on every other sheet in this project returns to a net
called GND that, at this boundary, has no pin. A board cannot be built
without one, and choosing one from the 50 unknowns would be exactly the
guess this project's own rule forbids. See the sheet note.

THE PART NUMBER IS KNOWN, and this sheet said otherwise until it was
corrected on 21 September 2026. refs/field-evidence-2026-09-18.md sec.2b
closed U1 off a photograph of the housing angled to the light: BOSCH and
the armature-in-circle logo on the side body, 1 928 405 194 under the
BOSCH text, 1 928 405 192 on the lower body strip, code C beside it,
>PA66-GF50< on the locking lever. Read off the physical part, which is
better evidence than a catalogue match because it cannot be a
mis-identification. A Bosch 94-way ECU connector of the EDC17 family.

CODE C IS NOT A DETAIL: Bosch supplies these housings in mechanically
coded variants so differently-coded plugs cannot mate, so any
replacement or adapter housing must match code C or it will not engage.

What is still missing is the OEM PIN LIST -- a different document from
the part number -- and the board-side land pattern. A web search for
both numbers returned no catalogue hit, so the footprint has to come
through a Bosch distributor quoting them. None is assigned here, because
a mating land pattern is not a thing to infer from a photograph.

DECIDED 22 September 2026, by the owner: the ECU carries THIS connector
on the board and plugs straight into the unmodified OEM loom -- no
adapter harness. That reverses spec sec.7 deviation 1 (functionally-
split sealed connectors plus an adapter), which the spec now records as
reversed. The land pattern is therefore load-bearing: it is the board's
own header.

THE ERROR THIS CORRECTS is the same shape as the six findings this
project has already turned up, and it is one I made:
refs/ecu-pinout-extracted.md predates the field visit and still says "a
complete pinout requires the connector part number and the OEM pin
list". Reading that file and not refs/field-evidence-2026-09-18.md put
"no part number is known" on a sheet in a repo that had the part number
in it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import schlib
from schlib import Sheet, pin_xy

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "connector.kicad_sch")
ICPINS = json.load(open(os.path.join(HW, "lib", "ic_pins.json")))
CONN = "ecu25kva:CONN_ECU_94"
STUB = 24.0

# ECU pin -> the hierarchical net the owning sheet already named. Nothing
# here is invented: every left-hand number is a pin the wiring diagram
# shows, and every right-hand name already exists on another sheet.
NETS = {
    # -- power (refs sec."Power") --
    "21": "VBAT_IN", "4": "V_BAT_1R", "6": "V_BAT_2R",
    # -- analog sensors --
    "11": "EXC_BOOST_11", "41": "BOOST_P_IN", "79": "BOOST_T_IN",
    "34": "SGND_34", "33": "COOLANT_T_IN",
    "15": "EXC_EGR_15", "37": "EGR_POS_IN", "36": "SGND_36",
    "39": "EXC_OIL_39", "80": "OIL_P_IN",
    "32": "EXC_RAIL_32", "35": "RAIL_P_IN",
    # -- speed --
    "45": "EXC_CAM_45", "46": "CAM_FREQ_46", "44": "CAM_GND_44",
    "52": "CRANK_HI_52", "74": "CRANK_LO_74", "30": "SHIELD_30",
    # -- discrete in --
    "43": "SW_COOLANT_C", "23": "SW_DROOP_C",
    "20": "IN_AUDIO_ABORT_H", "24": "IN_OVERRIDE_SS_H",
    "71": "IN_IGNITION_H",
    # -- outputs --
    "88": "MU_RETURN", "50": "RLY_MAIN_OUT", "69": "RLY_BUZZER_OUT",
    "59": "EGR_HIGH_59", "81": "EGR_LOW_81",
    # -- injectors --
    "3": "INJ_A_03", "5": "INJ_B_05",
    "73": "INJ_LS1_73", "7": "INJ_LS3_07", "29": "INJ_LS2_29",
    # -- CAN --
    "55": "CAN1_H", "77": "CAN1_L", "87": "CAN2_H", "86": "CAN2_L",
}

# Pin 08 is the rail-pressure sensor's DEDICATED return. Unlike pins 34
# and 36 -- which are shared returns and therefore SIGNALS, carried into
# the difference amplifiers on sensors_analog -- a dedicated return has
# nothing to reject and is simply ground at the ECU end.
GROUNDED = {"8": "rail-pressure dedicated sensor return"}

# Shown on the wiring diagram, and still without a function anyone has
# established. Wiring these would be guessing.
UNRESOLVED = {
    "9": "SYNCHRONIZATION GROUND -- drawn RED on a diagram whose legend "
         "makes red a positive feed. U6 on the unknowns register.",
    "1": "G_G_B AT1 -- memo 03 suspects a power ground rather than a "
         "switch return. No MCU pin assigned either way.",
    "2": "G_G_B AT2 -- same.",
}


def build():
    schlib.verify_pins()
    sh = Sheet("94-way ECU connector and harness mapping", paper="A2",
               comments=[
                   "Generated by hw/gen_sheet_connector.py -- do not hand-edit until it is retired",
                   "Pin count and 44 pin functions from GP3.8703.C4.pdf via refs/ecu-pinout-extracted.md",
                   "50 pins have no established function -- including, so far, the power ground",
                   "Bosch 1 928 405 192 / 194 code C ON THE BOARD, no adapter (owner, 22 Sep) -- land pattern still needed",
               ],
               ref_base=schlib.REF_BASE["connector"])
    cx, cy = 297.0, 200.0
    sh.place(CONN, "J", cx, cy, "CONN_ECU_94", ref="J1001",
             fields={"Source": "refs/ecu-pinout-extracted.md (pin count "
                               "and 44 functions); "
                               "refs/field-evidence-2026-09-18.md sec.2b "
                               "(part numbers, off the housing)",
                     "MPN": "Bosch 1 928 405 192 / 194, CODE C",
                     "Note": "Bosch 94-way ECU connector, EDC17 family, "
                             "PA66-GF50 housing. Code C is a MECHANICAL "
                             "coding variant -- a differently-coded "
                             "housing will not mate.",
                     "FootprintStatus": "not assigned: the board-side land "
                             "pattern needs the mating half's drawing, via "
                             "a Bosch distributor. No catalogue hit on "
                             "either number.",
                     "Shown": "44 of 94 pins appear on the wiring diagram"})

    geom = ICPINS["CONN_ECU_94"]
    wired = 0
    for n in range(1, 95):
        num = str(n)
        px, py = pin_xy(*geom[num], cx, cy, 0)
        left = px < cx
        ex = px - STUB if left else px + STUB
        if num in NETS:
            sh.wire(px, py, ex, py)
            sh.hlabel(NETS[num], ex, py, shape="passive",
                      rot=180 if left else 0)
            wired += 1
        elif num in GROUNDED:
            # Taken clear of the stub column before it drops. At 2.54 mm
            # pitch EVERY multiple of the pitch below a pin is another
            # pin's row: the first version dropped 7.62 mm and landed
            # exactly on pin 11's label anchor, which put the boost
            # sensor's 5 V excitation on GND in the netlist while the
            # page still plotted correctly. It then goes UP, clear of
            # the stub column, because dropping it landed the ground
            # symbol on top of pin 20's label instead.
            sh.wire(px, py, ex, py)
            sh.wire(ex, py, ex - 30.0, py)
            sh.wire(ex - 30.0, py, ex - 30.0, py - 34.0)
            sh.gnd(ex - 30.0, py - 34.0)
            wired += 1

    sh.text("J1 -- 94-way ECU harness connector", cx - 36.0, cy - 70.0,
            size=2.0)
    sh.text(f"{wired} pins wired, {94 - wired} left deliberately empty",
            cx - 36.0, cy - 64.0, size=1.6)

    sh.text(
        "THE POWER GROUND HAS NO PIN, AND THAT IS THIS SHEET'S FINDING.\n"
        "\n"
        "GP3.8703.C4.pdf shows pin 21 as the battery positive feed and\n"
        "shows no battery negative anywhere on the ECU connector. Its own\n"
        "scope note explains why -- it is a field troubleshooting diagram\n"
        "and it omits \"power grounds, unused pins and internal-only\n"
        "pins\" -- so this is a gap in the SOURCE, not a contradiction in\n"
        "it.\n"
        "\n"
        "It is still a gap that stops a board. Every other sheet in this\n"
        "project returns to GND: the injector low sides carry 18 A into\n"
        "it, the metering unit up to 1.35 A, and the analog front ends\n"
        "reference their zeners and their 22 nF filters to it. At this\n"
        "boundary that net has nowhere to go.\n"
        "\n"
        "It cannot be solved by choosing. Fifty pins have no established\n"
        "function and several of them are certainly grounds -- a 94-way\n"
        "connector feeding an 18 A injector stage does not have one\n"
        "return -- but picking which is exactly the guess this project\n"
        "forbids, and a wrong ground pin is not a rework, it is a\n"
        "harness that has to be remade.\n"
        "\n"
        "WHAT ACTUALLY SETTLES IT: the connector part number and the OEM\n"
        "pin list, or continuity measurement on the machine between the\n"
        "connector shell and battery negative. The reference names the\n"
        "first as the missing document. The second needs the machine and\n"
        "belongs with U16/U2/U8/U14/U5.",
        14.0, 130.0, size=1.6)

    sh.text(
        "PINS SHOWN ON THE DIAGRAM AND STILL NOT WIRED\n"
        "\n"
        "  09  SYNCHRONIZATION GROUND. Drawn RED on a diagram whose own\n"
        "      legend makes red a positive feed, so the name and the\n"
        "      colour disagree. U6 on the unknowns register.\n"
        "  01  G_G_B AT1.  02  G_G_B AT2. Memo 03 suspects these are\n"
        "      power grounds rather than switch-return legs. If that is\n"
        "      right they are part of the answer to the note on the left.\n"
        "      No MCU pin is assigned either way, because guessing which\n"
        "      would violate the same rule.\n"
        "\n"
        "NETS THAT EXIST AND HAVE NO PIN YET\n"
        "\n"
        "  TRIP_LOOP     the trip-module supervised loop is NEW -- it is\n"
        "                not on the OEM diagram at all, so it needs one\n"
        "                of the 50 unconfirmed pins. discrete_io draws\n"
        "                the front end; the pin waits on the same\n"
        "                document the ground does.\n"
        "  (EGR_HIGH_59 / EGR_LOW_81 were listed here until the bridge\n"
        "  was drawn on 22 Sep 2026 -- discrete, two AUIRS2184S.)\n"
        "\n"
        "WHY PINS 34 AND 36 ARE SIGNALS AND PIN 08 IS GROUND\n"
        "\n"
        "  34 and 36 are SHARED sensor returns -- 34 for boost pressure\n"
        "  and coolant temperature, 36 for EGR position and oil\n"
        "  pressure. A shared return carries both sensors' current, so\n"
        "  its own resistance is an offset on both readings, which is\n"
        "  why sensors_analog carries them into difference amplifiers\n"
        "  rather than to ground. 08 is rail pressure's DEDICATED\n"
        "  return: nothing to reject, so it is simply ground here.",
        400.0, 130.0, size=1.6)

    sh.text(
        "THE PART IS IDENTIFIED; THE LAND PATTERN IS NOT. "
        "refs/field-evidence-2026-09-18.md sec.2b closed U1 off a "
        "photograph of the housing angled to the light: BOSCH and the "
        "armature-in-circle logo moulded on the side body, "
        "1 928 405 194 under the BOSCH text, 1 928 405 192 on the lower\n"
        "body strip, CODE C beside it, >PA66-GF50< on the locking lever. "
        "Read off the physical part, which beats a catalogue match "
        "because it cannot be a mis-identification. CODE C IS "
        "LOAD-BEARING: Bosch supplies these housings mechanically coded\n"
        "so differently-coded plugs cannot mate, so any replacement or "
        "adapter must match it or it will not engage -- the kind of "
        "detail that is invisible until a part arrives and will not "
        "fit. Still missing: the OEM PIN LIST, a different document\n"
        "from the part number, and the board-side footprint. A search "
        "for both numbers returned no catalogue hit, so the land "
        "pattern has to come through a Bosch distributor quoting them. "
        "Nothing is assigned here, because a mating land pattern is\n"
        "not a thing to infer from a photograph. Pin NAMES on the "
        "symbol are the wiring diagram's own signal names where it "
        "shows the pin and KiCad's blank elsewhere -- the same "
        "treatment the op-amps and the comparator get: the symbol\n"
        "asserts what is known and declines to assert what is not.",
        14.0, 390.0, size=1.6)
    return sh


if __name__ == "__main__":
    print(build().write(OUT, force="--force" in sys.argv))
