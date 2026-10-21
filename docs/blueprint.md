# Smell Monitor — Blueprint, Build & User Specification

| | |
|---|---|
| **Document** | OS-BP-001 |
| **Revision** | L |
| **Date** | 2026-10-18 |
| **Status** | Architecture locked (socket fixed by `docs/module-standard.md`, blueprint §4.9); schematic ERC-clean, PCB routed and DRC-clean, firmware compiling; revision L is the board re-derive |
| **License** | Hardware: CERN-OHL-S-2.0 · Firmware: MIT |
| **Maintainer** | OpenSmell |


**Standards applied:** ASME Y14.100 (drawing practices) · ASME Y14.24 (types of
drawings) · ASME Y14.5 (dimensioning & tolerancing) · ISO 128 (lines) ·
ISO 5457 (sheet sizes) · ISO 2768 (general tolerances) · CERN-OHL-S / DIN SPEC
3105 (open-hardware documentation).

**How to read this document.** Every requirement traces upward to a success
criterion in §0.4 and downward to a design value and a verification test. A
number that traces to nothing does not belong here. §15 records why the
hard-to-vary choices are what they are, and which claims are proven, calculated
or untested. The module interface is `docs/module-standard.md`.

### Contents
0. Objective & Success Criteria · 1. System Overview · 2. Operating Principle ·
3. Pneumatic Design · 4. Sensing Interface · 5. Electrical Design ·
6. Mechanical Design · 7. Firmware Requirements · 8. Verification & Validation ·
9. Bill of Materials · 10. Assembly & Bring-up · 11. User Manual ·
12. Drawing Set · 13. Risks & Future · 14. Revision History ·
15. Design Decision Record

---

## 0. Objective & Success Criteria

### 0.1 What this is

An **open-hardware sensing platform** that presents a **controlled, repeatable
sample** (headspace) to a **user-selectable set of heterogeneous gas/odor
sensors** — MOX, NDIR, electrochemical, polymer, piezo, QCM — and emits a
**time-series sensory vector plus an open dataset**, so anyone can train
classifiers, swap components, and build vertical applications on top.

The hardware's entire job is to **remove confounders** (flow, temperature,
humidity, carryover, timing) so that cheap, cross-sensitive, drift-prone
sensors produce data that is *comparable and reproducible*. Sensing is
commodity; **reproducibility is the product.**

### 0.2 Why it exists — positioning

| Tier | Examples | Sampling | Sensing principles | Tooling | Cost |
|------|----------|----------|--------------------|---------|------|
| Cheap dev tier | Bosch BME688 + AI-Studio, Sensirion SGP4x/SEN6x, Renesas ZMOD | ambient air | one (MOX) | closed | $20–100 |
| Lab instruments | Alpha MOS, Sensigent, Aryballe, zNose | controlled | several | closed | $10k–100k |
| DIY | scattered projects | none | mixed | none | low |
| **This platform** | — | **controlled headspace** | **heterogeneous, swappable** | **open** | **low** |

**Gap filled:** controlled sampling **and** mixed technology **and** open. The
one-line differentiator used verbatim in all external material:

> *Controlled headspace, multiple sensing principles, open reproducible data,
> swappable modules.*

### 0.3 Users

Makers/students (learn olfaction, build a first e-nose) · researchers
(repeatable sample presentation for comparative studies) · product developers
(de-risk a sensing use case) · integrators (consume the open dataset/API).

### 0.4 Success criteria (LOCKED)

The platform is judged on **repeatability**. All targets are measured against a
**sealed reference vial** (fixed ethanol-in-water ratio, fixed temperature).

| ID | Metric | Definition | Test method | Target |
|----|--------|-----------|-------------|--------|
| **P1** | Repeatability (primary) | CV of a sensor's response to N identical samples | N=5 repeats, same session | **CV ≤ 5%** intra-session; ≤ 10% day-to-day |
| **G1** | Carryover | blank-after-sample ÷ sample response | alternate reference ↔ blank | **≤ 5%** |
| **G2** | Cycle time | intake + hold + purge | timed | **≤ 60 s** |
| **G3** | Environment control | chamber temperature stability; RH measured & reported | logged thermistor / SHT31 | **±0.5 °C**; RH reported ±3% |
| **U1** | Interchangeability | any breakout module in any slot of its bank, tool-free | swap test | **≤ 60 s, no tools** |
| **V1** | Proof-of-value | discrimination on one reference vertical | 3-class classifier (coffee/air/blank) | **≥ 90%**, ≫ chance |

**Coupled trade-offs:** repeatability ↑ with longer purge → cycle time ↑; carryover
↓ with longer purge / higher flow → cycle time ↑, ΔP ↑; environment stability ↑
with more thermal mass → mass, cost, volume ↑. MOX desorption time constants
(minutes) set a **hard floor under cycle time** — the chemistry cannot be beaten
by hardware, so P1 and G2 are traded, not both maximized.

### 0.5 What this is NOT

Not an ambient air-quality monitor · not a calibrated single-analyte instrument ·
not a substitute for lab GC/MS.

### 0.6 Design objectives (priority order)

| # | Objective | Target |
|---|-----------|--------|
| O1 | Cost (BOM) | ≤ $60 at qty 10 (base electronics) |
| O2 | Modularity | 8 identical slots, each carrying a 5 V gas-cell socket and a 3.3 V Qwiic port (§4.9); sensors are plug-in breakouts, sensor-agnostic |
| O3 | Repeatability | §0.4 P1/G1 |
| O4 | Buildability | Standard tools; no custom parts beyond the printed shell + insert |
| O5 | Power | USB-C 5 V/3 A source (≥ 1.5 A needed); idle < 1 W, ≈ 5 W loaded (MOX heaters dominate); §5.8 |
| O6 | Reliability | Sensor swap without tools; chamber cleanable |

### 0.7 Non-goals

No on-device classification (firmware acquires + streams; classification is
upstream) · no battery (USB-C only) · no sample concentration (direct headspace
via active flow) · no certified ppm output (qualitative/relative instrument).

---

## 1. System Overview

Three-phase, fan-driven, active sampling. A 40 mm axial fan pulls sample air
through 3×Ø6 nostrils, through a replaceable filter, across the two module rows
of interchangeable sensors, and out the rear.

```mermaid
flowchart LR
    S[Sample / headspace] --> N["3x Ø6 bellmouth nostrils"]
    N --> F[PTFE filter pack]
    F --> C["Sensing chamber<br/>106 x 100 x 48 mm"]
    C --> B["Two module rows<br/>8 identical sockets"]
    B --> X["40 mm PWM fan (rear)"]
    X --> E[Exhaust]
    ENV["SHT31 (T/RH)<br/>upstream of sensors"] -.-> C
    B --> M["ESP32 + ADS1115 + TCA9548A"]
    ENV --> M
    M --> U["USB-C to host (Osmograph)"]
```

**Signal path.** Any slot → its fixed 2:1 divider → ADS1115 (16-bit) when an
analog cell is fitted, or its own TCA9548A channel → ESP32 I²C when an I²C module
is fitted · SHT31 + OLED on the master bus · USB-C carries power and serial data
to the host. §4.9 defines the uniform slot; the board in the tree is still the
4 analog + 4 digital as-built revision that preceded it.

**Flow discipline (non-negotiable):** single pass front→rear; no internal
baffles except the sensor screen; no sharp internal corners (R ≥ 3 mm); sensors
sit in a low-convective zone, out of the high-velocity core, so fan speed has
minimal effect on their operating temperature (the dominant MOX error source).

---

## 2. Operating Principle — Three-Phase Cycle

The device never passively sniffs. Exposure is driven by a deterministic cycle
so every measurement sees the same pneumatic history; passive detection injects
uncontrolled ambient variability that corrupts comparison between samples.

| Phase | Fan | Duration | Purpose |
|-------|-----|----------|---------|
| **Intake** | ON (PWM ~50%) | 10 s | Draw sample through filter into chamber |
| **Hold** | OFF | 10 s | Sensors equilibrate; **acquisition happens here** |
| **Purge** | ON (PWM ~100%) | 20 s | Flush chamber with clean air, reset baseline |

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> INTAKE: button / host cmd
    INTAKE --> HOLD: fan ON 10 s
    HOLD --> PURGE: fan OFF 10 s (acquire)
    PURGE --> IDLE: fan ON 20 s, report to host
