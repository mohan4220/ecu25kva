#!/usr/bin/env python3
"""STM32G474VET6 pin assignment, checked against ST's own pin data.

Every function named here must appear on that pin in ST's open pin data
(the XML CubeMX reads), vendored in prototype/lib with its checksum. The
signal names are the production mcu sheet's, so the eight production
sheets connect to this chip unchanged.

Run: .venv/bin/python prototype/stm32_pins.py   (prints problems, exit 1)
"""
import os
import sys
import xml.etree.ElementTree as ET

XML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib",
                   "STM32G474V(B-C-E)Tx.xml")
_NS = {"m": "http://dummy.com"}


def _parse():
    root = ET.parse(XML).getroot()
    return {p.get("Name"): {"position": p.get("Position"),
                            "type": p.get("Type"),
                            "signals": {s.get("Name")
                                        for s in p.findall("m:Signal", _NS)}}
            for p in root.findall("m:Pin", _NS)}


PINDATA = _parse()

# signal -> (pin, function). Pin names are ST's, as in the XML.
ASSIGN = {
    # --- analog, 17 channels on distinct ADC inputs ---
    "V_BAT_1R_SNS":  ("PA0", "ADC1_IN1"),
    "V_BAT_2R_SNS":  ("PA1", "ADC1_IN2"),
    "ISNS_INJ_A":    ("PA2", "ADC1_IN3"),
    "ISNS_INJ_B":    ("PA3", "ADC1_IN4"),
    "ISNS_MU":       ("PA6", "ADC2_IN3"),
    "ISNS_EGR":      ("PA7", "ADC2_IN4"),
    "BOOST_P":       ("PC0", "ADC1_IN6"),
    "BOOST_T":       ("PC1", "ADC1_IN7"),
    "COOLANT_T":     ("PC2", "ADC1_IN8"),
    "EGR_POS":       ("PC3", "ADC1_IN9"),
    "OIL_P":         ("PC4", "ADC2_IN5"),
    "RAIL_P":        ("PC5", "ADC2_IN11"),
    "BARO":          ("PB0", "ADC1_IN15"),
    "SENSOR_5V_MON": ("PB1", "ADC1_IN12"),
    "TRIP_SENSE":    ("PB2", "ADC2_IN12"),
    "BOOST_MON":     ("PB11", "ADC1_IN14"),
    "VBAT_MON":      ("PB12", "ADC1_IN11"),
    # --- crank and cam: one 32-bit timer's input capture ---
    "CRANK_EDGE":    ("PD4", "TIM2_CH2"),
    "CAM_EDGE":      ("PD7", "TIM2_CH3"),
    # --- injector stage and metering valve: advanced timers TIM8/TIM20 ---
    "INJ_LS_1":      ("PC6", "TIM8_CH1"),
    "INJ_LS_2":      ("PC7", "TIM8_CH2"),
    "INJ_LS_3":      ("PC8", "TIM8_CH3"),
    "INJ_HS_A":      ("PC9", "TIM8_CH4"),
    "INJ_HS_B":      ("PE2", "TIM20_CH1"),
    "INJ_HS_A_BAT":  ("PE3", "TIM20_CH2"),
    "INJ_HS_B_BAT":  ("PF2", "TIM20_CH3"),
    "MU_PWM":        ("PE1", "TIM20_CH4"),
    # --- EGR bridge on TIM1 ---
    "EGR_IN1":       ("PA8", "TIM1_CH1"),
    "EGR_IN2":       ("PA9", "TIM1_CH2"),
    "EGR_EN":        ("PA10", "TIM1_CH3"),
    # --- discrete ---
    "SW_COOLANT":    ("PE4", "GPIO_Input"),
    "SW_DROOP":      ("PE5", "GPIO_Input"),
    "IN_AUDIO_ABORT": ("PE6", "GPIO_Input"),
    "IN_OVERRIDE_SS": ("PE0", "GPIO_Input"),
    "IN_IGNITION":   ("PC10", "GPIO_Input"),
    "RLY_MAIN":      ("PD5", "GPIO_Output"),
    "RLY_BUZZER":    ("PD15", "GPIO_Output"),
    "WDT_KICK":      ("PC11", "GPIO_Output"),
    "WDT_FAULT":     ("PC12", "GPIO_Input"),
    "LED_STATUS":    ("PB7", "GPIO_Output"),
    # --- CAN ---
    "CAN1_TX":       ("PD1", "FDCAN1_TX"),
    "CAN1_RX":       ("PD0", "FDCAN1_RX"),
    "CAN2_TX":       ("PB6", "FDCAN2_TX"),
    "CAN2_RX":       ("PB5", "FDCAN2_RX"),
    # --- USB, clock, debug ---
    "USB_DM":        ("PA11", "USB_DM"),
    "USB_DP":        ("PA12", "USB_DP"),
    "OSC_IN":        ("PF0-OSC_IN", "RCC_OSC_IN"),
    "OSC_OUT":       ("PF1-OSC_OUT", "RCC_OSC_OUT"),
    "SWDIO":         ("PA13", "SYS_JTMS-SWDIO"),
    "SWCLK":         ("PA14", "SYS_JTCK-SWCLK"),
    "SWO":           ("PB3", "SYS_JTDO-SWO"),
    # The production debug header carries TDI; PA15 is JTDI. Taking it
    # also keeps PA15 (pulled up at reset) away from every gate.
    "JTAG_TDI":      ("PA15", "SYS_JTDI"),
}

