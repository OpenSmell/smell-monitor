#!/usr/bin/env python3
"""Remove autorouter vias/tracks that no longer join anything.

FreeRouting's optimiser can leave a via behind after ripping up the B.Cu stub
that used it, or a short dangling F.Cu stub.  KiCad's DRC reports these as
warnings even though the remaining copper is fully connected.  This script is
run on a freshly loaded, already routed board (after ``route_seeded.py``) and
collects every removal before touching the board, because pcbnew's Python
``GetTracks()`` proxy becomes unusable once items have been Remove()d.

Run with KiCad's Python:
  & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" \\
      electrical/smell_monitor_v1_1/cleanup_drc.py
"""
import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "smell_monitor_v1_1.kicad_pcb")
TOL = pcbnew.FromMM(0.03)


def same(p, q):
    return abs(p.x - q.x) <= TOL and abs(p.y - q.y) <= TOL


def main():
    board = pcbnew.LoadBoard(PCB)
    tracks = list(board.GetTracks())
    vias = [t for t in tracks if t.Type() == pcbnew.PCB_VIA_T]
    segs = [t for t in tracks if t.Type() != pcbnew.PCB_VIA_T]
    b_segs = [t for t in segs if t.GetLayer() == pcbnew.B_Cu]
    pads = [(pad.GetPosition(), pad.GetLayerSet())
            for fp in board.GetFootprints() for pad in fp.Pads()]

    doomed = []

    # 1. Non-GND vias with no B.Cu track endpoint are inert; GND vias are
    #    connected by the B.Cu pour without a track.
    for via in vias:
        if via.GetNetname() == "GND":
            continue
        p = via.GetPosition()
        if not any(same(p, t.GetStart()) or same(p, t.GetEnd())
                   for t in b_segs):
            doomed.append(via)

    doomed_ids = {id(t) for t in doomed}
    live_segs = [t for t in segs if id(t) not in doomed_ids]
    live_vias = [v for v in vias if id(v) not in doomed_ids]

    # 2. A track end is connected if it meets a pad, a via, or another live
    #    track on the same layer.  Remove any segment with a free end.
    def connected(point, layer, item):
        if any(same(point, v.GetPosition()) for v in live_vias):
            return True
        if any(same(point, pos) and layers.Contains(layer)
               for pos, layers in pads):
            return True
        return any(t is not item and t.GetLayer() == layer and
                   (same(point, t.GetStart()) or same(point, t.GetEnd()))
                   for t in live_segs)

    for t in live_segs:
        if not connected(t.GetStart(), t.GetLayer(), t) or \
                not connected(t.GetEnd(), t.GetLayer(), t):
            doomed.append(t)
            doomed_ids.add(id(t))

    for item in doomed:
        board.Remove(item)
    board.Save(PCB)
    print("removed %d unused via(s)/dangling track(s); wrote %s"
          % (len(doomed), PCB))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
