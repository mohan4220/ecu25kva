#!/usr/bin/env python3
"""Every prototype test, assert-based.
Run: .venv/bin/python prototype/test_prototype.py [test_name ...]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(HERE, "..", "hw"))


# -- Task 1: pin assignment ------------------------------------------------
def test_pindata_parses():
    from stm32_pins import PINDATA
    assert len(PINDATA) >= 86, len(PINDATA)
    assert "ADC1_IN1" in PINDATA["PA0"]["signals"]


def test_assign_valid():
    import stm32_pins
    assert stm32_pins.check() == [], stm32_pins.check()


def test_gate_pins_float():
    import stm32_pins
    assert "TIM8_CH1" in stm32_pins.PINDATA["PA15"]["signals"]
    bad = dict(stm32_pins.ASSIGN, INJ_LS_1=("PA15", "TIM8_CH1"))
    bad["JTAG_TDI"] = ("PB4", "GPIO_Input")   # free PA15 so only the rule fires
    probs = stm32_pins.check(bad)
    assert any("INJ_LS_1" in p for p in probs), probs


def test_adc_count():
    from stm32_pins import ASSIGN
    adc = {f for _, f in ASSIGN.values() if f.startswith("ADC")}
    assert len(adc) == 17, sorted(adc)


# -- Task 2: the STM32 sheet ------------------------------------------------
def _hlabels(text):
    import re
    return set(re.findall(r'\(hierarchical_label "([^"]+)"', text))


def _label_points(text):
    import re
    return {(float(x), float(y)) for x, y in re.findall(
        r'\((?:hierarchical_label|label) "[^"]+"(?: \(shape \w+\))? '
        r'\(at ([-\d.]+) ([-\d.]+)', text)}


def test_stock_pins():
    from symbols import stock_pins
    p = stock_pins("MCU_ST_STM32G4:STM32G474VETx")
    assert len(p) == 100
    assert p["20"][3] == "PA0"          # LQFP-100 position 20 (ST's XML)


def test_mcu_labels():
    import gen_sheet_mcu_stm32
    prod = _hlabels(open(os.path.join(HERE, "..", "hw", "mcu.kicad_sch")).read())
    assert len(prod) == 42
    got = _hlabels(gen_sheet_mcu_stm32.build().render())
    assert got == prod | {"BOOST_MON"}, (got ^ (prod | {"BOOST_MON"}))


def test_mcu_every_assigned_pin_wired():
    import gen_sheet_mcu_stm32 as g
    from stm32_pins import ASSIGN
    pts = _label_points(g.build().render())
    for sig, (pin, _) in ASSIGN.items():
        end = g.pin_end(pin)
        assert end in pts, (sig, pin, end)


def test_mcu_supplies():
    import gen_sheet_mcu_stm32 as g
    from symbols import stock_pins
    text = g.build().render()
    for num, (_, _, _, name) in stock_pins(g.MCU).items():
        if name.startswith(("VDD", "VSS", "VREF", "VBAT")):
            x, y = g.pin_at(num)
            assert f"(xy {x} {y})" in text, (num, name)


def test_pdn_stm32():
    """The prototype's decoupling (6 x 100 nF + 4.7 uF + production's bulk
    pair) stays under mcu_pdn.cir's own 100 mOhm target at both ends of
    the bulk pair's ESR band, to 100 MHz (the model's validity limit)."""
    import pathlib
    import tempfile
    sys.path.insert(0, os.path.join(HERE, "..", "sim", "lib"))
    import ngrun
    cir = pathlib.Path(HERE, "sim", "mcu_pdn_stm32.cir").read_text()
    wd = pathlib.Path(tempfile.mkdtemp(prefix="pdn_stm32_"))
    ngrun.run(cir, wd)
    d = ngrun.read_wrdata(wd / "mcu_pdn_stm32.dat", ["f", "cold", "warm"])
    for k in ("cold", "warm"):
        peak = max(d[k])
        assert peak < 0.100, (k, peak)
        print(f"  {k}: peak {peak * 1000:.1f} mOhm")


# -- Task 3: lab terminals --------------------------------------------------
def test_lab_labels():
    import gen_sheet_lab_io
    prod = _hlabels(open(os.path.join(HERE, "..", "hw",
                                      "connector.kicad_sch")).read())
    assert len(prod) == 40
    got = _hlabels(gen_sheet_lab_io.build().render())
    assert got == prod | {"TRIP_LOOP"}, got ^ (prod | {"TRIP_LOOP"})


def test_lab_power_ground():
    import gen_sheet_lab_io as g
    gnd = [(ref, pos) for ref, nets in g.TERMINALS.items()
           for pos, net in enumerate(nets, 1) if net == "GND"]
    assert len(gnd) >= 3, gnd
    assert sum(ref == "J1002" for ref, _ in gnd) == 2, gnd


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(n for n in globals() if n.startswith("test_"))
    for n in names:
        globals()[n]()
        print("ok", n)
    print("prototype ok")
