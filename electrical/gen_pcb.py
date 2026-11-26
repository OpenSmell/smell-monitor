#!/usr/bin/env python3
"""Generate the OpenSmell v1.1 PCB from the validated board model (board.py).

The board model owns the truth (which part, which pin, which net, which
footprint).  This script turns it into a real `.kicad_pcb` that KiCad can open,
DRC and hand to a fabricator:

  * board outline  = CONST['PCB_X'] x CONST['PCB_Y']  (114 x 105 mm) with four
    circular cut-outs of BOSS_D/2 + BOSS_CLEAR at the tray's lid bosses - the
    bosses stand inside the board footprint, so a rectangle cannot be fitted,
  * sensing headers live exactly on the chamber coordinates
    (interface.ANALOG_HEADERS / DIGITAL_HEADERS), so the board seats in the tray
    with no re-measurement,
  * one net per board.py net, wired to every pad by pin number.

Run with KiCad's own Python (it ships pcbnew):
  & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" electrical/gen_pcb.py

Three fine-pitch escapes (USB-C CC1/A5, USB-C D_N/A7+B7 and TCA9548A SD7/pin
19) are seeded from the proven baseline copper before routing - see
``SEED_TRACKS`` below.  Because the placed board then already contains copper,
route it with ``electrical/smell_monitor_v1_1/route_seeded.py`` (a thin wrapper
around the standard FreeRouting driver) rather than ``electrical/route_pcb.py``,
whose "fresh board" guard intentionally rejects any existing tracks.
"""
import math
import os
import sys

# KiCad ships its own interpreter, so the user site (kiutils, used by
# electrical/board.py) is not on its path by default: add every one we find.
import glob
for _p in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python3*\site-packages")):
    if os.path.isdir(_p):
        sys.path.append(_p)

sys.path.insert(0, r"C:\Users\PRAISE\AppData\Roaming\Python\Python313\site-packages")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pcbnew  # noqa: E402
import board as B  # noqa: E402
import interface as IF  # noqa: E402
from constants import CONST  # noqa: E402

FP_LIB = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"
PROJECT = "smell_monitor_v1_1"
OUT_DIR = os.path.join(HERE, PROJECT)
OUT_PCB = os.path.join(OUT_DIR, PROJECT + ".kicad_pcb")

PCB_W, PCB_D = CONST["PCB_X"], CONST["PCB_Y"]


def _pad_numbers(pin):
    """Model pin token -> real pad numbers.

    The ESP32 library symbol groups its four GND pads into one token,
    ``[1,15,38,39]``.  The board model keeps that token (the schematic symbol
    only has one logical pin), but the physical package has four separate pads
    and every one of them must get the GND net.
    """
    s = str(pin)
    if s.startswith("[") and s.endswith("]"):
        return [n.strip() for n in s[1:-1].split(",") if n.strip()]
    return [s]


