# Field evidence, 13 October 2026

**Source:** Jeevan (a friend at the machine). Sent as a chat message, 5 photos, a PCAN-View CAN trace and a Bosch sensor catalogue.

**What this file holds:** what each item shows, and what it does and doesn't settle. It updates `field-evidence-2026-09-18.md`, which already recorded the DSE4522 configuration (`GP3.314.01.0.PR-DSE4522-config.pdf`). That PDF was sent again this time, and nothing in it is new.

---

## 1. Engine data, as stated (chat, 13 Oct 2026, 21:06–21:10)

| Item | Value | Effect on the design |
|---|---|---|
| Engine model | `3GK550ETA4SR1` | Matches the rating plate already on record (`3GK550ETA 4SR1`) |
| **Firing order** | **1-2-3** | **Confirms** the firmware's assumption (`CRANK_TDC1_DEG` + 240° steps). No change |
| Compression ratio | 18 ± 1 : 1 | Engine model only (cranking compression torque) |
| Layout | inline | Consistent with 3 cylinders at 240° |
| Generator | 3-phase, 415 V, full-load current 34.8 A, 40 A 3-pole breaker | 34.8 A × 415 V × √3 = **25.0 kVA**. Matches the 25 kVA / 20 kW basis |
| **Governor class** | **ISO 8528-5 G2** | Becomes a requirement. See §5 |
| Injector part number | `4H.508.70.0.PR.REV-1` (Kirloskar number) | U5 partly answered. The Bosch number (0 445 …) on the injector body is still needed for flow data and dead time |

## 2. The old ECU (photos 1–4: `old-ecu-2026-10-13-1..4.jpg`)

