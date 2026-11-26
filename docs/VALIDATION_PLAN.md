# Acceptance Test Plan — Flow, Interface and Data

**Document:** OSM-VP-001
**Revision:** D
**Date:** 2026-11-26
**Product:** Smell Monitor v1.1 (one SKU)
**Purpose:** Production acceptance of tracer exchange, purge, display, controls,
sealing, OTA rollback and data replay on a built unit.

The CFD case and its numerical stability check are in `cfd/RESULTS.md`; the
interpretation notes are in `docs/CFD_NOTES.md`. This document is the hardware
acceptance specification for a built unit; its criteria in §3 are the release
gate.

## Numerical results

The `side-wall-v2-linux` solve is numerically stable (81,432 cells, Courant
0.783, continuity -5.65e-08) and gives a wall-to-wall t63 delta of 0.23 s. It
also reports uniformity FAIL and 3/8 slots at or below the 4 s t63 target, with
t90 recorded at A0, A3 and D3. Physical tracer and purge acceptance in §2.2–§2.4
is the release gate. Nostril geometry is unchanged after CFD review.

The chamber has **eight uniform OSM-1 slots** on two inward-facing side-wall
rows: left wall slots 1–4 (J2–J5) and right wall slots 5–8 (J6–J9), both on
24 mm Y-pitch stations with 13 mm of wall clearance behind each upright card.
Every slot has the same gas-cell socket and Qwiic port, and every header and pin
is silkscreened. The three centred nostrils feed the channel between the rows
and the rear fan pulls the sample straight out. The inlet filter is a **thin
woven PTFE mesh** in the front drawer; verify it is fitted and clean before
testing. The gas path is inert-gas only: PTFE/PFA/FEP/PVDF, glass or stainless
in the wetted path, with **acrylic or polyurethane conformal coat only — never
silicone**.

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
| Printed legibility target | 16-character line sample at 0.5 m | Display readability check |
| Lux meter | 0–1000 lx | Display readability under test lighting |
| Logic analyser or oscilloscope | ≥ 1 MHz, two channels | Button debounce timing |
| Seal check kit | Indicator paper or pressure-decay rig | Front-bezel window, gasket and harness grommet sealing |
| OTA host and HTTP server | Manifest with SHA-256 digest and public-key signature | OTA, version and rollback testing |
| Power-interrupt rig | USB-C breakout with switch, ≥ 100 cycles | Power-fail flush and replay testing |
| NTP reference | Reachable time source | Wall-clock timestamp verification |

---

## 2. Test Procedure

### 2.1 Pre-test checks
1. Verify all 8 uniform slots are populated with identical reference sensors (e.g., MQ-135).
2. Verify the thin woven PTFE mesh filter is fitted, clean and unobstructed.
3. Verify fan spins freely at 100% PWM.
4. Verify flow bench reads 15 L/min at the chamber inlet (anemometer cross-check at nostril face).
5. Record ambient temperature and humidity from the onboard SHT31.
6. Verify baseline: all sensors stable in clean air for ≥ 10 min.
7. In Osmograph, confirm eight slot channels (two ADS1115s), live SHT31 T/RH and
   the sealed front-panel SSD1306 at master I²C `0x3C`, with its 27 × 13 mm
   window and single sealed Ø6 harness grommet at (82,45).
8. Verify the gas path contains inert materials only and that conformal coat is
   acrylic or polyurethane, never silicone.
9. Confirm all four buttons are reachable with the lid closed at MEASURE/OK
   (88,49), MENU/BACK (100,49), BOOT (88,39) and RESET (100,39), and that the
   lid is plain with four M3 screws and no wires or holes.

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

### 2.5 Display readability test

**Objective:** Verify the sealed front-panel OLED is readable during normal use.

1. Power the unit and confirm the status screen on the SSD1306 at `0x3C`.
2. Press MENU/BACK once to step through status, values and any configured user
   text screen; confirm each screen renders four complete 16-character lines.
3. View the front-panel display from 0.5 m at 200 lx and 500 lx; read the
   printed legibility target through the bezel window.
4. Confirm no window glare or gasket shadow obscures any of the four rows.
5. Confirm the fault banner and the derived-values strip appear when a fault or
   a versioned profile is present.

### 2.6 Button debounce test

**Objective:** Verify MEASURE/OK and MENU/BACK produce one action per press.

1. Connect the logic analyser to the two button nets.
2. Press and release each button 50 times with normal finger pressure.
3. Confirm one edge per press after the 30 ms debounce window and no extra
   short-press action from contact bounce.
