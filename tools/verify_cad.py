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

fc = circles(ents("shell", "FRONT", "visible"))
check("shell FRONT = 3 nostril circles",
      len(fc) == 3, f"{len(fc)}")
check("shell FRONT nostrils r = NO_R, pitch 26",
      len(fc) == 3 and all(near(c["r"], CONST["NO_R"], 1e-3) for c in fc)
      and near(sorted(c["c"][1] for c in fc)[1] - sorted(c["c"][1] for c in fc)[0],
               CONST["SH"] / 2 - (CONST["SH"] / 2 - 26), 1e-3), "")

# baffle plan: outer 4 + N slots x 4 wells = 4N + 4 straight edges
N_SLOTS = len(CONST["A_X"]) + len(CONST["D_X"])
bl = [e for e in ents("baffle", "PLAN", "visible") if e["t"] == "line"]
bx0, by0, bx1, by1 = extent(bl)
check("baffle PLAN extent = cavity",
      near(bx1 - bx0, CONST["CX"], 1e-3) and near(by1 - by0, CONST["CY"], 1e-3),
      f"{bx1-bx0:.1f} x {by1-by0:.1f} vs {CONST['CX']} x {CONST['CY']}")
check(f"baffle PLAN = {4*N_SLOTS+4} edges (outer 4 + {N_SLOTS} wells x 4)",
      len(bl) == 4 * N_SLOTS + 4, f"{len(bl)}")

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
    "OS-000": set(),                       # assembly: BOM only
    "OS-001": {CONST["SH"], CONST["SHH"], CONST["SW"]},
    "OS-002": {CONST["CX"], CONST["CY"]},
}
SHEET_TOKENS = {
    "OS-000": ("ASSEMBLY", "BILL OF MATERIALS", "PETG", "PTFE", "OpenSmell"),
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
