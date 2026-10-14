# Field evidence, 14 October 2026: the old ECU's own measurements, engine running

**Source:** `refs/25kva.dat`, from the owner. Said to be from a **25 kVA set, engine on**.

**What it is:** not a CAN bus trace. It is an **ASAM MDF 3.0 measurement file** recorded with ETAS tools over **XCP**, the calibration link into the old Bosch ECU. It holds the ECU's *internal* variables, the numbers its own software computes.

| Recording detail | Value |
|---|---|
| Date and time | 23 Sep 2026, 15:06:44 |
| Length | 35 min 38 s |
| Variables | 230 |
| Sample rates | three: every 10 ms, every 100 ms, and once per cylinder segment |

**Kept out of git.** The raw file is calibration data from Bosch/KOEL. It matches `*.dat` in `.gitignore`, so it stays on this machine only. This summary is what the repo keeps.

**How it was read:** `asammdf` 8.1.2 in `.venv`. Every number below comes from the file. Where a number is an interpretation, the text says so.

---

## 1. Is it our engine?

| Check | Recording | Ours |
|---|---|---|
| Cylinders (`Epm_numCyl`) | **3** | 3 |
| Speed while running (`Epm_nEng`) | 1499.5–1504 rpm (5th–95th percentile), median 1500.5 | 1500 |
| Battery (`BattU_u`) | 14.52–14.62 V while running | **12 V system** (spec §1). This also corrects two places today's PCB work called it "24 V" |
| Stored faults (`DFES_numDFC_[0..14]`) | **none**: every slot reads `DFC_Unused` | — |
| Calibration overrides during the run | **none**: the rail-pressure and quantity override switches stay 0 | — |

**Conclusion:** a 3-cylinder engine at 1500 rpm with a 12 V system and no faults. This is consistent with our set. It doesn't settle **U17** (which machine the 13 Oct identity strings came from), and it doesn't touch **U4** (the J1939 messages to the DSE), because this is not a bus trace.

## 2. Load during the run

| Quantity | Range (minute averages) |
|---|---|
| Fuel per injection (`InjCtl_qSetUnBal`) | 6.7–17.0 mg |
| Inner torque (`ActMod_trqInr`) | 36–84 Nm |

So the run is at **light to part load**, and there is **no full-load data**. Our `FUEL_RATED_MG` (34 mg) is still unverified.

**Two load changes** are in it:

| Event | Fuel | Speed | Back to 1500 |
|---|---|---|---|
| Load on (t = 1259 s) | 20 → 25 mg steady, 44 mg for 0.5 s | **dip to 1352.5 rpm (−9.8 %)** | in about 1 s |
| Load off (t = 1234 s) | 29.7 → 13.9 mg | **rise to 1593 rpm (+6.2 %)** | in about 1 s |

**What it means:**
- The OEM governor itself dips 9.8 % on this step, right at **G2's 10 % limit**. Our simulated governor showed 3.4 % on a full-load step, so **our engine model is probably optimistic** about how hard the engine can pull.
- Commissioning has to measure our dip on the real engine, not trust the simulation.

## 3. Findings that contradict firmware assumptions

### 3a. The metering valve is normally open (strong evidence)

`MeUn_iSet` is the metering-valve current setpoint. Paired with rail pressure (`RailP_pFlt`):

| Rail pressure | Fuel | Valve current |
|---|---|---|
| 827 bar | 6.7 mg | 1482 mA |
| 915 bar | 10.5 mg | 1466 mA |
| 994 bar | 11.7 mg | 1455 mA |
| 1057 bar | 17.0 mg | **1441 mA** |
| stopping | — | rises to **1684 mA**, then 200 mA once stopped |

**More flow needs *less* current, and stopping the engine needs *more*.** That is how a **normally-open** valve behaves: no current means full flow, and current closes it. It matches Bosch's usual inlet metering valve.

**Our firmware assumes the opposite**: `METER_NC 1` in `rail.h`.

**Consequences, if our ECU drives this valve:**
1. The rail-pressure loop runs backwards. More duty would mean less flow.
2. Our "safe" state, `METER_CLOSED` (duty 0), would be **full flow, not zero**.
3. With a normally-open valve, losing drive (or a trip that cuts the drive) means full delivery. Pressure is then limited only by the relief valve, and the engine is stopped only by the injectors not firing. The memory note `metering-valve-polarity-open` already says: **if it is normally open, the trip module's contacts have to move.**

**Still needed to make it certain:** the part number on the valve (inspection brief, item 7). Until then, it is strong evidence, not proof.

### 3b. Injection timing: about 12–15° before TDC, not 5°

