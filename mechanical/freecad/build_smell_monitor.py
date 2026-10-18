#!/usr/bin/env python3
"""Build the OpenSmell v1.1 parametric 3D model headlessly (FreeCAD cmd).

Emitter: mechanical/freecad/build_smell_monitor.py
Outputs:
  mechanical/freecad/smell_monitor.FCStd   full parametric model
  mechanical/freecad/smell_monitor.STEP    exchange geometry
  mechanical/drawings/model_hlr.json       real HLR 2D projections for sheets

Coordinate frame (mm), origin = front-lower-left outer corner of shell:
  X = width  (slot axis, 0..122)
  Y = depth  (front=0 .. rear=114)
  Z = height (0..90, up)

All dimensions live in the CONST dict -> single source of truth.
Run:  freecadcmd.exe mechanical/freecad/build_smell_monitor.py
"""
import json
import math
import os
import sys

import FreeCAD as App
import Part

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_FCSTD = os.path.join(ROOT, "mechanical", "freecad", "smell_monitor.FCStd")
OUT_STEP = os.path.join(ROOT, "mechanical", "freecad", "smell_monitor.STEP")
OUT_JSON = os.path.join(ROOT, "mechanical", "drawings", "model_hlr.json")

sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST  # noqa: E402  (single source of truth)

CX0, CY0, BZ, BT = CONST["WSIDE"], CONST["WFB"], CONST["BAFFLE_Z"], CONST["BAFFLE_T"]
CX1, CY1 = CX0 + CONST["CX"], CY0 + CONST["CY"]
CAV_Z0, CAV_Z1 = CONST["FLOOR"], CONST["FLOOR"] + CONST["CH"]
MIDX = CONST["SH"] / 2.0


def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0,
                        App.Vector(x0, y0, z0))


def cylinder(r, z0, z1, cx, cy):
    c = Part.makeCylinder(r, z1 - z0, App.Vector(cx, cy, z0), App.Vector(0, 0, 1))
    return c


doc = App.newDocument("SmellMonitor")

objs = {}  # label -> Part::Feature

# --- shell with cavity pocket, 3x d6 intake bores and d40 rear exhaust ---
shell = doc.addObject("Part::Feature", "Shell")
shell.Label = "shell"
cavity = box(CX0, CY0, CAV_Z0, CX1, CY1, CAV_Z1)
# PCB seat: the board is the sealed chamber floor (blueprint.md 6.1/6.2), so
# the shell carries a PCB_T-deep rebate on the PCB outline under the cavity.
# The board drops in from below; its top face lands flush with z = FLOOR,
# which is the datum behind "baffle 37 mm above board" and "29 mm module
# allowance".  (The stacking error this fixes: PCB_Z used to be CAV_Z1-1.6,
# which buried the board in the cavity ceiling and blocked all 3 intakes.)
pcb_seat = box((CONST["SH"] - CONST["PCB_X"]) / 2.0,
               (CONST["SW"] - CONST["PCB_Y"]) / 2.0, CONST["PCB_Z"],
               (CONST["SH"] + CONST["PCB_X"]) / 2.0,
               (CONST["SW"] + CONST["PCB_Y"]) / 2.0, CAV_Z0)
body = box(0, 0, 0, CONST["SH"], CONST["SW"], CONST["SHH"]).cut(cavity).cut(pcb_seat)
NO_X = (CONST["SH"] / 2 - 26, CONST["SH"] / 2, CONST["SH"] / 2 + 26)
for cx in NO_X:                                   # 3x d6 through front wall
    body = body.cut(Part.makeCylinder(
        CONST["NO_R"], 10.0, App.Vector(cx, -1.0, CONST["NO_Z"]),
        App.Vector(0, 1, 0)))
body = body.cut(Part.makeCylinder(                # d40 through rear wall
    CONST["FAN_R"], 12.0, App.Vector(CONST["FAN_X"], 105.0, CONST["FAN_Z"]),
    App.Vector(0, 1, 0)))
shell.Shape = body

# --- baffle plate with well slots ---------------------------------------
# Plate spans the whole cavity at BZ; well slots are open-bottom (they cut
# through the plate) so the sub-baffle volume exchanges with the 11 mm flow
# lane above it.  Digital wells sit upstream of the analog wells.
baffle = doc.addObject("Part::Feature", "Baffle")
baffle.Label = "baffle"
plate = box(CX0, CY0, BZ - BT, CX1, CY1, BZ)
for cx in CONST["A_X"]:
    plate = plate.cut(box(cx - CONST["A_SX"] / 2, CONST["A_Y0"],
                          BZ - BT, cx + CONST["A_SX"] / 2,
                          CONST["A_Y0"] + CONST["A_SY"], BZ))