# ---------------------------------------------------------------------------
# placement (board-local mm, origin lower-left, Y up).  Sensing headers come
# from the chamber contract; everything else is grouped by subsystem.
# ---------------------------------------------------------------------------
PLACE = {
    # --- sensing sockets: exactly on the chamber contract ------------------
    # J2..J5 are the LEFT inner side wall, J6..J9 the RIGHT.  Both rows are on
    # the same four front-to-back stations, so the boards face each other
    # across the central channel.  Positions come from interface; rotation 0
    # puts the 1x6 pin line ALONG Y, so a straight-header breakout stands
    # upright and its face looks inward.  See the loop after this dict.
    # --- Qwiic ports: one per slot, just inboard of its socket -------------
    # placed in the loop below so cable and connector stay inside the channel.
    # --- USB + power, front strip ------------------------------------------
    # J1 is 14 mm in, not 10: the tray's front-left boss needs an r = 4.3 mm
    # cut-out, and a USB-C receptacle whose courtyard reaches x = 4.7 would sit
    # inside it.  14 also puts the receptacle directly under the d12 bulkhead
    # hole, so the panel pigtail is a short, straight plug.
    "J1": (14.0, 6.0, 0),
    "R1": (21.0, 6.0, 0), "R2": (24.0, 6.0, 0),
    "U7": (31.0, 8.0, 0),
    "C13": (38.0, 6.0, 0),     # +5 V bulk at the LDO input
    "C9": (42.0, 6.0, 0), "C12": (46.0, 6.0, 0),
    "C10": (50.0, 6.0, 0), "C11": (54.0, 6.0, 0),
    # Both front-panel harnesses enter through the ONE grommet in the fixed
    # front wall at shell x = UI_FEED_X (82 mm) -> board x = 78.  J19 (display)
    # sits 6 mm to its left, J20 (buttons) 6 mm to its right; both are on the
    # front strip behind the filter rails, clear of the corner bosses.  Their
    # JST courtyards are 1.5 mm apart and end by y=15.3, 3.4 mm before the
    # Qwiic row at y=22.
    "J19": (72.0, 12.0, 0),
    "J20": (84.0, 12.0, 0),
    "R54": (65.0, 6.0, 0),     # BUTTON_MENU pull-up at the front strip
    # --- AO dividers + DO series, left of the centre line ------------------
    # Three shallow rows beside the side-wall sockets: DO series nearest the
    # sockets (short 5 V stub), then the two divider rows.
    "R19": (8.0, 33.0, 0), "R20": (11.5, 33.0, 0),
    "R21": (15.0, 33.0, 0), "R22": (18.5, 33.0, 0),
    "R23": (22.0, 33.0, 0), "R24": (25.5, 33.0, 0),
    "R25": (29.0, 33.0, 0), "R26": (32.5, 33.0, 0),
    "R3": (8.0, 37.0, 0), "R4": (36.5, 37.0, 0), "R5": (22.0, 26.0, 0),
    "R6": (18.5, 37.0, 0),
    "R7": (22.0, 37.0, 0), "R8": (25.5, 37.0, 0),
    "R9": (29.0, 37.0, 0), "R10": (32.5, 37.0, 0),
    "R11": (8.0, 40.5, 0), "R12": (36.5, 40.5, 0), "R13": (15.0, 30.0, 0),
    "R14": (18.5, 40.5, 0),
    "R15": (22.0, 40.5, 0), "R16": (25.5, 40.5, 0),
    "R17": (29.0, 40.5, 0), "R18": (32.5, 40.5, 0),
    # --- ADC pair + sensor + mux, centre band ------------------------------
    "U5": (12.0, 78.0, 0), "C5": (17.0, 48.0, 0),
    "U2": (26.0, 48.0, 0), "C3": (31.0, 48.0, 0),
    "U8": (38.0, 48.0, 0), "C6": (43.0, 48.0, 0),
    "U4": (52.0, 48.0, 0), "C4": (58.0, 48.0, 0),
    "U3": (94.0, 81.0, 90), "C7": (109.5, 50.0, 0),
    "C8": (109.5, 44.0, 0),
    # --- bus pull-ups + housekeeping --------------------------------------
    "R31": (36.0, 58.0, 0), "R32": (39.5, 58.0, 0),
    "R33": (43.0, 58.0, 0), "R37": (46.5, 58.0, 0),
    "R38": (8.0, 53.0, 0), "R39": (11.5, 53.0, 0),
    "R40": (15.0, 53.0, 0), "R41": (18.5, 53.0, 0),
    "R42": (22.0, 53.0, 0), "R43": (25.5, 53.0, 0),
    "R44": (29.0, 53.0, 0), "R45": (32.5, 53.0, 0),
    "R46": (8.0, 59.0, 0), "R47": (11.5, 56.0, 0),
    "R48": (15.0, 56.0, 0), "R49": (18.5, 59.0, 0),
    "R50": (22.0, 59.0, 0), "R51": (25.5, 59.0, 0),
    "R52": (29.0, 59.0, 0), "R53": (32.5, 59.0, 0),
    "R34": (84.0, 54.0, 0), "R35": (88.0, 54.0, 0), "R36": (92.0, 54.0, 0),
    # --- controller: at the top edge, antenna overhangs the board ---------
    # 94.4, not 95.0: at 95.0 the module outline silk pokes 0.18 mm past the
    # top Edge.Cuts and trips silk_edge_clearance.  The antenna keep-out still
    # overhangs the edge by >20 mm either way, so nothing electrical changes.
    # x moved 68.0 -> 69.1 only to open the notch under the antenna overhang
    # for J10 at the fan centre line (see J10 below); the keep-out still
    # overhangs the rear edge and no electrical contract changes.
    "U1": (69.1, 94.4, 0),
    "C1": (46.0, 92.0, 0), "C2": (50.0, 92.0, 0),
    # --- outputs, rear strip -----------------------------------------------
    # BZ1 moved from the rear-left corner (12, 93): the rear-left boss needs an
    # r = 4.3 cut-out and the buzzer's 10.2 mm body sat inside it.
    "BZ1": (24.0, 84.0, 0), "D1": (18.0, 92.0, 0),
    "Q2": (24.0, 92.0, 0),
    "R28": (29.0, 90.0, 0), "R29": (32.0, 90.0, 0),
    "LED1": (40.0, 94.0, 0), "R30": (36.5, 94.0, 0),
    "Q1": (92.0, 88.0, 0), "R27": (96.0, 88.0, 0),
    # Fan harness: shell x = PCB_X0 + 57 = 61 = FAN_X, and the connector sits
    # in the notch under the ESP32 antenna overhang as far rearward as DRC
    # allows (courtyard top y=104.20, 0.13 mm clear of U1's keep-out and
    # 0.80 mm inside Edge.Cuts).  Rotation 270 puts the 2 mm pin line along Y,
    # pointing the cable at the rear fan; the reference is moved clear in
    # tools/add_board_markings.py.
    "J10": (57.0, 100.7, 270),
}

