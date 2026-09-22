# Engine Inspection Brief — Field Checklist

> ### STATUS 18 Sep 2026 — part of this brief is done
>
> A first visit has happened and photographs came back. **Four register items closed**,
> and the tasks that closed them are ticked below. What remains is mostly the
> multimeter work, which is the part that actually gates the design.
>
> **Closed:** U11 engine identity (task 3.1 — the plate reads `3GK550ETA 4SR1`, *not*
> the model memo 01 inferred) · U1 the connector (tasks 3.4–3.8 — Bosch
> `1 928 405 192` / `194`, **code C**) · U13 which controller is fitted (**DSE4522
> MKII AMF**, not a KG640C — this was not a task in this brief, it was raised by the
> evidence itself) · U3 no speed pickup (from DSE's manual).
>
> **UPDATE, later on 18 Sep: U12 is CLOSED, and it closed badly.** Reported from the
> machine: **the fuel relay cuts a signal, it does not remove power.** That is the
> outcome task 2.1's table told the reader to flag immediately. §3's second line of
> defence terminates in the failure it was meant to catch, and the standalone trip
> module is now the only shutdown path on this machine that does not require the
> cooperation of the ECU being protected against. Task 1.4's contact-type check is still
> wanted as confirmation — see `refs/field-evidence-2026-09-18.md` §4 for why nothing
> depends on it.
>
> **Also reported:** the intake throttle and the pre/post-heaters are **battery-fed**.
> That answers who supplies them, not who commands them — tasks 3.11 and the U14 trace
> both still stand.
>
> **Also still open and cheap:** task 1.3 (U2, one resistance reading) and task 3.11
> (U8, follow one cable by hand).
>
> **SECOND VISIT, 21 Sep 2026 — see Group 5 at the foot of this brief.** Seven new
> tasks, written after the schematics were drawn rather than from documents. **5.1
> blocks the board outright: the 94-way connector has no identified
> battery-negative pin, and every circuit on the new board returns to a net that
> currently has nowhere to land.** 5.7 and the still-open 3.11 are the only two
> items that can make the board bigger, so both want answering before layout.
>
> **New since this brief was written**, worth adding to the next visit: trace the
> **pre-heat / post-heat** supply — the DSE4522's configuration enables both at 50 °C
> and this design has no heater output at all (U14).


**Purpose:** close every open unknown that no amount of desk research can close — only
a person with a multimeter and a camera, at the machine, can. Closes or advances
**U1, U2, U4, U6, U7, U8, U9, U10, U11, U12**, plus the pin 01/02 ground question
raised in the reconciled spec.

**Print this. Carry it. Tick boxes as you go — a half-finished visit is still useful
if the ticks say which half.**

Sources: reconciled spec `docs/superpowers/specs/2026-09-13-ecu-reconciled-spec-design.md`
(§3 safety, §8 unknowns register), `refs/ecu-pinout-extracted.md`, research memos
`docs/research/01-engine-identity.md` and `docs/research/03-ecu-connector.md`. Every
expected reading below cites one of these. Anything not sourced is marked **inferred**.

---

## SAFETY — read this before touching anything

This is a 25 kVA genset: a diesel engine that can start, and a 415 V three-phase
alternator. This checklist is bench/inspection work only.

- **Battery disconnected before any continuity or resistance measurement.** Negative
  terminal off first, isolated, out of reach of the positive post.
- **Nothing inside the alternator output enclosure.** No task here requires it. If you
  find yourself reaching toward the 415 V output terminals, stop — that is not this
  checklist.
- **The engine does not run during any of this.** Every task below is done with the
  engine off. Ignition-on tasks mean the key/master switch position only, never
  cranking or running.
- **If a measurement needs the set running** (this includes the full CAN log in
  Group 4, which may need it), **that is a separate supervised activity**, done by
  someone qualified to run the set, not a solo checklist item. Note it as such and
  move on.
- Reconnect the battery only after Group 1 is fully complete and you've checked no
  tools or leads are left on the terminals.

**Materials:** digital multimeter (V, Ω, continuity beep), clamp meter if available
(safer than breaking a fused circuit for current), phone/camera with flashlight,
notebook or voice memo, 10 mm socket for the battery terminal, tape/marker for
labelling. **Group 4 additionally needs a USB-CAN adapter and a laptop** — it may
warrant its own trip.

---

## Group 1 — Battery disconnected (continuity / resistance)

Do these first, in this order, with the battery negative terminal removed and
isolated.

- [ ] **1.1 — Pin 01/02 ground hypothesis.** Continuity from ECU connector pins **01**
  and **02** to battery negative / chassis ground.
  - *Why:* the connector drawing places 01/02/05/06 as large power contacts, but 01/02
    are labelled `G_G_B AT1`/`AT2` — switch-return legs, which wouldn't need a large
    contact. The alternate reading: `G_G_B` = battery ground, and these are the ECU's
    main power grounds (also the only explanation for why no power-ground pin appears
    anywhere in the 44-pin extraction). *(spec §4 note; pinout "Digital inputs")*
  - **Continuity (near 0 Ω) → hypothesis confirmed:** 01/02 are power grounds, not
    switch returns. Update the pin map and power/ground plan.
  - **Open circuit → hypothesis wrong.** They're isolated switch-return legs as
    originally labelled; the power-ground pin(s) remain unidentified — keep looking
    during Group 3 tracing.

- [ ] **1.2 — Pin 09 "synchronization ground."** Continuity from pin **09** to (a)
  battery negative and (b) a known sensor ground pin (e.g. 34 or 08).
  - *Why:* pin 09 is named as a ground but drawn in **red** (switched-battery colour
    class), which is contradictory on its face. *(spec §4, "Power"; pinout, U6 entry)*
  - **Continuous to battery negative →** it likely is a ground point, oddly coloured
    in the diagram for harness-routing reasons, not a live signal. Note this for §4 but
    treat as resolved.
  - **Open to both →** it is *not* a simple ground. Carry to Group 2 (2.3) for a
    voltage measurement — the red wire colour then means what it usually means.

- [ ] **1.3 — Boost sensor thermistor topology (closes U2 outright).** Boost P&T
  sensor unplugged, engine **cold**. Resistance across sensor pins **2 and 1**
  (ECU pins 79 / 34 per the pinout — temperature signal / sensor ground).
  *(brief; spec §8 U2; pinout "Analog sensors")*
  - **A few kΩ, falling if you re-check once the engine's warmed a little →** NTC
    thermistor. Design a pull-up divider front-end. **U2 closed.**
  - **Open circuit, or a fixed high reading that doesn't move with temperature →**
    not a bare NTC — a conditioned/ratiometric output. Design the ratiometric
    front-end (same as the pressure channel). **U2 closed.**
  - This is a single measurement. Either outcome closes U2 — there is no third case.

---

- [ ] **1.4 — Ignition relay contact type.** *(Still wanted 18 Sep as confirmation; task 2.1 has since been answered the other way round — see the status banner.)* **Do this BEFORE task 2.1; it decides how 2.1's
  result is read.** Locate ignition relay `-13RB1` on the GCU relay board. With the
  battery disconnected and the relay coil unpowered, measure continuity across its
  **load contacts** (not the coil).

  *Why this matters and why 2.1 is ambiguous without it:* task 2.1 reads voltage with
  the ignition switch off, assuming that is the relay's de-energised state. If the
  relay turns out to be normally-closed, "de-energised" means contacts **made** and
  power still present — so a battery-voltage reading in 2.1 would mean the test state
  was wrong, not that the relay only signals. Those two have opposite conclusions and
  the same reading. This measurement separates them. **Inferred concern, not sourced —
  raised because the relay's drive logic is not documented anywhere we have.**

  | Continuity across load contacts, coil unpowered | Meaning for task 2.1 |
  |---|---|
  | **Open** (normally-open, energise to run) | Expected case. 2.1's table reads as written. |
  | **Closed** (normally-closed, energise to cut) | 2.1's table is **inverted**. Battery voltage with the switch off is then normal, and U12 must instead be tested by energising the relay and re-measuring. Note it and flag it. |

## Group 2 — Ignition switch tests (battery connected, engine OFF, not cranking)

Reconnect the battery for this group only. Key/master switch is the only thing that
moves. **Do not crank or start.**

- [ ] **2.1 — U12, the priority item. Complete task 1.4 first.** Ignition/master
  switch **OFF**. This is assumed to be ignition relay `-13RB1`'s de-energised state —
  **task 1.4 confirms that assumption, and if it fails, the table below inverts.**
  You do not need to pull or force the relay. If you
  can see or hear the relay (GCU relay board), confirm it looks/sounds unenergised
  before measuring; photograph its label to confirm 70 A rating.

  With the switch OFF, measure voltage (relative to chassis/battery negative) at:
  - ECU connector pin **21** (battery+ feed)
  - ECU connector pin **04** (`V_V_BAT_1R`)
  - ECU connector pin **06** (`V_V_BAT_2R`)
  - the **fuel metering unit's own pin 2** (its battery-fed pin, via 20 A fuse `8F1`
    — not ECU pin 88, which is the ECU's PWM output to metering unit pin 1)

  *Why this is the whole point of the trip:* spec §3's safety argument — that a hung
  ECU can't keep injecting because the GCU physically removes fuel-system power —
  depends entirely on this. *(spec §3, §8 U12)*

  | Reading at all four points | Meaning |
  |---|---|
  | **0 V (no battery voltage present)** | Relay **removes power**. §3's second line of defence is real. U12 closed in the safe direction. |
  | **Battery voltage present at any of them** | Relay **signals only** — power stays up through a hung ECU. §3's relaxation is void: reverts to "standalone MPU trip module mandatory." **Flag this immediately, do not wait for the writeup.** |

- [ ] **2.2 — U7: are pins 04/06 sense-only or load feeds?** Switch **ON** (engine
  still off). Re-measure voltage at pins 04 and 06 (expect battery voltage present
  now, per 2.1's contrast — that alone doesn't answer U7).
  - **Then measure current**, preferably with a clamp meter on the wire (safer — no
    circuit break). If only a multimeter is available, break the circuit at the fuse
    holder for 04/06 and measure DC current in series, briefly.
  - *Why:* sense lines draw milliamps; something that's actually feeding a load draws
    amps, and each fuse is rated 10 A. *(brief; spec §8 U7; spec §4 "Power" — both
    pins are 10 A fused)*

  | Current | Meaning |
  |---|---|
  | **mA range** | Sense-only — these just feed the battery-voltage ADC divider. Power sheet needs no extra current rating here. |
  | **Amps, approaching the 10 A fuse rating under some load state** | Load feed — something downstream draws real current through the ECU. Power sheet must size for it. |

- [ ] **2.3 — Pin 09, if 1.2 left it open.** Switch ON. Voltage at pin 09 vs. chassis.
  - **~0 V →** confirms a ground reference despite the odd wire colour.
  - **Switched battery voltage →** it's a real signal wearing a "ground" name — treat
    as an undocumented discrete/analog input, not a ground. Note whatever else in the
    harness moves when this changes (if observable) as a clue to its function.

---

## Group 3 — Photography (engine off; battery may be either state, disconnect
preferred while working around the engine bay)

