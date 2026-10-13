# electrical/

KiCad design files for the Smell Monitor v1.

| Path | What |
|------|------|
| `smell_monitor_v0/` | KiCad 9 project — schematic + PCB (in progress) |
| `bom.csv` | Master BOM with LCSC part numbers + alternatives |

## Wiring / pinout contract (from `docs/architecture.md`)

- **Analog slots J2–J9** (1×4 female): `+5V | GND | AO | DO` — AO feeds a fixed 2:1 divider into ADS1115 (≤2.5 V), DO → ESP32 GPIO.
- **Digital slots J10–J17** (1×6 female): `3V3 | GND | SDA | SCL | INT | CTRL` — SDA/SCL behind TCA9548A channel segments.
- **Master I2C bus:** ESP32 (GPIO21/22) → 2× ADS1115 (0x48/0x49), TCA9548A (0x70), SHT31 (0x44), OLED (0x3C).
- **Power tree:** USB-C 5 V → 5 V net (fan, buzzer, +5V headers) → **U7 AMS1117-3.3** → 3.3 V net (ESP32, ADCs, mux, SHT31, OLED, 3V3 headers).

## Existing / pending

- [x] Core schematic + BOM with alternates
- [ ] Add U7 AMS1117-3.3 (BOM done; schematic pending — BOM gap resolved in v1)
- [ ] AO divider networks (8× 10k/10k to +2.5 V clamp)
- [ ] TCA9548A per-slot 4.7 kΩ segment pull-ups
- [ ] Buzzer/fan drive transistors (GPIO→MOSFET/transistor)
- [ ] ESP32 GPIO allocation review vs strapping pins
- [ ] ERC clean → DRC clean → Gerber export

## Fabrication

Use `bom.csv` column `Supplier Part Number` (LCSC) for JLCPCB/Seeed one-stop PCBA. Export Gerbers per `docs/assembly_guide.md`.