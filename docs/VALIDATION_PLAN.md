# Physical Flow Bench Validation Plan

**Document:** OSM-VP-001
**Revision:** A
**Product:** Smell Monitor v1.1
**Purpose:** Validate `t63`/`t90` exchange times physically after hardware fabrication.

CFD proves air moves through the chamber (max inlet velocity ≈ 2 m/s at 15 L/min, continuity residual ≈ 10⁻⁹), but quantitative exchange times require physical measurement. CFD t63/t90 at high Courant number is a numerical-diffusion artifact; this plan is the source of truth.

---\n\n## 1. Required Equipment\n\n| Item | Specification | Purpose |\n|------|--------------|---------|\n| Flow bench / mass flow controller | 0–100 L/min, ±1% accuracy | Set and verify 15 L/min purge flow |
| Tracer gas source | 100 ppm CO₂ (or similar) in air, mass-flow controlled | Step-change tracer input at t=0 |
| Fast-response gas sensor | CO₂ NDIR or PID, T90 < 1 s, sampled at slot plane | Measure breakthrough curve at each sensor |
| SHT31 reference (onboard) | Temperature/humidity at 1 Hz | Log ambient conditions during test |
| Anemometer | Hot-wire or vane, 0–5 m/s | Verify face velocity at nostrils |
| Data logger | ≥ 10 Hz sampling, synchronized to flow bench | Record sensor response vs time |
| PTFE tubing | 6 mm ID, minimal dead volume | Connect tracer source to nostrils |
| Clean air source | Zero-grade air, < 1 ppm VOC | Baseline and purge gas\n\n---\n\n## 2. Test Procedure\n\n### 2.1 Pre-test checks\n1. Verify all 8 slots populated with identical reference sensors (e.g., MQ-135).\n2. Verify fan spins freely at 100% PWM.\n3. Verify flow bench reads 15 L/min at the chamber inlet (anemometer cross-check at nostril face).\n4. Record ambient temperature and humidity from onboard SHT31.\n5. Verify baseline: all sensors stable in clean air for ≥ 10 min.\n\n### 2.2 Tracer breakthrough test (primary)\n\n**Objective:** Measure `t63` and `t90` at each sensor slot.\n\n1. Set flow bench to 15 L/min (purge flow).\n2. Allow 2 min for flow stabilization.\n3. Confirm sensor baselines are stable (drift < 1% over 1 min).\n4. At t = 0, step tracer gas from 0 → 100 ppm CO₂ at the nostril inlets.\n5. Sample each sensor at ≥ 10 Hz for 60 s.\n6. Record time when each sensor reaches 63% and 90% of its steady-state reading.\n7. Repeat for all 8 slots.\n8. Repeat 3×; report mean and standard deviation.\n\n### 2.3 Purge completeness test\n\n**Objective:** Verify the chamber clears after odor exposure (smell memory check).\n\n1. Expose chamber to strong odor (e.g., 100 ppm isopropanol vapor) for 30 s.\n2. Return to clean air at 15 L/min.\n3. Measure time for all sensors to return to ≥ 95% of baseline.\n4. Pass criterion: ≤ 40 s (one full cycle).\n\n### 2.4 Row-to-row cascade test\n\n**Objective:** Measure delay between upstream (digital) and downstream (analog/MOX) rows.\n\n1. Populate slots 1–4 (digital row) with responsive sensors.\n2. Populate slots 5–8 (analog row) with responsive sensors.\n3. Step tracer at t = 0.\n4. Record `t63` for row 1 and row 2 separately.\n5. Report row-to-row delta.\n\n---\n\n## 3. Pass/Fail Criteria\n\n| Criterion | Threshold | Notes |\n|-----------|-----------|-------|\n| `t63` per slot | ≤ 3 s | Empty-chamber plug-flow reference V/Q ≈ 2.0 s |
| `t90` per slot | ≤ 22 s | Conservative: ~11× V/Q to allow for mixing |
| Row-to-row delta | ≤ 5 s | Downstream row should not lag excessively |
| Purge completeness | ≥ 95% baseline recovery ≤ 40 s | One full cycle must clear odor |
| Face velocity at nostril | ≥ 2 m/s at 15 L/min | Confirms flow is entering, not bypassing |
| Flow uniformity | All slots within ±20% of mean `t63` | No dead zones or short-circuits\n\n---\n\n## 4. Acceptance\n\n**Pass:** All criteria in Section 3 met for all 8 slots across 3 repeat runs.\n\n**Fail:** Any criterion missed → investigate blockage, leak, or fan speed; redesign if needed.\n\n---\n\n## 5. Records\n\nSave all raw data (CSV: time, slot1…slot8, flow, temp, RH) to `docs/validation/`.\n\n---\n\n*This plan is executed after hardware fabrication. CFD results are not substituted for physical measurement.*\n