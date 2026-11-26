#!/usr/bin/env python3
"""Route the placed board that already carries the three seeded fine-pitch escapes.

``electrical/gen_pcb.py`` writes J19/J20 placement and seeds the USB-C CC1,
USB-C D_N and TCA9548A SD7 local escapes before DSN export.  FreeRouting's
standard driver, ``electrical/route_pcb.py``, deliberately refuses any board
that already has copper, so this wrapper reuses that driver's jar discovery and
router invocation but allows the seeded tracks to stay in the board.

Run with KiCad's Python after ``gen_pcb.py --force``::

    set FREEROUTING_JAR=C:\\Users\\PRAISE\\Tools\\freerouting\\freerouting-2.5.0.jar
    & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" \\
        electrical/smell_monitor_v1_1/route_seeded.py

The import is only saved when KiCad's connectivity reports 0 unconnected pads.
FreeRouting is multi-threaded and occasionally stalls at two open connections;
in that case regenerate with ``gen_pcb.py --force`` and rerun until it saves.
After a successful route, run ``cleanup_drc.py`` to drop unused vias/stubs.
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ELEC = os.path.dirname(HERE)
sys.path.insert(0, ELEC)
sys.path.insert(0, r"C:\Users\PRAISE\AppData\Roaming\Python\Python313\site-packages")

import pcbnew  # noqa: E402
import route_pcb  # noqa: E402

# The seeded board reaches 0 unrouted at auto-routing pass 6; 12 passes only
# adds optimizer time.  Let FREEROUTING_PASSES override for experiments.
route_pcb.PASSES = int(os.environ.get("FREEROUTING_PASSES", "6"))

PCB = os.path.join(HERE, "smell_monitor_v1_1.kicad_pcb")
EXPECTED_SEEDS = 10  # CC1 3 + D_N 5 + SD7 2, from gen_pcb.SEED_TRACKS


def main():
    if not os.path.isfile(PCB):
        raise SystemExit("no board at %s - run electrical/gen_pcb.py first" % PCB)
    jar = route_pcb.find_jar()
    board = pcbnew.LoadBoard(PCB)
    seeds = len(list(board.GetTracks()))
    if seeds != EXPECTED_SEEDS:
        raise SystemExit("expected %d seeded track(s), found %d - regenerate "
                         "with electrical/gen_pcb.py --force"
                         % (EXPECTED_SEEDS, seeds))
    left0 = board.GetConnectivity().GetUnconnectedCount(False)
    print("routing seeded %s (%d tracks, %d unconnected)"
          % (os.path.basename(PCB), seeds, left0))

    tmp = tempfile.mkdtemp(prefix="osmell-seeded-route-")
    dsn = os.path.join(tmp, "smell_monitor_v1_1.dsn")
    ses = os.path.join(tmp, "smell_monitor_v1_1.ses")
    try:
        if not pcbnew.ExportSpecctraDSN(board, dsn):
            raise SystemExit("DSN export failed")
        route_pcb.run_router(jar, dsn, ses)
        if not pcbnew.ImportSpecctraSES(board, ses):
            raise SystemExit("SES import failed")
        left = board.GetConnectivity().GetUnconnectedCount(False)
        if left:
            dbg = os.environ.get("ROUTE_DEBUG_SAVE", "")
            if dbg:
                board.Save(dbg)
                print("  saved partially routed board to %s" % dbg)
            raise SystemExit("%d connections still unrouted - not saving" % left)
        board.Save(PCB)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    vias = sum(1 for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T)
    segs = sum(1 for t in board.GetTracks() if t.Type() != pcbnew.PCB_VIA_T)
    print("  routed: %d segments, %d vias, 0 unconnected" % (segs, vias))
    print("  wrote %s" % PCB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
