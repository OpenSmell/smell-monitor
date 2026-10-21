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


check("HLR has shell/lid/assembly views",
      {"shell", "lid", "assembly"} <= set(hlr),
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
      set(hlr.get("explode", {})) == {"pcb", "filter", "lid", "screws", "fan"},
      str(hlr.get("explode")))

fc = circles(ents("shell", "FRONT", "visible"))
no = [c for c in fc if near(c["r"], CONST["NO_R"], 1e-3)]
usb = [c for c in fc if near(c["r"], CONST["USB_R"], 1e-3)]
check("shell FRONT = 3 nostril bores + 1 USB port",
      len(no) == 3 and len(usb) == 1, f"{len(fc)} circles")
# the FRONT projection puts model X on the second coordinate and -Z on the first
xs = sorted(c["c"][1] for c in no)
check("shell FRONT nostril pitch = NO_PITCH",
      len(xs) == 3 and near(xs[1] - xs[0], CONST["NO_PITCH"], 1e-3)
      and near(xs[2] - xs[1], CONST["NO_PITCH"], 1e-3), str(xs))
check("shell FRONT USB port at (USB_X, USB_Z)",
      len(usb) == 1 and near(usb[0]["c"][1], CONST["USB_X"], 1e-3)
      and near(-usb[0]["c"][0], CONST["USB_Z"], 1e-3),
      str(usb[0]["c"]) if usb else "-")

# The section has to show the real part, not a bounding box: a cut through x=61
# must measure the shell depth (fan plate included) and the height.  The fan
# plate is a 44 mm square centred on the fan axis, so it stands 2 mm above the
# tray rim; the tray itself stops at CAV_Z1, where the lid lands.
_shell_top = max(CONST["CAV_Z1"], CONST["FAN_Z"] + CONST["FAN_PLATE"] / 2.0)
sl = ents("shell", "SECTION_A", "visible")
sx0, sy0, sx1, sy1 = extent(sl)
check(f"shell SECTION A-A extent {CONST['SW'] + CONST['FAN_PLATE_T']:.0f} x "
      f"{_shell_top:.0f}",
      sorted([round(sx1 - sx0, 3), round(sy1 - sy0, 3)])
      == sorted([CONST["SW"] + CONST["FAN_PLATE_T"], _shell_top]),
      f"{sx1-sx0:.1f} x {sy1-sy0:.1f}")

# The lid plan must be the plate, with four counterbored screw holes on the boss
# centres: that pattern is what the shell's inserts are drilled to.
lp = ents("lid", "PLAN", "visible")
lx0, ly0, lx1, ly1 = extent(lp)
check(f"lid PLAN extent {CONST['SH']:.0f} x {CONST['SW']:.0f}",
      near(lx1 - lx0, CONST["SH"], 1e-3) and near(ly1 - ly0, CONST["SW"], 1e-3),
      f"{lx1-lx0:.1f} x {ly1-ly0:.1f}")
