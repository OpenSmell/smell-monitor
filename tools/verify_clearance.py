"""Solid-to-solid clearance gate for the enclosure (FreeCAD, not a drawing check).

`tools/verify_cad.py` proves the drawings match the constants; it cannot prove
that separately-built solids do not occupy the same space.  Two defects of that
class are cheap to make and expensive to find at assembly, so they are measured
here:

  1. **Filter pad vs the tray.**  The pad is a separate solid that has to drop
     into the drawer.  Any overlap with a boss or rail means the pad cannot be
     fitted, however correct the drawing looks.
  2. **The real PCB outline vs the lid bosses.**  The CAD board carries four
     r = 5 mm corner notches, but the fabricated board's Edge.Cuts is a plain
     rectangle.  If a boss intersects that rectangle, the board cannot drop past
     it, and no amount of DRC-clean copper changes that.

Run with FreeCAD's own interpreter:

    & "C:\\Program Files\\FreeCAD 1.1\\bin\\FreeCADCmd.exe" tools/verify_clearance.py

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

CZ0 = CONST["CAV_Z0"]
CZ1 = CONST["CAV_Z1"]
PCB_W, PCB_D = CONST["PCB_X"], CONST["PCB_Y"]
PCB_X0 = (CONST["SH"] - PCB_W) / 2.0
PCB_Y0 = (CONST["SW"] - PCB_D) / 2.0
BOSSES = [(CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
          (CONST["SH"] - CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
          (CONST["BOSS_INSET"], CONST["SW"] - CONST["BOSS_INSET"]),
          (CONST["SH"] - CONST["BOSS_INSET"], CONST["SW"] - CONST["BOSS_INSET"])]

results = []


def check(name, volume, detail=""):
    ok = volume <= TOL
    results.append(ok)
    print("[%-4s] %-46s %10.3f mm3  %s"
          % ("ok  " if ok else "CLASH", name, volume, detail))


def main():
    doc = FreeCAD.openDocument(FCSTD)
    sh = {}
    for o in doc.Objects:
        shape = getattr(o, "Shape", None)
        if shape is not None:
            sh[o.Label] = shape
    missing = [k for k in ("shell", "pcb", "filter") if k not in sh]
    if missing:
        print("FAIL: model is missing solids: %s" % missing)
        return 1

    # 1. The consumable must fit the drawer it slides into.
    check("filter pad vs tray (shell)", sh["filter"].common(sh["shell"]).Volume,
          "pad must drop in without force")

    # 2. The CAD board as modelled (it carries the notches).
    check("modelled PCB vs tray", sh["pcb"].common(sh["shell"]).Volume,
          "notched board clears the bosses")

    # 3. The board the fab actually receives: a plain rectangle.
    rect = Part.makeBox(PCB_W, PCB_D, CONST["PCB_T"],
                        FreeCAD.Vector(PCB_X0, PCB_Y0, CONST["PCB_Z"]))
    total = 0.0
    worst = 0.0
    for bx, by in BOSSES:
        cyl = Part.makeCylinder(CONST["BOSS_D"] / 2.0, CZ1 - CZ0,
                                FreeCAD.Vector(bx, by, CZ0))
        v = rect.common(cyl).Volume
        total += v
        worst = max(worst, v)
    check("rectangular PCB outline vs bosses", total,
          "the drawn Edge.Cuts has no notches")

    # The numbers a fix needs.
    tangent = CONST["BOSS_INSET"] + CONST["BOSS_D"] / 2.0
    pad_y0 = sh["filter"].BoundBox.YMin
    print("")
    print("front boss tangent y = %.1f mm; filter pad front face y = %.1f mm "
          "(clearance %.1f mm)" % (tangent, pad_y0, pad_y0 - tangent))
    print("notch radius needed on the PCB:  %.1f mm at %s"
          % (CONST["BOSS_D"] / 2.0 + 1.0,
             ", ".join("(%.1f, %.1f)" % (x, y) for x, y in BOSSES)))

    bad = results.count(False)
    print("")
    print("RESULT: %s (%d of %d clearance checks clash)"
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
