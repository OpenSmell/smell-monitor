#!/usr/bin/env python3
"""OpenSmell v1.1 CAD-native drawing sheets -> DXF (+ A3 vector PDF, PNG).

Authoring model
---------------
Geometry comes from real model hidden-line removal (HLR) computed in FreeCAD
(`mechanical/freecad/build_smell_monitor.py` -> `model_hlr.json`).  This script
never invents outlines: it places the measured visible/hidden edges onto A3
paperspace layouts at paper millimetres (420 x 297).

The HLR record also carries `axes`: the (u, v) components of the global +X/+Y/+Z
axes *measured* in that projection by the same projector.  An orthographic
projection is linear, so every view here can map a model point (x, y, z) to its
exact paper position.  That is what lets dimensions and leaders be attached to
the real features they name instead of to hand-guessed paper coordinates - a
dimension that is not on its feature is a lie, and this file refuses to guess.

Dimensions are true DIMENSION entities whose displayed value is the model
millimetre size (dimlfac = 1/s), so the DXF stays the editable CAD source and the
PDF/PNG are only plots.

Outputs (mechanical/drawings/sheets/)
  OS-000.dxf / .png     assembly + exploded view + BOM
  OS-001.dxf / .png     shell
  OS-002.dxf / .png     baffle plate
  OpenSmell_v1.1_sheets.pdf        (3 pages, exact A3, vector)

Pipeline:  FreeCAD build (model + HLR + axes)  ->  this script (sheets).
Run:  python mechanical/drawings/gen_dxf_sheets.py
"""
import json
import math
import os
import sys

import ezdxf
from ezdxf.enums import TextEntityAlignment

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST, PROCESS  # noqa: E402

HLR_JSON = os.path.join(ROOT, "mechanical", "drawings", "model_hlr.json")
OUT = os.path.join(ROOT, "mechanical", "drawings", "sheets")
os.makedirs(OUT, exist_ok=True)

with open(HLR_JSON, encoding="utf-8") as _fh:
    HLR = json.load(_fh)

PW, PH = 420.0, 297.0                 # A3 landscape, paper mm
MARGIN, BORDER = 6.0, 12.0            # trim edge + drawing border (6 mm zone strip)
TB_W, TB_H = 180.0, 40.0              # ISO 7200 title block
REV, PROJECT = "L", "OpenSmell"       # sheet revision tracks the design revision
DATE = "2026-10-18"

# ---- layers: name -> (ACI colour, linetype, lineweight 1/100 mm) -----------
LAYERS = {
    "FRAME": (7, "CONTINUOUS", 60),
    "VIS":   (7, "CONTINUOUS", 50),
    "THK":   (7, "CONTINUOUS", 70),
    "HID":   (8, "DASHED", 25),
    "CEN":   (4, "CENTER", 18),
    "DIM":   (1, "CONTINUOUS", 18),
    "HATCH": (34, "CONTINUOUS", 13),
    "TXT":   (7, "CONTINUOUS", 25),
    "BOM":   (7, "CONTINUOUS", 25),
    "SEC":   (1, "CONTINUOUS", 50),
}
_ALIGN = {"l": TextEntityAlignment.LEFT, "c": TextEntityAlignment.MIDDLE_CENTER,
          "r": TextEntityAlignment.RIGHT, "tc": TextEntityAlignment.TOP_CENTER,
          "bl": TextEntityAlignment.BOTTOM_LEFT,
          "lt": TextEntityAlignment.TOP_LEFT}


def new_doc():
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4       # millimetres
    doc.header["$LUNITS"] = 2
    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[1.0, 0.6, -0.4])
    if "CENTER" not in doc.linetypes:
        doc.linetypes.add("CENTER", pattern=[2.0, 0.6, -0.4, 0.6, -0.4])
    for name, (col, lt, lw) in LAYERS.items():
        if name not in doc.layers:
            lay = doc.layers.add(name, color=col, linetype=lt)
            lay.dxf.lineweight = lw
    ds = doc.dimstyles.get("Standard")
    ds.dxf.dimtxt = 2.6
    ds.dxf.dimasz = 1.8
    ds.dxf.dimexo = 1.2
    ds.dxf.dimexe = 1.2
    ds.dxf.dimgap = 0.8
    ds.dxf.dimdec = 0
    ds.dxf.dimtad = 1
    ds.dxf.dimtxsty = "Standard"
    return doc


def _rot(x, y, mode):
    if mode == 90:
        return (-y, x)
    if mode == 180:
        return (-x, -y)
    if mode == 270:
        return (y, -x)
    return (x, y)


def _ent_pts(e):
    """The raw projection-plane points an HLR entity spans."""
    t = e["t"]
    if t == "line":
        return (e["a"], e["b"])
    if t in ("circle", "arc"):
        c, r = e["c"], e["r"]
        return ((c[0] - r, c[1] - r), (c[0] + r, c[1] + r))
    return e["pts"]


