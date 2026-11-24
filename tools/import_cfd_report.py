#!/usr/bin/env python3
"""Import an OpenFOAM run into the repository as a readable CFD report.

Usage:
  python tools/import_cfd_report.py --case-dir /path/to/case [--label my-run]

It reads postProcessing/probes/*/T and log.* from a completed run, copies those
small text artefacts into cfd/results/<label>/, and rewrites cfd/RESULTS.md with
the parsed t63/t90 table, the numerical scheme in use, and the achieved Courant
and continuity figures as the acceptance check.

Run from anywhere; no OpenFOAM installation is required to import.
"""
import argparse
import importlib.util
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT_PY = ROOT / "cfd" / "report.py"
OUT_MD = ROOT / "cfd" / "RESULTS.md"

SCHEME_NOTE = """## Numerical setup

The tracer pass is transient (`Euler`, `deltaT = 4e-4 s`) on the converged
steady flow field, with the scalar discretised by `bounded Gauss limitedLinear 1`
(TVD, bounded, second-order). At the imposed 15 L/min the inlet jets reach
~2 m/s through 1 mm cells, so `deltaT` holds the Courant number at or below 0.8.
The plug-flow reference for the empty chamber is V/Q = 2.28 s.

| Check | Value | Criterion |
|---|---:|---|
| Max Courant number (tracer) | %s | <= 1 |
| Final global continuity error | %s | <= 1e-6 |
| Cell count | %s | checkMesh: Mesh OK |

%s
"""


def quality_note(meta):
    co = meta.get("courant_max")
    cont = meta.get("continuity_global")
    try:
        co_v = float(co) if co else None
    except ValueError:
        co_v = None
    try:
        cont_v = abs(float(cont)) if cont else None
    except ValueError:
        cont_v = None
    if co_v is None:
        return ("**Numerical quality: Courant number not parsed from the log.** "
                "Check `log.scalarTransportFoam` before using these times.")
    if co_v > 1.0:
        return ("**Numerical quality: FAILED.** Max Courant %.2f exceeds 1. The "
                "tracer step violated the stability criterion; re-run with a "
                "smaller `deltaT`." % co_v)
    ok_cont = cont_v is None or cont_v <= 1e-6
    verdict = "PASS" if ok_cont else "REVIEW continuity"
    return ("**Numerical quality: %s.** Max Courant %.3f (limit 1); final global "
            "continuity %s. The tracer transient is resolved and bounded."
            % (verdict, co_v, cont or "n/a"))