`InjCrv_phiMI1Des` (start of the main injection, degrees of crank; read here as before TDC, which is Bosch's usual sign) runs from **11.5° at 6.7 mg to 13.7–14.9° at 15–17 mg**. There is no pilot injection in this mode (`InjVlv_tiPiI1ET` = 0).

Our firmware: `INJ_SOI_BTDC 5.0`, fixed.

### 3c. Rail pressure follows load: 830 to 1060 bar

| Fuel (mg) | 6.7 | 8.0 | 9.8 | 11.7 | 15.2 | 17.0 |
|---|---|---|---|---|---|---|
| Setpoint (bar) | 827 | 848 | 914 | 994 | 1039 | 1057 |

The actual pressure tracks the setpoint to within ±4 bar (5th–95th percentile of `Rail_pDvt`).

Our firmware: `RAIL_SET_BAR 1000`, fixed (a placeholder).

### 3d. The injector: 330 µs dead time, flow constant about 0.0020

Main-injection energising time (`InjVlv_tiMI1ET`) against fuel and rail pressure fits our firmware's own law almost exactly:

    t = dead + q / (K · √p)

with **dead ≈ 330 µs and K ≈ 0.00199 mg/µs/√bar**. Three checks:

| Fuel | Pressure | Measured | Predicted |
|---|---|---|---|
| 11.4 mg | 941 bar | 513.5 µs | 517 µs |
| 15.2 mg | 1039 bar | 567.1 µs | 567.5 µs |
| 11.7 mg | 994 bar | 516 µs | 516.8 µs |

Our firmware: `INJ_DEAD_US 300` and `INJ_K 0.0009`. So for a given fuel mass, **our injectors would stay open about twice as long as needed**. The speed loop would hide this by asking for "less fuel", but the fuel limits, the droop reference (`FUEL_RATED_MG`) and the cranking fuel (`FUEL_START_MG`) would all be off by about 2×.

### 3e. The governor is isochronous: no droop

Speed sits at 1500.2–1501.9 rpm (minute averages) from 6.7 to 17 mg of fuel. There is **no droop**. The governor's high setpoint (`EISGov_nSetPHi`) is a separate limit.

Our firmware: `GOV_DROOP 0.04`, "assumed: droop switch closed". The droop switch input (pin 23, `SW_DROOP`) exists, but the firmware ignores it.

## 4. Sensors

| Signal | Recording | Meaning |
|---|---|---|
| Intake air temperature, raw (`IntkAirT_uRawTIntkVUs`) | **0 mV throughout**; the ECU uses a fixed 54.96 °C | **No sensor on that input** (or it isn't wired). Bears on **U2**: the old ECU runs without boost-air temperature |
| Fuel temperature (`FuelT_t`) | fixed 89.96 °C | Substitute value: no fuel temperature sensor |
| Boost pressure (`Air_pIntkVUs`) | 0.97–1.45 bar absolute | Within our 50–400 kPa placeholder |
| Ambient pressure (`EnvP_p`) | 935–939 hPa | About 650 m altitude (inference) |
| Oil pressure (`Oil_pAna`) | 4.1–5.4 bar (5th–95th percentile) | Gauge or absolute is not stated |
| Coolant (`CEngDsT_t`) | 65–70 °C | Ran cool. Light load |
| EGR valve position (`EGRVlv_rAct`) | 0–54 % | **EGR is active** at 1500 rpm part load |
| Accelerator (`APP_r`) | 100 % fixed | Genset: the governor sets the speed, not a pedal |

## 5. What changes, and what doesn't

**Recorded:**
- 12 V system confirmed. The "24 V" wording in today's PCB work is corrected.
- No faults.
- Light/part-load data only.

**Proposed firmware calibration changes** (awaiting the owner's go-ahead):

| Item | Today | From this recording |
|---|---|---|
| `METER_NC` | 1 (normally closed) | **0, normally open**, once the valve's part number confirms it. This is a **safety change**: the safe state and the trip-module wiring both flip |
| `INJ_SOI_BTDC` | 5° fixed | a table: about 11.5° at 7 mg to 14° at 17 mg |
| `RAIL_SET_BAR` | 1000 fixed | a table: 827 bar at 7 mg to 1057 bar at 17 mg |
| `INJ_DEAD_US` and `INJ_K` | 300 µs and 0.0009 | 330 µs and 0.0020 |
| `GOV_DROOP` | 4 % always | **0 (isochronous)** unless the droop switch is closed |

**Not settled:**
- **U4**: needs a bus trace on the DSE CAN.
- Full-load fuel.
- The valve's part number.