def _arrow(psp, tip, ang_deg, size=2.4, layer="DIM"):
    a = math.radians(ang_deg)
    w = size * 0.26
    p1 = (tip[0] - size * math.cos(a) + w * math.sin(a),
          tip[1] - size * math.sin(a) - w * math.cos(a))
    p2 = (tip[0] - size * math.cos(a) - w * math.sin(a),
          tip[1] - size * math.sin(a) + w * math.cos(a))
    psp.add_solid([tip, p1, p2, tip], dxfattribs={"layer": layer})


# ===========================================================================
#  A placed HLR view, with the measured model -> paper mapping
# ===========================================================================
class View:
    """An HLR view on paper, dimensionable in model millimetres.

    Mapping (exact, because orthographic projection is linear)::

        u = ax[X][0]*x + ax[Y][0]*y + ax[Z][0]*z        (v likewise)
        paper = (left + (u' - u0)*s, bottom + (v' - v0)*s),  (u', v') = rot(u, v)

    `ax` is measured by the FreeCAD builder, never assumed (see its docstring).
    """

    def __init__(self, psp, part, view, orient, s, left, bottom, hidden=True):
        self.psp = psp
        self.rec = HLR[part][view]
        self.ax = self.rec["axes"]
        self.orient = orient
        self.s = float(s)
        self.left, self.bottom = float(left), float(bottom)
        self.hidden = hidden
        x0, y0, x1, y1 = self._raw_ext()
        corners = [_rot(x, y, orient) for x in (x0, x1) for y in (y0, y1)]
        us = [c[0] for c in corners]
        vs = [c[1] for c in corners]
        self.u0, self.v0, self.u1, self.v1 = min(us), min(vs), max(us), max(vs)
        self.draw()

    # ---- geometry ---------------------------------------------------------
    def _raw_ext(self):
        xs, ys = [], []
        for grp in ("visible", "hidden"):
            for e in self.rec[grp]:
                for p in _ent_pts(e):
                    xs.append(p[0])
                    ys.append(p[1])
        return (min(xs), min(ys), max(xs), max(ys))

    def _T(self, uv):
        u, v = _rot(uv[0], uv[1], self.orient)
        return (self.left + (u - self.u0) * self.s,
                self.bottom + (v - self.v0) * self.s)

    def P(self, x, y, z):
        """Paper coordinates of model point (x, y, z), in shell-frame mm."""
        u = (self.ax["X"][0] * x + self.ax["Y"][0] * y + self.ax["Z"][0] * z)
        v = (self.ax["X"][1] * x + self.ax["Y"][1] * y + self.ax["Z"][1] * z)
        return self._T((u, v))

    @property
    def box(self):
        return (self.left, self.bottom,
                self.left + (self.u1 - self.u0) * self.s,
                self.bottom + (self.v1 - self.v0) * self.s)

    @property
    def centre(self):
        b = self.box
        return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)

    def draw(self):
        psp = self.psp
        for grp, layer in (("visible", "VIS"), ("hidden", "HID")):
            if grp == "hidden" and not self.hidden:
                continue
            for e in self.rec[grp]:
                t = e["t"]
                if t == "line":
                    psp.add_line(self._T(e["a"]), self._T(e["b"]),
                                 dxfattribs={"layer": layer})
                elif t == "circle":
                    psp.add_circle(self._T(e["c"]), e["r"] * self.s,
                                   dxfattribs={"layer": layer})
                elif t == "arc":
                    psp.add_arc(self._T(e["c"]), e["r"] * self.s,
                                (e["a0"] + self.orient) % 360.0,
                                (e["a1"] + self.orient) % 360.0,
                                dxfattribs={"layer": layer})
                elif t == "poly":
                    psp.add_lwpolyline([self._T(p) for p in e["pts"]],
                                       dxfattribs={"layer": layer})

    # ---- dimensions (features named in model mm) --------------------------
    def _dec(self, measure):
        return 0 if abs(measure - round(measure)) < 0.01 else 1

    def _ovr(self, measure):
        return {"dimlfac": 1.0 / self.s, "dimtxt": 3.0, "dimasz": 2.0,
                "dimclrd": 1, "dimclre": 1, "dimclrt": 1,
                "dimdec": self._dec(measure), "dimtxsty": "Standard"}

    def dim_x(self, a, b, off, above=False, layer="DIM"):
        """Horizontal dimension between two model points, `off` mm below them."""
        A, B = self.P(*a), self.P(*b)
        m = abs(B[0] - A[0]) / self.s
        y = ((max(A[1], B[1]) + off) if above else (min(A[1], B[1]) - off))
        self.psp.add_linear_dim(base=(A[0], y), p1=A, p2=B, angle=0,
                                override=self._ovr(m),
                                dxfattribs={"layer": layer}).render()

    def dim_y(self, a, b, off, side="left", layer="DIM"):
        """Vertical dimension between two model points, `off` mm to one side."""
        A, B = self.P(*a), self.P(*b)
        m = abs(B[1] - A[1]) / self.s
        x = (min(A[0], B[0]) - off) if side == "left" else (max(A[0], B[0]) + off)
        self.psp.add_linear_dim(base=(x, A[1]), p1=A, p2=B, angle=90,
                                override=self._ovr(m),
                                dxfattribs={"layer": layer}).render()

    def chain_x(self, pts, off, above=False, layer="DIM"):
        """A line of horizontal dimensions through a list of model points."""
        for a, b in zip(pts, pts[1:]):
            self.dim_x(a, b, off, above, layer)

    def chain_y(self, pts, off, side="left", layer="DIM"):
        for a, b in zip(pts, pts[1:]):
            self.dim_y(a, b, off, side, layer)

    # ---- annotation -------------------------------------------------------
    def leader(self, model_pt, dx, dy, text, size=2.4, layer="DIM"):
        psp = self.psp
        p = self.P(*model_pt)
        tail = (p[0] + dx, p[1] + dy)
        _arrow(psp, p, math.degrees(math.atan2(tail[1] - p[1], tail[0] - p[0])))
        psp.add_line(p, tail, dxfattribs={"layer": layer})
        w = 0.60 * size * len(text) + 3.0
        right = dx >= 0
        end = (tail[0] + w, tail[1]) if right else (tail[0] - w, tail[1])
        psp.add_line(tail, end, dxfattribs={"layer": layer})
        x = tail[0] + 1.6 if right else tail[0] - 1.6
        psp.add_text(text, height=size, dxfattribs={"layer": "TXT"}).set_placement(
            (x, tail[1] + 1.0), align=_ALIGN["l" if right else "r"])

    def balloon(self, model_pt, dx, dy, num, r=3.6):
        psp = self.psp
        p = self.P(*model_pt)
        c = (p[0] + dx, p[1] + dy)
        ang = math.degrees(math.atan2(p[1] - c[1], p[0] - c[0]))
        edge = (c[0] + r * math.cos(math.radians(ang)),
                c[1] + r * math.sin(math.radians(ang)))
        psp.add_line(edge, p, dxfattribs={"layer": "VIS"})
        _arrow(psp, p, ang)
        psp.add_circle(c, r, dxfattribs={"layer": "TXT"})
        psp.add_text(str(num), height=2.8,
                     dxfattribs={"layer": "TXT"}).set_placement(c, align=_ALIGN["c"])


