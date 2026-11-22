#!/usr/bin/env python3
"""Generate the OpenSmell v1.1 PCB from the validated board model (board.py).

The board model owns the truth (which part, which pin, which net, which
footprint).  This script turns it into a real `.kicad_pcb` that KiCad can open,
DRC and hand to a fabricator:

  * board outline  = CONST['PCB_X'] x CONST['PCB_Y']  (114 x 105 mm) with four
    circular cut-outs of BOSS_D/2 + BOSS_CLEAR at the tray's lid bosses - the
    bosses stand inside the board footprint, so a rectangle cannot be fitted,
  * sensing headers live exactly on the chamber coordinates
    (interface.ANALOG_HEADERS / DIGITAL_HEADERS), so the board seats on the
    baffle wells with no re-measurement,
  * one net per board.py net, wired to every pad by pin number.

Run with KiCad's own Python (it ships pcbnew):
  & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" electrical/gen_pcb.py
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

# ---------------------------------------------------------------------------
# placement (board-local mm, origin lower-left, Y up).  Sensing headers come
# from the chamber contract; everything else is grouped by subsystem.
# ---------------------------------------------------------------------------
PLACE = {
    # --- sensing sockets: exactly on the chamber contract ------------------
    # Flow order is front -> rear, so J6..J9 are the UPSTREAM row (board
    # y 28.5 ~ shell y 33) and J2..J5 are downstream (board y 70.5 ~ shell
    # y 75).  Y comes from interface.ANALOG/DIGITAL_HEADERS.
    # 90 deg: the pin line runs ACROSS the flow, so a 20 mm cartridge can sit
    # on the 22 mm front-row pitch and reach 32 mm downstream (standard).
    "J2": (18.0, 70.5, 90), "J3": (44.0, 70.5, 90),
    "J4": (70.0, 70.5, 90), "J5": (96.0, 70.5, 90),
    "J6": (25.5, 28.5, 90), "J7": (47.5, 28.5, 90),
    "J8": (69.5, 28.5, 90), "J9": (91.5, 28.5, 90),
    # --- Qwiic ports: one per slot, in front of its socket ----------------
    # The cartridge plugs into the socket and extends rearward, so the strip
    # in front of each socket is open: the Qwiic plug goes in with the module
    # seated, and the cable stays inside the module's own footprint.
    "J11": (18.0, 64.0, 0), "J12": (44.0, 64.0, 0),
    "J13": (70.0, 64.0, 0), "J14": (96.0, 64.0, 0),
    "J15": (25.5, 22.0, 0), "J16": (47.5, 22.0, 0),
    "J17": (69.5, 22.0, 0), "J18": (91.5, 22.0, 0),
    # --- USB + power, front strip ------------------------------------------
    # J1 is 14 mm in, not 10: the tray's front-left boss needs an r = 4.3 mm
    # cut-out, and a USB-C receptacle whose courtyard reaches x = 4.7 would sit
    # inside it.  14 also puts the receptacle directly under the d12 bulkhead
    # hole, so the panel pigtail is a short, straight plug.
    "J1": (14.0, 6.0, 0),
    "R1": (21.0, 6.0, 0), "R2": (24.0, 6.0, 0),
    "U7": (31.0, 8.0, 0),
    "C9": (42.0, 6.0, 0), "C12": (46.0, 6.0, 0),
    "C10": (50.0, 6.0, 0), "C11": (54.0, 6.0, 0),
    "SW1": (74.0, 12.0, 0), "SW2": (83.0, 12.0, 0), "SW3": (92.0, 12.0, 0),
    # --- AO dividers + DO series, left of the centre line ------------------
    # Three shallow rows under the upstream cartridges: DO series nearest the
    # sockets (short 5 V stub), then the two divider rows.
    "R19": (8.0, 33.0, 0), "R20": (11.5, 33.0, 0),
    "R21": (15.0, 33.0, 0), "R22": (18.5, 33.0, 0),
    "R23": (22.0, 33.0, 0), "R24": (25.5, 33.0, 0),
    "R25": (29.0, 33.0, 0), "R26": (32.5, 33.0, 0),
    "R3": (8.0, 37.0, 0), "R4": (11.5, 37.0, 0),
    "R5": (15.0, 37.0, 0), "R6": (18.5, 37.0, 0),
    "R7": (22.0, 37.0, 0), "R8": (25.5, 37.0, 0),
    "R9": (29.0, 37.0, 0), "R10": (32.5, 37.0, 0),
    "R11": (8.0, 40.5, 0), "R12": (11.5, 40.5, 0),
    "R13": (15.0, 40.5, 0), "R14": (18.5, 40.5, 0),
    "R15": (22.0, 40.5, 0), "R16": (25.5, 40.5, 0),
    "R17": (29.0, 40.5, 0), "R18": (32.5, 40.5, 0),
    # --- ADC pair + sensor + mux, centre band ------------------------------
    "U5": (12.0, 48.0, 0), "C5": (17.0, 48.0, 0),
    "U2": (26.0, 48.0, 0), "C3": (31.0, 48.0, 0),
    "U8": (38.0, 48.0, 0), "C6": (43.0, 48.0, 0),
    "U4": (52.0, 48.0, 0), "C4": (58.0, 48.0, 0),
    "U3": (100.0, 50.0, 90), "C7": (109.5, 50.0, 0),
    "C8": (109.5, 44.0, 0),
    # --- bus pull-ups + housekeeping --------------------------------------
    "R31": (36.0, 58.0, 0), "R32": (39.5, 58.0, 0),
    "R33": (43.0, 58.0, 0), "R37": (46.5, 58.0, 0),
    "R38": (8.0, 53.0, 0), "R39": (11.5, 53.0, 0),
    "R40": (15.0, 53.0, 0), "R41": (18.5, 53.0, 0),
    "R42": (22.0, 53.0, 0), "R43": (25.5, 53.0, 0),
    "R44": (29.0, 53.0, 0), "R45": (32.5, 53.0, 0),
    "R46": (8.0, 59.0, 0), "R47": (11.5, 59.0, 0),
    "R48": (15.0, 59.0, 0), "R49": (18.5, 59.0, 0),
    "R50": (22.0, 59.0, 0), "R51": (25.5, 59.0, 0),
    "R52": (29.0, 59.0, 0), "R53": (32.5, 59.0, 0),
    "R34": (84.0, 54.0, 0), "R35": (88.0, 54.0, 0), "R36": (92.0, 54.0, 0),
    # --- controller: at the top edge, antenna overhangs the board ---------
    # 94.4, not 95.0: at 95.0 the module outline silk pokes 0.18 mm past the
    # top Edge.Cuts and trips silk_edge_clearance.  The antenna keep-out still
    # overhangs the edge by >20 mm either way, so nothing electrical changes.
    "U1": (68.0, 94.4, 0),
    "C1": (46.0, 92.0, 0), "C2": (50.0, 92.0, 0),
    # --- outputs, rear strip -----------------------------------------------
    # BZ1 moved from the rear-left corner (12, 93): the rear-left boss needs an
    # r = 4.3 cut-out and the buzzer's 10.2 mm body sat inside it.
    "BZ1": (12.0, 84.0, 0), "D1": (12.0, 92.0, 0),
    "Q2": (24.0, 92.0, 0),
    "R28": (29.0, 90.0, 0), "R29": (32.0, 90.0, 0),
    "LED1": (40.0, 94.0, 0), "R30": (36.5, 94.0, 0),
    "Q1": (100.0, 88.0, 0), "J10": (108.0, 88.0, 90), "R27": (96.0, 88.0, 0),
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


def check_placement(board):
    """Report courtyard overlaps and parts outside the board outline."""
    fps = list(board.GetFootprints())
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
    return overlaps, outside


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
            net = None
            for nname, conns in B.NETS.items():
                if (ref, str(pad.GetNumber())) in [(r, str(p)) for r, p in conns]:
                    net = nets[nname]
                    break
            if net is not None:
                pad.SetNet(net)

    if missing:
        print("MISSING FOOTPRINTS:", sorted(set(missing)))
        return 1

    set_rules(board)
    board.Save(OUT_PCB)
    patch_project(os.path.join(OUT_DIR, PROJECT + ".kicad_pro"))
    placed = len(list(board.GetFootprints()))
    overlaps, outside = check_placement(board)
    unrouted = board.GetConnectivity().GetUnconnectedCount(False)
    print("wrote %s" % OUT_PCB)
    print("  footprints=%d nets=%d unconnected=%s"
          % (placed, len(nets), unrouted))
    if overlaps:
        print("  COURTYARD OVERLAPS (%d):" % len(overlaps))
        for a, b in overlaps:
            print("    %s <-> %s" % (a, b))
    if outside:
        print("  OUTSIDE OUTLINE:", outside)
    if not overlaps and not outside:
        print("  placement OK (no courtyard overlaps, all inside outline)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