For each: square-on unless noted, fill the frame, flash off / raking light for
part numbers (on-axis flash washes out shallow embossing).

- [x] ~~3.1 DONE 18 Sep~~ — **Engine rating plate** (rocker cover / flywheel housing / block side).
  Get legible: model string (expect something matching **`3R550ETA`** — anything
  else means the engine-identity inference in memo 01 is wrong and should be
  discarded, not patched), serial number, rated output/speed/frequency, any
  emissions certification mark. **Closes U11.** *(memo 01, "What would close this")*
- [ ] **3.2 Genset nameplate** (canopy/control panel). **Do not go looking for a string
  you expect.** This brief originally said to expect `KG4-25WS1`, inferred from memo 01's
  engine identification — and that identification turned out to be wrong when the engine
  plate was read. The genset model inference came from the same chain and is equally
  unsupported. Photograph whatever is actually on the plate, including the serial number.
  *(memo 01, and its correction)*
- [ ] **3.3 ECU case label.** Flat, well-lit. Hunting a vendor part number — Bosch
  EDC pattern `0 281 0xx xxx`, Bosch-reseller pattern `F 01R 0xx xxx`, or any
  Continental/Delphi/Denso mark. **Now more likely to pay off than when this was
  written:** the connector is confirmed Bosch (`1 928 405 192` / `194`), so a Bosch
  part number on the case would be consistent and would identify the OEM ECU outright. Would resolve the still-open OEM-ECU-vendor
  question. *(memo 03 §4 item 4)*
