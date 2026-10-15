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


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(n for n in globals() if n.startswith("test_"))
    for n in names:
        globals()[n]()
        print("ok", n)
    print("prototype ok")