# ===========================================================================
#  Sheet furniture
# ===========================================================================
def frame(psp):
    # ISO 5457 sheet: trim line, drawing border, and a zone reference grid
    # (columns 1..6 across, rows A..D down) for locating features.
    psp.add_lwpolyline([(MARGIN, MARGIN), (PW - MARGIN, MARGIN),
                        (PW - MARGIN, PH - MARGIN), (MARGIN, PH - MARGIN)],
                       close=True, dxfattribs={"layer": "FRAME"})
    psp.add_lwpolyline([(BORDER, BORDER), (PW - BORDER, BORDER),
                        (PW - BORDER, PH - BORDER), (BORDER, PH - BORDER)],
                       close=True, dxfattribs={"layer": "VIS"})
    nx, ny = 6, 4
    xc = (MARGIN + BORDER) / 2.0
    yc = (MARGIN + BORDER) / 2.0
    for i in range(nx):
        xa = BORDER + (PW - 2 * BORDER) * i / nx
        xb = BORDER + (PW - 2 * BORDER) * (i + 1) / nx
        if i:
            psp.add_line((xa, MARGIN), (xa, BORDER), dxfattribs={"layer": "VIS"})
            psp.add_line((xa, PH - BORDER), (xa, PH - MARGIN),
                         dxfattribs={"layer": "VIS"})
        for yy in (yc, PH - yc):
            psp.add_text(str(i + 1), height=2.6,
                         dxfattribs={"layer": "TXT"}).set_placement(
                ((xa + xb) / 2.0, yy), align=_ALIGN["c"])
    for j in range(ny):
        ya = BORDER + (PH - 2 * BORDER) * j / ny
        yb = BORDER + (PH - 2 * BORDER) * (j + 1) / ny
        if j:
            psp.add_line((MARGIN, ya), (BORDER, ya), dxfattribs={"layer": "VIS"})
            psp.add_line((PW - BORDER, ya), (PW - MARGIN, ya),
                         dxfattribs={"layer": "VIS"})
        for xx in (xc, PW - xc):
            psp.add_text(chr(ord("A") + j), height=2.6,
                         dxfattribs={"layer": "TXT"}).set_placement(
                (xx, (ya + yb) / 2.0), align=_ALIGN["c"])