- [x] ~~3.4 DONE 18 Sep~~ — **ECU connector — full-face, mating side, connector unplugged.** Determines
  at a glance: flat rectangular multi-row grid (Bosch/Delphi-style) vs. oval/rounded
  single-lever shell (AMPSEAL-style) — the top-level branch of the connector
  shortlist. **Advances U1.** *(memo 03 §4 item 1, ranked candidate table)*
- [x] ~~3.5 DONE 18 Sep~~ — **Connector retention mechanism**, actuated and disengaged, if it can be
  operated safely with the connector unplugged. Lever vs. slide latch vs. bolt vs.
  friction/CPA clip. *(memo 03 §4 item 2)*
- [x] ~~3.6 DONE 18 Sep~~ — **Raking-light pass over every flat face of the connector housing** — top,
  both sides, cable boot. Hunting molded/raised part number, date code, or logo:
  Bosch roundel, Delphi/Aptiv wordmark, TE Connectivity mark. Take several shots at
  different light angles if the first doesn't show text. **Would settle U1's
  connector-family ranking outright if a logo turns up.** *(memo 03 §4 item 3)*
- [x] ~~3.7 DONE 18 Sep~~ — **Connector still mated, wide shot** — backshell, cable exit angle, strain
  relief. Feeds the adapter-harness design even without a family ID. *(memo 03 §4
  item 5)*
