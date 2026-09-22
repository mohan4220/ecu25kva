#!/usr/bin/env python3
"""Package every resistor and capacitor from the voltage ACROSS it.

The package of a chip passive is not a free choice. A resistor has a
working-voltage ceiling and a power rating that falls with temperature;
a ceramic capacitor has a rated voltage and loses capacitance under DC
bias. On this board a node can reach 73.3 V (ISO 7637-2 pulse 2a) or
104 V (the injector boost rail), and an 0603 resistor is rated 75 V.
So the rule is computed, not remembered:

  1. every net gets (continuous max, peak max) volts, in NET_V below;
  2. a part's voltage is the worst difference between its two nets --
     except inside a FLOATING domain (a bootstrap supply riding on an
     injector bank node), where it is the domain's own swing;
  3. a resistor's power is V_cont^2 / R -- CONTINUOUS, because a 50 us
     pulse does not set a wattage -- unless the value states its own
     wattage, or the net pair is in PAIR_V with what is really across it;
  4. the smallest package that clears both, at a 105 C board
     (ASSUMED -- the spec states no ambient), wins.

Resistor ratings: Vishay D/CRCW e3 (AEC-Q200), standard operation mode,
retrieved 22 Sep 2026. Power derates linearly from 70 C to 0 at 155 C,
which is x0.588 at 105 C. Voltage margin: the rail table's 1.09x.

Capacitors: rated voltage must clear the peak and 1.5x the continuous
voltage (DC-bias headroom); the package is looked up in CAP_PACKAGE,
which lists only (value, rating) pairs checked against a manufacturer
part. A pair not in that table stops the script rather than guessing.

Writes lib/passive_fp.json: ref -> (footprint, why). schlib.place()
applies it; check_netlist.py fails if it goes stale.
"""
import collections
import json
import os
import re
import subprocess
import sys
import tempfile

HW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HW, "lib", "passive_fp.json")

T_BOARD = 105.0
DERATE = (155.0 - T_BOARD) / (155.0 - 70.0)
V_MARGIN = 1.09

# size: (P70 W, Umax V) -- Vishay D/CRCW e3, standard mode
R_SIZES = [("0402", 0.063, 50.0), ("0603", 0.10, 75.0),
           ("0805", 0.125, 150.0), ("1206", 0.25, 200.0),
           ("1210", 0.5, 200.0), ("2010", 0.75, 400.0),
           ("2512", 1.0, 500.0)]
R_MIN_SIZE = "0603"          # nothing smaller: hand rework, probe access

BAT = (24.0, 73.3)           # jump-start continuous, pulse 2a peak
HARNESS = (24.0, 73.3)       # any loom wire can be shorted to battery
BOOST = (104.0, 104.0)
LOGIC3 = (3.6, 3.6)
LOGIC5 = (5.5, 5.5)
GATE12 = (13.6, 13.6)        # 12V_GATE high corner, run_sim