def first_angle_symbol(psp, x, y, s=1.0):
    psp.add_circle((x + 15 * s, y + 11 * s), 5.0 * s, dxfattribs={"layer": "VIS"})
    psp.add_line((x, y), (x + 10 * s, y), dxfattribs={"layer": "VIS"})
    psp.add_line((x + 10 * s, y), (x + 6.5 * s, y + 14 * s), dxfattribs={"layer": "VIS"})
    psp.add_line((x + 6.5 * s, y + 14 * s), (x, y + 14 * s), dxfattribs={"layer": "VIS"})
    for t in (0.3, 0.5, 0.7, 0.9):
        psp.add_line((x + 10 * s * t, y), (x + 6.5 * s * t, y + 14 * s),
                     dxfattribs={"layer": "VIS"})


def _fit(text, width, hgt):
    """Truncate text so it cannot overflow a cell of `width` at text height."""
    maxc = max(3, int(width / (0.62 * hgt)))
    return text if len(text) <= maxc else text[:maxc - 1].rstrip() + "\u2026"


def title_block(psp, f):
    x1, y0 = PW - BORDER, BORDER
    x0, y1 = x1 - TB_W, y0 + TB_H
    xm = x0 + 125.0                    # info column | scale/logo column

    def rect(a, b, ww, hh, layer="VIS"):
        psp.add_lwpolyline([(a, b), (a + ww, b), (a + ww, b + hh), (a, b + hh)],
                           close=True, dxfattribs={"layer": layer})

    def line(a, b, c, d, layer="VIS"):
        psp.add_line((a, b), (c, d), dxfattribs={"layer": layer})

    def txt(x, y, s, hgt, align="bl", layer="TXT"):
        psp.add_text(s, height=hgt, dxfattribs={"layer": layer}).set_placement(
            (x, y), align=_ALIGN[align])

    rect(x0, y0, TB_W, TB_H, "THK")
    line(xm, y0, xm, y1)                                   # column divider

    # left column bands (bottom -> top): DRAWN | MATERIAL/FINISH | DWG No. | TITLE
    b1, b2, b3 = y0 + 9.0, y0 + 21.0, y0 + 29.0
    line(x0, b1, xm, b1)
    line(x0, b2, xm, b2)
    line(x0, b3, xm, b3)
    line(x0 + 78, b3, x0 + 78, y1)                         # DWG No. | REV
    line(x0 + 100, b3, x0 + 100, y1)                       # REV | SHEET
    line(x0 + 46, y0, x0 + 46, b1)                         # DRAWN | CHECK
    line(x0 + 92, y0, x0 + 92, b1)                         # CHECK | DATE

    # right column bands: SCALE | SIZE | PROJECTION + logo
    r1, r2 = y0 + 19.0, y0 + 28.0
    line(xm, r1, x1, r1)
    line(xm, r2, x1, r2)

    txt(x0 + 2, b3 + 3.6, f["title"], 4.4)
    txt(x0 + 2, b2 + 1.5, "DRAWING No.   " + f["no"], 3.4)
    txt(x0 + 80, b2 + 1.5, "REV " + REV, 3.0)
    txt(x0 + 102, b2 + 1.5, "SHEET %s/%s" % (f["sheet"], f["sheets"]), 2.8)
    txt(x0 + 2, b1 + 6.0, _fit("MATERIAL   " + f["material"], 121, 2.4), 2.4)
    txt(x0 + 2, b1 + 2.0, _fit("FINISH       " + f["finish"], 121, 2.4), 2.4)
    txt(x0 + 2, y0 + 1.5, "DRAWN  OpenSmell", 2.4)
    txt(x0 + 48, y0 + 1.5, "CHECK  \u2013", 2.4)
    txt(x0 + 94, y0 + 1.5, "DATE  " + DATE, 2.4)

    txt(xm + 2, r2 + 3.6, "SCALE   " + f["scale"], 3.2)
    txt(xm + 2, r1 + 5.6, "SIZE   A3", 2.6)
    txt(xm + 2, r1 + 2.4, "UNITS   mm", 2.6)
    txt(xm + 2, y0 + 15.8, "FIRST ANGLE", 2.4)
    txt(xm + 2, y0 + 12.6, "(ISO 128)", 2.4)
    first_angle_symbol(psp, xm + 34, y0 + 3.0, 0.62)

    # notes live just above the block (keeps the cells uncluttered)
    txt(x1, y1 + 2.4, "NOTES:  " + f["notes"], 2.3, "r")
    txt(x1, y1 + 5.2, "GENERAL TOLERANCE  " + PROCESS["tolerance_general"]
        + "   \u00b7   PROJECT " + PROJECT + " v1.1  REV " + REV, 2.3, "r")


def caption(psp, x, y, text):
    psp.add_text(text, height=3.0, dxfattribs={"layer": "TXT"}).set_placement(
        (x, y), align=_ALIGN["c"])


def notes_block(psp, x, y, lines, size=2.5, lead=3.6):
    """A numbered general-notes list, top-left anchored at (x, y)."""
    psp.add_text("NOTES", height=3.0,
                 dxfattribs={"layer": "TXT"}).set_placement((x, y))
    for i, t in enumerate(lines):
        psp.add_text("%d.  %s" % (i + 1, t), height=size,
                     dxfattribs={"layer": "TXT"}).set_placement(
            (x, y - lead * (i + 1)))