# The eight gas-cell sockets are derived from the chamber contract
# (interface.ANALOG_HEADERS / DIGITAL_HEADERS), never typed twice.  Rotation 0
# runs the 1x6 pin line front-to-back: a straight header plugged in stands the
# breakout in the Y-Z plane, facing across the channel.
for _bank, _refs in (("analog", range(2, 6)), ("digital", range(6, 10))):
    _hdr = IF.ANALOG_HEADERS if _bank == "analog" else IF.DIGITAL_HEADERS
    for _ref, (_x, _y) in zip(_refs, _hdr):
        PLACE[f"J{_ref}"] = (_x, _y, 0)

# Qwiic ports stay on the proven, DRC-clean interior grid: two rows of four,
# clear of both side-wall socket columns.  Each is tied to its slot by netlist
# and silkscreen, so location does not carry sensor identity (OSM-1 host map).
for _ref, (_x, _y) in zip(range(11, 15),
                          [(18.0, 64.0), (44.0, 64.0),
                           (70.0, 64.0), (96.0, 64.0)]):
    PLACE[f"J{_ref}"] = (_x, _y, 0)
for _ref, (_x, _y) in zip(range(15, 19),
                          [(25.5, 22.0), (47.5, 22.0),
                           (69.5, 22.0), (91.5, 22.0)]):
    PLACE[f"J{_ref}"] = (_x, _y, 0)

# The four buttons are panel-mounted in the fixed front wall (CONST['BTN_FRONT'])
# and reach this board only through J20.  There are no board-mounted switches:
# PLACE therefore has exactly one entry per board.py part, nothing derived from
# the old lid-hole table.

# FreeRouting's fanout occasionally loses the escape from three fine-pitch
# pads (USB-C CC1/A5, USB-C D_N/A7+B7, TCA9548A SD7/pin 19): its session then
# reports 0 unrouted but KiCad's SES importer finds those pads still open.
# Seed the proven, DRC-clean local escapes before DSN export so the router
# sees them as connected.  All three are existing contract nets; no netlist
# or placement changes are involved.  Coordinates are KiCad board mm.
SEED_TRACKS = {
    "CC1": [
        ((12.7500, 96.6225), (12.7500, 97.2651), 0.30),
        ((12.7500, 97.2651), (14.4849, 99.0000), 0.30),
        ((14.4849, 99.0000), (20.1750, 99.0000), 0.30),
    ],
    "D_N": [
        ((13.2500, 96.6225), (13.2500, 96.0041), 0.30),
        ((13.2500, 96.0041), (13.5135, 95.7406), 0.30),
        ((13.5135, 95.7406), (14.2423, 95.7406), 0.30),
        ((14.2423, 95.7406), (14.2500, 95.7483), 0.30),
        ((14.2500, 95.7483), (14.2500, 96.6225), 0.30),
    ],
    "SD7": [
        ((54.8625, 56.6750), (54.7131, 56.5256), 0.225),
        ((54.7131, 56.5256), (53.4387, 56.5256), 0.225),
    ],
}