```

Timings are firmware parameters and may be tuned per sensor pack; the
three-phase structure is fixed. Full cycle ≈ 40 s (meets **G2 ≤ 60 s**).

---

## 3. Pneumatic Design

> **Geometry note.** The element-loss table below was derived for the earlier
> closed-lane chamber (106 × 11 mm lane, eight wells, plate). The chamber is now
> the open tray of §6.1 (116 × 108 × 40, no lane, no wells), so the *distribution*
> of those losses has changed while the sizing conclusions have not: the filter
> and fan are still sized by the same flow and the same total ΔP, and the open
> chamber has strictly less restriction than the lane it replaces. NF1 (filter
> ΔP bench) and the CFD pass in §8.3 are what confirm the current numbers; treat
> the per-element split below as the derivation, not as a prediction for the new
> part.

Method: hand-calculation system model (pipe-flow / orifice / duct theory) against
datasheet-anchored fan and media figures, plus a validation plan. CFD is not
required to lock v1 (§8.3).

### 3.1 Requirements

| # | Requirement | Value | Reason |
|---|-------------|-------|--------|
| R1 | Purge completeness | ≥ 99% cavity exchange in 20 s | §8.2 acceptance |
| R2 | Sample throughput | Fresh-air flush of the whole ~0.51 L cavity | MOX baseline reset |
| R3 | Nose velocity (BME688-class) | ≥ 0.1 × Bosch guidance; slower accepted & logged | Bosch BME688 note |
| R4 | Fan static head | ≥ 3× system ΔP at operating point | fouling/age margin |
| R5 | Noise | ≤ 30 dBA @ 1 m (intent ≤ 20 dBA) | UX |
| R6 | Filter | hydrophobic, particulate barrier, ≤ 2 Pa clean | sample-memory-free path |

### 3.2 Design operating point

Q_design = **15 L/min** = 2.5×10⁻⁴ m³/s. Cavity V ≈ 0.51 L ⇒ time constant
τ = V/Q = **2.0 s**. After 20 s purge, residual = e^(−10) ≈ **0.005 %** ⇒ R1
met with ~10 theoretical exchanges.

### 3.3 Governing equations

```
ΔP_i     = K_i · ½·ρ·v_i²          (form / orifice)
ΔP_c     = f · (L/Dh) · ½·ρ·v²     (duct friction)
ΔP_media = R_media · Q / A         (porous media, laminar Darcy)
```
ρ = 1.2 kg/m³, μ = 1.81×10⁻⁵ Pa·s, ν = 1.5×10⁻⁵ m²/s. Continuity Q = v·A.

### 3.4 Element losses @ 15 L/min

| Element | ΔP |
|---|---|
| 3×Ø6 bellmouth nostrils (Re ≈ 1180 laminar, K ≈ 0.04) | 0.21 Pa (2.6 Pa if sharp — bellmouth mandatory) |
| Inlet plenum expansion (85 → 1680 mm²) | ~0.01 Pa |
| Filter pack (hydrophobic PTFE + prefilter, pleated, ~100 cm²) | 1.5 Pa clean / ≤ 3 fouled |
| Chamber duct (106 × 11 mm lane, Re ≈ 160) | 0.03 Pa |
| Sensor wells (open-bottom, τ_well ≈ 1.2 s) | ~0.02 Pa |
| Fan inlet + exhaust grille | ~0.10 Pa |
| **System total** | **≈ 1.9 Pa** (design ≤ 5 Pa, hard limit 10 Pa) |

Losses are friction/orifice-dominated ⇒ ΔP(Q) = K_sys·Q², K_sys ≈ 1.9 Pa @ 15 L/min.

### 3.5 Fan selection & operating point

40×40×10 mm 5 V axial, Sunon Super-Silence 4010-class anchor: free air
150–230 L/min, P_stall ≈ 17 Pa, 4500–5000 RPM, ~15 dBA. Design point 15 L/min
sits ≤ 10% of Q_max; at ~1.9–5 Pa the fan delivers **35–60 L/min at 20–30%
PWM**. Full-speed purge Q ≈ 100–150 L/min ⇒ cavity τ ≈ 0.4–0.7 s ⇒ 99%+ flush
in **< 3 s**; the 20 s window is then dominated by MOX desorption, not flush.
A pump (0.1–5 bar) overshoots pressure and defeats the low-noise/low-power goal.

### 3.6 Filter specification — the decision the physics forces

A 0.45 µm PTFE membrane needs ~0.16–0.2 m² of media to stay ≤ 5 Pa at this flow
— physically incompatible with a < 10 Pa axial fan in a 122×114 box. Locked spec:

| Property | Spec |
|---|---|
| Position | **series element**: spans the full 106 × 11 mm lane cross-section immediately behind the nostrils, so no stream can bypass it |
| Form | pleated pack (a flat 106 × 11 face is only 11.7 cm² — the media must be folded to reach the area below) |
| Hydrophobic PTFE mesh / coating | WEP ≥ 350 mbar |
| Particle-cut pre-filter | 5–20 µm nominal |
| Effective area | ≥ 70 cm² clean, target 100 cm² |
| ΔP budget | ≤ 2 Pa clean; ≤ 5 Pa fouled |
| Swappable | tool-free, 90-day interval |

The filter stops liquid water/droplets and coarse PM; it is **not** a sterile
membrane and does **not** remove water vapor (humidity compensation is via SHT31
downstream).

### 3.7 Noise budget

Fan @ ~25% ≈ 10–14 dBA · @ full ≈ 16–20 dBA · bellmouth inlet whistle ≤ 2 dBA ·
**total design intent ≤ 20 dBA** (R5).

### 3.8 Verification

| # | Test | Pass |
|---|------|------|
| NF1 | Filter ΔP vs Q (manometer) | ≤ 3 Pa @ 15 L/min |
| NF2 | Smoke ribbon, each phase | uniform front→rear; no vortex in wells |
| NF3 | Sound @ 1 m purge duty | ≤ 30 dBA |
| NF4 | Purge completeness (odor then cycle) | all sensors ≥ 95% baseline |
| NF5 | Well washout vs mainstream | τ_well ≈ mainstream ± 50% |
| NF6 (opt) | 2D steady `simpleFoam` | no recirc zone > 5% upstream of any sensor |

---

## 4. Sensing Interface — The Contract

> **§4.1–§4.7 describe the as-built revision; §4.9 supersedes the socket.**
> The as-built board has two different slot types (4 analog + 4 digital), 5- and
> 6-pin, with modules standing perpendicular to the board and one ADC.
> **[§4.9](#49-the-module-standard-osm-1--the-decision-that-closes-45) and
> `docs/module-standard.md` replace that with one uniform slot design repeated
> eight times — a keyed 5 V gas-cell socket plus a Qwiic port at every slot — and
> flat-mounted cartridges.** Revision L is the board that implements it. If you
> are designing a module, read the standard first; the mechanical derivation of
> the envelope stays in §4.5/§4.6.

The platform defines **two kinds of slot**; it does **not** define sensor
chemistry. Sensors are ordinary plug-in breakout modules; anything matching a
contract drops in. A clean, repeatable, instrumented electrical + pneumatic
environment is ours; chemistry choice is the user's.

The board has **8 slots in two rows — 4 analog + 4 digital**:

Plan view. X = width (the rows), Y = depth; the sample flows front → rear:

```
   front wall: 3 x D6 nostrils ....................... sample in
        |
        v            <---- flow, cavity depth 100 mm ---->
   J6/D1  J7/D2  J8/D3  J9/D4    DIGITAL row  (3.3 V, I2C)   upstream
   J2/A1  J3/A2  J4/A3  J5/A4    ANALOG  row  (5 V,  AO/DO)  downstream
        |
        v
   rear wall: taper duct -> D40 fan .................. exhaust
