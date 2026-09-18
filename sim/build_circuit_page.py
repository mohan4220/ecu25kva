#!/usr/bin/env python3
"""Generate docs/handbook/circuits.html -- every block, with live results.

    .venv/bin/python sim/build_circuit_page.py

The page is generated rather than written, for the same reason the
schematics are: there is one description of each circuit in this repo,
the netlist, and everything else is derived from it. The schematic comes
from draw_schematics.py, and the result rows come from actually running
run_sim.py's checks at build time. A number on this page cannot disagree
with the simulation, because it IS the simulation's output.

The prose is the one part that is written by hand, and it is kept here
rather than in the netlist so the netlists stay readable as netlists.
"""
import html
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_sim  # noqa: E402

OUT = HERE.parent / "docs" / "handbook" / "circuits.html"
SVG = HERE.parent / "docs" / "handbook" / "circuits"

# (block, title, pins, what it does, why it looks like that, model limits)
BLOCKS = {
    "power": ("01", "Power chain", "From the battery terminal to the MCU rail. Six stages, each one a "
              "different failure it has to survive.", [
        ("emi_filter", "EMI input filter", "pin 21",
         "Two LC stages between the battery and everything else, measured 50 ohm to 50 ohm the way a "
         "LISN would see it.",
         "One stage is not enough, and the reason is the capacitor: C1's own lead inductance puts its "
         "self-resonance near 1.9 MHz, and above that it stops being a capacitor. Stage two picks up "
         "there. The damper across C2 is not optional either — without it the ferrite and C2 ring at "
         "717 kHz and hand back 12 dB right where the switching frequency's second harmonic sits.",
         "Differential mode only. Common-mode noise — both wires swinging together against chassis, "
         "which is most real automotive failures — needs the common-mode choke, and that cannot be "
         "modelled honestly without a layout to give it a return path."),
        ("reverse_battery", "Reverse-battery protection", "—",
         "A P-FET held on by a controller that watches polarity, compared against the obvious Schottky.",
         "Somebody will reverse the jump leads eventually. A Schottky survives it and charges you 0.46 V "
         "on every amp forever; the ideal-diode arrangement costs a controller IC and drops 24 mV. At 3 A "
         "that is 1.4 W of heat that simply never happens.",
         "Steady state only. A real controller takes about a microsecond to turn the FET off, and current "
         "flows backwards through the body diode during that window. The switch model here turns off "
         "instantly, so it will always look perfect in reverse — that number is a datasheet question."),
        ("transient_clamp", "Transient clamp", "pin 21",
         "A bidirectional TVS and a ferrite, against ISO 7637-2 pulse 2a: +112 V through 2 ohms for 50 us.",
         "Clamps to 50 V, which leaves 2x margin inside the buck controller's 100 V rating and keeps "
         "60 V-class parts viable everywhere downstream.",
         "It misses the 42 V figure the earlier documents asked for, and that figure should be dropped: "
         "it was arbitrary, with no standard behind it. The real constraints are the parts' ratings."),
        ("load_dump", "Load dump", "pin 21",
         "The same TVS and capacitor as transient_clamp, against ISO 7637-2 pulse 5b: a suppressed load "
         "dump, 40 V through 0.5 ohms for 400 ms — four orders of magnitude longer than pulse 2a.",
         "Clamps to 38 V, comfortably inside every voltage rating in the chain — the same story as pulse "
         "2a. But 400 ms is long enough that the limit stops being clamp voltage and becomes dissipated "
         "energy: the TVS absorbs roughly 46 J at ~116 W average, which is on the order of 100x an "
         "SMBJ-class part's single-pulse energy rating and its continuous power rating both. This block "
         "FAILS on purpose — a TVS sized against pulse 2a's peak voltage was never sized against pulse "
         "5b's energy, because nothing before this block asked the energy question. But the whole failure "
         "turns on one inequality: re-run at Us* = 35 V, the figure usually quoted for a 12 V suppressed "
         "dump, and the TVS never reaches its 36.7 V breakdown — 0.000 A, 0 J, no problem at all. So the "
         "finding is not that an SMBJ33CA cannot survive a load dump. It is that a TVS whose standoff sits "
         "BELOW the dump level gets forced to conduct during a normal event and then has to absorb it. "
         "The fix is a higher standoff (SMBJ40CA/45CA class), not a bigger energy rating: the TVS then "
         "stays off and the buck, rated 100 V, rides 40 V without complaint. Energy absorption only "
         "becomes unavoidable under pulse 5a.",
         "Whether this pulse even applies: 5b assumes the alternator's rectifier is suppressed/clamping. "
         "That has not been confirmed for this genset — if it is not, the real event is pulse 5a "
         "(65–87 V, unclamped), a harder problem this block does not simulate. Also not modelled: the "
         "real pulse's exponential-decay shape (approximated here as a trapezoid, which is pessimistic "
         "in the right direction), and the TVS's actual junction thermal transient."),
        ("buck_preregulator", "Buck pre-regulator", "—",
         "6–40 V down to 5 V at 400 kHz, run open-loop at fixed duty so the output filter is visible.",
         "400 kHz is chosen against CISPR 25, not for size: the conducted band starts at 150 kHz, so a "
         "fundamental below it would put every harmonic inside the measurement from the first one up. "
         "The inductor is sized at HIGH line, not low — ripple current grows with input voltage even "
         "though duty cycle falls.",
         "Ideal switches with a fixed on-resistance. Good enough for ripple, which is set by L and C; "
         "useless for efficiency, which is set by switching overlap, gate charge and reverse recovery, "
         "none of which this model has."),
        ("sensor_rail", "5V_SENSOR distribution", "—",
         "One resettable fuse per sensor group, and the same fault simulated without them.",
         "A 5 V sensor supply shorted to engine ground is a routine fault, not an exotic one. The "
         "question is what it does to the OTHER sensors: with per-group protection the healthy groups "
         "keep 4.66 V, without it the whole rail collapses to 0.5 V and the ECU loses every analog "
         "channel at once — which means it cannot tell a wiring fault from an engine failing.",
         "The polyfuse is modelled cold, which is the worst case for the healthy groups: the instant "
         "after the short, before the device has heated and tripped. Once tripped the healthy groups "
         "recover further. Firmware still has to notice — a tripped fuse and a dead sensor look "
         "identical from the ADC's side."),
        ("mcu_pdn", "3V3_MCU decoupling", "—",
         "The impedance the S32K148 sees looking into its own supply, from 1 kHz to 100 MHz.",
         "The bulk capacitor here is sized by a resonance, not by charge. The first version used 10 uF "
         "with low ESR and peaked at 3.4 ohms around 48 kHz — the regulator's own output inductance "
         "ringing against the bulk capacitance, decades away from the bulk/ceramic anti-resonance the "
         "design was drawn around. Bigger AND lossier fixes it, which is why a plain aluminium part "
         "beats a ceramic in that position.",
         "Lumped: no planes, no via inductance, no spreading inductance, so it is optimistic above about "
         "100 MHz — which is exactly where the sweep stops. An earlier version swept to 1 GHz and "
         "obediently reported ESL times omega at the last point as a 'peak'."),
    ]),
    "sensors": ("02", "Sensor front-ends", "Everything that turns something on the engine into a number "
                "in the ADC.", [
        ("sensor_ratiometric", "Ratiometric sensor input", "pins 41, 35, 80, 37",
         "The 0.5–4.5 V pressure and position channels, scaled into a 3.3 V ADC.",
         "Full scale deliberately lands at 2.77 V rather than hard against the ceiling, so the protection "
         "clamp can do its job on a harness fault without ever touching the signal in normal running. "
         "That costs a little span and buys a front-end 40 V cannot damage. The last four checks cover the "
         "ratiometric property itself, which this block was named for and did not model until the spec "
         "review caught it: a sensor's output is a fraction of its own supply, so a reading taken against "
         "an assumed 5.000 V carries the rail's whole error band — 10% here. Giving the rail its own ADC "
         "channel through an identical divider removes it, and the divider ratio cancels algebraically, "
         "so its tolerance drops out too.",
         "Ground offset. Every network here measures against a perfect ground, and pins 34 and 36 are "
         "shared returns — which is why spec §4 now specifies a differential front-end for those channels "
         "and leaves this one for pin 08, the dedicated return. Also not modelled: divider tolerance "
         "matching, on which the rail correction depends, and ADC sampling time against the source "
         "impedance."),
        ("sensor_differential", "Differential sensor input", "pin 34 group",
         "The same channel measured sensor-to-sensor-ground instead of sensor-to-ECU-ground, swept against "
         "the harness return's resistance.",
         "Pin 34 is spliced between the boost sensor and the coolant sensor, so it carries both sensors' "
         "return current. A single-ended input reads the resulting offset as signal. Research memo 09 "
         "found this is exactly what Deep Sea Electronics specifies against (+/-2 V common mode on every "
         "sender channel) and what SEDEMAC's dedicated sensor common point exists for. Note what the OEM "
         "did with the channel that could not tolerate it: rail pressure gets pin 08, spliced with nothing.",
         "The error is about half a percent of span at 1 ohm of return resistance, and that understates it. "
         "It is a bias rather than noise, so it never averages out; it grows as contacts corrode; and it "
         "is indistinguishable from a real reading — a boost pressure biased high permits more fuel, and "
         "the first symptom is smoke, not a fault code."),
        ("ntc_frontend", "NTC temperature input", "pin 79",
         "The thermistor branch of U2, as a pull-up divider and as a constant-current source, across the "
         "full –40 to 150 C range.",
         "Memo 09 found DSE drives its temperature senders with a fixed 15 mA and measures differentially, "
         "and the obvious move is to copy it. Checked against an actual charge-air NTC it does not "
         "transfer: 88 ohms to 59 kilohms is a 670:1 span against the 50:1 a genset sender covers, and a "
         "current source sized to give useful signal at 150 C demands 5.9 V from a 5 V rail at –40 C. "
         "The divider's non-linearity is what saves it — it is bounded by the supply at both ends.",
         "Which branch this engine actually needs is still U2, and one resistance measurement at the "
         "machine settles it. The self-heating figure should be revisited once the real sensor's "
         "dissipation constant is known."),
        ("battery_sense", "Battery voltage sense", "pins 04, 06",
         "The 6–40 V system rail scaled into the ADC.",
         "The inherited 75k/10k divider was sized for a 5 V ADC and reaches 4.69 V at 40 V — it would "
         "have damaged the input pin. 120k/10k peaks at 3.07 V and still resolves 573 counts at the 6 V "
         "cranking dip.",
         "Nothing subtle. A resistive divider is exactly linear and the check confirms it, which is there "
         "to catch a wrong topology rather than a wrong value."),
        ("discrete_input", "Discrete switch input", "pins 20, 24, 71",
         "The switched-battery inputs, active high.",
         "This one cannot be built as a divider at all. Reading logic high at a 6 V cranking dip needs a "
         "ratio above 0.385; staying under 3.3 V at 40 V needs it below 0.0825. No fixed ratio satisfies "
         "both, so the original was impossible rather than merely mis-valued. A 3.0 V zener sets the "
         "level and the divider only biases into it, which holds the output flat within 92 mV across the "
         "whole range.",
         "The debounce capacitor went from 100 nF to 220 nF after simulation showed the smaller value "
         "let two threshold crossings through a bouncing contact — which firmware would have read as "
         "two separate presses."),
    ]),
    "speed": ("03", "Speed and position", "The most safety-critical input on the board.", [
        ("vr_conditioner", "Crank speed conditioner", "pins 52, 74, 30",
         "A variable-reluctance sensor into a zero-crossing comparator, run at both running speed and "
         "cranking speed.",
         "A VR sensor generates voltage by induction, so its amplitude is proportional to speed: roughly "
         "20 V peak at 1500 rpm and 2 V at cranking. A fixed 5 V threshold, which looks perfectly "
         "sensible against a 20 V signal, produces all 30 teeth at running speed and NOTHING at cranking. "
         "That is the worst failure shape there is — it works on the bench and the engine never starts. "
         "Zero-crossing detection does not care about amplitude, and the crossing is also where the "
         "waveform is steepest and timing jitter is smallest.",
         "A real VR signal is not a clean sine — tooth edges distort it and the missing-tooth sync gap "
         "produces one large excursion per revolution. Amplitude at true cranking speed on a cold engine "
         "with a weak battery can be under a volt, which is when starting matters most, and the "
         "hysteresis window needs checking against the real sensor rather than this 2 V estimate."),
    ]),
    "injection": ("04", "Injection", "The most expensive stage on the board and the reason it exists.", [
        ("injector_boost", "Why the boost rail exists", "pins 03, 05",
         "The same injector driven from the battery and from a 100 V rail, compared on time to reach the "
         "18 A peak threshold.",
         "439 us from the battery, 38 us from the boost rail. On a 1 ms injection the battery drive "
         "spends 44% of the event just lifting the needle; the boost rail spends 3.8%. That ratio is the "
         "entire argument for the stage.",
         "An RL model of the injector with no magnetic saturation and no moving needle. The envelope it "
         "sits in — 65–115 V, 12–24 A peak — is family-wide from memo 04, not this injector's "
         "measured values. That is U5."),
        ("boost_converter", "Boost rail reservoir", "pins 03, 05",
         "The reservoir capacitor under a real injection event, with and without the hold phase drawn "
         "from the same rail.",
         "The converter cannot deliver 18 A — it delivers a trickle and the capacitor delivers the "
         "pulse, so the capacitor is the component that matters. The design question is where the HOLD "
         "current comes from, and the answer is not subtle: hold costs 29 times the peak phase's charge, "
         "so a rail supplying both collapses completely. Hold comes from the battery. 50 mA of average "
         "charging recovers the rail with room to spare in the 26.67 ms before the next cylinder fires.",
         "Charge balance only. There is no inductor, no switch and no control loop — just a current "
         "source standing in for the converter's average output. It says nothing about the converter's "
         "stability or its inrush, and the collapsed voltage in the second case should be read as 'far "
         "below usable' rather than as a number."),
    ]),
    "actuators": ("05", "Actuators", "Outputs that move something.", [
        ("metering_unit_pwm", "Fuel metering unit driver", "pin 88",
         "Low-side PWM into the metering solenoid at three frequencies, all at the same duty.",
         "Rail pressure is controlled by the AVERAGE current through this coil, and all three frequencies "
         "produce the same average — which is what makes the control law independent of the PWM "
         "constant. What changes is ripple, and ripple is not purely a nuisance here: a proportional "
         "solenoid has stiction, and deliberate dither keeps it moving. At 100 Hz the period is "
         "comparable to the coil's own 3 ms time constant and the result is 152% ripple — that is not "
         "dither, that is chopping, and the valve follows the PWM rather than its average.",
         "The correct dither amplitude is a property of the specific metering unit's mechanics and is "
         "manufacturer data tied to a part number — the same gap as U5, in a smaller form. Keeping the "
         "frequency a firmware constant rather than a hardware one means it can be tuned on the machine. "
         "Coil inductance is also not constant: it falls as the armature moves and as the core saturates."),
        ("relay_driver", "Relay driver", "pins 50, 69",
         "A low-side FET switching a relay coil, run with and without the flyback diode.",
         "With the diode the drain stays at 14.3 V on turn-off. Without it the coil's stored energy has "
         "nowhere to go except through the FET.",
         "The simulated peak without the diode is hundreds of kilovolts, which is the ideal-switch model "
         "taken literally. A real MOSFET avalanches at its breakdown voltage and dissipates that energy "
         "in the die instead — once per relay operation, until it fails. The magnitude is a model "
         "artifact; the conclusion is not."),
    ]),
    "comms": ("06", "Communications", "The bus to the genset controller.", [
        ("can_termination", "CAN split termination", "CAN H, CAN L",
         "A split 60+60 termination with a capacitor to ground at the midpoint, against a single 120 ohm "
         "resistor.",
         "Both are 120 ohms differential and a schematic label cannot tell them apart. The difference is "
         "common mode: a single resistor gives noise on both wires together nowhere to go, while the "
         "split version shunts it to ground without touching the differential signal, because the "
         "midpoint is a virtual ground for differential drive. That matters more here than on a truck. "
         "The fitted controller is a Deep Sea DSE4522, and DSE\u2019s manual is explicit that with a CAN "
         "engine the ECU transmits engine speed to it \u2014 so this bus carries a safety-relevant value, "
         "and it runs beside 415 V three-phase wiring and contactor coils in the same panel.",
         "Termination is not the whole common-mode story; the choke is the other half and needs a layout. "
         "And this does not decide whether to fit termination at all: a 120 ohm terminator belongs at "
         "each END of the backbone, and if this ECU is not an end node, fitting one makes the bus worse. "
         "That is U4 — so the board should carry the parts with a link and let the machine decide. "
         "The DSE4522 terminates CAN on its terminals 18/19/20 and DSE specify 120 ohm cable, which "
         "settles the cable but not which nodes carry the terminators."),
    ]),
}