def section_marker(psp, x, y, label, size=3.0):
    """A section flag: a filled triangle with the section letter."""
    psp.add_solid([(x, y), (x - 3.2, y - 5.0), (x + 3.2, y - 5.0), (x, y)],
                  dxfattribs={"layer": "SEC"})
    psp.add_text(label, height=size,
                 dxfattribs={"layer": "TXT"}).set_placement((x, y + 1.2),
                                                            align=_ALIGN["c"])


def bom(psp, x0, y0):
    n_wells = len(CONST["A_X"]) + len(CONST["D_X"])
    rows = [
        ("1", "Shell  %d\u00d7%d\u00d7%d, cavity %d\u00d7%d\u00d7%d" % (
            CONST["SH"], CONST["SW"], CONST["SHH"],
            CONST["CX"], CONST["CY"], CONST["CH"]), "1",
         "PETG FDM (or AL 6061-T6)", "make"),
        ("2", "Baffle plate  %d\u00d7%d\u00d7%d, %d wells + ref port" % (
            CONST["CX"], CONST["CY"], CONST["BAFFLE_T"], n_wells), "1",
         "PTFE machined (or PVDF)", "make"),
        ("3", "Filter pack, full-lane series element",
         "1", "pleated PTFE, \u226570 cm\u00b2 media", "buy"),
        ("4", "Main PCB  %d\u00d7%d, sealed chamber floor" % (
            CONST["PCB_X"], CONST["PCB_Y"]), "1",
         "FR4 1.6 mm + build (OS-003)", "make"),
        ("5", "Axial fan  DIA40 \u00d7 t10, 5 V", "1",
         "off-the-shelf (any 40 mm)", "buy"),
    ]
    colw = [12, 92, 10, 74, 14]
    psp.add_text("BILL OF MATERIALS", height=3.4,
                 dxfattribs={"layer": "TXT"}).set_placement((x0, y0 + 9))
    heads = ["ITEM", "PART / DESCRIPTION", "QTY", "MATERIAL / SOURCE", "TYPE"]
    x = x0
    for h, wd in zip(heads, colw):
        psp.add_text(h, height=2.7, dxfattribs={"layer": "TXT"}).set_placement(
            (x + 1, y0 + 0.6))
        psp.add_lwpolyline([(x, y0 - 4), (x + wd, y0 - 4), (x + wd, y0 + 5),
                            (x, y0 + 5)], close=True, dxfattribs={"layer": "DIM"})
        x += wd
    y = y0 - 4
    for r in rows:
        x = x0
        for i, v in enumerate(r):
            psp.add_text(v, height=2.6, dxfattribs={"layer": "TXT"}).set_placement(
                (x + 1, y - 4))
            x += colw[i]
        y -= 6.0
        psp.add_line((x0, y), (x0 + sum(colw), y), dxfattribs={"layer": "DIM"})
    psp.add_lwpolyline([(x0, y), (x0 + sum(colw), y), (x0 + sum(colw), y0 - 4),
                        (x0, y0 - 4)], close=True, dxfattribs={"layer": "DIM"})
    psp.add_text("geometry from real HLR of the v1.1 solid; all dims mm; "
                 "per blueprint.md 0.4", height=2.4,
                 dxfattribs={"layer": "TXT"}).set_placement((x0, y - 6))


# ===========================================================================
#  Sheets
# ===========================================================================
COMMON = dict(project=PROJECT, notes="all dims mm; deburr/de-flash; "
              "seal wetted faces; print thin parts 0.2 mm layer")

A_X, D_X = CONST["A_X"], CONST["D_X"]
CX0, CY0 = CONST["WSIDE"], CONST["WFB"]
CX1, CY1 = CX0 + CONST["CX"], CY0 + CONST["CY"]
BZ, BT = CONST["BAFFLE_Z"], CONST["BAFFLE_T"]
MIDX = CONST["SH"] / 2.0