```

One PCB, 114 × 105 mm, seated as the chamber **floor** (its top face is the
cavity floor, see §6.2). All 8 sockets face up and every breakout module stands
**perpendicular** to the board, its plane parallel to the flow, so one module
never shadows the row behind it and the connector line of every slot runs along
the flow axis.

**Why digital is upstream.** The analog bank is where the 5 V parts live, and
those are the ones that disturb the gas: four MOX heaters ≈ 3.6 W into ~2.5×10⁻⁴
m³/s is a ≳ 10 K local rise, MOX *consumes* reducing gas (it is a net sink), and
it desorbs during purge. Putting that row last means nothing is downstream of it,
the small cold digital breakouts present the least blockage to the wide analog
cards behind them, and purge carries the analog row's own desorbed VOC straight
out of the exhaust.

Two rows, because the two kinds of sensor need different electricity:

- **Analog row (4):** 5 V for heaters and analog-output cells (MOX,
  electrochemical), read through the ADS1115 ADC. These are the wide parts
  (≈ 22 mm) and the ones that carry the chemically distinct (orthogonal)
  information.
- **Digital row (4):** 3.3 V I²C for smart chips (digital NDIR, VOC-index,
  humidity). Small parts (≈ 18 mm), each on its own mux channel, so I²C
  addresses can never collide.

4 + 4 is where the 106 mm chamber lands at the wide-row pitch (§4.6), and it
covers every real application (§4.7).

### 4.1 Analog bank — J2..J5 (4 × 1×5 header)

| Pin | Name | Rail | Notes |
|-----|------|------|-------|
| 1 | `+5V` | 5 V | Module logic + MOX heater (150 mA/slot budget, ≈0.9 W worst case) |
| 2 | `GND` | GND | |
| 3 | `AO` | — | Analog out → fixed 2:1 divider → ADS1115 (2.5 V full scale) |
| 4 | `DO` | — | Digital out → ESP32 GPIO (input, pull-down) |
| 5 | `3V3` | 3.3 V | For 3.3 V-native analog modules |

Order is `5V GND AO DO 3V3` (frozen in `electrical/interface.py`), not
`5V 3V3 GND AO DO`: a naive 4-pin MQ-type module (VCC, GND, AO, DO) then seats on
pins 1–4 with power and ground adjacent, instead of landing its GND on 3V3.

The 2:1 divider is fixed and always present; a 0–5 V swing cannot exceed the ADC
range. A 3.3 V-output sensor reads at 66% of full scale — thousands of counts.
`DO` supports frequency-output sensors (piezo, QCM) by pulse counting.

### 4.2 Digital bank — J6..J9 (4 × 1×6 header)

| Pin | Name | Rail | Notes |
|-----|------|------|-------|
| 1 | `3V3` | 3.3 V | Logic + sensor VDD |
| 2 | `GND` | GND | |
| 3 | `SDA` | I²C | Through TCA9548A channel (segmented bus) |
| 4 | `SCL` | I²C | same |
| 5 | `INT` | — | Interrupt / spare GPIO |
| 6 | `CTRL` | — | Enable / spare GPIO |

Each digital slot owns a dedicated TCA9548A channel ⇒ **no I²C address
collisions ever**. Both rails on the analog bank (5 V + 3V3) are the cheapest way
to be truly sensor-agnostic.

### 4.3 Environmental sensing (compensation backbone)

SHT31-D (`U5`) sits in the gas path **upstream of the MOX array** (between the
digital row and the analog row), on the master I²C bus (not behind the mux).
`U5` is soldered to the board rather than plugged in, so the baffle carries a
dedicated reference port over it (`CONST["SHT_*"]`) — without that opening the
compensation backbone would be sealed behind a solid plate. Firmware logs T/RH
at 1 Hz beside every record; no hard correction in firmware — raw + environment
data is the contract with the host for compensation models.

### 4.4 Recommended starter pack (matrix-derived)

The base has a **4 analog + 4 digital** slot bank (§4; the split is justified in
§4.6–§4.7). `electrical/
sensor_matrix.py` enumerates the market sensor pool and solves an **exact**
minimum set-cover under the two bank contracts — the fewest plug-in modules
whose union covers every required chemical axis, each module placed in the only
bank that can electrically host it.

| Bank contract | Rail | Read-back | Hosts |
|---------------|------|-----------|-------|
| Analog J2–J5 | **5 V**/GND/3V3 | AO + DO | 5 V modules read via analog Vout (MOX heaters, MH‑Z19C/ZE03 Vout) |
| Digital J6–J9 | **3V3**/GND | SDA/SCL/INT/CTRL | 3.3 V I²C modules only — **no 5 V** |

The recommended **starter pack** spans the union of all target personas:

| Slot | Sensor | Principle | Axes covered | Read via | Power | ~Cost |
|------|--------|-----------|--------------|----------|-------|-------|
| A1 | MQ-135 | MOX | amine, reducing, VOC, alcohol | AO | 0.90 W | $2 |
| A2 | MQ-136 | MOX | sulfur (H₂S) | AO | 0.95 W | $3 |
| A3 | MICS-6814 | MOX | reducing, oxidising, amine | AO | 0.50 W | $12 |
| A4 | ZE03-C2H4 | Electrochemical | ethylene | AO (Vout) | 0.03 W | $20 |
| D1 | SCD40 | NDIR | IR-active (CO₂) | I²C | 0.015 W | $25 |
| — | *SHT31 (`U5`)* | T/RH | humidity, temperature | *base I²C* | — | $4 |
| D2–D4 | — | — | spare (specialisation) | — | — | — |

**5 slot modules + soldered base · 4 transduction principles (MOX,
electrochemical, NDIR, T/RH) · all 10 axes · analog bank full, 3 digital slots
free.** Gate: `python tools/verify_sensor_matrix.py`.

Why CO₂ lands on **SCD40 (I²C, digital)** and not MH‑Z19C: ethylene exists only
on the 5 V electrochemical ZE03‑C2H4, and oxidising only on 5 V MOX, so the
analog bank is fully spent (MQ‑135, MQ‑136, MICS‑6814, ZE03‑C2H4). MH‑Z19C is
also 5 V and would need a fifth analog slot — it does not exist. SCD40 is
3.3 V I²C, so it takes a digital slot instead (MH‑Z19C stays a valid swap-in
choice for a persona that frees an analog slot).

The same pool solves far smaller packs for individual personas — the platform is
over-provisioned for the casual user and exactly right for a lab:

| Persona | Modules needed | Pack |
|---------|----------------|------|
| Perfume / personal experiments | 2 | MQ-135 + MICS-6814 |
| Fermentation | 2 | MQ-135 + SCD40 |
| Breath analysis | 3 | MQ-135 + MICS-6814 + SCD40 |
| Kitchen / fridge / cold chain | 4 | MQ-135 + MQ-136 + SCD40 + ZE03-C2H4 |
| Lab researcher (broadest) | 4 | MQ-135 + MICS-6814 + MQ-136 + SCD40 |
| *Starter pack (all personas)* | *5 + base* | *the pack above* |

### 4.5 Sensor module envelope and connector classes

The chamber cannot be sized from a table of "typical" breakout dimensions,
because for the parts this product recommends no such table exists. Auditing the
real ones (`mechanical/modules.py`, gate `tools/verify_module_fit.py`) turned up
five facts that the earlier "worst-case 22 × 35 × 23" assumption hid:

1. **The same sensor ships on different boards.** The MQ-135 today is a 32 × 20,
   32 × 22, 36 × 24 *or* 40 × 21 mm board depending on vendor. "Worst case 35"
   was a single vendor's number presented as a datasheet fact.
2. **The same breakout ships with a different pin order, and the published order
   is the *other* one.** MQ-135 breakouts are sold as `VCC GND AO DO` *and* as
   `VCC GND DO AO`; the widely-copied 32 × 20 board documents `VCC GND DO AO`,
   i.e. the reverse of §4.2's `+5V GND AO DO 3V3`. `tools/verify_module_fit.py`
   compares the two orders as *roles* on every module, so this can't drift back
   into silence: with the documented order the module's **analog output lands on
   the slot's DO pin**, which `board.py` wires to an unprotected 3.3 V GPIO.
3. **Several recommended parts are not plug-in modules at all.** MICS-6814,
   SCD40/41, SGP4x and BME688 are SMD packages; they are only pluggable because
   somebody else's *carrier board* exists, and carriers vary in size.
4. **MICS-6814 has three analog outputs**, while one analog slot reads one AO.
5. **Not every module uses a 2.54 mm header.** MH-Z19C is a 38.8 mm flat module
   with a 1.5 mm JST-ZH connector; DFRobot's Gravity modules use a 3-pin
   JST-PH 2.0; Adafruit STEMMA QT boards use 1.0 mm JST-SH (their unpopulated
   0.1 in holes make them 2.54-compatible); Figaro's TGS parts are bare TO-5 cans.
   The ZE03 is not a card at all but a Ø23.5 × 24.5 mm can.

So the slot is a **standard, not a universal socket**:

| Slot standard | Value |
|---------------|-------|
| Connector | 1 × N male 2.54 mm on the module, receptacle on the board |
| Pose | connector edge horizontal; card plane parallel to the flow (header line along Y) |
| Module must | present a 2.54 mm header, ≤ the envelope below, 1 analog output per analog slot |
| Anything else | arrives on a carrier, or on a pigtail into an unused well |

Verified numbers (mm). `FITS` is the gate's verdict against the geometry in
`mechanical/constants.py`; `MEASURE` means a deciding number is not yet known.

| Module | Form | Outline | Bank | Verdict | Note |
|--------|------|---------|------|---------|------|
| MQ-135/136 class | card | 32 × 20 … 40 × 21 × 1.6 | Analog | **MEASURE** | 40.5–48.5 mm tall in the standing pose ⇒ **hits the plate** (37 mm clear). Pins are `VCC GND DO AO` ⇒ AO/DO transposed against §4.2. |
| Winsen ZE03 (EC) | can | Ø23.5 × 24.5 | Analog | FITS | 33 mm tall ⇒ only a 4 mm recess (spec 8); Ø23.5 in a 26 mm pitch = 2.5 mm gap |
| Winsen MH-Z19C (NDIR) | flat | 38.8 × 19.7 × 8.6 | Analog | **carrier** | 1.5 mm JST-ZH, not 2.54 — pigtail or carrier |
| Figaro TGS2600 | TO-5 can | Ø9.2 | Analog | **carrier** | bare 4-lead can: needs the load resistor + heater drive on a carrier |
| DFRobot Gravity MQ-2 | card | 33 × 22 | Analog | **carrier** | Gravity 3-pin JST-PH 2.0, no 2.54 header |
| Sensirion SEK-SCD41 board | card | 28 × 24 × 8 | Digital | **MEASURE** | standing on its 24 mm edge it leaves 0.5 mm of the recess; flat, its 24 mm width needs a 26 mm pitch |
| Adafruit SCD-40 / STEMMA QT class | card | 25.4 × 17.8 × 4.6 | Digital | FITS | 0.1 in holes must be soldered; flat-mounted its 17.8 mm width still fits a 21 mm pitch |
| SCD40/41, SGP4x, BME688, MICS-6814 | SMD | 2.45² … 10.1² | both | **carrier** | MICS-6814 also needs 3 AO channels for 1 slot |

The two facts that decide the analog-row envelope are still open, and they are
one caliper measurement each:

* **Which card edge carries the connector.** If the 4-pin header is on a MQ
  breakout's *short* edge (as the usual 32 × 20 module looks in vendor photos),
  the card stands on that edge and its **long** edge becomes the height:
  8.5 mm of socket + 32–40 mm of board = 40.5–48.5 mm, i.e. through the 37 mm
  gap to the plate. If the header is on the *long* edge the card is only
  20–24 mm tall and everything fits with room to spare. The 29 mm allowance
  in §4.6 assumed the second case; it is a *requirement*, not a market fact.
* **Where the sensing element sits along the card.** With the card standing on
  its short edge the element is centred on the header line, which is exactly
  where the baffle aperture is — centring is right. With the card standing on
  its long edge the element is 10–20 mm downstream of the header line and the
  aperture, centred on the header line, would **miss the sensor**.

There is no pose in which the aperture can be right for both, which is itself the
result: the pose must be fixed first, then the aperture placed from it.

### 4.6 Derived layout rules

| Rule | Value | Derivation |
|------|-------|-----------|
| Analog in-row pitch | **26 mm** | the module is 24.6 mm across when its Ø19 can points sideways (card 1.6 + can 23) → 1.4 mm gap |
| Digital in-row pitch | **21 mm** | worst 17.6–22.8 mm + ≥ 3 mm gap; a module standing on an edge is only ~8 mm across, but **flat-mounted** only a ≤19 mm-wide board fits — Sensirion's own SCD41 board is 24 mm wide, so it needs 26 mm |
| Analog row span (4) | 3×26 + 24.6 = **102.6 mm** | with every can pointing the same way; the end cans must face inward or the chain exits the cavity (x −2.6 … 124.6 in a 114 mm shell) |
| Digital row span (4) | 3×21 + 5 = **68 mm** | no cans |
| Free depth per row | 26 / 42 / 32 mm | ahead of the digital row / between the rows / behind the analog row |
| Module height allowance | **≤ 29 mm**, i.e. 8 mm of recess under the plate | 8.5 socket + card + 8 must stay ≤ 37 mm; **open** — the real card height is §4.5's measurement |
| Module envelope along flow | analog **≤ 35 mm**, digital **≤ 26 mm** | a *requirement on the module* (§4.5), not a market fact |
| Insertion orientation | card body into the free depth, silkscreen arrow | a 35 mm analog card only fits extending **forward** into the 42 mm inter-row gap; a digital card extends **rearward**, stopping ≥ 7 mm short of the analog apertures |
| Clear height | **34.4 mm** above the board | to the lid underside at 43 mm |
| Cavity inner height | **40 mm** | board top 8.6 to lid 43 |

> **Mounting is not free, and the previous rule was backwards.** A module hangs
> off its connector by its card length. "Connector edge toward the front" put a
> 35 mm analog card's far edge at y = 110 mm — through the rear wall at 107 —
> which is the failure §4.6 already warned about in the same paragraph. The
> correct rule is that the connector edge sits at the rear of the *analog* row
> (card body forward, into the 42 mm gap) and at the front of the *digital* row
> (card body rearward, no more than 33 mm). Because the free depths are 26/42/32
> and the apertures are placed at the header lines, the pose and the aperture
> positions must be derived together — see §4.5's aperture-alignment finding and
> §14's open item. Until the card height is measured, the module envelope is a
> requirement, not a verified fit.

> 17.5 mm pitch (older spec) is **discarded** — it cannot seat two MQ modules
> (17.5 < 22). The 26 mm analog lane is the "wide-body" lane; a narrow lane
> would exclude four of eight common families. 26/21 is a deliberate pitch
> choice, not a hard constraint: §4.7 shows that tightening the analog row to
> ≈ 21 mm would fit a **fifth** analog slot (5 × 21 = 105 ≤ 106 mm), which the
> information analysis says is worth having.

### 4.7 Trade study — the slot count, derived

The literature is **mixed, and in a specific way**: the right number is a
*per-task* property set by response-matrix geometry, not a slogan.

- Pruning helps when channels are **redundant**: ISOEN 2026, Ren et al.
  (doi:10.1109/ISOEN68725.2026.11665159) 13 → **5** raised 83.59% → **89.69%**;
  *Sens. Actuators B* 2024 (S0925400524003083) 8 → **4**, 0.905; Kong et al.
  *Sensors* 2025 (PMC11902490) 6 → best 4; oyster cold-chain (PMC12730598)
  10 → 5–6, > 40% redundancy removed, still > 93%.
- Adding helps when channels are **orthogonal** or average noise: *PLOS ONE*
  2023 (doi:10.1371/journal.pone.0295703) replicated each of 6 types ×5,
  98.08% → 99.78% (noise averaging, **not** new information); Cyranose 320 ships
  a deliberately-redundant 32-sensor array and prunes at run time.
- Selectivity ranking (EPA / Boise State survey): NDIR > electrochemical > PID
  > MOX. MOX is high-sensitivity, low-selectivity, drift-prone — useful only
  *inside* an array.

So "more slots" is the wrong axis; **sensor count ≠ information**. `electrical/
orthogonality.py` makes it computable on `sensor_data.py`: build R[sensor × gas]
over the 17-analyte space, unit-normalise the rows, greedily add the channel
whose response has the largest component orthogonal to those already chosen
(its *marginal information*), and read the *effective rank* (participation
ratio). Two near-parallel rows add ≈ 0 no matter how many axes they name.

Order-independent anchors:

- the whole **45-module market spans only 8.21 independent dimensions** for the
  broad 17-gas set → slots beyond ≈ 8 add no independent information, only MOX
  self-heat;
- analog pool spans **7.93**, digital pool only **3.43** — **9 of 17 gases are
  analog-only** (NH₃, TMA, H₂S, mercaptan, ethylene, HCHO, CO, CH₄, SO₂); a
  digital-only bank (0A+9D) captures just **50%** of broad energy.

Per-use-case **analog floor** (greedy certificate; an upper bound on the true
minimum — if the greedy set works, that many analog slots suffice):

| use case | A-floor (D=9) | 4A+4D | 5A+3D | 6A+2D |
|----------|:---:|:---:|:---:|:---:|
| indoor_air | 4 | 100% | 100% | 100% |
| fermentation | 1 | 100% | 100% | 100% |
| cold_chain | 4 | 96% | 100% | 100% |
| kitchen_fridge | 5 | 93% | 96% | 100% |
| breath | 4 | 100% | 100% | 100% |
| perfume | 3 | 100% | 100% | 100% |
| broad (multi-domain) | 10 | 61% | 55% | 60% |

**Conclusion — analog and digital are different currencies; the optimum is
asymmetric.**

- **Analog is scarce and valuable.** It carries the orthogonal information and
  the 9 analog-only gases; it is the *only* way to reach breath / kitchen /
  cold-chain. Its floor is **5** (4 analog leaves `kitchen` at 93%; 5 lifts the
  worst single-domain case to 96%). Each analog slot costs
  a 5 V rail, ≈ 0.9 W self-heat, an ADC channel (4 per ADS1115) and a *wide*
  module.
- **Digital is abundant and cheap.** ≈ 0.05 W, tiny modules, one shared I²C bus
  (TCA9548A, 8 channels). Extra digital slots add little *new* information
  (digital pool rank 3.43) but cost almost nothing and host the NDIR-CO₂ /
  VOC-index / NOx parts plus replication headroom (the *PLOS ONE* noise-averaging
  result). They **cannot** substitute for the 5th analog — the gap is
  analog-only gases.
- **Pins** (17): analog = 1 each, digital = 2 each; 5A+4D = 17/17 MCU-only,
  5A+6D needs the MCP23017 expander.

Candidate frontier (broad capture / worst single-domain case):

| bank | pins | MCU-only? | broad | worst case | note |
|------|:---:|:---:|:---:|:---:|------|
| 4A+4D (as-built) | 16 | yes | 61% | 93% | kitchen starved |
| **5A+4D** | 17 | yes | **64%** | **96%** | info-optimal |
| 5A+3D | 15 | yes | 55% | 96% | 2 spare pins |
| 6A+3D | 16 | yes | 64% | 100% | 16.8 mm pitch — infeasible full-width |
| 6A+4D | 18 | expander | 73% | 100% | +9% broad; needs expander |
| 5A+6D | 21 | expander | 69% | 96% | more digital, cheap |

**Information-optimal bank: 5 analog + 4 digital (9 slots), 17/17 MCU-only.**
The product is the as-built **4A+4D** (§4.6): the 106 mm analog lane holds four
full-width (22 mm) modules, so a 5th is a mechanical decision, not a count one.

Caveat (feasibility, not information): a 5th *full-width* analog module needs
21 mm pitch < the 22 mm MQ body, so the 106 mm lane holds 4 full-width analog
unless the analog modules are narrower (Alphasense 20, MICS 10, bare MOX can
18) or the lane is staggered in depth (the bay has 54 mm of depth — enough for
two 18 mm sub-rows). That — plus the 5-MOX thermal check (≈ 4.5 W, versus the
stated ≤ 2.5 W system figure that 4 MOX already exceeds) — is the open
mechanical/thermal question, *not* the slot count. As-built is 4A+4D (§4.6);
re-banking to 5A+4D changes the analog pitch and needs the NF2/NF6 flow/thermal
pass. The 17-gas "broad" research set needs 8 analog and deliberately does
**not** fit. Gate: `python tools/verify_orthogonality.py --banks`.

### 4.8 Open items

MQ module envelope **and mass** from a physical sample (§4.5 — three caliper
numbers decide the chamber) · fan derating through the real filter
(flow bench / scaled CFD) · sensor-matrix upkeep as new market sensors appear
(add a row in `electrical/sensor_matrix.py`; the gate re-solves the pack).

### 4.9 The module standard (OSM-1) — the decision that closes §4.5

§4.5 and the trade study in §4.7 both end at the same wall: the market sells one
socket contract (2.54 mm) and a size zoo (see `mechanical/modules.py`), so
"which modules fit" is not answerable in general. The answer adopted is to stop
chasing footprints and define the socket:

**One slot design, repeated.** Every slot carries a keyed 5 V gas-cell socket
(1×6) *and* a 3.3 V Qwiic/STEMMA QT port on the same footprint. There
is no analog row and digital row for the user to get wrong; the module's own
identity tells the base how to talk to it. The full rules — pinouts, the
identity EEPROM and its memory map, the flat cartridge envelope, the wetted
material bans, the conformance checklist and the cost — are in
**`docs/module-standard.md`**, with the same numbers as data in
`mechanical/standard.py` and the gap against the as-built board reported by
`tools/verify_module_fit.py`.

Three consequences matter here:

| Decision | Why |
|----------|-----|
| **Flat cartridge** (card parallel to the board, right-angle header in a vertical socket, sensing face up, lifts out upward) | a MOX can's inlet is its **end face**, so flat points it at its window instead of at its neighbour; and it turns the 40–48 mm standing height that collided with the plate into 25 mm |
| **Uniform 24 mm pitch, 8 slots, 2 rows of 4** | four slots span 96 mm inside the existing 106 mm cavity, so uniformity costs **no size**: the same 122 mm shell, built from one repeat unit instead of two different ones |
| **Identity EEPROM on the cartridge** | pin order stops being a hazard, calibration and exposure hours travel with the cell, and per-cell drift becomes a software problem (the TEDS idea from IEEE 1451, one pin for all slots) |

The chamber is a **cascade**, not eight parallel chambers: the upstream row sees
fresh sample and the downstream row sees partly-depleted sample. Each record
therefore carries its slot index and flow position so the host models the
depletion, and the guidance is to put the cells you trust most upstream. That,
the window pitch and the front-row/aperture exchange question are what the CFD
pass in §8.3 must quantify — §4.9 fixes the hardware, the solve fixes the
numbers.

Service access follows from the flat pose and is an enclosure requirement, not a
socket one: the cartridge comes out upward, and the flat screwed lid is the only
thing above it (§6.1).

---

## 5. Electrical Design

### 5.1 Power tree

```mermaid
flowchart TD
    USB["USB-C 5 V / 3 A"] --> N5["5 V net"]
    N5 --> FAN[Fan via PWM MOSFET]
    N5 --> AH["Analog headers +5V (J2–J5)"]
    N5 --> BZ[Buzzer via transistor]
    N5 --> LDO["U7 AMS1117-3.3"]
    LDO --> N33["3.3 V net"]
    N33 --> MCU[ESP32-WROOM-32E]
    N33 --> ADC["ADS1115"]
    N33 --> MUX[TCA9548A]
    N33 --> ENV["SHT31 + OLED"]
    N33 --> DH["Digital headers 3V3 (J6–J9)"]