def _bbox(fp):
    """Pads-and-body bounding box in mm (x0,y0,x1,y1), pcbnew coordinates.

    Uses pad extents (+1 mm) rather than the courtyard, because the ESP32
    module carries a large antenna keep-out *courtyard* that would otherwise
    read as a 48 mm component.
    """
    xs, ys = [], []
    for pad in fp.Pads():
        p = pad.GetPosition()
        sz = pad.GetSize()
        xs += [pcbnew.ToMM(p.x - sz.x / 2), pcbnew.ToMM(p.x + sz.x / 2)]
        ys += [pcbnew.ToMM(p.y - sz.y / 2), pcbnew.ToMM(p.y + sz.y / 2)]
    if not xs:
        bb = fp.GetBoundingBox(False, False)
        return (pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()),
                pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
    m = 0.25
    return (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)


def _courtyard_bbox(fp):
    """True F.CrtYd outline in mm, or None for a footprint without one."""
    if fp is None:
        return None
    bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
    if bb.GetWidth() <= 0 or bb.GetHeight() <= 0:
        return None
    return (pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()),
            pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))


def check_placement(board):
    """Report pad-field overlaps, new-part courtyard clashes and strays."""
    fps = list(board.GetFootprints())
    by_ref = {fp.GetReference(): fp for fp in fps}
    boxes = [(fp.GetReference(), _bbox(fp)) for fp in fps]
    overlaps = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (ra, a), (rb, b) = boxes[i], boxes[j]
            if min(a[2] - 0.01, b[2]) - max(a[0], b[0]) > 0 and \
               min(a[3] - 0.01, b[3]) - max(a[1], b[1]) > 0:
                overlaps.append((ra, rb))
    outside = []
    for ref, b in boxes:
        if b[0] < -0.01 or b[1] < -0.01 or b[2] > PCB_W + 0.01 \
                or b[3] > PCB_D + 0.01:
            outside.append(ref)

    # The inherited layout has a few documented pad-field near-touches, but the
    # two front-panel harness connectors must not add a single real F.CrtYd
    # clash.  Check their courtyards against every other footprint on the board.
    courtyard_overlaps = []
    for ref in ("J19", "J20"):
        a = _courtyard_bbox(by_ref.get(ref))
        if a is None:
            courtyard_overlaps.append((ref, "NO COURTYARD"))
            continue
        for other, fp in by_ref.items():
            if other == ref:
                continue
            b = _courtyard_bbox(fp)
            if b is None:
                continue
            if min(a[2], b[2]) - max(a[0], b[0]) > 0.01 and \
                    min(a[3], b[3]) - max(a[1], b[1]) > 0.01:
                courtyard_overlaps.append((ref, other))
    return overlaps, outside, courtyard_overlaps


def set_rules(board):
    """Two-layer, fab-friendly constraints.

    Minimums are 0.15 mm because the standard footprints use 0.15 mm pad gaps
    and 0.75 mm USB-C holes, so KiCad's 0.2/0.25/0.3 defaults would flag
    known-good parts.  The *nominal* track width is 0.30 mm: the autorouter
    (route_pcb.py) necks down to 75 % then 50 % of the class width in tight
    spots, so a 0.15 mm nominal would let it draw 0.075 mm traces.  At 0.30 mm
    nominal the narrowest trace it produces is 0.15 mm, i.e. still above the
    fab minimum.

    Current: eight 150 mA gas cells plus the fan put up to 1.4 A on the 5 V
    trunk.  IPC-2221 for a 0.30 mm external trace of 1 oz copper gives about
    21 C rise at that current (the fan moves air through the chamber), so no
    narrower class is used and the ground return is poured rather than routed.
    A 0.50 mm class does not route on this 2-layer board: FreeRouting leaves 15
    connections open, so the width is a routing constraint, not a preference.
    """
    ds = board.GetDesignSettings()
    ds.m_MinClearance = pcbnew.FromMM(0.15)
    ds.m_HoleClearance = pcbnew.FromMM(0.19)
    ds.m_MinThroughDrill = pcbnew.FromMM(0.2)
    for nc in board.GetAllNetClasses().values():
        nc.SetClearance(pcbnew.FromMM(0.15))
        nc.SetTrackWidth(pcbnew.FromMM(0.30))