NET_V = {
    "GND": (0.0, 0.0),
    # battery side
    "/VBAT_PROT": BAT, "/power_input/VBAT_CLAMPED": BAT,
    "/power_input/VBAT_REV_GATE": BAT, "/V_BAT_1R": HARNESS,
    "/V_BAT_2R": HARNESS, "/TRIP_LOOP": HARNESS,
    "/IN_AUDIO_ABORT_H": HARNESS, "/IN_OVERRIDE_SS_H": HARNESS,
    "/IN_IGNITION_H": HARNESS, "/SW_COOLANT_C": HARNESS,
    "/SW_DROOP_C": HARNESS, "/EGR_HIGH_59": BAT, "/EGR_LOW_81": BAT,
    "/RAIL_P_IN": HARNESS, "/CAM_FREQ_46": HARNESS,
    "/rails/SW": BAT,
    "/power_input/VBAT_EMI1": BAT,    # between L1 and the ferrite
    "Net-(U201-EN{slash}UVLO)": (6.0, 18.3),   # 24.9k/(75k+24.9k) of rail
    "/power_input/NCL_SENSE": (5.7, 5.7),      # BAV199 to 5V_MAIN
    "/power_input/NCL_REF": LOGIC5, "/power_input/NCL_OUT": LOGIC5,
    "/power_input/EMI_DAMP": (0.1, 1.0),  # Cd/Rd node: ripple only
    # injector boost
    "/injector/BOOST_100V": BOOST,
    # bank nodes: boost only for the 38 us peak; battery through hold
    "/INJ_A_03": (24.0, 104.0), "/INJ_B_05": (24.0, 104.0),
    "/injector/FB_BOOST_MID": (51.0, 51.0),  # 499k/499k midpoint
    "/injector/BIAS_12V_MID": (58.5, 58.5),  # 47k/47k midpoint
    "/injector/Q1C_MID": (83.5, 83.5),  # collector string midpoint
    "/injector/Q1C_12V": (67.0, 67.0),
    "/injector/BASE_12V": (13.7, 13.7), "/injector/Q1E_12V": GATE12,
    "/injector/VDD_BOOST": (24.0, 46.6), "/injector/RC_BOOST": (24.0, 46.6),
    "/injector/BP_BOOST": (8.5, 8.5), "/injector/EN_BOOST": LOGIC5,
    "/injector/FB_BOOST": LOGIC5, "/injector/COMP_BOOST": LOGIC5,
    "/injector/SS_BOOST": LOGIC5, "/injector/COMP_RC_BOOST": LOGIC5,
    "/injector/ISNS_BOOST": (0.3, 0.3),
    "/injector/ISNS_INJ_A_SENSE": (0.3, 0.3),
    "/injector/ISNS_INJ_B_SENSE": (0.3, 0.3),
    # gate drive
    "/12V_GATE": GATE12, "/GATE_KILL": (13.7, 13.7),
    "/injector/LS1_GATE": GATE12, "/injector/LS2_GATE": GATE12,
    "/injector/LS3_GATE": GATE12, "/metering_egr/MU_GATE": GATE12,
    "/metering_egr/EGR_AL_G": GATE12, "/metering_egr/EGR_BL_G": GATE12,
    # floating: absolute values are the bank's, but see DOMAINS
    "/injector/UA1_VB": BOOST, "/injector/UA2_VB": BOOST,
    "/injector/UB1_VB": BOOST, "/injector/UB2_VB": BOOST,
    "/injector/HSA_BOOST_GATE": BOOST, "/injector/HSA_BAT_GATE": BOOST,
    "/injector/HSB_BOOST_GATE": BOOST, "/injector/HSB_BAT_GATE": BOOST,
    "/metering_egr/EGR_A_VB": BAT, "/metering_egr/EGR_B_VB": BAT,
    "/metering_egr/EGR_AH_G": BAT, "/metering_egr/EGR_BH_G": BAT,
    # sense and logic
    "/metering_egr/EGR_ISNS": (0.3, 0.3),
    "/metering_egr/ISNS_MU_SENSE": (0.3, 0.3),
    "/3V3_MCU": LOGIC3, "/5V_MAIN": LOGIC5, "/5V_SENSOR_C": LOGIC5,
    "/SENSOR_5V_MON": LOGIC5, "/rails/PGOOD_5V": LOGIC5,
    "/rails/FB_5V": LOGIC5, "/rails/BST": BAT,
    "Net-(U201-RON)": LOGIC5,
    "/V_BAT_1R_SNS": (5.7, 5.7), "/V_BAT_2R_SNS": (5.7, 5.7),
    # VR pair: ~14 V rms at rated speed, 48 V at the TVS standoff
    "/CRANK_HI_52": (14.0, 48.0), "/CRANK_LO_74": (14.0, 48.0),
    "/speed_inputs/VR_HI_CLAMPED": (3.9, 3.9),
    "/speed_inputs/VR_LO_CLAMPED": (3.9, 3.9),
    "/speed_inputs/VR_BIAS": LOGIC3,
    # CAN: normal bus is a few volts; the rating covers a battery short
    "/CAN1_H": (3.0, 40.0), "/CAN1_L": (3.0, 40.0),
    "/CAN2_H": (3.0, 40.0), "/CAN2_L": (3.0, 40.0),
    "/can/CAN1_SPLIT": (3.0, 40.0), "/can/CAN2_SPLIT": (3.0, 40.0),
    "/discrete_io/RLY_MAIN_G": LOGIC5, "/discrete_io/RLY_BUZZER_G": LOGIC5,
}
# Nets at MCU logic level, by name pattern.
LOGIC3_RE = re.compile(
    r"^/(IN_AUDIO_ABORT|IN_OVERRIDE_SS|IN_IGNITION|SW_COOLANT|SW_DROOP|"
    r"TRIP_SENSE|RLY_MAIN|RLY_BUZZER|EGR_EN|CAM_EDGE|CRANK_EDGE|"
    r"INJ_HS_[AB](_BAT)?|can/CAN[12]_STB|mcu/WDT_FAULT|mcu/~\{RESET\}|"
    r"metering_egr/EGR_SD|injector/U[AB][12]_HIN)$|^Net-\(U302-")
LOGIC5_RE = re.compile(
    r"^/(BARO|BOOST_P|BOOST_T|COOLANT_T|EGR_POS|OIL_P|RAIL_P)$|"
    r"^Net-\(U60[1-6]-(OUT|VOUT)\)$")

