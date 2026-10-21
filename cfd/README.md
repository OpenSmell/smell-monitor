# CFD — the v1.1 chamber

Three questions, one case:

1. **Exchange time.** How long does the gas over each row take to be replaced?
2. **Cascade.** How much of the sample does the upstream row remove before the
   downstream row sees it?
3. **Interference.** Does a cartridge plugged into one slot disturb the flow
   over its neighbours?

The geometry is generated from `mechanical/constants.py` and
`mechanical/standard.py`, so the mesh cannot drift from the enclosure.

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
| Domain | the tray cavity above the board: 116 × 108 × 34.4 mm |
| Mesh | 2 mm hex background, 1 mm on sockets, cartridges and bosses; ~0.3 M cells |
| Flow | incompressible, steady, k-ω SST, no-slip on every solid |
| Inlet | 3 patches, 15 L/min total (`flowRateInletVelocity`) |
| Outlet | fixed p = 0 on a 34 × 30 mm patch in the fan bore |
| Filter | Darcy–Forchheimer sink in the 4 mm pad slab (`constant/fvOptions`) |
| Tracer | unit step at the inlets, `scalarTransportFoam`, 0.02 s steps |

`report.py` prints t63 and t90 at eight probe points in the 4.9 mm gap over each
cartridge, plus a probe under the filter pad and one near the outlet.

## Idealisations, and why they are acceptable

* **The nostrils are 6 × 6 mm squares, not Ø6 circles.** A box mesh cannot cut
  a round hole on a face without a much heavier mesh. The total flow is imposed,
  so the jet velocity is ~21 % low (area 36 mm² vs 28 mm²). A slower jet spreads
  less, so the mixing this reports is a floor, not a ceiling.
* **The outlet is 34 × 30 mm, not Ø38.** 9 % less area; the real bore is
  rounded, which is kinder to the flow than a square.
* **The fan is not a curve.** The operating point is imposed as a flow rate, so
  the inlet pressure the case reports *is* the system ΔP at that flow. Compare
  it with the NF1 bench (blueprint §3.8).
* **The pad is a porous sink, not a fibre structure.** `d = 7e7 1/m²`
  corresponds to ~3 Pa at 0.6 m/s; that is the one number a bench measurement
  should replace.
* **Cartridges are boxes.** The real can, its mesh cap and its header are
  smaller than the OSM-1 envelope, so the blockage here is conservative.

The bulk flow is laminar at 15 L/min (Re ≈ 220 on the cavity's hydraulic
diameter); the three inlet jets are not (Re ≈ 3 500 each). k-ω SST is used
because the flush case at 150 L/min is transitional, and because the jets are
the part of this flow that is definitely turbulent. For the 15 L/min purge the
result is effectively a laminar solution.

## Reading the result

* **t63 per row.** If the two rows' t63 differ by more than ~1 s, the cascade is
  real and every record has to carry the slot's flow position — which it does
  (`slot_index` and `flow_position` in the record).
* **t63 vs V/Q.** V/Q = 1.72 s for the empty chamber. A row that comes out at
  3–4× that is sitting in a recirculation, not in the stream.
* **Under-pad probe.** If it fills faster than the first row, the slot below the
  filter is a bypass and the drawer needs its bottom gap closed. That is a
  ten-minute change to `constants.py`, not a redesign.
* **The 4.9 mm gap.** The sensing face is 4.9 mm under the lid. If t63 there is
  poor, the fix is 6 mm more wall (`CH` 40 → 46), not a new pose: the flat
  cartridge is right, the hood over it is what is short.

## Changing the flow

Edit `0/U` (all three inlets, `volumetricFlowRate`, m³/s per inlet) and rerun.
15 L/min is the design purge; 150 L/min is the flush case in blueprint §2.
