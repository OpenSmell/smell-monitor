#!/usr/bin/env python3
"""Generate the OpenSmell v1.1 PCB from the validated board model (board.py).

The board model owns the truth (which part, which pin, which net, which
footprint).  This script turns it into a real `.kicad_pcb` that KiCad can open,
DRC and hand to a fabricator:

  * board outline  = CONST['PCB_X'] x CONST['PCB_Y']  (114 x 105 mm)
  * sensing headers live exactly on the chamber coordinates
    (interface.ANALOG_HEADERS / DIGITAL_HEADERS), so the board seats on the
    baffle wells with no re-measurement,
  * one net per board.py net, wired to every pad by pin number.

Run with KiCad's own Python (it ships pcbnew):
  & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" electrical/gen_pcb.py
"""
import os
import sys

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
    # --- sensing headers: exactly on the chamber wells ---------------------
    # Flow order is front -> rear, so the digital row is the UPSTREAM row
    # (board y 28.5 ~ shell y 33) and the analog row is downstream of it
    # (board y 70.5 ~ shell y 75).  Y from interface.ANALOG/DIGITAL_HEADERS.
    "J2": (18.0, 70.5, 0), "J3": (44.0, 70.5, 0),
    "J4": (70.0, 70.5, 0), "J5": (96.0, 70.5, 0),
    "J6": (25.5, 28.5, 0), "J7": (46.5, 28.5, 0),
    "J8": (67.5, 28.5, 0), "J9": (88.5, 28.5, 0),
    # --- USB + power, bottom strip ----------------------------------------
    "J1": (10.0, 6.0, 0),
    "R1": (18.0, 6.0, 0), "R2": (22.0, 6.0, 0),
    "U7": (31.0, 8.0, 0),
    "C7": (42.0, 6.0, 0), "C9": (46.0, 6.0, 0),
    "C10": (50.0, 6.0, 0), "C11": (54.0, 6.0, 0),
    "C12": (58.0, 6.0, 0), "C8": (62.0, 6.0, 0),
    "SW1": (74.0, 12.0, 0), "SW2": (83.0, 12.0, 0), "SW3": (92.0, 12.0, 0),
    "R11": (102.0, 16.0, 0),
    # --- ADC + sensor + mux, centre band ----------------------------------
    "U2": (14.0, 50.0, 0), "C3": (19.0, 50.0, 0),
    "U5": (14.0, 44.0, 0), "C5": (19.0, 44.0, 0),
    "U4": (34.0, 50.0, 0), "C4": (40.0, 50.0, 0),
    "U3": (100.0, 50.0, 90), "C6": (100.0, 43.0, 0),
    "U6": (108.0, 46.0, 0),
    "C1": (78.0, 54.0, 0), "C2": (78.0, 44.0, 0),
    "R18": (84.0, 54.0, 0), "R19": (88.0, 54.0, 0), "R20": (92.0, 54.0, 0),
    "R15": (36.0, 59.0, 0), "R16": (39.5, 59.0, 0), "R17": (43.0, 59.0, 0),
    # --- analog dividers (slot AO -> ADS1115) -----------------------------
    # 39 mm, not 41: at 41 their part numbers collide with U5/C5 silkscreen
    # (DRC silk_overlap) and there is nothing else in the 35-42 mm band.
    "R3": (14.0, 39.0, 0), "R4": (17.5, 39.0, 0),
    "R5": (21.0, 39.0, 0), "R6": (24.5, 39.0, 0),
    "R7": (28.0, 39.0, 0), "R8": (31.5, 39.0, 0),
    "R9": (35.0, 39.0, 0), "R10": (38.5, 39.0, 0),
    # --- digital-channel pull-ups (SD/SC) ---------------------------------
    "R21": (8.0, 57.0, 0), "R22": (11.5, 57.0, 0),
    "R23": (15.0, 57.0, 0), "R24": (18.5, 57.0, 0),
    "R25": (22.0, 57.0, 0), "R26": (25.5, 57.0, 0),
    "R27": (29.0, 57.0, 0), "R28": (32.5, 57.0, 0),
    # --- controller: at the top edge, antenna overhangs the board ---------
    # 94.4, not 95.0: at 95.0 the module outline silk pokes 0.18 mm past the
    # top Edge.Cuts and trips silk_edge_clearance.  The antenna keep-out still
    # overhangs the edge by >20 mm either way, so nothing electrical changes.
    "U1": (68.0, 94.4, 0),
    # --- outputs, top strip -----------------------------------------------
    "BZ1": (12.0, 93.0, 0), "Q2": (24.0, 92.0, 0),
    "R12": (29.0, 90.0, 0), "R13": (32.0, 90.0, 0),
    "LED1": (40.0, 94.0, 0), "R14": (36.5, 94.0, 0),
    "Q1": (100.0, 88.0, 0), "J10": (108.0, 88.0, 90),
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
    for x0, y0, x1, y1 in ((0, 0, PCB_W, 0), (PCB_W, 0, PCB_W, PCB_D),
                           (PCB_W, PCB_D, 0, PCB_D), (0, PCB_D, 0, 0)):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x0), pcbnew.FromMM(y0)))
        seg.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x1), pcbnew.FromMM(y1)))
        seg.SetWidth(pcbnew.FromMM(0.1))
        board.Add(seg)

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