for cx in CONST["D_X"]:
    plate = plate.cut(box(cx - CONST["D_SX"] / 2, CONST["D_Y0"],
                          BZ - BT, cx + CONST["D_SX"] / 2,
                          CONST["D_Y0"] + CONST["D_SY"], BZ))
# Reference T/RH port over the on-board SHT31 (U5) + its cap.  The compensation
# backbone must sample the gas path, and U5 is a soldered part - not a plug-in
# module - so it needs its own opening through the plate.
plate = plate.cut(box(CONST["SHT_X"] - CONST["SHT_SX"] / 2, CONST["SHT_Y0"],
                      BZ - BT, CONST["SHT_X"] + CONST["SHT_SX"] / 2,
                      CONST["SHT_Y0"] + CONST["SHT_SY"], BZ))
baffle.Shape = plate

# --- PCB: the sealed chamber floor ---------------------------------------
# Its top face is at CAV_Z0, so "N mm above board" == "N mm above the cavity
# floor" and the baffle/allowance/recess numbers in blueprint.md 4.6 hold.
pcb = doc.addObject("Part::Feature", "PCB")
pcb.Label = "pcb"
pcb_x0 = (CONST["SH"] - CONST["PCB_X"]) / 2.0
pcb_y0 = (CONST["SW"] - CONST["PCB_Y"]) / 2.0
pcb.Shape = box(pcb_x0, pcb_y0, CONST["PCB_Z"],
                pcb_x0 + CONST["PCB_X"], pcb_y0 + CONST["PCB_Y"],
                CONST["PCB_Z"] + CONST["PCB_T"])

# --- nostrils (3x d6, bore axis along Y through the front wall) -----------
nostrils = doc.addObject("Part::Feature", "Nostrils")
nostrils.Label = "nostrils"
ns = None
for cx in NO_X:
    n = Part.makeCylinder(CONST["NO_R"], 9.0,
                          App.Vector(cx, CONST["NO_Y"], CONST["NO_Z"]),
                          App.Vector(0, 1, 0))
    ns = n if ns is None else ns.fuse(n)
nostrils.Shape = ns

# --- intake plenum + filter pack (top-front, above baffle) --------------
# The filter is a SERIES element (blueprint.md 3.4 losses, 3.6 spec): it spans
# the full 106 x 11 mm lane cross-section right behind the nostrils, so nothing
# can bypass it and dust cannot reach the wells unfiltered.  It has to be a
# pleated pack - a flat 106 x 11 face is only 11.7 cm2, and 3.6 needs >= 70 cm2
# to stay <= 2 Pa.
plenum = doc.addObject("Part::Feature", "Plenum")
plenum.Label = "plenum"
plenum.Shape = box(CX0, CY0, BZ, CX1, CONST["FILT_Y0"], CAV_Z1)

filt = doc.addObject("Part::Feature", "Filter")
filt.Label = "filter"
filt.Shape = box(CX0, CONST["FILT_Y0"], BZ,
                 CX1, CONST["FILT_Y0"] + CONST["FILT_T"], CAV_Z1)

# --- taper duct + fan (rear) ---------------------------------------------
duct = doc.addObject("Part::Feature", "Duct")
duct.Label = "duct"
duct.Shape = box(CX0 + 20, CY1 - 8.0, BZ - 2.0,
                 MIDX + 20.0, CY1, CAV_Z1 - 2.0)

fan = doc.addObject("Part::Feature", "Fan")
fan.Label = "fan"
shroud = box(MIDX - 24.0, CONST["FAN_Y"], CONST["FAN_Z"] - 24.0,
             MIDX + 24.0, CONST["FAN_Y"] + CONST["FAN_T"], CONST["FAN_Z"] + 24.0)
fan_disc = Part.makeCylinder(CONST["FAN_R"], CONST["FAN_T"],
                             App.Vector(CONST["FAN_X"], CONST["FAN_Y"], CONST["FAN_Z"]),
                             App.Vector(0, 1, 0))
fan.Shape = fan_disc.fuse(shroud)

