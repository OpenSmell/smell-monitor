# Smell Monitor — Open-Source Digital Olfaction Hardware

**Status:** v1 architecture LOCKED (`docs/architecture.md` v1.0) — schematic v0.x, PCB layout in progress, enclosure pending.

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

- **16 sensor slots, sensor-agnostic:** 8 analog (4-pin, 5 V) + 8 digital (6-pin, 3.3 V I2C). MOX, MEMS, NDIR, electrochemical — if the electrical contract fits, it works.
- **Repeatable measurements:** active three-phase cycle (intake → hold → purge), cavity-recessed sensors, PTFE/glass gas-contacting chamber.
- **Defensible data:** 2× ADS1115 (16-bit ADC), SHT31 temp/humidity in the gas path, I2C mux (TCA9548A) so address collisions never happen.
- **Open:** KiCad source, LCSC-numbered BOM (1-stop PCBA), STL/STEP enclosure, firmware, manuals — all in this repo.

## Repository layout

```
smell-monitor/
├── docs/                    # Architecture spec, manual, assembly guide, figures
│   ├── architecture.md      # ← LOCKED decisions + rationale (read me first)
│   ├── manual.md            # End-user / printed manual
│   ├── assembly_guide.md    # Build + fabrication instructions
│   └── figures/             # Mermaid diagrams (.mmd)
├── electrical/
│   ├── smell_monitor_v0/    # KiCad project (schematic, PCB)
│   ├── bom.csv              # BOM with LCSC part numbers
│   └── README.md
├── mechanical/
│   ├── freecad/  step/  stl/
│   └── README.md
├── firmware/
│   ├── esp32/
│   └── README.md
└── README.md
```

## Quick links

1. **Read the spec first:** `docs/architecture.md`
2. **Build one:** `docs/assembly_guide.md`
3. **Use one:** `docs/manual.md`
4. **Order a board:** BOM + Gerbers (pending DRC/ERC-clean export) in `electrical/`

## Project status

- [x] Architecture locked — pneumatic, sensing, electrical, mechanical
- [x] Core schematic (v0) and BOM with alternatives
- [ ] ERC/DRC clean-up and review
- [ ] PCB layout + routing
- [ ] Enclosure CAD (FreeCAD) derived from routed board
- [ ] Firmware (three-phase cycle + serial protocol)
- [ ] Fabrication pass (Seeed Fusion / JLCPCB DC)
- [ ] CFD validation pass (optional, §8.3)

## Contributing

Open issues for hardware bugs or component suggestions. Contributions welcome per the licenses. If you identify a conflict between files and `docs/architecture.md`, the architecture doc wins until amended (see its versioning note).

## Licenses

- Hardware: **CERN-OHL-S**
- Firmware/software: **MIT**
- Documentation: **CC BY-SA 4.0**

## Community

OpenSmell · [github.com/OpenSmell](https://github.com/OpenSmell) · smell-monitor issues are monitored.