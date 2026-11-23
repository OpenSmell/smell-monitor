# CFD run status

**Case:** `cfd/` (OpenFOAM v10/v11, generated from `mechanical/constants.py`)

**Status:** the case has been run on Linux. Raw `postProcessing/` output and
`log.*` files were **not committed** to this repository, so there is no machine
readable report here yet. The surviving numerical note is in `cfd/README.md`.

## What the run established

* The sample path is open: three inlets -> woven-PTFE filter -> eight uniform
  sockets -> rear fan. `cfd/README.md` records max inlet velocity ~2 m/s at
  15 L/min and continuity residual ~1e-9.
* The simulated tracer jumps cells almost immediately: t63/t90 ~0.02 s at every
  probe, against a plug-flow reference V/Q = 1.72 s.

## What the run did not establish

Those t63/t90 numbers are **not physical exchange times**. At 2 m/s through a
1 mm cell the Courant number is O(10-20), and `Gauss upwind` adds numerical
diffusion, so the scalar reaches 63 % by diffusion rather than advection. Do not
use 0.02 s to size a timing cycle or to claim a row-to-row cascade. The physical
flow bench in `docs/VALIDATION_PLAN.md` is the gate for real exchange times.

## Import a real run

If the Linux run output is still available:

```sh
python tools/import_cfd_report.py --case-dir /path/to/OpenFOAM/case --label linux-run
```

The script copies the probe tables and logs into `cfd/results/<label>/` and
rewrites this file with the parsed t63/t90 table, the run metadata, and the same
limitation note. Re-run the gates listed in `docs/VALIDATION_PLAN.md` afterwards.

Without that import, this file is the authoritative status: **run performed,
raw results not in repo, physical timing validation still open**.
