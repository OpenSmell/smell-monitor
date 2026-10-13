# Smell Monitor — User Manual

**Product:** Smell Monitor v1 · Open Source Electronic Nose
**Document:** `docs/manual.md` — intended to be printed at production
**License:** CERN-OHL-S / MIT

---

## 1. What This Device Does

Smell Monitor is a digital nose. It draws in a small air sample through its intake, exposes a set of interchangeable gas sensors to that sample, and records how each sensor responds. The combined response — the "smell signature" — is sent over USB to a computer, where it can be viewed, compared, and analysed.

It does **not** identify smells on its own. It is a sensitive instrument that gives you data; what the data means depends on the sensors you install and the software you connect it to.

### What it is for
- Comparing two samples (is this batch different from that one?)
- Monitoring a smell over time (is something in this room changing?)
- Recording and archiving odor signatures
- Research and experimentation with gas sensors

### What it is not for
- It is **not** a calibrated safety instrument. Do not use it for gas-leak alarms, toxics monitoring, or compliance measurement.
- It detects relative changes, not certified concentrations.

---

## 2. Package Contents (Production Units)

| Item | Qty |
|------|-----|
| Smell Monitor unit (enclosure + PCB assembled) | 1 |
| Analog sensor breakout board (installed) | 1–8* |
| Digital sensor breakout board (installed) | 0–8* |
| USB-C cable (1 m) | 1 |
| Spare PTFE intake filters | 2 |
| Quick start card | 1 |

\* Depending on the sensor pack ordered.

---

## 3. Getting Started

### 3.1 What you need
- A USB-C power source (5 V, at least 1 A; 2 A recommended). A phone charger works.
- A computer with the Osmograph software (or any serial terminal).

### 3.2 First power-on
1. Connect the USB-C cable to the device and to power.
2. The screen lights up. The device runs a self-check: fan spin, sensor detection, internal thermometer check.
3. Status LED behaviour:
   - **Blinking slowly** — idle, ready
   - **Breathing** — taking a sample
   - **Solid** — analysing
   - **Fast blink** — done, results ready
4. If a sensor was not detected, its slot is skipped. The screen shows `OK` or a warning list.

### 3.3 Taking your first measurement
1. Place the device near (but not touching) the thing you want to sniff.
2. Press the measure button (or send a start command from the software).
3. Wait ~40 seconds while the device completes its cycle (the screen shows which phase it is in).
4. Read the result on screen, and on the computer.

A single measurement takes about 40 seconds: 10 s intake, 10 s analysis, 20 s cleaning.

---

## 4. How the Device Works

Each measurement follows three fixed phases:

| Phase | What happens | Takes |
|-------|--------------|-------|
| Intake | The fan draws a sample through the front filter | 10 s |
| Hold | The fan stops. Sensors analyse the trapped sample | 10 s |
| Purge | The fan clears the chamber for the next sample | 20 s |

Between measurements, keep the device somewhere clean. After the purge phase it is ready to sample again.

---

## 5. Sensors

### 5.1 The two kinds of slots
The device has 16 sensor ports on its top surface:

- **8 analog ports** (4 pins) — for classic sensors that output a changing voltage. Examples: MOX sensors (MQ-135, MQ-136…), electrochemical cells.
- **8 digital ports** (6 pins) — for smart sensors that talk on a digital bus. Examples: SGP30, BME688, SCD40, and other MEMS sensors.

### 5.2 Installing or swapping a sensor
No tools needed.

1. Open the top hatch.
2. Look at the connector pins and align the sensor board's socket with the port. It only fits one way.
3. Press down until seated. Close the hatch.
4. On next power-on, the device detects the sensor automatically.

**To remove:** open the hatch, pull straight up. Store spare sensors in closed dry containers.

### 5.3 Choosing sensors for your job
Different sensors react to different chemicals. Selecting the right ones is how you tune the device to your problem.

| If you care about… | Try sensors like… | Port type |
|--------------------|-------------------|-----------|
| Ammonia / amine smells | MQ-135, MQ-137 | Analog |
| Rotten-egg / sulfur smells | MQ-136 | Analog |
| General household VOC levels | MQ-138, SGP30 | Either |
| CO₂ levels | SCD40 | Digital |
| Humidity + a general smell profile | BME688 | Digital |

