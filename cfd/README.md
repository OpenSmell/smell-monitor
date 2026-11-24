# CFD — the v1.1 chamber

Three questions, one case:

1. **Exchange time.** How long does the gas at each side-wall card take to be
   replaced through the 4.9 mm hood?
2. **Uniformity.** Do the three centred nostrils flood both inward-facing rows
   evenly, or does one bank see fresher sample?
3. **Interference.** Does a cartridge plugged into one slot disturb the flow
   over its neighbours?

The geometry is generated from `mechanical/constants.py` and
`mechanical/standard.py`, so the mesh cannot drift from the enclosure.

**Run status and exact commands:** see `cfd/RESULTS.md`.

## Run

OpenFOAM v10 (openfoam.com) or v11, on Linux:

```sh
cd cfd
bash run.sh                    # 8 slots filled - the reference build
bash run.sh --omit 3,6         # leave slots 3 and 6 empty, for question 3
```

`run.sh` meshes (`blockMesh` → `topoSet` → `createPatch` → `snappyHexMesh`),
runs `simpleFoam`, then runs `scalarTransportFoam` on the frozen field and
prints `report.py`. Logs are `log.*`.

## What it solves

| | |
|---|---|
| Domain | the tray cavity above the board: 116 × 108 × 45.4 mm |
| Mesh | 2 mm hex background, 1 mm on sockets, cartridges and bosses; ~0.3 M cells |
| Flow | incompressible, steady, k-ω SST, no-slip on every solid |
| Inlet | 3 patches, 15 L/min total (`flowRateInletVelocity`) |
| Outlet | fixed p = 0 on a 38 × 38 mm patch in the fan bore |
| Filter | Darcy–Forchheimer sink in the 4 mm pad slab (`constant/fvOptions`) |
| Tracer | unit step at the inlets, `scalarTransportFoam`, 0.02 s steps |

`report.py` prints t63 and t90 at eight probe points at the inward tip of each
upright card (z = 33 mm, the sensing band), plus a probe under the filter pad
and one near the outlet.

## Idealisations, and why they are acceptable

* **The nostrils are 6 × 6 mm squares, not Ø6 circles.** A box mesh cannot cut
  a round hole on a face without a much heavier mesh. The total flow is imposed,
  so the jet velocity is ~21 % low (area 36 mm² vs 28 mm²). A slower jet spreads
  less, so the mixing this reports is a floor, not a ceiling.
* **The outlet is a 38 × 38 mm square, not Ø38.** 21 % more area; the real bore
  is rounded, which is kinder to the flow than a square.
* **The fan is not a curve.** The operating point is imposed as a flow rate, so
  the inlet pressure the case reports *is* the system ΔP at that flow. Compare
  it with the NF1 bench (blueprint §3.8).
* **The pad is a porous sink, not a fibre structure.** `d = 7e7 1/m²`
  corresponds to ~3 Pa at 0.6 m/s; that is the one number a bench measurement
  should replace.
* **Cartridges are boxes.** Each is modelled as a 20 × 32 mm upright panel on a
  side wall reaching 21 mm into the channel. The real can, its mesh cap and its
  header are smaller than the OSM-1 envelope, so the blockage is conservative.

The bulk flow is laminar at 15 L/min (Re ≈ 220 on the cavity's hydraulic
diameter); the three inlet jets are not (Re ≈ 3 500 each). k-ω SST is used
because the flush case at 150 L/min is transitional, and because the jets are
the part of this flow that is definitely turbulent. For the 15 L/min purge the
result is effectively a laminar solution.

## Reading the result

* **t63 per wall.** If the two walls' t63 differ by more than ~1 s, the inlet
  pattern is uneven and every record has to carry the slot's wall — which it does
  (`slot_index` identifies one of the eight wall stations).
* **t63 vs V/Q.** V/Q = 2.28 s for the empty chamber. A wall that comes out at
  3–4× that is sitting in a recirculation, not in the stream.
* **Under-pad probe.** If it fills faster than the cards, the slot below the
  filter is a bypass and the drawer needs its bottom gap closed. That is a
  ten-minute change to `constants.py`, not a redesign.
* **The 4.9 mm gap.** The card top is 4.9 mm under the lid. If t63 there is
  poor, the fix is 6 mm more wall (`CH` 51 → 57), not a new pose: the upright
  inward-facing card is right, the hood over it is what is short.

## Numerical quality

The tracer pass is transient (`Euler`) with a bounded second-order scalar
scheme (`bounded Gauss limitedLinear 1`) and `deltaT = 4e-4 s`, which holds the
Courant number at or below 0.8 at the inlet jets. `tools/import_cfd_report.py`
records the achieved Courant number and continuity error alongside t63/t90 and
rejects a run above Courant 1. The v1 result of ≈ 0.02 s came from a steady-state
ddt scheme and upwind advection at Courant ≈ 40; it was a discretisation error
and has been superseded.

## Changing the flow

Edit `0/U` (all three inlets, `volumetricFlowRate`, m³/s per inlet) and rerun.
15 L/min is the design purge; 150 L/min is the flush case in blueprint §2.
