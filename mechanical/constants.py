"""OpenSmell v1.1 single source of truth for all CAD geometry (millimetres).

Every generator and the parametric FreeCAD model import CONST from here.
NEVER re-type these numbers anywhere else: the sketches, the parametric 3D
model, and the fabrication DXF output all derive from this one dict, so a
design change is a one-line edit followed by a full regenerate.

Coordinate frame (mm), origin = front-lower-left outer corner of the shell:
  X = width  (0..122)
  Y = depth  (front = 0 .. rear = 114, + the 4 mm fan plate)
  Z = height (0..49, up)

The architecture is the one a builder can hold in their head:

    tray  ->  board on four standoffs  ->  modules plug into the headers
          ->  flat lid, four M3 screws  ->  done.

There is no baffle plate, no plenum, no flow lane and no well.  The sample
enters through three nostrils in the front wall, crosses a serviceable filter
pad, flows over the module row (digital upstream, analog downstream) and leaves
through a 40 mm fan in the back.  The board's top face is the chamber floor, so
"plug a module in" is exactly what it sounds like.

Flow order is front -> rear: 3 nostril inlets (front wall) -> filter pad ->
digital row -> analog row -> rear fan.  The small, cold digital breakouts are
upstream so the 4 MOX heaters of the analog row sit last: ~0.9 W each, the
biggest heat load in the box, and they consume VOC (a net sink) and desorb
during purge, so nothing sits behind them.
"""

CONST = {
    # outer envelope (the fan itself stands 10 mm proud of the rear face)
    "SH": 122.0, "SW": 114.0, "SHH": 49.0,
    # walls / floor / lid
    "WALL": 3.0, "FLOOR_T": 3.0, "LID_T": 6.0,
    # cavity: inside the walls, above the floor, under the lid
    "CX": 116.0, "CY": 108.0, "CH": 40.0,
    # PCB on four standoffs, component side up; its top face is the chamber floor
    "PCB_X": 114.0, "PCB_Y": 105.0, "PCB_T": 1.6, "PCB_Z": 7.0,
    "STANDOFF_D": 6.0,
    # lid: 4 x M3 into heat-set inserts in corner bosses
    "BOSS_D": 8.0, "BOSS_INSET": 6.5,
    "SCREW_D": 3.4, "CBORE_D": 6.2, "CBORE_T": 3.2,
    # module sockets, in SHELL coordinates: these are the as-built PCB header
    # positions (board origin is at 4.0, 4.5), so the enclosure and the board
    # agree by construction.  A 1 x 6 keyed 2.54 mm socket per slot (OSM-1).
    # A cartridge extends 32 mm from the pin line; rows are 42 mm apart so the
    # two rows cannot touch.  Pitch is a BASE parameter (26 / 21 mm here), not a
    # module rule: a module only has to fit the socket and the envelope.
    "A_X": [22.0, 48.0, 74.0, 100.0], "A_Y0": 75.0,   # analog row, downstream
    "D_X": [29.5, 50.5, 71.5, 92.5], "D_Y0": 33.0,    # digital row, upstream
    "SOCK_N": 6, "SOCK_P": 2.54, "SOCK_H": 8.5,
    # nostrils: 3 x d6 on the front wall, pitch 26, centred, above the modules
    "NO_R": 3.0, "NO_Z": 30.0, "NO_PITCH": 26.0,
    # USB-C: d12 bulkhead hole for a panel-mount pigtail, in the dead zone
    # below the filter (the only place a cable can live without wetting)
    "USB_R": 6.0, "USB_X": 14.0, "USB_Z": 10.0,
    # filter drawer: a 110 x 4 x 23 pad slides down between two side rails and
    # is held by the lid.  It is the only consumable, and it costs cents.
    "FILT_Z0": 20.0, "FILT_T": 4.0,
    "RAIL_W": 3.0, "RAIL_D": 5.0,
    # fan: d40 x t10 on the rear plate, axis +Y, pulling air out of the box
    "FAN_R": 19.0, "FAN_T": 10.0, "FAN_Z": 23.0, "FAN_X": 61.0,
    "FAN_PLATE": 44.0, "FAN_PLATE_T": 4.0,
}

# Derived, so "the lid sits on the wall tops" and "the board top is the chamber
# floor" are identities rather than coincidences.
CONST["CX0"] = CONST["WALL"]
CONST["CY0"] = CONST["WALL"]
CONST["CX1"] = CONST["WALL"] + CONST["CX"]
CONST["CY1"] = CONST["WALL"] + CONST["CY"]
CONST["CAV_Z0"] = CONST["FLOOR_T"]
CONST["CAV_Z1"] = CONST["FLOOR_T"] + CONST["CH"]
CONST["LID_Z0"] = CONST["CAV_Z1"]
CONST["LID_Z1"] = CONST["LID_Z0"] + CONST["LID_T"]
CONST["PCB_TOP"] = CONST["PCB_Z"] + CONST["PCB_T"]
CONST["FILT_Z1"] = CONST["CAV_Z1"]

# Material / process decision (engineering rationale -- see DRAWINGS_NOTES):
#   The wetted flow path (anything the sample gas touches) sets carryover
#   ("memory"), background off-gassing and humidity sorption, so it dominates
#   olfaction fidelity.  Structural parts stay in a stiff, dimensionally stable
#   polymer; the inert polymer is used only where gas touches it (the filter
#   frame and, optionally, a PTFE liner sheet).
PROCESS = {
    "shell": {
        "primary": "PETG, FDM 0.2 mm, 4 perimeters, vapor-sealed inner cavity",
        "substitute": "AL 6061-T6 CNC (toleranced dims unchanged)",
        "finish": "as-printed, de-flash; wetted faces seamed/sealed",
    },
    "lid": {
        "primary": "PETG, FDM 0.2 mm, 4 perimeters (same spool as the shell)",
        "substitute": "AL 6061-T6, 6 mm plate",
        "finish": "as-printed; mating face flat within 0.2",
    },
    "tolerance_general": "ISO 2768-mK",
    "tolerance_critical": "0.05",
}
