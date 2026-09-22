#!/usr/bin/env python3
"""mcu sheet: S32K148, its decoupling, the supervisor, and the debug port.

Pin assignments are docs/pinmap.md's, and pin POSITIONS come from
hw/lib/s32k148_layout.json, which hw/gen_symbols.py writes when it draws
the symbol. Neither is re-derived here -- a wire stub that misses its pin
by 1.27 mm still plots as a wire.

TWO ADDITIONS TO THE PIN MAP ARE MADE HERE, and both are gaps rather than
changes. pinmap.md assigns 37 signals and none of them services the
external watchdog, but memo 11's supervisor topology requires the MCU to
kick it -- a window watchdog nobody feeds resets the board on a timer.
So:

    PTE0  WDT_KICK   MCU -> TPS3850 WDI   (falling edge inside the window)
    PTE1  WDT_FAULT  TPS3850 WDO -> MCU   (so firmware can read that the
                                           watchdog, not the rail, tripped)

Both are free GPIO-HD pins on the 144-LQFP, PE=0/PS=0 at reset, taken
from the 91 the pin map leaves spare.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import schlib
from schlib import Sheet, pin_xy, PINS

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "mcu.kicad_sch")
LAYOUT = json.load(open(os.path.join(HW, "lib", "s32k148_layout.json")))
# The layout map is keyed by package pin (six pins are called VDD), so
# build the port -> entry view this sheet wants.
BY_PORT = {v["port"]: dict(v, pin=k) for k, v in LAYOUT.items()
           if v["port"].startswith("PT")}
SUPPLY = [dict(v, pin=k) for k, v in LAYOUT.items()
          if not v["port"].startswith("PT")]

MCU = "ecu25kva:S32K148_144LQFP"
SUP = "ecu25kva:TPS3850G33"
STUB = 22.86          # wire stub from pin to its label
FP144 = "Package_QFP:LQFP-144_20x20mm_P0.5mm"

# port -> (net name, hierarchical shape). shape "" means the net stays on
# this sheet. Names are pinmap.md's signals, shortened to net names.
NETS = {
    # --- analog, 14 channels (pinmap sec.1) ---
    "PTA0":  ("V_BAT_1R_SNS", "input"),   "PTA2":  ("V_BAT_2R_SNS", "input"),
    "PTA1":  ("BOOST_P", "input"),        "PTA3":  ("BOOST_T", "input"),
    "PTA6":  ("COOLANT_T", "input"),      "PTA15": ("EGR_POS", "input"),
    "PTA7":  ("OIL_P", "input"),          "PTA16": ("RAIL_P", "input"),
    "PTC14": ("SENSOR_5V_MON", "input"),  "PTD18": ("BARO", "input"),
    "PTC15": ("ISNS_INJ_A", "input"),     "PTD19": ("ISNS_INJ_B", "input"),
    "PTC16": ("ISNS_MU", "input"),        "PTD22": ("ISNS_EGR", "input"),
    # --- speed inputs ---
    "PTB2":  ("CRANK_EDGE", "input"),     "PTB3":  ("CAM_EDGE", "input"),
    # --- injector and actuator drive ---
    "PTC0":  ("INJ_HS_A", "output"),      "PTC1":  ("INJ_HS_B", "output"),
    "PTC2":  ("INJ_LS_1", "output"),      "PTC3":  ("INJ_LS_3", "output"),
    "PTB4":  ("INJ_LS_2", "output"),      "PTD10": ("MU_PWM", "output"),
    "PTB8":  ("EGR_IN1", "output"),       "PTB9":  ("EGR_IN2", "output"),
    # ADDED 21 Sep 2026. A discrete peak-and-hold stage needs TWO
    # high-side switches per bank -- boost for the peak phase, battery
    # for hold -- and the pin map had allocated one. See pinmap.md
    # sec.1.5's correction and hw/injector.kicad_sch. Both are FTM0
    # channels like the five already here, so the whole injector stage
    # stays on one timer and its edges stay phase-locked to each other.
    "PTB5":  ("INJ_HS_A_BAT", "output"),  "PTA17": ("INJ_HS_B_BAT", "output"),
    # ADDED 22 Sep 2026: the EGR bridge's shared shutdown. Pulled low on
    # metering_egr so the bridge COASTS while this pin is Hi-Z at reset;
    # the MCU raises it to drive. FTM3_CH2, the same timer as EGR_IN1/IN2.
    "PTB10": ("EGR_EN", "output"),
    # --- discrete in ---
    "PTD5":  ("SW_COOLANT", "input"),     "PTD7":  ("SW_DROOP", "input"),
    "PTD11": ("IN_AUDIO_ABORT", "input"), "PTD12": ("IN_OVERRIDE_SS", "input"),
    "PTD16": ("IN_IGNITION", "input"),
    # Trip sense moved PTD6 -> PTB0 on 20 Sep 2026: the loop is
    # three-state and a GPIO reads two. See pinmap.md sec.1.4.
    "PTB0":  ("TRIP_SENSE", "input"),
    # --- discrete out ---
    "PTD13": ("RLY_MAIN", "output"),      "PTD14": ("RLY_BUZZER", "output"),
    # --- CAN ---
    "PTE4":  ("CAN1_RX", "input"),        "PTE5":  ("CAN1_TX", "output"),
    "PTC6":  ("CAN2_RX", "input"),        "PTC7":  ("CAN2_TX", "output"),
    # --- on-sheet: debug, reset, watchdog ---
    "PTA5":  ("~{RESET}", ""),            "PTA4":  ("JTAG_TMS", ""),
    "PTC4":  ("JTAG_TCK", ""),            "PTC5":  ("JTAG_TDI", ""),
    "PTE0":  ("WDT_KICK", ""),            "PTE1":  ("WDT_FAULT", ""),
}

# A2, not A3. Six 25-pin units plus a supervisor, a debug header and an
# eleven-part decoupling network do not fit an A3 page without stacking
# things on top of each other, and a schematic whose parts overlap is one
# nobody reads. Two rows of three, with the right-hand column of the page
# left for the supervisor, the kill inverter and the debug port.
PAPER = "A2"                      # 594 x 420 mm
UNIT_AT = {1: (95, 78), 2: (270, 78), 3: (445, 78),
           4: (95, 232), 5: (270, 232), 6: (445, 232)}
SUP_AT = (120, 345)
INV_AT = (295, 340)
DBG_AT = (385, 330)
DEC_AT = (400, 395)


def place_units(sh):
    """One symbol instance per unit, sharing a reference."""
    at = {}
    for u in sorted(UNIT_AT):
        x, y = UNIT_AT[u]
        # Every unit is the SAME component -- one part, six units.
        ref = sh.place(MCU, "U", x, y, "S32K148_144LQFP", unit=u, ref="U301",
                       footprint=FP144,
                       fields={"MPN": "FS32K148HAT0MLQT",
                               "Source": "docs/research/05-mcu-selection.md; "
                                         "pins from refs/s32k148-144lqfp-pins.csv"})
        at[u] = (x, y, ref)
    return at


def stub_and_label(sh, port, at):
    """Wire a pin out to a label, on the side the pin is actually on."""
    L = BY_PORT[port]
    x, y, _ = at[L["unit"]]
    px, py = x + L["dx"], y + L["dy"]
    net, shape = NETS[port]
    # ONE label per pin. An earlier version emitted a plain label AND a
    # hierarchical label 2.54 mm apart, which names the same net twice
    # and prints the name on top of itself.
    left = L["side"] == "L"
    ex = px - STUB if left else px + STUB
    rot = 180 if left else 0
    sh.wire(px, py, ex, py)
    if shape:
        sh.hlabel(net, ex, py, shape=shape, rot=rot)
    else:
        sh.label(net, ex, py, rot=rot)


def build():
    schlib.verify_pins()
    sh = Sheet("MCU, supervisor and debug", paper=PAPER,
               comments=[
                   "Generated by hw/gen_sheet_mcu.py -- do not hand-edit until it is retired",
                   "Pin assignments: docs/pinmap.md. Pin positions: hw/lib/s32k148_layout.json",
                   "Supervisor TPS3850G33: memo 11 sec.2.1 + TI SBVS301B Table 5-1",
                   "PTE0/PTE1 are added here -- pinmap.md assigns no watchdog pins",
               ],
               ref_base=schlib.REF_BASE["mcu"])
    at = place_units(sh)
    for port in NETS:
        stub_and_label(sh, port, at)
    wire_supplies(sh, at)
    supervisor(sh)
    decoupling(sh)
    debug_port(sh)
    notes(sh)
    return sh, at


def wire_supplies(sh, at):
    """Unit 6's sixteen power pins. VDD/VDDA/VREFH to 3V3_MCU, VSS/VREFL
    to ground -- all of them, not a representative one, because the
    footprint has all of them and an unconnected supply pin is a real
    defect that ERC is the only thing likely to catch."""
    x, y, _ = at[6]
    for e in SUPPLY:
        px, py = x + e["dx"], y + e["dy"]
        left = e["side"] == "L"
        ex = px - STUB if left else px + STUB
        sh.wire(px, py, ex, py)
        net = "GND" if e["port"] in ("VSS", "VREFL") else "3V3_MCU"
        sh.label(net, ex, py, rot=180 if left else 0)


def supervisor(sh):
    """TPS3850G33 watching 3V3_MCU, plus the inverting stage that turns
    its active-low RESET into an active-high GATE_KILL."""
    sx, sy = SUP_AT
    sh.place(SUP, "U", sx, sy, "TPS3850G33",
             footprint="Package_SON:VSON-10-1EP_3x3mm_P0.5mm_EP1.2x2mm",
             fields={"MPN": "TPS3850G33DRCT",
                     "Source": "memo 11 sec.2.1; TI SBVS301B Table 5-1",
                     "Note": "G33: UV 3.168 V nom / 3.143 V worst-low, "
                             "clear of the S32K148's 3.0 V LVD max and "
                             "2.97 V correctness floor"})
    half = (6 - 1) * 2.54 / 2
    top = half + 2.54
    lx, rx = sx - 12.7 - 5.08, sx + 12.7 + 5.08
    lp = {n: (lx, sy - (half - i * 2.54))
          for i, (n, _, _) in enumerate(
              [("SENSE", 0, 0), ("WDI", 0, 0), ("CWD", 0, 0),
               ("CRST", 0, 0), ("SET0", 0, 0), ("SET1", 0, 0)])}
    rp = {n: (rx, sy - (half - i * 2.54))
          for i, n in enumerate(["~RESET", "~WDO"])}

    # VDD and GND come out the top and bottom of the body.
    sh.wire(sx, sy - top - 5.08, sx, sy - top - 10.16)
    sh.label("3V3_MCU", sx, sy - top - 10.16)
    sh.wire(sx, sy + top + 5.08, sx, sy + top + 10.16)
    sh.gnd(sx, sy + top + 10.16)

    # SENSE watches the rail it protects.
    px, py = lp["SENSE"]
    sh.wire(px, py, px - STUB, py)
    sh.label("3V3_MCU", px - STUB, py, rot=180)
    # WDI is kicked by the MCU; WDO reports a watchdog trip back to it.
    px, py = lp["WDI"]
    sh.wire(px, py, px - STUB, py)
    sh.label("WDT_KICK", px - STUB, py, rot=180)
    px, py = rp["~WDO"]
    sh.wire(px, py, px + STUB, py)
    sh.label("WDT_FAULT", px + STUB, py)

    # Open-drain outputs need pullups -- datasheet: "Connect RESET using
    # a 1-kOhm to 100-kOhm resistor to VDD."
    for name, (px, py), val in (("~RESET", rp["~RESET"], "10k"),
                                ("~WDO", rp["~WDO"], "10k")):
        ry = py - 15.24
        sh.place("Device:R", "R", px + 5.08, ry, val,
                 fields={"Source": "TPS3850 datasheet sec.5 -- open-drain "
                                   "output pullup, 1k-100k to VDD"})
        a = pin_xy(*PINS["Device:R"]["1"], px + 5.08, ry, 0)
        b = pin_xy(*PINS["Device:R"]["2"], px + 5.08, ry, 0)
        t, bo = (a, b) if a[1] < b[1] else (b, a)
        sh.wire(t[0], t[1], t[0], t[1] - 5.08)
        sh.label("3V3_MCU", t[0], t[1] - 5.08)
        sh.wire(bo[0], bo[1], bo[0], py)
        sh.wire(px, py, bo[0], py)
        sh.junction(bo[0], py)

    # RESET goes to the MCU's own RESET_b and to the kill inverter.
    px, py = rp["~RESET"]
    sh.wire(px, py, px + STUB + 10.16, py)
    sh.label("~{RESET}", px + STUB + 10.16, py)

    # Timing and strap pins are routed as a comb -- each goes left to its
    # own column, then down to its own part. Sharing a column stacked the
    # capacitors and their ground symbols on top of each other.
    comb = [
        ("CRST", "Device:C", "10nF", 25.4,
         "TPS3850 datasheet -- reset delay, Equation 3"),
        ("CWD", "Device:C", "10nF", 38.1,
         "TPS3850 datasheet -- watchdog upper boundary, Equation 6"),
        ("SET0", "Device:R", "0R", 50.8,
         "TPS3850 sec.6.6 -- window ratio strap. OPEN: the ratio depends "
         "on a firmware loop period that does not exist yet, phase 4"),
        ("SET1", "Device:R", "0R", 63.5,
         "TPS3850 sec.6.6 -- window ratio strap. OPEN: see SET0"),
    ]
    for name, libid, val, reach, src in comb:
        px, py = lp[name]
        cx = px - reach
        cy = sy + 30.48
        sh.wire(px, py, cx, py)
        sh.wire(cx, py, cx, cy - 3.81)
        sh.place(libid, "R" if libid == "Device:R" else "C", cx, cy, val,
                 fields={"Source": src})
        a = pin_xy(*PINS[libid]["1"], cx, cy, 0)
        b = pin_xy(*PINS[libid]["2"], cx, cy, 0)
        t, bo = (a, b) if a[1] < b[1] else (b, a)
        sh.wire(bo[0], bo[1], bo[0], bo[1] + 5.08)
        sh.gnd(bo[0], bo[1] + 5.08)

    # ---- the inverting stage, and the rail its pullup sits on ----
    qx, qy = INV_AT
    sh.place("Device:Q_NMOS_GSD", "Q", qx, qy, "60V logic-level N-ch",
             fields={"Source": "memo 11 Recommendation -- 'through one "
                               "inverting stage'; supervisor.cir models "
                               "the inverter and kill FET as one switch",
                     "Note": "RESET low (fault) turns this OFF, so the "
                             "pullup asserts GATE_KILL high"})
    qp = PINS["Device:Q_NMOS_GSD"]
    g = pin_xy(*qp["1"], qx, qy, 0)
    sr = pin_xy(*qp["2"], qx, qy, 0)
    d = pin_xy(*qp["3"], qx, qy, 0)
    sh.wire(g[0], g[1], g[0] - STUB, g[1])
    sh.label("~{RESET}", g[0] - STUB, g[1], rot=180)
    sh.wire(sr[0], sr[1], sr[0], sr[1] + 7.62)
    sh.gnd(sr[0], sr[1] + 7.62)
    sh.wire(d[0], d[1], d[0], d[1] - 7.62)
    sh.junction(d[0], d[1] - 7.62)

    ry = d[1] - 20.32
    sh.place("Device:R", "R", d[0], ry, "47k",
             fields={"Source": "kill-path pullup",
                     "Note": "Pulled to VBAT_PROT, NOT 3V3_MCU -- a pullup "
                             "on the rail being supervised has no supply "
                             "during the brownout it exists to catch"})
    a = pin_xy(*PINS["Device:R"]["1"], d[0], ry, 0)
    b = pin_xy(*PINS["Device:R"]["2"], d[0], ry, 0)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    sh.wire(t[0], t[1], t[0], t[1] - 5.08)
    sh.label("VBAT_PROT", t[0], t[1] - 5.08)
    sh.hlabel("VBAT_PROT", t[0], t[1] - 7.62, shape="input")
    sh.wire(bo[0], bo[1], bo[0], d[1] - 7.62)
    sh.wire(d[0], d[1] - 7.62, d[0] + 15.24, d[1] - 7.62)
    sh.label("GATE_KILL", d[0] + 15.24, d[1] - 7.62)
    sh.hlabel("GATE_KILL", d[0] + 17.78, d[1] - 7.62, shape="output")


def decoupling(sh):
    """mcu_pdn.cir's network: ten 100 nF ceramics and one 150 uF polymer
    bulk. The count is the design -- ESL divides by the number of
    packages sharing the current, and the block shows ten parts beating
    one part of the same total capacitance by 7.6x at 100 MHz."""
    x0, y0 = DEC_AT
    for i in range(10):
        x = x0 - i * 12.7
        sh.place("Device:C", "C", x, y0, "100nF",
                 fields={"Source": "mcu_pdn.cir -- one of ten; ESL 0.08 nH, "
                                   "ESR 3 mOhm modelled"})
        a = pin_xy(*PINS["Device:C"]["1"], x, y0, 0)
        b = pin_xy(*PINS["Device:C"]["2"], x, y0, 0)
        t, bo = (a, b) if a[1] < b[1] else (b, a)
        sh.wire(t[0], t[1], t[0], t[1] - 6.35)
        if i == 0:
            sh.label("3V3_MCU", t[0], t[1] - 6.35)
        else:
            sh.wire(t[0], t[1] - 6.35, t[0] + 12.7, t[1] - 6.35)
        sh.wire(bo[0], bo[1], bo[0], bo[1] + 6.35)
        if i == 0:
            sh.gnd(bo[0], bo[1] + 6.35)
        else:
            sh.wire(bo[0], bo[1] + 6.35, bo[0] + 12.7, bo[1] + 6.35)

    # The bulk sits at the end of the same two rails.
    # Same 12.7 mm pitch as the ceramics, so the bulk joins the two
    # rails the chain already forms instead of hanging off a stub that
    # reaches 12.7 mm towards a cap 25.4 mm away and connects to nothing.
    xb = x0 - 10 * 12.7
    sh.place("Device:C_Polarized", "C", xb, y0, "150uF",
             fields={"Source": "mcu_pdn.cir bulk; bom_requirements PDN-BULK",
                     "Note": "POLYMER, specified by an ESR BAND of "
                             "20-50 mOhm across -40/+125 C. Not a ceiling: "
                             "at 20 mOhm the PDN peak climbs back to "
                             "92 mOhm, because this part's ESR is also the "
                             "damping.",
                     "ESR": "20-50 mOhm over temperature"})
    a = pin_xy(*PINS["Device:C_Polarized"]["1"], xb, y0, 0)
    b = pin_xy(*PINS["Device:C_Polarized"]["2"], xb, y0, 0)
    t, bo = (a, b) if a[1] < b[1] else (b, a)
    sh.wire(t[0], t[1], t[0], t[1] - 6.35)
    sh.wire(t[0], t[1] - 6.35, t[0] + 12.7, t[1] - 6.35)
    sh.hlabel("3V3_MCU", t[0] - 5.08, t[1] - 6.35, shape="input", rot=180)
    sh.wire(t[0] - 5.08, t[1] - 6.35, t[0], t[1] - 6.35)
    sh.wire(bo[0], bo[1], bo[0], bo[1] + 6.35)
    sh.wire(bo[0], bo[1] + 6.35, bo[0] + 12.7, bo[1] + 6.35)
    sh.gnd(bo[0] - 5.08, bo[1] + 6.35)
    sh.wire(bo[0] - 5.08, bo[1] + 6.35, bo[0], bo[1] + 6.35)


# Conn_ARM_JTAG_SWD_10 pin geometry, read out of the stock library
# rather than remembered (see schlib.PINS for why that matters).
SWD = {"1": (0, 15.24), "2": (12.7, 0), "3": (0, -15.24), "4": (12.7, 2.54),
       "6": (12.7, -2.54), "8": (12.7, -5.08), "9": (-2.54, -15.24),
       "10": (12.7, 7.62)}


def debug_port(sh):
    """Cortex debug header. PTA4/PTC4/PTC5 are JTAG TMS/TCK/TDI and PTA5
    is the dedicated RESET_b -- the only four pins on the whole part that
    come out of reset with a pull, which is why they are reserved."""
    x, y = DBG_AT
    sh.place("Connector:Conn_ARM_JTAG_SWD_10", "J", x, y, "SWD/JTAG",
             footprint="Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical",
             fields={"Source": "docs/pinmap.md sec.0 -- PTA4/PTC4/PTC5 and "
                               "PTA5 reserved, excluded from the signal map"})
    for num, net in (("1", "3V3_MCU"), ("10", "~{RESET}"),
                     ("2", "JTAG_TMS"), ("4", "JTAG_TCK"),
                     ("8", "JTAG_TDI")):
        lx, ly = SWD[num]
        px, py = pin_xy(lx, ly, x, y, 0)
        if lx > 0:
            sh.wire(px, py, px + STUB, py)
            sh.label(net, px + STUB, py)
        else:
            sh.wire(px, py, px, py - STUB)
            sh.label(net, px, py - STUB, rot=90)
    # Both grounds, and the shell's ground-detect leg.
    # Both ground pins plus the shell's ground-detect leg, brought to
    # ONE ground symbol -- two symbols 2.54 mm apart print as "GNDGND".
    g3 = pin_xy(*SWD["3"], x, y, 0)
    g9 = pin_xy(*SWD["9"], x, y, 0)
    sh.wire(g3[0], g3[1], g3[0], g3[1] + STUB)
    sh.wire(g9[0], g9[1], g9[0], g9[1] + STUB)
    sh.wire(g9[0], g9[1] + STUB, g3[0], g3[1] + STUB)
    sh.junction(g3[0], g3[1] + STUB)
    sh.gnd(g3[0], g3[1] + STUB)
    # Pin 6 (SWO/TDO) is deliberately left open: the pin map reserves
    # only TMS/TCK/TDI plus RESET_b, and a fourth JTAG pin would be a
    # fifth reservation nobody has made. SWD debugging does not need it;
    # trace output would.
    lx, ly = SWD["6"]
    px, py = pin_xy(lx, ly, x, y, 0)
    sh.text("SWO/TDO left open -- see note", px + 3.81, py + 1.27, size=1.0)


def notes(sh):
    sh.text(
        "PIN MAP ADDITIONS MADE ON THIS SHEET -- both are gaps in "
        "docs/pinmap.md, not changes to it:\n"
        "  PTE0  WDT_KICK   MCU -> TPS3850 WDI.  pinmap.md assigns 37 "
        "signals and none of them services the external\n"
        "                   watchdog, but memo 11's topology requires the "
        "MCU to kick it. A window watchdog nobody feeds\n"
        "                   resets the board on a timer.\n"
        "  PTE1  WDT_FAULT  TPS3850 WDO -> MCU, so firmware can tell a "
        "watchdog trip from a rail trip.\n"
        "Both are free GPIO-HD pins, PE=0/PS=0 at reset, from the 91 the "
        "pin map leaves spare.",
        40, 132, size=1.6)
    sh.text(
        "SUPERVISOR CHOICE -- TPS3850G33, from the datasheet's own "
        "nomenclature table (G = thresholds at +/-4% of nominal, H = "
        "+/-7%) and its +/-0.8% accuracy spec:\n"
        "  G33  UV 3.168 V nom, 3.143 V worst-low   |   H33  UV 3.069 V "
        "nom, 3.044 V worst-low\n"
        "The supervisor has to assert BEFORE the MCU's own LVD (3.0 V max) "
        "and above the 2.97 V correctness floor. G33 clears LVD by 143 mV "
        "worst case; H33 by 44 mV,\n"
        "close enough that the two could fire in either order. The cost is "
        "that the rail must stay inside 3.143-3.459 V -- a +/-2% regulator "
        "spans 3.234-3.366 V, leaving ~90 mV each end.\n"
        "That is this choice's constraint on the rails sheet.\n"
        "\n"
        "OPEN: SET0/SET1 strap the watchdog window ratio, and the right "
        "ratio depends on a firmware loop period that does not exist yet "
        "(phase 4). Link resistors, not hard wires.",
        40, 155, size=1.6)


if __name__ == "__main__":
    sh, _ = build()
    print(sh.write(OUT, force="--force" in sys.argv))
