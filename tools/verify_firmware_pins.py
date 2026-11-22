"""Parity gate: firmware/config.h pins must equal interface.PINMAP.

Keeps the firmware from silently drifting away from the electrical contract
(electrical/interface.py), the same way verify_netlist.py pins the schematic to
board.py.

Run:  python tools/verify_firmware_pins.py
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "electrical"))
import interface as IF  # noqa: E402

CONFIG_H = os.path.join(ROOT, "firmware", "esp32", "smell_monitor", "config.h")


def parse_defines(text):
    d = {}
    for m in re.finditer(r"#define\s+([A-Z_][A-Z0-9_]*)\s+(0x[0-9A-Fa-f]+|\d+)", text):
        d[m.group(1)] = int(m.group(2), 0)
    return d


def parse_array(text, name):
    m = re.search(re.escape(name) + r"\s*\[\s*\d+\s*\]\s*=\s*\{([^}]*)\}", text)
    if not m:
        return None
    return [int(x) for x in re.findall(r"-?\d+", m.group(1))]


def main():
    text = open(CONFIG_H, encoding="utf-8").read()
    d = parse_defines(text)
    pm = IF.PINMAP["mcu"]

    errors = []

    def check(define, signal):
        want = pm[signal]
        got = d.get(define)
        if got != want:
            errors.append("  %-14s config.h=%s  interface=%s (%s)"
                          % (define, got, want, signal))

    check("OS_PIN_SDA", "I2C_SDA")
    check("OS_PIN_SCL", "I2C_SCL")
    check("OS_PIN_FAN_PWM", "FAN_PWM")
    check("OS_PIN_LED", "LED")
    check("OS_PIN_BUZZER", "BUZZER")
    check("OS_PIN_BUTTON", "BUTTON")
    check("OS_PIN_ONEWIRE", "ONEWIRE")

    # Eight digital read-back lines, slots 0-7.
    got = parse_array(text, "OS_PIN_DO")
    want = [pm["DO%d" % i] for i in range(IF.N_SLOTS)]
    if got != want:
        errors.append("  OS_PIN_DO      config.h=%s  interface=%s" % (got, want))

    # No boot-strapping pins used anywhere.
    gpio = list(pm.values())
    check_unused = [g for g in gpio if g in IF.PINS_STRAP]
    if check_unused:
        errors.append("  boot-strapping pins used: %s" % check_unused)

    # No input-only pin used as an output.
    out_pins = [pm[n] for n in ("FAN_PWM", "BUZZER", "LED")]
    bad = [g for g in out_pins if g in IF.PINS_IN_ONLY]
    if bad:
        errors.append("  input-only pin used as output: %s" % bad)

    # I2C addresses.
    for define, key in (("ADDR_ADS1115_A", "ADS1115_A"),
                        ("ADDR_ADS1115_B", "ADS1115_B"),
                        ("ADDR_TCA9548A", "TCA9548A"),
                        ("ADDR_SHT31", "SHT31")):
        want = IF.I2C.get(key)
        got = d.get(define)
        want_i = int(want, 0) if isinstance(want, str) else want
        if got != want_i:
            errors.append("  %-18s config.h=%s  interface=%s (%s)"
                          % (define, got, want_i, key))

    # Nothing may reference the removed OLED address.
    if d.get("ADDR_OLED") is not None:
        errors.append("  ADDR_OLED still defined (OLED removed in OSM-1 re-lay)")

    print("interface MCU signals: %d / capacity %d"
          % (IF.PINMAP["mcu_signals"], IF.PINMAP["capacity"]))
    if errors:
        print("MISMATCH (%d):" % len(errors))
        for e in errors:
            print(e)
        sys.exit(1)
    print("FIRMWARE PIN PARITY OK")


if __name__ == "__main__":
    main()