| Read from the label | Value |
|---|---|
| Bosch part number | **0 281 021 133** (0 281 is Bosch's diesel ECU range) |
| Bosch ECU type | **MD1CS162**, from the MD1 family |
| Kirloskar part number | **T4.435.01.0** |
| Other | `4740823284 0148 7923 25-02-03`, `Made in India`; casting mark `1/25-2/2` |

**Housing:** die-cast aluminium. It has cooling fins on the back face, four corner mounting lugs plus side lugs, and a round vent plug. That matches the "old housing" plan in the PCB spec. The housing is the heat sink, so where the board touches it matters.

**The connector face (photo 4)** settles the J1001 pin arrangement:

| Group | Pins | Arrangement |
|---|---|---|
| Large power contacts | **1–6** | Six large blades in two staggered rows of three, at one end of the shroud |
| Signal contacts | 7–28, 29–50, 51–72, 73–94 | **Four rows of 22**: two rows on each side of a central polarising rib |

The total is 6 + 88 = **94**, which confirms the 94-way single connector. The earlier reading from the wiring-diagram drawing ("PIN NO.1" and "PIN NO.5" corner clusters, memo 03) found only 4 large pins. **The photo shows 6.** The J1001 placeholder footprint in the PCB plan is corrected to match.

**Not in the photos:** pitch, row spacing, the board outline, or the header's position. Those still need calipers (inspection brief, Group 6). This unit appears to be **off the engine**, so measuring it may be possible without stopping the genset. To confirm with Jeevan.

## 3. A second ECU (photo 5: `old-ecu-2026-10-13-5.jpg`)

The photo shows a pressed-steel cover with a label `0406773189` and a hand-written `T4.8941`. A different housing and part number from §2. **What engine it belongs to is not stated.** It is recorded here and not used until it is identified.

## 4. CAN trace, engine off (PCAN-View, start time 01-10-2026 16:02:33)

**What it contains:** 362 frames, **all 11-bit**. A diagnostic tester on ID `0x7E0` sends UDS *ReadDataByIdentifier* (0x22) requests, and the ECU replies on `0x7E8`, with multi-frame replies using ISO-TP. There are **no 29-bit J1939 frames at all**: no EEC1, no DM1, nothing to or from the DSE.

**Identifiers the ECU reported:**

| DID | Meaning (UDS) | Value |
|---|---|---|
| F190 | Vehicle / set identification | **`KOEL_TC_82.5KVA`** |
| F182 | Application data identification | **`4R1190ETA4G1`** |
| F181 / F195 | Software identification | **`P2229_4R65V14T`** |
| 1072 | (manufacturer) | `200001` |

Many other DIDs return two-byte values. Several of them sit around 0x0BF0–0x0C02, which is 305–307 in units of 0.1 K, or about 32–34 °C. That's what you'd expect for temperature readings from a cold engine on an October afternoon, but **this is an inference, not a decode**.

**What this does settle:**
- The old ECU's **diagnostic interface**: UDS on CAN, request `0x7E0`, response `0x7E8`. That's a useful model for our own service tool.

**What it does not settle, and what it raises:**
1. **U4 (the J1939 messages the DSE expects) is still open.** The trace has no J1939 traffic. It was either taken on the diagnostic CAN rather than the DSE CAN, or with nothing else on the bus.
2. **The ECU identifies itself as an 82.5 kVA, `4R1190ETA4G1` (4-cylinder) set.** Our genset is a **25 kVA, 3-cylinder `3GK550ETA4SR1`**. Either this trace came from a different genset, or the ECU carries a generic data set. **Which machine was this trace taken on?** Until that's answered, nothing in this trace is used as a fact about our engine.

**Still needed for U4:** a trace with the **engine running and the DSE connected**, on the CAN pair that goes to the DSE, capturing 29-bit frames (J1939 normally runs at 250 kbit/s). One minute is enough.

## 5. ISO 8528-5 class G2, and what it means for us

G2 sets the transient limits for a step of rated load:

| G2 requirement | Firmware today (simulation) | Status |
|---|---|---|
| Speed dip on full-load acceptance ≤ 10 % | 3.4 % (1449 rpm) | meets |
| Speed rise on full-load rejection ≤ 12 % | 3.1 % (1547 rpm) | meets |
| Recovery inside the band ≤ 5 s | < 5 s | meets |
| Steady-state speed band ≤ 1.5 % | ±0.2 % | meets |
| Droop ≤ 5 % | 4 % (3.8 % in simulation) | meets |

**One interaction to know about:** G2 allows a rejection overshoot of up to **+12 % (1680 rpm)**, but our own overspeed trip is at **+10 % (1650 rpm)**. Our governor keeps the peak at +3 %, so the two never meet in simulation. But **the governor tuning on the real engine has to keep the rejection peak below 1650 rpm, not merely within G2.** That's a calibration acceptance criterion: overspeed protection wins over G2's allowance.

## 6. Bosch sensor catalogue (generic, not the engine's own list)

The catalogue covers Bosch's sensor ranges in general. It doesn't say which sensors are fitted to this engine. Where it bears on the firmware's placeholder sensor tables:

| Firmware placeholder | Closest Bosch range in the catalogue | Fit |
|---|---|---|
| Rail 0.5–4.5 V = 0–1800 bar | DS-RPS4-2, 1800 bar, ratiometric 10–90 % | Same law |
| Boost 0.5–4.5 V = 50–400 kPa | DS-S3-TF / DS-S2-TF (T-MAP) 50–400 kPa, with a built-in NTC | Same law. This also means **boost air temperature (U2) is likely the NTC inside a T-MAP sensor** |
| Coolant NTC 2.5 kΩ @ 20 °C, β 3450 | TF-W: 2.35–2.65 kΩ @ 20 °C, 0.31–0.33 kΩ @ 80 °C, 8.6–10.1 kΩ @ −10 °C | Close. A β of 3500 would land inside every Bosch tolerance band (3450 reads 0.34 kΩ at 80 °C, just above the band) |
| Oil 0.5–4.5 V = 0–1000 kPa | DS-O-TF / DS-AM5: 50–600 kPa absolute | **Different.** Re-scale once the fitted part is known |
| Crank: VR input | DG-6 inductive sensor, "for 60-2 type wheel" | Consistent with the 60-2 assumption, but not proof |

**What's still needed:** the part number on each sensor fitted to the engine (inspection brief item 7). The catalogue then gives its exact curve.

## 7. What changes, and what doesn't

Recorded and applied:
- Firing order 1-2-3: an assumption becomes a **fact**.
- Governor class G2: becomes a **requirement**, with the overspeed interaction in §5.
- J1001 pin arrangement: 6 large plus 4 × 22. The **PCB plan's placeholder is corrected**.

Raised, not yet decided:
- **The ECU and the trace may belong to an 82.5 kVA set** (§4). Which machine? Logged as **U17**.
- **The second ECU** (§3): which engine is it from?
- **U4** still needs a running-engine trace on the DSE CAN.
- **The DSE shuts down only on the "ECU Protect" lamp.** The September record (`field-evidence-2026-09-18.md`) shows the DSE treating DM1 red stop as a *warning* and **ECU Protect as a shutdown**. Our firmware sets the red lamp on its shutdown faults but never the Protect lamp. So when our ECU stops the engine for overspeed, the DSE would see the speed fall and shut down on *under-speed* (1310 rpm), logging the wrong reason. **Fixed on 14 October** (owner's go-ahead): shutdown faults now set the Protect lamp as well as red. Decisions log §12, addendum.
