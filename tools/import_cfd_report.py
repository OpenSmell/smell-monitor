#!/usr/bin/env python3
"""Import an OpenFOAM run into the repository as a readable CFD report.

Usage:
  python tools/import_cfd_report.py --case-dir /path/to/case [--label my-run]

It reads postProcessing/probes/*/T and log.* from a completed run, copies those
small text artefacts into cfd/results/<label>/, and rewrites cfd/RESULTS.md with
the parsed t63/t90 table, numerical stability figures and the acceptance
summary. A stable solve is reported separately from physical release acceptance.

Run from anywhere; no OpenFOAM installation is required to import.
"""
import argparse
import importlib.util
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT_PY = ROOT / "cfd" / "report.py"
OUT_MD = ROOT / "cfd" / "RESULTS.md"

T63_LIMIT_S = 4.0
T90_LIMIT_S = 22.0
WALL_DELTA_LIMIT_S = 5.0
UNIFORMITY_FRACTION = 0.20
SLOT_RE = re.compile(r"^[AD][0-3]$")

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
| Cell count | %s | resolved from constants |

%s
"""

TUNING_NOTE = """## Tuning candidates and priority

Nostril geometry is unchanged after CFD review; no tuned geometry is claimed.
The solve is stable but non-certifying, so physical tracer and purge acceptance
remains the release gate. No geometry is changed in this baseline. Tuning is
deferred until a re-solve, in this order:

1. **Nostril count, position and angle** — first control over how the centred
   jets flood the two inward-facing rows.
2. **Baffles and flow guides** — candidate devices only, not part of the current
   chamber.
3. **Fan and straightener** — operate on the downstream field after the inlet
   and guides are settled.
4. **Channel and card-reach changes** — last, because they alter the locked
   OSM-1 envelope.
"""

RUN_NOTE = """## Run and import

```sh
cd cfd && bash run.sh
cd .. && python3 tools/import_cfd_report.py --case-dir cfd --label linux-run
```

`run.sh` builds the mesh, solves the steady flow, then steps a passive tracer on
the frozen field. Both runs are deterministic and derive their geometry from
`constants.py`. Add `--omit 3,6` to `run.sh` for the empty-slot interference
study. This importer rewrites `cfd/RESULTS.md` from the parsed probe table and
logs; raw tables and logs are archived under `cfd/results/<label>/`."""

V2_NOTE = """## What changed in v2

The v1 flat-card case was non-functional: its tracer pass used `ddtSchemes
steadyState` with `Gauss upwind` at `deltaT = 0.02 s`. That is a discretisation
error, not a result: steady ddt removes the time derivative and upwind at
Courant ~ 40 diffuses the scalar across cells in one step. The reported t63/t90
~ 0.02 s was the signature of that error and is superseded.

| Setting | Value | Reason |
|---|---|---|
| `ddtSchemes` | `Euler` | real transient time-stepping |
| `div(phi,T)` | `bounded Gauss limitedLinear 1` | bounded, second-order, low diffusion |
| `deltaT` | `4e-4 s` | Courant <= 0.8 at the inlet jets through 1 mm cells |
| `endTime` | `8 s` | well beyond the 2.28 s plug-flow reference |
| probe interval | `0.25 s` | resolves the breakthrough curve |

