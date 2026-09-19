#!/usr/bin/env python3
"""Draw a schematic for every circuit block, as SVG and PNG.

Each drawing mirrors the netlist of the same name in sim/blocks/, so the
picture and the thing that gets simulated cannot drift apart.

    .venv/bin/python sim/draw_schematics.py

SVGs are post-processed to use `currentColor` instead of black, so they
read correctly on both light and dark backgrounds when embedded in the
handbook. PNGs are fixed dark-on-white, for pasting into slides.
"""
import pathlib
import re

import schemdraw
import schemdraw.elements as elm

OUT = pathlib.Path(__file__).resolve().parent.parent / "docs" / "handbook" / "circuits"
OUT.mkdir(parents=True, exist_ok=True)

schemdraw.config(lw=1.6, fontsize=11.5)


def battery_sense(d):
    """ECU pins 04/06 -- 6-40 V rail scaled into a 3.3 V ADC.

    Draws the ADOPTED divider only, using the netlist's own designators
    for it: R3/R4 in battery_sense.cir (120k/10k, sized for the 3.3 V
    ADC). The netlist also runs a REJECTED comparison divider, R1/R2
    (75k/10k, inherited from a 5 V-ADC-era assumption) -- that one is
    not drawn, because it isn't the circuit on the board. Using R1/R2
    here, as an earlier version of this drawing did, collided with the
    netlist's own R1/R2 and pointed a reader at the wrong resistors.
    Spec sec.4's front-end table gives 120k/10k for pins 04/06, which
    matches R3/R4 exactly."""
    d += elm.Dot(open=True).label("BATT\n6-40 V", "left")
    d += elm.Line().right().length(0.6)
    d += (r3 := elm.Resistor().right().label("R3\n120k"))
    d += (node := elm.Dot())
    d += elm.Line().right().length(1.4)
    d += elm.Dot(open=True).label("MCU ADC", "right")
    d += elm.Resistor().down().at(node.center).label("R4\n10k")
    d += elm.Ground()
    d += elm.Label().at((node.center[0] - 2.3, node.center[1] - 4.6)).label(
        "R3/R4: the adopted divider (spec sec.4, pins 04/06).\n"
        "battery_sense.cir also carries a rejected R1/R2 75k/10k\n"
        "divider, sized for a 5 V ADC -- not drawn here.")
    return "Battery voltage sense -- pins 04 / 06"


def discrete_input(d):
    """ECU pins 20/24/71 -- active-high switched battery."""
    d += elm.Dot(open=True).label("SWITCHED\nBATTERY\n6-40 V", "left")
    d += elm.Line().right().length(0.6)
    d += elm.Resistor().right().label("R5\n47k")
    d += (node := elm.Dot())
    d += elm.Line().right().length(3.5)
    d += elm.Dot(open=True).label("MCU GPIO", "right")

    # Three shunt legs, spread rightwards so none sits under R5
    d += elm.Resistor().down().at(node.center).label("R6\n68k", loc="bottom")
    d += elm.Ground()

    d.push()
    d += elm.Line().right().at(node.center).length(1.3)
    d += elm.Dot()
    d += elm.Capacitor().down().label("C1\n220n", loc="bottom")
    d += elm.Ground()
    d.pop()

    d += elm.Line().right().at(node.center).length(2.6)
    d += elm.Dot()
    d += elm.Zener().down().label("D1\n3.0 V", loc="bottom")
    d += elm.Ground()
    return "Discrete switch input -- pins 20 / 24 / 71"


def trip_module_sense(d):
    """NEW pin -- three-state supervised trip-module sense loop.

    Rt and the NC aux contact live AT THE TRIP MODULE, physically at
    the far end of a new harness run -- labelled, not boxed, to avoid
    this file's own rotated/multi-anchor label traps. That placement
    is the detail that makes "wire cut" distinguishable from "Rt is
    the only path": a break anywhere between the module and the ECU
    removes both the contact and Rt from the circuit the same way.
    R5/R6/zener/C1 are discrete_input.cir's own divider, reused
    unchanged -- drawn solid, not dashed, because they ARE this
    netlist's elements, just fed from a new source topology."""
    d += elm.Dot(open=True).label("BATT +\n(switched)", "left")
    d += elm.Line().right().length(0.6)
    d += (left := elm.Dot())
    d += elm.Resistor().right().at(left.center).label("Rt\n1.2M", loc="bottom")
    d += (right := elm.Dot())

    d.push()
    d += elm.Line().up().at(left.center).length(1.0)
    d += elm.Switch().right().length(2.2).label(
        "NC aux contact\nclosed = healthy", loc="top")
    d += elm.Line().down().toy(right.center[1])
    d.pop()

    d += elm.Label().at((left.center[0] - 0.3, left.center[1] - 1.2)).label(
        "-- at the trip module, remote (part TBD) --")

    d += elm.Line().right().at(right.center).length(1.2).linestyle("--")
    d += elm.Label().at((right.center[0] + 0.6, right.center[1] + 0.5)).label(
        "new harness run\n(not on this board)")

    # ECU-side divider: discrete_input.cir's own R5/R6/zener/C1, reused
    d += elm.Resistor().right().label("R5\n47k")
    d += (node := elm.Dot())
    d += elm.Line().right().length(3.0)
    d += elm.Dot(open=True).label("MCU ADC\n(3-band read)", "right")

    d += elm.Resistor().down().at(node.center).label("R6\n68k", loc="bottom")
    d += elm.Ground()

    d.push()
    d += elm.Line().right().at(node.center).length(1.2)
    d += elm.Dot()
    d += elm.Capacitor().down().label("C1\n220n", loc="bottom")
    d += elm.Ground()
    d.pop()

    d += elm.Line().right().at(node.center).length(2.4)
    d += elm.Dot()
    d += elm.Zener().down().label("D1\n3.0 V", loc="bottom")
    d += elm.Ground()

    d += elm.Label().at((0.0, -4.2)).label(
        "healthy 2.86-2.95 V (clamped, flat) -- tripped 0.31-2.07 V\n"
        "(linear, Rt in circuit, never reaches the zener knee) -- wire\n"
        "fault ~0 V (neither Rt nor battery reaches the divider at all)")
    return "Trip-module sense -- new pin, three-state supervised loop"