# Bootstrap domains: every net in one domain rides on the first, and a
# part with both ends in the domain sees only the gate-drive swing.
DOMAINS = [
    ["/INJ_A_03", "/injector/UA1_VB", "/injector/UA2_VB",
     "/injector/HSA_BOOST_GATE", "/injector/HSA_BAT_GATE"],
    ["/INJ_B_05", "/injector/UB1_VB", "/injector/UB2_VB",
     "/injector/HSB_BOOST_GATE", "/injector/HSB_BAT_GATE"],
    ["/EGR_HIGH_59", "/metering_egr/EGR_A_VB", "/metering_egr/EGR_AH_G"],
    ["/EGR_LOW_81", "/metering_egr/EGR_B_VB", "/metering_egr/EGR_BH_G"],
    ["/rails/SW", "/rails/BST"],
]

# Parts where "the worse of its two nets" over-states what is ACROSS it:
# series strings between two biased nodes, and parts that carry only AC.
# Keyed by the net pair, not the ref -- refs move when parts are added.
# (v_cont, v_peak, why)
PAIR_V = {
    ("/injector/BIAS_12V_MID", "/injector/BOOST_100V"):
        (45.5, 45.5, "upper half of the 47k/47k zener bias string"),
    ("/injector/BASE_12V", "/injector/BIAS_12V_MID"):
        (45.5, 45.5, "lower half of the 47k/47k zener bias string"),
    ("/power_input/VBAT_CLAMPED", "/power_input/VBAT_EMI1"):
        (0.2, 1.0, "ferrite damper Rf, across Lf: filter AC only"),
    ("/12V_GATE", "/injector/Q1E_12V"):
        (0.28, 0.65, "56 ohm limit sense: 5 mA, one Vbe at the limit"),
    ("/CAN1_H", "/can/CAN1_SPLIT"): (1.0, 40.0, "half the 2 V dominant"),
    ("/CAN1_L", "/can/CAN1_SPLIT"): (1.0, 40.0, "half the 2 V dominant"),
    ("/CAN2_H", "/can/CAN2_SPLIT"): (1.0, 40.0, "half the 2 V dominant"),
    ("/CAN2_L", "/can/CAN2_SPLIT"): (1.0, 40.0, "half the 2 V dominant"),
}

# Sense shunts are a different product family (metal element, milliohm);
# they carry their own package in the value string or here.
SHUNT_FP = {
    "5mOhm 2W 1%": "Resistor_SMD:R_2512_6332Metric",
    "20mOhm 1W 1%": "Resistor_SMD:R_2512_6332Metric",
    "50mOhm 1%": "Resistor_SMD:R_1206_3216Metric",
    "82mOhm 1%": "Resistor_SMD:R_1206_3216Metric",
}

R_FP = {s: f"Resistor_SMD:R_{s}_{m}Metric" for s, m in [
    ("0402", "1005"), ("0603", "1608"), ("0805", "2012"),
    ("1206", "3216"), ("1210", "3225"), ("2010", "5025"),
    ("2512", "6332")]}
C_FP = {s: f"Capacitor_SMD:C_{s}_{m}Metric" for s, m in [
    ("0402", "1005"), ("0603", "1608"), ("0805", "2012"),
    ("1206", "3216"), ("1210", "3225"), ("1812", "4532")]}

# What exists: KEMET C1023 X7R AUTO (AEC-Q200), "Table 1 -- Capacitance
# Range/Selection Waterfall", retrieved 22 Sep 2026 and parsed by x
# coordinate (tools/parse_kemet_waterfall.py -- the text layout
# compresses the data columns and mis-assigns them). capacitance ->
# [(case, rated V)]. A (value, rating) pair absent here stops the script.
KEMET = json.load(open(os.path.join(HW, "lib", "kemet_x7r_auto.json")))
C_CASES = ["0603", "0805", "1206", "1210", "1812"]   # smallest first
C_FLOOR = 25.0          # <=1 uF: never below 25 V, for DC-bias headroom
SPECIAL_C = {           # not MLCC -- chosen separately
    "150uF": "polymer, PDN-BULK ESR band -- chosen separately",
    "47uF 150V": "aluminium electrolytic -- chosen separately",
}


CLAMP_NODE = (3.1, 4.4)      # BAV199-Q node: signal max / one diode up
BUFFER_BASE = (1.0, 1.1)     # discrete-input NPN base: one Vbe, or -1 V


def netv(n):
    if n in NET_V:
        return NET_V[n]
    if n.endswith("_CL"):
        return CLAMP_NODE
    if n.startswith("/discrete_io/") and n.endswith("_B"):
        return BUFFER_BASE
    if LOGIC3_RE.search(n):
        return LOGIC3
    if LOGIC5_RE.search(n):
        return LOGIC5
    raise SystemExit(f"no voltage for net {n!r} -- add it to NET_V")


