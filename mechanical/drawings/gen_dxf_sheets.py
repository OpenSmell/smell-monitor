#!/usr/bin/env python3
"""OpenSmell v1.1 CAD-native drawing sheets -> DXF (+ A3 vector PDF, PNG).

Authoring model
---------------
Geometry comes from real model hidden-line removal (HLR) computed in FreeCAD
(`mechanical/freecad/build_smell_monitor.py` -> `model_hlr.json`).  This script
never invents outlines: it places the measured visible/hidden edges onto A3
paperspace layouts at 1:1 paper millimetres (420 x 297), with true DIMENSION
entities whose displayed value is the model millimetre size (dimlfac = 1/s).
The DXF is the authoritative, editable CAD source; the PDF and PNG are plots.

Outputs (mechanical/drawings/sheets/)
  OS-000.dxf / .png     assembly
  OS-001.dxf / .png     shell
  OS-002.dxf / .png     baffle
  OpenSmell_v1.1_sheets.pdf        (3 pages, exact A3, vector)

Pipeline:  FreeCAD build (model + HLR)  ->  this script (sheets).
Run:  python mechanical/drawings/gen_dxf_sheets.py
"""
import json
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
MARGIN, BORDER = 8.0, 10.0
TB_W, TB_H = 170.0, 44.0              # ISO 7200 style title block
REV, PROJECT = "A", "OpenSmell"

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
          "bl": TextEntityAlignment.BOTTOM_LEFT}


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


# ===========================================================================
#  HLR geometry on paper
# ===========================================================================
def _rot(x, y, mode):
    if mode == 90:
        return (-y, x)
    if mode == 180:
        return (-x, -y)
    if mode == 270:
        return (y, -x)
    return (x, y)


def _ext(view, orient):
    xs, ys = [], []
    for grp in ("visible", "hidden"):
        for e in view[grp]:
            t = e["t"]
            if t == "line":
                pts = (e["a"], e["b"])
            elif t in ("circle", "arc"):
                pts = ((e["c"][0] - e["r"], e["c"][1] - e["r"]),
                       (e["c"][0] + e["r"], e["c"][1] + e["r"]))
            else:
                pts = e["pts"]
            for p in pts:
                u, v = _rot(p[0], p[1], orient)
                xs.append(u)
                ys.append(v)
    return (min(xs), min(ys), max(xs), max(ys))


def place_view(psp, view, orient, s, left, bottom, hidden=True):
    """Draw an HLR view so its lower-left oriented corner sits at (left,bottom)."""
    minx, miny, _, _ = _ext(view, orient)

    def T(x, y):
        u, v = _rot(x, y, orient)
        return (left + (u - minx) * s, bottom + (v - miny) * s)

    def group(ents, layer):
        for e in ents:
            t = e["t"]
            if t == "line":
                psp.add_line(T(*e["a"]), T(*e["b"]), dxfattribs={"layer": layer})
            elif t == "circle":
                psp.add_circle(T(*e["c"]), e["r"] * s, dxfattribs={"layer": layer})
            elif t == "arc":
                psp.add_arc(T(*e["c"]), e["r"] * s,
                            (e["a0"] + orient) % 360.0,
                            (e["a1"] + orient) % 360.0,
                            dxfattribs={"layer": layer})
            elif t == "poly":
                psp.add_lwpolyline([T(*p) for p in e["pts"]],
                                   dxfattribs={"layer": layer})

    group(view["visible"], "VIS")
    if hidden:
        group(view["hidden"], "HID")
    w = (_ext(view, orient)[2] - minx) * s
    h = (_ext(view, orient)[3] - miny) * s
    return (left, bottom, left + w, bottom + h)


def dim_h(psp, x0, x1, y_line, y_feat, s, layer="DIM"):
    over = {"dimlfac": 1.0 / s, "dimtxt": 2.4, "dimasz": 1.6,
            "dimclrd": 1, "dimclre": 1, "dimclrt": 1, "dimtxsty": "Standard"}
    d = psp.add_linear_dim(base=(x0, y_line), p1=(x0, y_feat), p2=(x1, y_feat),
                           angle=0, override=over, dxfattribs={"layer": layer})
    d.render()


