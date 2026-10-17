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
            errors.append("  %-12s config.h=%s  interface=%s (%s)"
                          % (define, got, want, signal))

    check("OS_PIN_SDA", "I2C_SDA")
    check("OS_PIN_SCL", "I2C_SCL")
    check("OS_PIN_FAN_PWM", "FAN_PWM")
    check("OS_PIN_LED", "LED")
    check("OS_PIN_BUZZER", "BUZZER")
    check("OS_PIN_BUTTON", "BUTTON")

    for arr, sig in (("OS_PIN_DO", "DO"), ("OS_PIN_INT", "INT"), ("OS_PIN_CTRL", "CTRL")):
        got = parse_array(text, arr)
        want = [pm["%s%d" % (sig, i)] for i in range(4)]
        if got != want:
            errors.append("  %-12s config.h=%s  interface=%s" % (arr, got, want))

    # I2C addresses
    for define, key in (("ADDR_ADS1115", "ADS1115"), ("ADDR_TCA9548A", "TCA9548A"),
                        ("ADDR_SHT31", "SHT31"), ("ADDR_OLED", "OLED")):
        want = IF.I2C.get(key)
        got = d.get(define)
        # interface stores addresses as int or hex-string; normalise
        want_i = int(want, 0) if isinstance(want, str) else want
        if got != want_i:
            errors.append("  %-12s config.h=%s  interface=%s (%s)"
                          % (define, got, want_i, key))

    print("interface MCU signals: %d" % len(pm))
    if errors:
        print("MISMATCH (%d):" % len(errors))
        for e in errors:
            print(e)
        sys.exit(1)
    print("FIRMWARE PIN PARITY OK")


if __name__ == "__main__":
    main()
