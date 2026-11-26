#!/usr/bin/env python3
"""HIL simulator for OpenSmell v1.1.

Pumps exact `.osmell` JSON records (one per line) at an accelerated
40-second cycle rate and injects anomalies via CLI flags to verify
Osmograph's QC pipeline in real time.

Each cycle: intake (10s) -> hold (10s) -> purge (20s) -> report.
With --accel 10 (default) a full cycle takes 4s wall-clock.

The simulator emits records for every phase so all QC rules can fire:
baseline_drift (hold), adc_saturation (any phase, 2 consecutive cycles),
eeprom_mismatch (any phase), flow_stagnation (intake), sht31_out_of_range
(environment delta between consecutive cycles).

Output: one compact `.osmell` JSON object per line on stdout.

Schema: the raw eight slots stay canonical.  Additive v1.1 fields are a
top-level monotonic `sequence` (uint32), an ISO-8601Z `wall_clock`, and a
`derived` interpretation object with all-null members when no profile is
installed.  `flow_position` is always "left" (S0-S3) or "right" (S4-S7) - it
never encodes upstream/downstream, because both rows face the same channel.

`eeprom_id` is synthetic host metadata here, not a value emitted by v1 firmware
(firmware leaves it null). It exists so the eeprom_mismatch QC rule can be
exercised against a real stream shape.  Identity and calibration fields stay
null in the raw slots.

`--self-test` validates one accelerated cycle without pacing or stdout records.
"""

import argparse
import json
import math
import re
import sys
import time

HARDWARE_ID = "OpenSmell_Monitor_v1.1"
WALL_CLOCK = "2026-11-25T00:00:00Z"   # fixed ISO-8601Z for deterministic HIL runs
CYCLE_S = {"intake": 10.0, "hold": 10.0, "purge": 20.0}
PHASES = ["intake", "hold", "purge", "report"]
SLOTS = 8       # eight identical OSM-1 slots; no analog/digital bank split
UINT32 = 0xFFFFFFFF
# Real MOX cells are never perfectly flat. Small intake-phase noise keeps a
# healthy clean-air stream from looking like a stuck cell to the QC rules,
# while injected anomalies deliberately override it. Noise is intake-only so
# the hold phase stays flat (drift rule compares hold-to-hold over the 10 s
# hold).
NOISE_V = 0.002


def intake_noise(cycle_id, slot_index):
    """Deterministic alternating +/-NOISE_V so consecutive intakes always move."""
    seed = cycle_id * 3 + slot_index
    return NOISE_V * (1 if seed % 2 else -1)


# Nominal per-slot voltages (V) at each phase. Analog MOX drops slightly
# during intake as gas is absorbed, recovers during purge.
BASE_V = {
    "intake": 1.200,
    "hold": 1.250,
    "purge": 1.300,
    "report": 1.300,
}


def make_slot(i, analog_v, adc_counts, digital_value, i2c_model,
              eeprom_id, sensor_model):
    """Build one OSM-1 slot entry matching the locked `.osmell` shape.

    Slot index tells the host which side-wall station the slot occupies
    (0..3 left wall, 4..7 right wall); it does not say what module is fitted
    and it is not an upstream/downstream claim.  Both rows face the same
    central channel, so there is no cascade bank.
    """
    return {
        "index": i,
        "flow_position": "left" if i < 4 else "right",
        "sensor_type": "I2C" if i2c_model else "ANALOG",
        "sensor_model": sensor_model or i2c_model,
        "eeprom_id": eeprom_id,
        "calibration_date": None,
        "readings": {
            "analog_value_v": round(analog_v, 3),
            "adc_counts": adc_counts,
            "digital_value": digital_value,
            "unit": "V",
        },
        "qc_flags": [],
    }


