# CFD Notes — side-wall-v2 baseline

**Document:** OSM-CFD-NOTES-001
**Revision:** A
**Date:** 2026-11-26
**Companion files:** `cfd/RESULTS.md`, `docs/VALIDATION_PLAN.md`

## Numerical results

The stable OpenFOAM side-wall-v2-linux run at 15 L/min used 81,432 cells, reached
a maximum Courant number of 0.783 and closed at a global continuity error of
-5.65e-08.

| Probe group | t63 / s | Result against ≤ 4 s |
|---|---|---|
| A0, A3, D3 | 2.25, 0.65, 0.15 | 3 slots pass |
| A1, A2, D0, D1, D2 | 6.43, 6.42, 4.86, 5.83, 5.83 | 5 slots above target |

A0–A3 are the left-wall card tips (J2–J5); D0–D3 are the right-wall card tips
(J6–J9). Wall-to-wall mean t63 delta is 0.23 s. The ±20%-of-mean uniformity
criterion in `docs/VALIDATION_PLAN.md` §3 is not met in this solve. The 90%
crossing is recorded for A0, A3 and D3; the other probes do not reach a 90%
crossing inside the recorded tracer window.

## Acceptance

Physical tracer and purge acceptance is specified in `docs/VALIDATION_PLAN.md`
§3. Nostril geometry is unchanged after CFD review.

## Solver settings

| Setting | Value |
|---|---|
| `ddtSchemes` | `Euler` |
| `div(phi,T)` | `bounded Gauss limitedLinear 1` |
| `deltaT` | `4e-4 s` (Courant ≤ 0.8 at the inlet jets through 1 mm cells) |
| `endTime` | `8 s` |
| probe interval | `0.25 s` |
