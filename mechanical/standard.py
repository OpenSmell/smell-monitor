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
it carries a keyed 5 V gas-cell socket *and* a 3.3 V Qwiic port, over its own
window in the plate. The user fills the slots with whatever chemistry the job
needs; the module's own identity decides how the base talks to it. That is what
removes the 4-analog / 4-digital split, the wrong-row mistake and the "which
sensor can I not use" ceiling at the same time.

Units: mm, V, mA.
"""

STANDARD_REV = 1
DOC = "docs/module-standard.md"

# --- the cartridge: a 5 V gas cell on the user's side of the socket ----------
# Flat because a MOX can's gas inlet is its END FACE, not its barrel: standing
# a card in a socket points the inlet sideways at its neighbour instead of at
# the window. Flat also removes the 40-48 mm standing height that collided with
# the baffle plate.
CARTRIDGE = {
    "conn": "2.54 mm keyed 1x6, right-angle male header on the card edge",
    "pins": ["+5V", "GND", "AO", "DO", "3V3", "ID"],
    "pose": "flat: card parallel to the board, sensing face up, removed upward",
    # Height is the cartridge's own, not the distance to the plate: on a
    # vertical socket it rides ~8.5 mm up, so its top ends ~4 mm under the
    # 37 mm plate and the plate is the service lid (docs/module-standard.md 4).
    "envelope": {"across": 22.0, "along": 40.0, "height": 26.0},
    "sensor_zone": {"size": (20.0, 20.0), "offset_from_face": 16.0},
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

# --- identity: one 1-Wire EEPROM on the cartridge's ID pin ------------------
# One pin on the base serves every slot: every 1-Wire part carries a unique
# 64-bit ROM, so there is no address scheme and no extra mux. This is the TEDS
# idea from IEEE 1451 in one wire and 1 kbit.
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
# The reference base keeps today's 122 mm shell. Four slots at a 24 mm pitch
# span 96 mm inside a 106 mm cavity, so uniformity costs no size at all - it is
# the same box with one repeat unit instead of two different ones.
SLOTS = {
    "reference_count": 8,
    "rows": 2,
    "per_row": 4,
    "pitch": 24.0,              # >= envelope.across (22) + 2 mm
    "window": (20.0, 20.0),     # equals CARTRIDGE.sensor_zone.size
    "ports_per_slot": ["gas cell socket", "Qwiic port"],
    "channels": {"mux": 8, "adc": 2, "onewire": 1},
    "growth": "slot count is a constant: more slots is a wider base, or an "
              "expansion head on the same sample line. The socket never "
              "changes, so a cell moves with the user.",
    "cascade": "the base is a cascade, not 8 parallel chambers: every record "
               "carries the slot index and its position in the flow so the "
               "software can model depletion. Put the cells you trust most "
               "upstream.",
}


def checklist():
    """Everything a module must satisfy to be called OSM-1 conforming."""
    c = CARTRIDGE
    return [
        "1x6 keyed 2.54 mm header, pinout %s" % " ".join(c["pins"]),
        "flat outline <= %.0f across x %.0f along x %.0f high"
        % (c["envelope"]["across"], c["envelope"]["along"],
           c["envelope"]["height"]),
        "sensing element centred %.0f mm downstream of the connector face, "
        "inside a %gx%g mm zone"
        % (c["sensor_zone"]["offset_from_face"], *c["sensor_zone"]["size"]),
        "EEPROM per ID_EEPROM.map, checksum valid",
        "output analog 0-5 V on AO, or TTL serial 9600 8N1 on DO",
        "power <= %.0f mA at 5 V and <= %.0f mA at 3.3 V"
        % (c["rail_mA"]["5V"], c["rail_mA"]["3V3"]),
        "wetted materials per MATERIALS: no silicone, no PVC",
        "marked: part number, class, lot, polarity key",
    ]


def id_map():
    return [(a, n, t) for a, n, t in ID_EEPROM["map"]]


if __name__ == "__main__":
    print("OpenSmell Module Standard v1 (rev %d)" % STANDARD_REV)
    print("doc:", DOC)
    print("cartridge:", CARTRIDGE["conn"])
    print("port:     ", PORT["conn"])
    print("slots:     %d = %d rows of %d at a %.0f mm pitch"
          % (SLOTS["reference_count"], SLOTS["rows"], SLOTS["per_row"],
             SLOTS["pitch"]))
    print()
    for line in checklist():
        print("  ", line)
