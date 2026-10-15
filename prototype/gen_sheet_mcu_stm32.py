#!/usr/bin/env python3
"""mcu_stm32 sheet: STM32G474VET6 in place of the S32K148 (prototype).

Pin functions come from stm32_pins.ASSIGN (checked against ST's XML);
pin POSITIONS come from the stock KiCad symbol via symbols.stock_pins.
The supervisor, gate kill and debug header are production's own
functions, called unchanged, so the prototype's safety cut-off is the
production one:
  SWDIO -> JTAG_TMS, SWCLK -> JTAG_TCK, PA15 (JTDI) -> JTAG_TDI,
  NRST  -> ~{RESET} (the TPS3850's RESET), WDO -> WDT_FAULT (a GPIO).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(HERE, "..", "hw"))
import schlib  # noqa: E402
from schlib import Sheet, pin_xy, r2  # noqa: E402
import gen_sheet_mcu as prod  # noqa: E402
from stm32_pins import ASSIGN, PINDATA  # noqa: E402
from symbols import flatten, stock_pins, stub_dir  # noqa: E402

MCU = "MCU_ST_STM32G4:STM32G474VETx"
U_AT = (160.0, 200.0)
STUB = 10.16
S = 5.08                      # stub on the small parts
OUT = os.path.join(HERE, "mcu_stm32.kicad_sch")

C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
R0603 = "Resistor_SMD:R_0603_1608Metric"

RENAME = {"SWDIO": "JTAG_TMS", "SWCLK": "JTAG_TCK"}
SHAPE = {net: shape for net, shape in prod.NETS.values() if shape}
SHAPE["BOOST_MON"] = "input"


def pin_at(num):
    lx, ly, _, _ = stock_pins(MCU)[num]
    x, y = pin_xy(lx, ly, *U_AT, 0)
    return r2(x), r2(y)


def pin_end(pin, n=STUB):
    """Free end of the stub on an XML-named pin (e.g. "PF0-OSC_IN")."""
    num = PINDATA[pin]["position"]
    x, y = pin_at(num)
    dx, dy = stub_dir(stock_pins(MCU)[num][2])
    return r2(x + dx * n), r2(y + dy * n)


def stub(sh, x, y, angle, net, n, shape=None):
    """Wire out of a pin, ending in a label, a hierarchical label or GND."""
    dx, dy = stub_dir(angle)
    ex, ey = x + dx * n, y + dy * n
    sh.wire(x, y, ex, ey)
    rot = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[(dx, dy)]
    if net == "GND":
        sh.gnd(ex, ey)
    elif shape:
        sh.hlabel(net, ex, ey, shape=shape, rot=rot)
    else:
        sh.label(net, ex, ey, rot=rot)


def part(sh, libid, prefix, x, y, value, fp, nets, fields=None, ref=None):
    """Place a part and hang a labelled stub on each listed pin."""
    flatten(libid)            # before place(), which caches the symbol
    ref = sh.place(libid, prefix, x, y, value, footprint=fp,
                   fields=fields, ref=ref)
    pins = stock_pins(libid)
    for num, net in nets.items():
        lx, ly, a, _ = pins[num]
        stub(sh, *pin_xy(lx, ly, x, y, 0), a, net, S)
    return ref


def chip(sh):
    flatten(MCU)
    sh.place(MCU, "U", *U_AT, "STM32G474VETx", ref="U301",
             footprint="Package_QFP:LQFP-100_14x14mm_P0.5mm",
             fields={"MPN": "STM32G474VET6",
                     "Source": "prototype/docs/spec.md sec.3; pins from "
                               "prototype/stm32_pins.py (ST open pin data)"})
    pins = stock_pins(MCU)
    for sig, (pin, _) in ASSIGN.items():
        num = PINDATA[pin]["position"]
        net = RENAME.get(sig, sig)
        stub(sh, *pin_at(num), pins[num][2], net, STUB, SHAPE.get(net))
    special = {"PG10": "~{RESET}", "PB8": "BOOT0", "VREF+": "3V3_A",
               "VDDA": "3V3_A", "VSSA": "GND", "VBAT": "3V3_MCU"}
    done = set()
    for num, (lx, ly, a, name) in sorted(pins.items()):
        net = special.get(name) or {"VDD": "3V3_MCU", "VSS": "GND"}.get(name)
        if net is None or (lx, ly) in done:
            continue          # stacked VSS pins share one point
        done.add((lx, ly))
        stub(sh, *pin_at(num), a, net, STUB)


def support(sh):
    # -- decoupling: one 100 nF per VDD/VBAT pin, 4.7 uF, production bulk --
    x, y = 240.0, 60.0
    for i in range(6):
        part(sh, "Device:C", "C", x + i * 10.16, y, "100nF", C0402,
             {"1": "3V3_MCU", "2": "GND"},
             fields={"Source": "DS12288 / AN5093: 100 nF at each VDD pin"})
    part(sh, "Device:C", "C", x + 60.96, y, "4.7uF", C0805,
         {"1": "3V3_MCU", "2": "GND"},
         fields={"Source": "AN5093: 4.7 uF bulk on VDD"})
    part(sh, "Device:C_Polarized", "C", x + 76.2, y, "150uF", "",
         {"1": "3V3_MCU", "2": "BULK_RTN"}, ref="C313",
         fields={"Source": "production mcu sheet: mcu_pdn.cir bulk, kept"})
    part(sh, "Device:R", "R", x + 86.36, y, "22mOhm 1%", "",
         {"1": "BULK_RTN", "2": "GND"}, ref="R306",
         fields={"Source": "production mcu sheet: mcu_pdn.cir Rb, kept"})
    # the sheet's supply input, as production exports it
    sh.wire(x + 96.52, y - 10.16, x + 101.6, y - 10.16)
    sh.label("3V3_MCU", x + 101.6, y - 10.16)
    sh.hlabel("3V3_MCU", x + 96.52, y - 10.16, shape="input", rot=180)
    # -- analog supply through a ferrite --
    x, y = 240.0, 95.0
    part(sh, "Device:FerriteBead_Small", "FB", x, y, "600R@100MHz",
         "Inductor_SMD:L_0805_2012Metric", {"1": "3V3_MCU", "2": "3V3_A"},
         fields={"Source": "AN5093: VDDA/VREF+ filtered from VDD"})
    for i, val in enumerate(("1uF", "100nF", "1uF", "100nF")):
        part(sh, "Device:C", "C", x + 15.24 + i * 10.16, y, val,
             C0603 if val == "1uF" else C0402, {"1": "3V3_A", "2": "GND"},
             fields={"Source": "AN5093: 1 uF + 100 nF on VDDA and on VREF+"})
    # -- clock: 8 MHz HSE, CL 10 pF crystal, 2 x 12 pF (2 x (CL - 4 pF stray)) --
    x, y = 250.0, 150.0
    part(sh, "Device:Crystal_GND24", "Y", x, y, "8MHz CL10pF",
         "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
         {"1": "OSC_IN", "3": "OSC_OUT", "2": "GND", "4": "GND"},
         fields={"Spec": "8 MHz, 3225, CL 10 pF, +/-20 ppm, ESR <= 80 ohm "
                         "(AN2867 gm margin on the G4 HSE)"})
    for i, net in enumerate(("OSC_IN", "OSC_OUT")):
        part(sh, "Device:C", "C", x + 15.24 + i * 10.16, y, "12pF", C0402,
             {"1": net, "2": "GND"},
             fields={"Source": "CL = C/2 + 4 pF stray -> 12 pF for CL 10 pF"})
    # -- reset and boot --
    x, y = 330.0, 150.0
    part(sh, "Device:C", "C", x, y, "100nF", C0402, {"1": "~{RESET}", "2": "GND"},
         fields={"Source": "RM0440 NRST: 100 nF filter"})
    part(sh, "Device:R", "R", x + 10.16, y, "10k", R0603, {"1": "BOOT0", "2": "GND"},
         fields={"Source": "BOOT0 low: boot from flash"})
    # -- battery monitor: production's 120k/10k divider, 40 V -> 3.08 V --
    x, y = 330.0, 200.0
    part(sh, "Device:R", "R", x, y, "120k", R0603, {"1": "VBAT_PROT", "2": "VBAT_MON"})
    part(sh, "Device:R", "R", x + 10.16, y, "10k", R0603, {"1": "VBAT_MON", "2": "GND"})
    part(sh, "Device:C", "C", x + 20.32, y, "22nF", C0402, {"1": "VBAT_MON", "2": "GND"})
    # -- LEDs: 3V3 present, firmware status --
    x, y = 250.0, 220.0
    for i, (drive, node) in enumerate((("3V3_MCU", "LED_PWR_A"),
                                       ("LED_STATUS", "LED_STAT_A"))):
        part(sh, "Device:R", "R", x + i * 25.4, y, "1k", R0603,
             {"1": drive, "2": node})
        part(sh, "Device:LED", "D", x + i * 25.4 + 10.16, y + 15.24, "green",
             "LED_SMD:LED_0603_1608Metric", {"2": node, "1": "GND"})
    # -- USB-C, data only: VBUS reaches the ESD array and nothing else --
    x, y = 470.0, 80.0
    part(sh, "Connector:USB_C_Receptacle_USB2.0_14P", "J", x, y, "USB-C",
         "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
         {"A4": "USB_VBUS", "A5": "USB_CC1", "B5": "USB_CC2",
          "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM",
          "A1": "GND", "S1": "GND"}, ref="J302",
         fields={"MPN": "USB4105-GF-A",
                 "Note": "Data only: VBUS is not a supply (spec sec.3)"})
    part(sh, "Power_Protection:USBLC6-2SC6", "U", x + 50.8, y, "USBLC6-2SC6",
         "Package_TO_SOT_SMD:SOT-23-6",
         {"1": "USB_DP", "6": "USB_DP", "3": "USB_DM", "4": "USB_DM",
          "5": "USB_VBUS", "2": "GND"}, ref="U303",
         fields={"MPN": "USBLC6-2SC6"})
    for i, net in enumerate(("USB_CC1", "USB_CC2")):
        part(sh, "Device:R", "R", x + i * 10.16, y + 45.72, "5.1k", R0603,
             {"1": net, "2": "GND"},
             fields={"Source": "USB-C sink: Rd 5.1 k on each CC"})
    # -- SWO to the debug header's pin 6, which production leaves open --
    px, py = pin_xy(*prod.SWD["6"], *prod.DBG_AT, 0)
    sh.wire(px, py, px + STUB, py)
    sh.label("SWO", px + STUB, py)
    sh.text("Prototype: SWO (PB3) is wired to pin 6", px + 3.81, py + 3.81, size=1.0)


def build():
    schlib.verify_pins()
    sh = Sheet("STM32G474, supervisor and debug (prototype)", paper=prod.PAPER,
               comments=["Generated by prototype/gen_sheet_mcu_stm32.py",
                         "Pins: prototype/stm32_pins.py, checked against "
                         "ST's open pin data",
                         "Supervisor and debug port: hw/gen_sheet_mcu.py, "
                         "called unchanged"],
               ref_base=schlib.REF_BASE["mcu"])
    chip(sh)               # first, as production: U301 is the MCU
    prod.supervisor(sh)
    prod.debug_port(sh)
    support(sh)
    return sh


if __name__ == "__main__":
    print(build().write(OUT, force=True))