def sensor_ratiometric(d):
    """ECU pins 41/35/80/37 -- 0.5-4.5 V ratiometric sensor."""
    d += elm.Dot(open=True).label("SENSOR\n0.5-4.5 V", "left")
    d += elm.Line().right().length(0.6)
    d += elm.Resistor().right().label("R1\n10k")
    d += (node := elm.Dot())
    d += elm.Line().right().length(3.5)
    d += elm.Dot(open=True).label("MCU ADC", "right")

    d += elm.Resistor().down().at(node.center).label("R2\n16k", loc="bottom")
    d += elm.Ground()

    d.push()
    d += elm.Line().right().at(node.center).length(1.3)
    d += elm.Dot()
    d += elm.Capacitor().down().label("C1\n22n", loc="bottom")
    d += elm.Ground()
    d.pop()

    d += elm.Line().right().at(node.center).length(2.6)
    d += elm.Dot()
    d += elm.Zener().down().label("D1\n3.3 V", loc="bottom")
    d += elm.Ground()
    return "Ratiometric sensor front-end -- pins 41 / 35 / 80 / 37"


def transient_clamp(d):
    """Battery input protection -- ISO 7637-2 pulse 2a. Sits between the EMI
    filter and the reverse-battery FET, per spec sec.4's stage order for
    pin 21: EMI filter -> fuse -> TVS -> reverse-battery FET. FB1 does not
    belong on this drawing -- it is emi_filter's own ferrite, one stage
    upstream; drawing a second FB1 here was the bug (see F2 in the
    2026-09-18 power-chain review)."""
    d += elm.Dot(open=True).label("from EMI\nfilter", "left")
    d += elm.Line().right().length(0.5)
    d += elm.Fuse().right().linestyle("--").label("F1\n5 A")
    d += (node := elm.Dot())
    d += elm.Line().right().length(1.6)
    d += elm.Dot(open=True).label("to reverse-\nbattery FET", "right")

    d += elm.Line().down().at(node.center).length(0.4)
    d += (tvs := elm.Dot())
    d += (d1 := elm.DiodeShockley().down())
    d += elm.Ground()
    # Same trap load_dump's picture already worked around: loc= on this
    # rotated element lands on top of C1's label. Explicit coordinate to
    # the LEFT of the diode, and the C1 branch pushed out to 2.3 pitch
    # instead of 1.5, clears it.
    d += elm.Label().at((tvs.center[0] - 2.7, tvs.center[1] - 1.5)).label(
        "D1  TVS\nSMBJ33CA")

    d += elm.Line().right().at(tvs.center).length(2.3)
    d += elm.Dot()
    d += elm.Capacitor().down().label("C1\n10u")
    d += elm.Ground()

    d += elm.Label().at((3.0, -5.0)).label(
        "F1 dashed: on the board per spec sec.4, but this netlist folds\n"
        "all series impedance into Rsrc -- F1 is not modelled, and its\n"
        "survival under pulse 2a's repeated ~38 A stress is untested")
    return "Transient clamp -- battery input, ISO 7637-2"


def load_dump(d):
    """Battery input protection -- ISO 7637-2 pulse 5b, same physical stage
    as transient_clamp, a much longer and more energetic pulse. FB1 is
    deliberately not drawn here -- see transient_clamp's docstring."""
    d += elm.Dot(open=True).label("from EMI\nfilter", "left")
    d += elm.Line().right().length(0.5)
    d += elm.Fuse().right().linestyle("--").label("F1\n5 A")
    d += (node := elm.Dot())
    d += elm.Line().right().length(1.6)
    d += elm.Dot(open=True).label("to reverse-\nbattery FET", "right")

    d += elm.Line().down().at(node.center).length(0.4)
    d += (tvs := elm.Dot())
    d += (d1 := elm.DiodeShockley().down())
    d += elm.Ground()
    # loc= on this rotated element landed on top of C1's label (same trap
    # transient_clamp's picture has -- not fixed there, fixed here instead
    # of copying the collision forward). Explicit coordinate to the LEFT of
    # the diode, and the C1 branch pushed out to 2.3 pitch instead of 1.5,
    # clears it.
    d += elm.Label().at((tvs.center[0] - 2.7, tvs.center[1] - 1.5)).label(
        "D1  TVS\nSMBJ33CA")

    d += elm.Line().right().at(tvs.center).length(2.3)
    d += elm.Dot()
    d += elm.Capacitor().down().label("C1\n10u")
    d += elm.Ground()

    # Severity + result, placed by explicit coordinate well clear of every
    # other element -- this is a lot of text to land safely.
    d += elm.Label().at((3.3, -5.0)).label(
        "pulse 5b: Us*=40 V, 0.5R, 400 ms\n"
        "D1 absorbs ~46 J at ~116 W -- FAILS an SMBJ-class part's rating\n"
        "F1 dashed (drawn, not in this netlist) does not rescue it either:\n"
        "fault current is 3.04 A, 0.6x F1's rating, and won't clear in 400 ms")
    return "Load dump -- battery input, ISO 7637-2 pulse 5b"


def injector_boost(d):
    """ECU pins 03/05 high side, 73/07/29 low side. The netlist is a
    turn-on-only step response (ideal source straight onto L/R): neither
    switch nor the sense resistor is a netlist element, so both are
    dashed."""
    d += elm.Dot(open=True).label("BOOST RAIL\n~100 V", "left")
    d += elm.Line().right().length(0.7)
    d += (hs := elm.Switch().right().linestyle("--").label("high side\npin 03 / 05"))
    d += elm.Line().right().length(0.5)
    d += elm.Dot(open=True).label("INJECTOR", "top")
    d += elm.Inductor().right().label("L\n200u")
    d += elm.Resistor().right().label("R\n0.5")
    d += elm.Line().right().length(0.5)
    d += elm.Switch().right().linestyle("--").label("low side\npin 73 / 07 / 29")
    d += elm.Line().right().length(0.5)
    d += (sense := elm.Dot())
    d += elm.Resistor().down().linestyle("--").label("R_sense\ncurrent fb")
    d += elm.Ground()
    d += elm.Label().at((hs.center[0] + 0.3, hs.center[1] - 2.6)).label(
        "dashed: on the board, not in this netlist -- R above already\n"
        "lumps whatever series resistance the real drive path adds")
    return "Injector drive -- bank high side, per-cylinder low side"


