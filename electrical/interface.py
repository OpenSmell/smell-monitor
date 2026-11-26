#!/usr/bin/env python3
"""OpenSmell electrical interface - the frozen L1/L2 contract (single source).

Sibling of ``mechanical/constants.py``. Everything electrical that is
*hard to vary* lives here and derives from the mechanical geometry, so the
schematic, PCB and firmware cannot drift from the chamber:

  * the standard slot pinout   (the product contract users design against)
  * I2C topology + device addresses
  * the MCU pin map, with a checked GPIO-closure budget
  * board <-> chamber header coordinates (from CONST)

One slot design, repeated eight times (OSM-1, docs/module-standard.md):
a keyed 1x6 gas-cell socket and a Qwiic port on the same footprint.  The ID pin
is wired to one shared 1-Wire bus, but v1 firmware does not enumerate per-slot
EEPROMs: slot meaning and calibration are attached by the host application.

Run ``python tools/verify_electrical.py`` to check closure and consistency
against CONST.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "mechanical"))
from constants import CONST  # noqa: E402


# --- geometry-derived counts ----------------------------------------------
N_ANALOG = len(CONST["AN_Y"])     # left inner side wall (gas-cell bank)
N_DIGITAL = len(CONST["DI_Y"])    # right inner side wall
N_SLOTS = N_ANALOG + N_DIGITAL

# --- the standard slot (physical pin order; index 0 == header pin 1) --------
# A 4-pin MQ-style module (VCC, GND, AO, DO) seats straight onto pins 1-4,
# with power and ground adjacent.  3V3 is pin 5 so a 3.3 V analog module works,
# and ID is the last pin so no signal can be mistaken for a rail.
SLOT = ["+5V", "GND", "AO", "DO", "3V3", "ID"]

# Qwiic / STEMMA QT, JST-SH 1.0 mm 4-pin (SparkFun channel order).
QWIC = ["GND", "3V3", "SDA", "SCL"]

# --- I2C address map (master bus must be unique) ---------------------------
# The ADS1115 pair gives eight single-ended analog channels, one per slot.
# The TCA9548A gives one isolated downstream segment per Qwiic port, so eight
# identical I2C modules cannot collide.
I2C = {
    "ADS1115_A": 0x48,
    "ADS1115_B": 0x49,
    "TCA9548A": 0x70,
    "SHT31": 0x44,
    "DISPLAY": 0x3C,        # SSD1306 in the sealed front-panel bezel, master bus
}

# --- ESP32-WROOM-32E usable pins -------------------------------------------
PINS_BIDIR = [4, 13, 14, 16, 17, 18, 19, 23, 25, 26, 27, 32, 33]
PINS_IN_ONLY = [34, 35, 36, 39]
PINS_STRAP = [0, 2, 5, 12, 15]          # boot strapping: avoided by design
PINS_RESERVED = {"I2C_SDA": 21, "I2C_SCL": 22, "UART_TX": 1, "UART_RX": 3}

OUTPUTS = ["FAN_PWM", "BUZZER", "LED"]
INPUTS = ["BUTTON", "BUTTON_MENU"]


def build_pinmap(n_slots=N_SLOTS):
    """Assign every required signal to a concrete GPIO.

    The eight gas-cell DO lines and the three outputs stay directly on the MCU;
    the per-slot identity bus is one shared 1-Wire net.  There is no I2C GPIO
    expander in the OSM-1 build: eight DO lines plus one 1-Wire line fit the
    WROOM's usable pins with three spare bidirectional pins.
    """
    dos = ["DO%d" % i for i in range(n_slots)]
    outputs = list(OUTPUTS)
    inputs = list(INPUTS) + dos
    need = len(outputs) + len(inputs) + 1          # + ONEWIRE
    capacity = len(PINS_BIDIR) + len(PINS_IN_ONLY)

    mcu = dict(PINS_RESERVED)
    warnings = []
    if need > capacity:
        warnings.append("INFEASIBLE: %d signals exceed %d usable pins"
                        % (need, capacity))
        return {
            "mcu": mcu, "expander": {}, "needs_expander": False,
            "mcu_signals": need, "capacity": capacity, "warnings": warnings,
            "outputs": outputs, "inputs": inputs,
        }

    bidir = list(PINS_BIDIR)
    in_only = list(PINS_IN_ONLY)
    for s in outputs:
        mcu[s] = bidir.pop(0)
    # 1-Wire is open-drain and must have a bidirectional pin.  Reserve it
    # BEFORE the buttons/DO inputs so adding a UI button can never silently
    # move the shared ID bus to an input-only GPIO.
    mcu["ONEWIRE"] = bidir.pop(0)
    for s in inputs:
        mcu[s] = (bidir or in_only).pop(0)

    return {
        "mcu": mcu,
        "expander": {},
        "needs_expander": False,
        "mcu_signals": need,
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

ANALOG_WALL_X = CONST["AN_X"]     # shell frame, left inner side wall
DIGITAL_WALL_X = CONST["DI_X"]    # shell frame, right inner side wall


def board_xy(shell_x, shell_y):
    """Shell (mm) -> board-local (mm, origin at board lower-left)."""
    return (shell_x - PCB_X0, shell_y - PCB_Y0)


# Upright boards plug into sockets whose pin lines run front-to-back: a board
# stands in the X-Z plane and faces inward across the central channel.  Analog
# bank on the left wall, digital bank on the right; both rows on the same four
# Y stations so the two faces look directly at each other.
ANALOG_HEADERS = [board_xy(ANALOG_WALL_X, y) for y in CONST["AN_Y"]]
DIGITAL_HEADERS = [board_xy(DIGITAL_WALL_X, y) for y in CONST["DI_Y"]]

# --- rail budgets (design average, ampere; ESP32 peak ~0.5 A transient) -----
# 5 V: eight 150 mA MOX heaters + fan + buzzer.  The USB-C input and the board
# net are sized for 1.5 A continuous; a 5 V/2 A source is the stated supply.
RAILS = {
    "5V": {"MOX heaters": 0.15 * N_SLOTS, "fan": 0.15, "buzzer": 0.03},
    "3V3": {"ESP32 (avg)": 0.15, "Qwiic modules": 0.05 * N_SLOTS,
            "adc+mux+sht31": 0.10},
}


def railtotals():
    return {rail: round(sum(v.values()), 3) for rail, v in RAILS.items()}


def summary():
    return {
        "n_slots": N_SLOTS, "n_analog": N_ANALOG, "n_digital": N_DIGITAL,
        "slot": SLOT, "qwic": QWIC,
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
    for n in (4, 8, 12, 16):
        pm = build_pinmap(n)
        tag = "expander" if pm["needs_expander"] else "MCU-only"
        print("%2d slots: %2d signals / %d capacity -> %s %s"
              % (n, pm["mcu_signals"], pm["capacity"], tag,
                 pm["warnings"] or ""))