- [x] ~~3.8 DONE 18 Sep~~ — **Pin-count/contact-size check, connector unplugged.** Confirm four rows of
  small pins plus two 2-pin corner blocks (near pins 1 and 5). **Check specifically
  whether the corner-block contacts (pins 1/2/5/6) are visibly larger/wider than the
  small-pin grid.** This is the photographic half of the 1.1 pin 01/02 question —
  larger contacts support "these are power," normal-sized contacts support "these
  are ordinary switch returns after all." *(memo 03 §4 item 6; spec §4 note)*
- [ ] **3.9 Boost P&T sensor body** — part number, if legible. Backs up 1.3's
  electrical answer with a datasheet-checkable part.
- [ ] **3.10 Injector body** — part number, if accessible without disturbing the
  fuel system. Corroborates the Bosch-family injector inference already used in
  memo 03/04.
- [ ] **3.11 Intake throttle — 6-pin connector and cable run (closes U8).** Photograph
  the connector, then follow the cable by hand through the loom.
  - **Terminates at the ECU's 94-pin connector →** in scope. Photograph which
    physical position on the ECU housing it plugs into (row/corner), so it can be
    matched to a pin number once U1 is resolved.
  - **Joins the XC11/XC1 panel loom instead** (same path as fuel level/WIF, per
    spec §2.3) **→** out of scope for this ECU; a throttle driver sheet is not needed.
- [ ] **3.12 Catalyst temperature sensor — 2-pin connector and harness run (closes
  U9).** Same method as 3.11: photograph, then trace.
  - **Terminates at ECU →** in scope, an EGT-style front-end is needed.
  - **Joins the panel/GCU loom →** out of scope, same treatment as fuel level/WIF.
- [ ] **3.13 KG640C terminal strip (J1–J8), photographed with terminal labels
  legible.** Reference material for the MPU-input question (U3) and future GCU
  interface work; not expected to close anything by itself this visit.