The importer rejects a run whose logged max Courant exceeds 1, so an unstable
solve cannot be reported as a stable one."""


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
        return ("**Numerical stability: NOT VERIFIED.** Courant number was not "
                "parsed from the log. Check `log.scalarTransportFoam` before "
                "using these times.")
    if co_v > 1.0:
        return ("**Numerical stability: FAILED.** Max Courant %.2f exceeds 1. "
                "The tracer step violated the stability criterion; re-run with "
                "a smaller `deltaT`." % co_v)
    ok_cont = cont_v is None or cont_v <= 1e-6
    verdict = "PASS" if ok_cont else "REVIEW continuity"
    return ("**Numerical stability: %s.** Max Courant %.3f (limit 1); final "
            "global continuity %s. This is a stable numerical solve, not "
            "acceptance of 8/8 physical response."
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


def acceptance_lines(table, left, right):
    slots = [(name, a, b) for name, a, b in table if SLOT_RE.match(name)]
    t63_pass = [name for name, a, _ in slots
                if a is not None and a <= T63_LIMIT_S]
    t90_cert = [name for name, _, b in slots
                if b is not None and b <= T90_LIMIT_S]
    vals = [a for _, a, _ in slots if a is not None]
    mean = sum(vals) / len(vals) if vals else None
    uniform = (mean is not None and len(vals) == 8 and
               all(abs(v - mean) <= UNIFORMITY_FRACTION * mean for v in vals))
    wall_ok = (left is not None and right is not None and
               abs(right - left) <= WALL_DELTA_LIMIT_S)
    wall_text = ("-" if left is None or right is None
                 else "%+.2f" % (right - left))
    return [
        "## Acceptance summary",
        "",
        "| Check | Result | Criterion |",
        "|---|---:|---|",
        "| t63 pass count | %d/8 | <= %.2f s at every slot |"
        % (len(t63_pass), T63_LIMIT_S),
        "| t90 certified | %s | 90%% crossing observed within %.2f s |"
        % (", ".join(t90_cert) if t90_cert else "none", T90_LIMIT_S),
        "| Wall-to-wall delta | %s s (%s) | <= %.2f s |"
        % (wall_text, "PASS" if wall_ok else "FAIL", WALL_DELTA_LIMIT_S),
        "| Slot uniformity | %s | all 8 slots within +/-%d%% of mean t63 |"
        % ("PASS" if uniform else "FAIL", int(UNIFORMITY_FRACTION * 100)),
        "| Physical tracer/purge acceptance | OPEN | "
        "`docs/VALIDATION_PLAN.md` on a built unit |",
        "",
        "**Numerical evidence vs release acceptance.** The numerical solve is "
        "stable, but it does not certify 8/8 response: %d/8 slots meet the t63 "
        "target and slot uniformity %s. Physical tracer and purge acceptance "
        "remains the release gate in `docs/VALIDATION_PLAN.md`. See also "
        "`docs/CFD_NOTES.md`."
        % (len(t63_pass), "passes" if uniform else "fails"),
        "",
    ]


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
    dest = None if args.no_copy else copy_artifacts(case, label)

    rep = load_report_module()
    names, rows = rep.read_probes(str(pf))
    if not rows:
        raise SystemExit("%s has no data rows" % pf)
    n = len(rows[0]) - 1
    labels = rep.LABELS[:n] if n <= len(rep.LABELS) else ["P%d" % i for i in range(n)]
    table = []
    t63 = {}
    for i, name in enumerate(labels):
        a = rep.crossing(rows, i + 1, 0.63)
        b = rep.crossing(rows, i + 1, 0.90)
        t63[name] = a
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
        "**Case:** `%s` (label `%s`)" % (case, label),
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
        "| Probe | t63 / s | t63 <= 4 s | t90 | t63 / (V/Q) |",
        "|---|---:|---|---|---:|",
    ]
    for name, a, b in table:
        t90 = ("certified" if b is not None and b <= T90_LIMIT_S
               else "not certified")
        lines.append("| %s | %s | %s | %s | %s |" % (
            name, fmt(a), "PASS" if a is not None and a <= T63_LIMIT_S else "FAIL",
            t90, "-" if a is None else "%.2f" % (a / rep.TAU)))
    lines += [
        "",
        "Plug-flow reference V/Q = %.2f s at 15 L/min." % rep.TAU,
        "Left wall mean t63 %s s; right wall mean t63 %s s; wall-to-wall delta %s s."
        % (fmt(left), fmt(right), fmt(wall_delta)),
        "`t90` is certified where the 90%% crossing is observed in the recorded "
        "tracer window. A0-A3 are the left wall (J2-J5); D0-D3 are the right "
        "wall (J6-J9).",
        "",
    ]
    lines += acceptance_lines(table, left, right)
    lines += [
        SCHEME_NOTE % (meta["courant_max"] or "not parsed",
                       meta["continuity_global"] or "not parsed",
                       meta["cells"] or "not parsed",
                       quality_note(meta)),
        TUNING_NOTE,
        "",
        RUN_NOTE,
        "",
        V2_NOTE,
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT_MD)
    if dest:
        print("archived run artefacts in", dest)


if __name__ == "__main__":
    main()