def dim_v(psp, y0, y1, x_line, x_feat, s, layer="DIM"):
    over = {"dimlfac": 1.0 / s, "dimtxt": 2.4, "dimasz": 1.6,
            "dimclrd": 1, "dimclre": 1, "dimclrt": 1, "dimtxsty": "Standard"}
    d = psp.add_linear_dim(base=(x_line, y0), p1=(x_feat, y0), p2=(x_feat, y1),
                           angle=90, override=over, dxfattribs={"layer": layer})
    d.render()


# ===========================================================================
#  Sheet furniture
# ===========================================================================
def frame(psp):
    psp.add_lwpolyline([(MARGIN, MARGIN), (PW - MARGIN, MARGIN),
                        (PW - MARGIN, PH - MARGIN), (MARGIN, PH - MARGIN)],
                       close=True, dxfattribs={"layer": "FRAME"})
    psp.add_lwpolyline([(BORDER, BORDER), (PW - BORDER, BORDER),
                        (PW - BORDER, PH - BORDER), (BORDER, PH - BORDER)],
                       close=True, dxfattribs={"layer": "VIS"})


def first_angle_symbol(psp, x, y, s=1.0):
    psp.add_circle((x + 15 * s, y + 11 * s), 5.0 * s, dxfattribs={"layer": "VIS"})
    psp.add_line((x, y), (x + 10 * s, y), dxfattribs={"layer": "VIS"})
    psp.add_line((x + 10 * s, y), (x + 6.5 * s, y + 14 * s), dxfattribs={"layer": "VIS"})
    psp.add_line((x + 6.5 * s, y + 14 * s), (x, y + 14 * s), dxfattribs={"layer": "VIS"})
    for t in (0.3, 0.5, 0.7, 0.9):
        psp.add_line((x + 10 * s * t, y), (x + 6.5 * s * t, y + 14 * s),
                     dxfattribs={"layer": "VIS"})


def title_block(psp, f):
    x0, y0 = PW - BORDER - TB_W, BORDER
    x1, y1 = PW - BORDER, BORDER + TB_H
    psp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                       dxfattribs={"layer": "THK"})
    col = 42.0
    xm = x1 - col
    psp.add_line((xm, y0), (xm, y1), dxfattribs={"layer": "VIS"})
    for i in range(1, 4):
        psp.add_line((xm, y0 + i * TB_H / 4), (x1, y0 + i * TB_H / 4),
                     dxfattribs={"layer": "VIS"})
    a = y0 + TB_H * 0.46
    psp.add_line((x0, a), (x1, a), dxfattribs={"layer": "VIS"})
    psp.add_line((x0 + 100, a), (x0 + 100, y1), dxfattribs={"layer": "VIS"})
    psp.add_line((x0, y0 + TB_H * 0.74), (x0 + 100, y0 + TB_H * 0.74),
                 dxfattribs={"layer": "VIS"})

    def txt(x, y, s, h, layer="TXT", align="bl"):
        psp.add_text(s, height=h, dxfattribs={"layer": layer}).set_placement(
            (x, y), align=_ALIGN[align])

    txt(x0 + 2, y1 - 5.5, "%s  \u2013  %s" % (f["project"], f["title"]), 4.0)
    txt(x0 + 2, y0 + TB_H * 0.74 + 2.0,
        "DWG NO %s     REV %s     SHEET %s/%s" % (f["no"], REV, f["sheet"], f["sheets"]), 3.2)
    txt(x0 + 2, y0 + TB_H * 0.74 - 2.4,
        "SCALE %s   UNITS mm   PROJECTION FIRST ANGLE (ISO 128)" % f["scale"], 2.5)
    txt(x0 + 2, a + 1.8, "MATERIAL   " + f["material"], 2.6)
    txt(x0 + 2, a - 3.0, "FINISH     " + f["finish"], 2.6)
    txt(x0 + 102, a + 1.8, "TOLERANCE general " + PROCESS["tolerance_general"], 2.6)
    txt(x0 + 102, a - 3.0, "critical fits \u00b1" + PROCESS["tolerance_critical"]
        + " (marked)", 2.6)
    txt(x0 + 2, y1 - 9.5, "DRAWN OpenSmell   CHECK  \u2013", 2.2)
    txt(x0 + 2, y0 + 1.6, "OpenSmell v1.1   |   " + f["notes"], 2.3)
    first_angle_symbol(psp, x1 - 30, y0 + 8, 0.75)


