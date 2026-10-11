# PCB preparation for hand routing: design

**Date:** 2026-10-11
**Status:** design agreed in conversation; written for review.
**Phase:** 3, PCB layout (status table). It starts from the complete
schematic: 379 parts, 377 with footprints, connectivity OK.
**Decisions taken in conversation:**
- **I prepare, a person routes.** I prepare the board; a layout engineer
  routes it by hand in KiCad.
- **The board goes in the old ECU's housing.** The board outline,
  mounting points, cooling contact areas and the J1001 header all come
  from measuring the old unit.

---

## 1. Purpose

Hand the layout engineer a board that is ready to route:
- every part on it, grouped by circuit block and placed sensibly
- every rule set: stack-up, net classes, clearances, widths
- a written guide to what matters in each block

Everything that depends on the old housing is a clearly marked
placeholder, so the routing starts the day the measurements arrive.

**Success:**
- `hw/ecu25kva.kicad_pcb` opens in KiCad with all 379 footprints, every
  net and every net class.
- KiCad's design-rule check reports no clearance or courtyard
  violations among the placed parts. Unrouted connections are expected
  and allowed.
- The layout guide and the field measurement brief are in the bible.

## 2. Stack-up

**Board:** 4 layers, 1.6 mm FR-4, **high-Tg (≥ 170 °C)**, because it
sits in an engine bay.

| Layer | Copper | Use |
|---|---|---|
| L1, top | 2 oz (70 µm) | Parts, power copper, short signals |
| L2 | 1 oz | **Solid ground plane**, unbroken under the switching stages and the MCU |
| L3 | 1 oz | Power distribution (VBAT, 5 V, 3V3, 12V_GATE) and slow signals |
| L4, bottom | 2 oz | Power copper, heat spreading into the housing contact areas |

Two rules follow from this stack-up:
- The ground plane is split nowhere. Power and signal returns separate by
  *placement and routing*, not by cutting the plane.
- The single point where the injector return meets the sensor ground is
  fixed in the layout guide.

## 3. Net classes and rules

Widths come from the IPC-2152 current-versus-temperature-rise
relationship. Every width allows a **20 °C rise at 85 °C ambient** and
is computed by the generator, not typed in. Clearances follow **IPC-2221B
table 6-1, external, uncoated**, so the board is safe even before any
conformal coating.

| Class | Nets | Current | Width (outer, 2 oz) | Clearance |
|---|---|---|---|---|
| `PWR_HI` | VBAT_INJ and its feed, the injector return path, VBAT_PROT trunk | 18 A | computed (≈ 6 mm outer, or split across layers) | 0.6 mm |
| `PWR` | VBAT_EGR, the EGR bridge, the metering valve, 12V_GATE, the 5 V/3V3 trunks | ≤ 6.4 A | computed | 0.3 mm |
| `HV100` | the boost rail (BOOST_MID, the reservoir, the boost switch node), the injector high-side | 100–116 V peak | computed | **0.6 mm** (101–150 V) |
| `CAN` | CAN_H/L, both channels | — | for 120 Ω differential | 0.2 mm |
| `ANALOG` | sensor inputs before the ADC | — | 0.25 mm | 0.2 mm |
| `Default` | logic | — | 0.2 mm | 0.15 mm |

Nets are assigned to classes by name, in one table in the generator. Any
power net that is not assigned is reported as a failure, so a new power
net can't silently default to a thin trace.

## 4. Placement plan

Parts are placed **by sheet** (the schematic's ten blocks), each block a
KiCad group:
- **Connector side:** power input, CAN, discrete inputs and the
  connector sheet sit nearest J1001, each closest to its own pins.
- **Housing contact zone:** the parts that make heat. That's the injector
  FETs and turn-off diodes, the boost switch and diodes, the EGR bridge,
  the metering-valve driver and the regulators. They go where the old
  board touched the case. Until that is measured, the zone is a
  placeholder band along the edge opposite the connector.
- **Quiet zone:** the MCU, its decoupling, the sensor front-ends and the
  supervisor go away from the boost and injector loops, over unbroken
  ground.
- **Tight loops**, placed as close as their courtyards allow:
  - the boost converter's switch loop
  - each injector turn-off loop
  - each feed filter's input loop
  - the MCU decoupling

  The layout guide lists each one, with the loop area the simulations
  assume.

The generator places parts in blocks on a grid, without overlap. Fine
placement inside a block is left to the person routing, guided by §5.

## 5. Layout guide (a new bible document)

`docs/layout-guide.md`, written for the layout engineer. For each block:
- which loop is critical, and why
- where its return current flows
- which simulation (`sim/blocks/*.cir`) assumed what about the copper
- what must not be crossed

It also covers:
- the single-point ground join
- the creepage around the 100 V parts
- the CAN pair
- test points
- the J1001 placeholder, and the rule that **no board is ordered** until
  J1001 and the outline are measured

## 6. What depends on the old housing

| Item | Placeholder until measured |
|---|---|
| Board outline and thickness | 160 × 120 mm rectangle, 1.6 mm |
| Mounting holes | 4 × M3 at the corners |
| Housing contact (cooling) areas | a band 25 mm deep along the edge opposite J1001 |
| Keep-outs for tall parts | none |
| **J1001 footprint and position** | a 94-pad block at 2.5 mm pitch on one long edge, marked "PLACEHOLDER — DO NOT FABRICATE" |
| Power-ground pin | pins 1, 2, 5, 6 (the large corner contacts on the drawing) assumed, marked as an assumption |

All of these sit in one `HOUSING` table at the top of the generator.
When the measurements arrive, updating that table and re-running moves
the outline, holes, zones and connector together.

## 7. Field measurement brief

A new **Group 6** in `docs/research/08-engine-inspection-brief.md`,
written for the person at the machine. It asks for photos with a ruler
or calipers in frame:
1. **The housing:**
   - inside length, width and depth
   - the position and size of the connector opening
   - the mounting bosses (positions, hole size)
   - any thermal pads or contact pedestals inside the lid
2. **The board:**
   - outline, with corners and cut-outs
   - thickness
   - mounting holes
   - where it touches the housing
   - the tallest parts and their heights
3. **The header on the board:**
   - the pin grid (pitch, rows, how many pins per row)
   - which pins are the large ones
   - the mounting pegs or screws
   - its distance from the board edge
   - any marking on it
4. **If the unit can be opened safely:** continuity from the large pins
   to the board ground (closes the power-ground pin), and the cavity
   census (closes the trip-loop pin).

The brief warns not to open the only working ECU on a running genset;
use a spare or dead unit, or wait until ours replaces it.

## 8. Tooling

- `hw/gen_pcb.py` builds the board with KiCad's own Python (`pcbnew`,
  bundled with the installed KiCad):
  - footprints, from the same assignments the schematic uses
  - nets
  - net classes and rules (also written into `ecu25kva.kicad_pro`)
  - groups, outline, holes, zones
- `hw/check_pcb.py` runs `kicad-cli pcb drc` and checks:
  - 379 footprints
  - every net present
  - every power net in its class
  - the computed widths
  - no clearance or courtyard violations
  - unrouted connections are reported as a count, not a failure
- Regenerating is safe: `gen_pcb.py` refuses to overwrite a board that
  has routing in it, unless forced. Once a person starts routing, the
  generator only updates rules.

## 9. Out of scope

- Routing.
- Fabrication outputs (Gerbers, drill files, assembly) and the fab-house
  stack-up confirmation. These come after routing and after the housing
  and J1001 measurements.
- The enclosure itself.
- The S32K148 dev-kit spec.
