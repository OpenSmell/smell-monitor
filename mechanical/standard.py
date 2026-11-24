#!/usr/bin/env python3
"""OpenSmell Module Standard v1 (OSM-1) - the machine-readable contract.

``docs/module-standard.md`` is the prose a module maker reads; this file
is the same rules as data, so ``tools/verify_module_fit.py`` can check the
chamber, the socket contract and the module database against them instead of a
paragraph. Nothing here is a wish: every number is either the mainstream
dimension of a part the market actually sells or a deliberate consequence of
the flat-mounted pose (blueprint 4.5).

THE ONE IDEA
------------
There is a single slot design, repeated. A slot is not "analog" or "digital":
it carries a keyed 5 V gas-cell socket *and* a 3.3 V Qwiic port on the same
footprint. The user fills the slots with whatever chemistry the job
needs. The host application maps each slot to a sensor type and calibration;
v1 firmware does not enumerate per-slot identity devices. That is what removes
the 4-analog / 4-digital split, the wrong-row mistake and the "which sensor can
I not use" ceiling at the same time.

Units: mm, V, mA.
"""

STANDARD_REV = 1
DOC = "docs/module-standard.md"

# --- the cartridge: a 5 V gas cell on the user's side of the socket ----------
# The pose is FIXED by the product architecture: breakout boards plug into the
# two inner side-wall rows, stand UPRIGHT and FACE INWARD across a clear central
# channel.  The socket pin line runs front-to-back, so a straight 1x6 header
# leaves the card in the Y-Z plane, its face normal along X.  Gas enters at the
# front nostrils, travels down the middle between the facing rows and is drawn
# out by the rear fan.  The sockets are inset WALL_GAP from each inner wall so a
# breakout board with pins or a component on its BACK clears the wall: that is
# the rear-pin housekeeping margin, not a connector option.
CARTRIDGE = {
    "conn": "2.54 mm keyed 1x6, straight male header on the card edge",
    "pins": ["+5V", "GND", "AO", "DO", "3V3", "ID"],
    "pose": "upright: card perpendicular to the board, face inward across the "
            "central channel, removed upward",
    # Height is measured vertically from the socket pin line: an 8.5 mm socket
    # sits on a board top at z = 8.6, so a 32 mm card tops out at z = 49.1.  The
    # cavity ceiling is at z = 54, leaving a 4.9 mm flow hood over the card.
    # "reach" is how far the cell/mesh protrudes INTO the channel (along X);
    # "back_clear" is the reserved gap BEHIND the card (toward the side wall)
    # for rear pins and through-hole tails.  If the hood comes out slow in CFD,
    # the fix is more wall height (CH), not a new pose.
    "envelope": {"across": 20.0, "height": 32.0, "reach": 21.0},
    "back_clear": 13.0,         # WALL_GAP: space behind the card for rear pins
    "sensor_zone": None,        # no window to align to; element is free on the card
    "rail_mA": {"5V": 150, "3V3": 50},
    "source_mV": 5000,          # AO may swing to 5 V; the base divides it 10k/10k
    "protocols": ["analog 0-5 V on AO", "TTL serial 9600 8N1 on DO"],
    "id": "required",
    "key": "1x6 header, pin-1 chamfer plus a polarising slot in the socket wall",
}

# --- the port: a 3.3 V I2C module, cabled (the mainstream I2C standard) ------
PORT = {
    "conn": "JST-SH 1.0 mm 4-pin (Qwiic / STEMMA QT)",
    "pins": ["GND", "3V3", "SDA", "SCL"],
    "fallback": "0.1 in pads carrying the same four signals, in parallel",
    "rail_mA": {"3V3": 50},
    "protocols": ["I2C, one TCA9548A channel per slot"],
    "id": "I2C probe / WHO_AM_I; no EEPROM needed on a Qwiic module",
    "adapters": "Grove (2.0 mm JST-PH) and Gravity carry the same 4 signals "
                "and work through an adapter cable",
}

# --- identity: HOST-MANAGED IN v1 ------------------------------------------
# The ID pin is wired to one shared 1-Wire bus on the base.  v1 firmware does
# NOT enumerate per-slot ROMs: all eight pins are in parallel, and the .osmell
# identity/calibration fields are filled by the host application.  The memory
# map below is kept as a RESERVED future cartridge option; it is not a v1
# conformance requirement and no gate may assume a chip is present.
ID_EEPROM = {
    "bus": "1-Wire (one MCU GPIO for all slots)",
    "parts": ["DS2431", "AT21CS01"],
    "bytes": 128,
    "magic": b"OSM1",
    "map": [
        (0x00, 4, "magic 'OSM1'"),
        (0x04, 1, "standard revision"),
        (0x05, 1, "kind: 1 gas cell, 2 I2C module"),
        (0x06, 1, "class: 1 MOX, 2 EC, 3 NDIR, 4 PID, 5 T/RH, 6 PM, 7 other"),
        (0x07, 1, "flags: heater, needs purge, needs 5 V"),
        (0x08, 8, "part number, ASCII"),
        (0x10, 4, "lot / serial"),
        (0x14, 2, "first use, year+month (0 = virgin)"),
        (0x16, 4, "accumulated exposure hours"),
        (0x1A, 2, "peak temperature seen, int16, 0.1 degC"),
        (0x1C, 4, "rail requirement: mV, mA"),
        (0x20, 32, "calibration blob, defined per class"),
        (0x40, 63, "reserved for the module maker"),
        (0x7F, 1, "checksum over 0x00-0x7E"),
    ],
}