- [ ] **3.14 Wire-colour spot check at each analog sensor connector (boost, coolant,
  EGR, oil pressure, rail pressure) — flag toward U10.** SENT and CAN H share the
  same yellow colour code in this harness's legend *(pinout, "Wire colour classes")*,
  so this can't be resolved by colour alone. Photograph any **single yellow wire that
  is not paired with a green wire** (a CAN pair) and is not part of a 3-wire AC
  bundle — that's the SENT candidate. **This will likely only narrow it down, not
  close it outright** — say so in the notes rather than guessing a pin.

---

## Group 4 — Separate trip: CAN bus log (closes U4 in practice, not from a manual)

**Needs a USB-CAN adapter and a laptop.** Do this as its own visit unless you're
already bringing the hardware.

- [ ] **4.1** With the OEM ECU still fitted and the harness intact, tap CAN channel 1
  (pins **55**/**77**, H/L) and channel 2 (pins **87**/**86**, H/L) via breakout or
  fly leads. *(pinout, "CAN — two channels"; spec §4)*
- [ ] **4.2** Log traffic with the ignition on (ECU and GCU powered). Identify PGNs
  present, source addresses, and update rates.
  - Basic identification/status broadcasts should appear at key-on. **Engine-state
    PGNs (speed, load) may not appear, or may read zero/stale, until the engine is
    actually running** — if you need those, that's the "separate supervised
    activity" from the safety preamble, not a solo add-on to this trip.
- [ ] **4.3** Compare the captured PGN set against whatever the KG640C is found to
  expect (from the log itself, and cross-check against the KG640 manual if it
  surfaces). This is the practical closure the brief couldn't get from documents —
  **the log is the source, not a spec.** *(spec §8 U4)*

---

## Group 5 — Second visit, added 21 September 2026

**Why there is a Group 5.** Groups 1–4 were written from documents. These tasks come
out of **drawing the schematics**, which is a different kind of question: not "what is
this signal" but "where does this wire actually go, because the board cannot be built
without it." Two of them block the board outright.

Priority order is the order below. **5.1 is the blocker** — nothing about the board's
ground plane, its connector footprint or its power path can be finished without it.

- [ ] **5.1 — WHERE IS THE POWER GROUND? (blocks the board, no workaround)**
  Battery disconnected, connector **unmated**. Working on the **harness side** plug,
  probe every populated cavity for continuity to **chassis ground**. Write down every
  cavity number that beeps, and its resistance.

  *Why:* the ECU's 94-way connector has **no identified battery-negative pin.**
  `GP3.8703.C4.pdf` shows pin 21 as the battery **positive** feed and shows no negative
  anywhere — which is not a contradiction, because that document says outright it omits
  "power grounds, unused pins and internal-only pins." But it means the net that every
  circuit on the new board returns to, and that the injector low sides put **18 A**
  into, currently has nowhere to land. It cannot be guessed: a wrong ground pin is not
  a rework, it is a harness that has to be remade.

  **Do task 1.1 first if it has not been done** — pins 01/02 (`G_G_B AT1`/`AT2`) are
  the leading hypothesis and 1.1 tests them directly. 5.1 is the wider sweep that
  catches the answer if 1.1 comes back open.

  | What you find | What it means |
  |---|---|
  | **Two or more cavities at well under 1 Ω to chassis** | Those are the power grounds. Record every one — an 18 A injector stage does not return through a single contact, so expect more than one and record them all, not just the first. **This closes the blocker.** |
  | **Exactly one** | Record it, and say so explicitly in the notes. One 18 A return through one contact is a design constraint worth knowing about early, not a measurement error. |
  | **A few ohms, not near zero** | That is a return **through a device** (a sensor ground, a lamp, a coil), not a power ground. Note it separately — do not count it. |
  | **Nothing beeps anywhere** | The ECU is grounded through its **case/mounting**, not through the connector. Photograph the mounting points and any ground strap, and measure continuity from a mounting bolt to chassis. That answer changes the mechanical design, so it matters as much as the other outcomes. |

