"""OpenSmell v1.1 single source of truth for all CAD geometry (millimetres).

Every generator and the parametric FreeCAD model import CONST from here.
NEVER re-type these numbers anywhere else: the sketches, the parametric 3D
model, and the fabrication DXF output all derive from this one dict, so a
design change is a one-line edit followed by a full regenerate.

Coordinate frame (mm), origin = front-lower-left outer corner of the shell:
  X = width  (0..122)
  Y = depth  (front = 0 .. rear = 114, + the 4 mm fan plate)
  Z = height (0..60, up)

The architecture is fixed and non-negotiable:

    tray  ->  board on four standoffs  ->  breakout boards plug into two
    opposing inner SIDE-WALL header rows, stand UPRIGHT and FACE INWARD
    across a clear central channel  ->  flat lid, four M3 screws  ->  done.

Gas enters through three nostrils in the front wall, travels straight down the
central channel ("a red carpet") between the two facing rows, and is pulled out
by the 40 mm fan in the rear wall.  Nostrils are centred on that channel, not on
the walls, and spaced to flood it evenly.  The sockets are inset from the inner
side walls so a breakout board with pins or a tall component on its back has
room and never touches the wall.
"""

CONST = {
    # outer envelope (the fan itself stands 10 mm proud of the rear face)
    "SH": 122.0, "SW": 114.0, "SHH": 60.0,
    # walls / floor / lid
    "WALL": 3.0, "FLOOR_T": 3.0, "LID_T": 6.0,
    # cavity: inside the walls, above the floor, under the lid
    "CX": 116.0, "CY": 108.0, "CH": 51.0,
    # PCB on four standoffs, component side up; its top face is the chamber floor
    "PCB_X": 114.0, "PCB_Y": 105.0, "PCB_T": 1.6, "PCB_Z": 7.0,
    "STANDOFF_D": 6.0,
    # lid: 4 x M3 into heat-set inserts in corner bosses.  The bosses stand
    # inside the board footprint (they carry the lid), so the board gets a
    # BOSS_D/2 + BOSS_CLEAR cut-out at each one - one number shared by the
    # enclosure model and the PCB Edge.Cuts.
    "BOSS_D": 8.0, "BOSS_INSET": 6.5, "BOSS_CLEAR": 0.3,
    "SCREW_D": 3.4, "CBORE_D": 6.2, "CBORE_T": 3.2,
    # ---- the two UPRIGHT, INWARD-FACING side-wall socket rows -------------
    # Left row at shell x = WALL + WALL_GAP, right row mirrored about the shell
    # centre line.  WALL_GAP is the clear space between the inner face of the
    # side wall and the socket pin line: it is the room a board needs for pins
    # or a component on its BACK, so an upright breakout never fouls the wall.
    # Socket pin lines run FRONT-TO-BACK (along Y): a board plugged straight in
    # therefore stands in the Y-Z plane and its face looks across the channel.
    # Four sockets per wall on a 24 mm pitch along Y, centred in the cavity.
    "WALL_GAP": 13.0,
    "SOCK_X_L": 16.0, "SOCK_X_R": 106.0,
    "ROW_Y": [24.0, 48.0, 72.0, 96.0],
    # one wall per bank; all eight sockets are electrically identical (OSM-1)
    "AN_X": 16.0, "AN_Y": [24.0, 48.0, 72.0, 96.0],   # analog bank, left wall
    "DI_X": 106.0, "DI_Y": [24.0, 48.0, 72.0, 96.0],  # digital bank, right wall
    "SOCK_N": 6, "SOCK_P": 2.54, "SOCK_H": 8.5,
    # an upright board rises 32 mm above the socket pin line; its can/probe
    # protrudes ~21 mm into the channel.  Both numbers are verified downstream.
    "CARD_H": 32.0, "CARD_REACH": 21.0,
    # nostrils in the FRONT wall, on the central channel (not the walls),
    # spaced NO_PITCH mm so the jets flood the channel evenly.  Z is centred on
    # the upright cards' sensing height.  NO_COUNT selects how many; NO_PITCH is
    # the centre-to-centre spacing between adjacent nostrils.
    "NO_COUNT": 3, "NO_R": 3.0, "NO_Z": 33.0, "NO_PITCH": 14.0,
    # USB-C: d12 bulkhead hole for a panel-mount pigtail, in the dead zone
    # below the channel (the only place a cable can live without wetting).
    # X is pinned to J1's board position plus the board origin (14 + 4), so the
    # pigtail plugs straight into the receptacle instead of jogging sideways.
    "USB_R": 6.0, "USB_X": 18.0, "USB_Z": 10.0,
    # filter drawer: a 110 wide x 4 deep slot slides down between two side
    # rails and is held by the lid.  It carries THIN WOVEN PTFE MESH; the mesh
    # is the only consumable.  A 4 mm sintered panel would drop ~3.8 kPa at
    # 15 L/min against ~50 Pa of fan head, so it is physically impossible here.
    "FILT_Z0": 20.0, "FILT_T": 4.0,
    "RAIL_W": 3.0, "RAIL_D": 5.0,
    # fan: d40 x t10 on the rear plate, axis +Y, centred on the channel and the
    # nostrils, pulling air straight out of the back of the box.
    "FAN_R": 19.0, "FAN_T": 10.0, "FAN_Z": 33.0, "FAN_X": 61.0,
    "FAN_PLATE": 44.0, "FAN_PLATE_T": 4.0,
    # ---- local UI (v1.1 refresh): front-panel bezel + buttons -------------
    # The OLED sits in a shallow sealed bezel on the FIXED FRONT WALL, above
    # the nostrils and clear of the USB-C/filter openings.  Its cable and the
    # four button harness pass through one grommet in that same fixed wall to
    # the base board.  The lid is a plain flat plate: opening it never breaks
    # an electrical connection.
    "DISP_X": 61.0, "DISP_Z": 45.0, "DISP_W": 30.0, "DISP_H": 17.0,
    "DISP_WIN_W": 27.0, "DISP_WIN_H": 13.0, "DISP_POD_D": 6.0,
    "DISP_GASKET": 1.0, "UI_FEED_D": 6.0,
    "UI_FEED_X": 82.0, "UI_FEED_Z": 45.0,
    # Four front-panel buttons: MEASURE/OK, MENU/BACK, BOOT, RESET.  Routine
    # updates are OTA; BOOT/RESET remain reachable on the panel for recovery
    # without opening the enclosure.
    "BTN_HOLE_D": 3.4,
    "BTN_FRONT": {"MEASURE": (88.0, 49.0), "MENU": (100.0, 49.0),
                  "BOOT": (88.0, 39.0), "RESET": (100.0, 39.0)},
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
# The pad starts behind the front bosses (their radius sets the offset), plus
# 0.3 mm so the pad drops in and the rail never shares a tangent face with a
# boss (a coincident contact makes the fused shell non-manifold).
CONST["FILT_Y0"] = CONST["BOSS_INSET"] + CONST["BOSS_D"] / 2.0 + 0.3
CONST["FILT_Y1"] = CONST["FILT_Y0"] + CONST["FILT_T"]
# Hood over an upright board: clear air between the top of the 32 mm card and
# the underside of the lid.  This is the flow hood the CFD case reports on.
CONST["CARD_TOP"] = CONST["PCB_TOP"] + CONST["SOCK_H"] + CONST["CARD_H"]
CONST["HOOD"] = CONST["LID_Z0"] - CONST["CARD_TOP"]
# Board origin, shared with interface.py.
CONST["PCB_X0"] = (CONST["SH"] - CONST["PCB_X"]) / 2.0
CONST["PCB_Y0"] = (CONST["SW"] - CONST["PCB_Y"]) / 2.0
CONST["DISP_X0"] = CONST["DISP_X"] - CONST["DISP_W"] / 2.0
CONST["DISP_Z0"] = CONST["DISP_Z"] - CONST["DISP_H"] / 2.0

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