def injector_turnoff(d):
    """ECU pins 73/07/29 -- low-side switch, recirculation into the boost
    cap (Cres, the same reservoir boost_converter.cir sizes)."""
    d += elm.Dot(open=True).label("BOOST RAIL\n~100 V", "left")
    d += elm.Line().right().length(0.5)
    d += (rail := elm.Dot())
    d += elm.Capacitor().down().at(rail.center).label("Cres\n47u", loc="bottom")
    d += elm.Ground()

    d += elm.Line().right().at(rail.center).length(0.6)
    d += elm.Switch().right().label("high side\nbank shared")
    d += (hi := elm.Dot())
    d += elm.Line().right().length(0.4)
    d += elm.Dot(open=True).label("INJECTOR", "top")
    d += elm.Inductor().right().label("L\n200u")
    d += elm.Resistor().right().label("R\n0.5")
    d += (lo := elm.Dot())
    d += elm.Line().right().length(0.4)
    d += elm.Switch().right().label("low side\npin 73 / 07 / 29")
    d += elm.Line().right().length(0.4)
    d += elm.Ground()

    # D_fw -- ground back into "hi", the loop's return path. Not the new
    # part this block adds: it is the same external recirculation diode
    # Infineon's TLE8242-2 datasheet already requires for hold-phase
    # constant-current chopping (research memo 10, section 1.2). Dropped
    # straight down from "hi" so it never crosses the main chain.
    d += elm.Line().down().at(hi.center).length(1.7)
    d += elm.Diode().down().reverse()
    d += elm.Ground()
    # loc= on a rotated element lands unpredictably (the trap every other
    # diode/switch label in this file works around) -- explicit coordinate,
    # clear of both the diode and the ground symbol below it.
    d += elm.Label().at((hi.center[0] + 0.85, hi.center[1] - 1.0)).label(
        "D_fw\nreturn path\n(TLE8242-2's own\nhold-phase diode)")

    # D_recirc -- "lo" back into the boost cap. THIS is the new part this
    # block exists to add. Routed above the main chain, clear of the
    # "INJECTOR" label, then down into the same node Cres hangs off.
    d += elm.Line().up().at(lo.center).length(2.8)
    d += (rc_top := elm.Dot())
    d += (drc := elm.Diode().left().reverse())
    d += elm.Line().left().tox(rail.center)
    d += elm.Line().down().toy(rail.center)
    d += elm.Label().at((drc.center[0] - 0.3, rc_top.center[1] + 0.45)).label(
        "D_recirc")

    # Well clear of D_fw's own diode and ground symbol below "hi" -- the
    # first attempt put this text straight through them.
    d += elm.Label().at((hi.center[0] + 3.0, lo.center[1] - 6.2)).label(
        "18 A -> ~0 A in ~33 us, rail bump ~+6.4 V/event (measured)\n"
        "memo 10 predicted ~36 us / ~+6.9 V ideal -- real diode and\n"
        "switch losses shave both, and the bump undershoots the\n"
        "7.3 V on-phase droop it is paired with -- net loss, not gain")
    return "Injector turn-off -- recirculation into the boost cap"


def relay_driver(d):
    """ECU pins 50/69 -- low-side FET with flyback diode."""
    d += elm.Dot(open=True).label("BATT +  13.5 V", "top")
    d += elm.Line().right().length(0.6)
    d += (top := elm.Dot())
    d += (coil := elm.Inductor().down())
    d += (drain := elm.Dot())
    # Placed by coordinate: loc= on a rotated element lands unpredictably
    d += elm.Label().at((coil.center[0] + 1.05, coil.center[1])).label(
        "relay coil\n1.2 H / 160R")

    # Flyback diode across the coil, cathode to the battery side. It sits to
    # the LEFT because the NFet symbol puts its gate on the right, and a gate
    # lead routed leftwards would cross back over the coil.
    d += elm.Line().left().at(top.center).length(1.8)
    d += elm.Diode().down().reverse().label("D1\nflyback", loc="left")
    d += elm.Line().right().tox(drain.center)

    # Low-side switch below the coil, gate out to the right
    d += (q := elm.NFet(bulk=False).at(drain.center).anchor("drain"))
    d += elm.Ground().at(q.source)
    d += elm.Line().right().at(q.gate).length(0.7).label("MCU pin 50 / 69", loc="right")
    return "Relay driver -- pins 50 / 69"


