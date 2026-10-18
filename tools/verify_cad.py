"""Numeric verification of the CAD deliverables against the v1.1 source of truth.

The agent cannot see rendered drawings, so correctness is proven with numbers:
the HLR projection data is measured and compared to CONST, the A3 sheet DXFs are
audited and their dimensions checked to measure true model millimetres, the PDF
is confirmed vector/A3/3-page, and the 3D model + print meshes are checked.

Pipeline under test:
  FreeCAD build  ->  mechanical/drawings/model_hlr.json
                     mechanical/freecad/smell_monitor.{FCStd,STEP,stl}
  sheet compose  ->  mechanical/drawings/sheets/OS-00{0,1,2}.dxf + PDF

Run:  python tools/verify_cad.py     (exit 0 = all PASS)
No drawing change may be accepted while any check here FAILs.
"""
import json
import os
import sys

import ezdxf
from pypdf import PdfReader

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST  # noqa: E402

HLR = os.path.join(ROOT, "mechanical", "drawings", "model_hlr.json")
SHEETS = os.path.join(ROOT, "mechanical", "drawings", "sheets")
FC = os.path.join(ROOT, "mechanical", "freecad")
FAILS = []
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    if not ok:
        FAILS.append(name)


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol


# ------------------------------- HLR geometry -------------------------------
hlr = json.load(open(HLR, encoding="utf-8"))


def ents(part, view, grp):
    return hlr[part][view][grp]


def circles(lst):
    return [e for e in lst if e["t"] in ("circle", "arc")]


def extent(lst):
    xs, ys = [], []
    for e in lst:
        if e["t"] == "line":
            pts = (e["a"], e["b"])
        elif e["t"] in ("circle", "arc"):
            pts = ((e["c"][0] - e["r"], e["c"][1] - e["r"]),
                   (e["c"][0] + e["r"], e["c"][1] + e["r"]))
        else:
            pts = e["pts"]
        for p in pts:
            xs.append(p[0])
            ys.append(p[1])
    return (min(xs), min(ys), max(xs), max(ys))


check("HLR has shell/baffle/assembly views",
      {"shell", "baffle", "assembly"} <= set(hlr),
      ",".join(sorted(hlr)))
check("HLR has an exploded assembly view",
      "EXPLODED" in hlr.get("assembly", {}),
      ",".join(sorted(hlr.get("assembly", {}))))

# Every view must carry the *measured* projection axes: the sheet generator maps
# dimensions onto features through them, so a view without them cannot be
# dimensioned honestly.  An orthographic projection never stretches an axis
# (|axis| <= 1) and the axes seen true length are exactly 1.
for _part, _views in hlr.items():
    if _part == "explode":
        continue
    for _view, _rec in _views.items():
        _ax = _rec.get("axes") or {}
        _ok = (set(_ax) == {"X", "Y", "Z"}
               and all(len(_v) == 2 for _v in _ax.values()))
        _norms = [_v[0] ** 2 + _v[1] ** 2 for _v in _ax.values()] if _ok else []
        if _ok:
            _nz = [round(_n, 6) for _n in _norms if _n > 1e-9]
            _ok = (all(_n <= 1.0 + 1e-6 for _n in _norms) and bool(_nz)
                   and len(set(_nz)) == 1)
        check(f"HLR {_part}/{_view} carries measured projection axes", _ok,
              str(_ax))
check("exploded view offsets are recorded with the geometry",
      set(hlr.get("explode", {})) == {"baffle", "filter", "pcb", "fan"},
      str(hlr.get("explode")))

fc = circles(ents("shell", "FRONT", "visible"))
check("shell FRONT = 3 nostril circles",
      len(fc) == 3, f"{len(fc)}")
check("shell FRONT nostrils r = NO_R, pitch 26",
      len(fc) == 3 and all(near(c["r"], CONST["NO_R"], 1e-3) for c in fc)
      and near(sorted(c["c"][1] for c in fc)[1] - sorted(c["c"][1] for c in fc)[0],
               CONST["SH"] / 2 - (CONST["SH"] / 2 - 26), 1e-3), "")

# baffle plan: outer 4 + (N slots + 1 reference port) x 4 = 4N + 4 straight edges
N_SLOTS = len(CONST["A_X"]) + len(CONST["D_X"])
N_PORTS = 1                       # SHT31 reference-sensor port
bl = [e for e in ents("baffle", "PLAN", "visible") if e["t"] == "line"]
bx0, by0, bx1, by1 = extent(bl)
check("baffle PLAN extent = cavity",
      near(bx1 - bx0, CONST["CX"], 1e-3) and near(by1 - by0, CONST["CY"], 1e-3),
      f"{bx1-bx0:.1f} x {by1-by0:.1f} vs {CONST['CX']} x {CONST['CY']}")
