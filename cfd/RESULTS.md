# CFD results

**Baseline run:** `side-wall-v2-linux` — OpenFOAM side-wall v2 at 15 L/min,
geometry generated from `mechanical/constants.py`.

**Case:** `cfd/` — OpenFOAM v10/v11.

## Numerical evidence (side-wall-v2-linux)

| Check | Value | Criterion | Result |
|---|---:|---:|---|
| Cells | 81,432 | mesh resolved from constants | recorded |
| Max Courant number (tracer) | 0.783 | ≤ 1 | PASS |
| Final global continuity error | -5.65e-08 | ≤ 1e-6 | PASS |
| Wall-to-wall t63 delta | 0.23 s | ≤ 5 s | PASS |

The tracer pass is transient (`Euler`, `deltaT = 4e-4 s`) on the converged steady
flow field, with the scalar discretised by `bounded Gauss limitedLinear 1`
(bounded, second-order TVD). At the imposed 15 L/min the inlet jets reach about
2 m/s through 1 mm cells, so the timestep holds Courant at or below 0.8. The
empty-chamber plug-flow reference is V/Q = 2.28 s. Physical acceptance is
specified in `docs/VALIDATION_PLAN.md` §3.

## Tracer crossing times

| Probe | t63 / s | t63 ≤ 4 s | t90 | t63 / (V/Q) |
|---|---:|---|---|---:|
| A0 (left wall) | 2.25 | PASS | 7.78 | 0.99 |
| A1 (left wall) | 6.43 | above target | — | 2.82 |
| A2 (left wall) | 6.42 | above target | — | 2.82 |
| A3 (left wall) | 0.65 | PASS | 5.19 | 0.29 |
| D0 (right wall) | 4.86 | above target | — | 2.13 |
| D1 (right wall) | 5.83 | above target | — | 2.56 |
| D2 (right wall) | 5.83 | above target | — | 2.56 |
| D3 (right wall) | 0.15 | PASS | 3.06 | 0.07 |

A dash means no 90% crossing was observed inside the recorded tracer window;
A0, A3 and D3 are the recorded probes. Slots are labelled A0–A3 (left wall,
J2–J5) and D0–D3 (right wall, J6–J9).

## Acceptance summary

| Check | Result | Criterion |
|---|---:|---|
| t63 pass count | 3/8 | ≤ 4 s at every slot |
| t90 recorded | A0, A3, D3 | 90% crossing observed |
| Wall-to-wall delta | 0.23 s (PASS) | ≤ 5 s |
| Slot uniformity | FAIL | all 8 slots within ±20% of mean t63 |
| Physical tracer/purge | `docs/VALIDATION_PLAN.md` §3 on a built unit | release acceptance |

Nostril geometry is unchanged after CFD review.

## Solver settings

| Setting | Value | Reason |
|---|---|---|
| `ddtSchemes` | `Euler` | transient time-stepping |
| `div(phi,T)` | `bounded Gauss limitedLinear 1` | bounded, second-order, low diffusion |
| `deltaT` | `4e-4 s` | Courant ≤ 0.8 at the inlet jets through 1 mm cells |
| `endTime` | `8 s` | beyond the 2.28 s plug-flow reference |
| probe interval | `0.25 s` | resolves the breakthrough curve |

## Run and import

```sh
cd cfd && bash run.sh
cd .. && python3 tools/import_cfd_report.py --case-dir cfd --label linux-run
```

`run.sh` builds the mesh, solves the steady flow, then steps a passive tracer on
the frozen field. Both runs are deterministic and derive their geometry from
`constants.py`. Add `--omit 3,6` to `run.sh` for the empty-slot interference
study. The importer rewrites this file from the parsed probe table and logs and
archives raw probe tables and logs under `cfd/results/<label>/`.

The importer rejects a run whose logged max Courant exceeds 1.