def egr_hbridge(d):
    """ECU pins 59 (EGR HIGH) / 81 (EGR LOW) -- H-bridge into a positional
    actuator, position feedback on pin 37.

    The driver is drawn as one Ic block, the same convention supervisor()
    uses for its supervisor IC: no H-bridge part is chosen (spec sec.4's
    outputs table names the function, not a part), so the four internal
    power switches are not drawn as discrete symbols here -- they ARE
    modelled, as four generic switches plus body diodes, in the netlist,
    but drawing four unlabelled switch symbols would suggest a part
    selection that has not been made. The motor and the kill-clamp
    pulldowns are real, modelled parts and are drawn solid; the driver
    IC's internal FETs and the position pot are the board's actual
    parts but are not this netlist's own elements, so the pot is dashed
    per this file's convention (see e.g. injector_boost's R_sense) and
    cited to sensor_ratiometric.cir rather than redrawn.

    Trap from this file's own header, hit while building this one: the
    Motor element inherits the PREVIOUS element's direction unless given
    its own -- placed with an explicit `.right()` rather than relying on
    the drawing's current heading."""
    ic = elm.Ic(
        pins=[
            elm.IcPin(name="IN1", side="left", anchorname="in1"),
            elm.IcPin(name="IN2", side="left", anchorname="in2"),
            elm.IcPin(name="OUT1", side="right", anchorname="out1"),
            elm.IcPin(name="OUT2", side="right", anchorname="out2"),
            elm.IcPin(name="GND", side="bottom", anchorname="gnd"),
        ],
        size=(4.6, 3.0),
    ).label("H-bridge\ndriver (part TBD)", "top")
    d += ic
    in1 = ic.absanchors["in1"]
    in2 = ic.absanchors["in2"]
    out1 = ic.absanchors["out1"]
    out2 = ic.absanchors["out2"]
    d += elm.Ground().at(ic.absanchors["gnd"])

    # ---- kill-clamp pulldowns on IN1/IN2, drawn once each: the real
    # modelled parts (Rpd=470, kill FET keyed to the supervisor's RESET,
    # same topology supervisor.cir already validated). ----
    k1 = (in1[0] - 2.0, in1[1])
    d += elm.Line().left().at(in1).tox(k1[0])
    d += (kn1 := elm.Dot())
    d += elm.Resistor().down().at(kn1.center).length(1.2).label("Rpd\n470", loc="right")
    d += (kf1 := elm.NFet(bulk=False).right().anchor("drain"))
    d += elm.Ground().at(kf1.source)
    d += elm.Line().down().at(kf1.gate).length(0.5)
    d += elm.Dot(open=True).label("kill (RESET)", "bottom")
    d += elm.Line().left().at(kn1.center).length(1.3)
    d += elm.Dot(open=True).label("MCU pin 59\n(EGR HIGH)", "left")

    k2 = (in2[0] - 2.0, in2[1])
    d += elm.Line().left().at(in2).tox(k2[0])
    d += (kn2 := elm.Dot())
    d += elm.Resistor().down().at(kn2.center).length(1.2).label("Rpd\n470", loc="right")
    d += (kf2 := elm.NFet(bulk=False).right().anchor("drain"))
    d += elm.Ground().at(kf2.source)
    d += elm.Line().down().at(kf2.gate).length(0.5)
    d += elm.Dot(open=True).label("kill (RESET)", "bottom")
    d += elm.Line().left().at(kn2.center).length(1.3)
    d += elm.Dot(open=True).label("MCU pin 81\n(EGR LOW)", "left")

    # ---- battery feed and the motor between OUT1/OUT2. Built from
    # explicit .tox()/.toy() legs rather than a direct point-to-point
    # line -- a diagonal line straight from out1 to the BATT+ label was
    # this drawing's first version and read as a stray wire. ----
    d += elm.Line().right().at(out1).length(1.0)
    d += (nodeA := elm.Dot())
    d += elm.Line().up().length(1.8)
    d += elm.Dot(open=True).label("BATT +\n13.5 V", "top")

    d += elm.Line().right().at(nodeA.center).length(0.8)
    d += (m := elm.Motor().right())
    d += elm.Line().right().at(m.end).length(0.8)
    d += (nodeB := elm.Dot())
    d += elm.Line().up().toy(out2[1])
    d += elm.Line().left().tox(out2[0])
    d += elm.Label().at((m.center[0], m.center[1] + 1.0)).label(
        "EGR actuator\nRm 3R / Lm 5mH (INFERRED)")

    # ---- position feedback: not this netlist's own front end ----
    d += elm.Line().down().at((m.center[0], m.center[1] - 0.7)).length(0.5).linestyle("--")
    d += elm.Potentiometer().down().linestyle("--").label(
        "position pot\n(pin 37)", loc="right")
    d += elm.Line().down().length(0.4).linestyle("--")
    d += elm.Dot(open=True).linestyle("--")
    d += elm.Label().at((m.center[0] - 1.6, m.center[1] - 4.2)).label(
        "to sensor_ratiometric.cir\n(Group A, already built)")

    d += elm.Label().at((0.0, -6.5)).label(
        "dashed: on the board, not in this netlist -- the driver's internal\n"
        "FETs are modelled generically (four switches + body diodes), the\n"
        "position pot is a REAL front end but it is sensor_ratiometric.cir's,\n"
        "not a new one (see that block's pins 41/35/80/37)")
    return "EGR actuator H-bridge -- pins 59 / 81, position feedback pin 37"


def emi_filter(d):
    """Power chain stage 1 -- CISPR 25 differential input filter."""
    d += elm.Dot(open=True).label("BATT +\npin 21", "left")
    d += elm.Line().right().length(0.5)
    d += elm.Inductor2().right().label("L1\n22u")
    d += (n1 := elm.Dot())
    d += elm.Inductor2().right().at(n1.center).label("FB1\nferrite 0.5u / 120R")
    d += (n2 := elm.Dot())
    d += elm.Line().right().length(3.4)
    d += elm.Dot(open=True).label("to fuse ->\nTVS stage", "right")

    d += elm.Capacitor().down().at(n1.center).label("C1\n4u7")
    d += elm.Ground()

    d.push()
    d += elm.Capacitor().down().at(n2.center).label("C2\n100n")
    d += elm.Ground()
    d.pop()

    # The damper branch sits well clear of C2: at 1.2 of pitch its label
    # landed on top of C2's, which is how the first render came out.
    d += elm.Line().right().at(n2.center).length(2.2)
    d += elm.Dot()
    d += elm.Capacitor().down().label("Cd\n1u")
    d += elm.Resistor().down().label("Rd\n2R2")
    d += elm.Ground()
    return "EMI input filter -- CISPR 25, differential mode"


def reverse_battery(d):
    """Power chain stage 2 -- ideal-diode controller and P-FET. Sits
    downstream of the TVS clamp per spec sec.4's stage order, so this FET
    sees the clamped ~50 V, not the raw pulse -- see transient_clamp."""
    d += elm.Dot(open=True).label("from TVS\nstage", "left")
    d += elm.Line().right().length(0.8)
    d += (q := elm.PFet(bulk=False).right().anchor("source"))
    d += elm.Line().right().at(q.drain).length(1.0)
    d += (n := elm.Dot())
    d += elm.Line().right().length(1.4)
    d += elm.Dot(open=True).label("to buck VIN", "right")

    # Controller box below the FET, with its gate lead dropping into it.
    # The first render put this caption straight through the transistor.
    d += elm.Line().down().at(q.gate).length(1.6)
    d += (g := elm.Dot())
    d += elm.Label().at((g.center[0], g.center[1] - 0.55)).label(
        "ideal-diode controller\nwatches polarity, drives the gate")

    # Placed above the FET rather than at n: the "from TVS stage" label
    # change shifted nothing structurally, but this caption already sat
    # on top of the FET symbol before that edit -- pre-existing collision,
    # fixed here rather than carried forward.
    d += elm.Label().at((q.drain[0] + 0.7, q.source[1] + 0.55)).label(
        "< 0.3 V drop -- 24 mV at 3 A")
    return "Reverse-battery protection -- ideal diode, not a Schottky"


