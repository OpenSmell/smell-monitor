# CFD results

**Imported:** 2026-11-24 18:32 UTC
**Case:** `cfd` (label `sidewall-v2-linux`)
**Archive:** `cfd/results/sidewall-v2-linux`
**Probe table:** `postProcessing/probes/0/T`
**Samples:** 20000, t = 0.00 .. 8.00 s

## Run metadata

| Item | Value |
|---|---|
| Cells | 81432 |
| Max Courant | 0.783166 |
| Final global continuity error | -5.64744e-08 |
| Logs found | log.simpleFoam, log.scalarTransportFoam, log.snappyHexMesh, log.blockMesh |

## Tracer crossing times

| Probe | t63 / s | t90 / s | t63 / (V/Q) |
|---|---:|---:|---:|
| A0 | 2.25 | 7.78 | 0.99 |
| A1 | 6.43 | - | 2.83 |
| A2 | 6.42 | - | 2.82 |
| A3 | 0.65 | 5.19 | 0.28 |
| D0 | 4.86 | - | 2.14 |
| D1 | 5.83 | - | 2.56 |
| D2 | 5.83 | - | 2.56 |
| D3 | 0.15 | 3.06 | 0.07 |
| bypass | 3.48 | - | 1.53 |
| outlet | 0.11 | 0.12 | 0.05 |

Plug-flow reference V/Q = 2.28 s at 15 L/min.
Left wall mean t63 3.94 s; right wall mean t63 4.17 s; wall-to-wall delta 0.23 s.

## Numerical setup

The tracer pass is transient (`Euler`, `deltaT = 4e-4 s`) on the converged
steady flow field, with the scalar discretised by `bounded Gauss limitedLinear 1`
(TVD, bounded, second-order). At the imposed 15 L/min the inlet jets reach
~2 m/s through 1 mm cells, so `deltaT` holds the Courant number at or below 0.8.
The plug-flow reference for the empty chamber is V/Q = 2.28 s.

| Check | Value | Criterion |
|---|---:|---|
| Max Courant number (tracer) | 0.783166 | <= 1 |
| Final global continuity error | -5.64744e-08 | <= 1e-6 |
| Cell count | 81432 | checkMesh: Mesh OK |

**Numerical quality: PASS.** Max Courant 0.783 (limit 1); final global continuity -5.64744e-08. The tracer transient is resolved and bounded.


## Design-target check (numerical run only)

| Target from `docs/VALIDATION_SPECS.md` | Result | Verdict |
|---|---|---|
| t63 <= 4 s at every card tip | pass: A0, A3, D3; fail: A1, A2, D0, D1, D2 | FAIL |
| t90 <= 22 s at every card tip | observed: A0, A3, D3; no crossing inside 8 s: A1, A2, D0, D1, D2 | NOT CERTIFIED |
| Wall-to-wall delta <= 5 s | 0.23 s | PASS |
| All 8 slots within +/-20% of mean t63 | mean 4.05 s; allowed band +/-0.81 s | FAIL |
| Purge recovery >=95% within 40 s | not simulated | NOT ASSESSED |
| Face velocity at nostril >=2 m/s | imposed inlet boundary condition, not a prediction | NOT VALIDATED BY SIMULATION |

**Release position:** the numerical solve is stable and bounded, but this run does not demonstrate that all eight slots meet the t63 and exposure-uniformity targets. Physical tracer and purge acceptance remain release gates.

Raw probe tables and logs are archived under `cfd/results/sidewall-v2-linux`.
