#!/usr/bin/env python3
"""Export the ROUTED KiCad board as render-ready geometry (shell coordinates).

Run with KiCad's Python:
  & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" tools/extract_pcb_geometry.py

The story renderer uses system Python + Pillow, so this bridge is deliberately
dumb: it converts pcbnew objects to plain mm numbers in the mechanical frame.
No visual styling happens here.  Every coordinate is taken from the committed
.kicad_pcb, not guessed, so the animation cannot drift from what gets fabbed.
"""
import json
import math
import os
import sys

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST  # noqa: E402

PCB = os.path.join(ROOT, "electrical", "smell_monitor_v1_1",
                   "smell_monitor_v1_1.kicad_pcb")
OUT = os.path.join(ROOT, "docs", "figures", "cad", "pcb_geometry.json")

PCB_X0 = (CONST["SH"] - CONST["PCB_X"]) / 2.0
PCB_Y0 = (CONST["SW"] - CONST["PCB_Y"]) / 2.0
MM = pcbnew.ToMM


def shell(v):
    """KiCad board point (x right, y down from rear) -> shell X/Y (mm)."""
    return (PCB_X0 + MM(v.x), CONST["SW"] - PCB_Y0 - MM(v.y))


def pt(v):
    x, y = shell(v)
    return (round(x, 4), round(y, 4))


def polyline(shape):
    st = pcbnew.SHAPE_T_SEGMENT
    arc = pcbnew.SHAPE_T_ARC
    cir = pcbnew.SHAPE_T_CIRCLE
    t = shape.GetShape()
    if t == st:
        return [pt(shape.GetStart()), pt(shape.GetEnd())]
    if t == arc:
        a, m, b = shape.GetStart(), shape.GetArcMid(), shape.GetEnd()
        # Three-point arc -> sampled polyline, flat enough at render scale.
        ax, ay = MM(a.x), MM(a.y)
        bx, by = MM(b.x), MM(b.y)
        mx, my = MM(m.x), MM(m.y)
        d = 2 * (ax * (by - my) + bx * (my - ay) + mx * (ay - by))
        if abs(d) < 1e-9:
            return [pt(a), pt(b)]
        a2 = ax * ax + ay * ay
        b2 = bx * bx + by * by
        m2 = mx * mx + my * my
        cx = (a2 * (by - my) + b2 * (my - ay) + m2 * (ay - by)) / d
        cy = (a2 * (mx - bx) + b2 * (ax - mx) + m2 * (bx - ax)) / d
        r = math.hypot(ax - cx, ay - cy)
        a0 = math.atan2(ay - cy, ax - cx)
        a1 = math.atan2(by - cy, bx - cx)
        am = math.atan2(my - cy, mx - cx)
        # Walk the short way through the midpoint recorded by KiCad.
        while a1 <= a0:
            a1 += 2 * math.pi
        while am <= a0:
            am += 2 * math.pi
        if am > a1:
            a0, a1 = a1, a0 + 2 * math.pi
        n = max(4, int(abs(a1 - a0) * r / 0.4))
        out = []
        for i in range(n + 1):
            th = a0 + (a1 - a0) * i / n
            out.append((round(PCB_X0 + cx + r * math.cos(th), 4),
                        round(CONST["SW"] - PCB_Y0 - cy - r * math.sin(th), 4)))
        return out
    if t == cir:
        c = shape.GetCenter()
        r = MM(shape.GetRadius())
        cx, cy = MM(c.x), MM(c.y)
        return [(round(PCB_X0 + cx + r * math.cos(2 * math.pi * i / 40), 4),
                 round(CONST["SW"] - PCB_Y0 - cy + r * math.sin(2 * math.pi * i / 40), 4))
                for i in range(41)]
    return []


def main():
    print("  loading", PCB, flush=True)
    b = pcbnew.LoadBoard(PCB)
    print("  loaded; drawings", len(list(b.GetDrawings())), flush=True)

    outline = []
    silk = []
    for d in b.GetDrawings():
        layer = b.GetLayerName(d.GetLayer())
        if layer == "Edge.Cuts":
            outline.append(polyline(d))
        elif layer == "F.Silkscreen":
            if isinstance(d, pcbnew.PCB_TEXT):
                silk.append({"text": d.GetText(), "pos": pt(d.GetPosition())})
            elif isinstance(d, pcbnew.PCB_SHAPE):
                line = polyline(d)
                if line:
                    silk.append(line)

    print("  outline/silk done", len(outline), len(silk), flush=True)
    tracks = []
    vias = []
    for t in b.GetTracks():
        net = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            x, y = shell(t.GetPosition())
            vias.append({"x": round(x, 4), "y": round(y, 4),
                         "d": round(MM(t.GetWidth(pcbnew.F_Cu)), 4),
                         "drill": round(MM(t.GetDrillValue()), 4), "net": net})
            continue
        layer = b.GetLayerName(t.GetLayer())
        if layer not in ("F.Cu", "B.Cu"):
            continue
        tracks.append({"layer": layer, "net": net,
                       "a": pt(t.GetStart()), "b": pt(t.GetEnd()),
                       "w": round(MM(t.GetWidth()), 4)})

    print("  tracks done", len(tracks), len(vias), flush=True)
    pads = []
    footprints = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        x, y = shell(fp.GetPosition())
        bb = fp.GetBoundingBox(False, False)
        x0, y0 = shell(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
        x1, y1 = shell(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
        footprints.append({"ref": ref, "value": fp.GetValue(),
                           "x": round(x, 4), "y": round(y, 4),
                           "layer": b.GetLayerName(fp.GetLayer()),
                           "bbox": [round(min(x0, x1), 4), round(min(y0, y1), 4),
                                    round(max(x0, x1), 4), round(max(y0, y1), 4)]})
        for p in fp.Pads():
            px, py = shell(p.GetPosition())
            sz = p.GetSize()
            pads.append({"ref": ref, "num": p.GetNumber(), "net": p.GetNetname(),
                         "x": round(px, 4), "y": round(py, 4),
                         "w": round(MM(sz.x), 4), "h": round(MM(sz.y), 4),
                         "rot": round(p.GetOrientationDegrees(), 2),
                         "shape": str(p.GetShape())})

    data = {
        "source": os.path.relpath(PCB, ROOT).replace("\\", "/"),
        "frame": "shell mm: X 0..122, Y 0=front..114=rear, Z up",
        "board_origin": [round(PCB_X0, 4), round(PCB_Y0, 4)],
        "outline": outline, "silk": silk, "tracks": tracks,
        "vias": vias, "pads": pads, "footprints": footprints,
        "counts": {"footprints": len(footprints), "pads": len(pads),
                   "tracks": len(tracks), "vias": len(vias),
                   "nets": len({t["net"] for t in tracks}),
                   "outline_polylines": len(outline)},
    }
    print("  footprints done", len(footprints), len(pads), flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print("wrote", OUT, data["counts"])


if __name__ == "__main__":
    main()