def buck_preregulator(d):
    """Power chain stage 4 -- synchronous buck, 6-40 V to 5 V."""
    d += elm.Dot(open=True).label("VIN\n6-40 V", "left")
    d += elm.Line().right().length(0.5)
    d += (top := elm.Dot())
    d += (hs := elm.Switch().down())
    d += (sw := elm.Dot())
    d += (ls := elm.Switch().down())
    d += elm.Ground()

    # Placed by coordinate: loc= on a rotated element lands unpredictably,
    # and here it put "high side" straight through the VIN terminal label.
    d += elm.Label().at((hs.center[0] + 1.15, hs.center[1])).label("high side")
    d += elm.Label().at((ls.center[0] + 1.15, ls.center[1])).label("low side")
    d += elm.Label().at((sw.center[0] - 0.75, sw.center[1] + 0.3)).label("SW")

    d += elm.Inductor2().right().at(sw.center).label("L 33u")
    d += (out := elm.Dot())
    d += elm.Line().right().length(1.2)
    d += elm.Dot(open=True).label("5V_MAIN", "right")

    d += elm.Capacitor().down().at(out.center).label("Cout\n47u / 10m")
    d += elm.Ground()

    d += elm.Label().at((top.center[0] + 2.0, top.center[1] + 1.0)).label(
        "400 kHz -- above CISPR 25's 150 kHz band start")
    return "Buck pre-regulator -- 6-40 V to 5 V at 400 kHz"


def sensor_rail(d):
    """Power chain stage 5 -- one PTC per sensor group."""
    d += elm.Dot(open=True).label("5V_MAIN", "left")
    d += elm.Line().right().length(0.5)
    d += elm.Resistor().right().label("Rsrc\n0R1")
    d += (rail := elm.Dot())
    d += elm.Label().at((rail.center[0], rail.center[1] + 0.55)).label("5V_SENSOR")
    d += elm.Line().right().length(7.2)

    # 3.5 of pitch, because the captions are wider than the branches.
    for i, (name, pins) in enumerate((
            ("group A", "rail P -- pin 08"),
            ("group B", "boost + coolant -- 34"),
            ("group C", "EGR + oil -- 36"))):
        x = rail.center[0] + 3.5 * i
        d += elm.Line().down().at((x, rail.center[1])).length(0.4)
        d += (f := elm.Fuse().down())
        d += elm.Label().at((f.center[0] + 0.95, f.center[1])).label("PTC 2R")
        d += elm.Line().down().length(0.4)
        d += elm.Dot(open=True).label(f"{name}\n{pins}", "bottom")
    return "5V_SENSOR distribution -- a fault stays in its own group"


def mcu_pdn(d):
    """Power chain stages 6-7 -- the 3V3_MCU decoupling network."""
    d += elm.Dot(open=True).label("5V_MAIN", "left")
    d += elm.Line().right().length(0.5)
    d += elm.Resistor().right().label("LDO\n5 V -> 3V3")
    d += (rail := elm.Dot().label("3V3_MCU", "top"))
    d += elm.Line().right().length(3.2)
    d += elm.Dot(open=True).label("S32K148\nVDD pins", "right")

    d += elm.Capacitor().down().at(rail.center).label("Cbulk 150u\nESR 50m")
    d += elm.Ground()

    d.push()
    d += elm.Line().right().at(rail.center).length(1.6)
    d += elm.Dot()
    d += elm.Capacitor().down().label("10 x 100n\nat the pins")
    d += elm.Ground()
    d.pop()

    d += elm.Label().at((rail.center[0] + 1.0, rail.center[1] - 3.0)).label(
        "bulk ESR damps the 68 kHz peak -- low-ESR here makes it worse")
    return "3V3_MCU power distribution -- target 100 mOhm"


def vr_conditioner(d):
    """Crank speed input -- pins 52 / 74 / 30."""
    d += elm.Dot(open=True).label("VR +\npin 52", "left")
    d += elm.Line().right().length(0.5)
    d += elm.Resistor().right().label("R1 1k")
    d += (n := elm.Dot())
    d += elm.Line().right().length(1.6)
    d += (cmp := elm.Dot())
    d += elm.Line().right().length(1.4)
    d += elm.Dot(open=True).label("FlexTimer\ncapture", "right")

    d += elm.Resistor().down().at(n.center).label("R2\n100k")
    d += elm.Ground()

    d += elm.Label().at((cmp.center[0] + 0.1, cmp.center[1] + 0.6)).label(
        "comparator, threshold 0 V, hysteresis +/-0.2 V")
    d += elm.Line().down().at(cmp.center).length(0.8)
    d += elm.Dot(open=True).label("VR -\npin 74", "bottom")
    return "Crank VR conditioner -- zero-cross, not a fixed threshold"