```

v0 gap resolved: the earlier design referenced 3.3 V with **no regulator** —
this revision adds `U7` AMS1117-3.3 (SOT-223, 5→3.3 V, 1 A; 100 nF in, 10 µF out).

### 5.2 Microcontroller — ESP32-WROOM-32E (`U1`)

Dual-core Wi-Fi/BT; onboard ADC unused (nonlinear). I²C master GPIO 21 (SDA) /
22 (SCL) @ 400 kHz. UART0 over USB-C to host via bridge `U3` (CH340C): TXD/RXD
cross to the ESP32 RX0/TX0 and its 3V3 tap is the 3.3 V logic reference.
Three buttons: **SW1 MEASURE** (GPIO 23), **SW2 BOOT** (GPIO 0), **SW3 RESET**
(EN) — flashing is manual (hold BOOT, tap RESET), no auto-reset transistors.

### 5.3 Analog acquisition — ADS1115 (`U2`)

16-bit, 4-ch, I²C @ `0x48`. 4 single-ended channels (AINn–GND), PGA ±4.096 V,
input clamped ≤ 2.5 V by the divider. 8–16 SPS/channel during HOLD — one channel
per analog slot.

### 5.4 Digital bus — TCA9548A (`U4`)

8-channel I²C switch @ `0x70`, one channel per digital slot. Per-channel 4.7 kΩ
pull-ups so one slow sensor cannot block another. Master bus: ESP32 + U2 +
SHT31 + OLED.

### 5.5 GPIO map (generated by `electrical/interface.py`)

| Function | GPIO |
|----------|------|
| I²C SDA / SCL | 21 / 22 |
| UART0 TX / RX (USB serial) | 1 / 3 |
| Fan PWM | 4 |
| Buzzer | 13 |
| Status LED | 14 |
| Measure button | 23 |
| DO0–DO3 (analog 1–4) | 33, 34, 35, 36 |
| INT0–INT3 (digital) | 25, 26, 27, 32 |
| CTRL0–CTRL3 (digital) | 16, 17, 18, 19 |

> This is the **native 4+4** map. It uses no boot-strapping pin, and no
> input-only pin as an output (DO1–DO3 are read-only on GPIO 34–36). One ADC
> plus one mux closes the ESP32's usable pins; §4.7 shows why the bank is fixed
> at 4+4. Buzzer needs a drive transistor (GPIO cannot sink 30 mA).

### 5.6 UI & indicators

OLED SSD1306 0.96" (`U6`, `0x3C`) — phase, time, live AO/TVOC, T/RH, last
summary. Status LED: heartbeat/breathing/solid/fast-blink. Active 5 V buzzer
(`BZ1`) for end-of-measurement.

### 5.7 Connectors

| Connector | Type | Purpose |
|-----------|------|---------|
| J1 | USB-C 16P | Power + serial |
| J2–J5 | 1×5 2.54 mm female | Analog slots (`5V GND AO DO 3V3`) |
| J6–J9 | 1×6 2.54 mm female | Digital slots |
| J10 | JST-PH 2P | Fan |

All sensor headers female ⇒ breakouts plug straight in, swappable without
soldering.

### 5.8 Rail budgets

Two budgets, because they answer different questions: the **worst case** bounds
*any* pack (all 8 slots populated), while the **starter pack** is what ships.

| Rail | Worst case (every slot filled) | Starter pack (§4.4) | Supply |
|------|-------------------------------|---------------------|--------|
| 5 V | 4 × MOX 0.60 + fan 0.15 + buzzer 0.03 = **0.78 A** | sensors 0.476 + fan 0.15 + buzzer 0.03 = **0.66 A** | USB-C 5 V/3 A |
| 3.3 V | ESP32 0.15 + 4 × digital 0.20 + ADC/mux/OLED/SHT31 0.10 = **0.45 A** | sensors 0.005 + ESP32 0.15 + periph 0.10 = **0.25 A** | AMS1117-3.3 1 A |

ESP32 draws 0.15 A average but peaks ~0.5 A transiently (Wi-Fi); the AMS1117
1 A rating absorbs that. Both budgets stay inside their supply, with the gates
enforcing ≤ 80 % of each rail: `python tools/verify_electrical.py` (worst case)
and `python tools/verify_sensor_matrix.py` (pack draw).

---

## 6. Mechanical Design

### 6.1 Envelope & layout

Shell (tray) **122 × 114 × 43 mm**, lid **122 × 114 × 6 mm**, assembled
**122 × 114 × 49 mm** (128 mm deep with the rear fan). 3 mm walls, 3 mm floor.
Board **114 × 105 mm** on four Ø6 standoffs, component side up, its top face at
z = 8.6 mm. The eight 1×6 sockets stand 8.5 mm above it and the modules plug
straight in. Service is four M3 screws.

The architecture is deliberately the one a builder can hold in their head:

```
tray  ->  board on four standoffs  ->  modules into the eight headers
      ->  filter pad drops into the front  ->  flat lid, four M3 screws
