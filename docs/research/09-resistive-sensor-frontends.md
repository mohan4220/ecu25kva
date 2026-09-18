# Research Memo 09: Resistive Temperature Front-Ends — DSE and SEDEMAC Prior Art

> ### UPDATED 18 Sep 2026 — DSE is not just prior art here, it is the fitted controller
>
> This memo studied Deep Sea Electronics and SEDEMAC as **prior art** — other vendors'
> answers to a problem we share. It opened by noting that both are genset-controller
> class devices, "the same class of device as the KG640C we talk to", and was careful
> that findings from them might not transfer.
>
> The controller on this machine has since been photographed. It is a **Deep Sea
> Electronics DSE4522 MKII AMF**. The DSE practice described below is therefore not
> analogous guidance from a comparable product — **it is the behaviour of the device
> this ECU actually has to work alongside.**
>
> That strengthens §3.1's ground-offset finding considerably. DSE's own manual for the
> fitted module's siblings (`057-260`) is emphatic about it: *"It is VERY important that
> terminal 10 (sensor common) is connected to an earth point on the ENGINE BLOCK, not
> within the control panel … This connection MUST NOT be used to provide an earth
> connection for other terminals or devices."* The differential front-end recommendation
> in §4 has been adopted into spec §4.
>
> §3.4's scaling caveat also held up under its own test: `sim/blocks/ntc_frontend.cir`
> found that copying DSE's constant-current topology onto a 670:1 automotive NTC runs out
> of rail compliance at the cold end. The divider survived.
>
> The SEDEMAC material remains what it was — prior art, snippet-sourced, and still not
> verified against a retrieved manual.


**Task:** U2 supporting research — how two established genset-controller vendors
build resistive temperature sensor inputs. Consumes memo 02 (KG640C is the same
class of device). Feeds the sheet 3b analog front-end and a re-examination of
the already-simulated `sensor_ratiometric` block.
**Date:** 2026-09-14
**Author:** Follow-up research, phase 1 exit

---

## Verdict (read this first)

**Neither vendor uses a plain pull-up divider to a fixed rail** — the topology
this project had planned for the U2 NTC branch.

- **Deep Sea Electronics** forces a **fixed current** through the sender and
  measures the voltage across it with a **differential** input, specified for
  **±2 V of common-mode** (ground offset) rejection. *(Confirmed — read directly
  from two DSE operator manuals.)*
- **SEDEMAC** uses **ratiometric** resistive sensing with a dedicated **sensor
  common point** terminal bonded to the engine body. *(Secondary — see the
  sourcing caveat in §2; the manual itself could not be retrieved.)*

**This does not close U2.** Both are genset *controllers* — the same class of
device as the KG640C we talk to, not the common-rail ECU we are replacing. They
read VDO/Datcon-style senders bolted into the block; U2 concerns a charge-air
temperature element inside a 4-pin P&T combo on a common-rail engine. This is
prior art on how to build the resistive branch **well**, not evidence about
which branch this engine is on. Brief task 1.3's resistance measurement remains
the only thing that settles U2.

---

## 1. Deep Sea Electronics — constant current, differential

Two generations of the same controller, both read directly from the operator
manuals via text extraction. **Confirmed.**

### DSE8610, Operator Manual Issue 5, document 057-115

| Channel | Excitation current | Full scale | Over range / fail |
|---|---|---|---|
| Oil pressure | 15 mA | 240 Ω | 270 Ω |
| Coolant temperature | 10 mA | 480 Ω | 540 Ω |
| Flexible sensor (×2) | 10 mA | 480 Ω | 540 Ω |

### DSE8610 MKII, document 057-254 Issue 3

Unified every channel on **15 mA, 480 Ω full scale, 600 Ω over range/fail**, and
made all four inputs selectable between resistive, 0–10 V and 4–20 mA modes.

### The wording that matters

Identical across every channel of both generations:

> **Measurement type:** Resistance measurement by measuring voltage across
> sensor with a fixed current applied
> **Arrangement:** Differential resistance measurement input
> **Max common mode voltage:** ±2 V
> **Accuracy:** ±2 % of full scale resistance, excluding sensor error

Sources (both downloaded and text-extracted, not read from search snippets):
- https://www.reactpower.com/wp-content/uploads/2020/07/DSE8610-Control-Panel.pdf
- http://www.davidsonsalesshop.com/catalog/files/Products/Deep%20Sea/DSE8610MKII%20Manual.pdf

---

## 2. SEDEMAC — ratiometric, with a dedicated sensor common point

**Sourcing caveat, stated plainly:** every attempt to retrieve a SEDEMAC manual
failed. ManualsLib, Manualzz and Scribd all returned HTTP 403 to direct fetch,
and one aggregator link redirected to an unrelated cryptocurrency domain and was
not followed. The figures below come from **search-result snippets**, consistent
across two independently phrased queries, and are recorded as **secondary,
unverified against the document itself**. They should not be used as design
numbers without retrieving the manual.

