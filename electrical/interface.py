#!/usr/bin/env python3
"""OpenSmell electrical interface - the frozen L1/L2 contract (single source).

Sibling of ``mechanical/constants.py``. Everything electrical that is
*hard to vary* lives here and derives from the mechanical geometry, so the
schematic, PCB and firmware cannot drift from the chamber:

  * sensing-slot pinouts   (the product contract users design against)
  * I2C topology + device addresses
  * the MCU pin map, with a checked GPIO-closure budget
  * board <-> chamber header coordinates (from CONST)

The architecture is the *contract*; the slot *count* is a configuration that
follows the mechanical model. Run ``python tools/verify_electrical.py`` to
check closure and consistency against CONST.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "mechanical"))
from constants import CONST  # noqa: E402


# --- geometry-derived counts ----------------------------------------------
N_ANALOG = len(CONST["A_X"])
N_DIGITAL = len(CONST["D_X"])

# --- slot contracts (physical pin order; index 0 == header pin 1) ----------
SLOT_ANALOG = ["+5V", "GND", "AO", "DO", "3V3"]
SLOT_DIGITAL = ["3V3", "GND", "SDA", "SCL", "INT", "CTRL"]
MUX_CHANNEL = {"SDA": "SDA", "SCL": "SCL"}  # routed through TCA9548A per slot

# --- I2C address map (master bus must be unique) ---------------------------
# Native 4+4 build populates only the first group; the expansion group is
# added when the slot count is raised to 8+8 (second ADC + GPIO expander).
I2C = {
    "ADS1115": 0x48,
    "TCA9548A": 0x70,
    "SHT31": 0x44,
    "OLED": 0x3C,
}
I2C_EXPANSION = {"ADS1115.2": 0x49, "MCP23017": 0x20}

# --- ESP32-WROOM-32E usable pins -------------------------------------------
PINS_BIDIR = [4, 13, 14, 16, 17, 18, 19, 23, 25, 26, 27, 32, 33]
PINS_IN_ONLY = [34, 35, 36, 39]
PINS_STRAP = [0, 2, 5, 12, 15]          # boot strapping: avoided by design
PINS_RESERVED = {"I2C_SDA": 21, "I2C_SCL": 22, "UART_TX": 1, "UART_RX": 3}

_OUTPUT_FIXED = ["FAN_PWM", "BUZZER", "LED"]
_INPUT_FIXED = ["BUTTON"]


def build_pinmap(n_analog=N_ANALOG, n_digital=N_DIGITAL):
    """Assign every required signal to a concrete GPIO.

    Interrupts (latency-critical) always stay on the MCU. The slow parallel
    lines (analog DO read-back + digital CTRL enables) move to an I2C
    expander only when the MCU pin budget cannot otherwise close.
    """
    ints = ["INT%d" % i for i in range(n_digital)]
    dos = ["DO%d" % i for i in range(n_analog)]
    ctrls = ["CTRL%d" % i for i in range(n_digital)]

    outputs = _OUTPUT_FIXED + ctrls
    inputs = _INPUT_FIXED + ints + dos
    mcu_signals = len(outputs) + len(inputs)
    capacity = len(PINS_BIDIR) + len(PINS_IN_ONLY)

    mcu = dict(PINS_RESERVED)
    expander = {}
    warnings = []

    if mcu_signals <= capacity:
        bidir = list(PINS_BIDIR)
        in_only = list(PINS_IN_ONLY)
        for name in outputs:
            mcu[name] = bidir.pop(0)
        for name in inputs:
            mcu[name] = (bidir or in_only).pop(0)
    elif (n_analog + n_digital) <= 16:
        bidir = list(PINS_BIDIR)
        for name in _OUTPUT_FIXED:
            mcu[name] = bidir.pop(0)
        for name in _INPUT_FIXED + ints:
            mcu[name] = bidir.pop(0)
        for i, name in enumerate(dos + ctrls):
            expander[name] = i  # MCP23017 GPA0..GPB7
    else:
        warnings.append("INFEASIBLE: %d slots exceed even the expander budget"
                        % (n_analog + n_digital))

    return {
        "mcu": mcu,
        "expander": expander,
        "needs_expander": bool(expander),
        "mcu_signals": mcu_signals,
        "capacity": capacity,
        "warnings": warnings,
        "outputs": outputs,
        "inputs": inputs,
    }


PINMAP = build_pinmap()


# --- board <-> chamber interface (L2) --------------------------------------
PCB_W, PCB_D, PCB_T = CONST["PCB_X"], CONST["PCB_Y"], CONST["PCB_T"]
PCB_X0 = (CONST["SH"] - PCB_W) / 2.0            # centred in the shell
PCB_Y0 = (CONST["SW"] - PCB_D) / 2.0

ANALOG_ROW_Y = CONST["A_Y0"] + CONST["A_SY"] / 2.0     # shell frame
DIGITAL_ROW_Y = CONST["NOSEY"] + CONST["D_SY"] / 2.0   # shell frame


def board_xy(shell_x, shell_y):
    """Shell (mm) -> board-local (mm, origin at board lower-left)."""
    return (shell_x - PCB_X0, shell_y - PCB_Y0)


ANALOG_HEADERS = [board_xy(x, ANALOG_ROW_Y) for x in CONST["A_X"]]
DIGITAL_HEADERS = [board_xy(x, DIGITAL_ROW_Y) for x in CONST["D_X"]]

# --- rail budgets (design average, ampere; ESP32 peak ~0.5 A transient) -----
RAILS = {
    "5V": {"MOX heaters": 0.15 * N_ANALOG, "fan": 0.15, "buzzer": 0.03},
    "3V3": {"ESP32 (avg)": 0.15, "digital slots": 0.05 * N_DIGITAL,
            "adc+mux+oled+sht31": 0.10},
}


def railtotals():
    return {rail: round(sum(v.values()), 3) for rail, v in RAILS.items()}


def summary():
    return {
        "n_analog": N_ANALOG, "n_digital": N_DIGITAL,
        "analog_headers": [(round(x, 2), round(y, 2)) for x, y in ANALOG_HEADERS],
        "digital_headers": [(round(x, 2), round(y, 2)) for x, y in DIGITAL_HEADERS],
        "board_origin": (round(PCB_X0, 2), round(PCB_Y0, 2)),
        "needs_expander": PINMAP["needs_expander"],
        "mcu_signals": PINMAP["mcu_signals"],
        "mcu_capacity": PINMAP["capacity"],
        "rails_A": railtotals(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(summary(), indent=2))
    for a, d in [(4, 4), (6, 6), (8, 8)]:
        pm = build_pinmap(a, d)
        tag = "expander" if pm["needs_expander"] else "MCU-only"
        print("%d+%d: %2d signals / %d capacity -> %s %s"
              % (a, d, pm["mcu_signals"], pm["capacity"], tag,
                 pm["warnings"] or ""))
