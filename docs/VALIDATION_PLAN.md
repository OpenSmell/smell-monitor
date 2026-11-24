# Flow Acceptance Test

**Document:** OSM-VP-001
**Revision:** B
**Date:** 2026-11-22
**Product:** Smell Monitor v1.1
**Purpose:** Production acceptance of `t63`/`t90` exchange times and purge.

The CFD case and its numerical acceptance check are in `cfd/RESULTS.md`. This
document is the hardware acceptance specification for a built unit; its
criteria in §3 are the release gate.

The chamber has **eight uniform OSM-1 slots** on two inward-facing side-wall
rows: left wall slots 1–4 (J2–J5) and right wall slots 5–8 (J6–J9), both on
24 mm Y-pitch stations with 13 mm of wall clearance behind each upright card.
Every slot has the same gas-cell socket and Qwiic port, and every header and pin
is silkscreened. The three centred nostrils feed the channel between the rows
and the rear fan pulls the sample straight out. The inlet filter is a **thin
woven PTFE mesh** in the front drawer; verify it is fitted and clean before
testing (a 4 mm sintered panel would cost ≈ 3.8 kPa at 15 L/min against ≈ 50 Pa
of fan head and must not be used).

---

## 1. Required Equipment

| Item | Specification | Purpose |
|------|--------------|---------|
| Flow bench / mass flow controller | 0–100 L/min, ±1% accuracy | Set and verify 15 L/min purge flow |
| Tracer gas source | 100 ppm CO₂ (or similar) in air, mass-flow controlled | Step-change tracer input at t=0 |
| Fast-response gas sensor | CO₂ NDIR or PID, T90 < 1 s, sampled at slot plane | Measure breakthrough curve at each slot |
| SHT31 reference (onboard) | Temperature/humidity at 1 Hz | Log ambient conditions during test |
| Anemometer | Hot-wire or vane, 0–5 m/s | Verify face velocity at nostrils |
| Data logger | ≥ 10 Hz sampling, synchronized to flow bench | Record sensor response vs time |
| Host running Osmograph | USB serial at 115200 baud | Start the 10/10/20 s cycle and capture `.osmell` records from the two ADS1115s through the 8-channel mux |
| PTFE tubing | 6 mm ID, minimal dead volume | Connect tracer source to nostrils |
| Clean air source | Zero-grade air, < 1 ppm VOC | Baseline and purge gas |

---

## 2. Test Procedure

### 2.1 Pre-test checks
1. Verify all 8 uniform slots are populated with identical reference sensors (e.g., MQ-135).
2. Verify the thin woven PTFE mesh filter is fitted, clean and unobstructed.
3. Verify fan spins freely at 100% PWM.
4. Verify flow bench reads 15 L/min at the chamber inlet (anemometer cross-check at nostril face).
5. Record ambient temperature and humidity from the onboard SHT31.
6. Verify baseline: all sensors stable in clean air for ≥ 10 min.
7. In Osmograph, confirm eight slot channels (two ADS1115s) and live SHT31 T/RH.

### 2.2 Tracer breakthrough test (primary)

**Objective:** Measure `t63` and `t90` at each of the eight slots.

1. Set flow bench to 15 L/min (purge flow).
2. Allow 2 min for flow stabilization.
3. Confirm sensor baselines are stable (drift < 1% over 1 min).
4. At t = 0, step tracer gas from 0 → 100 ppm CO₂ at the nostril inlets.
5. Sample each sensor at ≥ 10 Hz for 60 s.
6. Record time when each sensor reaches 63% and 90% of its steady-state reading.
7. Repeat for all 8 slots.
8. Repeat 3×; report mean and standard deviation.

### 2.3 Purge completeness test

**Objective:** Verify the chamber clears after odor exposure (smell memory check).

1. Expose chamber to strong odor (e.g., 100 ppm isopropanol vapor) for 30 s.
2. Return to clean air at 15 L/min.
3. Measure time for all sensors to return to ≥ 95% of baseline.
4. Pass criterion: ≤ 40 s (one full cycle).

### 2.4 Wall-to-wall uniformity test

**Objective:** Measure the delay between the left inward-facing row (slots 1–4)
and the right inward-facing row (slots 5–8).

1. Populate the 4 left-wall slots (1–4, J2–J5) with responsive sensors.
2. Populate the 4 right-wall slots (5–8, J6–J9) with responsive sensors.
3. Step tracer at t = 0 through the centred nostrils.
4. Record `t63` for the two walls separately.
5. Report the wall-to-wall delta. The rows are identical electrically; only
   their position in the channel differs.

---

## 3. Pass/Fail Criteria

| Criterion | Threshold | Notes |
|-----------|-----------|-------|
| `t63` per slot | ≤ 4 s | Empty-chamber plug-flow reference V/Q ≈ 2.28 s |
| `t90` per slot | ≤ 22 s | Conservative: ~11× V/Q to allow for mixing |
| Wall-to-wall delta | ≤ 5 s | The two facing rows should fill together |
| Purge completeness | ≥ 95% baseline recovery ≤ 40 s | One full cycle must clear odor |
| Face velocity at nostril | ≥ 2 m/s at 15 L/min | Confirms flow is entering, not bypassing |
| Flow uniformity | All 8 slots within ±20% of mean `t63` | No dead zones or short-circuits |

---

## 4. Acceptance

**Pass:** All criteria in Section 3 met for all 8 slots across 3 repeat runs.

**Fail:** Any criterion missed → investigate blockage, leak, or fan speed; redesign if needed.

---

## 5. Records

Save all raw data (CSV: time, slot1…slot8, flow, temp, RH) to `docs/validation/`.

---

*Acceptance is by the criteria in §3; records are stored under `docs/validation/`.*
