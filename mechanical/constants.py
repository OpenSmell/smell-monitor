"""OpenSmell v1.1 single source of truth for all CAD geometry (millimetres).

Every generator and the parametric FreeCAD model import CONST from here.
NEVER re-type these numbers anywhere else: the sketches, the parametric 3D
model, and the fabrication DXF output all derive from this one dict, so a
design change is a one-line edit followed by a full regenerate.

Coordinate frame (mm), origin = front-lower-left outer corner of the shell:
  X = width  (slot axis, 0..226)
  Y = depth  (front=0 .. rear=114)
  Z = height (0..90, up)
"""

CONST = {
    # shell outer
    "SH": 122.0, "SW": 114.0, "SHH": 90.0,
    # walls / floor
    "WSIDE": 8.0, "WFB": 7.0, "FLOOR": 12.0,
    # cavity interior 106 x 100 x 48, centred
    "CX": 106.0, "CY": 100.0, "CH": 48.0,
    # baffle plane: 37 mm above cavity floor
    "BAFFLE_Z": 12.0 + 37.0, "BAFFLE_T": 2.0,
    # well/row layout (seat to blueprint.md 4.6): 4 analog + 4 digital
    "A_X": [22, 48, 74, 100],                          # analog centres, pitch 26
    "A_SX": 22.0, "A_SY": 18.0, "A_Y0": 25.0,          # slot x-width, y-depth, y-start
    "D_X": [29.5, 50.5, 71.5, 92.5],                   # digital, pitch 21
    "D_SX": 18.0, "D_SY": 16.0,
    # nose column openings (baffle open-space above nozzle row) -- digital row column 4
    "NOSEY": 66.0,
    # PCB lid
    "PCB_X": 114.0, "PCB_Y": 105.0, "PCB_T": 1.6, "PCB_Z": 60.0 - 1.6,
    # nostrils: 3 x d6 bellmouth on front wall, pitch 26, centred x=61
    "NO_R": 3.0, "NO_Z": 58.0, "NO_Y": 0.0,
    # filter slab in intake plenum (above baffle, behind nostrils)
    "FILT_T": 4.0,
    # fan: d40 x t10, axis along Y (rear exhaust), centred
    "FAN_R": 20.0, "FAN_T": 10.0, "FAN_Z": 30.0, "FAN_Y": 107.0, "FAN_X": 61.0,
    "DUCT_H": 48.0,  # taper duct from cavity rear face down to fan
}

# Material / process decision (engineering rationale -- see DRAWINGS_NOTES):
#   The wetted flow path (anything the sample gas touches) sets carryover
#   ("memory"), background off-gassing and humidity sorption, so it dominates
#   olfaction fidelity. Therefore the inert polymer is used ONLY where gas
#   touches it; structural parts stay in a stiff, dimensionally stable polymer
#   (PTFE creeps and has high CTE -> would drift the 26/21 mm pitches).
PROCESS = {
    "shell": {
        "primary": "PETG, FDM 0.2 mm, 4 perimeters, vapor-sealed inner cavity",
        "substitute": "AL 6061-T6 CNC (toleranced dims unchanged)",
        "finish": "as-printed, de-flash; wetted faces seamed/sealed",
    },
    "baffle": {
        "primary": "PTFE, machined (inert, non-porous, hydrophobic)",
        "substitute": "PVDF (Kynar) or borosilicate glass (3.0 mm)",
        "finish": "deburr; 16 open-bottom wells d/w to CONST",
    },
    "tolerance_general": "ISO 2768-mK",
    "tolerance_critical": "0.05",
}
