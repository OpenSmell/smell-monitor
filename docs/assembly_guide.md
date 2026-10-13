# Smell Monitor — Assembly Guide

**Document:** `docs/assembly_guide.md`
**Audience:** Builders and fabricators (including PCBA services like Seeed Fusion / JLCPCB).
**Scope:** From bare boards and parts to a working, tested unit.

---

## 1. Parts Overview

- **PCB:** `electrical/smell_monitor_v0/` (order assembled or bare)
- **BOM:** `electrical/bom.csv` (LCSC part numbers supplied for 1-stop PCBA)
- **Enclosure:** `mechanical/` — STL for shell + PTFE/chamber insert (or machined)
- **Sensors:** user-supplied breakout boards per `docs/architecture.md §4`

### 1.1 Optional order of operations
Two routes, identical result:

- **Route A — PCBA service does everything:** submit BOM + Gerbers from the repo; receive a fully assembled board; you only snap it into the printed enclosure and add sensors.
- **Route B — hand assembly:** follow §2 below.

---

## 2. PCB Assembly (hand-build route)

### 2.1 Tools
Soldering iron (fine tip), flux, solder, tweezers, magnifier, multimeter, USB-C test supply.

### 2.2 Order of soldering (small → large)
1. 0603 passives (R1–R21, C1–C20/uF) — work in one orientation sweep.
2. LDO U7 (AMS1117-3.3, SOT-223), ensuring the tab pad is well soldered.
3. ICs: U2/U3 (ADS1115 MSOP-10), U4 (TCA9548A TSSOP-24), U5 (SHT31 SMD-8).
4. OLED U6 (header or SMD), LED1 (watch polarity), buzzer BZ1.
5. Connectors: USB-C J1, fan JST J19, all 16 sensor headers (J2–J17).
6. ESP32-WROOM-32E U1 last (large module); verify pad alignment before reflow.

### 2.3 First-power tests (before enclosure)
1. Power via USB-C. Measure **3.3 V** rail at U7 output — expect 3.35 ± 0.1 V.
2. Probe every analog slot `+5V`–`GND` and every digital slot `3V3`–`GND`.
3. Scan I2C bus (idle): expect `0x48`, `0x49` (ADS1115s), `0x44` (SHT31, if present), `0x70` (TCA9548A), `0x3C` (OLED).
4. Flash firmware (`firmware/`), confirm OLED shows the self-test screen.

---

## 3. Enclosure and Chamber

Sources in `mechanical/`:
- **Shell:** cosmetic outer; PLA/PETG print is acceptable (non gas-contacting).
- **Chamber insert (IMPORTANT):** the gas-contacting cavity must be PTFE-lined, glass, or PTFE insert. A plain plastic print is not acceptable (see `docs/architecture.md §3.4`). Fabricate or print the shell, then bed the PTFE insert.
- **Baffle:** perforated screen offset ~8 mm above seated sensor elements.
- **Filter retainer:** holds the PTFE membrane behind the two Ø5 mm nostril intakes.

### 3.1 Chamber assembly sequence
1. Position the PTFE chamber insert in the front half of the shell; it presses against the PCB bulkhead gasket.
2. Install the perforated baffle over the sensor area.
3. Fit the filter membrane + retainer behind the intake.
4. Install the fan in the rear service bay (exhaust facing out), wire to J19.
5. Seal the bulkhead; fix the two halves.

### 3.2 Sensor seating
Insert sensor breakouts into J2–J17 before closing the top hatch. Orient so sensing elements face up into the chamber through the baffle.

---

## 4. Final Integration and Self-Test

1. Power on; confirm self-test passes (screen shows `OK`).
2. Perform a **purge sanity test**: run 3 cycles in clean air; baseline readings should return to within a few % of each other.
3. Perform a **sample challenge**: expose to a known source (e.g., coffee), confirm sensors respond, then confirm full baseline return after one cycle (memory acceptance — see `architecture.md §8.2`).
4. Update the filter-counter and sensor inventory fields in the software.

## 5. Hand-off to Production

Use `docs/architecture.md §8.4` delivery checklist: ERC/DRC clean, BOM with LCSC numbers, Gerbers + position file, STEP, this guide, firmware binary + flash guide.