# NOTE: ViewProvider appearance (transparency/colour) cannot be set headless
# (freecadcmd has no Gui). Run style_smell_monitor.py through the GUI once
# after rebuilding so internals are visible when people open the .FCStd.
doc.recompute()

# =========================================================================
#  Real hidden-line-removal (HLR) projections -> neutral JSON for the sheets
#  TechDraw.projectEx returns the true visible/hidden edges measured off the
#  solid (not reconstructed by hand), so drawing views are faithful.
# =========================================================================
import TechDraw

os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)


def _ent_from_edge(edge):
    """Convert one projected 2D edge (XY plane) to a neutral drawing entity."""
    cur = edge.Curve
    ctype = getattr(cur, "TypeId", "")
    if "Line" in ctype:
        p0, p1 = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
        return {"t": "line", "a": [round(p0.x, 3), round(p0.y, 3)],
                "b": [round(p1.x, 3), round(p1.y, 3)]}
    if "Circle" in ctype:
        c, r, ax = cur.Center, cur.Radius, cur.Axis
        a0 = math.degrees(edge.FirstParameter)
        a1 = math.degrees(edge.LastParameter)
        if ax.z < 0:                        # reversed parametric direction
            a0, a1 = -a1, -a0
        a0 %= 360.0
        a1 %= 360.0
        if abs((a1 - a0) % 360.0) < 1e-6:   # closed -> full circle
            return {"t": "circle", "c": [round(c.x, 3), round(c.y, 3)],
                    "r": round(r, 3)}
        if a1 <= a0:
            a1 += 360.0
        return {"t": "arc", "c": [round(c.x, 3), round(c.y, 3)], "r": round(r, 3),
                "a0": round(a0, 3), "a1": round(a1, 3)}
    # ellipses (iso circles), B-splines, etc. -> sampled polyline
    n = max(4, int(math.ceil(edge.Length / 0.8)))
    q0, q1 = edge.FirstParameter, edge.LastParameter
    pts = []
    for i in range(n + 1):
        p = cur.value(q0 + (q1 - q0) * i / n)
        pts.append([round(p.x, 3), round(p.y, 3)])
    return {"t": "poly", "pts": pts}


def _ents(edges):
    return [_ent_from_edge(e) for e in edges]


def hlr_view(shape, direction):
    g = TechDraw.projectEx(shape, App.Vector(*direction))
    vis = g[0].Edges + g[1].Edges + g[2].Edges + g[3].Edges + g[4].Edges
    hid = g[5].Edges + g[6].Edges + g[7].Edges + g[8].Edges + g[9].Edges
    return {"dir": list(direction), "visible": _ents(vis), "hidden": _ents(hid)}


def axis_vectors(direction):
    """(u,v) components of the global +X/+Y/+Z axes *measured* in this projection.

    An orthographic projection is linear, so recording these three vectors makes
    the projection exactly invertible: a model point (x, y, z) lands at
    u = ax[X].u*x + ax[Y].u*y + ax[Z].u*z (likewise v).  The drawing generator
    needs that to place dimensions on real features - a dimension that is not on
    the feature it names is a lie.  Measured by projecting a 100 mm reference
    line along each global axis with the same projector, never assumed.
    """
    L = 100.0
    out = {}
    for name, end in (("X", (L, 0, 0)), ("Y", (0, L, 0)), ("Z", (0, 0, L))):
        line = Part.makeLine(App.Vector(0, 0, 0), App.Vector(*end))
        g = TechDraw.projectEx(Part.makeCompound([line]), App.Vector(*direction))
        edges = g[0].Edges + g[1].Edges + g[2].Edges + g[3].Edges + g[4].Edges
        if not edges:
            # the axis is parallel to the view direction: it has no in-plane
            # component, so it projects to a point (a zero vector).
            out[name] = [0.0, 0.0]
            continue
        a, b = edges[0].Vertexes[0].Point, edges[0].Vertexes[-1].Point
        out[name] = [round((b.x - a.x) / L, 6), round((b.y - a.y) / L, 6)]
    return out


def half_space_cut(shape, axis, coord, keep_less=True):
    B = 1000.0
    if axis == 0:
        cutter = box(coord, -B, -B, coord + B, B, B) if keep_less else \
                 box(coord - B, -B, -B, coord, B, B)
    elif axis == 1:
        cutter = box(-B, coord, -B, B, coord + B, B) if keep_less else \
                 box(-B, coord - B, -B, B, coord, B)
    else:
        cutter = box(-B, -B, coord, B, B, coord + B) if keep_less else \
                 box(-B, -B, coord - B, B, B, coord)
    return shape.cut(cutter)