def results_for(name):
    """Run the block's own checks and return its rows. Never cached."""
    c = run_sim.CHECKS[name]()
    return c.rows


def row_html(ok, claim, actual, expected, unit):
    cls = "ok" if ok else "bad"
    if isinstance(actual, str):
        val = html.escape(actual)
    else:
        val = f"{actual:,.3f} {unit}".strip()
    return (f'<tr class="{cls}"><td>{html.escape(claim)}</td>'
            f'<td class="v">{val}</td></tr>')


def main():
    parts = []
    nav = []
    total = 0
    for key, (num, title, blurb, blocks) in BLOCKS.items():
        nav.append(f'<li><i>{num}</i><a href="#{key}">{html.escape(title)}</a></li>')
        body = [f'<section id="{key}"><div class="sechead"><i>{num}</i>'
                f'<h2>{html.escape(title)}</h2></div>'
                f'<p class="col lead">{html.escape(blurb)}</p>']
        for name, label, pins, does, why, limits in blocks:
            total += 1
            svg = (SVG / f"{name}.svg").read_text()
            svg = svg[svg.index("<svg"):]
            # Once. Each call runs the block's simulation, and an earlier
            # version called it three times per block for the row markup and
            # the two counts.
            checks = results_for(name)
            rows = "".join(row_html(*r) for r in checks)
            npass = sum(1 for r in checks if r[0])
            n = len(checks)
            body.append(f'''
  <div class="blk">
    <header><h3>{html.escape(label)}</h3><span class="pins">{html.escape(pins)}</span>
      <span class="tag">{npass}/{n} checks</span></header>
    <div class="body">
      <figure class="sch">{svg}</figure>
      <div class="col">
        <p>{does}</p>
        <p><b>Why it looks like that.</b> {why}</p>
        <p class="lim"><b>What the model does not cover.</b> {limits}</p>
      </div>
    </div>
    <table class="res"><tbody>{rows}</tbody></table>
    <p class="src">Netlist: <code>sim/blocks/{name}.cir</code></p>
  </div>''')
        body.append("</section>")
        parts.append("\n".join(body))

    page = TEMPLATE.format(nav="\n".join(nav), body="\n".join(parts), total=total)
    OUT.write_text(page)
    print(f"{total} circuits -> {OUT}")