def caption(psp, x, y, text):
    psp.add_text(text, height=3.0, dxfattribs={"layer": "TXT"}).set_placement(
        (x, y), align=_ALIGN["c"])


# ===========================================================================
#  Views from HLR (orientation chosen to read upright)
# ===========================================================================
def view_front(psp, left, bottom, s):
    r = place_view(psp, HLR["shell"]["FRONT"], 270, s, left, bottom)
    w = r[2] - r[0]
    dim_h(psp, r[0], r[2], r[1] - 12, r[1], s)
    dim_v(psp, r[1], r[3], r[0] - 12, r[0], s)
    psp.add_text("3\u00d7\u00d86 nostrils", height=2.4,
                 dxfattribs={"layer": "TXT"}).set_placement((left + w / 2, r[1] - 20),
                                                            align=_ALIGN["c"])
    return r


def view_plan(psp, left, bottom, s):
    r = place_view(psp, HLR["shell"]["PLAN"], 0, s, left, bottom)
    dim_h(psp, r[0], r[2], r[1] - 12, r[1], s)
    dim_v(psp, r[1], r[3], r[2] + 12, r[2], s)
    return r


def view_section_bb(psp, left, bottom, s):
    r = place_view(psp, HLR["shell"]["SECTION_BB"], 90, s, left, bottom)
    dim_h(psp, r[0], r[2], r[1] - 12, r[1], s)
    dim_v(psp, r[1], r[3], r[0] - 12, r[0], s)
    return r


def view_shell_iso(psp, left, bottom, s):
    return place_view(psp, HLR["shell"]["ISO"], 0, s, left, bottom, hidden=False)


def view_baffle_plan(psp, left, bottom, s):
    r = place_view(psp, HLR["baffle"]["PLAN"], 0, s, left, bottom)
    dim_h(psp, r[0], r[2], r[1] - 12, r[1], s)
    dim_v(psp, r[1], r[3], r[2] + 12, r[2], s)
    dx = (CONST["A_X"][1] - CONST["A_X"][0]) * s
    psp.add_text("pitch %d analog / %d digital" % (
        CONST["A_X"][1] - CONST["A_X"][0], CONST["D_X"][1] - CONST["D_X"][0]),
        height=2.6, dxfattribs={"layer": "TXT"}).set_placement(
        (left + (r[2] - r[0]) / 2, r[3] + 6), align=_ALIGN["c"])
    return r


def view_baffle_section(psp, left, bottom, s):
    return place_view(psp, HLR["baffle"]["SECTION_AA"], 270, s, left, bottom)


def view_baffle_iso(psp, left, bottom, s):
    return place_view(psp, HLR["baffle"]["ISO"], 0, s, left, bottom, hidden=False)


def view_assembly_iso(psp, left, bottom, s):
    return place_view(psp, HLR["assembly"]["ISO"], 0, s, left, bottom, hidden=False)