def cam_frontend(d):
    """ECU pins 45/46/44 -- cam Hall sensor, open-collector, into
    PTB3/FTM1_CH1. Drawn as network B (the transient/switching network):
    R1/R2/C1/D1 identical in value to sensor_ratiometric.cir's own front
    end, just with the sensor's open-collector output (S1, a switch to
    ground) standing in place of an analog source."""
    d += elm.Dot(open=True).label("5V_SENSOR\npin 45", "left")
    d += elm.Line().right().length(0.6)
    d += elm.Resistor().right().label("R1\n10k")
    d += (node := elm.Dot())
    d += elm.Line().right().length(3.5)
    d += elm.Dot(open=True).label("MCU capture\nPTB3 / FTM1_CH1", "right")

    d += elm.Resistor().down().at(node.center).length(1.6).label("R2\n16k",
                                                                   loc="bottom")
    d += elm.Ground()

    d.push()
    d += elm.Line().right().at(node.center).length(1.3)
    d += elm.Dot()
    d += elm.Capacitor().down().label("C1\n22n", loc="bottom")
    d += elm.Ground()
    d.pop()

    d += elm.Line().right().at(node.center).length(2.6)
    d += elm.Dot()
    d += elm.Zener().down().label("D1\n3.3 V", loc="bottom")
    d += elm.Ground()

    # The sensor itself: open-collector to ground. Routed OFF to the left
    # of the R2/ground column below the node -- dropping it straight down
    # from node.center would stack it on top of R2's own ground symbol.
    # It IS a real netlist element (S1/HALLSW), not a dashed/undrawn part,
    # so it is drawn solid.
    hall_x = node.center[0] - 2.2
    d += elm.Line().left().at(node.center).tox(hall_x)
    d += elm.Line().down().length(1.0)
    d += (sw := elm.Switch().down())
    d += elm.Line().down().length(0.8)
    d += elm.Dot(open=True).label("pin 44, sensor gnd", "bottom")
    # loc= on this rotated element lands unpredictably (this file's own
    # trap, worked around everywhere else here too) -- explicit
    # coordinate, clear of both the switch glyph and the pin-44 label.
    d += elm.Label().at((sw.center[0] - 2.6, sw.center[1])).label(
        "Hall sensor\n(open collector)")

    d += elm.Label().at((hall_x - 2.2, node.center[1] - 6.2)).label(
        "R1/R2/C1/D1: identical values to sensor_ratiometric.cir's own\n"
        "5V_SENSOR front end -- same divider ratio, same filter corner,\n"
        "same clamp. Not a coincidence: pin 46 is not 5 V tolerant on this\n"
        "MCU (S32K1xx datasheet Vih max = VDD+0.3 V), so the spec's literal\n"
        "'pull-up to 5V_SENSOR' has to be divided into the 3.3 V domain\n"
        "before PTB3, the same treatment every other 5 V-rail input gets.")
    return "Cam signal front-end -- pins 45 / 46 / 44"


def sensor_differential(d):
    """Shared sensor ground on pin 34 -- single-ended divider plus a
    differential front end, both reading the boost sensor's output (sa),
    against two different references. This redraws the block: the
    previous version drew two resistor dividers joined by a plain wire,
    which matched neither the netlist nor any plausible physical circuit
    (see the 2026-09-18 schematic-drift report).

    sensor_differential.cir models ONE divider (R1/R2, 10k/16k, identical
    to sensor_ratiometric's -- single-ended, referenced to ECU ground)
    plus a behavioral gain block (Bd: 16/26 gain matched to that same
    ratio, plus an 80 dB CMRR term) standing in for a differential/
    instrumentation amplifier -- not a second resistor divider. Drawn
    here as a generic op-amp symbol, since the netlist doesn't model
    discrete gain-setting resistors for it and neither vendor studied in
    memo 09 published an internal schematic to draw instead.

    Rg (gs to ECU ground) is the netlist's actual subject: the shared
    harness + connector resistance in pin 34's return path, swept
    0.01-2 ohm by the check. It is a real, modelled part and is drawn
    solid. Ib (0 to gs, 20 mA) is also a real, modelled netlist element,
    but it is NOT drawn: it doesn't stand for a part of this front end at
    all, it's a stimulus representing the coolant sensor's own return
    current, injected into gs because the two channels share splice V3.
    The dashed convention is for a real part the netlist omits; Ib is the
    opposite (a modelled element that isn't a part here), so dashing it
    would claim the wrong thing about it. Captioned instead, the same way
    the previous drawing captioned it."""
    d += (sa := elm.Dot(open=True).label("SENSOR OUT\npin 41 (sa)", "left"))
    d += elm.Line().right().length(0.6)
    d += elm.Resistor().right().label("R1\n10k")
    d += (nse := elm.Dot())
    d += elm.Line().right().length(1.2)
    d += elm.Dot(open=True).label("MCU ADC\nsingle-ended", "right")
    d += elm.Resistor().down().at(nse.center).length(2.2).label("R2\n16k", loc="bottom")
    d += elm.Ground()

    d += (gs := elm.Dot(open=True).label("SENSOR GND\npin 34, shared (gs)", "left")
          .at((-3.2, -4.0)))
    d += elm.Line().right().at(gs.center).length(1.8)
    d += (gtap := elm.Dot())
    d += elm.Resistor().down().length(2.0).label(
        "Rg\nharness + contacts\n(swept 0.01-2 ohm)", loc="bottom")
    d += elm.Ground()
    d += elm.Label().at((gs.center[0] + 0.3, gs.center[1] - 3.8)).label(
        "Not drawn: Ib (netlist, 20 mA into gs) -- the coolant sensor's\n"
        "own return current, sharing this ground via splice V3. It is\n"
        "what moves gs; Rg is what decides how far it moves.")

    # amp sits well above row A (single-ended) so neither its wires nor
    # its top caption come near anything else -- the trap this file's
    # rotated/multi-anchor elements keep hitting.
    # sign=False: schemdraw's own +/- glyphs inherit the element's
    # rotation, and the minus renders as a bare vertical bar on an
    # op-amp oriented this way -- the same rotated-label trap as loc=.
    # Place both signs at explicit coordinates instead.
    d += (amp := elm.Opamp(sign=False).at((1.2, 4.5)))
    # This Opamp inherits the previous element's "down" direction, so it
    # is rotated: its inputs sit along the TOP edge, not the left one.
    # Offset the signs downward into the triangle, not sideways -- a +x
    # offset slides them along that edge and away from their own pins.
    # in1 takes the sensor signal, in2 the shared ground; getting these
    # the wrong way round inverts the measurement.
    d += elm.Label().at((amp.absanchors["in1"][0],
                         amp.absanchors["in1"][1] - 0.45)).label("+")
    d += elm.Label().at((amp.absanchors["in2"][0],
                         amp.absanchors["in2"][1] - 0.45)).label("−")
    d += elm.Line().up().at(sa.center).toy(amp.absanchors["in1"][1])
    d += elm.Line().right().tox(amp.absanchors["in1"][0])
    d += elm.Line().up().at(gs.center).toy(amp.absanchors["in2"][1])
    d += elm.Line().right().tox(amp.absanchors["in2"][0])
    d += elm.Line().right().at(amp.absanchors["out"]).length(1.2)
    d += elm.Dot(open=True).label("MCU ADC\ndifferential", "right")
    d += elm.Label().at((amp.absanchors["center"][0] - 0.9, amp.absanchors["center"][1] + 2.2)).label(
        "diff amp -- netlist's Bd: gain 16/26 (matches the single-\n"
        "ended ratio) plus a realistic 80 dB CMRR term")
    return "Differential sensor front-end -- rejects shared-ground offset"


