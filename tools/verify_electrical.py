#!/usr/bin/env python3
"""Numeric acceptance gate for the OpenSmell electrical interface.

Fails (exit 1) if the frozen L1/L2 contract is internally inconsistent or does
not close against the ESP32 pin budget. Mirrors tools/verify_cad.py in spirit:
a green run is the gate before any schematic/PCB work is trusted.

Run:  python tools/verify_electrical.py
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "electrical"))
import interface as IF  # noqa: E402

fails = []
n_checks = 0


def check(ok, label, detail=""):
    global n_checks
    n_checks += 1
    tag = "ok  " if ok else "FAIL"
    if not ok:
        fails.append(label)
    print("[%-4s] %-52s %s" % (tag, label, detail))


def main():
    CONST = IF.CONST
    pm = IF.PINMAP

    print("== closure ==")
    for a, d in [(4, 4), (6, 6), (8, 8)]:
        p = IF.build_pinmap(a, d)
        tag = "I2C expander" if p["needs_expander"] else "MCU only"
        print("   %dA+%dD: %2d signals vs %d pins -> %-12s %s"
              % (a, d, p["mcu_signals"], p["capacity"], tag,
                 p["warnings"] or ""))

    print("== pin map ==")
    gpio = list(pm["mcu"].values())
    check(len(gpio) == len(set(gpio)), "MCU GPIO assignments unique")
    check(all(g not in IF.PINS_STRAP for g in gpio),
          "no boot-strapping pins used", str(sorted(set(gpio) & set(IF.PINS_STRAP))))

    input_names = set(pm["inputs"])
    out_pins = [pm["mcu"][n] for n in pm["outputs"] if n in pm["mcu"]]
    check(not (set(out_pins) & set(IF.PINS_IN_ONLY)),
          "no input-only pin used as output",
          str(sorted(set(out_pins) & set(IF.PINS_IN_ONLY))))
    check(not pm["warnings"], "pin budget closes without warnings")

    if pm["expander"]:
        lines = list(pm["expander"].values())
        check(len(lines) == len(set(lines)) and max(lines) < 16,
              "expander line count <= 16", "%d lines" % len(lines))

    print("== i2c ==")
    addrs = list(IF.I2C.values())
    check(len(addrs) == len(set(addrs)), "I2C addresses unique on master bus")

    print("== board <-> chamber (L2) ==")
    bx0, by0 = IF.PCB_X0, IF.PCB_Y0
    check(abs(bx0 - (CONST["SH"] - CONST["PCB_X"]) / 2) < 1e-9,
          "board centred in X", "x0=%.2f" % bx0)
    for cx, cy in IF.ANALOG_HEADERS:
        check(0 <= cx <= CONST["PCB_X"] and 0 <= cy <= CONST["PCB_Y"],
              "analog header inside board", "(%.2f, %.2f)" % (cx, cy))
    for cx, cy in IF.DIGITAL_HEADERS:
        check(0 <= cx <= CONST["PCB_X"] and 0 <= cy <= CONST["PCB_Y"],
              "digital header inside board", "(%.2f, %.2f)" % (cx, cy))

    A = CONST["A_X"]
    D = CONST["D_X"]
    a_gaps = sorted(round(A[i + 1] - A[i], 2) for i in range(len(A) - 1))
    d_gaps = sorted(round(D[i + 1] - D[i], 2) for i in range(len(D) - 1))
    check(len(set(a_gaps)) <= 1, "analog pitch uniform", "gaps=%s" % a_gaps)
    check(len(set(d_gaps)) <= 1, "digital pitch uniform", "gaps=%s" % d_gaps)
    # a cartridge is at most 20 mm wide (OSM-1), so the row spans its centres
    # plus 10 mm each side; both rows must stay inside the cavity walls.
    for bank, xs in (("analog", A), ("digital", D)):
        check(max(xs) - min(xs) + 20.0 <= CONST["CX"],
              "%s row fits cavity" % bank,
              "%.1f mm row in a %.0f mm cavity"
              % (max(xs) - min(xs) + 20.0, CONST["CX"]))

    print("== rails ==")
    for rail, amps in IF.railtotals().items():
        limit = 3.0 if rail == "5V" else 1.0
        check(amps <= limit * 0.8, "%s rail within headroom" % rail,
              "%.2f A / %.1f A" % (amps, limit))

    print()
    if fails:
        print("RESULT: FAIL (%d)" % len(fails))
        for f in fails:
            print("   -", f)
        return 1
    print("RESULT: ALL PASS (%d checks)" % n_checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
