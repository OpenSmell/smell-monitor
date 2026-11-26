# CFD results

**Baseline run:** `side-wall-v2-linux` — OpenFOAM side-wall v2 at 15 L/min,
geometry generated from `mechanical/constants.py`.

**Case:** `cfd` (label `sidewall-v2-linux`)  
**Archive:** `cfd/results/sidewall-v2-linux`  
**Probe table:** `postProcessing/probes/0/T`  
**Samples:** 20,000, t = 0.00 .. 8.00 s  
**Imported:** 2026-11-24 18:32 UTC

## Numerical evidence

| Check | Value | Criterion | Result |
|---|---:|---:|---|
| Cells | 81,432 | checkMesh: Mesh OK | recorded |
| Max Courant number (tracer) | 0.783166 | ≤ 1 | PASS |
| Final global continuity error | -5.64744e-08 | ≤ 1e-6 | PASS |
| Wall-to-wall t63 delta | 0.23 s | ≤ 5 s | PASS |

The tracer pass is transient (`Euler`, `deltaT = 4e-4 s`) on the converged steady
flow field, with the scalar discretised by `bounded Gauss limitedLinear 1`
(bounded, second-order TVD). At 15 L/min the inlet jets reach about 2 m/s through
1 mm cells, so the timestep holds Courant at or below 0.8. The empty-chamber
plug-flow reference is V/Q = 2.28 s. Built-unit acceptance is specified in
`docs/VALIDATION_SPECS.md` §3.

## Tracer crossing times

| Probe | t63 / s | t90 / s | t63 / (V/Q) | t63 check |
|---|---:|---:|---:|---|
| A0 (left wall) | 2.25 | 7.78 | 0.99 | PASS |
| A1 (left wall) | 6.43 | — | 2.83 | above 4 s |
| A2 (left wall) | 6.42 | — | 2.82 | above 4 s |
| A3 (left wall) | 0.65 | 5.19 | 0.29 | PASS |
| D0 (right wall) | 4.86 | — | 2.14 | above 4 s |
| D1 (right wall) | 5.83 | — | 2.56 | above 4 s |
| D2 (right wall) | 5.83 | — | 2.56 | above 4 s |
| D3 (right wall) | 0.15 | 3.06 | 0.07 | PASS |
| bypass | 3.48 | — | 1.53 | reference |
| outlet | 0.11 | 0.12 | 0.05 | reference |

A dash means no 90% crossing was observed inside the 8 s tracer window. A0–A3
are the left-wall card tips (J2–J5); D0–D3 are the right-wall tips (J6–J9).
Left-wall mean t63 is 3.94 s; right-wall mean t63 is 4.17 s.

## Acceptance summary

| Check | Result | Criterion |
|---|---:|---|
| t63 pass count | 3/8 | ≤ 4 s at every slot |
| t90 recorded | A0, A3, D3 | 90% crossing observed within the window |
| Wall-to-wall delta | 0.23 s (PASS) | ≤ 5 s |
| Slot uniformity | FAIL | all 8 slots within ±20% of mean t63 |
| Physical tracer/purge | `docs/VALIDATION_SPECS.md` §3 on a built unit | acceptance test |

The numerical solve is stable and bounded. Nostril geometry is unchanged after
CFD review.

## Solver settings

| Setting | Value | Reason |
|---|---|---|
| `ddtSchemes` | `Euler` | transient time-stepping |
| `div(phi,T)` | `bounded Gauss limitedLinear 1` | bounded, second-order, low diffusion |
| `deltaT` | `4e-4 s` | Courant ≤ 0.8 at the inlet jets through 1 mm cells |
| `endTime` | `8 s` | beyond the 2.28 s plug-flow reference |
| probe interval | `0.25 s` | resolves the breakthrough curve |

## Tuning candidates and priority

Nostril geometry is unchanged after CFD review; no tuned geometry is claimed.
Tuning is deferred until a re-solve and built-unit acceptance, in this order:

1. **Nostril count, position and angle** — first control over how the centred
   jets flood the two inward-facing rows.
2. **Baffles and flow guides** — candidate devices only, not part of the current
   chamber.
3. **Fan and straightener** — downstream field work after the inlet and guides
   are settled.
4. **Channel and card-reach changes** — last, because they alter the locked
   OSM-1 envelope.

## Run and import

```sh
cd cfd && bash run.sh
cd .. && python3 tools/import_cfd_report.py --case-dir cfd --label sidewall-v2-linux
```

`run.sh` builds the mesh, solves the steady flow, then steps a passive tracer on
the frozen field. Both runs are deterministic and derive their geometry from
`constants.py`. Add `--omit 3,6` to `run.sh` for the empty-slot interference
study. The importer rewrites this file from the parsed probe table and logs and
archives raw tables and logs under `cfd/results/<label>/`.
