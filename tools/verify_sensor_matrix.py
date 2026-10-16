#!/usr/bin/env python3
"""Numeric acceptance gate for the OpenSmell sensor matrix.

Fails (exit 1) if the sensor pool is malformed, if a sensor cannot be placed in
any bank (iface/bank inconsistency), if the recommended pack does not cover
every persona axis, if it overruns the fixed 4+4 bank, or if the resulting rail
draw exceeds the supply. Mirrors tools/verify_electrical.py and
tools/verify_cad.py: a green run is the gate before the BOM is trusted.

Run:  python tools/verify_sensor_matrix.py
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "electrical"))
import sensor_matrix as SM  # noqa: E402
from sensor_data import GASES as _GASES  # noqa: E402

SLOT_COUNT = sum(SM.BANK_CAP.values())   # derived from CONST (4 analog + 4 digital)
MIN_PRINCIPLES = 4       # MOX + EC + NDIR + T/RH across pack + base

# --- system rail constants (blueprint 5.8) ---------------------------------
SUPPLY_5V_A = 3.0        # USB-C 5 V / 3 A budget
SUPPLY_3V3_A = 1.0       # AMS1117-3.3 (1 A) budget
FAN_A = 0.15
BUZZER_A = 0.03
MCU_3V3_A = 0.15         # ESP32 avg (peak ~0.5 A transient)
PERIPH_3V3_A = 0.10      # ADC + mux + OLED (excl. base/pack sensors)

fails = []


def check(ok, label, detail=""):
    tag = "ok  " if ok else "FAIL"
    if not ok:
        fails.append(label)
    print("[%s] %-56s %s" % (tag, label, detail))


def rail_a(power_mw, volts):
    return power_mw / 1000.0 / volts


def main():
    print("== pool integrity ==")
    names = [s["name"] for s in SM.SENSORS]
    check(len(names) == len(set(names)), "sensor names unique")
    for s in SM.SENSORS:
        check(bool(s["axes"]) and set(s["axes"]) <= set(SM.AXES),
              "axes valid: %s" % s["name"],
              "+".join(s["axes"]) if s["axes"] else "NONE")
        check(s.get("principle") and s.get("iface") in ("analog", "i2c"),
              "iface hostable: %s" % s["name"],
              "%s (no UART/SPI bank exists)" % s.get("iface"))
        check(s["power"] > 0 and s["cost"] > 0,
              "power/cost positive: %s" % s["name"])
    # a profile key outside GASES is silently dropped by orthogonality.matrix,
    # which would make a sensor invisible to the information analysis.
    bad_gas = {s["name"]: sorted(set(s["profile"]) - set(_GASES))
               for s in SM.SENSORS if set(s["profile"]) - set(_GASES)}
    check(not bad_gas, "profile gases closed over GASES (no silent drops)",
          "" if not bad_gas else str(bad_gas))
    # every row must point at a real document -- a profile with no citation is
    # an untraceable number, which is exactly what this layer must not contain.
    unsourced = [s["name"] for s in SM.SENSORS if s.get("source") == "UNSOURCED"]
    check(not unsourced, "every sensor cites a source document",
          "" if not unsourced else str(unsourced))
    # `inferred` flags profile keys no datasheet backs; if it names a key that
    # is not even in the profile it is a stale annotation, not a caveat.
    bad_inf = {s["name"]: sorted(set(s.get("inferred", ())) - set(s["profile"]))
               for s in SM.SENSORS if set(s.get("inferred", ())) - set(s["profile"])}
    check(not bad_inf, "inferred keys are subset of profile",
          "" if not bad_inf else str(bad_inf))

    print("== slot placement (iface vs physical bank) ==")
    for s in SM.SENSORS:
        slot = s.get("slot")
        check(slot in ("analog", "digital", "base"),
              "slot declared: %s" % s["name"], str(slot))
        if slot == "analog":
            # analog bank: 5V|3V3|GND + AO + DO -- no SDA/SCL, no UART pin, so
            # a UART-only module cannot be read here (MH-Z19C/ZE03 expose Vout
            # and are therefore encoded iface="analog").
            check(s["iface"] == "analog",
                  "analog bank hostable: %s" % s["name"],
                  "%s (via AO; no UART/I2C pins)" % s["iface"])
        elif slot == "digital":
            # digital bank: 3V3|GND + SDA|SCL|INT|CTRL -- no 5 V, no UART
            check(s["iface"] == "i2c",
                  "digital bank hostable: %s" % s["name"],
                  "%s (needs 3.3 V I2C; no 5 V here)" % s["iface"])
        elif slot == "base":
            check(s["iface"] == "i2c",
                  "base is I2C: %s" % s["name"], s["iface"])

    print("== base ==")
    check(bool(SM.BASE_SENSORS), "base present", ", ".join(SM.BASE_SENSORS))
    check(set(SM.BASE_SENSORS) <= set(names), "base sensors exist in pool")

    print("== persona coverage (within starter pack, 4+4 banks) ==")
    starter = set(SM.RECOMMENDED_PACK)
    pack_cov = SM.covered(starter) | SM.base_axes()
    for p, axes in SM.PERSONAS.items():
        check(set(axes) <= set(SM.AXES), "persona axes valid: %s" % p)
        # the starter pack must be able to serve this persona ...
        check(set(axes) <= pack_cov,
              "starter pack covers persona: %s" % p,
              "" if set(axes) <= pack_cov
              else "MISS %s" % sorted(set(axes) - pack_cov))
        # ... and its pack-subset is solvable inside the banks.
        got, miss = SM.select(axes, within=SM.RECOMMENDED_PACK)
        na = sum(1 for n in got if SM._BYNAME[n]["slot"] == "analog")
        nd = sum(1 for n in got if SM._BYNAME[n]["slot"] == "digital")
        fits = na <= SM.BANK_CAP["analog"] and nd <= SM.BANK_CAP["digital"]
        subset = set(got) <= starter
        check(not miss and fits and subset,
              "persona subset in pack/banks: %s" % p,
              "%d module(s) A%d/D%d" % (len(got), na, nd)
              if not miss else "MISS %s" % miss)

    print("== recommended pack ==")
    d = SM.RECOMMENDED_PACK
    na = sum(1 for n in d if SM._BYNAME[n]["slot"] == "analog")
    nd = sum(1 for n in d if SM._BYNAME[n]["slot"] == "digital")
    check(not SM.RECOMMENDED_MISSING,
          "covers union of all personas (incl. base)",
          "" if not SM.RECOMMENDED_MISSING else "MISS %s" % SM.RECOMMENDED_MISSING)
    check(len(d) <= SLOT_COUNT,
          "fits the fixed 8-slot bank", "%d <= %d slots" % (len(d), SLOT_COUNT))
    check(na <= SM.BANK_CAP["analog"],
          "analog bank within cap", "%d <= %d" % (na, SM.BANK_CAP["analog"]))
    check(nd <= SM.BANK_CAP["digital"],
          "digital bank within cap", "%d <= %d" % (nd, SM.BANK_CAP["digital"]))
    system = d + SM.BASE_SENSORS
    check(MIN_PRINCIPLES <= SM.principle_diversity(system),
          "principle diversity >= %d (pack + base)" % MIN_PRINCIPLES,
          "%d (%s)" % (SM.principle_diversity(system),
                       ", ".join(sorted({SM._BYNAME[n]["principle"]
                                         for n in system}))))

    print("== rail budgets (blueprint 5.8) ==")
    # analog-slot modules hang off 5 V (heater/Vout); digital + base off 3.3 V.
    i5_sensors = sum(rail_a(SM._BYNAME[n]["power"], 5.0)
                     for n in d if SM._BYNAME[n]["slot"] == "analog")
    i33_sensors = sum(rail_a(SM._BYNAME[n]["power"], 3.3)
                      for n in system if SM._BYNAME[n]["slot"] != "analog")
    i5_total = i5_sensors + FAN_A + BUZZER_A
    i33_total = i33_sensors + MCU_3V3_A + PERIPH_3V3_A
    check(i5_total <= SUPPLY_5V_A, "5 V rail <= supply",
          "%.2f A <= %.2f A (sensors %.3f + fan %.2f + buzzer %.2f)"
          % (i5_total, SUPPLY_5V_A, i5_sensors, FAN_A, BUZZER_A))
    check(i33_total <= SUPPLY_3V3_A, "3.3 V rail <= AMS1117",
          "%.2f A <= %.2f A (sensors %.3f + mcu %.2f + periph %.2f)"
          % (i33_total, SUPPLY_3V3_A, i33_sensors, MCU_3V3_A, PERIPH_3V3_A))

    print("== coverage matrix ==")
    cov = SM.covered(d) | SM.base_axes()
    header = "  %-14s" % "sensor" + "".join("%-6s" % a[:5] for a in SM.AXES)
    print(header)
    for n in d:
        s = SM._BYNAME[n]
        row = "  %-14s" % n + "".join(
            "%-6s" % ("X" if a in s["axes"] else ".") for a in SM.AXES)
        print(row)
    for n in SM.BASE_SENSORS:
        s = SM._BYNAME[n]
        row = "  %-14s*" % n + "".join(
            "%-6s" % ("X" if a in s["axes"] else ".") for a in SM.AXES)
        print(row)
    print("  %-14s" % "COVERED" + "".join(
        "%-6s" % ("X" if a in cov else "-") for a in SM.AXES))

    print()
    if fails:
        print("RESULT: FAIL (%d)" % len(fails))
        for f in fails:
            print("   -", f)
        return 1
    print("RESULT: ALL PASS (pack=%d slot modules + base %s; A%d/D%d; "
          "%d principles; 5V %.2f A, 3V3 %.2f A)"
          % (len(d), "+".join(SM.BASE_SENSORS), na, nd,
             SM.principle_diversity(system), i5_total, i33_total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