def build_slots(cycle_id, phase, base_v, slot_v, slot_idx, eeprom_id, sensor_model):
    """Eight uniform slots: raw analog value is always the canonical channel."""
    slots = []
    for i in range(SLOTS):
        # Non-target slots also get intake-only noise so a clean stream
        # never reads as a stuck cell.
        av = slot_v if i == slot_idx else base_v + (
            intake_noise(cycle_id, i) if phase == "intake" else 0.0
        )
        counts = int(av / 4.096 * 32768 / 2)
        i2c_model = "SCD40" if i >= 4 else None
        dv = 400 + i * 10 if i2c_model else None
        slots.append(make_slot(i, av, counts, dv, i2c_model,
                               eeprom_id, sensor_model))
    return slots


def make_record(cycle_id, phase, ts_ms, temp_c, rh_pct, slots, anomaly_flags,
                sequence, wall_clock=WALL_CLOCK):
    """Build a complete additive `.osmell` record.

    Raw slots remain canonical; `derived` is a host/display convenience only
    and never overwrites an `analog_value_v`.  A profile may be absent in a
    real device, in which case every derived member is JSON null; the HIL
    stream installs the synthetic "v1" profile so the presentation path is
    exercised end to end.
    """
    duration = CYCLE_S.get(phase, 0.0) if phase in CYCLE_S else 0.0
    raw_slots = slots  # canonical: no rewriting of analog values
    derived_slots = [round(s["readings"]["analog_value_v"] * 10.0, 3)
                     for s in raw_slots]
    aqi = round(sum(derived_slots) / len(derived_slots), 2)
    return {
        "format": ".osmell",
        "version": "1.0",
        "hardware_id": HARDWARE_ID,
        "sequence": sequence & UINT32,
        "wall_clock": wall_clock,
        "timestamp_ms": ts_ms,
        "cycle": {"id": cycle_id, "phase": phase, "duration_s": duration},
        "environment": {
            "temperature_c": round(temp_c, 2),
            "humidity_pct": round(rh_pct, 2),
            "sensor_id": "SHT31",
        },
        # Gas + pH + T/H travel together.  The base has no pH sensor, so the
        # simulator leaves the field null just like the firmware does until an
        # ISFET cartridge supplies a value.
        "ph": {"value": None, "slot": None, "unit": "pH"},
        "slots": raw_slots,
        "derived": {
            "profile": "v1",
            "aqi": aqi,
            "label": "good",
            "slots": derived_slots,
        },
        "user_metadata": anomaly_flags.get("user_metadata", {}),
    }


def validate_record(rec, expected_sequence):
    """Schema check used by --self-test; returns a list of failures."""
    problems = []
    required = ("format", "version", "hardware_id", "sequence", "wall_clock",
                "timestamp_ms", "cycle", "environment", "ph", "slots",
                "derived", "user_metadata")
    missing = [k for k in required if k not in rec]
    if missing:
        return ["missing keys: %s" % ",".join(missing)]

    if rec["format"] != ".osmell" or rec["version"] != "1.0":
        problems.append("format/version")
    if rec["sequence"] != expected_sequence or not (0 <= rec["sequence"] <= UINT32):
        problems.append("sequence")
    if not isinstance(rec["wall_clock"], str) or not re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", rec["wall_clock"]):
        problems.append("wall_clock")
    if rec["cycle"]["phase"] not in PHASES:
        problems.append("phase")
    if rec["environment"]["sensor_id"] != "SHT31":
        problems.append("environment.sensor_id")
    if rec["ph"]["value"] is not None or rec["ph"]["slot"] is not None:
        problems.append("ph identity")

    slots = rec["slots"]
    if not isinstance(slots, list) or len(slots) != SLOTS:
        return problems + ["slots length"]
    for i, slot in enumerate(slots):
        if slot["index"] != i:
            problems.append("slot %d index" % i)
        if slot["flow_position"] != ("left" if i < 4 else "right"):
            problems.append("slot %d flow_position" % i)
        if slot["calibration_date"] is not None:
            problems.append("slot %d calibration_date" % i)
        if "adc_counts" not in slot["readings"]:
            problems.append("slot %d raw readings" % i)

    derived = rec["derived"]
    if sorted(derived) != ["aqi", "label", "profile", "slots"]:
        problems.append("derived keys")
    elif (derived["profile"] != "v1"
          or not isinstance(derived["aqi"], (int, float))
          or derived["label"] != "good"
          or not isinstance(derived["slots"], list)
          or len(derived["slots"]) != SLOTS
          or any(not isinstance(v, (int, float)) for v in derived["slots"])):
        problems.append("derived values")
    # Additive values must be a view of the canonical raw slots, not a rewrite.
    if "derived" in rec and len(derived.get("slots", [])) == SLOTS:
        for i, slot in enumerate(slots):
            raw = slot["readings"]["analog_value_v"]
            if abs(derived["slots"][i] - round(raw * 10.0, 3)) > 1e-6:
                problems.append("slot %d derived/raw mismatch" % i)
    return problems