check(f"baffle PLAN = {4*(N_SLOTS+N_PORTS)+4} edges "
      f"(outer 4 + ({N_SLOTS} wells + {N_PORTS} port) x 4)",
      len(bl) == 4 * (N_SLOTS + N_PORTS) + 4, f"{len(bl)}")
# the reference port must be in the lane, upstream of the hot analog row and
# clear of both well rows (a module must not sit over it)
check("SHT31 port clears both module rows and stays in-cavity",
      CONST["SHT_Y0"] >= CONST["D_Y0"] + CONST["D_SY"]
      and CONST["SHT_Y0"] + CONST["SHT_SY"] <= CONST["A_Y0"]
      and CONST["SHT_X"] - CONST["SHT_SX"] / 2 >= CONST["WSIDE"]
      and CONST["SHT_X"] + CONST["SHT_SX"] / 2 <= CONST["WSIDE"] + CONST["CX"],
      f"y {CONST['SHT_Y0']}..{CONST['SHT_Y0']+CONST['SHT_SY']} "
      f"x {CONST['SHT_X']-CONST['SHT_SX']/2}..{CONST['SHT_X']+CONST['SHT_SX']/2}")

sl = ents("shell", "PLAN", "visible")
sx0, _, sx1, _ = extent(sl)
check(f"shell PLAN width {CONST['SH']:.0f}",
      near(sx1 - sx0, CONST["SH"], 1e-3), f"{sx1-sx0:.1f}")

# ------------------------------- 3D model -----------------------------------
for f in ("smell_monitor.FCStd", "smell_monitor.STEP"):
    p = os.path.join(FC, f)
    check(f"{f} exists and non-empty",
          os.path.exists(p) and os.path.getsize(p) > 1000,
          f"{os.path.getsize(p)/1024:.0f} KB" if os.path.exists(p) else "missing")

# ------------------------- print meshes (Seeed: STL only, <=10 MB) ---------
import struct as _struct  # noqa: E402
from collections import Counter as _Counter  # noqa: E402


def _stl_manifold(path):
    b = open(path, "rb").read()
    n = _struct.unpack("<I", b[80:84])[0]
    if 84 + n * 50 != len(b):
        return None, None
    ec = _Counter()
    vmap = {}

    def k(v):
        return vmap.setdefault(tuple(round(c, 4) for c in v), len(vmap))

    for i in range(n):
        o = 84 + i * 50
        v = _struct.unpack("<12f", b[o:o + 48])
        t = [k(v[3:6]), k(v[6:9]), k(v[9:12])]
        for a, bb in ((0, 1), (1, 2), (2, 0)):
            ec[tuple(sorted((t[a], t[bb])))] += 1
    return n, sum(1 for c in ec.values() if c != 2)


for s in ("smell_monitor_shell.stl", "smell_monitor_baffle.stl"):
    p = os.path.join(FC, s)
    sz = os.path.getsize(p) if os.path.exists(p) else 0
    check(f"STL {s} present, <=10 MB",
          os.path.exists(p) and 0 < sz <= 10 * 1024 * 1024, f"{sz/1024:.0f} KB")
    tri, bad = _stl_manifold(p) if os.path.exists(p) else (None, None)
    check(f"STL {s} watertight (closed 2-manifold)",
          tri is not None and bad == 0, f"{tri} tris, {bad} bad edges")