- [ ] **5.2 — Cavity census: which are populated, which are empty.**
  Same session as 5.1, connector unmated. Photograph the mating face square-on with
  good light, then list: which cavity numbers have a **wire crimped in**, which have a
  **contact but no wire**, and which are **empty**.

  *Why:* the wiring diagram accounts for 44 of 94 pins. The new design needs one more
  signal than the OEM harness carries — `TRIP_LOOP`, the supervised trip-module loop,
  which is not on the OEM diagram at all because it is new. **The question is not just
  "is there a spare pin" but "is there a spare WIRE":** an empty cavity means a
  contact and a conductor have to be added to a loom that is already on the machine.

  | What you find | What it means |
  |---|---|
  | **Spare cavities with wires already run** | Best case. Trace where one goes (same method as 3.11) — if it reaches the trip module or the panel, `TRIP_LOOP` has a home with no harness work. |
  | **Contacts fitted, no wires** | Adding a conductor is possible without re-terminating. Note the contact type so the crimp can be matched. |
  | **All 50 empty** | `TRIP_LOOP` needs a new contact **and** a new wire. Record the cavity you would use, so the board and the harness rework agree. |

- [ ] **5.3 — Connector contact geometry (for the board-side footprint).**
  **Now load-bearing (22 Sep 2026):** the owner decided the ECU carries this OEM
  connector directly, with no adapter harness, so the board's own header is the
  mating half of this plug.
  Connector unmated. Measure with calipers, and photograph with a scale in frame:
  **contact pitch** within a row, **row-to-row spacing**, and the **overall footprint**
  of the housing. If a contact can be seen down a cavity, photograph it.

  *Why:* the connector is identified — **Bosch `1 928 405 192` / `1 928 405 194`,
  code C** — but neither number returns a catalogue hit, so no land pattern can be
  downloaded. The board-side footprint has to come either from a Bosch distributor
  quoting those numbers, or from measurement. Measurement will not be precise enough
  to build from on its own; what it will do is **confirm which family drawing is the
  right one** when a distributor sends one.

  **Also re-photograph the `code C` marking and the `2.7` beside the logo.** Code C is
  mechanical keying — a differently-coded housing will not mate, and that is the kind
  of detail that is invisible until a part arrives and will not fit.

- [ ] **5.4 — Crank sensor output while cranking, COLD.**
  **SUPERVISED ACTIVITY, NOT A SOLO CHECKLIST ITEM** — the engine cranks, and a diesel
  with fuel available will start. Treat this like Group 4's running tests: someone
  qualified to operate the set, with the normal start procedure, not a meter held in
  one hand.

  Measure across ECU connector pins **52** and **74** (crank VR high/low) on the
  harness side, during the first seconds of cranking, engine cold.
  **Oscilloscope strongly preferred** — a multimeter on AC volts reads an RMS
  approximation of a non-sinusoidal waveform and will under-read the peak, which is
  the number that matters. If a meter is all there is, record that it was a meter.

  *Why:* the crank conditioner is a zero-cross comparator with a **±198 mV** hysteresis
  window, and a signal that never leaves that window cannot flip it at all, whatever
  its amplitude margin. The design was sized against a **2 V estimate** at cranking and
  the simulation says it still works down to about **0.25 V** — roughly a decade of
  headroom. That headroom has never been checked against this sensor.

  | Peak amplitude, cranking, cold | What it means |
  |---|---|
  | **Above 1 V** | Comfortable. Record the number and move on. |
  | **0.25 V to 1 V** | The design still works, with less margin than assumed. Record the number — it becomes the real design figure and replaces the estimate. |
  | **Below 0.25 V** | The hysteresis window has to shrink, which costs noise immunity, or the front end needs gain ahead of the comparator. **This is the outcome that changes a drawn sheet**, so flag it immediately rather than filing it. |

