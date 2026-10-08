# Handoff — state of the project, 28 September 2026

Written for the next session (human or Claude) picking this up on
another machine. It says what exists, what is verified, what is open and
what to do next. `docs/status.md` remains the long-form record; this is
the short one.

---

## 1. Standing rules — these override defaults

1. **Safety and reliability come before cost, size and convenience.**
   Check at worst-case corners (datasheet min/max, −40 °C and +125 °C,
   105 °C board ambient, reverse battery, ISO 7637-2 pulse 2a), never at
   typical. Prefer a topology that removes a failure mechanism over one
   that manages it. State failure modes and which direction is safe.
2. **No AI attribution in commits.** No `Co-Authored-By`, no "Generated
   with" line. (Commits `1332322`..`7a189fe` carry such trailers from
   before the rule; they are left alone deliberately — do not rewrite
   that history.)
3. **Deliverables are files in this repository.** No externally hosted
   pages.
4. **Verify with the project venv and `set -o pipefail`.** Never a bare
   `python3`, and never `| tail` in a chain that gates a commit — a
   piped tail once let a 22/24 suite into a commit claiming 24/24.
5. **Nothing is claimed without a check that runs.** A caveat in prose
   gets believed; a corner that is written as an enforced check is the
   one that gets caught. Every finding in this project was found this
   way.

---

## 2. Setting up on a new machine

```bash
git clone https://github.com/mohan4220/ecu25kva.git
cd ecu25kva
python3 -m venv .venv                 # .venv is git-ignored
.venv/bin/pip install numpy markdown matplotlib pypdf schemdraw
```

System packages (not pip):

| Need | Why | Notes |
|---|---|---|
| `kicad` 7.x, with `kicad-cli` | netlist export, SVG/PDF plots | schematics are generated, never hand-edited |
| KiCad stock symbol + footprint libraries | `/usr/share/kicad/{symbols,footprints}` | `hw/gen_footprints.py` derives from them |
| `libngspice.so.0` | the simulator, driven by ctypes | override the path with `NGSPICE_LIB=` if it lives elsewhere |
| `inkscape`, `imagemagick` | only for eyeballing rendered sheets | optional |

**On macOS** (set up 8 October 2026, KiCad 10.0.7, ngspice 42): KiCad
from kicad.org or `brew install --cask kicad`, and Chrome for the PDF
build. **Use ngspice 42, not Homebrew's 47** — on 47, three blocks fail
(`injector_turnoff` and `boost_converter` never finish, and
`metering_unit_pwm` misses by 3 %), and the suite stalls at random.
Build 42 from the release tarball (clang needs one warning disabled):

```bash
curl -fsSL -o ngspice-42.tar.gz \
  https://sourceforge.net/projects/ngspice/files/ng-spice-rework/old-releases/42/ngspice-42.tar.gz/download
tar xzf ngspice-42.tar.gz && cd ngspice-42
./configure --prefix=$HOME/opt/ngspice-42 --with-ngshared --enable-xspice \
  --enable-cider --disable-debug --without-x CFLAGS=-O2 \
  CXXFLAGS="-O2 -Wno-invalid-specialization"
make -j8 && make install
```

Nothing lives at the Linux paths, so the scripts read these instead —
put them in `~/.zshrc`:

