#!/usr/bin/env python3
"""Deterministic clean-up applied to the routed OSM-1 board.

FreeRouting produces an electrically complete board, but three cosmetic/manual
fixes are cheaper to apply here than to fight the autorouter:

  * move D1 1 mm away from BZ1 so their courtyards clear,
  * pull the D_P bottom-edge run 0.3 mm inside the 0.5 mm edge rule,
  * delete one 0.15 mm dangling AIN4 stub.

Run with KiCad's Python after route_pcb.py:
  & "C:\Program Files\KiCad\10.0\bin\python.exe" tools/post_route_fixes.py
"""
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PCB = os.path.join(ROOT, "electrical", "smell_monitor_v1_1",
                   "smell_monitor_v1_1.kicad_pcb")

MM = pcbnew.FromMM
V = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))  # noqa: E731


def near(a, b, tol=0.02):
    return abs(a - b) <= tol


def main():
    b = pcbnew.LoadBoard(PCB)

    # 1. D1: (12, 14) -> (12, 13) in KiCad coordinates.
    fp = next(f for f in b.GetFootprints() if f.GetReference() == "D1")
    pos = fp.GetPosition()
    if near(pcbnew.ToMM(pos.y), 14.0):
        fp.Move(V(0, -1.0))
        for t in b.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                continue
            s, e = t.GetStart(), t.GetEnd()
            sx, sy = pcbnew.ToMM(s.x), pcbnew.ToMM(s.y)
            ex, ey = pcbnew.ToMM(e.x), pcbnew.ToMM(e.y)
            if t.GetNetname() == "+5V" and near(sx, 10.35) and near(sy, 14.0):
                t.SetStart(V(10.35, 13.0))
            if t.GetNetname() == "+5V" and near(ex, 10.35) and near(ey, 14.0):
                t.SetEnd(V(10.35, 13.0))
            if t.GetNetname() == "BUZZ_NEG" and near(sx, 13.65) and near(sy, 14.0):
                t.SetStart(V(13.65, 13.0))
            if t.GetNetname() == "BUZZ_NEG" and near(ex, 13.65) and near(ey, 14.0):
                t.SetEnd(V(13.65, 13.0))
        print("  D1 moved 1 mm clear of BZ1 courtyard")

    # 2. D_P bottom-edge run: 104.496 -> 104.196, 104.43 -> 104.13,
    #    104.365 -> 104.065.  Whole cluster shifts together so connectivity
    #    is preserved; only clearance to Edge.Cuts improves.
    shift = 0.30
    for t in list(b.GetTracks()):
        if t.GetNetname() != "D_P":
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            y = pcbnew.ToMM(p.y)
            if y > 104.0:
                t.SetPosition(V(pcbnew.ToMM(p.x), y - shift))
            continue
        for which in ("start", "end"):
            p = t.GetStart() if which == "start" else t.GetEnd()
            y = pcbnew.ToMM(p.y)
            if y > 104.0:
                np = V(pcbnew.ToMM(p.x), y - shift)
                if which == "start":
                    t.SetStart(np)
                else:
                    t.SetEnd(np)
    print("  D_P bottom run pulled 0.3 mm inside the board edge")

    # 3. Delete the single dangling AIN4 stub left by the optimiser.
    killed = 0
    for t in list(b.GetTracks()):
        if t.Type() == pcbnew.PCB_VIA_T or t.GetNetname() != "AIN4":
            continue
        s, e = t.GetStart(), t.GetEnd()
        pts = [(pcbnew.ToMM(s.x), pcbnew.ToMM(s.y)),
               (pcbnew.ToMM(e.x), pcbnew.ToMM(e.y))]
        if ((near(pts[0][0], 37.1093) and near(pts[0][1], 57.5245)) or
                (near(pts[1][0], 37.1093) and near(pts[1][1], 57.5245))):
            b.Remove(t)
            killed += 1
    print("  removed %d dangling AIN4 stub(s)" % killed)

    # 4. BZ1 reference text was clipped by D1's pad/silk after D1 moved.
    bz = next(f for f in b.GetFootprints() if f.GetReference() == "BZ1")
    bz.Reference().SetPosition(V(12.0, 30.0))
    print("  moved BZ1 reference clear of D1")

    b.Save(PCB)
    print("  wrote", PCB)


if __name__ == "__main__":
    main()
