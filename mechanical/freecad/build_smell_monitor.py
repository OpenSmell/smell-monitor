#!/usr/bin/env python3
"""Build the OpenSmell v1.1 parametric 3D model with FreeCADCmd.

Emitter: mechanical/freecad/build_smell_monitor.py
Outputs:
  mechanical/freecad/smell_monitor.FCStd   full parametric model
  mechanical/freecad/smell_monitor.STEP    exchange geometry
  mechanical/drawings/model_hlr.json       real HLR 2D projections for sheets

Coordinate frame (mm), origin = front-lower-left outer corner of shell:
  X = width  (0..122)
  Y = depth  (front outer face = 0, cavity = WALL..SW, rear fan plate to SW+4)
  Z = height (0..60; the flat lid top is SHH, nothing stands above it)

The v1.1 UI lives on the FIXED FRONT WALL: the aperture, harness grommet and
four button bores are cut through y=0..WALL, and the sealed panel stacks out
into negative Y.  The lid is a plain plate with four M3 counterbores only, so
opening it never breaks a wire.

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

SH, SW, SHH = CONST["SH"], CONST["SW"], CONST["SHH"]
CX0, CY0 = CONST["CX0"], CONST["CY0"]
CX1, CY1 = CONST["CX1"], CONST["CY1"]
CZ0, CZ1 = CONST["CAV_Z0"], CONST["CAV_Z1"]
LZ0, LZ1 = CONST["LID_Z0"], CONST["LID_Z1"]
MIDX, MIDY = SH / 2.0, SW / 2.0
PCB_X0 = (SH - CONST["PCB_X"]) / 2.0
PCB_Y0 = (SW - CONST["PCB_Y"]) / 2.0
PCB_X1 = PCB_X0 + CONST["PCB_X"]
PCB_Y1 = PCB_Y0 + CONST["PCB_Y"]
PZ0, PZ1 = CONST["PCB_Z"], CONST["PCB_TOP"]
FAN_Y0 = SW + CONST["FAN_PLATE_T"]          # outer face of the rear fan plate

# ---- front-panel UI (all cuts in the FIXED front wall, y = 0..WALL) --------
# Aperture: 27 x 13 centred on (DISP_X, DISP_Z) = (61, 45).  Its bottom z=38.5
# clears the nostril tops (z=36) by 2.5 mm; the bezel clears the lid seam by
# 0.5 mm at both ends of its z=36.5..53.5 envelope.
WIN_X0 = CONST["DISP_X"] - CONST["DISP_WIN_W"] / 2.0
WIN_X1 = CONST["DISP_X"] + CONST["DISP_WIN_W"] / 2.0
WIN_Z0 = CONST["DISP_Z"] - CONST["DISP_WIN_H"] / 2.0
WIN_Z1 = CONST["DISP_Z"] + CONST["DISP_WIN_H"] / 2.0
# The panel envelope is the display module footprint in X-Z.  It spans
# z=36.5..53.5: 0.5 mm above the nostril tops and 0.5 mm below the lid seam.
PAN_X0 = CONST["DISP_X"] - CONST["DISP_W"] / 2.0
PAN_X1 = CONST["DISP_X"] + CONST["DISP_W"] / 2.0
PAN_Z0 = CONST["DISP_Z"] - CONST["DISP_H"] / 2.0
PAN_Z1 = CONST["DISP_Z"] + CONST["DISP_H"] / 2.0
# No new free dimensions: acrylic thickness is the gasket thickness, and the
# outward stack depth is DISP_POD_D plus the two 1 mm gasket/acrylic layers.
# Y is negative OUTSIDE the front wall; the gasket touches the wall at y=0.
ACRYLIC_T = CONST["DISP_GASKET"]
GASKET_Y1 = 0.0
GASKET_Y0 = GASKET_Y1 - CONST["DISP_GASKET"]
ACRYLIC_Y1 = GASKET_Y0
ACRYLIC_Y0 = ACRYLIC_Y1 - ACRYLIC_T
BEZEL_Y1 = ACRYLIC_Y0
BEZEL_Y0 = BEZEL_Y1 - CONST["DISP_POD_D"]
FEED_X, FEED_Z = CONST["UI_FEED_X"], CONST["UI_FEED_Z"]
FEED_R = CONST["UI_FEED_D"] / 2.0
BTN_FRONT = CONST["BTN_FRONT"]
# Button caps cover the bores from the dry side.  Their diameter is twice the
# bore diameter (derived, not a new free dimension) and they stop at y=0.
CAP_R = CONST["BTN_HOLE_D"]
CAP_Y0 = -CONST["DISP_GASKET"]
CAP_Y1 = 0.0

BOSSES = [(CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
          (SH - CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
          (CONST["BOSS_INSET"], SW - CONST["BOSS_INSET"]),
          (SH - CONST["BOSS_INSET"], SW - CONST["BOSS_INSET"])]
STANDOFFS = [(16.0, 16.0), (SH - 16.0, 16.0),
             (16.0, SW - 16.0), (SH - 16.0, SW - 16.0)]
NO_X = (MIDX - CONST["NO_PITCH"], MIDX, MIDX + CONST["NO_PITCH"])
FAN_SCREWS = [(CONST["FAN_X"] + dx, CONST["FAN_Z"] + dz)
              for dx in (-16.0, 16.0) for dz in (-16.0, 16.0)]
# two opposing inner side-wall rows; pin lines run front-to-back (along Y) so
# a straight-header breakout stands upright and faces inward across the channel
SOCKETS = ([(CONST["AN_X"], cy) for cy in CONST["AN_Y"]] +
           [(CONST["DI_X"], cy) for cy in CONST["DI_Y"]])


def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0,
                        App.Vector(x0, y0, z0))


def cylinder(r, z0, z1, cx, cy):
    c = Part.makeCylinder(r, z1 - z0, App.Vector(cx, cy, z0), App.Vector(0, 0, 1))
    return c


def cyl_y(r, y0, y1, cx, cz):
    return Part.makeCylinder(r, y1 - y0, App.Vector(cx, y0, cz),
                             App.Vector(0, 1, 0))


doc = App.newDocument("SmellMonitor")

objs = {}  # label -> Part::Feature

# --- shell: an open tray.  Nothing else to take apart. -------------------
shell = doc.addObject("Part::Feature", "Shell")
shell.Label = "shell"
body = box(0, 0, 0, SH, SW, CZ1).cut(box(CX0, CY0, CZ0, CX1, CY1, CZ1))
for cx in NO_X:                                    # 3 x d6 intake bores
    body = body.cut(cyl_y(CONST["NO_R"], -1.0, CONST["WALL"] + 1.0,
                          cx, CONST["NO_Z"]))
body = body.cut(cyl_y(CONST["USB_R"], -1.0, CONST["WALL"] + 1.0,
                      CONST["USB_X"], CONST["USB_Z"]))
# ---- v1.1 front-panel UI: every cut in the FIXED front wall ---------------
# Display aperture (27 x 13) and one d6 harness grommet.  Both are through the
# wall only; neither touches the lid, so no wire ever crosses the lid seam.
body = body.cut(box(WIN_X0, -1.0, WIN_Z0,
                    WIN_X1, CONST["WALL"] + 1.0, WIN_Z1))
body = body.cut(cyl_y(FEED_R, -1.0, CONST["WALL"] + 1.0, FEED_X, FEED_Z))
# Four front-panel switches: MEASURE / MENU / BOOT / RESET at (x, z).
for bx, bz in BTN_FRONT.values():
    body = body.cut(cyl_y(CONST["BTN_HOLE_D"] / 2.0, -1.0,
                          CONST["WALL"] + 1.0, bx, bz))
# Filter drawer: two side rails and a bottom rail.  The pad drops in from the
# top and the lid is what holds it down - no fasteners, no adhesive.
_fz0, _rw, _rd = CONST["FILT_Z0"], CONST["RAIL_W"], CONST["RAIL_D"]
_fy0 = CONST["FILT_Y0"]
body = body.fuse(box(CX0, _fy0, _fz0 - _rw, CX1, _fy0 + _rd, _fz0))
body = body.fuse(box(CX0, _fy0, _fz0, CX0 + _rw, _fy0 + _rd, CZ1))
body = body.fuse(box(CX1 - _rw, _fy0, _fz0, CX1, _fy0 + _rd, CZ1))
for bx, by in BOSSES:                              # M3 heat-set inserts
    body = body.fuse(cylinder(CONST["BOSS_D"] / 2.0, CZ0, CZ1, bx, by))
for sx, sy in STANDOFFS:                           # board rests here
    body = body.fuse(cylinder(CONST["STANDOFF_D"] / 2.0, CZ0, PZ0, sx, sy))
# Rear fan plate: 4 mm proud of the back, so the fan sits outside the sample
# path and can be swapped without opening the box.  Screws are blind: the
# plate plus the wall is 7 mm of PETG, and no hole goes into the chamber.
body = body.fuse(box(MIDX - CONST["FAN_PLATE"] / 2.0, SW,
                     CONST["FAN_Z"] - CONST["FAN_PLATE"] / 2.0,
                     MIDX + CONST["FAN_PLATE"] / 2.0, FAN_Y0,
                     CONST["FAN_Z"] + CONST["FAN_PLATE"] / 2.0))
body = body.cut(cyl_y(CONST["FAN_R"], CY1 - 1.0, FAN_Y0 + 1.0,
                      CONST["FAN_X"], CONST["FAN_Z"]))
for sx, sz in FAN_SCREWS:
    body = body.cut(cyl_y(1.4, FAN_Y0 - 6.0, FAN_Y0 + 1.0, sx, sz))
shell.Shape = body

# --- lid: a PLAIN flat plate with four counterbored M3 screws -------------
# Nothing else cuts this plate: no window, no pod, no grommet, no switches.
# Opening the box therefore never breaks an electrical connection.
lid = doc.addObject("Part::Feature", "Lid")
lid.Label = "lid"
plate = box(0, 0, LZ0, SH, SW, LZ1)
for bx, by in BOSSES:
    plate = plate.cut(cylinder(CONST["SCREW_D"] / 2.0, LZ0 - 1.0, LZ1 + 1.0,
                               bx, by))
    plate = plate.cut(cylinder(CONST["CBORE_D"] / 2.0, LZ1 - CONST["CBORE_T"],
                               LZ1 + 1.0, bx, by))
lid.Shape = plate

# --- sealed front-panel stack, entirely OUTSIDE the front wall (y <= 0) ---
# Layer order from the wall outward: PTFE gasket ring (y=-1..0), PMMA acrylic
# sheet (y=-2..-1), then the PETG bezel ring (y=-8..-2).  The gasket and bezel
# are annular: neither occupies the 27 x 13 opening, so the only solid the
# sample gas can touch is the acrylic.  The OLED module sits behind that
# acrylic, inside the bezel cavity, wholly on the dry side.
gasket = doc.addObject("Part::Feature", "DisplayGasket")
gasket.Label = "display gasket"
gasket.Shape = box(PAN_X0, GASKET_Y0, PAN_Z0,
                   PAN_X1, GASKET_Y1, PAN_Z1).cut(
    box(WIN_X0, GASKET_Y0 - 1.0, WIN_Z0,
        WIN_X1, GASKET_Y1 + 1.0, WIN_Z1))

window = doc.addObject("Part::Feature", "DisplayWindow")
window.Label = "display window"
window.Shape = box(PAN_X0, ACRYLIC_Y0, PAN_Z0,
                   PAN_X1, ACRYLIC_Y1, PAN_Z1)

bezel = doc.addObject("Part::Feature", "DisplayBezel")
bezel.Label = "display bezel"
bezel.Shape = box(PAN_X0, BEZEL_Y0, PAN_Z0,
                  PAN_X1, BEZEL_Y1, PAN_Z1).cut(
    box(WIN_X0, BEZEL_Y0 - 1.0, WIN_Z0,
        WIN_X1, BEZEL_Y1 + 1.0, WIN_Z1))

oled = doc.addObject("Part::Feature", "DisplayOLED")
oled.Label = "OLED module"
oled.Shape = box(WIN_X0, BEZEL_Y0, WIN_Z0,
                 WIN_X1, ACRYLIC_Y0, WIN_Z1)

# Button caps are simple representations of the four front switches.  They are
# outside the wall (y <= 0), tied to BTN_FRONT, and seal their bores from the
# dry side; nothing protrudes into the sample channel.
caps = doc.addObject("Part::Feature", "ButtonCaps")
caps.Label = "button caps"
_cs = None
for bx, bz in BTN_FRONT.values():
    one = cyl_y(CAP_R, CAP_Y0, CAP_Y1, bx, bz)
    _cs = one if _cs is None else _cs.fuse(one)
caps.Shape = _cs

# --- PCB: the chamber floor, carrying the eight sockets -------------------
pcb = doc.addObject("Part::Feature", "PCB")
pcb.Label = "pcb"
plate = box(PCB_X0, PCB_Y0, PZ0, PCB_X1, PCB_Y1, PZ1)
for bx, by in BOSSES:                              # corner notches for the bosses
    plate = plate.cut(cylinder(CONST["BOSS_D"] / 2.0 + CONST["BOSS_CLEAR"],
                               PZ0 - 1.0, PZ1 + 1.0, bx, by))
_half_l = CONST["SOCK_N"] * CONST["SOCK_P"] / 2.0
for cx, cy in SOCKETS:
    # pin line runs front-to-back (Y): narrow in X, long in Y
    plate = plate.fuse(box(cx - CONST["SOCK_P"] / 2.0, cy - _half_l, PZ1,
                           cx + CONST["SOCK_P"] / 2.0, cy + _half_l,
                           PZ1 + CONST["SOCK_H"]))
pcb.Shape = plate

# --- filter pad: 110 x 4 x 23, the only consumable ------------------------
filt = doc.addObject("Part::Feature", "Filter")
filt.Label = "filter"
filt.Shape = box(CX0 + CONST["RAIL_W"], CONST["FILT_Y0"], CONST["FILT_Z0"],
                 CX1 - CONST["RAIL_W"], CONST["FILT_Y1"], CONST["FILT_Z1"])

# --- exhaust fan: d40 x t10, mounted on the rear plate --------------------
fan = doc.addObject("Part::Feature", "Fan")
fan.Label = "fan"
fs = box(CONST["FAN_X"] - 20.0, FAN_Y0, CONST["FAN_Z"] - 20.0,
         CONST["FAN_X"] + 20.0, FAN_Y0 + CONST["FAN_T"],
         CONST["FAN_Z"] + 20.0)
fs = fs.cut(cyl_y(18.0, FAN_Y0 - 1.0, FAN_Y0 + CONST["FAN_T"] + 1.0,
                  CONST["FAN_X"], CONST["FAN_Z"]))
for sx, sz in FAN_SCREWS:
    fs = fs.cut(cyl_y(1.7, FAN_Y0 - 1.0, FAN_Y0 + CONST["FAN_T"] + 1.0, sx, sz))
fan.Shape = fs

# --- four M3 x 12 lid screws ---------------------------------------------
screws = doc.addObject("Part::Feature", "Screws")
screws.Label = "screws"
ss = None
for bx, by in BOSSES:
    one = cylinder(1.5, LZ1 - 12.0, LZ1, bx, by).fuse(
        cylinder(2.75, LZ1 - CONST["CBORE_T"], LZ1, bx, by))
    ss = one if ss is None else ss.fuse(one)
screws.Shape = ss

# NOTE: ViewProvider appearance (transparency/colour) cannot be set in cmd mode
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


def cut_faces(shape, axis, coord, tol=1e-3):
    """The faces the cut created, as ordered 3D polygons (outer wire first).

    A section without hatching is a wireframe, not a section: the reader has to
    be told which material the cutting plane passes through.  These are exactly
    the planar faces that lie on the cutting plane, so the sheet can hatch them
    from real geometry instead of guessing outlines.  Inner wires are returned
    after the outer one as islands (a wall section is a ring, not a rectangle).
    """
    out = []
    for f in shape.Faces:
        try:
            if f.Surface.__class__.__name__ != "Plane":
                continue
            n = f.normalAt(0, 0)
        except Exception:
            continue
        if abs(abs(n[axis]) - 1.0) > 1e-6:
            continue
        if abs(f.CenterOfMass[axis] - coord) > tol:
            continue
        # FreeCAD 1.x has no Face.outerWire(); the outer boundary is simply the
        # wire that encloses the most area on this planar face.
        try:
            wires = sorted(list(f.Wires), key=lambda w: -Part.Face(w).Area)
        except Exception:
            wires = list(f.Wires)
        polys = []
        for w in wires:
            try:
                pts = [(p.x, p.y, p.z) for p in w.discretize(Deflection=0.05)]
            except Exception:
                pts = [(v.Point.x, v.Point.y, v.Point.z) for v in w.Vertexes]
            if len(pts) >= 3:
                polys.append(pts)
        if polys:
            out.append(polys)
    return out


display_assembly = (gasket.Shape.fuse(window.Shape).fuse(bezel.Shape)
                    .fuse(oled.Shape))
assembly = shell.Shape.fuse(lid.Shape).fuse(pcb.Shape).fuse(
    filt.Shape).fuse(fan.Shape).fuse(screws.Shape).fuse(
    display_assembly).fuse(caps.Shape)
sec_a = half_space_cut(shell.Shape, 0, MIDX, keep_less=True)      # shell
sec_b = half_space_cut(assembly, 0, MIDX, keep_less=True)         # full stack
sec_c = half_space_cut(lid.Shape, 1, CONST["BOSS_INSET"], keep_less=True)
sec_d = half_space_cut(display_assembly, 0, CONST["DISP_X"], keep_less=True)


def moved(shape, v):
    """A copy of `shape` translated by v (works whether translate copies or not)."""
    vec = App.Vector(*v)
    fn = getattr(shape, "translated", None)
    if fn is not None:
        return fn(vec)
    s = shape.copy()
    r = s.translate(vec)
    return r if r is not None else s


# Exploded general arrangement: internals come out along +Z (lid off, filter
# out, board up), the fan pulls back off its plate, and the front-panel UI
# assembly lifts straight out of the front wall along -Y.  The offsets travel
# to the drawing as data, so balloon leaders point at real exploded positions.
EXPLODE = {
    "pcb": (0, 0, 50),
    "filter": (0, 0, 80),
    "lid": (0, 0, 128),
    "screws": (0, 0, 128),
    "fan": (0, 46, 0),
    "display": (0, -2.0 * CONST["DISP_POD_D"], 0),
}
exploded = shell.Shape
for _s, _v in ((pcb.Shape, EXPLODE["pcb"]),
               (filt.Shape, EXPLODE["filter"]),
               (lid.Shape, EXPLODE["lid"]),
               (screws.Shape, EXPLODE["screws"]),
               (display_assembly, EXPLODE["display"]),
               (caps.Shape, EXPLODE["display"]),
               (fan.Shape, EXPLODE["fan"])):
    exploded = exploded.fuse(moved(_s, _v))

VIEW_REQUESTS = [
    ("shell", "FRONT", shell.Shape, (0, -1, 0)),
    ("shell", "PLAN", shell.Shape, (0, 0, 1)),
    ("shell", "SECTION_A", sec_a, (1, 0, 0)),
    ("shell", "ISO", shell.Shape, (1, -1, 1)),
    ("lid", "PLAN", lid.Shape, (0, 0, 1)),
    ("lid", "SECTION_C", sec_c, (0, 1, 0)),
    ("lid", "ISO", lid.Shape, (1, -1, 1)),
    ("display", "FRONT", display_assembly, (0, -1, 0)),
    ("display", "PLAN", display_assembly, (0, 0, 1)),
    ("display", "SECTION_D", sec_d, (1, 0, 0)),
    ("display", "ISO", display_assembly, (1, -1, 1)),
    ("assembly", "SECTION_B", sec_b, (1, 0, 0)),
    ("assembly", "ISO", assembly, (1, -1, 1)),
    ("assembly", "EXPLODED", exploded, (1, -1, 1)),
]

out = {"explode": {k: list(v) for k, v in EXPLODE.items()}}
CUTS = {
    ("shell", "SECTION_A"): cut_faces(sec_a, 0, MIDX),
    ("assembly", "SECTION_B"): cut_faces(sec_b, 0, MIDX),
    ("lid", "SECTION_C"): cut_faces(sec_c, 1, CONST["BOSS_INSET"]),
    ("display", "SECTION_D"): cut_faces(sec_d, 0, CONST["DISP_X"]),
}
for part, view, shp, direction in VIEW_REQUESTS:
    rec = hlr_view(shp, direction)
    rec["axes"] = axis_vectors(direction)
    if (part, view) in CUTS:
        rec["cuts"] = CUTS[(part, view)]
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
    """Mesh export for print services (one watertight STL per part, <= 10 MB).
    BRep solids are closed, so a fine tessellation stays manifold."""
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
_part_step(lid.Shape, "smell_monitor_lid.STEP")
_part_step(gasket.Shape, "smell_monitor_display_gasket.STEP")
_part_step(window.Shape, "smell_monitor_display_window.STEP")
_part_step(bezel.Shape, "smell_monitor_display_bezel.STEP")
_part_step(oled.Shape, "smell_monitor_display_oled.STEP")
_part_step(caps.Shape, "smell_monitor_button_caps.STEP")
_part_stl(shell.Shape, "smell_monitor_shell.stl")
_part_stl(lid.Shape, "smell_monitor_lid.stl")
_part_stl(gasket.Shape, "smell_monitor_display_gasket.stl")
_part_stl(window.Shape, "smell_monitor_display_window.stl")
_part_stl(bezel.Shape, "smell_monitor_display_bezel.stl")
_part_stl(oled.Shape, "smell_monitor_display_oled.stl")
_part_stl(caps.Shape, "smell_monitor_button_caps.stl")

print("model OK ->", OUT_FCSTD)
print("step   OK ->", OUT_STEP)
print("edges  OK ->", OUT_JSON)