# --- the wetted path: why this does not die in the field --------------------
# The classic MOX death is silicone poisoning: silicone vapour cracks on the hot
# SnO2 surface into a silica layer that permanently kills the response. It comes
# from the assembly, not the sample.
MATERIALS = {
    "banned": ["silicone (sealant, adhesive, grease, tubing, wire insulation, "
               "conformal coat)", "PVC tubing or insulation", "bare zinc",
               "paper or card", "foam"],
    "allowed": ["PTFE", "PFA / FEP", "PVDF", "borosilicate glass",
                "316 stainless", "gold- or nickel-plated contacts",
                "PTFE-insulated wire", "non-silicone epoxy outside the path"],
    "filter": "hydrophobic PTFE (WEP >= 350 mbar) behind a 5-20 um particulate "
              "pre-filter, pleated, spanning the full lane cross-section; no "
              "carbon in series with the sample (it strips the analyte - carbon "
              "belongs on a reference-air path, blueprint 6.3/13)",
}

# --- the base: one slot design, repeated ------------------------------------
# The reference base keeps the 122 x 114 mm shell footprint (taller to stand a
# card upright). The two rows are the two inner side walls; pitch is measured
# front-to-back along each wall and is a base parameter, not a module rule:
# 24 mm as built, and a cartridge only has to be <= 20 mm wide along the wall.
SLOTS = {
    "reference_count": 8,
    "rows": 2,                  # the two opposing inner side walls
    "per_row": 4,
    "pitch": 24.0,              # along each wall (front-to-back)
    "pitch_min": 22.0,          # >= envelope.across (20) + 2 mm gap
    "max_width": 20.0,          # a cartridge is at most this wide along the wall
    "reach": 21.0,              # from its face INTO the central channel
    "back_clear": 13.0,         # behind the card, reserved for rear pins
    "ports_per_slot": ["gas cell socket", "Qwiic port"],
    "channels": {"mux": 8, "adc": 2, "onewire": 1},
    "growth": "slot count is a constant: more slots is a wider base, or an "
              "expansion head on the same sample line. The socket never "
              "changes, so a cell moves with the user.",
    "flow": "two inward-facing side-wall rows share one central channel: every "
            "record carries the slot index and wall so the host can model any "
            "uptake gradient between the banks. The nostrils and fan share the "
            "channel centreline.",
}


def checklist():
    """Everything a module must satisfy to be called OSM-1 conforming."""
    c = CARTRIDGE
    return [
        "1x6 keyed 2.54 mm header, pinout %s" % " ".join(c["pins"]),
        "upright outline <= %.0f across the wall x %.0f high"
        % (c["envelope"]["across"], c["envelope"]["height"]),
        "cell/mesh protrudes <= %.0f mm into the central channel, with >= %.0f "
        "mm reserved behind the card for rear pins"
        % (c["envelope"]["reach"], c["back_clear"]),
        "sensing element anywhere on the card, facing inward across the channel",
        "identity/calibration registered in the host slot map (EEPROM optional, reserved map in ID_EEPROM)",
        "output analog 0-5 V on AO, or TTL serial 9600 8N1 on DO",
        "power <= %.0f mA at 5 V and <= %.0f mA at 3.3 V"
        % (c["rail_mA"]["5V"], c["rail_mA"]["3V3"]),
        "wetted materials per MATERIALS: no silicone, no PVC",
        "marked: part number, class, lot, polarity key",
    ]


def id_map():
    """Reserved future cartridge EEPROM map; optional, not used by v1 firmware."""
    return [(a, n, t) for a, n, t in ID_EEPROM["map"]]


if __name__ == "__main__":
    print("OpenSmell Module Standard v1 (rev %d)" % STANDARD_REV)
    print("doc:", DOC)
    print("cartridge:", CARTRIDGE["conn"])
    print("port:     ", PORT["conn"])
    print("slots:     %d = %d rows of %d, pitch is a base parameter "
          "(>= %.0f mm)" % (SLOTS["reference_count"], SLOTS["rows"],
                            SLOTS["per_row"], SLOTS["pitch_min"]))
    print()
    for line in checklist():
        print("  ", line)
