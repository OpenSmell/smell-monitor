# Smell Monitor — Open-Source Digital Olfaction Hardware

**Status:** Design locked and consolidated in the single source of truth — **`docs/blueprint.md`** (OS-BP-001). Model + HLR drawing set produced (`mechanical/`); schematic v0.x; PCB layout, firmware and enclosure pending.

The Smell Monitor is an open-source, modular, sensor-agnostic electronic nose. It is a low-cost (~$50–150 BOM), reproducible acquisition platform for anyone doing digital olfaction — researchers, labs, and makers who can't justify $10k–100k commercial e-nose systems.

**You** choose the sensors. **It** supplies the repeatable pneumatic environment, clean power, 16-bit acquisition, and logged temperature/humidity to make their outputs comparable.

## Why it's different from incumbents

| | Smell Monitor | Commercial e-noses |
|---|---|---|
| Price | ~$50–150 BOM | $8k–100k+ |
| Architecture | Open, modular, sensor-agnostic | Closed, proprietary |
| Sensors | You plug in whatever fits a slot | Vendor-locked array |
| Users | Researchers, makers, small business | Large enterprise / regulated QC |

We're not competing on certified precision. We're building the *Arduino of noses* — an ecosystem of sensors, packs, software, and shared datasets.

## Key features

- **16 sensor slots, sensor-agnostic:** 8 analog (5-pin: 5 V + 3 V3 + GND + AO + DO) + 8 digital (6-pin, 3.3 V I2C). MOX, MEMS, NDIR, electrochemical, piezo, QCM — if the electrical contract fits, it works.
- **Repeatable measurements:** active three-phase cycle (intake → hold → purge), cavity-recessed sensors, PTFE/glass gas-contacting chamber.
- **Defensible data:** 2× ADS1115 (16-bit ADC), SHT31 temp/humidity in the gas path, I2C mux (TCA9548A) so address collisions never happen.
- **Open:** KiCad source, LCSC-numbered BOM (1-stop PCBA), STL/STEP enclosure, firmware, manuals — all in this repo.

## Repository layout

```
smell-monitor/
├── docs/
│   └── blueprint.md         # ← THE single source of truth: objective, design,
│                            #   verification, BOM, assembly, manual, drawings
├── electrical/
│   ├── smell_monitor_v0/    # KiCad project (schematic v0.x, PCB in progress)
│   ├── bom.csv              # BOM with LCSC part numbers
│   └── README.md
├── mechanical/
│   ├── constants.py         # locked parametric dimensions (single source)
│   ├── freecad/             # parametric 3D model (build + style scripts)
│   ├── drawings/            # DXF/PDF sheet generation
│   └── README.md
├── firmware/
│   └── README.md            # firmware requirements (see blueprint §7)
├── tools/
│   └── verify_cad.py        # numeric CAD gate
└── README.md
```

## Quick links

1. **Read the blueprint:** `docs/blueprint.md` — objective & success criteria (§0), design (§1–7), verification (§8)
2. **Build one:** `docs/blueprint.md` §9 (BOM) → §10 (assembly)
3. **Use one:** `docs/blueprint.md` §11 (user manual)
4. **Order a board:** BOM + Gerbers (pending ERC/DRC-clean export) in `electrical/`

## Project status

- [x] Objective & success criteria locked (blueprint §0)
- [x] Architecture locked — pneumatic, sensing, electrical, mechanical (blueprint §1–7)
- [x] Volume model (FreeCAD, `mechanical/freecad/`)
- [x] Core schematic (v0) and BOM with alternatives
- [x] Drawing set — real HLR views → editable DXF + vector PDF (blueprint §12)
- [ ] Electrical sheet OS-003 (PCB floor plan) + pneumatic sheet OS-004
- [ ] ERC/DRC clean-up and review
- [ ] PCB layout + routing
- [ ] Enclosure CAD derived from routed board
- [ ] Firmware (three-phase cycle + serial protocol)
- [ ] Fabrication pass (Seeed Fusion / JLCPCB)
- [ ] CFD validation pass (optional, blueprint §8.3)

## Contributing

Open issues for hardware bugs or component suggestions. Contributions welcome per the licenses. If you identify a conflict between files and `docs/blueprint.md`, the blueprint wins until deliberately amended (see its traceability note and revision history).

## Licenses

- Hardware: **CERN-OHL-S**
- Firmware/software: **MIT**
- Documentation: **CC BY-SA 4.0**

## Community

OpenSmell · [github.com/OpenSmell](https://github.com/OpenSmell) · smell-monitor issues are monitored.