def self_test():
    """One accelerated cycle, schema + QC injection coverage, no stdout data."""
    problems = []
    for seq, phase in enumerate(PHASES, start=1):
        base_v = BASE_V[phase]
        slots = build_slots(1, phase, base_v, base_v, 0, "EEPROM-1234", None)
        rec = make_record(1, phase, seq * 1000, 22.5, 45.0, slots, {}, seq)
        problems += ["%s: %s" % (phase, p) for p in validate_record(rec, seq)]

    # Injection paths must still change the canonical raw stream.
    saturated = build_slots(1, "intake", BASE_V["intake"], 3.3, 0, None, None)
    if saturated[0]["readings"]["analog_value_v"] != 3.3:
        problems.append("saturation injection")
    drifted = build_slots(1, "hold", BASE_V["hold"],
                          BASE_V["hold"] + 1.0 / 1000.0, 0, None, None)
    if drifted[0]["readings"]["analog_value_v"] <= BASE_V["hold"]:
        problems.append("drift injection")
    stagnant = build_slots(1, "intake", BASE_V["intake"], BASE_V["intake"],
                           0, None, None)
    if stagnant[0]["readings"]["analog_value_v"] != BASE_V["intake"]:
        problems.append("stagnation injection")
    null_id = make_slot(0, BASE_V["intake"], 9600, None, None, None, None)
    if null_id["eeprom_id"] is not None:
        problems.append("eeprom injection")
    if 22.5 + 10.0 <= 22.5:
        problems.append("sht31 injection")

    if problems:
        print("HIL SELF-TEST FAIL: " + "; ".join(problems), file=sys.stderr)
        return 1
    print("HIL SELF-TEST PASS: 4 phases, additive sequence/wall_clock/derived, "
          "raw slots canonical, flow_position left/right, 5 QC injections",
          file=sys.stderr)
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="OpenSmell v1.1 HIL simulator — pumps .osmell JSON with injected anomalies."
    )
    ap.add_argument(
        "--accel",
        type=float,
        default=10.0,
        help="Acceleration factor vs real-time (default 10: 40s cycle -> 4s).",
    )
    ap.add_argument(
        "--cycles",
        type=int,
        default=0,
        help="Number of cycles to run (0 = run forever).",
    )
    ap.add_argument(
        "--inject-saturation",
        action="store_true",
        help="Force analog_value_v to the 3.3V rail on all slots (adc_saturation).",
    )
    ap.add_argument(
        "--inject-drift",
        action="store_true",
        help="Force positive voltage slope in hold phase (baseline_drift).",
    )
    ap.add_argument(
        "--inject-sht31",
        action="store_true",
        help="Force +10 degC environment temperature spike (sht31_out_of_range).",
    )
    ap.add_argument(
        "--inject-eeprom",
        action="store_true",
        help="Force null EEPROM ID while keeping valid readings (eeprom_mismatch).",
    )
    ap.add_argument(
        "--inject-stagnation",
        action="store_true",
        help="Force flat MOX derivative in intake phase (flow_stagnation).",
    )
    ap.add_argument(
        "--slot",
        type=int,
        default=0,
        help="Target slot index for anomaly injection (default 0).",
    )
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="Validate one accelerated cycle and the additive schema; emit no data.",
    )
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    slot_idx = max(0, min(args.slot, SLOTS - 1))
    cycle_id = 0
    sequence = 0
    sim_t = 0.0  # simulated seconds since boot
    prev_env = None  # (temp_c, rh_pct) for SHT31 delta detection
    hold_last_v = None  # last hold-phase analog V for drift detection
    intake_last_v = None  # last intake-phase analog V for stagnation detection
    drift_offset = 0.0  # cumulative drift for --inject-drift

    while True:
        if args.cycles and cycle_id >= args.cycles:
            break
        cycle_id += 1

        for phase in PHASES:
            phase_wall_start = time.monotonic()

            # ---- simulated sensor values -------------------------------------
            base_v = BASE_V[phase]

            # Clean analog voltage: intake-only noise so healthy cells move
            # slightly each intake (distinguishes live cells from stuck ones)
            # while hold stays perfectly flat (drift rule compares hold-to-hold
            # over the 10 s hold).
            clean_v = base_v + (
                intake_noise(cycle_id, slot_idx) if phase == "intake" else 0.0)

            # --inject-saturation: rail the target analog slot at 3.3V
            if args.inject_saturation:
                slot_v = 3.3 if phase in ("intake", "hold", "purge") else clean_v
            # --inject-drift: add growing positive offset during hold
            elif args.inject_drift and phase == "hold":
                drift_offset += 1.0  # mV per cycle -> triggers >0.05 mV/s
                slot_v = clean_v + drift_offset / 1000.0
            # --inject-stagnation: flat MOX derivative during intake
            elif args.inject_stagnation and phase == "intake":
                slot_v = intake_last_v if intake_last_v is not None else clean_v
            else:
                slot_v = clean_v

            # --inject-sht31: alternate 22.5 <-> 32.5 each cycle starting cycle 2.
            # The QC rule is a *delta* between consecutive cycles, so every
            # transition re-triggers; the flag stays visible through end of stream.
            spike = args.inject_sht31 and (cycle_id % 2 == 0)
            temp_c = 22.5 + (10.0 if spike else 0.0)
            rh_pct = 45.0

            # --inject-eeprom: null host identity with valid readings.
            # Non-null values are synthetic host metadata, not a firmware
            # readout; firmware emits null and the host fills this field.
            eeprom_id = None if args.inject_eeprom else "EEPROM-1234"
            sensor_model = "TGS-2600" if (phase == "intake" and not args.inject_eeprom) else None

            slots = build_slots(cycle_id, phase, base_v, slot_v, slot_idx,
                                eeprom_id, sensor_model)
            sequence = (sequence + 1) & UINT32
            ts_ms = int(sim_t * 1000)
            record = make_record(cycle_id, phase, ts_ms, temp_c, rh_pct, slots,
                                 {}, sequence)
            sys.stdout.write(json.dumps(record, separators=(",", ":")) + "\n")
            sys.stdout.flush()

            # ---- update simulated state for next phase -----------------------
            if phase == "intake":
                intake_last_v = slot_v
            if phase == "hold":
                hold_last_v = slot_v

            sim_t += CYCLE_S.get(phase, 0.0) / args.accel
            prev_env = (temp_c, rh_pct)

            # ---- wall-clock pacing ------------------------------------------
            phase_wall_s = CYCLE_S.get(phase, 0.0) / args.accel
            elapsed = time.monotonic() - phase_wall_start
            remaining = phase_wall_s - elapsed
            if remaining > 0:
                time.sleep(remaining)

    return 0


if __name__ == "__main__":
    sys.exit(main())
