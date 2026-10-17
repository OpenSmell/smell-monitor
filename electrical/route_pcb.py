#!/usr/bin/env python3
"""Route the placed OpenSmell v1.1 PCB with FreeRouting.

`gen_pcb.py` writes a board that is fully placed and fully net-listed but has no
copper on it (181 unconnected).  This script closes that gap, and is the only
supported way to put copper on the board, so that the routed artifact in git is
reproducible instead of hand-drawn:

    1. export a Specctra ``.dsn`` from the placed board,
    2. run FreeRouting until every connection is routed,
    3. import the resulting ``.ses`` session back into the board,
    4. refuse to save unless the board came back with 0 unconnected.

FreeRouting is a Java tool and is not vendored here.  Point the script at the
jar once per shell::

    set FREEROUTING_JAR=C:\\Tools\\freerouting\\freerouting-2.5.0.jar
    & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" electrical/route_pcb.py

Notes
-----
* Use the ``.jar`` through ``java -jar``.  The ``freerouting-cli.exe`` native
  build of 2.5.0 aborts on this board with ``UnsupportedFeatureError:
  SerializationConstructorAccessor ... ComponentOutline``.
* ``-mp`` has to be high enough for the autorouter to reach 0 unrouted before
  the optimizer stage starts, because the optimizer is skipped entirely on an
  incomplete board.  This design finishes at pass 6; the default here is 12.
* The autorouter is multi-threaded, so the exact copper is not bit-stable
  between runs.  What is stable is the outcome, and that is what the gate in
  ``tools/verify_pcb.py`` checks: 0 unconnected, no track below the 0.15 mm
  fab minimum, and 0 DRC errors.
* Input must be a freshly generated board.  Routing is not incremental and
  importing a session on top of existing copper is undefined.
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, r"C:\Users\PRAISE\AppData\Roaming\Python\Python313\site-packages")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pcbnew  # noqa: E402

PROJECT = "smell_monitor_v1_1"
PCB = os.path.join(HERE, PROJECT, PROJECT + ".kicad_pcb")
PASSES = 12


def find_jar():
    jar = os.environ.get("FREEROUTING_JAR", "")
    if jar and os.path.isfile(jar):
        return jar
    raise SystemExit(
        "set FREEROUTING_JAR to the FreeRouting jar, e.g. "
        "freerouting-2.5.0.jar (nothing was changed)")


def run_router(jar, dsn, ses):
    java = shutil.which("java")
    if java is None:
        raise SystemExit("java not found on PATH (nothing was changed)")
    cmd = [java, "-jar", jar, "-de", dsn, "-do", ses,
           "-mp", str(PASSES), "-l", "en"]
    print("  $ java -jar %s -de %s -do %s -mp %d -l en"
          % (os.path.basename(jar), os.path.basename(dsn),
             os.path.basename(ses), PASSES))
    # run inside the throwaway DSN/SES directory: FreeRouting writes its log to
    # a locale directory ("en/freerouting.log") relative to the CWD, which would
    # otherwise litter the repository root
    proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True,
                          cwd=os.path.dirname(dsn) or None)
    for line in proc.stdout.splitlines():
        if ("pass #" in line or "Optimization was completed" in line
                or "Skipping optimization" in line or "Saved" in line):
            print("    " + line.split("] ", 1)[-1].strip())
    if proc.returncode != 0 or not os.path.isfile(ses):
        raise SystemExit("FreeRouting failed (exit %d)" % proc.returncode)


def main():
    if not os.path.isfile(PCB):
        raise SystemExit("no board at %s - run electrical/gen_pcb.py first"
                         % PCB)

    jar = find_jar()
    board = pcbnew.LoadBoard(PCB)

    if list(board.GetTracks()):
        raise SystemExit(
            "board already has copper; re-run electrical/gen_pcb.py "
            "(--force) to restore the unrouted placed board first")

    print("routing %s (%d unconnected)"
          % (PCB, board.GetConnectivity().GetUnconnectedCount(False)))

    tmp = tempfile.mkdtemp(prefix="osmell-route-")
    dsn = os.path.join(tmp, PROJECT + ".dsn")
    ses = os.path.join(tmp, PROJECT + ".ses")
    try:
        if not pcbnew.ExportSpecctraDSN(board, dsn):
            raise SystemExit("DSN export failed")
        run_router(jar, dsn, ses)
        if not pcbnew.ImportSpecctraSES(board, ses):
            raise SystemExit("SES import failed")
        left = board.GetConnectivity().GetUnconnectedCount(False)
        if left:
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