def across(a, b):
    key = tuple(sorted((a, b)))
    if key in PAIR_V:
        return PAIR_V[key][:2]
    for d in DOMAINS:
        if a in d and b in d:
            return GATE12
    (ca, pa), (cb, pb) = netv(a), netv(b)
    return max(ca, cb), max(pa, pb)


def parse_value(v):
    """'2R2' 2.2, '120R' 120, '4.7k' 4700, '82mOhm' 0.082, '100nF' 1e-7,
    '4.7uF/100V' 4.7e-6 -- the leading quantity only."""
    m = re.match(r"^(\d+)R(\d*)\b", v)
    if m:
        return float(f"{m.group(1)}.{m.group(2) or 0}")
    m = re.match(r"^([\d.]+)\s*([pnumkM]?)", v)
    if not m:
        raise SystemExit(f"cannot read value {v!r}")
    mul = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3,
           "M": 1e6, "": 1.0}[m.group(2)]
    return float(m.group(1)) * mul


def netlist():
    fd, path = tempfile.mkstemp(suffix=".net")
    os.close(fd)
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", path,
                    os.path.join(HW, "ecu25kva.kicad_sch")], check=True,
                   capture_output=True)
    text = open(path).read()
    os.unlink(path)
    return text


def main():
    text = netlist()
    comps = dict(re.findall(r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]*)"',
                            text))
    netsof = collections.defaultdict(list)
    for blk in text.split("(net (code")[1:]:
        name = re.search(r'\(name "([^"]+)"', blk).group(1)
        for ref, _pin in re.findall(
                r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"', blk):
            netsof[ref].append(name)

    out, unresolved = {}, []
    for ref, val in sorted(comps.items()):
        kind = ref[0]
        if kind not in "RC" or not re.match(r"^[RC]\d", ref):
            continue
        if kind == "C" and re.match(r"^C\d", ref) and "uF 150V" in val:
            continue                     # electrolytic, chosen separately
        nets = netsof[ref]
        if len(nets) != 2:
            continue
        vc, vp = across(*nets)
        if kind == "R":
            if val in SHUNT_FP:
                out[ref] = (SHUNT_FP[val], f"shunt: {val}")
                continue
            m = re.search(r"\b(2512|2010|1210|1206)\b", val)
            if m:
                out[ref] = (R_FP[m.group(1)], f"size stated in value")
                continue
            r = parse_value(val)
            if "1W" in val:
                out[ref] = (R_FP["2512"], "1 W stated in value")
                continue
            if r == 0.0:
                out[ref] = (R_FP[R_MIN_SIZE], "0R jumper")
                continue
            p = vc * vc / r
            sizes = [x[0] for x in R_SIZES]
            for size, p70, umax in R_SIZES[sizes.index(R_MIN_SIZE):]:
                if p <= p70 * DERATE and vp * V_MARGIN <= umax:
                    out[ref] = (R_FP[size],
                                f"{vp:.1f} V peak, {p*1e3:.1f} mW cont; "
                                f"{size} = {umax:.0f} V, "
                                f"{p70*DERATE*1e3:.0f} mW at {T_BOARD:.0f} C")
                    break
            else:
                unresolved.append((ref, val, nets, vc, vp, p))
        else:
            if val in SPECIAL_C:
                continue
            c = parse_value(val)
            need = max(vp, 1.5 * vc)
            if c <= 1.01e-6:
                need = max(need, C_FLOOR)
            m = re.search(r"(\d+)V", val)
            if m:
                need = max(need, float(m.group(1)))
            have = KEMET.get(f"{c:.3e}", [])
            pick = None
            for case in C_CASES:
                rs = sorted(v for cs, v in have if cs == case and v >= need)
                if rs:
                    pick = (case, rs[0])
                    break
            if pick:
                out[ref] = (C_FP[pick[0]],
                            f"{vp:.1f} V peak, needs >= {need:.0f} V; "
                            f"KEMET X7R AUTO {pick[0]} {pick[1]:g} V")
            else:
                unresolved.append((ref, val, nets, vc, vp, need))

    if "--report" in sys.argv or unresolved:
        need = collections.Counter()
        for u in unresolved:
            if u[0][0] == "C":
                need[(u[1], u[5])] += 1
            else:
                print("  R unresolved:", u)
        for (v, r), n in sorted(need.items(), key=lambda x: (x[0][1], x[0][0])):
            print(f"  C needs a package: {v} at >= {r:.0f} V  x{n}")
    with open(OUT, "w") as f:
        json.dump({k: {"footprint": v[0], "why": v[1],
                       "value": comps[k]} for k, v in out.items()},
                  f, indent=1, sort_keys=True)
    print(f"{OUT}: {len(out)} parts packaged, {len(unresolved)} unresolved")
    return 1 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