GC1200 series, analog resistive sensor inputs on terminals 24 / 25 / 26 (engine
temperature, fuel level, lube oil pressure):

| Property | Value |
|---|---|
| Type | Ratiometric sensing |
| Range | 10 Ω to 1000 Ω |
| Open-circuit detection | Above 5.5 kΩ |
| Accuracy | ±2 % of FSD up to 1000 Ω |

Separately, terminal 41 is a **sensor common point (SCP)**, specified to bond
directly to an electrically sound point on the engine body, serving as the
shared reference for all analog senders.

Sources (snippet-level only):
- https://www.scribd.com/document/558526157/sedmac-controller-manual-1202
- https://www.manualslib.com/manual/1474533/Sedemac-Gc1100.html

---

## 3. What transfers to this design

### 3.1 The differential input is the load-bearing finding

DSE specifies ±2 V common-mode rejection on every sender channel, and SEDEMAC
solves the same problem from the other direction by insisting on a dedicated
sensor common point bonded to the engine body. Both are addressing **ground
offset between the sensor's return and the controller's reference**.

This project has that exact problem, and it is visible in the OEM wiring:
**pin 34 is a shared sensor ground, spliced between the boost P&T sensor and the
coolant sensor** (per `refs/ecu-pinout-extracted.md`, splice V3). A shared return
carries the other sensor's current, developing an offset across the harness
resistance. A differential input rejects that offset; a single-ended input reads
it as signal.

**`sim/blocks/sensor_ratiometric.cir` is single-ended.** It passes its checks,
but those checks never modelled a ground offset, so passing does not mean the
topology is right for a shared return. This is a gap in the *check set*, not a
failure of the simulation — and it is exactly the kind of thing the simulation
programme exists to catch. It should be re-examined before sheet 3b is drawn.

Worth noting the OEM's own hierarchy here: the rail-pressure sensor gets a
**dedicated** ground (pin 08, not spliced), while boost and coolant share pin 34.
Whoever designed that harness ranked the channels by how much ground offset each
could tolerate. That ranking is information, and it agrees with SEDEMAC's SCP
discipline.

### 3.2 Fault detection belongs in the range, not bolted on

Both vendors reserve a band above full scale as the fault region — DSE
480 Ω → 600 Ω, SEDEMAC anything above 5.5 kΩ. An open or shorted sender lands
somewhere that is unambiguously **not a temperature**, rather than pinning to a
rail where it could be read as a plausible cold or hot value. Front-end
component values should be chosen so both failure modes land outside the
signal band, and firmware should treat that band as a distinct state.

### 3.3 Constant current linearises the readout

With a pull-up divider, the measured voltage is `Vref · R / (R + Rpu)` —
non-linear in R, so resolution varies across the range and the pull-up's
tolerance enters the result directly. With a forced current it is `I · R`,
linear, with the current source's accuracy as the only gain error. That is why
DSE does it, and it costs a current source per channel.

Ratiometric sensing (SEDEMAC's approach, and the one already used on this
project's pressure channels) does not linearise, but it does cancel supply
drift by making the ADC reference track the excitation. The two approaches
solve different halves of the problem.

### 3.4 The current values do NOT transfer — a scaling caveat

These controllers expect senders in the **tens to hundreds of ohms** (VDO/Datcon
range). This project's own inspection brief predicts **"a few kΩ"** for the NTC
case at task 1.3. Forcing DSE's 15 mA through a few kΩ would demand tens of
volts and is impossible on a 5 V sensor rail.

If the constant-current topology is adopted, excitation must be scaled to
roughly the **100 µA class** for a kΩ-range NTC. Copying DSE's numbers directly
would be a straightforward and expensive mistake. **Inferred** from the
resistance ranges involved, not sourced.

---

## 4. Recommendation

1. **Upgrade the U2 mitigation.** The register's original hedge was a
   do-not-populate pull-up so either sensor type would work. That hedge assumed
   the NTC branch is a divider. Design the front-end so the branch can be either
   a scaled current source or a divider, and the choice remains a populate
   option after task 1.3 answers U2.
2. **Add a ground-offset check to `sensor_ratiometric`** before drawing sheet 3b,
   and reconsider a differential front-end for the two channels that share
   pin 34. The block's current PASS verdict does not cover this case.
3. **Retrieve a SEDEMAC manual properly** before using any figure in §2 as a
   design number. Everything there is snippet-level.

---

## 5. Negative results, recorded

- No DSE application note on wiring resistive sensors was retrieved, though
  search results reference one existing on the DSE site. Its guidance on common
  wiring mistakes would likely be relevant and was not obtained.
- No SEDEMAC document was retrieved in full. Three separate hosts refused.
- Neither vendor publishes a schematic of the input stage — only its
  specification. The internal topology in §1 is read from the specification's
  own wording ("fixed current applied", "differential"), which is explicit
  enough to be treated as confirmed, but no circuit diagram was seen.