def sheet_assembly(doc):
    psp = doc.layouts.new("OS-000")
    psp.page_setup(size=(PW, PH), margins=(0, 0, 0, 0), units="mm")
    frame(psp)
    psp.add_text("ASSEMBLY \u2013 OpenSmell v1.1 sensing platform", height=5,
                 dxfattribs={"layer": "TXT"}).set_placement(
        (PW / 2, PH - 18), align=_ALIGN["c"])
    psp.add_text("exploded isometric (parts separated along the assembly axis) "
                 "+ general arrangement \u2013 shell, baffle plate, filter pack, "
                 "PCB chamber floor, DIA40 exhaust fan", height=3,
                 dxfattribs={"layer": "TXT"}).set_placement(
        (PW / 2, PH - 24), align=_ALIGN["c"])

    ex = View(psp, "assembly", "EXPLODED", 0, 0.42, 152, 92, hidden=False)
    caption(psp, ex.centre[0], 84, "EXPLODED \u2013 assembly order  (NTS)")
    off = HLR["explode"]
    ex.balloon((MIDX, CONST["SW"] / 2, CONST["SHH"] - 8), -46, 30, 1)
    ex.balloon((CX0 + CONST["CX"] / 2, CY0 + CONST["CY"] / 2,
                BZ + BT / 2 + off["baffle"][2]), -40, -26, 2)
    ex.balloon((MIDX, CONST["FILT_Y0"] + CONST["FILT_T"] / 2,
                (BZ + CONST["FLOOR"] + CONST["CH"]) / 2 + off["filter"][2]),
               6, 44, 3)
    ex.balloon((MIDX, CONST["SW"] / 2,
                CONST["PCB_Z"] + CONST["PCB_T"] / 2 + off["pcb"][2]), -46, -8, 4)
    ex.balloon((CONST["FAN_X"], CONST["FAN_Y"] + CONST["FAN_T"] / 2,
                CONST["FAN_Z"] + off["fan"][2]), 40, 8, 5)

    ga = View(psp, "assembly", "ISO", 0, 0.26, 262, 132, hidden=True)
    caption(psp, ga.centre[0], 126, "ISO \u2013 general arrangement  (NTS)")

    bom(psp, 20.0, 232.0)
    notes_block(psp, 264, 108, [
        "ENVELOPE %d \u00d7 %d \u00d7 %d; CAVITY %d \u00d7 %d \u00d7 %d." % (
            CONST["SH"], CONST["SW"], CONST["SHH"], CONST["CX"], CONST["CY"],
            CONST["CH"]),
        "FLOW: DIA6 INTAKE \u2192 FILTER \u2192 11 mm LANE \u2192 8 WELLS "
        "\u2192 DUCT \u2192 DIA40 FAN.",
        "PCB = CHAMBER FLOOR (OS-001); CARTRIDGES LIFT OUT WITH THE PLATE.",
        "NO SILICONE, PVC, PAPER OR FOAM WHERE THE SAMPLE TOUCHES.",
        "ITEM NUMBERS MATCH THE BOM; EXPLODED IS A TRUE HLR.",
    ])
    title_block(psp, dict(COMMON, title="ASSEMBLY", no="OS-000", sheet="1",
                          sheets="3", scale="NTS", material="see BOM",
                          finish="see BOM"))
    return psp