- [ ] **5.5 — Injector part number (was 3.10 — now load-bearing, not corroboration).**
  Same task, higher priority. Photograph the injector body markings.

  *Why it was upgraded:* the boost rail's **100 V target** and the **18 A peak
  threshold** come from a family-wide envelope in memo 04, not from this injector. The
  whole injector stage — the 47 µF reservoir, the 150 V part classes, the recirculation
  diodes — is sized off those two numbers. A part number turns an envelope into a
  datasheet. **Closes U5.**

- [ ] **5.6 — Alternator rectifier / regulator identification (closes U16).**
  Photograph the charging alternator's nameplate, and any separate rectifier or
  regulator module, with part numbers legible under raking light.

  *Why:* whether the alternator is **suppressed** decides which ISO 7637-2 load-dump
  pulse the input has to survive — the suppressed 5b case the design is currently
  built around, or the unsuppressed 5a case at 65–87 V. The input-protection topology
  and `load_dump`'s failure mode both hang off this. If no part number is readable, the
  alternative is a scope during a live disconnect under load, which is a supervised
  activity and a separate trip.

- [ ] **5.7 — Who commands the pre-heat / post-heat? (closes U14).**
  Trace the heater feed by hand, the same method as 3.11.

  *Why:* the DSE4522's fitted configuration enables pre-heat and post-heat at 50 °C,
  and this design has **no heater output at all**. It was already reported that the
  heaters are **battery-fed** — that answers who supplies them, not who **commands**
  them.

  | Where the command comes from | What it means |
  |---|---|
  | **The DSE4522 / panel** | Out of scope. Nothing is added to the board. |
  | **The ECU's 94-way connector** | **A driver channel has to be added** — which changes the board's area and its output count. Flag this one immediately: it is one of only two open items that can make the board bigger. |

### Still open from the earlier groups, and cheap

These were written for the first visit and have not been done. Two of them are a single
measurement each.

- [ ] **1.3** — one resistance reading across the boost P&T sensor, cold. **Closes U2**
  either way; there is no third case.
- [ ] **3.11** — follow the intake throttle's 6-pin cable by hand. **Closes U8**, and
  like 5.7 it is one of the two items that can make the board bigger.

---

## What this closes

| # | Unknown | Closed by |
|---|---|---|
| U1 | Connector family | 3.4, 3.5, 3.6, 3.7, 3.8 (photographic — narrows the ranked shortlist in memo 03, may not fully settle it without a logo hit) |
| U2 | Boost air-temp topology | 1.3 — closes outright |
| U4 | KG640C PGN set | Group 4 — practical answer via live log |
| U6 | Pin 09 function | 1.2, 2.3 |
| U7 | Pins 04/06 sense vs. load | 2.2 |
| U8 | Intake throttle on ECU? | 3.11 |
| U9 | Catalyst sensor routing | 3.12 |
| U10 | Which signal is SENT | 3.14 — narrows, may not fully close |
| U11 | Engine identity | 3.1 — closes outright if plate matches |
| U12 | Ignition relay: power-cut or signal-only | 2.1 — **the safety-gate item; closes §3's open question either way** |
| — | Pin 01/02 ground hypothesis | 1.1, 3.8 |
| U5 | Injector part number | 5.5 — turns memo 04's family envelope into a datasheet |
| U14 | Who commands the heaters | 5.7 — **can add a driver channel to the board** |
| U16 | Alternator suppressed or not | 5.6 — decides which load-dump pulse the input must survive |
| — | **The power ground's pin** | **5.1 — blocks the board outright** |
| — | A pin *and a wire* for `TRIP_LOOP` | 5.2 |
| — | Board-side connector footprint | 5.3 — confirms which family drawing is right |
| — | Crank VR amplitude at cranking | 5.4 — supervised; the only Group 5 item that can change a drawn sheet |

Ten register entries touched, two (U2, U11) closeable outright on the spot, one
(U12) resolves the live safety-argument branch either way, the rest narrowed with a
clear next step recorded regardless of outcome.

**Group 5 adds four more register entries and three questions that are not register
entries at all** — they are things the schematics need and no document in this project
contains. Of those, **5.1 is the one that stops the board**, and **5.7 and 3.11 are the
only two that can make the board bigger**, so they should be answered before layout
starts rather than after.