```

There is **no baffle plate, no plenum, no flow lane, no well and no window**.
An earlier revision put a 2 mm plate 37 mm above the board with eight 20 × 20 mm
openings over the modules. It was dropped: it doubled the part count, made the
chamber 90 mm tall, required a machined PTFE insert to stay inert, and forced
every cartridge into a recess so the sensing face sat below the plate. None of
that was needed. A cartridge plugged into its socket looks straight into the
moving sample; the only thing it needs is unobstructed air above its sensing
face.

| Part | Size | Process |
|------|------|---------|
| Shell (open tray) | 122 × 114 × 43 | PETG FDM, or AL 6061-T6 |
| Lid (flat plate) | 122 × 114 × 6 | PETG FDM, same spool |
| Filter pad | 110 × 4 × 23 | non-woven or PTFE felt, consumable |
| Fan | Ø40 × 10 | any 5 V axial, mounted on the rear plate |
| Screws | M3 × 12, 4 off | into heat-set inserts |

The fan sits **outside** the rear face on a 4 mm plate, so motor heat never
enters the sample and the fan can be changed without opening the box. Its four
screws are blind: 6 mm of thread in plate + wall, and no hole into the chamber.

v1 is **headless**. There is no display window, no button hole and no buzzer
hole: those parts live on the board inside, reachable with the lid off, and the
UI is Osmograph. This removes the separate front-panel board, the ribbon, and
the entire class of "the panel does not line up with the chamber" defects.

> **Board re-lay is the next electrical task.** The enclosure is now the
> contract: the board must match it, not the other way round. Two changes are
> needed — four corner notches (r = 5) for the lid bosses, and the USB-C moved to
> the front edge. Nothing else moves.

### 6.2 Chamber geometry (locked)

| Parameter | Value |
|-----------|-------|
| Cavity inner (L×W×H) | 116 × 108 × 40 mm (≈ 0.50 L) |
| Floor | 3 mm printed, under the board |
| Board top (chamber floor) | z = 8.6 mm |
| Lid underside (chamber ceiling) | z = 43 mm |
| Clear height above the board | 34.4 mm |
| Inlet | 3 × Ø6 through the front wall at z = 30, pitch 26 |
| Outlet | Ø38 bore at z = 23, into a Ø40 fan |
| Socket rows | analog y = 75, digital y = 33 (as-built PCB positions) |
| Row spacing | 42 mm, so a 32 mm cartridge cannot reach the next row |
| Header pitch | 26 mm analog / 21 mm digital (a base parameter, not a module rule) |
| Filter | 110 × 4 × 23 pad in a front drawer, held down by the lid |
| USB-C | Ø12 bulkhead hole at x = 14, z = 10 |

Flow is horizontal, front to rear: nostrils → filter pad → over the digital row
→ over the analog row → rear bore → fan. The nostrils sit 11 mm above the
module plane so the inlet jet spreads before it reaches the first row instead of
blasting one cartridge.

### 6.3 Materials & sample-memory control

Sample *memory* (carryover) is the silent killer of e-nose data. Every
gas-contacting surface either adsorbs/outgasses VOCs or it does not.

| Surface | Allowed | Forbidden (why) |
|---------|---------|-----------------|
| Chamber walls | PETG, sealed; optional PTFE liner sheet | silicone, PVC, bare zinc, paper, foam (adsorb/outgas) |
| Tubing | PTFE, PFA, stainless | silicone, PVC, Tygon (adsorb VOCs) |
| Filter→sensor path | mechanical media only | porous carbon in series (strips the analyte; carbon belongs on a reference-air line) |
| Gaskets | none in v1 | natural rubber, EPDM (outgas) |
| Conformal coat | acrylic or polyurethane | silicone (its vapour poisons SnO₂) |

**Manufacturing consequence:** the tray and lid are printed PETG, and the wetted
faces are sealed. That is a deliberate change from the earlier "machined PTFE
insert" plan: an open chamber with a small wetted area and no dead volumes
carries far less memory than a closed plate-and-liner assembly, at a fraction of
the cost. A PTFE liner remains an optional upgrade for trace-level work, not a
requirement for the base.

### 6.4 Mass estimate

| Item | Qty | Subtotal |
|------|-----|----------|
| PCB 114×105×1.6 FR4 | 1 | 36 g |
| MQ breakout | 4 | 36 g |
| MEMS/NDIR breakout | 4 | 9 g |
| Shell + lid (PETG, 3 mm) | 1 | 130 g |
| Fan + hardware | — | 25 g |
| **Total (worst case)** | | **≈ 240 g** |

---

## 7. Firmware Requirements

Structurally defined; timing parameterised. Reference target: Arduino-ESP32 core,
single serial main loop + cyclic state machine (see `firmware/`).

1. **Cycle state machine** — IDLE → INTAKE(10 s) → HOLD(10 s) → PURGE(20 s) →
   report; driven by the MEASURE button (`GPIO23`) or a host command over any
   transport. `GPIO0` is the BOOT/strapping button only.
2. **Analog acquisition** — during HOLD, read the **4 ADS1115 channels** (AIN0–3,
   one per analog slot) at ~8 SPS/channel with per-channel averaging.
3. **Digital scan** — during HOLD, iterate **TCA9548A channels 0–3** (one per
   digital slot); driver registry keyed by the chip ID found on each channel.
4. **Environmental logging** — SHT31 at 1 Hz, all phases.
5. **Comms** — one JSON record shape over three transports; **USB serial is the
   wired default and always on**:
   `{ts, phase, ao[4], digital[4], t, rh, cycle_id}`
   - **USB-UART** @115200 baud → host (Osmograph). Carries power and data.
   - **Wi-Fi 2.4 GHz** — join (STA) using credentials set over serial or BLE,
     with a fallback soft-AP for first-time setup; publish records to **MQTT**
     (JSON topic) and serve a minimal **HTTP/JSON + WebSocket** live endpoint.
     Off by default, enabled by button or host command, so idle stays < 1 W.
   - **Bluetooth LE** — a GATT **notify** characteristic streams the same JSON
     frames for phone/field use, plus a write/command characteristic; BLE is also
     the credential-provisioning path.
   The radio is on the **ESP32-WROOM-32E** module (pre-certified; no BOM change);
   Wi-Fi TX peaks ~0.5 A, already inside the §6 power budget.
6. **UI** — OLED phase/values; LED state machine (§5.6).
7. **Self-test on boot** — fan tach (if present), I²C enumeration, divider sanity,
   SHT31 read; pass/fail on OLED.

**Proposed source layout:**

```
firmware/esp32/smell_monitor/     # arduino-cli sketch; build with:
                                  #   arduino-cli compile --profile default