# Pins that come out of reset with a pull or as a strap: a gate driver
# here would see a level, not Hi-Z, before firmware runs.
RESET_PULLED = {"PA13", "PA14", "PA15", "PB3", "PB4", "PB8-BOOT0"}
GATE_PREFIX = ("INJ_", "MU_PWM", "EGR_", "RLY_")
INJ_STAGE = ("INJ_LS_1", "INJ_LS_2", "INJ_LS_3", "INJ_HS_A", "INJ_HS_B",
             "INJ_HS_A_BAT", "INJ_HS_B_BAT", "MU_PWM")
FIXED = {"USB_DM": "PA11", "USB_DP": "PA12", "OSC_IN": "PF0-OSC_IN",
         "OSC_OUT": "PF1-OSC_OUT", "SWDIO": "PA13", "SWCLK": "PA14",
         "SWO": "PB3"}


def _timer(fn):
    return fn.split("_")[0]


def check(assign=None):
    a = ASSIGN if assign is None else assign
    probs = []
    used = {}
    for sig, (pin, fn) in a.items():
        p = PINDATA.get(pin)
        if p is None or p["type"] != "I/O":
            probs.append(f"{sig}: {pin} is not an I/O pin")
            continue
        if fn not in ("GPIO_Input", "GPIO_Output") and fn not in p["signals"]:
            probs.append(f"{sig}: {fn} not available on {pin}")
        if pin in used:
            probs.append(f"{sig}: {pin} already used by {used[pin]}")
        used[pin] = sig
        if sig.startswith(GATE_PREFIX) and pin in RESET_PULLED:
            probs.append(f"{sig}: gate output on reset-pulled pin {pin}")
    adc = [fn for _, fn in a.values() if fn.startswith("ADC")]
    if len(adc) != len(set(adc)):
        probs.append("ADC input used twice")
    ic = [a[s][1] for s in ("CRANK_EDGE", "CAM_EDGE")]
    if {_timer(f) for f in ic} not in ({"TIM2"}, {"TIM5"}) or \
            not all("_CH" in f and not f.endswith("N") for f in ic):
        probs.append(f"crank/cam not on one TIM2/TIM5's channels: {ic}")
    for s in INJ_STAGE:
        f = a[s][1]
        if _timer(f) not in ("TIM1", "TIM8", "TIM20") or "_CH" not in f \
                or f.endswith("N"):
            probs.append(f"{s}: {f} is not a TIM1/8/20 output channel")
    for s in ("EGR_IN1", "EGR_IN2"):
        if "_CH" not in a[s][1]:
            probs.append(f"{s}: {a[s][1]} is not a PWM channel")
    for bus in ("1", "2"):
        for d in ("TX", "RX"):
            if a[f"CAN{bus}_{d}"][1] != f"FDCAN{bus}_{d}":
                probs.append(f"CAN{bus}_{d} not on FDCAN{bus}")
    for s, pin in FIXED.items():
        if a[s][0] != pin:
            probs.append(f"{s} must be on {pin}")
    return probs


if __name__ == "__main__":
    bad = check()
    print("\n".join(bad) or f"{len(ASSIGN)} signals, pin map sound")
    sys.exit(1 if bad else 0)
