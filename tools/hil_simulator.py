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
"""

import argparse
import json
import math
import sys
import time

HARDWARE_ID = "OpenSmell_Monitor_v1.1"
CYCLE_S = {"intake": 10.0, "hold": 10.0, "purge": 20.0}
PHASES = ["intake", "hold", "purge", "report"]
SLOTS = 8       # eight identical OSM-1 slots; no analog/digital bank split
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
    """Build one OSM-1 slot entry matching the locked .osmell v1.0 shape.

    Slot index tells the host where the slot sits in the cascade (0..3
    downstream, 4..7 upstream); it does not say what kind of module is fitted.
    """
    return {
        "index": i,
        "flow_position": "downstream" if i < 4 else "upstream",
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


def make_record(cycle_id, phase, ts_ms, temp_c, rh_pct, slots, anomaly_flags):
    """Build a complete `.osmell` v1.0 record."""
    duration = CYCLE_S.get(phase, 0.0) if phase in CYCLE_S else 0.0
    return {
        "format": ".osmell",
        "version": "1.0",
        "hardware_id": HARDWARE_ID,
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
        "slots": slots,
        "user_metadata": anomaly_flags.get("user_metadata", {}),
    }


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
    args = ap.parse_args()

    slot_idx = max(0, min(args.slot, SLOTS - 1))
    cycle_id = 0
    wall_start = time.monotonic()
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
            clean_v = base_v + (intake_noise(cycle_id, slot_idx) if phase == "intake" else 0.0)

            # --inject-saturation: rail the target analog slot at 3.3V
            if args.inject_saturation:
                slot_v = 3.3 if (phase in ("intake", "hold", "purge")) else clean_v
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

            # --inject-eeprom: null EEPROM ID with valid readings
            eeprom_id = None if args.inject_eeprom else "EEPROM-1234"
            sensor_model = "TGS-2600" if (phase == "intake" and not args.inject_eeprom) else None

            # Build eight uniform slots.  A mix is simulated here (analog MOX
            # everywhere, I2C model on the downstream four), but the *schema*
            # is identical for every position: index carries flow position,
            # not module type.
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
                slots.append(
                    make_slot(i, av, counts, dv, i2c_model,
                              eeprom_id, sensor_model)
                )

            ts_ms = int(sim_t * 1000)
            record = make_record(
                cycle_id, phase, ts_ms, temp_c, rh_pct, slots, {}
            )
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


if __name__ == "__main__":
    main()
