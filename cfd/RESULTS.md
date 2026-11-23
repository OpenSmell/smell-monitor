# CFD results

**Case:** `cfd/` — OpenFOAM v10/v11, geometry generated from `mechanical/constants.py`.

**Status:** the corrected case (v2) is committed. Run it on Linux with one
command, then import the output with one command. The import writes the measured
t63/t90 table together with the achieved Courant number, continuity error and
cell count into this file, and archives the probe tables and logs under
`cfd/results/<label>/`.

## Run on Linux

```sh
cd cfd && bash run.sh
cd .. && python3 tools/import_cfd_report.py --case-dir cfd --label linux-run
```

`run.sh` builds the mesh, solves the steady flow, then steps a passive tracer on
the frozen field. Both runs are deterministic and derive their geometry from
`constants.py`. Add `--omit 3,6` to `run.sh` for the empty-slot interference
study.

## What changed in v2

The v1 tracer pass used `ddtSchemes steadyState` with `Gauss upwind` at
`deltaT = 0.02 s`. That is a discretisation error, not a result: steady ddt
removes the time derivative and upwind at Courant ≈ 40 diffuses the scalar
across cells in one step. The reported t63/t90 ≈ 0.02 s was the signature of
that error and is superseded.

v2 uses:

| Setting | Value | Reason |
|---|---|---|
| `ddtSchemes` | `Euler` | real transient time-stepping |
| `div(phi,T)` | `bounded Gauss limitedLinear 1` | bounded, second-order, low diffusion |
| `deltaT` | `4e-4 s` | Courant ≤ 0.8 at the 2 m/s inlet jets through 1 mm cells |
| `endTime` | `8 s` | well beyond the 1.72 s plug-flow reference |
| probe interval | `0.25 s` | resolves the breakthrough curve |

The importer rejects a run whose logged max Courant exceeds 1, so a bad solve
cannot be committed as a good result.
