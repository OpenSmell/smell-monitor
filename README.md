# Smell Monitor — Open-Source Digital Olfaction Hardware

**Status:** Design locked and consolidated in the single source of truth — **`docs/blueprint.md`** (OS-BP-001). Schematic ERC-clean, PCB placed + routed + **DRC-clean** (reproducible pipeline), firmware compiling, model + HLR drawing set produced. The module interface is fixed by **`docs/module-standard.md`** (OpenSmell Module Standard v1, OSM-1, blueprint §4.9); the board in the tree is still the revision that predates it, and `tools/verify_module_fit.py` prints every remaining gap as an open item.

**One blocking mechanical defect is open:** the shell is modelled as a sealed box
— 30 mm of material over the chamber, no lid and no service opening — so it
cannot be printed, assembled or serviced as drawn. Blueprint §14 records the
measurement, the cause and the fix.

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

- **8 identical, sensor-agnostic slots:** every slot carries a keyed 5 V gas-cell socket (`+5V GND AO DO 3V3 ID`, the `ID` pin being a 1-Wire EEPROM that says what the module is and carries its calibration) *and* a 3.3 V Qwiic/STEMMA QT port. MOX, MEMS, NDIR, electrochemical, piezo, QCM — plug in whatever the use case needs, in any mix, in any slot. The socket, the flat cartridge envelope, the identity memory map and the wetted-material rules are the [OpenSmell Module Standard v1](docs/module-standard.md); rewiring the current board to it is revision L.
- **Repeatable measurements:** active three-phase cycle (intake → hold → purge), cavity-recessed sensors, PTFE/glass gas-contacting chamber.
- **Defensible data:** 16-bit ADC (ADS1115), SHT31 temp/humidity in the gas path, I2C mux (TCA9548A) so address collisions never happen.
- **Open:** KiCad source, BOM, STL/STEP enclosure, firmware, verification gates — all in this repo. (Part numbers: `electrical/bom.csv` is designator/value/footprint/qty; supplier PNs are still an open item.)

## How it works, in one paragraph

Air is pulled through three Ø6 nostrils, through a filter that spans the full
width of the duct, along an 11 mm lane, and down through eight 20 × 20 mm
windows — one per slot — into the sealed volume under the baffle plate, then out
through a 40 mm fan. Each window sits over one module's sensing face, so every
sensor sees the same sample at the same time, at a known flow position (digital
row upstream, the hot MOX row last). The board is the chamber floor and a PTFE
insert covers all of it except the eight sensor windows and the reference port,
so the air touches PTFE, borosilicate and 316 stainless only. Readings stay
comparable because the cycle is driven (intake → hold → purge) and every record
carries slot index, flow position, temperature, humidity, and the module's
identity and calibration from its 1-Wire EEPROM.

## What it costs

Indicative one-off prices in USD (Oct 2026). The gates check geometry and nets,
not prices.

| Item | ~ |
|---|---|
| PCB, 114 × 105 mm, 2-layer, 5 pcs | $3 |
| Board parts: ESP32-WROOM, ADC, I²C mux, LDO, passives, connectors | $16 |
| 8 × keyed 1×6 gas-cell sockets + 8 × Qwiic ports | $4 |
| SHT31 reference module | $4 |
| 40 mm 5 V PWM fan | $6 |
| Filter media (pleated pack) | $4 |
| PETG + PTFE stock | $8 |
| M3 thumb screws + heat-set inserts | $3 |
| **Base, no sensors** | **≈ $48** |
| Starter pack: MQ-135, MQ-136, MICS-6814 carrier, ZE03-C2H4, SCD40 | $60–110 |

## Repository layout

```
smell-monitor/
├── docs/
│   ├── blueprint.md         # ← THE single source of truth: objective, design,
│   │                        #   verification, BOM, assembly, manual, drawings,
│   │                        #   decision record (§15)
│   └── module-standard.md   # OpenSmell Module Standard v1 (OSM-1): the slot,
│                            #   pinouts, cartridge envelope, ID EEPROM, materials
├── electrical/
│   ├── interface.py         # the frozen slot contract (schematic+PCB+firmware)
│   ├── board.py             # parts + nets (netlist source of truth)
│   ├── gen_schematic.py     #   -> KiCad schematic (ERC-clean)
│   ├── gen_pcb.py           #   -> placed board (--force-guarded)
│   ├── route_pcb.py         #   -> DSN / FreeRouting / SES auto-route
│   ├── bom.csv              # designator, value, footprint, qty
│   └── smell_monitor_v1_1/  # KiCad project + routed board + fab/ export
├── mechanical/
│   ├── constants.py         # locked parametric dimensions (single source)
│   ├── standard.py          # the OSM-1 module rules as data (gates read this)
│   ├── modules.py           # what the market actually sells, with sources
│   ├── freecad/             # parametric 3D model (build + style scripts)
│   └── drawings/            # DXF/PDF sheet generation
├── firmware/esp32/smell_monitor/   # ESP32 firmware (arduino-cli, sketch.yaml)
├── tools/                   # numeric verification gates (see below)
└── README.md
```

Every claim above is checked by a gate that must exit 0 — there are no
hand-verified numbers:

| Gate | Checks |
|---|---|
| `tools/verify_electrical.py` | slot contract ↔ geometry ↔ GPIO/pin budget |
| `tools/verify_netlist.py` | model netlist == exported schematic netlist |
| `tools/verify_pcb.py` | headers on contract, outline, track width, vias, 0 unconnected, DRC |
| `tools/verify_cad.py` | HLR views, baffle wells, DXFs, vector A3 PDF, print meshes |
| `tools/verify_sensor_matrix.py` | starter pack covers every persona |
| `tools/verify_orthogonality.py` | response-matrix rank / slot-count trade study |
| `tools/verify_firmware_pins.py` | firmware pin map == `interface.PINMAP` |
| `tools/verify_module_fit.py` | real plug-in modules vs the chamber, and the chamber vs the OSM-1 module standard |

## Quick links

1. **Read the blueprint:** `docs/blueprint.md` — objective & success criteria (§0), design (§1–7), verification (§8)
2. **Design a module:** `docs/module-standard.md` — the slot, pinouts, cartridge envelope, identity EEPROM, conformance checklist
3. **Build one:** `docs/blueprint.md` §9 (BOM) → §10 (assembly)
4. **Use one:** `docs/blueprint.md` §11 (user manual)
5. **Order a board:** `tools/export_fab.py` exports Gerbers, Excellon drill and a CPL to `electrical/smell_monitor_v1_1/fab/`

## Project status

- [x] Objective & success criteria locked (blueprint §0)
- [x] Architecture locked — pneumatic, sensing, electrical, mechanical (blueprint §1–7)
- [x] Volume model + HLR drawing set — real hidden-line views → editable DXF + vector PDF (blueprint §12)
- [x] Schematic generated from the model, ERC-clean, with netlist parity
- [x] PCB placed + routed + DRC-clean, reproducibly (blueprint §12.1)
- [x] Fab package (Gerbers + drill + CPL)
- [x] Firmware — three-phase cycle, USB/Wi-Fi/BLE, compiles clean
- [ ] Electrical sheet OS-003 (PCB floor plan) + pneumatic sheet OS-004
- [ ] Enclosure CAD derived from the routed board (open: module mounting key, PTFE floor liner, reference pocket — §14)
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