4. Confirm MEASURE/OK starts a cycle, acknowledges a fault and confirms a
   pending factory reset; confirm MENU/BACK advances the screen, opens the
   setup AP on a >2 s hold and arms factory reset on a >5 s hold.
5. Confirm BOOT/RESET remain reachable for serial recovery with the lid closed
   and the front bezel undisturbed.

### 2.7 Bezel and grommet sealing test

**Objective:** Verify the front-bezel window, gasket and single harness grommet
keep the UI outside the sample path.

1. Inspect the fixed front wall: the shallow bezel window and gasket and the
   single sealed Ø6 grommet at (82,45) sit outside the wetted chamber; no display
   opening penetrates the sample path. Confirm the lid is plain with four M3
   screws and no wires or holes.
2. Run the indicator-paper or pressure-decay check with the lid closed and four
   M3 screws torqued to the assembly specification.
3. Expose the outside of the window and grommet to a clean-air tracer challenge;
   confirm no tracer reaches the chamber through the bezel or grommet.
4. Remove and replace the lid once; confirm the lid seal is restored without
   disconnecting the display or button harnesses.

### 2.8 OTA rollback test

**Objective:** Verify manifest checks, monotonic versioning and rollback-safe
activation.

1. Host prepares a manifest carrying the SHA-256 digest and a signature made
   with its private key; the signing key stays on the host. Issue
   `ota <url> <sha256>` and confirm the device verifies the signature with its
   embedded public key before fetching image bytes.
2. Install a valid newer version; confirm device-side signature verification,
   digest match, version-monotonic gate, image verification, activation and a
   successful boot confirmation.
3. Present a manifest with an invalid signature and confirm the device rejects
   it before fetching any image bytes.
4. Install a manifest with a mismatched digest and confirm rejection before
   image activation.
5. Install a manifest whose version is not greater than the running firmware
   and confirm rejection.
6. Interrupt or withhold boot confirmation for three boots; confirm the
   previous partition is selected and the device boots into the old firmware.
7. Confirm USB-C serial recovery flashing still works after rollback.
8. Confirm the device reports manifest signature verification, SHA-256 state,
   version gate and rollback state through `ota status`.

### 2.9 Data-loss and replay test

**Objective:** Verify records survive power loss and can be replayed by sequence
ID.

1. Enable Wi-Fi and MQTT explicitly; confirm radios remain off until enabled.
2. Set the NTP reference and confirm `wall_clock` timestamps on new records.
3. Generate at least 32 records and note the sequence IDs. The NVS ring holds
   the most recent 32 records.
4. Cut USB-C power during a cycle, restore power and confirm every generated
   record in that window was persisted before the cut (power-fail flush).
5. Query `HTTP /data` and `HTTP /data?since=<seq>`; confirm the replay returns
   exactly the retained records after `<seq>` in sequence order, oldest first.
6. Confirm retained MQTT status and LWT are published on connect and on
   unexpected disconnect.
7. Confirm realtime telemetry continues on the enabled transports during the
   next cycle.

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
| Display readability | Four 16-character rows legible at 0.5 m, 200–500 lx | Acrylic window and gasket create no obstruction |
| Button debounce | One action per press over 50 presses per button | 30 ms debounce; long-press actions distinct |
| Bezel/grommet sealing | No tracer path through the front bezel or grommet after lid reseat | UI remains outside the sample path; lid carries no wires or holes |
| OTA activation | Device verifies host-signed manifest with embedded public key, SHA-256 digest match and strictly greater version | No activation on failed checks |
| OTA rollback | Previous image boots within three unconfirmed boots | USB-C serial recovery remains available |
| Power-fail flush | Every retained record present after restore | Each record persisted at generation |
| Sequence replay | `/data?since=<seq>` returns only later retained records from the 32-record NVS buffer | Sequence IDs ordered and gap-checked |
| MQTT state | Retained status and LWT present | Radios off until user enables them |
| Timestamps | NTP `wall_clock` on new records | Realtime telemetry on enabled transports |

---

## 4. Acceptance

**Pass:** All criteria in Section 3 met for all 8 slots across 3 repeat runs.

**Fail:** Any criterion missed → investigate blockage, leak, fan speed, sealing,
update path or telemetry path as indicated by the failed test.

---

## 5. Records

Save all raw data (CSV: time, slot1…slot8, flow, temp, RH; display and button
logs; OTA manifests and status; replay captures) to `docs/validation/`.

---

*Acceptance is by the criteria in §3; records are stored under `docs/validation/`.*