For guidance, see the OpenSmell community's recommended "packs" — pre-chosen sets of sensors for common jobs (cooking odours, damp/mould, air-quality checking).

### 5.4 Sensor lifespan
- Analog sensors slowly wear out with continued use. Typical useful life: months to a few years depending on duty.
- If a sensor's idle reading drifts far from its original value, or it no longer responds to a strong smell, replace it. Capacitors have a limited lifespan (as is the case for other electronic devices).

### 5.5 Handling care
- Do not power sensors beyond their electrical limits. Each analog slot supplies 5 V; each digital slot supplies 3.3 V. Check your sensor's datasheet before plugging anything custom in.
- Do not sniff liquids, corrosive gases, solvents directly, or anything that would damage the unit or sensors. While the filter protects the sensors from particulates, no filter protects against corrosive chemicals.

---

## 6. Maintenance

### 6.1 Cleaning the chamber
Over time, residues can build up inside the sensing cavity.

1. Remove all sensors (see §5.2) and the top hatch.
2. Wipe the inner cavity with a soft, dry lint-free cloth or a cotton swab. **Do not use solvents or water** unless instructed by the maintenance bulletin — some residues only need dry removal.
3. To air out the cavity, run one purge cycle without sensors installed, or leave the hatch open for a few minutes.
4. Replace the hatch and sensors.

### 6.2 Replacing the intake filter
1. Open the top hatch.
2. Locate the filter behind the front intake holes.
3. Remove the filter retainer, discard the old membrane, insert a new one (PTFE side lettering facing the incoming air), replace the retainer.
4. Reset the filter counter in the software.

**When:** every 90 days of use, after any visible clogging, or after suspected smoke/dust exposure.

### 6.3 Firmware updates
Connect over USB and use the Osmograph software's update tool. Do not unplug during an update.

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Screen stays dark on power-on | No power / cable fault | Try another USB-C cable and a 5 V/2 A supply |
| "Fan fault" at start | Fan blocked or disconnected | Check the fan and its connector |
| "No sensors found" | None installed or seating fault | Install a sensor; reseat it in its port |
| Reading stuck at same value | Sensor worn out or chamber contaminated | Clean chamber (§6.1); replace the sensor |
| Measurements drift all day | Device warmed up / environment changed | Run the device for 10 min before critical work; log temperature |
| Smell from a previous sample lingers | Chamber needs cleaning | Run 2–3 purge cycles; if persistent, clean per §6.1 |
| Bad data over USB | Loose cable / wrong baud rate | Check cable; use 115200 baud |

If the problem persists or you smell something you doubt is safe, stop using the device and contact the OpenSmell community.

---

## 8. Safety

- This device is an **experimental/research instrument**, not a safety device.
- It is powered by low-voltage USB-C (5 V) and is safe to handle normally.
- Do not open the rear service bay while powered.
- Do not use in explosive atmospheres or near flammable vapours without review.
- Keep the device away from liquids.

---

## 9. Specifications

| Parameter | Value |
|-----------|-------|
| Power input | USB-C 5 V / 1 A (2 A recommended) |
| Power consumption | ≤ 2.5 W worst case |
| Sensor ports | 8 analog (4-pin), 8 digital (6-pin) |
| Measurement cycle | ~40 s (intake 10 / hold 10 / purge 20) |
| Airflow | Active fan draw, ~1 L/min |
| Intake filter | PTFE membrane, replaceable |
| Dimensions (L×W×H) | ≈ 140 × 80 × 60 mm |
| Weight | ≈ 250 g (config-dependent) |
| Operating temperature | 5–40 °C |
| Operating humidity | 20–80 % RH (non-condensing) |
| Interface | USB-C serial (115200 baud) |
| Warranty | None implied — open-source kit; defect and reliability information available via the OpenSmell repository |

---

## 10. Getting Help and Sharing Data

- Project repository & issues: `github.com/OpenSmell/smell-monitor`
- Community forum and sensor-pack recommendations: OpenSmell community channels
- Data format documented in `docs/firmware` / Osmograph docs.
- Share anonymised datasets — this is how we all learn to interpret smells together.

*Thank you for building with us. If you improve something — a sensor pack, an enclosure mod, a calibration — please contribute it back.*