def boost_converter(d):
    """Injector boost rail and its reservoir. L, D and the switch are
    drawn because the converter physically has them, but the netlist below
    is charge-balance only -- a current source standing in for all three
    (see the RESULT NOTE), so all three are dashed."""
    d += elm.Dot(open=True).label("BATT +\n13.5 V", "left")
    d += elm.Line().right().length(0.5)
    d += elm.Inductor2().right().linestyle("--").label("L")
    d += (sw := elm.Dot())
    d += elm.Diode().right().linestyle("--").label("D")
    d += (rail := elm.Dot().label("~100 V", "top"))
    d += elm.Line().right().length(1.5)
    d += elm.Dot(open=True).label("injector high side\npins 03 / 05", "right")

    d += elm.Switch().down().at(sw.center).linestyle("--")
    # loc= on this rotated element lands on top of the caption below --
    # pre-existing collision (the trap this file's other diodes/switches
    # already work around), fixed here rather than carried forward.
    d += elm.Label().at((sw.center[0] - 1.35, sw.center[1] - 1.0)).label(
        "boost\nswitch")
    d += elm.Ground()

    d += elm.Capacitor().down().at(rail.center).label("Cres\n47u")
    d += elm.Ground()

    d += elm.Label().at((rail.center[0] + 0.5, rail.center[1] - 3.1)).label(
        "reservoir supplies the 38 us peak phase only --\n"
        "hold current comes from the battery, 28x the charge")
    return "Injector boost rail -- the reservoir does the work"


def ntc_frontend(d):
    """U2's NTC branch -- pin 79."""
    d += elm.Dot(open=True).label("5V_SENSOR", "left")
    d += elm.Line().right().length(0.6)
    d += elm.Resistor().right().label("Rpu\n2k2")
    d += (n := elm.Dot())
    d += elm.Line().right().length(1.5)
    d += elm.Dot(open=True).label("MCU ADC", "right")

    d += elm.Thermistor().down().at(n.center).label("NTC\n2k5 at 25 C", loc="bottom")
    d += elm.Line().down().length(0.3)
    d += elm.Dot(open=True).label("pin 34", "bottom")

    d.push()
    d += elm.Line().right().at(n.center).length(1.0)
    d += elm.Dot()
    d += elm.Capacitor().down().label("C 22n", loc="bottom")
    d += elm.Ground()
    d.pop()
    d += elm.Label().at((n.center[0] + 0.4, n.center[1] - 3.2)).label(
        "divider, not a current source: 88R to 59k is 670:1,\n"
        "and a current source runs out of rail at the cold end")
    return "NTC temperature front-end -- pin 79, U2's NTC branch"


def metering_unit_pwm(d):
    """Fuel metering unit driver -- ECU pin 88."""
    d += elm.Dot(open=True).label("BATT + (fused 20 A, 8F1)", "top")
    d += elm.Line().right().length(0.6)
    d += (top := elm.Dot())
    d += elm.Inductor().down()
    d += (drain := elm.Dot())
    d += elm.Label().at((top.center[0] + 1.15, top.center[1] - 1.5)).label(
        "metering unit\n10R / 30 mH")

    d += elm.Line().left().at(top.center).length(1.8)
    d += elm.Diode().down().reverse().label("D1\nfreewheel", loc="left")
    d += elm.Line().right().tox(drain.center)

    d += (q := elm.NFet(bulk=False).at(drain.center).anchor("drain"))
    d += elm.Line().down().at(q.source).length(0.3)
    d += (sense := elm.Dot())
    d += elm.Resistor().down().label("R_sense")
    d += elm.Ground()
    d += elm.Line().right().at(q.gate).length(0.7).label(
        "PWM, pin 88", loc="right")
    return "Fuel metering unit driver -- pin 88, low-side PWM"


def can_termination(d):
    """CAN split termination, both channels."""
    d += elm.Dot(open=True).label("CAN H\nyellow", "left")
    d += elm.Line().right().length(0.6)
    d += (h := elm.Dot())
    d += elm.Line().right().length(1.8)
    d += elm.Dot(open=True).label("transceiver", "right")

    d += elm.Resistor().down().at(h.center).label("60R", loc="left")
    d += (mid := elm.Dot().label("split", "right"))
    d += elm.Resistor().down().label("60R", loc="left")
    d += (l := elm.Dot())
    d += elm.Line().right().length(1.8)
    d += elm.Dot(open=True).label("transceiver", "right")
    d += elm.Line().left().at(l.center).length(0.6)
    d += elm.Dot(open=True).label("CAN L\ngreen", "left")

    d += elm.Line().right().at(mid.center).length(1.2)
    d += elm.Dot()
    d += elm.Capacitor().down().label("4n7")
    d += elm.Ground()
    d += elm.Label().at((mid.center[0] + 1.0, mid.center[1] - 2.4)).label(
        "120R differential either way -- the cap is what\n"
        "gives common-mode noise somewhere to go")
    return "CAN split termination -- 120R differential, low-Z common mode"


