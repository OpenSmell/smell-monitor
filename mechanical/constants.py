"""OpenSmell v1.1 single source of truth for all CAD geometry (millimetres).

Every generator and the parametric FreeCAD model import CONST from here.
NEVER re-type these numbers anywhere else: the sketches, the parametric 3D
model, and the fabrication DXF output all derive from this one dict, so a
design change is a one-line edit followed by a full regenerate.

Coordinate frame (mm), origin = front-lower-left outer corner of the shell:
  X = width  (slot axis, 0..122)
  Y = depth  (front=0 .. rear=114)
  Z = height (0..90, up)

Flow order is front -> rear: 3 nostril inlets (front wall) -> digital row ->
analog row -> rear taper duct -> fan exhaust.  The small, cold digital
breakouts are upstream so the 4 MOX heaters of the analog row sit last: ~0.9 W
each, the biggest heat load in the box, and they consume VOC (a net sink) and
desorb during purge, so nothing sits behind them.
"""

CONST = {
    # shell outer
    "SH": 122.0, "SW": 114.0, "SHH": 90.0,
    # walls / floor
    "WSIDE": 8.0, "WFB": 7.0, "FLOOR": 12.0,
    # cavity interior 106 x 100 x 48, centred
    "CX": 106.0, "CY": 100.0, "CH": 48.0,
    # baffle plane: 37 mm above the *chamber floor* (see PCB_Z below)
    "BAFFLE_Z": 12.0 + 37.0, "BAFFLE_T": 2.0,
    # well/row layout (seat to blueprint.md 4.6): 4 digital (front, upstream)
    # + 4 analog (rear, downstream).  Slot geometry is sized to the worst-case
    # breakout: analog 22 wide x 35 long x 23 can; digital <= 26 x 23 x 8.
    "A_X": [22, 48, 74, 100],                          # analog centres, pitch 26
    "A_SX": 22.0, "A_SY": 18.0, "A_Y0": 66.0,          # slot x-width, y-depth, y-start
    "D_X": [29.5, 50.5, 71.5, 92.5],                   # digital, pitch 21
    "D_SX": 18.0, "D_SY": 16.0, "D_Y0": 25.0,
    # reference T/RH port: the SHT31 (U5) is soldered on the board, so it is
    # behind the baffle unless the plate is opened over it.  Without this the
    # compensation backbone (blueprint 4.3) is sealed out of the gas path.
    "SHT_X": 18.0, "SHT_SX": 16.0, "SHT_Y0": 44.0, "SHT_SY": 12.0,
    # PCB: the board is the sealed chamber FLOOR.  Its top face is flush with
    # the cavity floor (z = FLOOR), which is what makes "baffle 37 mm above
    # board" + "29 mm module allowance" + "8 mm sensor recess" add up
    # (12 + 37 = 49 = BAFFLE_Z; 12 + 29 = 41; 49 - 41 = 8).
    "PCB_X": 114.0, "PCB_Y": 105.0, "PCB_T": 1.6,
    # nostrils: 3 x d6 bellmouth on front wall, pitch 26, centred x=61.
    # NO_Z must keep the full bore inside the flow lane (BAFFLE_Z..FLOOR+CH).
    "NO_R": 3.0, "NO_Z": 55.0, "NO_Y": 0.0,
    # filter pack: a SERIES element spanning the full lane cross-section
    # immediately behind the nostrils (blueprint.md 3.4/3.6).  Pleated: a flat
    # 106 x 11 face is 11.7 cm2 and 3.6 needs >= 70 cm2 for <= 2 Pa clean.
    "FILT_T": 4.0, "FILT_Y0": 14.0,
    # fan: d40 x t10, axis along Y (rear exhaust), centred
    "FAN_R": 20.0, "FAN_T": 10.0, "FAN_Z": 30.0, "FAN_Y": 107.0, "FAN_X": 61.0,
    "DUCT_H": 48.0,  # taper duct from cavity rear face down to fan
}

# derived, so "the board is the chamber floor" is an identity, not a coincidence
CONST["PCB_Z"] = CONST["FLOOR"] - CONST["PCB_T"]      # board top face == CAV_Z0

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
        "finish": "deburr; 8 open-bottom wells + 1 sensor port, d/w to CONST",
    },
    "tolerance_general": "ISO 2768-mK",
    "tolerance_critical": "0.05",
}