```bash
export NGSPICE_LIB=$HOME/opt/ngspice-42/lib/libngspice.0.dylib
export SPICE_SCRIPTS=$HOME/opt/ngspice-42/share/ngspice/scripts   # else no spinit
export PATH="/Applications/KiCad/KiCad.app/Contents/MacOS:$PATH"
export KICAD_SYMBOL_DIR=$HOME/opt/kicad7-libs/kicad-symbols-7.0.11   # see below
export KICAD_FOOTPRINT_DIR=/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints
export CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

**Generate against KiCad 7.0.11's symbols, not KiCad 10's.** The
generators copy each library symbol into the sheet, so KiCad 10's
library would change every symbol on every regenerated sheet (and
`schlib` cannot read its tab-indented format anyway). With the 7.0.11
library an unchanged sheet regenerates identically, apart from UUIDs.
KiCad 10 is used only for `kicad-cli`.

```bash
mkdir -p ~/opt/kicad7-libs && cd ~/opt/kicad7-libs
curl -fsSL https://gitlab.com/kicad/libraries/kicad-symbols/-/archive/7.0.11/kicad-symbols-7.0.11.tar.gz | tar xz
```

The PDFs come out two pages shorter on this Chrome (326, not 328) with
no source change — font metrics, not content. Don't commit a rebuild
for that alone.

Verify the whole project in one go:

```bash
set -o pipefail
.venv/bin/python sim/run_sim.py | tail -3        # expect 25/25 blocks pass
.venv/bin/python hw/check_netlist.py | tail -6   # expect "schematic connectivity OK", 2 open items
.venv/bin/python hw/assign_passives.py           # expect 232 packaged, 0 unresolved
.venv/bin/python docs/build_pdf.py | tail -1     # rebuilds docs/pdf/ECU-Bible.pdf
```

**The schematics are generated.** Edit `hw/gen_sheet_*.py`, then
`.venv/bin/python hw/gen_sheet_<name>.py --force`. Without `--force` the
generator refuses to overwrite a non-empty file. After adding or
re-valuing any R or C, re-run `assign_passives.py` and then regenerate
the sheets again so the footprints land.

---

## 3. Where things stand

**Phase 2 (schematic capture) is complete and checked.** Ten
hierarchical sheets, root wired, project netlist verified. Phase 3
(part selection) is most of the way through; phase 4 (PCB) has not
started, and no firmware exists.

| Gate | State |
|---|---|
| Simulation blocks | **25 of 25 pass** |
| Netlist connectivity | **passes**, with 2 named open items |
| Footprints | **363 of 365** components |
| Chip R and C packaged | **232 of 232** |

**Verified part numbers** are in `docs/bom_requirements.md` under
"Chosen parts" — every one against a datasheet that was actually
retrieved and read. That now covers the MCU, regulators, supervisor,
gate drivers, current-sense and difference amplifiers, comparator, the
boost controller, all sixteen power FETs, the small-signal FETs, 27
diodes, the gate-rail transistors, the buck inductor, and the packaging
of every chip resistor and capacitor.

**Design decisions taken with the owner** are in
`docs/decisions-log.md` — the four approved findings, the discrete-input
redesign and the sensor-supply redesign, with the options and reasoning
for each.

---

## 4. What is open, in the order I would do it

### 4.1 Three approved redesigns: all three built

1. **POWER-PATH — built 8 October 2026.** Pin 04 now feeds `VBAT_INJ`
   and pin 06 feeds `VBAT_EGR`, each through a TVS, an
   SQM120P10-10m1L reverse P-FET and a Schottky (`power_path.cir`, and
   the netlist gate checks the split). Pin 21's L101, L102 and F101
   are chosen for its new 2.95 A bound (`docs/bom_requirements.md`
   § POWER-PATH, with the thin margins stated). Left over: the two new
   rails' conducted emissions, and F101's pulse-cycling data. The original item read: move
   the injector and EGR supply onto connector
   pins 04/06 (10 A fused each in the loom) with their own protection,
   leaving pin 21 feeding the electronics through the EMI filter and
   reverse FET. Today every high-current load runs through a path whose
   reverse FET was sized for 5 A and whose filter never stated a DC
   current. Blocks: L101, L102, F101. See `docs/bom_requirements.md`
   § POWER-PATH.
2. **SENSOR-PTC — built 8 October 2026.** The cut-off is a TPS48110-Q1
   (chosen over the LTC4368 for AEC-Q100, decisions log §7).
   `sensor_rail.cir` is rewritten and the trackers' input peaks at
   22.3 V. C211 and both land patterns were done 8 October.
   The original item read: one TPS7B4253-Q1 per sensor group, ADJ
   tracking 5V_MAIN, behind a 100 V-class overvoltage cut-off (an
   LTC4368-class controller was the candidate; **its datasheet was not
   retrieved yet — do that first**) with a 47 µF hold-up capacitor. The
   cut-off exists because the tracker's IN pin is rated 45 V and the
   rail reaches 73.3 V for 50 µs. Replaces F201–F203 and the whole
   SENSOR-PTC requirement. `sensor_rail.cir` needs rewriting with it,
   including the fault-containment check (one group shorted, the other
   two and the MCU unaffected).
3. **BOOST-SLOPE — built 8 October 2026.** VDD comes from a follower off
   the output (34.3–45.0 V), with the battery for start-up only. L401
   is **150 µH**, Würth 7447709151 (decisions log §8 revised the
   approved 100 µH), and the sense resistor is 62 mΩ. Equation 9 holds
   by 1.12× at the worst corner, oscillator −20 % included. The original
   item read: feed the TPS40210's VDD from the clamped output
   side to steepen its internal ramp, and drop L401 to 100 µH (Würth
   7447709101, Isat 3.1 A typ, AEC-Q200). Re-check TI Equation 9 at the
   cranking corner after the change; the current design is 1.83× over
   its ceiling there. The check that pins the finding is in
   `run_sim.py` under `boost_converter`.

### 4.2 Parts still unchosen

The three non-ceramic capacitors were chosen 8 October 2026 (decisions
log §9): C313 is a KEMET T599 polymer tantalum with a 22 mΩ series
resistor (R306) as its ESR floor. C211 is a Chemi-Con HXC 47 µF 63 V.
C401 + C420 are two HXC 82 µF 80 V cans in series, balanced by the
2 × 11 kΩ bleed. What is left:

- **The trip-loop clamp** — the LOWV-CLAMP residual. It is the one input
  that still needs a continuous clamp, because its healthy band *is* the
  clamp level. It is also blocked on a connector pin.

### 4.3 Blocked on the machine or a supplier

- **The power ground.** GND reaches the connector only through
  sensor-ground pins 8/30/44. The 18 A injector return has no pin. The
  netlist gate now counts this as an open item rather than passing
  silently. Field brief tasks 1.1 and 5.1 settle it — pins 01/02
  (`G_G_B AT1/AT2`) are the hypothesis.
- **`TRIP_LOOP` has no connector pin** — it is not on the OEM diagram
  and needs one of the 50 unconfirmed pins.
- **The Bosch 94-way land pattern** — needs a distributor drawing for
  1 928 405 192 / 194, code C. The board carries the OEM connector
  (spec §7 deviation 1 reversed), so this is the board's own header.
- **U16, the alternator rectifier** — still decides which ISO 7637-2
  pulse applies, and would change the transient design if answered.
- **MC33816AE last-time-buy 06/08/2027** — needs a distributor, not
  another search. It only matters for the fallback path. (The L9781
  item is closed: the owner supplied ST's data brief on 8 October,
  confirming its 80 V tank ceiling.)

### 4.4 The 2 components still without a footprint

| Parts | Why |
|---|---|
| J1001 | the Bosch 94-way header: needs the distributor drawing (§4.3) |
| D806 | the trip-loop clamp, the LOWV-CLAMP residual |

`hw/gen_footprints.py` holds the project footprints. It derives two from
stock by renumbering pads: a TO-277A and a SOT-23 zener, whose stock pad
numbering would otherwise have reversed the part. It also **draws** four
from the makers' recommended layouts (8 October): SMPD for D408–D414
(tab = cathode = pad 1), WE-PD 1050 for L201, TI DGX0019A for U203
(position 16 empty) and TI DDA0008J for U204–U206 (thermal pad 2.95 ×
4.9 copper, 2.6 × 3.2 solder-mask-defined opening). They are written in
KiCad 7 format. The installed KiCad 10 library is newer than KiCad 7
can open, so the script skips re-deriving the two stock copies from it.
TI's optional thermal vias under the DDA pad are left to layout.

### 4.5 Then

Firmware skeleton (phase 4) and PCB layout (phase 5). Layout should not
start before POWER-PATH is settled, since it changes which copper
carries 18 A.

---

## 5. Traps worth knowing before editing

These each cost a debugging session already:

- **A wire endpoint landing mid-span does not connect** in KiCad 7, even
  with a junction in the file. The page plots correctly and the netlist
  says "unconnected". Use `schlib.Rail`, which splits every segment at
  its taps.
- **A label's justification is read in its own rotated frame.** At 180°,
  "left" puts the text back across its own wire. Both label types are
  fixed in `schlib`; keep it that way.
- **Pin numbers are not pad numbers.** A SOT-23 FET symbol (G-S-D) on a
  DPAK footprint puts the source on the tab. Power FETs use the G-D-S
  symbols; BJTs in SOT-23 are B-E-C; BZX84 zeners and TO-277A diodes
  need the renumbered footprints from `gen_footprints.py`.
- **Auto-generated net names move.** `Net-(R407-Pad2)` changes the
  moment a part is added ahead of it, and `assign_passives.py` keys
  voltages on net names — so give any node whose voltage matters a real
  label.
- **`--force`**, or the generator keeps the existing sheet.
- **The ngspice version matters.** The suite passes on ngspice 42
  and fails on 47 (see §2). Upgrading the simulator is a change that
  needs the whole suite re-run, not a routine update.
- **Simulation models hide things.** An idealised zener hid both the
  leakage that started LOWV-CLAMP and an 84 mV loading error that a
  passing check had pinned as the expected value. When a model's part
  gets chosen, re-fit the model to the datasheet.

---

## 6. Repository map

| Path | What it is |
|---|---|
| `hw/gen_sheet_*.py` | the ten sheet generators — the schematic source of truth |
| `hw/schlib.py` | drawing primitives, pin geometry, the chosen-parts table |
| `hw/assign_passives.py` | packages every chip R and C from the voltage across it |
| `hw/gen_symbols.py`, `hw/gen_footprints.py` | project symbols and renumbered footprints |
| `hw/check_netlist.py` | the connectivity gate: shadowed nets, decoupling, rails, open items |
| `sim/blocks/*.cir` | 25 self-checking SPICE blocks |
| `sim/run_sim.py` | runs them and asserts every claim as arithmetic |
| `docs/bom_requirements.md` | requirements, chosen parts, and the open design items |
| `docs/status.md` | the long-form running record |
| `docs/decisions-log.md` | decisions put to the owner, with options and reasoning |
| `docs/pinmap.md` | pin assignments, including the inverted discrete inputs |
| `docs/research/` | twelve research memos |
| `refs/` | OEM wiring diagram, machine photographs, extracted pinout, field evidence |

`README.md` is stale in its counts (it said 163 pages,
17 blocks and nine memos; it is now 328 pages, 24 blocks and twelve
memos, and it has been corrected). Worth a pass.
