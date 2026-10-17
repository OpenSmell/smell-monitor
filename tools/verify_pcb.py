#!/usr/bin/env python3
"""Numeric verification of the routed PCB against the chamber contract.

The routed board is the one deliverable that costs money and a fab lead time,
so it is checked with numbers rather than by looking at pictures:

  * placement - all 8 sensing headers sit exactly on
    ``interface.ANALOG_HEADERS`` / ``DIGITAL_HEADERS`` (the L2 contract), so a
    slot can never drift off its chamber well,
  * fabrication - board outline = ``CONST['PCB_X'] x CONST['PCB_Y']``, no
    copper narrower than the board's own minimum track width, via stack sane,
  * routing - every net fully connected (0 unconnected),
  * DRC - ``kicad-cli pcb drc`` clean (0 violations / 0 unconnected /
    0 footprint errors), i.e. the board a fab house would accept.

pcbnew is only importable from KiCad's own interpreter, so this gate runs with
it (same as ``electrical/gen_pcb.py``):

  & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" tools/verify_pcb.py

If ``kicad-cli`` cannot be found the DRC row is reported SKIPPED (loudly) and
the rest of the gate still decides the exit code.
"""
import os
import glob
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "electrical"))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
# KiCad ships its own interpreter, so the user site (kiutils, used by
# electrical/board.py) is not on its path by default: add every one we find.
for _p in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python3*\site-packages")):
    if os.path.isdir(_p):
        sys.path.append(_p)

import pcbnew  # noqa: E402
import interface as IF  # noqa: E402
import board as B  # noqa: E402
from constants import CONST  # noqa: E402

PROJECT = "smell_monitor_v1_1"
PCB = os.path.join(ROOT, "electrical", PROJECT, PROJECT + ".kicad_pcb")
MIN_TRACK_MM = 0.15            # board design-rule minimum (netclass nominal 0.30)
FAILS = []
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    if not ok:
        FAILS.append(name)


def mm(v):
    return round(pcbnew.ToMM(v), 4)


board = pcbnew.LoadBoard(PCB)
B.build()                       # board.py builds PARTS/NETS on demand

# ------------------------------- placement ----------------------------------
# what must land on a chamber well is the header's connector line (the pad
# centre), not the footprint origin
def pad_centre(fp):
    pts = [p.GetPosition() for p in fp.Pads()]
    return (sum(mm(p.x) for p in pts) / len(pts),
            sum(mm(p.y) for p in pts) / len(pts))


rows = {"analog": IF.ANALOG_HEADERS, "digital": IF.DIGITAL_HEADERS}
for bank, want in rows.items():
    refs = [f"J{i}" for i in (range(2, 6) if bank == "analog" else range(6, 10))]
    got = []
    for ref in refs:
        fp = board.FindFootprintByReference(ref)
        got.append(None if fp is None
                   else (pad_centre(fp) + (fp.GetOrientationDegrees(),)))
    ok = all(g is not None for g in got) and all(
        abs(g[0] - x) <= 0.01 and abs(g[1] - (CONST["PCB_Y"] - y)) <= 0.01
        and g[2] == 0.0
        for g, (x, y) in zip(got, want))
    check(f"{bank} headers J{refs[0][1]}..J{refs[-1][1]} on the chamber contract",
          ok, "" if ok else str([(g[0], round(CONST["PCB_Y"] - g[1], 2))
                                 for g in got if g]))

# ------------------------------ fabrication ---------------------------------
# measure the outline from the Edge.Cuts segments themselves - the bounding box
# would include the 0.1 mm edge line width
edge = []
for d in board.GetDrawings():
    if d.GetLayer() == pcbnew.Edge_Cuts and isinstance(d, pcbnew.PCB_SHAPE):
        for pt in (d.GetStart(), d.GetEnd()):
            edge.append((mm(pt.x), mm(pt.y)))
w = max(p[0] for p in edge) - min(p[0] for p in edge)
h = max(p[1] for p in edge) - min(p[1] for p in edge)
check(f"board outline = {CONST['PCB_X']:.0f} x {CONST['PCB_Y']:.0f} mm",
      abs(w - CONST["PCB_X"]) <= 0.01 and abs(h - CONST["PCB_Y"]) <= 0.01,
      f"{w} x {h}")

tracks = [t for t in board.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
vias = [t for t in board.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
widths = sorted({mm(t.GetWidth()) for t in tracks})
check(f"no track below the {MIN_TRACK_MM} mm board minimum",
      bool(widths) and widths[0] >= MIN_TRACK_MM - 1e-6,
      f"min {widths[0]} mm of {len(widths)} widths={widths}")
via_pads = sorted({mm(v.GetWidth(pcbnew.F_Cu)) for v in vias})
via_drills = sorted({mm(v.GetDrillValue()) for v in vias})
check("via stack is a single sane size (0.6 / 0.3 mm)",
      via_pads == [0.6] and via_drills == [0.3],
      f"pads={via_pads} drills={via_drills}")

# -------------------------------- parity ------------------------------------
check("one footprint per board.py part",
      len(board.GetFootprints()) == len(B.PARTS),
      f"{len(board.GetFootprints())} vs {len(B.PARTS)}")
check("one net per board.py net",
      board.GetNetCount() - 1 == len(B.NETS),      # net 0 is the no-net sentinel
      f"{board.GetNetCount()-1} vs {len(B.NETS)}")

# ------------------------------- routing ------------------------------------
check("every net fully routed (0 unconnected)",
      board.GetConnectivity().GetUnconnectedCount(False) == 0,
      str(board.GetConnectivity().GetUnconnectedCount(False)))

# --------------------------------- DRC --------------------------------------
def kicad_cli():
    p = shutil.which("kicad-cli")
    if p:
        return p
    for cand in (r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
                 r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
                 "/usr/bin/kicad-cli"):
        if os.path.isfile(cand):
            return cand
    return None


cli = kicad_cli()
if cli is None:
    CHECKS.append(("kicad-cli DRC", None,
                   "SKIPPED - kicad-cli not found; run it before shipping"))
else:
    rpt = os.path.join(tempfile.gettempdir(), PROJECT + "-verify-drc.rpt")
    subprocess.run([cli, "pcb", "drc", "--format", "report", "--severity-all",
                    "-o", rpt, PCB], capture_output=True, text=True)
    txt = open(rpt, encoding="utf-8", errors="replace").read() \
        if os.path.isfile(rpt) else ""
    n_viol = txt.count("** Found 0 DRC violations") == 1
    n_unconn = txt.count("** Found 0 unconnected pads") == 1
    n_fp = txt.count("** Found 0 Footprint errors") == 1
    check("DRC clean (0 violations / 0 unconnected / 0 footprint errors)",
          n_viol and n_unconn and n_fp,
          " ".join(s for s, ok in (("violations", n_viol),
                                   ("unconnected", n_unconn),
                                   ("footprints", n_fp)) if not ok) or "clean")

# ------------------------------- report -------------------------------------
w = max(len(n) for n, _, _ in CHECKS) + 2
print(f"{'CHECK':<{w}} {'RESULT':<7} DETAIL")
for name, ok, detail in CHECKS:
    verdict = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
    print(f"{name:<{w}} {verdict:<7} {detail}")
print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    sys.exit(1)
print("ALL PASS - routed board consistent with the chamber contract")