assembly = shell.Shape.fuse(baffle.Shape).fuse(pcb.Shape).fuse(
    ns).fuse(filt.Shape).fuse(fan.Shape)
sec_bb = half_space_cut(shell.Shape, 0, MIDX, keep_less=True)
sec_aa = half_space_cut(baffle.Shape, 1, CONST["A_Y0"] + CONST["A_SY"] / 2.0,
                        keep_less=True)

def moved(shape, v):
    """A copy of `shape` translated by v (works whether translate copies or not)."""
    vec = App.Vector(*v)
    fn = getattr(shape, "translated", None)
    if fn is not None:
        return fn(vec)
    s = shape.copy()
    r = s.translate(vec)
    return r if r is not None else s


# Exploded general arrangement: the parts come out along the assembly axis (+Z),
# which is the direction a builder actually moves them (the board drops in from
# below, everything above it lifts out).  The nostrils are bores in the shell, so
# they stay with it.  The offsets travel to the drawing as data, so the balloon
# leaders always point at the real exploded positions.
EXPLODE = {
    "baffle": (0, 0, 46),
    "filter": (0, 0, 56),
    "pcb": (0, 0, 78),
    "fan": (0, 34, 60),
}
exploded = shell.Shape
for _s, _v in ((baffle.Shape, EXPLODE["baffle"]),
               (filt.Shape, EXPLODE["filter"]),
               (pcb.Shape, EXPLODE["pcb"]),
               (fan.Shape, EXPLODE["fan"])):
    exploded = exploded.fuse(moved(_s, _v))

VIEW_REQUESTS = [
    ("shell", "FRONT", shell.Shape, (0, -1, 0)),
    ("shell", "PLAN", shell.Shape, (0, 0, 1)),
    ("shell", "SECTION_BB", sec_bb, (1, 0, 0)),
    ("shell", "ISO", shell.Shape, (1, -1, 1)),
    ("baffle", "PLAN", baffle.Shape, (0, 0, 1)),
    ("baffle", "SECTION_AA", sec_aa, (0, 1, 0)),
    ("baffle", "ISO", baffle.Shape, (1, -1, 1)),
    ("assembly", "ISO", assembly, (1, -1, 1)),
    ("assembly", "EXPLODED", exploded, (1, -1, 1)),
]

out = {"explode": {k: list(v) for k, v in EXPLODE.items()}}
for part, view, shp, direction in VIEW_REQUESTS:
    rec = hlr_view(shp, direction)
    rec["axes"] = axis_vectors(direction)
    out.setdefault(part, {})[view] = rec

with open(OUT_JSON, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1)

# --- save model -----------------------------------------------------------
try:
    doc.saveAs(OUT_FCSTD)
except Exception as e:
    print("FCStd save failed:", e)
try:
    assembly.exportStep(OUT_STEP)
except Exception as e:
    print("STEP export failed:", e)


def _part_step(shape, name):
    path = os.path.join(os.path.dirname(OUT_STEP), name)
    try:
        shape.exportStep(path)
        print("step   OK ->", path)
    except Exception as e:
        print("part STEP export failed:", name, e)


def _part_stl(shape, name):
    """Mesh export for print services (Seeed takes one watertight STL per part,
    <=10 MB). BRep solids are closed -> a fine tessellation stays manifold."""
    import MeshPart
    path = os.path.join(os.path.dirname(OUT_STEP), name)
    try:
        mesh = MeshPart.meshFromShape(
            Shape=shape, LinearDeflection=0.05, AngularDeflection=0.3,
            Relative=False)
        mesh.write(path)
        kb = os.path.getsize(path) / 1024.0
        print("stl    OK -> %s (%d facets, %.0f KB)" % (path, mesh.CountFacets, kb))
    except Exception as e:
        print("part STL export failed:", name, e)


_part_step(shell.Shape, "smell_monitor_shell.STEP")
_part_step(baffle.Shape, "smell_monitor_baffle.STEP")
_part_stl(shell.Shape, "smell_monitor_shell.stl")
_part_stl(baffle.Shape, "smell_monitor_baffle.stl")

print("model OK ->", OUT_FCSTD)
print("step   OK ->", OUT_STEP)
print("edges  OK ->", OUT_JSON)