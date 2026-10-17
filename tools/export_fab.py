#!/usr/bin/env python3
"""Export the reproducible fabrication package for the OpenSmell v1.1 board.

A fab house wants a *specific* layer set, not "everything KiCad can plot".
``kicad-cli pcb export gerbers`` with no ``--layers`` dumps cosmetic layers
(Adhesive, Courtyard, Fab, Margin, User_1..4, User_Comments, User_Drawings,
User_Eco1/2) which no board shop can use and which only add noise to the zip.

This script is the single command that regenerates ``electrical/<proj>/fab/``
from the routed board, so the export is reproducible instead of hand-clicked:

    gerbers   F.Cu B.Cu F.Mask B.Mask F.Silkscreen B.Silkscreen F.Paste
              B.Paste Edge.Cuts  (+ the KiCad .gbrjob)
    drill     Excellon, mm, separate PTH/NPTH
    assembly  one front-side CPL (pick-and-place CSV)

Any other file already sitting in ``fab/`` is removed, so a stale layer from an
older export cannot ship by accident.  The board STEP is *not* exported: it is
5+ MB of regenerable geometry, not a fab deliverable.

Run:  python tools/export_fab.py
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT = "smell_monitor_v1_1"
PCB = os.path.join(ROOT, "electrical", PROJECT, PROJECT + ".kicad_pcb")
FAB = os.path.join(ROOT, "electrical", PROJECT, "fab")

LAYERS = [
    "F.Cu", "B.Cu",
    "F.Mask", "B.Mask",
    "F.Silkscreen", "B.Silkscreen",
    "F.Paste", "B.Paste",
    "Edge.Cuts",
]


def kicad_cli():
    for cand in ("kicad-cli", "kicad-cli.exe"):
        p = shutil.which(cand)
        if p:
            return p
    for cand in (r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
                 r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
                 "/usr/bin/kicad-cli"):
        if os.path.isfile(cand):
            return cand
    raise SystemExit("kicad-cli not found on PATH (nothing was changed)")


def run(cli, *args):
    cmd = [cli] + list(args)
    print("  $ " + " ".join(os.path.basename(c) if os.sep in c else c
                            for c in cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        raise SystemExit("kicad-cli exited %d" % r.returncode)


def expected():
    """Every filename this export is allowed to leave in fab/."""
    n = PROJECT
    names = {
        f"{n}-F_Cu.gtl", f"{n}-B_Cu.gbl",
        f"{n}-F_Mask.gts", f"{n}-B_Mask.gbs",
        f"{n}-F_Silkscreen.gto", f"{n}-B_Silkscreen.gbo",
        f"{n}-F_Paste.gtp", f"{n}-B_Paste.gbp",
        f"{n}-Edge_Cuts.gm1", f"{n}-job.gbrjob",
        f"{n}-PTH.drl", f"{n}-NPTH.drl",
        f"{n}-cpl.csv",
    }
    return names


def main():
    if not os.path.isfile(PCB):
        raise SystemExit("no board at %s (nothing was changed)" % PCB)
    cli = kicad_cli()
    os.makedirs(FAB, exist_ok=True)

    print("exporting %s" % os.path.relpath(PCB, ROOT))
    run(cli, "pcb", "export", "gerbers", "-o", FAB,
        "--layers", ",".join(LAYERS), PCB)
    run(cli, "pcb", "export", "drill", "-o", FAB, "--format", "excellon",
        "--excellon-units", "mm", "--excellon-separate-th",
        "--drill-origin", "absolute", PCB)
    run(cli, "pcb", "export", "pos", "-o",
        os.path.join(FAB, PROJECT + "-cpl.csv"), "--format", "csv",
        "--units", "mm", "--side", "front", "--smd-only",
        "--use-drill-file-origin", PCB)

    keep = expected()
    dropped = []
    for name in sorted(os.listdir(FAB)):
        if name not in keep:
            p = os.path.join(FAB, name)
            os.remove(p)
            dropped.append(name)

    have = sorted(os.listdir(FAB))
    missing = sorted(keep - set(have))
    print("  kept    %d files" % len(have))
    if dropped:
        print("  dropped %d stray: %s" % (len(dropped), ", ".join(dropped)))
    if missing:
        print("  MISSING %d: %s" % (len(missing), ", ".join(missing)))
        raise SystemExit(1)
    print("fab OK ->", os.path.relpath(FAB, ROOT))


if __name__ == "__main__":
    main()
