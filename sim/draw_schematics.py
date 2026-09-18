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
    """ECU pins 04/06 -- 6-40 V rail scaled into a 3.3 V ADC."""
    d += elm.Dot(open=True).label("BATT\n6-40 V", "left")
    d += elm.Line().right().length(0.6)
    d += (r1 := elm.Resistor().right().label("R1\n120k"))
    d += (node := elm.Dot())
    d += elm.Line().right().length(1.4)
    d += elm.Dot(open=True).label("MCU ADC", "right")
    d += elm.Resistor().down().at(node.center).label("R2\n10k")
    d += elm.Ground()
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
    """Battery input protection -- ISO 7637-2 pulse 2a."""
    d += elm.Dot(open=True).label("BATT +\npin 21", "left")
    d += elm.Line().right().length(0.5)
    d += elm.Inductor2().right().label("FB1\nferrite")
    d += elm.Fuse().right().label("F1\n5 A")
    d += (node := elm.Dot())
    d += elm.Line().right().length(1.6)
    d += elm.Dot(open=True).label("to buck\nVIN", "right")

    d += elm.Line().down().at(node.center).length(0.4)
    d += (tvs := elm.Dot())
    d += elm.DiodeShockley().down().label("D1  TVS\nSMBJ33CA", loc="bottom")
    d += elm.Ground()

    d += elm.Line().right().at(tvs.center).length(1.5)
    d += elm.Dot()
    d += elm.Capacitor().down().label("C1\n10u")
    d += elm.Ground()
    return "Transient clamp -- battery input, ISO 7637-2"


def load_dump(d):
    """Battery input protection -- ISO 7637-2 pulse 5b, same physical stage
    as transient_clamp, a much longer and more energetic pulse."""
    d += elm.Dot(open=True).label("BATT +\npin 21", "left")
    d += elm.Line().right().length(0.5)
    d += elm.Inductor2().right().label("FB1\nferrite")
    d += elm.Fuse().right().label("F1\n5 A")
    d += (node := elm.Dot())
    d += elm.Line().right().length(1.6)
    d += elm.Dot(open=True).label("to buck\nVIN", "right")

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
        "D1 absorbs ~46 J at ~116 W -- FAILS an SMBJ-class part's rating")
    return "Load dump -- battery input, ISO 7637-2 pulse 5b"


def injector_boost(d):
    """ECU pins 03/05 high side, 73/07/29 low side."""
    d += elm.Dot(open=True).label("BOOST RAIL\n~100 V", "left")
    d += elm.Line().right().length(0.7)
    d += (hs := elm.Switch().right().label("high side\npin 03 / 05"))
    d += elm.Line().right().length(0.5)
    d += elm.Dot(open=True).label("INJECTOR", "top")
    d += elm.Inductor().right().label("L\n200u")
    d += elm.Resistor().right().label("R\n0.5")
    d += elm.Line().right().length(0.5)
    d += elm.Switch().right().label("low side\npin 73 / 07 / 29")
    d += elm.Line().right().length(0.5)
    d += (sense := elm.Dot())
    d += elm.Resistor().down().label("R_sense\ncurrent fb")
    d += elm.Ground()
    return "Injector drive -- bank high side, per-cylinder low side"


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


def emi_filter(d):
    """Power chain stage 1 -- CISPR 25 differential input filter."""
    d += elm.Dot(open=True).label("BATT +\npin 21", "left")
    d += elm.Line().right().length(0.5)
    d += elm.Inductor2().right().label("L1\n22u")
    d += (n1 := elm.Dot())
    d += elm.Inductor2().right().at(n1.center).label("FB1\nferrite 0.5u / 120R")
    d += (n2 := elm.Dot())
    d += elm.Line().right().length(3.4)
    d += elm.Dot(open=True).label("to reverse-\nbattery stage", "right")

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
    """Power chain stage 2 -- ideal-diode controller and P-FET."""
    d += elm.Dot(open=True).label("BATT +\nfrom filter", "left")
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

    d += elm.Label().at((n.center[0] + 0.9, n.center[1] + 0.7)).label(
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

    d += elm.Capacitor().down().at(rail.center).label("Cbulk 47u\nESR 50m")
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


def sensor_differential(d):
    """Shared sensor ground on pin 34 -- differential front-end."""
    d += elm.Dot(open=True).label("SENSOR OUT\npin 41", "left")
    d += elm.Line().right().length(0.6)
    d += elm.Resistor().right().label("R1 10k")
    d += (hi := elm.Dot())
    d += elm.Line().right().length(1.5)
    d += elm.Dot(open=True).label("diff amp +", "right")

    d += elm.Line().down().at(hi.center).length(1.6)
    d += (lo := elm.Dot())
    d += elm.Line().right().length(1.5)
    d += elm.Dot(open=True).label("diff amp -", "right")

    d += elm.Resistor().left().at(lo.center).label("R3 10k")
    d += elm.Line().left().length(0.6)
    d += elm.Dot(open=True).label("SENSOR GND\npin 34 (shared)", "left")

    d += elm.Label().at((lo.center[0] - 1.0, lo.center[1] - 1.3)).label(
        "pin 34 is spliced to the coolant sensor -- its current\n"
        "moves this node, and single-ended reads that as signal")
    return "Differential sensor front-end -- rejects shared-ground offset"


def boost_converter(d):
    """Injector boost rail and its reservoir."""
    d += elm.Dot(open=True).label("BATT +\n13.5 V", "left")
    d += elm.Line().right().length(0.5)
    d += elm.Inductor2().right().label("L")
    d += (sw := elm.Dot())
    d += elm.Diode().right().label("D")
    d += (rail := elm.Dot().label("~100 V", "top"))
    d += elm.Line().right().length(1.5)
    d += elm.Dot(open=True).label("injector high side\npins 03 / 05", "right")

    d += elm.Switch().down().at(sw.center).label("boost\nswitch", loc="left")
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


BLOCKS = {
    "battery_sense": battery_sense,
    "discrete_input": discrete_input,
    "sensor_ratiometric": sensor_ratiometric,
    "transient_clamp": transient_clamp,
    "load_dump": load_dump,
    "injector_boost": injector_boost,
    "relay_driver": relay_driver,
    "emi_filter": emi_filter,
    "reverse_battery": reverse_battery,
    "buck_preregulator": buck_preregulator,
    "sensor_rail": sensor_rail,
    "mcu_pdn": mcu_pdn,
    "vr_conditioner": vr_conditioner,
    "sensor_differential": sensor_differential,
    "boost_converter": boost_converter,
    "ntc_frontend": ntc_frontend,
    "metering_unit_pwm": metering_unit_pwm,
    "can_termination": can_termination,
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