def sheet_shell(doc):
    psp = doc.layouts.new("OS-001")
    psp.page_setup(size=(PW, PH), margins=(0, 0, 0, 0), units="mm")
    frame(psp)
    psp.add_text("SHELL \u2013 main body  (OS-001)", height=5,
                 dxfattribs={"layer": "TXT"}).set_placement(
        (PW / 2, PH - 18), align=_ALIGN["c"])

    # ---- FRONT: X (horizontal) x Z (vertical), 1:2 ----------------------
    v = View(psp, "shell", "FRONT", 270, 0.5, 74, 206)
    caption(psp, v.centre[0], 184, "FRONT (intake face)  1:2")
    v.dim_x((0, 0, 0), (CONST["SH"], 0, 0), 16)                     # 122
    v.chain_x([(MIDX - 26, 0, 0), (MIDX, 0, 0), (MIDX + 26, 0, 0)], 8)  # 26/26
    v.dim_y((0, 0, 0), (0, 0, CONST["SHH"]), 13, "left")             # 90
    v.chain_y([(CONST["SH"], 0, 0), (CONST["SH"], 0, CONST["FLOOR"]),
               (CONST["SH"], 0, CONST["NO_Z"])], 13, "right")        # 12 / 43
    v.leader((MIDX, 0, CONST["NO_Z"]), 30, 20,
             "3 \u00d7 DIA%d through, bore axis z=%d" % (
                 2 * CONST["NO_R"], CONST["NO_Z"]))
    section_marker(psp, 74 + MIDX * 0.5, 256, "B")

    # ---- PLAN: X (horizontal) x Y (vertical), 1:2 ------------------------
    p = View(psp, "shell", "PLAN", 0, 0.5, 74, 104)
    caption(psp, p.centre[0], 82, "PLAN (PCB seat not fitted)  1:2")
    p.chain_x([(0, 0, 0), (CX0, 0, 0), (CX1, 0, 0), (CONST["SH"], 0, 0)], 8)
    p.dim_x((0, 0, 0), (CONST["SH"], 0, 0), 16)
    p.chain_y([(CONST["SH"], 0, 0), (CONST["SH"], CY0, 0),
               (CONST["SH"], CY1, 0), (CONST["SH"], CONST["SW"], 0)],
              8, "right")
    p.dim_y((CONST["SH"], 0, 0), (CONST["SH"], CONST["SW"], 0), 16, "right")
    p.leader((CX0, CY0 + CONST["CY"] / 2, CONST["FLOOR"]), -26, -46,
             "cavity %d \u00d7 %d \u00d7 %d" % (
                 CONST["CX"], CONST["CY"], CONST["CH"]))

    # ---- SECTION B-B through x=61: Y (horizontal) x Z (vertical), 1:2 ----
    s = View(psp, "shell", "SECTION_BB", 90, 0.5, 232, 206)
    caption(psp, s.centre[0], 184, "SECTION B-B (x=%d)  1:2" % MIDX)
    s.dim_x((0, 0, 0), (0, CONST["SW"], 0), 16)                      # 114
    s.chain_y([(0, 0, 0), (0, 0, CONST["FLOOR"]), (0, 0, BZ),
               (0, 0, CONST["FLOOR"] + CONST["CH"]), (0, 0, CONST["SHH"])],
              11, "left")                                            # 12/37/11/30
    s.dim_y((0, 0, 0), (0, 0, CONST["SHH"]), 11, "right")            # 90
    s.leader((0, CONST["FAN_Y"], CONST["FAN_Z"]), -30, -26,
             "DIA%d exhaust, axis z=%d" % (
                 2 * CONST["FAN_R"], CONST["FAN_Z"]))
    s.leader((0, CONST["FILT_Y0"], CONST["FLOOR"] + 3), 48, -26,
             "filter plane y=%d\u2013%d (pack not shown)" % (
                 CONST["FILT_Y0"], CONST["FILT_Y0"] + CONST["FILT_T"]))

    iso = View(psp, "shell", "ISO", 0, 0.30, 314, 96, hidden=False)
    caption(psp, iso.centre[0], 90, "ISO \u2013 shell, cavity and baffle plane"
            "  (NTS)")

    notes_block(psp, 170, 128, [
        "MATERIAL: PETG FDM, 0.2 mm LAYER, 4 PERIMETERS; SEAL WETTED FACES.",
        "PCB SEAT REBATE 1.6 DEEP: THE BOARD IS THE SEALED CHAMBER FLOOR "
        "(z=%d)." % CONST["FLOOR"],
        "BAFFLE PLANE z=%d (%d ABOVE THE FLOOR). MODULE ALLOWANCE %d, "
        "RECESS %d." % (BZ, BZ - CONST["FLOOR"],
                        CONST["BAFFLE_Z"] - CONST["FLOOR"] - 8, 8),
        "ALL OPENINGS DEBURRED; NO SILICONE, PVC OR FOAM IN THE GAS PATH.",
        "DIMS IN mm; DATUM = FRONT-LOWER-LEFT OUTER CORNER.",
    ])
    title_block(psp, dict(COMMON, title="SHELL \u2013 main body", no="OS-001",
                          sheet="2", sheets="3", scale="1:2",
                          material=PROCESS["shell"]["primary"],
                          finish=PROCESS["shell"]["finish"]))
    return psp


