"""Numeric verification of the CAD deliverables against the v1.1 source of truth.

Correctness is proven with numbers rather than by eyeballing a render:
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
import xml.etree.ElementTree as ET

import ezdxf
from pypdf import PdfReader

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST  # noqa: E402

HLR = os.path.join(ROOT, "mechanical", "drawings", "model_hlr.json")
SHEETS = os.path.join(ROOT, "mechanical", "drawings", "sheets")
FC = os.path.join(ROOT, "mechanical", "freecad")
SHEET_SVG = os.path.join(SHEETS, "OS-003.svg"), os.path.join(SHEETS, "OS-004.svg")
WIN_X0 = CONST["DISP_X"] - CONST["DISP_WIN_W"] / 2.0
WIN_X1 = CONST["DISP_X"] + CONST["DISP_WIN_W"] / 2.0
WIN_Z0 = CONST["DISP_Z"] - CONST["DISP_WIN_H"] / 2.0
WIN_Z1 = CONST["DISP_Z"] + CONST["DISP_WIN_H"] / 2.0
PAN_X0 = CONST["DISP_X"] - CONST["DISP_W"] / 2.0
PAN_X1 = CONST["DISP_X"] + CONST["DISP_W"] / 2.0
PAN_Z0 = CONST["DISP_Z"] - CONST["DISP_H"] / 2.0
PAN_Z1 = CONST["DISP_Z"] + CONST["DISP_H"] / 2.0
STACK_D = CONST["DISP_POD_D"] + 2.0 * CONST["DISP_GASKET"]
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


def lines(lst):
    return [e for e in lst if e["t"] == "line"]


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
      set(hlr.get("explode", {})) == {"pcb", "filter", "lid", "screws",
                                      "fan", "display"},
      str(hlr.get("explode")))

fc = circles(ents("shell", "FRONT", "visible"))
no = [c for c in fc
      if near(c["r"], CONST["NO_R"], 1e-3)
      and near(-c["c"][0], CONST["NO_Z"], 1e-3)]
usb = [c for c in fc if near(c["r"], CONST["USB_R"], 1e-3)]
check("shell FRONT = 3 nostril bores + 1 USB port",
      len(no) == 3 and len(usb) == 1, f"{len(fc)} circles")
# the FRONT projection puts model X on the second coordinate and -Z on the first
xs = sorted(c["c"][1] for c in no)
check("shell FRONT nostril pitch = NO_PITCH",
      len(xs) == 3 and near(xs[1] - xs[0], CONST["NO_PITCH"], 1e-3)
      and near(xs[2] - xs[1], CONST["NO_PITCH"], 1e-3), str(xs))
_want_no = sorted((CONST["SH"] / 2.0 + dx, CONST["NO_Z"])
                  for dx in (-CONST["NO_PITCH"], 0, CONST["NO_PITCH"]))
_got_no = sorted((round(c["c"][1], 3), round(-c["c"][0], 3)) for c in no)
check("shell FRONT nostrils keep centred X/Z positions",
      _got_no == _want_no, str(_got_no))
check("shell FRONT USB port at (USB_X, USB_Z)",
      len(usb) == 1 and near(usb[0]["c"][1], CONST["USB_X"], 1e-3)
      and near(-usb[0]["c"][0], CONST["USB_Z"], 1e-3),
      str(usb[0]["c"]) if usb else "-")

# The fixed front wall carries the whole UI.  In this projection the first
# coordinate is -Z and the second is X, so the aperture and bores can be located
# against the shell coordinates without guessing from a picture.
front = ents("shell", "FRONT", "visible")
ff = circles(front)
fl = lines(front)
_feed = [c for c in ff
         if near(c["r"], CONST["UI_FEED_D"] / 2.0, 1e-3)
         and near(c["c"][0], -CONST["UI_FEED_Z"], 1e-3)
         and near(c["c"][1], CONST["UI_FEED_X"], 1e-3)]
_btn = [c for c in ff
        if near(c["r"], CONST["BTN_HOLE_D"] / 2.0, 1e-3)
        and any(near(c["c"][0], -bz, 1e-3) and near(c["c"][1], bx, 1e-3)
                for bx, bz in CONST["BTN_FRONT"].values())]
_btn_got = sorted((round(-c["c"][0], 3), round(c["c"][1], 3)) for c in _btn)
_btn_want = sorted((round(z, 3), round(x, 3))
                   for x, z in CONST["BTN_FRONT"].values())


def _ap_h(z):
    return [e for e in fl
            if near(e["a"][0], e["b"][0], 1e-3)
            and near(-e["a"][0], z, 1e-3)
            and near(abs(e["b"][1] - e["a"][1]), CONST["DISP_WIN_W"], 1e-3)]


def _ap_v(x):
    return [e for e in fl
            if near(e["a"][1], e["b"][1], 1e-3)
            and near(e["a"][1], x, 1e-3)
            and near(abs(e["b"][0] - e["a"][0]), CONST["DISP_WIN_H"], 1e-3)]


_apw = _ap_h(WIN_Z0) + _ap_h(WIN_Z1)
_aph = _ap_v(WIN_X0) + _ap_v(WIN_X1)
check("shell FRONT UI grommet DIA UI_FEED_D at (UI_FEED_X, UI_FEED_Z)",
      len(_feed) == 1,
      str([(c["c"], c["r"]) for c in _feed]))
check("shell FRONT 4 button holes at BTN_FRONT with DIA BTN_HOLE_D",
      len(_btn) == 4 and _btn_got == _btn_want, str(_btn_got))
check("shell FRONT aperture edges = DISP_WIN_W x DISP_WIN_H",
      len(_apw) == 2 and len(_aph) == 2,
      f"{len(_apw)} horizontal, {len(_aph)} vertical edges")
check("shell FRONT aperture centred at (DISP_X, DISP_Z)",
      len(_apw) == 2 and len(_aph) == 2
      and all(near(min(e["a"][1], e["b"][1]), WIN_X0, 1e-3)
              and near(max(e["a"][1], e["b"][1]), WIN_X1, 1e-3) for e in _apw)
      and all(near(min(-e["a"][0], -e["b"][0]), WIN_Z0, 1e-3)
              and near(max(-e["a"][0], -e["b"][0]), WIN_Z1, 1e-3)
              for e in _aph),
      f"x {WIN_X0:g}..{WIN_X1:g}, z {WIN_Z0:g}..{WIN_Z1:g}")
check("front UI clears the nostril tops and the lid seam",
      PAN_Z0 - (CONST["NO_Z"] + CONST["NO_R"]) >= 0.5 - 1e-6
      and CONST["LID_Z0"] - PAN_Z1 >= 0.5 - 1e-6,
      f"panel z {PAN_Z0:g}..{PAN_Z1:g}; nostril top "
      f"{CONST['NO_Z'] + CONST['NO_R']:g}; lid {CONST['LID_Z0']:g}")

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


def _cut_bboxes(part, view):
    out = []
    for face in hlr[part][view].get("cuts", []):
        pts = face[0]
        out.append((min(p[1] for p in pts), max(p[1] for p in pts),
                    min(p[2] for p in pts), max(p[2] for p in pts)))
    return out


_slot_want = (CONST["FILT_Y0"], CONST["FILT_Y0"] + CONST["RAIL_D"],
              CONST["FILT_Z0"] - CONST["RAIL_W"], CONST["FILT_Z0"])
_slot_cut = [b for b in _cut_bboxes("shell", "SECTION_A")
             if all(near(a, w, 1e-3) for a, w in zip(b, _slot_want))]
check("filter slot section still at FILT_Y0/Y1 and FILT_Z0",
      len(_slot_cut) == 1, str(_slot_cut))

# The lid plan must be the plate, with four counterbored screw holes on the boss
# centres: that pattern is what the shell's inserts are drilled to.
lp = ents("lid", "PLAN", "visible")
lx0, ly0, lx1, ly1 = extent(lp)
check(f"lid PLAN extent {CONST['SH']:.0f} x {CONST['SW']:.0f}",
      near(lx1 - lx0, CONST["SH"], 1e-3) and near(ly1 - ly0, CONST["SW"], 1e-3),
      f"{lx1-lx0:.1f} x {ly1-ly0:.1f}")
lc = circles(lp)
bore = [c for c in lc if near(c["r"], CONST["CBORE_D"] / 2.0, 1e-3)]
thru = [c for c in lc
        if near(c["r"], CONST["SCREW_D"] / 2.0, 1e-3)
        and any(near(c["c"][0], x, 1e-3) and near(c["c"][1], y, 1e-3)
                for x, y in ((CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
                             (CONST["SH"] - CONST["BOSS_INSET"],
                              CONST["BOSS_INSET"]),
                             (CONST["BOSS_INSET"],
                              CONST["SW"] - CONST["BOSS_INSET"]),
                             (CONST["SH"] - CONST["BOSS_INSET"],
                              CONST["SW"] - CONST["BOSS_INSET"])))]
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

_lp_lines = lines(lp)
check("lid PLAN is plain: only 4 counterbores + 4 through holes",
      len(bore) == 4 and len(thru) == 4 and len(lc) == 8
      and len(_lp_lines) == 4,
      f"{len(bore)} counterbores, {len(thru)} through, {len(lc)} circles, "
      f"{len(_lp_lines)} outline edges")
_lid_cut_centres = {(6.5, 6.5), (CONST["SH"] - 6.5, 6.5),
                    (6.5, CONST["SW"] - 6.5),
                    (CONST["SH"] - 6.5, CONST["SW"] - 6.5)}
check("lid PLAN has no window, grommet or button cuts",
      not any(near(abs(e["b"][0] - e["a"][0]), CONST["DISP_WIN_W"], 1e-3)
              for e in _lp_lines)
      and all(any(near(c["c"][0], bx, 1e-3)
                  and near(c["c"][1], by, 1e-3)
                  for bx, by in _lid_cut_centres) for c in lc),
      str([(c["c"], c["r"]) for c in lc]))

# The assembly section is the one view that proves the stack: shell depth + the
# fan hanging off the back, and the full height including the lid.
ab = ents("assembly", "SECTION_B", "visible")
ax0, ay0, ax1, ay1 = extent(ab)
check("assembly SECTION B-B extent = shell + fan + front panel x full height",
      sorted([round(ax1 - ax0, 3), round(ay1 - ay0, 3)])
      == sorted([CONST["SW"] + CONST["FAN_PLATE_T"] + CONST["FAN_T"]
                 + STACK_D, CONST["SHH"]]),
      f"{ax1-ax0:.1f} x {ay1-ay0:.1f}")

# The front-panel stack projects in X/Y (PLAN) and Z/Y (SECTION_D).  Its depth
# is the same number of layers in both views: gasket, acrylic, bezel, OLED.
dp = ents("display", "PLAN", "visible")
dpx0, dpy0, dpx1, dpy1 = extent(dp)
check("display PLAN extent = DISP_W x front stack depth",
      near(dpx1 - dpx0, CONST["DISP_W"], 1e-3)
      and near(dpy1 - dpy0, STACK_D, 1e-3),
      f"{dpx1-dpx0:.1f} x {dpy1-dpy0:.1f}")
ds = ents("display", "SECTION_D", "visible")
dsy0, dsx0, dsy1, dsx1 = extent(ds)
check("display SECTION D extent = DISP_H x front stack depth",
      near(dsy1 - dsy0, CONST["DISP_H"], 1e-3)
      and near(dsx1 - dsx0, STACK_D, 1e-3),
      f"z {dsy1-dsy0:.1f}, stack {dsx1-dsx0:.1f}")
check("display section sits outside the front wall and below the lid seam",
      near(dsy0, PAN_Z0, 1e-3) and near(dsy1, PAN_Z1, 1e-3)
      and near(dsx0, 0.0, 1e-3) and near(dsx1, STACK_D, 1e-3)
      and CONST["LID_Z0"] - PAN_Z1 >= 0.5 - 1e-6,
      f"z {dsy0:.1f}..{dsy1:.1f}, depth {dsx0:.1f}..{dsx1:.1f}; "
      f"lid {CONST['LID_Z0']:.1f}")
_layer_y = {round(-p[1], 3) for face in
            hlr["display"]["SECTION_D"].get("cuts", []) for p in face[0]}
_layer_z = {round(p[2], 3) for face in
            hlr["display"]["SECTION_D"].get("cuts", []) for p in face[0]}
check("display section has gasket/acrylic/bezel layers at CONST depths",
      {0.0, round(CONST["DISP_GASKET"], 3),
       round(2 * CONST["DISP_GASKET"], 3), round(STACK_D, 3)} <= _layer_y,
      str(sorted(_layer_y)))
check("display section aperture edges are DISP_WIN_W x DISP_WIN_H",
      {round(WIN_Z0, 3), round(WIN_Z1, 3)} <= _layer_z,
      str(sorted(_layer_z)))

# ------------------------------- 3D model -----------------------------------
for f in ("smell_monitor.FCStd", "smell_monitor.STEP"):
    p = os.path.join(FC, f)
    check(f"{f} exists and non-empty",
          os.path.exists(p) and os.path.getsize(p) > 1000,
          f"{os.path.getsize(p)/1024:.0f} KB" if os.path.exists(p) else "missing")

for f in ("smell_monitor_display_gasket.STEP",
          "smell_monitor_display_window.STEP",
          "smell_monitor_display_bezel.STEP",
          "smell_monitor_display_oled.STEP",
          "smell_monitor_button_caps.STEP"):
    p = os.path.join(FC, f)
    check(f"{f} exists and non-empty",
          os.path.exists(p) and os.path.getsize(p) > 1000,
          f"{os.path.getsize(p)/1024:.0f} KB" if os.path.exists(p) else "missing")

# ------------------------- print meshes (STL only, <= 10 MB) ---------
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


for s in ("smell_monitor_shell.stl", "smell_monitor_lid.stl",
          "smell_monitor_display_gasket.stl",
          "smell_monitor_display_window.stl",
          "smell_monitor_display_bezel.stl",
          "smell_monitor_display_oled.stl",
          "smell_monitor_button_caps.stl"):
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
_probe += [(CONST["AN_X"], y) for y in CONST["AN_Y"]]
_probe += [(CONST["DI_X"], y) for y in CONST["DI_Y"]]
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
    "OS-000": {CONST["SW"] + CONST["FAN_PLATE_T"] + CONST["FAN_T"] + STACK_D,
               CONST["CY"], round(CONST["PCB_TOP"], 1), CONST["SHH"],
               CONST["DISP_H"], CONST["DISP_WIN_H"], CONST["UI_FEED_D"],
               STACK_D, CONST["DISP_GASKET"]},
    "OS-001": {CONST["SH"], CONST["CAV_Z1"], CONST["NO_Z"],
               round(CONST["CAV_Z1"] - CONST["NO_Z"], 1),
               CONST["NO_PITCH"], CONST["SW"] + CONST["FAN_PLATE_T"],
               CONST["CY"], CONST["CAV_Z1"] - CONST["FLOOR_T"],
               CONST["DISP_WIN_W"], CONST["DISP_WIN_H"], CONST["DISP_X"],
               CONST["DISP_Z"], CONST["UI_FEED_D"], CONST["UI_FEED_X"],
               CONST["BTN_HOLE_D"]},
    "OS-002": {CONST["SH"], CONST["SW"], CONST["BOSS_INSET"],
               CONST["SW"] - 2 * CONST["BOSS_INSET"], CONST["LID_T"],
               CONST["CBORE_T"], CONST["SCREW_D"], CONST["CBORE_D"]},
}
# A drawing that stops stating its geometry has stopped being a drawing, so each
# part sheet must carry at least this many dimensions.
SHEET_MIN_DIMS = {"OS-000": 8, "OS-001": 12, "OS-002": 8}
SHEET_TOKENS = {
    "OS-000": ("ASSEMBLY", "EXPLODED", "BILL OF MATERIALS", "SECTION B-B",
               "PETG", "FRONT PANEL", "ACRYLIC", "PLAIN LID"),
    "OS-001": ("SHELL", "FRONT", "SECTION A-A", "FILTER SEAT", "MATERIAL",
               "DISPLAY APERTURE", "UI HARNESS", "BUTTONS"),
    "OS-002": ("LID", "PLAN", "SECTION C-C", "CBORE", "MATERIAL",
               "NO WINDOW", "FRONT WALL", "ACRYLIC"),
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

# ------------------------- SVG sheets OS-003 / OS-004 -----------------------
def _svg_text(path):
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return ""
    return " ".join(t.strip() for t in root.itertext() if t.strip())


_svg3, _svg4 = (_svg_text(p) for p in SHEET_SVG)
check("OS-003 SVG has front-panel button and harness coordinates",
      bool(_svg3) and all(k in _svg3 for k in CONST["BTN_FRONT"])
      and "Ø %g × 4" % CONST["BTN_HOLE_D"] in _svg3
      and "Ø %g @ (%g,%g)" % (
          CONST["UI_FEED_D"], CONST["UI_FEED_X"], CONST["UI_FEED_Z"]) in _svg3,
      "front feed (%g,%g)" % (CONST["UI_FEED_X"], CONST["UI_FEED_Z"]))
check("OS-004 SVG states front-wall UI with acrylic wetted face",
      bool(_svg4)
      and "Front-panel UI outside the gas path" in _svg4
      and "acrylic is the only wetted face" in _svg4
      and "plain lid, no wires cross its seam" in _svg4
      and "UI grommet Ø%g @ (%g,%g) in the fixed front wall" % (
          CONST["UI_FEED_D"], CONST["UI_FEED_X"], CONST["UI_FEED_Z"]) in _svg4
      and "NO SILICONE" in _svg4)

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