# ------------------------- CAD drawing sheets (DXF source) ------------------
SHEET_DIMS = {
    "OS-000": set(),                       # assembly: BOM + NTS views
    "OS-001": {CONST["SH"], CONST["SW"], CONST["SHH"], CONST["CX"], CONST["CY"],
               CONST["FLOOR"], 11.0, 26.0, 37.0, 43.0},
    "OS-002": {CONST["CX"], CONST["CY"], CONST["A_SX"], CONST["A_SY"],
               CONST["D_SX"], CONST["D_SY"], 26.0, 21.0, 12.0,
               float(CONST["BAFFLE_T"])},
}
# A drawing that stops stating its geometry has stopped being a drawing, so each
# part sheet must carry at least this many dimensions.
SHEET_MIN_DIMS = {"OS-000": 0, "OS-001": 15, "OS-002": 12}
SHEET_TOKENS = {
    "OS-000": ("ASSEMBLY", "EXPLODED", "BILL OF MATERIALS", "PETG", "PTFE",
               "OpenSmell"),
    "OS-001": ("SHELL", "FRONT", "PLAN", "SECTION B-B", "MATERIAL"),
    "OS-002": ("BAFFLE", "PLAN", "SECTION A-A", "MATERIAL"),
}
for name, want in SHEET_DIMS.items():
    dxf = os.path.join(SHEETS, name + ".dxf")
    ok_file = os.path.exists(dxf) and os.path.getsize(dxf) > 1000
    check(f"sheet {name}.dxf exists", ok_file)
    if not ok_file:
        continue
    doc = ezdxf.readfile(dxf)
    lay = doc.layouts.get(name)
    check(f"sheet {name}.dxf audit clean", len(doc.audit().errors) == 0,
          f"{len(doc.audit().errors)} errors")
    dims = sorted({round(d.get_measurement() * d.override().get("dimlfac", 1.0))
                   for d in lay.query("DIMENSION")})
    check(f"sheet {name} dims measure true mm",
          want <= set(dims), f"got {dims}")
    check(f"sheet {name} is dimensioned (>= {SHEET_MIN_DIMS[name]} dims)",
          len(lay.query("DIMENSION")) >= SHEET_MIN_DIMS[name],
          f"{len(lay.query('DIMENSION'))} dims")
    txt = " ".join((t.dxf.text or "") for t in lay.query("TEXT"))
    for tok in SHEET_TOKENS[name]:
        check(f"sheet {name} text contains '{tok}'", tok in txt)
    # everything inside the drawn frame
    inside = True
    for e in lay:
        t = e.dxftype()
        pts = []
        if t == "LINE":
            pts = [e.dxf.start, e.dxf.end]
        elif t in ("CIRCLE", "ARC"):
            c, r = e.dxf.center, e.dxf.radius
            pts = [(c.x - r, c.y - r), (c.x + r, c.y + r)]
        elif t == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points()]
        elif t == "TEXT":
            pts = [e.dxf.insert]
        for p in pts:
            x = p[0] if not hasattr(p, "x") else p.x
            y = p[1] if not hasattr(p, "y") else p.y
            if not (6 <= x <= 414 and 6 <= y <= 291):
                inside = False
    check(f"sheet {name} geometry inside A3 frame", inside)
    # text must not run past the border either: the insert point is not enough,
    # because a long note anchored on the left overflows to the right.  Width is
    # estimated from the character count (the plot font is ~0.7 x height wide),
    # which is the same rule the note wording is written to.
    wide = []
    for e in lay.query("TEXT"):
        t = e.dxf.text or ""
        if not t:
            continue
        w = 0.75 * e.dxf.height * len(t)
        ha = e.dxf.get("halign", 0)
        x = e.dxf.insert.x
        x0 = x if ha == 0 else (x - w / 2.0 if ha == 1 else x - w)
        if len(t) == 1 and (x0 + w <= 12.5 or x0 >= 407.5):
            continue                     # ISO 5457 zone label, lives in the strip
        if x0 < 6 or x0 + w > 408:
            wide.append("%.0f..%.0f %s" % (x0, x0 + w, t[:28]))
    check(f"sheet {name} text fits inside the border", not wide,
          "; ".join(wide[:3]))

# ------------------------------- sheets PDF ---------------------------------
PDF = os.path.join(SHEETS, "OpenSmell_v1.1_sheets.pdf")
try:
    r = PdfReader(PDF)
    npages = len(r.pages)
    imgs = sum(len(p.images) for p in r.pages)
    mm = [(round(float(p.mediabox.width) / 72 * 25.4),
           round(float(p.mediabox.height) / 72 * 25.4)) for p in r.pages]
except Exception:
    npages, imgs, mm = 0, 99, []
check("drawings PDF = 3 sheets", npages == 3, str(npages))
check("drawings PDF is VECTOR (no raster images)", imgs == 0, f"{imgs} images")
check("drawings PDF pages are A3 landscape (420x297 mm)",
      bool(mm) and all(abs(w - 420) <= 2 and abs(h - 297) <= 2 for w, h in mm),
      str(mm))

# ------------------------------- report ------------------------------------
w = max(len(n) for n, _, _ in CHECKS) + 2
print(f"{'CHECK':<{w}} {'RESULT':<7} DETAIL")
for name, ok, detail in CHECKS:
    print(f"{name:<{w}} {'PASS' if ok else 'FAIL':<7} {detail}")
print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    sys.exit(1)
print("ALL PASS - deliverables consistent with mechanical/constants.py")