def patch_project(path):
    """Mirror the same rules into the project file (KiCad reads them there)."""
    import json
    if os.path.exists(path):
        with open(path) as fh:
            pro = json.load(fh)
    else:
        pro = {"meta": {"filename": PROJECT + ".kicad_pro", "version": 1}}
    ds = pro.setdefault("board", {}).setdefault("design_settings", {})
    rules = ds.setdefault("rules", {})
    rules.update({"min_clearance": 0.15, "min_hole_clearance": 0.19,
                  "min_through_hole_diameter": 0.2, "min_track_width": 0.15})
    classes = pro.setdefault("net_settings", {}).setdefault(
        "classes", [{"name": "Default"}])
    for cls in classes:
        if cls.get("name") == "Default":
            cls["clearance"] = 0.15
            cls["track_width"] = 0.30
    with open(path, "w") as fh:
        json.dump(pro, fh, indent=2)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing board that already has copper "
                         "(that copper is not recoverable)")
    args = ap.parse_args()

    # Placement only: this writes an unrouted board.  Refuse to run over a
    # routed one, because the tracks/vias live in this same file.
    if os.path.isfile(OUT_PCB) and not args.force:
        old = pcbnew.LoadBoard(OUT_PCB)
        n = len(list(old.GetTracks()))
        if n:
            print("%s already has %d copper items." % (OUT_PCB, n))
            print("It was routed by electrical/route_pcb.py; re-running this "
                  "script would delete that routing.")
            print("Pass --force if that is really what you want.")
            return 2

    B.build()
    os.makedirs(OUT_DIR, exist_ok=True)
    board = pcbnew.BOARD()

    # --- nets --------------------------------------------------------------
    nets = {}
    for name in sorted(B.NETS):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni

    # One lookup for every real pad, including the ESP32's grouped GND token.
    pad_net = {}
    for name, conns in B.NETS.items():
        for ref, pin in conns:
            for num in _pad_numbers(pin):
                pad_net[(ref, num)] = nets[name]

    # --- board outline -----------------------------------------------------
    # Not a plain rectangle: the tray's four M3 bosses stand inside the board
    # footprint, so the board has to give each one a circular cut-out of
    # r = boss radius + 0.3 mm.  Without them the board cannot drop past the
    # bosses (tools/verify_clearance.py measured 221 mm3 of interference), and
    # no copper change can fix that.
    _R = CONST["BOSS_D"] / 2.0 + CONST["BOSS_CLEAR"]
    _inset = CONST["BOSS_INSET"]
    _x0 = (CONST["SH"] - PCB_W) / 2.0
    _y0 = (CONST["SW"] - PCB_D) / 2.0
    # KiCad y runs opposite to the model, so the inward direction is derived
    # from the corner's own position on the board rather than carried over.
    _corners = {}
    for sx, sy in ((_inset, _inset), (CONST["SH"] - _inset, _inset),
                   (CONST["SH"] - _inset, CONST["SW"] - _inset),
                   (_inset, CONST["SW"] - _inset)):
        cx = sx - _x0
        cy = PCB_D - (sy - _y0)
        dx = 1.0 if cx < PCB_W / 2.0 else -1.0
        dy = 1.0 if cy < PCB_D / 2.0 else -1.0
        ex = 0.0 if dx > 0 else PCB_W
        ey = 0.0 if dy > 0 else PCB_D
        pv = (ex, cy + dy * math.sqrt(_R ** 2 - (ex - cx) ** 2))
        ph = (cx + dx * math.sqrt(_R ** 2 - (ey - cy) ** 2), ey)
        mid = (cx + dx * _R / math.sqrt(2.0), cy + dy * _R / math.sqrt(2.0))
        _corners[(dx, dy)] = (pv, ph, mid)

    def _kicad_shape(kind):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(kind)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(pcbnew.FromMM(0.1))
        return s

    def _line(p, q):
        s = _kicad_shape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1])))
        s.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(q[0]), pcbnew.FromMM(q[1])))
        board.Add(s)

    def _arc(p, m, q):
        s = _kicad_shape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(
            pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1])),
            pcbnew.VECTOR2I(pcbnew.FromMM(m[0]), pcbnew.FromMM(m[1])),
            pcbnew.VECTOR2I(pcbnew.FromMM(q[0]), pcbnew.FromMM(q[1])))
        board.Add(s)

    # Walk the perimeter: bottom edge, right edge, top edge, left edge.
    bl, br, tr, tl = (_corners[(1, 1)], _corners[(-1, 1)],
                      _corners[(-1, -1)], _corners[(1, -1)])
    _line(bl[1], br[1])          # bottom
    _arc(br[1], br[2], br[0])    # bottom-right notch
    _line(br[0], tr[0])          # right
    _arc(tr[0], tr[2], tr[1])    # top-right notch
    _line(tr[1], tl[1])          # top
    _arc(tl[1], tl[2], tl[0])    # top-left notch
    _line(tl[0], bl[0])          # left
    _arc(bl[0], bl[2], bl[1])    # bottom-left notch

    # --- footprints --------------------------------------------------------
    missing = []
    for ref in sorted(B.PARTS):
        info = B.PARTS[ref]
        lib, name = info["footprint"].split(":", 1)
        fp = pcbnew.FootprintLoad(os.path.join(FP_LIB, lib + ".pretty"), name)
        if fp is None:
            missing.append(info["footprint"])
            continue
        fp.SetReference(ref)
        fp.SetValue(info["value"])
        x, y, rot = PLACE.get(ref, (PCB_W / 2, PCB_D / 2, 0))
        fp.SetOrientationDegrees(rot)
        target = pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(PCB_D - y))
        fp.SetPosition(target)
        # centre the pad field on the requested point (headers are drawn
        # pin-1-anchored, but the chamber contract is slot-centre)
        xs, ys = [], []
        for pad in fp.Pads():
            pp = pad.GetPosition()
            xs.append(pp.x)
            ys.append(pp.y)
        if xs:
            cx = (min(xs) + max(xs)) // 2
            cy = (min(ys) + max(ys)) // 2
            fp.Move(pcbnew.VECTOR2I(target.x - cx, target.y - cy))
        board.Add(fp)
        for pad in fp.Pads():
            net = pad_net.get((ref, str(pad.GetNumber())))
            if net is not None:
                pad.SetNet(net)

    if missing:
        print("MISSING FOOTPRINTS:", sorted(set(missing)))
        return 1

    # Seed the three fine-pitch local escapes before DSN export.  FreeRouting
    # otherwise reports 0 unrouted in its own session but drops these pads on
    # KiCad's SES import; the router then sees them as already connected and
    # routes only the remaining connections around this known-good copper.
    for net_name, segments in SEED_TRACKS.items():
        net = nets.get(net_name)
        if net is None:
            print("SEED NET MISSING:", net_name)
            return 1
        for a, b, width in segments:
            t = pcbnew.PCB_TRACK(board)
            t.SetLayer(pcbnew.F_Cu)
            t.SetWidth(pcbnew.FromMM(width))
            t.SetNet(net)
            t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(a[0]),
                                       pcbnew.FromMM(a[1])))
            t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(b[0]),
                                     pcbnew.FromMM(b[1])))
            board.Add(t)

    set_rules(board)
    board.Save(OUT_PCB)
    patch_project(os.path.join(OUT_DIR, PROJECT + ".kicad_pro"))
    placed = len(list(board.GetFootprints()))
    overlaps, outside, new_courtyard = check_placement(board)
    unrouted = board.GetConnectivity().GetUnconnectedCount(False)
    print("wrote %s" % OUT_PCB)
    print("  footprints=%d nets=%d unconnected=%s"
          % (placed, len(nets), unrouted))
    if overlaps:
        print("  PAD-FIELD TOUCHES (%d):" % len(overlaps))
        for a, b in overlaps:
            print("    %s <-> %s" % (a, b))
    if new_courtyard:
        print("  NEW-PART COURTYARD OVERLAPS (%d):" % len(new_courtyard))
        for a, b in new_courtyard:
            print("    %s <-> %s" % (a, b))
    if outside:
        print("  OUTSIDE OUTLINE:", outside)
    if not overlaps and not outside and not new_courtyard:
        print("  placement OK (no pad-field touches or new courtyard "
              "overlaps, all inside outline)")
    return 0 if not outside and not new_courtyard else 1


if __name__ == "__main__":
    sys.exit(main())