def sheet_baffle(doc):
    psp = doc.layouts.new("OS-002")
    psp.page_setup(size=(PW, PH), margins=(0, 0, 0, 0), units="mm")
    frame(psp)
    psp.add_text("BAFFLE \u2013 well plate  (OS-002)", height=5,
                 dxfattribs={"layer": "TXT"}).set_placement(
        (PW / 2, PH - 18), align=_ALIGN["c"])

    # ---- PLAN: X (horizontal) x Y (vertical), 1:2 ------------------------
    p = View(psp, "baffle", "PLAN", 0, 0.5, 66, 202)
    caption(psp, p.centre[0], 188,
            "PLAN (%d wells + reference port)  1:2" % (len(A_X) + len(D_X)))
    p.chain_x([(CX0, CY0, 0)] + [(x, CY0, 0) for x in A_X] + [(CX1, CY0, 0)], 8)
    p.dim_x((CX0, CY0, 0), (CX1, CY0, 0), 16)                        # 106
    p.chain_x([(CX0, CY1, 0)] + [(x, CY1, 0) for x in D_X] + [(CX1, CY1, 0)],
              8, above=True)
    p.dim_y((CX1, CY0, 0), (CX1, CY1, 0), 16, "right")                # 100
    p.dim_y((CX1, CONST["D_Y0"], 0), (CX1, CONST["D_Y0"] + CONST["D_SY"], 0),
            8, "right")
    p.dim_y((CX1, CONST["A_Y0"], 0), (CX1, CONST["A_Y0"] + CONST["A_SY"], 0),
            8, "right")
    p.dim_y((CX1, CONST["SHT_Y0"], 0),
            (CX1, CONST["SHT_Y0"] + CONST["SHT_SY"], 0), 8, "right")
    p.leader((A_X[0], CONST["A_Y0"] + CONST["A_SY"] / 2, BZ), -20, 34,
             "4 \u00d7 %d \u00d7 %d analog wells" % (CONST["A_SX"], CONST["A_SY"]))
    p.leader((D_X[0], CONST["D_Y0"] + CONST["D_SY"] / 2, BZ), -20, 34,
             "4 \u00d7 %d \u00d7 %d digital wells" % (
                 CONST["D_SX"], CONST["D_SY"]))
    p.leader((CONST["SHT_X"], CONST["SHT_Y0"] + CONST["SHT_SY"] / 2, BZ),
             -26, -16, "U5 port %d \u00d7 %d" % (
                 CONST["SHT_SX"], CONST["SHT_SY"]))

    # ---- SECTION A-A through an analog well row: X x Z, 1:1 --------------
    a = View(psp, "baffle", "SECTION_AA", 270, 1.0, 66, 150, hidden=False)
    caption(psp, a.centre[0], 136, "SECTION A-A (analog well row)  1:1")
    a.dim_x((CX0, 0, BZ), (CX1, 0, BZ), 8)                           # 106
    a.chain_x([(A_X[0] - CONST["A_SX"] / 2, 0, BZ),
               (A_X[0] + CONST["A_SX"] / 2, 0, BZ)], 8)              # 22
    a.chain_x([(A_X[0] + CONST["A_SX"] / 2, 0, BZ),
               (A_X[1] - CONST["A_SX"] / 2, 0, BZ)], 8)              # 4 rib
    a.chain_y([(0, 0, BZ - BT), (0, 0, BZ)], 16)                     # 2
    a.leader((A_X[0], 0, BZ - BT / 2), 26, -22,
             "well open-bottom (through plate)")

    iso = View(psp, "baffle", "ISO", 0, 0.50, 296, 158, hidden=False)
    caption(psp, iso.centre[0], 152, "ISO \u2013 wells open-bottom  (NTS)")

    notes_block(psp, 264, 258, [
        "MATERIAL: PTFE, MACHINED. SUBSTITUTE: PVDF OR BOROSILICATE.",
        "PLATE %d \u00d7 %d \u00d7 %d, SEATS ON THE SHELL LEDGE AT z=%d." % (
            CONST["CX"], CONST["CY"], BT, BZ - BT),
        "WELL ORDER IS FLOW ORDER: DIGITAL UPSTREAM, ANALOG DOWNSTREAM.",
        "EVERY WELL IS OPEN-BOTTOM: THE CELL READS THE SUB-BAFFLE VOLUME.",
        "ANALOG WELLS %d \u00d7 %d, DIGITAL WELLS %d \u00d7 %d (4 EACH)." % (
            CONST["A_SX"], CONST["A_SY"], CONST["D_SX"], CONST["D_SY"]),
        "GENERAL TOLERANCE ISO 2768-mK; WETTED FACES FREE OF RESIDUE.",
    ])
    title_block(psp, dict(COMMON, title="BAFFLE \u2013 well plate", no="OS-002",
                          sheet="3", sheets="3", scale="AS NOTED",
                          material=PROCESS["baffle"]["primary"],
                          finish=PROCESS["baffle"]["finish"]))
    return psp


# ===========================================================================
#  Plot: DXF -> exact-A3 vector PDF + PNG
# ===========================================================================
def plot(sheets):
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.pymupdf import PyMuPdfBackend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.layout import Page, Units, Settings
    from ezdxf.addons.drawing.config import Configuration, ColorPolicy
    from ezdxf.math import BoundingBox2d
    import matplotlib.pyplot as plt
    from pypdf import PdfWriter, PdfReader
    import io

    # Engineering drawings are monochrome: layers differ by lineweight/linetype,
    # not colour (screen colours are a CAD convention, not a drawing board one).
    cfg = Configuration(color_policy=ColorPolicy.MONOCHROME, lineweight_scaling=1.0)
    box = BoundingBox2d([(0, 0), (PW, PH)])
    page = Page(PW, PH, Units.mm)
    settings = Settings(fit_page=False)
    writer = PdfWriter()
    for doc, lay in sheets:
        b = PyMuPdfBackend()
        Frontend(RenderContext(doc), b, config=cfg).draw_layout(lay)
        replay = b.get_replay(page, settings=settings, render_box=box)
        writer.append(PdfReader(io.BytesIO(replay.doc.tobytes())))
        fig = plt.figure(figsize=(PW / 25.4, PH / 25.4))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(
            lay, finalize=True)
        fig.savefig(os.path.join(OUT, lay.name + ".png"), dpi=150)
        plt.close(fig)
    out_pdf = os.path.join(OUT, "OpenSmell_v1.1_sheets.pdf")
    with open(out_pdf, "wb") as fh:
        writer.write(fh)
    print("pdf  OK ->", out_pdf)


SHEETS = (("OS-000_assembly", sheet_assembly), ("OS-001_shell", sheet_shell),
          ("OS-002_baffle", sheet_baffle))


def generate():
    sheets = []
    for name, builder in SHEETS:
        doc = new_doc()
        lay = builder(doc)
        sheets.append((doc, lay))
    for doc, lay in sheets:
        path = os.path.join(OUT, lay.name + ".dxf")
        doc.saveas(path)
        print("dxf  OK ->", path)
    plot(sheets)
    return os.path.join(OUT, "OpenSmell_v1.1_sheets.pdf")


if __name__ == "__main__":
    generate()