def supervisor(d):
    """Fail-safe kill path -- watches 3V3_MCU, RESET drives (through one
    inverting stage) a kill FET at each protected gate, in parallel with
    a standing 10k Rgs pulldown. Research memo 11's Recommendation.

    The supervisor's comparator + open-drain RESET stage is drawn as one
    Ic block (elm.Ic) rather than four separate primitives -- what the
    netlist's SWK switch model actually captures is the KILL FET alone
    conducting once RESET has already commanded it on, not a claim that
    the comparator/RESET/inverter chain adds zero delay (see the
    netlist's header). The inverting stage and the driver + protected
    FET are drawn dashed: real parts on the board, not their own
    netlist elements here.

    One gate node is drawn -- the mechanism is identical at all six
    protected gates (pin 88 metering, 73/07/29 injector low side, 03/05
    injector bank high side).

    Two traps this file's own comments already name, both hit while
    building this one: elements inherit the PREVIOUS element's
    direction (the NFet silently rotated 90 degrees until `.right()`
    was added explicitly -- the same class of bug sensor_differential's
    docstring already warns about for the op-amp's sign glyphs); and
    two nodes placed with nearly-cancelling offsets landed on top of
    each other (the kill FET's drain ended up almost exactly under the
    RESET_b node the first time) -- avoided here by choosing offsets
    that keep every branch's column visibly separate rather than by
    coincidence."""
    ic = elm.Ic(
        pins=[
            elm.IcPin(name="SENSE", side="left", anchorname="sense"),
            elm.IcPin(name="GND", side="bottom", anchorname="gnd"),
            elm.IcPin(name="RESET", side="right", anchorname="reset"),
        ],
        size=(3.0, 2.2),
    ).label("supervisor\nTPS3850-class", "top")
    d += ic
    sense = ic.absanchors["sense"]
    reset = ic.absanchors["reset"]
    gndp = ic.absanchors["gnd"]
    d += elm.Ground().at(gndp)

    RAILY = sense[1] + 4.0
    r1 = (reset[0] + 1.3, reset[1])
    r2 = (r1[0] + 3.0, r1[1])

    # ---- monitored rail + open-drain pull-up ----
    d += elm.Line().up().at(sense).toy(RAILY)
    d += elm.Line().left().length(0.8)
    d += elm.Dot(open=True).label("3V3_MCU", "left")
    d += elm.Line().right().at((sense[0], RAILY)).tox(r1[0])
    d += elm.Resistor().up().at(r1).toy(RAILY).label("pull-up", loc="right")

    # ---- RESET_b junction ----
    d += elm.Line().right().at(reset).tox(r1[0])
    d += (r1dot := elm.Dot())
    d += elm.Label().at((r1dot.center[0] - 0.7, r1dot.center[1] - 0.55)).label(
        "RESET_b")

    # ---- also feeds the S32K148's own RESET_B pin, conventionally ----
    d += elm.Line().right().at(r1).tox(r2[0])
    d += elm.Dot()
    d += elm.Line().right().length(0.8)
    d += elm.Dot(open=True).label("to S32K148\nRESET_B", "right")

    # ---- through one inverting stage (dashed -- real part, not its own
    # netlist element here) into the kill FET's gate ----
    kg = (r2[0], r2[1] - 2.2)
    d += elm.Line().down().at(r2).toy(kg[1]).linestyle("--")
    d += elm.Label().at((r2[0] + 0.15, (r2[1] + kg[1]) / 2)).label("inv.")

    q = elm.NFet(bulk=False).right().at(kg).anchor("gate")
    d += q
    d += elm.Ground().at(q.source)
    d += elm.Dot().at(q.drain)

    # riser straight up from the drain -- nothing else may share this column
    gtop = (q.drain[0], RAILY - 0.8)
    d += elm.Line().up().at(q.drain).toy(gtop[1])
    d += elm.Dot(open=True)
    d += elm.Label().at((gtop[0] - 0.25, gtop[1] - 0.55)).label("gate node")

    # jog right off the riser before dropping into Rgs, so Rgs's own
    # ground symbol never lands back on the drain/source column above
    rgs_top = (gtop[0] + 1.6, gtop[1] - 0.6)
    d += elm.Line().at(gtop).to(rgs_top)
    d += elm.Resistor().down().length(1.4).label("Rgs\n10k", loc="right")
    d += elm.Ground()

    # dashed stub to the undrawn driver + protected FET, off the riser
    # itself, routed up first so it clears the Rgs jog below it
    d += elm.Line().up().at(gtop).length(0.7)
    d += elm.Line().right().length(1.8).linestyle("--")
    d += elm.Dot(open=True).linestyle("--").label("driver + FET", "right")

    d += elm.Label().at((0.0, -2.7)).label(
        "gate node drawn once -- identical kill FET + Rgs sit at all six\n"
        "protected gates: pin 88 (metering), 73/07/29 (injector low side),\n"
        "03/05 (injector bank high side). \"inv.\" and \"driver + FET\" are\n"
        "on the board but not their own netlist elements here -- claim 3's\n"
        "FAIL (see RESULT NOTE) is about Rgs, drawn and modelled as 10k.")
    return "Supervisor -- fail-safe kill path, watches 3V3_MCU"


BLOCKS = {
    "battery_sense": battery_sense,
    "discrete_input": discrete_input,
    "trip_module_sense": trip_module_sense,
    "sensor_ratiometric": sensor_ratiometric,
    "transient_clamp": transient_clamp,
    "load_dump": load_dump,
    "injector_boost": injector_boost,
    "injector_turnoff": injector_turnoff,
    "relay_driver": relay_driver,
    "egr_hbridge": egr_hbridge,
    "emi_filter": emi_filter,
    "reverse_battery": reverse_battery,
    "buck_preregulator": buck_preregulator,
    "sensor_rail": sensor_rail,
    "mcu_pdn": mcu_pdn,
    "vr_conditioner": vr_conditioner,
    "cam_frontend": cam_frontend,
    "sensor_differential": sensor_differential,
    "boost_converter": boost_converter,
    "ntc_frontend": ntc_frontend,
    "metering_unit_pwm": metering_unit_pwm,
    "can_termination": can_termination,
    "supervisor": supervisor,
}

# schemdraw writes literal black; swap for currentColor so the drawing
# inherits the surrounding text colour and works in either theme.
BLACK = re.compile(r'(stroke|fill)="(#000000|#000|black)"', re.I)


def main():
    for name, fn in BLOCKS.items():
        for ext in ("svg", "png"):
            with schemdraw.Drawing(show=False) as d:
                title = fn(d)
                d.save(str(OUT / f"{name}.{ext}"), dpi=200)
        svg = OUT / f"{name}.svg"
        svg.write_text(BLACK.sub(lambda m: f'{m.group(1)}="currentColor"', svg.read_text()))
        print(f"  {name:<22} {title}")
    print(f"\n{len(BLOCKS)} schematics -> {OUT}")


if __name__ == "__main__":
    main()
