# mechanical/

Enclosure and chamber CAD for the Smell Monitor v1.

## Layout principle (see `docs/architecture.md §6`)

Front **sensing module** (PTFE/glass cavity, intake, baffle) separated from the rear **service bay** (MCU, power, display, fan exhaust) by a PCB-sealing bulkhead.

## Status

- [ ] Outer shell (cosmetic — PLA/PETG print acceptable)
- [ ] **PTFE chamber insert** (gas-contacting — must NOT be plain plastic; machine or liner)
- [ ] Perforated sensor baffle (recesses sensing elements ~8 mm below flow core)
- [ ] PTFE filter retainer (2× Ø5 mm intakes)
- [ ] Rear fan mount (Ø40 mm, exhaust)
- [ ] Bulkhead/gasket for PCB seal

Derive enclosure dimensions from the **routed** PCB outline (target 120 × 70 mm) — not the reverse.

## Design targets — chamber cavity

90 × 55 × 24 mm internal (≈119 cm³) · header pitch 17.5 mm · rows 40 mm apart · all internal corners radius ≥ 3 mm · single front-to-rear air pass.

## Outputs eventually placed here

- `freecad/` — editable assemblies (.FCStd)
- `step/` — STEP for fabrication (machined PTFE + sheet metal)
- `stl/` — STL for printing the cosmetic shell