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


BLOCKS = {
    "battery_sense": battery_sense,
    "discrete_input": discrete_input,
    "sensor_ratiometric": sensor_ratiometric,
    "transient_clamp": transient_clamp,
    "injector_boost": injector_boost,
    "relay_driver": relay_driver,
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