def bom(psp, x0, y0):
    n_wells = len(CONST["A_X"]) + len(CONST["D_X"])
    rows = [
        ("1", "Shell  %d\u00d7%d\u00d7%d, cavity %d\u00d7%d\u00d7%d" % (
            CONST["SH"], CONST["SW"], CONST["SHH"],
            CONST["CX"], CONST["CY"], CONST["CH"]), "1",
         "PETG FDM (or AL 6061-T6)", "make"),
        ("2", "Baffle plate  %d\u00d7%d\u00d7%d, %d open wells" % (
            CONST["CX"], CONST["CY"], CONST["BAFFLE_T"], n_wells), "1",
         "PTFE machined (or PVDF)", "make"),
        ("3", "Axial fan  \u00d840 \u00d7 t10, 5 V", "1",
         "off-the-shelf (substitute any 40mm)", "buy"),
        ("4", "Filter slab PTFE \u2248100 cm\u00b2", "1",
         "off-the-shelf (hydrophobic mesh)", "buy"),
        ("5", "Main PCB  %d\u00d7%d (SHT31, MCU)" % (
            CONST["PCB_X"], CONST["PCB_Y"]), "1",
         "FR4 1.6 mm + build", "make"),
    ]
    colw = [12, 92, 10, 74, 14]
    psp.add_text("BILL OF MATERIALS", height=3.4,
                 dxfattribs={"layer": "TXT"}).set_placement((x0, y0 + 8))
    heads = ["ITEM", "PART / DESCRIPTION", "QTY", "MATERIAL / SOURCE", "TYPE"]
    x = x0
    for h, wd in zip(heads, colw):
        psp.add_text(h, height=2.7, dxfattribs={"layer": "TXT"}).set_placement(
            (x + 1, y0 + 4))
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


def sheet_assembly(doc):
    psp = doc.layouts.new("OS-000")
    psp.page_setup(size=(PW, PH), margins=(0, 0, 0, 0), units="mm")
    frame(psp)
    psp.add_text("ASSEMBLY \u2013 OpenSmell v1.1 sensing platform", height=5,
                 dxfattribs={"layer": "TXT"}).set_placement(
        (PW / 2, PH - 18), align=_ALIGN["c"])
    psp.add_text("isometric general arrangement \u2013 shell, baffle plane, "
                 "3\u00d7 nostril, PCB lid, \u00d840 rear exhaust", height=3,
                 dxfattribs={"layer": "TXT"}).set_placement(
        (PW / 2, PH - 24), align=_ALIGN["c"])
    view_assembly_iso(psp, 80, 62, 0.38)
    caption(psp, 170, 54, "ISO \u2013 general arrangement  (NTS)")
    bom(psp, 22.0, 220.0)
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
    r1 = view_front(psp, 40, 205, 0.5)
    caption(psp, 40 + (r1[2] - r1[0]) / 2, 190, "FRONT (intake face)  1:2")
    r2 = view_plan(psp, 40, 100, 0.5)
    caption(psp, 40 + (r2[2] - r2[0]) / 2, 85, "PLAN (lid removed)  1:2")
    r3 = view_section_bb(psp, 300, 205, 0.5)
    caption(psp, 300 + (r3[2] - r3[0]) / 2, 190,
            "SECTION B-B (x=%d)  1:2" % (CONST["SH"] / 2))
    view_shell_iso(psp, 300, 100, 0.32)
    caption(psp, 330, 90, "ISO \u2013 shell / cavity / baffle plane  (NTS)")
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
    r1 = view_baffle_plan(psp, 40, 190, 0.5)
    caption(psp, 40 + (r1[2] - r1[0]) / 2, 178,
            "PLAN (%d wells)  1:2" % (len(CONST["A_X"]) + len(CONST["D_X"])))
    view_baffle_section(psp, 285, 220, 0.5)
    caption(psp, 330, 210, "SECTION A-A (2 mm plate)  1:2")
    view_baffle_iso(psp, 300, 100, 0.35)
    caption(psp, 330, 90, "ISO \u2013 wells open-bottom  (NTS)")
    title_block(psp, dict(COMMON, title="BAFFLE \u2013 well plate", no="OS-002",
                          sheet="3", sheets="3", scale="1:2",
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
    from ezdxf.math import BoundingBox2d
    import matplotlib.pyplot as plt
    from pypdf import PdfWriter, PdfReader
    import io

    box = BoundingBox2d([(0, 0), (PW, PH)])
    page = Page(PW, PH, Units.mm)
    settings = Settings(fit_page=False)
    writer = PdfWriter()
    for doc, lay in sheets:
        b = PyMuPdfBackend()
        Frontend(RenderContext(doc), b).draw_layout(lay)
        replay = b.get_replay(page, settings=settings, render_box=box)
        writer.append(PdfReader(io.BytesIO(replay.doc.tobytes())))
        fig = plt.figure(figsize=(PW / 25.4, PH / 25.4))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(
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