├── smell_monitor.ino   # setup() / loop()
├── config.h            # pins + I2C addresses (checked vs interface.PINMAP)
├── proto.h/.cpp        # one JSON record shape (all transports)
├── sensors.h/.cpp      # ADS1115, TCA9548A, SHT31 (raw I2C, no extra libs)
├── ui.h/.cpp           # OLED (U8g2), status LED, buzzer
├── net.h/.cpp          # USB serial + Wi-Fi (MQTT + HTTP) + BLE (GATT)
├── cycle.h/.cpp        # three-phase state machine + acquisition
├── sketch.yaml         # profile: esp32:esp32:esp32 (huge_app) + libs
└── test/               # unit tests for cycle state transitions
```

Target: **Arduino-ESP32 core 3.x** (`esp32:esp32:esp32`, partition scheme
`huge_app` — the radio + OLED stack needs > 1.3 MB). Builds clean against
U8g2 2.36.19 + PubSubClient 2.8.0; `tools/verify_firmware_pins.py` checks the
firmware pin map against `interface.PINMAP`.

**Non-goals:** no on-device classification; no hard sensor calibration.

---

## 8. Verification & Validation

### 8.1 Electrical
- KiCad **ERC** clean (0 errors; warnings reviewed) — gate for TCA9548A
  address/pull-up/strapping pins.
- KiCad **DRC** clean before Gerber export.
- Bench: rail integrity under max load; ADC linearity (divider 0–2.5 V); I²C
  enumeration of 8 simultaneous same-address sensors behind the mux.

### 8.2 Pneumatic (acceptance for sample-memory)
- **Purge completeness:** after strong odor, one full cycle returns all sensors to
  ≥ 95% baseline.
- **Fan-speed invariance:** fixed exposure at 40/70/100% PWM; response must not
  shift (validates the open chamber).
- Plus NF1–NF5 (§3.8).

### 8.3 CFD (optional, once)
Single steady-state cavity sim at 15 L/min (and a 150 L/min full-speed case).
Verify no recirculation zone > 5% of volume upstream of any sensor; sensor-nose
velocity ≤ 0.1 × duct core. Tool: OpenFOAM `simpleFoam`. This is *validation*,
not a design driver — v1 geometry is already locked by the rules of §3 and §4.

### 8.4 Delivery checklist for fabrication
- [x] ERC 0 errors · [x] DRC 0 errors (`tools/verify_netlist.py`, `tools/verify_pcb.py`)
- [x] Gerbers + drill + CPL (`tools/export_fab.py` → `electrical/smell_monitor_v1_1/fab/`)
- [ ] Supplier part numbers in the BOM (`electrical/bom.csv` is designator/value/footprint/qty only)
- [ ] STEP of assembly + enclosure · [ ] Assembly guide · [ ] Firmware binary + flash guide

---

## 9. Bill of Materials

Base electronics (representative; the full line-item list is in
`electrical/bom.csv`):

| Ref | Part | Notes |
|-----|------|-------|
| U1 | ESP32-WROOM-32E | MCU, Wi-Fi/BT |
| U2 | ADS1115 | 16-bit 4-ch ADC (4 analog channels) |
| U4 | TCA9548A | 8-ch I²C mux, one channel per digital slot |
| U5 | SHT31-D | T/RH, upstream |
| U6 | OLED SSD1306 0.96" | UI |
| U7 | AMS1117-3.3 | 5→3.3 V LDO (added this revision) |
| Q1 | AO3400A (SOT-23) | Low-side fan PWM switch (GPIO 4) |
| Q2 | MMBT3904 (SOT-23) | Buzzer driver NPN (GPIO 13) |
| FAN1 | 40×40×10 mm 5 V PWM | Rear exhaust |
| BZ1, LED1 | Active buzzer, status LED | UI |
| J1 / J2–J5 / J6–J9 / J10 | USB-C / 1×5 / 1×6 / JST-PH | Connectors |

BOM deltas from v0: **add U7** (v0 had no 3.3 V rail) · analog headers
`5V/GND/AO/DO/3V3` · digital headers `3.3V/GND/SDA/SCL/INT/CTRL` · fixed 2:1
divider on AO · OLED 0.96" + active buzzer.

---

## 10. Assembly & Bring-up

Sources: PCB `electrical/smell_monitor_v1_1/` (routed, DRC-clean) · BOM
`electrical/bom.csv` · enclosure `mechanical/` · sensors user-supplied.

**Order of soldering (small → large):** 0603 passives → U7 (SOT-223 tab well
soldered) → U2/U4/U5 → OLED/LED/buzzer → connectors (USB-C, JST, 8 headers)
→ ESP32 module last.

**First-power tests:** 3.3 V rail at U7 = 3.35 ± 0.1 V · probe every slot rail ·
I²C scan expects `0x48, 0x44, 0x70, 0x3C` · flash firmware, confirm
self-test screen.

**Chamber assembly:** PCB onto the four standoffs (component side up, top face is
the chamber floor) → eight sensor cartridges into their headers, flat, connector
toward the front → filter pad down into the front drawer → lid on, four M3 screws
→ fan in the service bay (exhaust out the rear) → seal, close the hatch.

**Final integration:** power-on self-test `OK` · purge sanity (3 clean cycles,
baselines within a few %) · sample challenge (coffee; confirm response, then full
baseline return after one cycle).

---

## 11. User Manual

**What it does.** Draws a small air sample, exposes interchangeable gas sensors,
records each response, and streams the "smell signature" over USB. It does **not**
identify smells on its own and is **not** a calibrated safety instrument.

**Uses:** compare two samples; monitor a smell over time; archive signatures;
sensor research.

**Operating a measurement.** Place near (not touching) the sample → press measure
→ wait ≈ 40 s (10 intake / 10 hold / 20 purge). LED: slow blink = idle, breathing
= sampling, solid = analysing, fast blink = results ready. Results stream over the
**USB-C cable** by default; the same readings can be sent over **Wi-Fi** or
**Bluetooth** to a phone or network once enabled (button or host command).

**Slots.** 4 analog (`5V|GND|AO|DO|3V3`) for MOX/e-chem/NDIR-5V; 4 digital
(`3V3|GND|SDA|SCL|INT|CTRL`) for MEMS/NDIR-I²C. Any matching breakout module
plugs straight in; swap is tool-free (open hatch, seat module) and
auto-detected at power-on.

**Choosing modules.** Start with the recommended pack (§4.4, 5 modules + base);
add or swap singly for a specific job. Ammonia/amine → MQ-135/137 · sulfur →
MQ-136 · general VOC → MQ-138/SGP40 · CO₂ → SCD40 (I²C) or MH-Z19C (5 V, needs a
free analog slot) · ethylene → ZE03-C2H4 · RH + profile → BME688.

**Maintenance.** Clean cavity with dry lint-free cloth (no solvents unless
instructed) · replace intake filter every 90 days or after clogging/smoke/dust
(PTFE side toward incoming air) · firmware update over USB via Osmograph.

**Troubleshooting.** Dark screen → power/cable · fan fault → check fan/connector ·
no sensors → install/reseat · stuck reading → clean/replace sensor · all-day drift
→ warm up 10 min and log temperature · lingering smell → 2–3 purge cycles, else
clean · bad data → check cable, 115200 baud.

**Safety.** Experimental/research instrument, 5 V USB-C, do not open the service
bay while powered, keep from liquids, not for explosive atmospheres.

**Specifications.** Power USB-C 5 V (3 A source assumed; ≥ 1.5 A needed) · idle < 1 W, ≈ 5 W loaded with four
MOX modules (their heaters dominate — see §5.8) · 4+4 sensor ports · cycle
≈ 40 s · airflow 15 L/min design purge (> 100 L/min flush) · intake filter
replaceable non-woven · 122 × 128 × 49 mm including the rear fan · ≈ 240 g · 5–40 °C, 20–80% RH · USB-C
serial 115200 baud · Wi-Fi 2.4 GHz + Bluetooth LE (same data).

---

## 12. Drawing Set (CAD, editable)

Drawings are generated from the single parametric 3D model, not hand-drawn, and
are provided in **two forms**: an editable **CAD source** (DXF / native) and a
plotted **PDF** for the record — per ASME Y14.100 / ISO 5457 practice.

| Sheet | Content | Status |
|-------|---------|--------|
| OS-000 | Assembly — exploded isometric with balloons + BOM + **section B-B** (the full stack at x = 61: lid, board, sockets, filter, fan) + isometric | **produced** |
| OS-001 | Shell — **front** (intake face) / **section A-A** at x = 61 / isometric, fully dimensioned | **produced** |
| OS-002 | Lid — **plan at 1:1** (hole pattern, print-and-check template) / **section C-C** at 1.5:1 through the counterbores / isometric | **produced** |
| OS-003 | PCB mechanical floor plan — board 114×105, header rows, corner notches | planned |
| OS-004 | Pneumatic schematic — flow path, ΔP, fan operating point | planned |

Projection is performed by the CAD kernel's hidden-line-removal (`TechDraw.projectEx`
returns true visible/hidden edges measured off the solid), so the views are
faithful, not schematic boxes. Sheet format: A3 landscape, ISO 7200 title block,
first-angle projection. The sheets are emitted as an editable **DXF** source and
a plotted vector **PDF** in `mechanical/drawings/sheets/`.

The set covers three parts and nothing else. There is no baffle sheet, because
there is no baffle; OS-002 is the lid, which is a plate with four counterbored
holes and is drawn at 1:1 so it can be printed and laid on the real part.

**Sections are cut, not drawn.** Each section view is the solid cut by a half
space, and the builder extracts the planar faces that cut created (outer wire
first, then islands) and ships them as `cuts` in the HLR record. The sheet
generator hatches exactly those polygons with ANSI31 and draws their boundary as
a heavy line, so the fill cannot drift off the part and a section can never
silently become a wireframe. `tools/verify_cad.py` requires HATCH entities on
both part sheets.

**A plan view is not a section.** Where a plan would project the cavity, the
board and the bosses onto each other as hidden lines, the sheet uses a real cut:
OS-001's section A-A is a vertical cut at x = 61 (through an intake, the filter
seat and the exhaust bore) and OS-000's section B-B is the same plane through
the whole assembly, so it proves the stack — lid, board, sockets, filter pad,
rear wall, fan. Isometric views are rotated by −30° so the model +Z is vertical —
TechDraw's projector puts +Y vertical, which makes an unrotated isometric lie on
its back and hides the fact that the parts are stacked in Z.

**Dimensioning.** Dimensions are true DIMENSION entities (`dimlfac = 1/s`, so the
displayed value is the model millimetre size) and they are attached to the real
features they name. That is possible because the builder also measures, per view,
the (u, v) components of the global +X/+Y/+Z axes *in that projection* — the same
projector is aimed at a 100 mm reference line along each axis — and stores them
as `axes` in the HLR record. An orthographic projection is linear, so the sheet
generator inverts it exactly and can put a dimension on a model feature instead
of on a hand-guessed paper coordinate. `tools/verify_cad.py` refuses a view with
no measured axes, checks the dimension *values* against `constants.py`, requires
a minimum number of dimensions on each part sheet, and fails any text that would
print past the sheet border.

**Sources & build (all checked in):**
- `mechanical/constants.py` — locked parametric dimensions (single source).
- `mechanical/freecad/build_smell_monitor.py` — headless model build + HLR +
  measured projection axes (`FreeCADCmd.exe .../build_smell_monitor.py`) →
  `.FCStd`, `.STEP`, `.stl`, and `mechanical/drawings/model_hlr.json`. The
  exploded arrangement is built here too (parts offset along the assembly axis,
  offsets stored with the geometry so the drawing's balloons point at the real
  exploded positions).
- `mechanical/freecad/style_smell_monitor.py` — paints the model for GUI viewing.
- `mechanical/drawings/gen_dxf_sheets.py` — places the HLR geometry on A3 sheets,
  dimensions it, writes `OS-000/001/002.dxf` and plots
  `OpenSmell_v1.1_sheets.pdf`.
- `tools/verify_cad.py` — numeric CAD gate over all of the above (must exit 0).

**Two-stage pipeline:** FreeCAD (model + HLR) → system Python (ezdxf sheet
composition + plot). OS-003/004 remain to be authored (§14).

### 12.1 PCB deliverables (routed output)

The board is generated, not hand-drawn, and every generator refuses to overwrite
a board that already carries copper without an explicit `--force`, so routing can
never be silently destroyed or faked:

- `electrical/board.py` — parts + nets (the netlist source of truth).
- `electrical/gen_schematic.py` → `smell_monitor_v1_1.kicad_sch` (ERC-clean).
- `electrical/gen_pcb.py` — placement only: outline, footprints, netclasses.
  The 8 sensing headers are placed on `interface.ANALOG_HEADERS` /
  `DIGITAL_HEADERS`, exactly the eight socket rows.
- `electrical/route_pcb.py` — export Specctra DSN → FreeRouting (`java -jar`,
  `-mp 12`) → import SES. Refuses to save unless 0 unconnected remain. The
  autorouter is multi-threaded and not bit-reproducible; the *outcome* is
  (0 unconnected, 0 DRC violations).
- `tools/export_fab.py` → `electrical/smell_monitor_v1_1/fab/` — the exact fab
  layer set (F/B Cu, mask, silkscreen, paste, Edge.Cuts), Excellon drill and one
  CPL; any stray layer in the folder is deleted.
- `tools/verify_pcb.py` — numeric gate on the routed board (headers on contract,
  outline, minimum track width, via stack, 0 unconnected, DRC clean).

---

## 13. Risks & Future

| Risk | Mitigation |
|------|------------|
| Wetted-material cost | Plain PETG tray + lid; a PTFE liner is an optional upgrade |
| Most slots unfilled at first | v1 proves the interface; packs modelled later |
| Fan speed affects MOX temperature | Fan outside the chamber; validated by §8.2 |
| Sensor drift over months | Swappable sockets + SHT31 data + shared open dataset |
| USB-C current limits | 5 V/3 A source assumed; §5.8 |
| MOX cross-sensitivity | Cannot be fixed in hardware; platform removes confounders only |
| Silicone poisoning of MOX in the field (the classic irreversible death) | Assembly ban: no silicone or PVC anywhere the gas touches (§5). Per-cell exposure hours and peak temperature live in the cartridge EEPROM (§4.9), so a cell that has been through a silicone event is de-rated or refused instead of quietly trusted. Carbon belongs on a **reference-air** line, never in series with the sample — it would strip the analyte (§3.6, §6.3). |

**Future:** v1.1 — battery/USB-PD, fan tach, higher-flow option · v2.0 —
manifold switching / multi-compartment robotics sampling, valued reference-air
path for automatic zero/baseline calibration.

---

## 14. Revision History & Open Items

| Rev | Date | Change |
|-----|------|--------|
| A | 2026-10-13 | Consolidation of all prior docs into this single blueprint. Objective + success criteria locked (§0). Drop-in of architecture, component analysis, pneumatics, manual, assembly. Best-practice stds adopted (ASME Y14.100/24/5, ISO 128/5457). |
| B | 2026-10-14 | **Architecture pivot to native 4 analog + 4 digital (8 slots, expandable to 8+8).** Driven by: GPIO closure (4+4 = 16 signals ≤ 17 ESP32 pins, no expander; 8+8 = 28, requires one), repeatability/carryover physics (smaller chamber), bulk, and cost. Shell 226→122 mm, cavity 210→106 mm, PCB 218→114 mm, board recentred. §4.5/§5.5/§5.7 regenerated. Added machine-checked contract `electrical/interface.py` + `tools/verify_electrical.py`. |
| C | 2026-10-15 | **Slot count settled by evidence.** Base keeps a fixed 4+4 (8-slot) bank of plug-in breakout slots. E-nose array-optimisation literature shows fewer orthogonal sensors beat more redundant ones (ISOEN 2026 13→5 sensors, 83.6→89.7%; S&AB 2024 8→4 sensors, 0.905), so a **6-module recommended pack** (4 principles, all 10 axes) is the starter set. Added `electrical/sensor_matrix.py` (21-sensor market pool, 10 axes, 7 personas, set-cover selector) + gate `tools/verify_sensor_matrix.py`. §0.6 O2, §1, §4, §9, §11 updated. |
| D | 2026-10-15 | **Corrected pack slot placement (Rev C electrical error).** Rev C placed MH‑Z19C and ZE03‑C2H4 in *digital* slots, but the digital bank carries only 3V3 + I²C (no 5 V); both are 5 V modules. Repacked → **A1 MQ‑135 · A2 MQ‑136 · A3 MICS‑6814 · A4 ZE03‑C2H4** (5 V, read via AO) + **D1 SCD40** (3.3 V I²C CO₂), SHT31 stays base `U5`: 5 slot modules + base, 4 principles, all 10 axes, 3 digital slots free. `sensor_matrix.py` now records each module's bank and solves an **exact** minimum set cover under 4+4; gate adds iface↔bank, per-bank cap, pack rail draw (5 V 0.66 A / 3.3 V 0.25 A) and *starter pack ⊇ every persona* checks. Fixed `verify_electrical.py` hardcoded check count. Header revision A→D; §4.4/§4.7/§5.8/§9/§11 updated. |
| E | 2026-10-15 | **Slot count now derived, not asserted; data provenance audited.** Added `electrical/orthogonality.py` (response matrix R[sensor×gas], greedy max-marginal-information, effective rank) + `tools/verify_orthogonality.py`, and extended `sensor_data.py` to a 46-sensor market pool with per-gas response profiles (`basis`: datasheet \| inferred). Audit found `so2`/`cl2` profile keys missing from `GASES` (silently dropped → `ZE03-SO2`/`SO2-A4` invisible); fixed by adding **`so2` as a 17th analyte** and a hard closure guard in `verify_sensor_matrix.py`. Findings (17-gas space): market spans **8.21 independent dimensions** (broad); analog pool 7.93 vs digital 3.43 and **9 of 17 gases are analog-only**; a digital-only bank captures just **50%**. Greedy certificate gives a **5-analog floor** to serve every single-domain use case (4 analog leaves kitchen 93%). **Information-optimal bank = 5 analog + 4 digital** (9 slots, 17/17 MCU-only); analog is the scarce currency, digital is cheap. As-built stays 4+4 (26 mm analog pitch) pending the mechanical change (pitch → ≈ 21 mm or a staggered depth bay + NF2/NF6 re-check). Flagged: the stated ≤ 2.5 W system figure is already exceeded by 4 MOX (3.6 W). Corrected Rev C's over-claim "more slots add redundancy, not information", the initial under-reasoned "3 digital", and stale hard-coded numbers in `slots_report`. §4.4/§4.7 rewritten; header D→E. **Datasheet re-audit:** every sensor row now carries a citable `source` (family- or part-level) and `basis` is the honest taxonomy **table \| curve \| list \| inferred** — only Alphasense EC + MiniPID publish cross-sensitivity *tables*; MOX datasheets (MQ/TGS/MICS) publish gas lists + sensitivity *curves*; NDIR is CO₂-only and Winsen ZE03/ME3 publish target+range only — so verbatim tables exist for a minority, and profiles are labelled accordingly. The verify gate rejects any `UNSOURCED` row. Verified contradictions fixed (MQ-136 is H₂S+CO, not H₂/toluene; MICS-6814 is a 3-element part). Figaro TGS curves and Ion Science MiniPID response factors (TA-02, 10.6 eV) folded in; unbacked profile keys are now machine-flagged `inferred` (guard: subset of profile). Final anchors: broad 8.21, analog 7.93 vs digital 3.43, 50% digital-only; 5A+4D info-optimal (as-built 4A+4D). |
| F | 2026-10-15 | **§4 reads as a product spec.** Added a board diagram and a plain explanation of the 4 analog / 4 digital split (two rows because the two sensor kinds need different electricity). Removed all internal editing instructions from the user-facing text. Engineering note (maintainers only): `sensor_matrix.BANK_CAP` and `verify_sensor_matrix.SLOT_COUNT` now derive from `CONST["A_X"]`/`["D_X"]` instead of a hard-coded 4/4, so the two counts cannot drift; the 8+8 contract (`build_pinmap(8,8)`) remains the growth path. |
| G | 2026-10-15 | **Whole 46-row sensor pool re-derived against datasheets; trade-study numbers re-synced (final).** Every row now carries `basis` + citable `src` with unbacked keys machine-flagged `inferred`. Corrections: MQ-3 replaced unsupported toluene/acetone with datasheet-curve gases (CH₄, CO), methanol flagged inferred; MQ-2 dropped unsupported toluene; MQ-8 added curve alcohol and range corrected to 100–1000 ppm (Winsen ver1.6); MQ-9 H₂ range added; MQ-131 identified as the low-concentration variant (Cl₂/NO₂ cross); MQ-138 added H₂, range 5–500 ppm; MICS-2714 replaced unsupported O₃ with documented H₂ (NO noted); MICS-5524 added documented NH₃; SGP30/40/41 non-reference keys flagged `inferred`. Gates re-run (all PASS) → §4.7 re-synced: broad **8.21**, analog pool **7.93** vs digital 3.43, digital-only **50%**; A-floor and candidate-frontier tables updated. Header F→G. |
| H | 2026-10-15 | **rev-B board model + analog-slot fix.** Added `electrical/board.py`: the fitted parts and the net every pin lands on (**63 parts / 50 nets / 225 connections**), derived from `interface.py` + §5 and machine-checked against the real KiCad symbol library, so the schematic/PCB/BOM generators share one source. **Analog slot reordered to `5V GND AO DO 3V3`** (was `5V 3V3 GND AO DO`) so a 4-pin MQ-type module (VCC,GND,AO,DO) seats straight onto pins 1–4 with power and ground adjacent — the old order put a naive 4-pin plug's GND onto 3V3. Filled three spec/BOM gaps as recorded `DECISIONS`: **U3 CH340C** USB↔UART bridge (blueprint says USB-C carries serial; the BOM had none), **BOOT/RESET/MEASURE buttons**, and **USB-C CC 5.1 kΩ** pulldowns. `bom.csv` passive counts are no longer authoritative — the BOM is regenerated from the schematic. Header G→H. |
| I | 2026-10-16 | **Schematic emitted from the model, and wireless telemetry adopted.** `electrical/gen_schematic.py` builds `smell_monitor_v1_1.kicad_sch` straight from `electrical/board.py`; KiCad **ERC is clean (0 violations)** and a new gate `tools/verify_netlist.py` re-exports the netlist with `kicad-cli` and proves it matches the model pin-for-pin, so schematic and model cannot drift. Board-model fix: **U3 CH340C now runs from 5 V** with V3 decoupled to GND (it is a `power_out`; tying it to +3V3 collided with the AMS1117 VO), and decoupling follows. §7 comms now emit **one JSON record over three transports** — USB serial (wired default), **Wi-Fi 2.4 GHz** (MQTT + HTTP/WebSocket), and **Bluetooth LE** (GATT notify + credential provisioning) — all on the pre-certified ESP32-WROOM-32E radio with **no BOM change**. Wrote the v1.1 firmware (`firmware/esp32/smell_monitor/`, arduino-cli): 4 analog + 4 digital + SHT31 acquisition, three-phase cycle, OLED/LED/buzzer, and all three transports — **compiles clean** (1.73 MB, 54% of a `huge_app` partition), and `tools/verify_firmware_pins.py` pins the firmware pin map to `interface.PINMAP` so it cannot drift. Header H→I. |
| J | 2026-10-17 | **PCB placed, routed and DRC-clean; chamber stack-up fixed; flow order corrected.** Added `electrical/gen_pcb.py` (placement only, `--force`-guarded), `electrical/route_pcb.py` (DSN → FreeRouting `-mp 12` → SES, refuses to save with any unconnected net) and `tools/export_fab.py`, wiring the board to the sky so the routed copper is *reproducible* rather than hand-drawn; `tools/verify_pcb.py` gates it. Netclass track width 0.15 → **0.30 mm** because FreeRouting necks to 75/50 % of nominal, which is what produced the earlier 109 `track_width` DRC errors; DRC is now **0 violations / 0 unconnected**, and `fab/` carries only the layers a board shop can use (16 cosmetic layers and a 5 MB STEP dropped). Mechanical fix: `PCB_Z` was `CAV_Z1 − 1.6` = 58.4 mm, i.e. the board sat in the cavity *ceiling* and physically **blocked all three Ø6 intakes** — it is now `FLOOR − PCB_T`, seated in a shell rebate with its top face flush with the cavity floor, which is the only way §4.6's "baffle 37 mm above board / 29 mm module allowance / 8 mm recess" (12+37=49, 12+29=41, 49−41=8) adds up. Nostril axis 58 → 55 mm so the full bore opens into the 11 mm lane. Flow order corrected: the **digital row is now upstream and the analog/MOX row downstream** — the 4 MOX heaters ≈ 3.6 W, MOX consumes reducing gas and desorbs during purge, so nothing should sit behind that row; this also makes §4.3's "U5 upstream of the MOX array" true (it was not) and puts the small cards ahead of the wide ones. Added a **reference port** in the baffle over U5 (`SHT_*`) — the soldered SHT31 was otherwise sealed behind a solid plate. Filter moved from a floating 90 × 12 slab to a **series element spanning the full 106 × 11 mm lane** behind the nostrils (a bypassable filter is not a filter); its area spec forces a pleated pack. Documented the module envelope + insertion orientation in §4.6. Header I→J. |
| K | 2026-10-17 | **Module envelope audited against real breakouts; §4.5/§4.6 rewritten.** Added `mechanical/modules.py` (per-module form, outline, connector class, sensing-element geometry — each with a source) and gate `tools/verify_module_fit.py` (reports by default so the suite stays green; `--strict` is what CI runs once the sample is measured). Findings that remove hidden assumptions: the MQ-135 is sold on 32×20, 32×22, 36×24 *or* 40×21 mm boards, so "worst case 22 × 35 × 23" was a vendor lottery presented as a datasheet fact; MQ breakouts ship as `VCC GND AO DO` *and* `VCC GND DO AO`, so §4.2's pin order is a convention, not a standard, and a swapped module puts its 0–5 V AO on an unprotected 3.3 V GPIO (`DO0..DO3`); the ZE03 is a Ø23.5 × 24.5 mm can, not a card; MH-Z19C-PC is 38.8 × 19.7 × 8.6 mm with a 1.5 mm JST-ZH connector; MICS-6814, SCD40/41, SGP4x and BME688 are SMD parts (MICS-6814 has three analog outputs against one AO per slot). §4.6 corrections: the "connector edge toward the front" insertion rule sent a 35 mm analog card through the rear wall, so the rule is now "card body into the free depth" (26/42/32 mm per lane), and the analog pitch derivation is corrected to card 1.6 + Ø19×23 can = 24.6 mm across in a 26 mm pitch. `tools/verify_pcb.py` placement checks are now measured from the board's own outline, so moving the board in the KiCad sheet (centring it) is safe — proven by re-running the gate on a board translated by (+60, +25) mm. Header J→K. |
| L | 2026-10-18 | **The module standard is defined, and the slot stops being two banks.** Added `docs/module-standard.md` (OpenSmell Module Standard v1, OSM-1) + `mechanical/standard.py` (the same rules as data) and extended `tools/verify_module_fit.py` to check the chamber, the socket contract and the module database against it and print the remaining gap as OPEN. **Decision:** one slot design repeated — every slot carries a keyed 2.54 mm 1×6 gas-cell socket (**`+5V GND AO DO 3V3 ID`**, the `ID` pin being a 1-Wire EEPROM carrying pinout + calibration + exposure history) *and* a 3.3 V Qwiic/STEMMA QT port (adopting the mainstream I²C standard rather than inventing one; Grove/Gravity via adapter), over its own 20 × 20 mm window; 8 slots as two rows of four at a uniform 24 mm pitch. Cartridges mount **flat** (right-angle header in a vertical socket, sensing face up, element centred in a 20 × 20 mm zone 16 mm downstream of the connector face) which points a MOX can's end-face inlet at its window and turns the standing pose's 40–48 mm height (against 37 mm available) into ≈25 mm. Uniformity costs no size: 4 × 24 = 96 mm fits the existing 106 mm cavity, so this is the same 122 mm shell built from one repeat unit. Wetted-material bans (no silicone anywhere in the gas path — silicone vapour permanently poisons SnO₂), a class-wise calibration blob, a module-maker conformance checklist and the cost (<$0.30 base overhead per slot) are recorded. Added §15 (design decision record: each invariant, the alternative considered, why it was rejected, and the evidence status of every claim). **Corrected:** no carbon in series with the sample (it strips the analyte we are measuring; carbon belongs on a reference-air line, §6.3/§13 — a risk row was added for silicone poisoning), and this document's own header revision brought back in step with the table (J→L). **Drawing set in the same revision:** every part sheet is now dimensioned against the real solid — the builder measures the projection's (u, v) axis vectors per view (`TechDraw.projectEx` aimed at a 100 mm reference line on each global axis) and stores them as `axes`, so the sheet generator inverts the projection exactly and a dimension cannot be attached to a guessed coordinate; OS-000 gained an **exploded assembly view** (parts offset along the assembly axis, offsets stored with the geometry) with item balloons keyed to the BOM; `tools/verify_cad.py` now rejects a view with no measured axes, checks the dimension *values* against `constants.py`, requires a minimum dimension count per part sheet, and fails any text that would print past the border. Header K→L. |

| M | 2026-10-21 | **The enclosure is rebuilt as the simple thing it should have been, and the drawings follow.** The shell was a sealed solid: 30 mm of material over the chamber, no lid, no service opening, so it could not be printed, assembled or serviced. Measured volume 714 427 mm³ against a 1 251 720 mm³ envelope, `isInside((61, 57, 75))` true. The cause was architectural, not cosmetic: a baffle plate 37 mm above the board, eight wells, a PTFE liner and a vertical front panel that was modelled as a horizontal chamber floor. **Replaced** by an open tray (122 × 114 × 43, 3 mm walls, 3 mm floor) + a flat 6 mm lid on four M3 screws into heat-set inserts; the board sits on four Ø6 standoffs with its top face as the chamber floor at z = 8.6; modules plug straight into the eight 1×6 sockets; a 110 × 4 × 23 filter pad drops into a front drawer and is held down by the lid; a Ø40 fan mounts outside a 4 mm rear plate through a Ø38 bore with blind screws. **Retired:** the baffle, the plenum, the 11 mm lane, the 20 × 20 mm windows, the PTFE insert, the reference port, the front-panel board and the OLED window. **Kept:** the flat cartridge pose, the two rows (digital upstream, MOX downstream), the as-built header positions (analog y = 75, digital y = 33, 26/21 mm pitch), the wetted-material bans and the OSM-1 socket contract. Slot pitch is now explicitly a base *parameter* (`standard.SLOTS.pitch_min` = 22, `max_width` = 20, `reach` = 32), not a module rule. The drawing set is rebuilt from the new solid: OS-000 exploded + section B-B through the whole stack, OS-001 tray (front + section A-A + iso), OS-002 lid (1:1 plan + 1.5:1 counterbore section + iso); sections are hatched from real cut faces and every dimension is on a measured feature. Gates: `verify_cad` now checks section extents and the lid hole pattern against `constants.py`; `verify_module_fit`, `verify_electrical` and `interface.py` no longer reference the retired constants. Header L→M. |

**Open items (need measurement or decision):**
- Electrical: **done** — board model (`electrical/board.py`) → generated ERC-clean
  schematic → placed + routed PCB (847 segments / 102 vias) → **DRC clean**
  (0 violations / 0 unconnected / 0 footprint errors) → fab package exported.
  `tools/verify_pcb.py` now holds that line. The v0 schematic is retained only as
  a pin-name source for `board.py`.
- **Module standard: the decision is made, the board is not yet built to it (top
  item).** §4.9 fixes the socket — flat cartridges, 8 slots, keyed 1×6 gas cell
  with an `ID` pin, a Qwiic port at every slot. Target revision L is therefore a
  re-derive, not a decision: electrical (6-pin socket, Qwiic per slot, **10 kΩ in
  series with every `DO`**, the 1-Wire net, the second ADS1115 for 8 analog
  channels) and then a re-route. `tools/verify_module_fit.py` prints every
  remaining gap as OPEN and exits 0; `--strict` is what CI runs once revision L
  is built. The slot pitch is a base parameter (26 / 21 mm as built), not a
  module rule — a cartridge only has to fit the socket, be ≤ 20 mm wide and stop
  within 32 mm of its pin line.
- **Board re-lay to the enclosure (next mechanical/electrical task).** The
  enclosure is the contract now (§6.1). Two changes: four r = 5 mm corner notches
  for the lid bosses, and `J1` USB-C moved to the front edge so its face lands
  behind the Ø12 bulkhead hole. `SW1..SW3`, `BZ1` and `LED1` stay on the board
  inside the chamber (headless v1, §6.1); `U6` (OLED) is not fitted.
- **Carrier boards** — MICS-6814, SCD40/41, SGP4x and BME688 are SMD parts, and
  MICS-6814 has three analog outputs against one AO per slot. One shared
  OpenSmell carrier accepts a TO-5 can, a Ø23.5 Winsen can or a bare SMD part and
  presents the standard socket, pinout and sensor zone (§4).
- Mechanical: OS-003 (PCB floor plan) and OS-004 (pneumatic schematic) sheets (§12).
- **Module mounting key** — §4.9 defines it (pin-1 chamfer plus a polarising slot
  in the socket wall) but no footprint carries it yet: revision L adds it to the
  socket and to the cartridge outline.
- **Closed this revision — the sealed shell.** The shell was a solid block with
  30 mm of material over the chamber: not printable, not assemblable, not
  serviceable. It is now an open tray (122 × 114 × 43) with a flat 6 mm screwed lid,
  measured from the rebuilt STEP, and `tools/verify_cad.py` checks the section
  extents and the lid hole pattern against `constants.py` so the same defect
  cannot return silently.
- **Closed this revision — the board/enclosure orientation mismatch.** The board
  is a horizontal chamber floor by design, and the enclosure now says so: USB-C
  reaches the front bulkhead hole, the buttons and buzzer are inside and
  reachable with the lid off, and no panel opening is drawn that the board cannot
  meet. Headless v1 removes the front-panel board entirely.
- **Closed this revision — service access (success criterion U1).** Four M3
  screws, lid off, modules lift straight out of their headers. No baffle to
  remove, no tool beyond a 2.5 mm hex key, well inside 60 s.
- **Closed this revision — the PTFE insert and the reference pocket.** With no
  plate there is no 35 mm pocket over U5 and no liner to fit: U5 sits on the
  board in the chamber air, and the wetted area is the tray walls, the lid and
  the board, all sealed (§6.3). A PTFE liner sheet stays an optional upgrade.
- Pneumatic: NF1 filter ΔP bench + media vendor (a flat 110 × 23 face is
  25 cm²; a 4 mm non-woven at ≈0.6 m/s drops only a few Pa, so the pleated-pack
  requirement is retired), fan P/N.
- CFD: one `simpleFoam` pass at 15 and 150 L/min (§8.3) on the current geometry.
  Three numbers it must produce: (1) the exchange time over each row, which sets
  the 34.4 mm clear height and the 42 mm row spacing; (2) the cascade between the
  upstream and downstream rows (how much of the sample the first row removes
  before the second sees it); (3) whether a filled slot's cartridge perturbs its
  neighbours' exchange.
- Mass: MQ module mass from a physical sample.

---

## 15. Design Decision Record

Why each hard-to-vary choice is what it is, the alternative that was considered,
and why it was rejected. **Parameters** are deliberately not recorded here — slot
pitch, window size, slot count, cartridge envelope and cycle timings are set by
`mechanical/constants.py` and the calculations in §3–§6, and change without a
revision. **Invariants** (the socket contract, the physics layer, identity on the
module, the record shape) change only through §14.

| # | Decision | Alternative considered | Rejected because |
|---|----------|------------------------|------------------|
| 1 | The platform's job is the **controlled sample**, not the sensor list | support every module on the market | There is one socket (2.54 mm) and a size zoo: the same MQ-135 is sold as 32×20, 32×22, 36×24 and 40×21 mm boards in two different pin orders (`mechanical/modules.py`). |
| 2 | **8 identical slots**, two rows of four | a row per electrical kind; a single row of eight | One row of eight needs 8 × 24 = 192 mm of the 106 mm cavity. Splitting by kind makes the bank a user decision and retires the analog advantage: 9 of 17 analytes are analog-only, the analog pool spans 7.93 independent dimensions against digital's 3.43, and a digital-only bank captures 50 % (`tools/verify_orthogonality.py`). |
| 3 | **Both interfaces at every slot** (5 V gas cell + 3.3 V I²C) | one bank per interface | A wrong-bank insertion becomes an unsupported failure mode, and a 5 V I²C sensor has nowhere to go. Both connectors together cost ≈ $0.30 per slot. |
| 4 | **Qwiic / STEMMA QT** for the I²C side | design a connector; Grove-first | Qwiic is what the sensor vendors ship. Grove and Gravity carry the same four signals and bridge with an adapter cable, so nothing is excluded. |
| 5 | Keyed **1×6** gas cell (`+5V GND AO DO 3V3 ID`) | the 4-pin vendor order; an 8-pin universal header | A common MQ breakout (`VCC GND DO AO`) puts a 0–5 V output on a 3.3 V GPIO; an 8-pin header is wider than the slot it serves and still has no identity pin. |
| 6 | **Identity EEPROM on the cartridge** | identity on the base; an ID resistor | A resistor identifies a part number, not a specimen. Per-cell calibration and exposure hours are what let drift and poisoning be handled in software (§4.9). |
| 7 | **Flat cartridges**, right-angle header in a vertical socket | standing cards; cable everything | A MOX can's inlet is its end face, so a standing card aims it at its neighbour; and a standing 32–40 mm card needs 40.5–48.5 mm where 37 mm exists (§4.5). Cable-only would need an adapter for every bare MQ card. |
| 8 | **Board is the chamber floor**, with a PTFE insert over its top face | board outside the chamber; bare FR4 wetted | FR4, solder mask and component plastics sorb and re-release VOC — that is carryover — and the 0603 dividers run ≈ 10 K above ambient so their tempco reaches the readings (§6.3). |
| 9 | Filter is a **full-lane series element, no carbon** | an inline filter; a carbon scrubber | A bypassable filter is not a filter (§3.6), and carbon removes the analyte along with the interferent (§6.3). |
| 10 | **MOX row last** in the flow | MOX first, at the freshest gas | Four MOX heaters ≈ 3.6 W are the largest heat load, MOX is a net sink for reducing gases, and it desorbs during purge (§4). |
| 11 | The chamber is a **cascade, and every record says where the slot is** | treat the slots as independent | Gas independence degrades with upstream uptake. Reporting slot index and flow position lets the host model it (§4.9). |
| 12 | **Driven three-phase cycle** | continuous streaming | Passive sampling injects uncontrolled ambient variability; comparability is the product (§2). |
| 13 | Hand calculation plus gates first, **CFD once** | CFD before freezing the interface | The interface is what blocks hardware; the CFD tunes parameters, not invariants (§8.3). |
| 14 | **No pH on the base** — pH is a different instrument, not another slot | a pH slot in the array | A glass electrode is a wet-storage consumable (it must sit in KCl and be re-calibrated), its output is ~−59 mV/pH at hundreds of MΩ, and it measures an aqueous phase, while every other slot measures headspace gas. A pH probe belongs on an external port or on a cartridge that brings its own buffer and storage cap; putting it in the gas chamber would dry it out and poison the array's reference. |
| 15 | **No battery on the base** — USB-C 5 V in, plus a 2-pin 5 V aux header | LiPo + charger + fuel gauge | A cell adds cost, a lithium shipping/compliance burden and a heat source next to four MOX heaters, and it makes the enclosure a battery compartment. A $10 power bank on the aux header gives hours of runtime with zero design, zero certification and zero thermal risk. |
| 16 | **UI on a small front-panel board**, not on the chamber-floor board | OLED + buttons on the main board | The main board's top face *is* the chamber floor: anything on it is either in the sample air (sorbing, heating, corroding) or behind a wall. The front face is the only surface a display can face the user from, and one Qwiic cable is cheaper than a windowed lid plus a re-laid main board. |
| 17 | **Reference sensor is a socketed module** (Qwiic), not a soldered part | SHT31 soldered to the main board | A soldered SHT31 makes the whole board a consumable when the sensor drifts, and it cannot be swapped for a calibrated one. A Qwiic reference module costs ~$4 and is field-replaceable, which is what "serviceable" has to mean for the one part that sees the air directly. |
| 18 | **Acrylic or PU conformal coat**, never silicone | silicone coat; parylene | Silicone vapour poisons SnO₂ permanently (§13), so a silicone-coated board is a slow array killer. Acrylic/PU protects the copper and the dividers at ~$0 and can be masked off the sensor windows and connectors; parylene is better but needs a vacuum house and cannot be touched up. |
| 19 | **Open tray, board on four standoffs, flat screwed lid** — no baffle, no plenum, no flow lane, no well, no window | the plate-with-eight-openings + machined PTFE insert | It doubles the part count and the envelope (90 mm tall, 1.25 L), needs a machined PTFE insert to stay inert, and forces every cartridge into an 8 mm recess so its sensing face sits *below* the plate. The plate bought nothing a plugged-in cartridge does not already have: unobstructed air over its sensing face. The tray prints on any FDM machine, needs no liner, and comes apart with four screws. |
| 20 | **Fan outside the rear face**, on a 4 mm printed plate | fan inside the chamber on the rear wall | The fan's motor and plastics would sit in the sample, adding heat and sorption right where the gas leaves the array, and its 40 × 40 × 10 body would cut through the board's rear edge. Outside, it is downstream of everything, keeps its heat out of the box, and is serviceable without opening the lid. Its four screws are blind, so no hole enters the chamber. |
| 21 | **Headless v1** — no display window, no panel buttons, no buzzer hole; UI is Osmograph | a small front-panel board (OLED + 3 buttons + Qwiic link) | A second board, a ribbon and a sealed feedthrough cost more than they return, and they create the whole class of defects where the panel and the chamber disagree about where the board is. The buttons, LED and buzzer stay on the board inside, reachable with the lid off; day-to-day use is a phone. |

### 15.1 Evidence status

Proven means a gate re-derives it and fails the build if it stops being true.
A gate is not a measurement.

| Claim | Checked by | Status |
|-------|-----------|--------|
| Netlist ≡ schematic ≡ firmware pin map | `tools/verify_netlist.py` (ERC 0/0/0), `tools/verify_firmware_pins.py` | proven, machine-checked |
| Routed board on the chamber contract, DRC-clean | `tools/verify_pcb.py` | proven, machine-checked |
| Chamber, shell, baffle and drawings derive from one constants file | `tools/verify_cad.py` | proven, machine-checked |
| Slot count is information-optimal for the modelled pool | `tools/verify_orthogonality.py` | proven within the model's sourced data |
| Real modules fit the chamber | `tools/verify_module_fit.py` | partly — pose settled by §4.9; three caliper numbers remain a module maker's conformance check |
| Window exchange time and row-to-row cascade | hand calculation (τ = V/Q ≈ 2.0 s, 20 s purge ≈ 10 exchanges) | calculated, not simulated — §8.3 |
| System ΔP ≈ 1.9 Pa, fan point 35–60 L/min at 20–30 % PWM | hand calculation against datasheet anchors | calculated — NF1 bench not run |
| Purge completeness ≥ 99 %, carryover ≤ 5 % | NF4 / §8.2 acceptance tests | not tested — no hardware built |
| Absolute concentration accuracy | — | not claimed (§0.5) |

---

*Changes to a locked section require a revision bump and a row in the revision
table (§14).*