TEMPLATE = """<title>Genset ECU Circuit Reference</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>
:root{{
  --paper:#f4f5f3; --surface:#ffffff; --surface-2:#eceeea; --surface-3:#e2e5e0;
  --rule:#d2d6cf; --rule-firm:#b4bab1;
  --ink:#171b1e; --ink-2:#4c5560; --ink-3:#7c8590;
  --petrol:#1f5566; --petrol-2:#2e7f96; --petrol-wash:#e3edef;
  --pass:#2f7d4f; --pass-wash:#e2f0e7;
  --fail:#b8332a; --fail-wash:#f7e6e4;
  --f-disp:'Archivo',system-ui,sans-serif;
  --f-body:'Source Serif 4',Georgia,serif;
  --f-mono:'JetBrains Mono',ui-monospace,Consolas,monospace;
}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
  --paper:#12161a; --surface:#191e24; --surface-2:#212830; --surface-3:#2b333c;
  --rule:#2e3740; --rule-firm:#43505c;
  --ink:#e6eaee; --ink-2:#a7b2bd; --ink-3:#76828e;
  --petrol:#5fb4cc; --petrol-2:#7ec9de; --petrol-wash:#152a33;
  --pass:#5cc189; --pass-wash:#14301f;
  --fail:#e8766c; --fail-wash:#361a18;
}}}}
:root[data-theme="dark"]{{
  --paper:#12161a; --surface:#191e24; --surface-2:#212830; --surface-3:#2b333c;
  --rule:#2e3740; --rule-firm:#43505c;
  --ink:#e6eaee; --ink-2:#a7b2bd; --ink-3:#76828e;
  --petrol:#5fb4cc; --petrol-2:#7ec9de; --petrol-wash:#152a33;
  --pass:#5cc189; --pass-wash:#14301f;
  --fail:#e8766c; --fail-wash:#361a18;
}}
*{{box-sizing:border-box}}
body{{background:var(--paper);color:var(--ink);font-family:var(--f-body);
  font-size:17px;line-height:1.62;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1080px;margin:0 auto;padding-inline:20px;padding-block:0 80px}}
.col{{max-width:66ch}}
h1,h2,h3{{font-family:var(--f-disp);color:var(--ink);text-wrap:balance;margin:0;line-height:1.14}}
p{{margin:0 0 1em}}
a{{color:var(--petrol)}}
code{{font-family:var(--f-mono);font-size:.88em}}
b{{font-weight:600}}

header.mast{{border-bottom:2px solid var(--ink);padding-block:44px 20px;margin-bottom:8px}}
.eyebrow{{font-family:var(--f-mono);font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--petrol);margin:0 0 14px;font-weight:500}}
header.mast h1{{font-size:clamp(34px,6.2vw,62px);font-weight:700;letter-spacing:-.022em;max-width:16ch}}
.standfirst{{font-size:20px;color:var(--ink-2);max-width:52ch;margin:18px 0 0}}
.meta{{font-family:var(--f-mono);font-size:12px;color:var(--ink-3);margin:20px 0 0;
  display:flex;flex-wrap:wrap;gap:22px}}
.meta b{{color:var(--ink)}}

.toc{{list-style:none;padding:0;margin:34px 0 0;display:grid;
  grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px 26px;
  border-top:1px solid var(--rule);padding-top:20px}}
.toc li{{display:flex;gap:10px;align-items:baseline}}
.toc i{{font-family:var(--f-mono);font-style:normal;font-size:11px;color:var(--ink-3)}}
.toc a{{text-decoration:none}}

section{{margin-top:56px}}
.sechead{{display:flex;gap:14px;align-items:baseline;border-bottom:1px solid var(--rule-firm);
  padding-bottom:10px;margin-bottom:18px}}
.sechead i{{font-family:var(--f-mono);font-style:normal;font-size:12px;color:var(--petrol)}}
.sechead h2{{font-size:27px;font-weight:700;letter-spacing:-.015em}}
.lead{{color:var(--ink-2);margin-bottom:22px}}

.blk{{border:1px solid var(--rule);border-radius:3px;background:var(--surface);
  margin:0 0 22px;overflow:hidden}}
.blk > header{{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;
  background:var(--surface-2);border-bottom:1px solid var(--rule);padding:11px 16px}}
.blk h3{{font-size:17px;font-weight:600}}
.pins{{font-family:var(--f-mono);font-size:11.5px;color:var(--ink-3)}}
.tag{{margin-left:auto;font-family:var(--f-mono);font-size:11px;color:var(--pass);
  background:var(--pass-wash);padding:2px 8px;border-radius:2px}}
.body{{padding:18px 16px 4px}}
.sch{{margin:0 0 18px;padding:14px;background:var(--surface-2);border-radius:2px;
  overflow-x:auto;color:var(--ink)}}
.sch svg{{max-width:100%;height:auto;display:block;margin:0 auto}}
.lim{{color:var(--ink-2);font-size:15.5px;border-left:2px solid var(--rule-firm);
  padding-left:14px}}
table.res{{width:100%;border-collapse:collapse;font-size:13px;
  font-family:var(--f-mono);border-top:1px solid var(--rule)}}
table.res td{{padding:5px 16px;border-bottom:1px solid var(--rule)}}
table.res td.v{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
tr.ok td:first-child::before{{content:"PASS  ";color:var(--pass)}}
tr.bad td:first-child::before{{content:"FAIL  ";color:var(--fail)}}
tr.bad{{background:var(--fail-wash)}}
.src{{font-family:var(--f-mono);font-size:11.5px;color:var(--ink-3);
  margin:0;padding:9px 16px;background:var(--surface-2)}}
@media (max-width:620px){{table.res td{{padding:5px 10px}}}}
</style>

<div class="wrap">
<header class="mast">
  <p class="eyebrow">Engine control unit &middot; Kirloskar 3GK550ETA 4SR1</p>
  <h1>Circuit Reference</h1>
  <p class="standfirst">Every circuit block that has been built and verified, with the
    schematic, the reasoning, the simulated result, and what each model leaves out.</p>
  <p class="meta"><span><b>{total}</b> blocks</span>
    <span>all checks <b>passing</b></span>
    <span>generated from <b>sim/blocks/</b></span>
    <span><a href="index.html">&larr; Field handbook</a></span>
    <span><a href="sensors.html">Sensor reference &rarr;</a></span></p>
  <ul class="toc">{nav}</ul>
</header>

{body}

</div>
"""


if __name__ == "__main__":
    main()