lc = circles(lp)
bore = [c for c in lc if near(c["r"], CONST["CBORE_D"] / 2.0, 1e-3)]
thru = [c for c in lc if near(c["r"], CONST["SCREW_D"] / 2.0, 1e-3)]
want = sorted((round(x, 1), round(y, 1)) for x, y in
              ((CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
               (CONST["SH"] - CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
               (CONST["BOSS_INSET"], CONST["SW"] - CONST["BOSS_INSET"]),
               (CONST["SH"] - CONST["BOSS_INSET"],
                CONST["SW"] - CONST["BOSS_INSET"])))
check("lid PLAN = 4 counterbores + 4 through holes at the boss centres",
      len(bore) == 4 and len(thru) == 4
      and sorted((round(c["c"][0], 1), round(c["c"][1], 1)) for c in thru) == want,
      str([(c["c"], c["r"]) for c in lc]))

# The assembly section is the one view that proves the stack: shell depth + the
# fan hanging off the back, and the full height including the lid.
ab = ents("assembly", "SECTION_B", "visible")
ax0, ay0, ax1, ay1 = extent(ab)
check("assembly SECTION B-B extent = shell + fan plate + fan x full height",
      sorted([round(ax1 - ax0, 3), round(ay1 - ay0, 3)])
      == sorted([CONST["SW"] + CONST["FAN_PLATE_T"] + CONST["FAN_T"],
                 CONST["SHH"]]),
      f"{ax1-ax0:.1f} x {ay1-ay0:.1f}")

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


for s in ("smell_monitor_shell.stl", "smell_monitor_lid.stl"):
    p = os.path.join(FC, s)
    sz = os.path.getsize(p) if os.path.exists(p) else 0
    check(f"STL {s} present, <=10 MB",
          os.path.exists(p) and 0 < sz <= 10 * 1024 * 1024, f"{sz/1024:.0f} KB")
    tri, bad = _stl_manifold(p) if os.path.exists(p) else (None, None)
    check(f"STL {s} watertight (closed 2-manifold)",
          tri is not None and bad == 0, f"{tri} tris, {bad} bad edges")

# The plan is the view that locates the bosses and the standoffs; without it a
# maker has to infer them from the lid sheet.
pl = ents("shell", "PLAN", "visible")
px0, py0, px1, py1 = extent(pl)
check(f"shell PLAN extent {CONST['SH']:.0f} x "
      f"{CONST['SW'] + CONST['FAN_PLATE_T']:.0f} (fan plate included)",
      near(px1 - px0, CONST["SH"], 1e-3)
      and near(py1 - py0, CONST["SW"] + CONST["FAN_PLATE_T"], 1e-3),
      f"{px1-px0:.1f} x {py1-py0:.1f}")
pc = circles(pl)
_have = [(c["c"][0], c["c"][1], c["r"]) for c in pc]


def _at(cx, cy, r):
    return any(near(x, cx, 0.05) and near(y, cy, 0.05) and near(rr, r, 1e-3)
               for x, y, rr in _have)


check("shell PLAN locates the 4 lid bosses and the 4 board standoffs",
      all(_at(x, y, CONST["BOSS_D"] / 2.0) for x, y in
          ((CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
           (CONST["SH"] - CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
           (CONST["BOSS_INSET"], CONST["SW"] - CONST["BOSS_INSET"]),
           (CONST["SH"] - CONST["BOSS_INSET"],
            CONST["SW"] - CONST["BOSS_INSET"])))
      and all(_at(x, y, CONST["STANDOFF_D"] / 2.0) for x, y in
              ((16.0, 16.0), (CONST["SH"] - 16.0, 16.0),
               (16.0, CONST["SW"] - 16.0),
               (CONST["SH"] - 16.0, CONST["SW"] - 16.0))),
      f"{len(pc)} circles/arcs in the view")

# ------------------- the shell must be a tray, not a sealed box -------------
# The defect this guards against: an earlier shell had 30 mm of material over
# the chamber.  It could not be printed (sealed cavity), assembled (the modules
# had no way in) or serviced - and every drawing of it was an empty box.  An
# open tray means a vertical ray from the cavity finds no material above it.
def _stl_tris(path):
    b = open(path, "rb").read()
    n = _struct.unpack("<I", b[80:84])[0]
    return [_struct.unpack("<12f", b[84 + i * 50:84 + i * 50 + 48])[3:]
            for i in range(n)]


def _ray_up(tris, x, y, z):
    """z of the first crossing of the solid boundary above (x, y, z), or None."""
    best = None
    for v in tris:
        a, b, c = v[0:3], v[3:6], v[6:9]
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
        w = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
        if u < -1e-9 or w < -1e-9 or u + w > 1 + 1e-9:
            continue
        zz = a[2] + u * (b[2] - a[2]) + w * (c[2] - a[2])
        if zz > z + 1e-6 and (best is None or zz < best):
            best = zz
    return best


_shell = _stl_tris(os.path.join(FC, "smell_monitor_shell.stl"))
_lid = _stl_tris(os.path.join(FC, "smell_monitor_lid.stl"))
_cav_top = 0.0
for v in _shell:
    for k in (0, 3, 6):
        if (CONST["CX0"] < v[k] < CONST["CX1"]
                and CONST["CY0"] < v[k + 1] < CONST["CY1"]):
            _cav_top = max(_cav_top, v[k + 2])
check("shell is an open tray: nothing above the cavity ceiling",
      near(_cav_top, CONST["CAV_Z1"], 1e-3),
      "cavity top z=%.2f, ceiling z=%.2f" % (_cav_top, CONST["CAV_Z1"]))
_lz = [v[k] for v in _lid for k in (2, 5, 8)]
check("lid is a separate part spanning CAV_Z1..LID_Z1",
      near(min(_lz), CONST["LID_Z0"], 1e-3) and near(max(_lz), CONST["LID_Z1"], 1e-3),
      "z %.2f..%.2f" % (min(_lz), max(_lz)))

_probe = [(CONST["CX0"] + CONST["CX"] / 2.0, CONST["CY0"] + CONST["CY"] / 2.0)]
_probe += [(x, CONST["A_Y0"]) for x in CONST["A_X"]]
_probe += [(x, CONST["D_Y0"]) for x in CONST["D_X"]]
_above = CONST["PCB_TOP"] + 0.5
_blocked = []
for x, y in _probe:
    z = _ray_up(_shell, x, y, _above)
    if z is not None:
        _blocked.append((round(x, 1), round(y, 1), round(z, 1)))
check("every socket has open air above it (only the lid covers it)",
      not _blocked, str(_blocked))

_cx = CONST["CX0"] + CONST["CX"] / 2.0
_cy = CONST["CY0"] + CONST["CY"] / 2.0
_floor = _ray_up(_shell, _cx, _cy, 0.5)
check("tray floor under the board is FLOOR_T thick",
      _floor is not None and near(_floor, CONST["FLOOR_T"], 0.05),
      "z=%s" % _floor)
_stand = _ray_up(_shell, 18.0, 16.0, CONST["FLOOR_T"] + 0.5)
check("board has a standoff to sit on at PCB_Z",
      _stand is not None and near(_stand, CONST["PCB_Z"], 0.05), "z=%s" % _stand)

# ------------------------- CAD drawing sheets (DXF source) ------------------
SHEET_DIMS = {
    "OS-000": {CONST["SW"] + CONST["FAN_PLATE_T"] + CONST["FAN_T"],
               CONST["CY"], round(CONST["PCB_TOP"], 1), CONST["SHH"]},
    "OS-001": {CONST["SH"], CONST["CAV_Z1"], CONST["NO_Z"],
               round(CONST["CAV_Z1"] - CONST["NO_Z"], 1),
               CONST["NO_PITCH"], CONST["SW"] + CONST["FAN_PLATE_T"],
               CONST["CY"], CONST["CAV_Z1"] - CONST["FLOOR_T"]},
    "OS-002": {CONST["SH"], CONST["SW"], CONST["BOSS_INSET"],
               CONST["SW"] - 2 * CONST["BOSS_INSET"], CONST["LID_T"],
               CONST["CBORE_T"]},
}
# A drawing that stops stating its geometry has stopped being a drawing, so each
# part sheet must carry at least this many dimensions.
SHEET_MIN_DIMS = {"OS-000": 5, "OS-001": 12, "OS-002": 8}
SHEET_TOKENS = {
    "OS-000": ("ASSEMBLY", "EXPLODED", "BILL OF MATERIALS", "SECTION B-B",
               "PETG"),
    "OS-001": ("SHELL", "FRONT", "SECTION A-A", "FILTER SEAT", "MATERIAL"),
    "OS-002": ("LID", "PLAN", "SECTION C-C", "COUNTERBORE", "MATERIAL"),
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
    dims = sorted({round(d.get_measurement() * d.override().get("dimlfac", 1.0), 1)
                   for d in lay.query("DIMENSION")})
    check(f"sheet {name} dims measure true mm",
          want <= set(dims), f"got {dims}")
    check(f"sheet {name} is dimensioned (>= {SHEET_MIN_DIMS[name]} dims)",
          len(lay.query("DIMENSION")) >= SHEET_MIN_DIMS[name],
          f"{len(lay.query('DIMENSION'))} dims")
    # A section without hatching is a wireframe: the reader cannot tell which
    # material the cutting plane passed through.  OS-001/002 each carry a cut
    # view, so each must carry real HATCH entities (filled from the measured
    # cut faces, not drawn by hand).
    if name in ("OS-001", "OS-002"):
        check(f"sheet {name} sections are hatched", len(lay.query("HATCH")) >= 1,
              f"{len(lay.query('HATCH'))} hatches")
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