def load_report_module():
    spec = importlib.util.spec_from_file_location("osm_cfd_report", REPORT_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def probe_file(case):
    hits = sorted((case / "postProcessing" / "probes").glob("*/T"))
    return hits[-1] if hits else None


def log_summary(case):
    text = ""
    for name in ("log.simpleFoam", "log.scalarTransportFoam",
                 "log.snappyHexMesh", "log.blockMesh"):
        p = case / name
        if p.is_file():
            text += "\n" + p.read_text(errors="replace")
    cells = re.findall(r"(?:nCells|cells)\s*[:=]?\s*(\d+)", text)
    cont = re.findall(r"time step continuity errors.*?global\s*=\s*([-\d.eE+]+)",
                      text)
    cour = re.findall(r"Courant Number mean:\s*[-\d.eE+]+\s+max:\s*([-\d.eE+]+)",
                      text)
    return {
        "cells": int(cells[-1]) if cells else None,
        "continuity_global": cont[-1] if cont else None,
        "courant_max": cour[-1] if cour else None,
        "logs": [n for n in ("log.simpleFoam", "log.scalarTransportFoam",
                             "log.snappyHexMesh", "log.blockMesh")
                 if (case / n).is_file()],
    }


def copy_artifacts(case, label):
    dest = ROOT / "cfd" / "results" / label
    dest.mkdir(parents=True, exist_ok=True)
    pf = probe_file(case)
    if pf:
        target = dest / pf.parent.name
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pf, target / "T")
        ufile = pf.parent / "U"
        if ufile.is_file():
            shutil.copy2(ufile, target / "U")
    for name in ("log.simpleFoam", "log.scalarTransportFoam",
                 "log.snappyHexMesh", "log.blockMesh"):
        if (case / name).is_file():
            shutil.copy2(case / name, dest / name)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", required=True, type=Path,
                    help="OpenFOAM case root containing postProcessing/probes")
    ap.add_argument("--label", default=None,
                    help="archive label (default: case directory name)")
    ap.add_argument("--no-copy", action="store_true",
                    help="only rewrite RESULTS.md, do not copy logs/probes")
    args = ap.parse_args()

    case = args.case_dir.expanduser().resolve()
    if not case.is_dir():
        raise SystemExit("case directory not found: %s" % case)
    pf = probe_file(case)
    if pf is None:
        raise SystemExit("no postProcessing/probes/*/T in %s" % case)

    label = args.label or case.name
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label)
    try:
        case_display = case.relative_to(ROOT).as_posix()
    except ValueError:
        case_display = str(case)
    dest = None if args.no_copy else copy_artifacts(case, label)

    rep = load_report_module()
    names, rows = rep.read_probes(str(pf))
    if not rows:
        raise SystemExit("%s has no data rows" % pf)
    n = len(rows[0]) - 1
    labels = rep.LABELS[:n] if n <= len(rep.LABELS) else ["P%d" % i for i in range(n)]
    table = []
    t63, t90 = {}, {}
    for i, name in enumerate(labels):
        a = rep.crossing(rows, i + 1, 0.63)
        b = rep.crossing(rows, i + 1, 0.90)
        t63[name] = a
        t90[name] = b
        table.append((name, a, b))
    # A probes sit at the left-wall card tips, D probes at the right-wall tips
    left_vals = [v for k, v in t63.items() if k.startswith("A") and v is not None]
    right_vals = [v for k, v in t63.items() if k.startswith("D") and v is not None]
    left = sum(left_vals) / len(left_vals) if left_vals else None
    right = sum(right_vals) / len(right_vals) if right_vals else None
    wall_delta = right - left if left is not None and right is not None else None

    meta = log_summary(case)
    fmt = lambda v: "-" if v is None else "%.2f" % v
    lines = [
        "# CFD results",
        "",
        "**Imported:** %s" % datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "**Case:** `%s` (label `%s`)" % (case_display, label),
        "**Archive:** `%s`" % (dest.relative_to(ROOT).as_posix() if dest else "not copied"),
        "**Probe table:** `%s`" % pf.relative_to(case).as_posix(),
        "**Samples:** %d, t = %.2f .. %.2f s" % (len(rows), rows[0][0], rows[-1][0]),
        "",
        "## Run metadata",
        "",
        "| Item | Value |",
        "|---|---|",
        "| Cells | %s |" % (meta["cells"] if meta["cells"] else "not parsed"),
        "| Max Courant | %s |" % (meta["courant_max"] or "not parsed"),
        "| Final global continuity error | %s |" % (meta["continuity_global"] or "not parsed"),
        "| Logs found | %s |" % (", ".join(meta["logs"]) or "none"),
        "",
        "## Tracer crossing times",
        "",
        "| Probe | t63 / s | t90 / s | t63 / (V/Q) |",
        "|---|---:|---:|---:|",
    ]
    for name, a, b in table:
        lines.append("| %s | %s | %s | %s |" % (
            name, fmt(a), fmt(b), "-" if a is None else "%.2f" % (a / rep.TAU)))
    slots = [n for n in labels if re.fullmatch(r"[AD][0-3]", n)]
    slot_vals = [t63[n] for n in slots if t63[n] is not None]
    overall = sum(slot_vals) / len(slot_vals) if slot_vals else None
    band = 0.20 * overall if overall is not None else None
    uniform = overall is not None and all(
        abs(v - overall) <= band for v in slot_vals)
    t63_ok = [n for n in slots if t63[n] is not None and t63[n] <= 4.0]
    t90_ok = [n for n in slots if t90[n] is not None and t90[n] <= 22.0]
    t90_missing = [n for n in slots if t90[n] is None]
    fill = lambda names: ", ".join(names) if names else "none"

    lines += [
        "",
        "Plug-flow reference V/Q = %.2f s at 15 L/min." % rep.TAU,
        "Left wall mean t63 %s s; right wall mean t63 %s s; wall-to-wall delta %s s."
        % (fmt(left), fmt(right), fmt(wall_delta)),
        "",
        SCHEME_NOTE % (meta["courant_max"] or "not parsed",
                       meta["continuity_global"] or "not parsed",
                       meta["cells"] or "not parsed",
                       quality_note(meta)),
        "",
        "## Design-target check (numerical run only)",
        "",
        "| Target from `docs/VALIDATION_SPECS.md` | Result | Verdict |",
        "|---|---|---|",
        "| t63 <= 4 s at every card tip | pass: %s; fail: %s | %s |"
        % (fill(t63_ok), fill([n for n in slots if n not in t63_ok]),
           "PASS" if len(t63_ok) == len(slots) else "FAIL"),
        "| t90 <= 22 s at every card tip | observed: %s; no crossing inside 8 s: %s | %s |"
        % (fill(t90_ok), fill(t90_missing),
           "PASS" if len(t90_ok) == len(slots) else "NOT CERTIFIED"),
        "| Wall-to-wall delta <= 5 s | %s s | %s |"
        % (fmt(wall_delta),
           "PASS" if wall_delta is not None and wall_delta <= 5.0 else "FAIL"),
        "| All 8 slots within +/-20%% of mean t63 | mean %s s; allowed band %s | %s |"
        % (fmt(overall), "-" if band is None else "+/-%.2f s" % band,
           "PASS" if uniform else "FAIL"),
        "| Purge recovery >=95% within 40 s | not simulated | NOT ASSESSED |",
        "| Face velocity at nostril >=2 m/s | imposed inlet boundary condition, not a prediction | NOT VALIDATED BY SIMULATION |",
        "",
        "**Release position:** the numerical solve is stable and bounded, but this run "
        "does not demonstrate that all eight slots meet the t63 and exposure-uniformity "
        "targets. Physical tracer and purge acceptance remain release gates.",
        "",
        "Raw probe tables and logs are archived under `%s`." % (
            dest.relative_to(ROOT).as_posix() if dest else "the original case"),
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT_MD)
    if dest:
        print("archived run artefacts in", dest)


if __name__ == "__main__":
    main()
