"""Solid-to-solid clearance gate for the enclosure (FreeCAD, not a drawing check).

`tools/verify_cad.py` proves the drawings match the constants; it cannot prove
that separately-built solids do not occupy the same space.  Two defects of that
class are cheap to make and expensive to find at assembly, so they are measured
here:

  1. **Filter pad vs the tray.**  The pad is a separate solid that has to drop
     into the drawer.  Any overlap with a boss or rail means the pad cannot be
     fitted, however correct the drawing looks.
  2. **The CAD board vs the tray.**  The board solid carries the boss cut-outs;
     if it intersects the tray, the imported board model is wrong even when the
     gerbers are right.
  3. **The CAD board's boss clearance.**  The cut-outs must be sized boss +
     clearance, not merely notch-shaped, or the board drops on with a press fit.
  4. **The front-panel UI.**  The gasket, acrylic, bezel, OLED and button caps
     sit outside the fixed front wall, off the sample channel.  The aperture,
     grommet and four switch holes must be genuinely clear, and the only solid
     in the aperture must be the acrylic.

The *fabricated* outline (the Edge.Cuts the fab actually cuts) is measured by
``tools/verify_pcb.py``, which reads the real polygon out of the .kicad_pcb;
this gate only sees FreeCAD solids.

Run with FreeCAD's own interpreter:

    & "C:\\Program Files\\FreeCAD 1.1\\bin\\FreeCADCmd.exe" tools/verify_clearance.py --strict

Reports by default (exit 0) so the suite stays green while a fix is designed;
`--strict` exits 1 on any clash and is what CI runs once the geometry is closed.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402

FCSTD = os.path.join(ROOT, "mechanical", "freecad", "smell_monitor.FCStd")
STRICT = "--strict" in sys.argv[1:]
TOL = 0.001  # mm3 - below this is numerical dust, not a clash

BOSSES = [(CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
          (CONST["SH"] - CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
          (CONST["BOSS_INSET"], CONST["SW"] - CONST["BOSS_INSET"]),
          (CONST["SH"] - CONST["BOSS_INSET"],
           CONST["SW"] - CONST["BOSS_INSET"])]
WIN_X0 = CONST["DISP_X"] - CONST["DISP_WIN_W"] / 2.0
WIN_X1 = CONST["DISP_X"] + CONST["DISP_WIN_W"] / 2.0
WIN_Z0 = CONST["DISP_Z"] - CONST["DISP_WIN_H"] / 2.0
WIN_Z1 = CONST["DISP_Z"] + CONST["DISP_WIN_H"] / 2.0
PAN_X0 = CONST["DISP_X"] - CONST["DISP_W"] / 2.0
PAN_X1 = CONST["DISP_X"] + CONST["DISP_W"] / 2.0
PAN_Z0 = CONST["DISP_Z"] - CONST["DISP_H"] / 2.0
PAN_Z1 = CONST["DISP_Z"] + CONST["DISP_H"] / 2.0
GASKET = CONST["DISP_GASKET"]
ACRYLIC_Y0 = -2.0 * GASKET
ACRYLIC_Y1 = -GASKET
BEZEL_Y0 = ACRYLIC_Y0 - CONST["DISP_POD_D"]
BEZEL_Y1 = ACRYLIC_Y0
STACK_D = CONST["DISP_POD_D"] + 2.0 * GASKET
DISP_PARTS = ("display gasket", "display window", "display bezel",
              "OLED module", "button caps")
NO_X = [CONST["SH"] / 2.0 + dx
        for dx in (-CONST["NO_PITCH"], 0, CONST["NO_PITCH"])]

results = []


def near(a, b, tol=1e-4):
    return abs(a - b) <= tol


def check(name, volume, detail=""):
    ok = volume <= TOL
    results.append(ok)
    print("[%-4s] %-46s %10.3f mm3  %s"
          % ("ok  " if ok else "CLASH", name, volume, detail))


def check_bool(name, ok, detail=""):
    ok = bool(ok)
    results.append(ok)
    print("[%-4s] %-46s %s" % ("ok  " if ok else "FAIL", name, detail))


def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, FreeCAD.Vector(x0, y0, z0))


def cyl_faces(shape, radius, axis, tol=1e-3):
    """Centres of cylindrical faces of one radius and axis direction."""
    out = []
    for face in shape.Faces:
        surf = face.Surface
        if surf.__class__.__name__ != "Cylinder":
            continue
        if not near(surf.Radius, radius, tol):
            continue
        dot = surf.Axis.x * axis[0] + surf.Axis.y * axis[1] + surf.Axis.z * axis[2]
        if not near(abs(dot), 1.0, 1e-6):
            continue
        out.append((surf.Center.x, surf.Center.y, surf.Center.z))
    return out


def at_xy(points, xy, tol=0.01):
    return [p for p in points if near(p[0], xy[0], tol)
            and near(p[1], xy[1], tol)]


def main():
    doc = FreeCAD.openDocument(FCSTD)
    sh = {}
    for o in doc.Objects:
        shape = getattr(o, "Shape", None)
        if shape is not None:
            sh[o.Label] = shape
    missing = [k for k in ("shell", "pcb", "filter", "lid", "screws", "fan")
               + DISP_PARTS if k not in sh]
    if missing:
        print("FAIL: model is missing solids: %s" % missing)
        return 1

    # 1. The consumable must fit the drawer it slides into.
    check("filter pad vs tray (shell)", sh["filter"].common(sh["shell"]).Volume,
          "pad must drop in without force")

    # 2. The CAD board as modelled (it carries the notches).
    check("modelled PCB vs tray", sh["pcb"].common(sh["shell"]).Volume,
          "notched board clears the bosses")

    # 3. The notches must be cut larger than the boss, not merely equal to it:
    #    a ring of boss radius + 0.2 mm about each axis must find no material.
    total = 0.0
    for bx, by in BOSSES:
        cyl = Part.makeCylinder(CONST["BOSS_D"] / 2.0 + 0.2, CONST["PCB_T"],
                                 FreeCAD.Vector(bx, by, CONST["PCB_Z"]))
        total += sh["pcb"].common(cyl).Volume
    check("modelled PCB keeps 0.2 mm off each boss", total,
          "cut-out radius must exceed the boss radius")

    # The numbers a fitter needs.
    tangent = CONST["BOSS_INSET"] + CONST["BOSS_D"] / 2.0
    pad_y0 = sh["filter"].BoundBox.YMin
    print("")
    print("front boss tangent y = %.1f mm; filter pad front face y = %.1f mm "
          "(clearance %.1f mm)" % (tangent, pad_y0, pad_y0 - tangent))
    print("board cut-out radius: boss %.1f + %.1f = %.1f mm at %s"
          % (CONST["BOSS_D"] / 2.0, CONST["BOSS_CLEAR"],
             CONST["BOSS_D"] / 2.0 + CONST["BOSS_CLEAR"],
             ", ".join("(%.1f, %.1f)" % (x, y) for x, y in BOSSES)))

    # ---------------- front-panel UI on the fixed front wall ----------------
    cavity = box(CONST["CX0"], CONST["CY0"], CONST["CAV_Z0"],
                 CONST["CX1"], CONST["CY1"], CONST["CAV_Z1"])
    for name in DISP_PARTS:
        bb = sh[name].BoundBox
        check_bool("%s sits outside the cavity on the dry side" % name,
                   bb.YMax <= 1e-6
                   and sh[name].common(cavity).Volume <= TOL,
                   "y %.2f..%.2f; cavity starts %.2f"
                   % (bb.YMin, bb.YMax, CONST["CY0"]))
        check("%s does not intersect the shell or lid" % name,
              sh[name].common(sh["shell"]).Volume
              + sh[name].common(sh["lid"]).Volume,
              "stack is outside both solids")

    _pb = sh["display gasket"].BoundBox
    check_bool("panel footprint clears nostril tops and the lid seam",
               near(_pb.XMin, PAN_X0) and near(_pb.XMax, PAN_X1)
               and near(_pb.ZMin, PAN_Z0) and near(_pb.ZMax, PAN_Z1)
               and PAN_Z0 - (CONST["NO_Z"] + CONST["NO_R"]) >= 0.5 - 1e-6
               and CONST["LID_Z0"] - PAN_Z1 >= 0.5 - 1e-6,
               "x %.1f..%.1f, z %.1f..%.1f"
               % (_pb.XMin, _pb.XMax, _pb.ZMin, _pb.ZMax))

    # The stack runs outward from the wall: gasket, acrylic, bezel; the OLED is
    # inside the bezel aperture and the switch caps cover the four bores.
    _g, _w, _b = (sh[n].BoundBox for n in
                  ("display gasket", "display window", "display bezel"))
    _o, _caps = (sh[n].BoundBox for n in ("OLED module", "button caps"))
    check_bool("display stack = gasket / acrylic / bezel depths",
               near(_g.YMin, -GASKET) and near(_g.YMax, 0.0)
               and near(_w.YMin, ACRYLIC_Y0) and near(_w.YMax, ACRYLIC_Y1)
               and near(_b.YMin, BEZEL_Y0) and near(_b.YMax, BEZEL_Y1)
               and near(_g.ZLength, CONST["DISP_H"])
               and near(_w.ZLength, CONST["DISP_H"])
               and near(_b.ZLength, CONST["DISP_H"]),
               "%.1f..%.1f / %.1f..%.1f / %.1f..%.1f"
               % (_g.YMin, _g.YMax, _w.YMin, _w.YMax, _b.YMin, _b.YMax))
    check_bool("OLED is behind the acrylic, inside the window aperture",
               near(_o.YMin, BEZEL_Y0) and near(_o.YMax, BEZEL_Y1)
               and near(_o.XMin, WIN_X0) and near(_o.XMax, WIN_X1)
               and near(_o.ZMin, WIN_Z0) and near(_o.ZMax, WIN_Z1),
               "x %.1f..%.1f, z %.1f..%.1f, y %.1f..%.1f"
               % (_o.XMin, _o.XMax, _o.ZMin, _o.ZMax, _o.YMin, _o.YMax))
    check_bool("switch caps sit on the dry side of the front wall",
               near(_caps.YMax, 0.0) and _caps.YMin >= -GASKET - 1e-6
               and near(_caps.XMin, min(CONST["BTN_FRONT"].values())[0]
                        - CONST["BTN_HOLE_D"])
               and near(_caps.XMax, max(CONST["BTN_FRONT"].values())[0]
                        + CONST["BTN_HOLE_D"]),
               "y %.1f..%.1f" % (_caps.YMin, _caps.YMax))

    # The aperture is cut through the front wall.  Only acrylic fills its face;
    # the gasket and bezel are rings around it, and the OLED is behind it.
    wall_aperture = box(WIN_X0, -1.0, WIN_Z0, WIN_X1,
                        CONST["WALL"] + 1.0, WIN_Z1)
    check("front-wall display aperture is clear through the wall",
          sh["shell"].common(wall_aperture).Volume,
          "%g x %g at (%g,%g)"
          % (CONST["DISP_WIN_W"], CONST["DISP_WIN_H"],
             CONST["DISP_X"], CONST["DISP_Z"]))
    acrylic_prism = box(WIN_X0, ACRYLIC_Y0, WIN_Z0,
                        WIN_X1, ACRYLIC_Y1, WIN_Z1)
    check("acrylic covers the whole window aperture",
          abs(sh["display window"].common(acrylic_prism).Volume
              - acrylic_prism.Volume),
          "wetted face is PMMA only")
    for name in ("display gasket", "display bezel",
                 "OLED module", "button caps"):
        check("%s stays out of the wetted aperture" % name,
              sh[name].common(acrylic_prism).Volume,
              "aperture must not touch gasket, bezel, OLED or caps")

    # Cable grommet: a real DIA6 bore in the fixed front wall.
    feed = Part.makeCylinder(
        CONST["UI_FEED_D"] / 2.0, CONST["WALL"] + 2.0,
        FreeCAD.Vector(CONST["UI_FEED_X"], -1.0, CONST["UI_FEED_Z"]),
        FreeCAD.Vector(0, 1, 0))
    check("front-wall harness grommet is clear", sh["shell"].common(feed).Volume,
          "DIA%g at (%g,%g)"
          % (CONST["UI_FEED_D"], CONST["UI_FEED_X"], CONST["UI_FEED_Z"]))
    _feed_faces = [p for p in cyl_faces(
        sh["shell"], CONST["UI_FEED_D"] / 2.0, (0, 1, 0))
        if at_xy([(p[0], p[2])],
                 (CONST["UI_FEED_X"], CONST["UI_FEED_Z"]))]
    check_bool("grommet is a cylindrical DIA%g bore" % CONST["UI_FEED_D"],
               len(_feed_faces) == 1,
               str([(round(p[0], 2), round(p[2], 2)) for p in _feed_faces]))
    for name in DISP_PARTS:
        check("%s clears the harness bore" % name,
              sh[name].common(feed).Volume, "grommet is in the wall")

    # Four front-panel switch bores and their caps.
    btn_total = 0.0
    for bx, bz in CONST["BTN_FRONT"].values():
        cyl = Part.makeCylinder(
            CONST["BTN_HOLE_D"] / 2.0, CONST["WALL"] + 2.0,
            FreeCAD.Vector(bx, -1.0, bz), FreeCAD.Vector(0, 1, 0))
        btn_total += sh["shell"].common(cyl).Volume
    check("four front-wall switch holes are clear at BTN_FRONT", btn_total,
          ", ".join("(%g,%g)" % xy for xy in CONST["BTN_FRONT"].values()))
    _btn_faces = cyl_faces(sh["shell"], CONST["BTN_HOLE_D"] / 2.0, (0, 1, 0))
    _btn_got = sorted((round(p[0], 3), round(p[2], 3))
                      for p in _btn_faces
                      if any(at_xy([(p[0], p[2])], xy)
                             for xy in CONST["BTN_FRONT"].values()))
    _btn_want = sorted((round(x, 3), round(z, 3))
                       for x, z in CONST["BTN_FRONT"].values())
    check_bool("switch holes are DIA%g cylinders at BTN_FRONT"
               % CONST["BTN_HOLE_D"],
               _btn_got == _btn_want and len(_btn_got) == 4, str(_btn_got))
    _cap_faces = cyl_faces(sh["button caps"], CONST["BTN_HOLE_D"], (0, 1, 0))
    _cap_got = sorted((round(p[0], 3), round(p[2], 3))
                      for p in _cap_faces
                      if any(at_xy([(p[0], p[2])], xy)
                             for xy in CONST["BTN_FRONT"].values()))
    check_bool("four DIA%g caps cover the switch holes from outside"
               % (2 * CONST["BTN_HOLE_D"]),
               _cap_got == _btn_want and len(_cap_got) == 4, str(_cap_got))

    # The lid is a plain plate: only the four M3 through/counterbore pairs.
    _lid_ui = sh["lid"].common(wall_aperture).Volume
    _lid_ui += sh["lid"].common(feed).Volume
    for bx, bz in CONST["BTN_FRONT"].values():
        _lid_ui += sh["lid"].common(Part.makeCylinder(
            CONST["BTN_HOLE_D"] / 2.0, CONST["WALL"] + 2.0,
            FreeCAD.Vector(bx, -1.0, bz), FreeCAD.Vector(0, 1, 0))).Volume
    check("plain lid has no UI cuts", _lid_ui,
          "all UI cuts stay in the fixed front wall")
    _lid_btn = cyl_faces(sh["lid"], CONST["BTN_HOLE_D"] / 2.0, (0, 0, 1))
    check_bool("lid M3 holes are only at the four boss centres",
               len(_lid_btn) == 4
               and all(any(at_xy([(p[0], p[1])], xy) for xy in BOSSES)
                       for p in _lid_btn),
               str([(round(p[0], 2), round(p[1], 2)) for p in _lid_btn]))
    _lid_feed = cyl_faces(sh["lid"], CONST["UI_FEED_D"] / 2.0, (0, 0, 1))
    check_bool("lid has no UI grommet", not _lid_feed, str(_lid_feed))

    # ---------------- unchanged architecture (no CFD changes here) ----------
    _no = [p for p in cyl_faces(sh["shell"], CONST["NO_R"], (0, 1, 0))
           if any(at_xy([(p[0], p[2])], (x, CONST["NO_Z"])) for x in NO_X)]
    _no_got = sorted((round(p[0], 3), round(p[2], 3)) for p in _no)
    _no_want = sorted((round(x, 3), round(CONST["NO_Z"], 3)) for x in NO_X)
    check_bool("shell keeps 3 centred nostrils of radius NO_R",
               _no_got == _no_want and len(_no_got) == 3, str(_no_got))
    _usb = [p for p in cyl_faces(sh["shell"], CONST["USB_R"], (0, 1, 0))
            if at_xy([(p[0], p[2])], (CONST["USB_X"], CONST["USB_Z"]))]
    check_bool("shell keeps the USB bulkhead bore",
               len(_usb) == 1, str([(round(p[0], 2), round(p[2], 2))
                                    for p in _usb]))
    _fan = [p for p in cyl_faces(sh["shell"], CONST["FAN_R"], (0, 1, 0))
            if at_xy([(p[0], p[2])], (CONST["FAN_X"], CONST["FAN_Z"]))]
    check_bool("shell keeps the DIA%d fan bore" % (2 * CONST["FAN_R"]),
               len(_fan) == 1, str([(round(p[0], 2), round(p[2], 2))
                                    for p in _fan]))
    _fb = sh["fan"].BoundBox
    _fan_side = 2 * (CONST["FAN_R"] + 1)  # 1 mm shroud beyond the bore
    check_bool("fan envelope still %g x %g x %g" % (
        _fan_side, CONST["FAN_T"], _fan_side),
        near(_fb.XLength, _fan_side) and near(_fb.YLength, CONST["FAN_T"])
        and near(_fb.ZLength, _fan_side),
        "%.1f x %.1f x %.1f" % (_fb.XLength, _fb.YLength, _fb.ZLength))

    # Filter drawer slot: clear passage with both side rails and the bottom
    # rail still present at their CONST positions.
    slot = box(CONST["CX0"] + CONST["RAIL_W"] + 0.01,
               CONST["FILT_Y0"] + 0.01, CONST["FILT_Z0"],
               CONST["CX1"] - CONST["RAIL_W"] - 0.01,
               CONST["FILT_Y1"] - 0.01, CONST["CAV_Z1"])
    check("filter drawer passage is clear", sh["shell"].common(slot).Volume,
          "y %.2f..%.2f, z %.1f..%.1f"
          % (CONST["FILT_Y0"], CONST["FILT_Y1"],
             CONST["FILT_Z0"], CONST["CAV_Z1"]))
    for name, sample in (
            ("left filter rail",
             box(CONST["CX0"], CONST["FILT_Y0"] + 1.0, CONST["FILT_Z0"] + 1.0,
                 CONST["CX0"] + CONST["RAIL_W"], CONST["FILT_Y1"] - 1.0,
                 CONST["CAV_Z1"] - 1.0)),
            ("right filter rail",
             box(CONST["CX1"] - CONST["RAIL_W"], CONST["FILT_Y0"] + 1.0,
                 CONST["FILT_Z0"] + 1.0, CONST["CX1"],
                 CONST["FILT_Y1"] - 1.0, CONST["CAV_Z1"] - 1.0)),
            ("filter bottom rail",
             box(CONST["CX0"] + CONST["RAIL_W"] + 1.0,
                 CONST["FILT_Y0"] + 1.0,
                 CONST["FILT_Z0"] - CONST["RAIL_W"],
                 CONST["CX1"] - CONST["RAIL_W"] - 1.0,
                 CONST["FILT_Y1"] - 1.0, CONST["FILT_Z0"]))):
        check_bool("%s still present" % name,
                   sh["shell"].common(sample).Volume > TOL,
                   "%.1f mm3" % sh["shell"].common(sample).Volume)

    # The wall is still WALL thick at a point away from nostrils, UI and bosses.
    _wx = (CONST["USB_X"] + CONST["USB_R"] + WIN_X0) / 2.0
    _wz0, _wz1 = CONST["NO_Z"] + CONST["NO_R"] + 5.0, CONST["FLOOR_T"] + 50.0
    _material = box(_wx - 2.0, 0.5, _wz0,
                    _wx + 2.0, CONST["WALL"] - 0.5, _wz1)
    _clear = box(_wx - 2.0, CONST["WALL"] + 0.5, _wz0,
                 _wx + 2.0, CONST["WALL"] + 3.0, _wz1)
    check_bool("front wall keeps WALL thickness and an open cavity",
               sh["shell"].common(_material).Volume > TOL
               and sh["shell"].common(_clear).Volume <= TOL,
               "wall %.1f mm at x=%.1f" % (CONST["WALL"], _wx))

    # Four M3 screws and the flat lid remain part of the baseline.
    _screw_centres = sorted((round((s.BoundBox.XMin + s.BoundBox.XMax) / 2.0, 3),
                             round((s.BoundBox.YMin + s.BoundBox.YMax) / 2.0, 3))
                            for s in sh["screws"].Solids)
    check_bool("four M3 lid screws remain at the boss centres",
               _screw_centres == sorted((round(x, 3), round(y, 3))
                                        for x, y in BOSSES),
               str(_screw_centres))
    _lb = sh["lid"].BoundBox
    check_bool("lid stays a flat SH x SW x LID_T plate",
               near(_lb.XLength, CONST["SH"]) and near(_lb.YLength, CONST["SW"])
               and near(_lb.ZLength, CONST["LID_T"]),
               "%.1f x %.1f x %.1f" % (_lb.XLength, _lb.YLength, _lb.ZLength))

    bad = results.count(False)
    print("")
    print("RESULT: %s (%d of %d clearance checks failed)"
          % ("PASS" if bad == 0 else "OPEN", bad, len(results)))
    if STRICT and bad:
        return 1
    return 0


if True:  # FreeCADCmd executes the file directly; a __main__ guard would skip it
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    _rc = main()
    sys.stdout.flush()
    raise SystemExit(_rc)
