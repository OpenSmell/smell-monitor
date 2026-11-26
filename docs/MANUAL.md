# OpenSmell Smell Monitor — User Manual

**Document:** OSM-UM-001
**Revision:** E
**Date:** 2026-11-26
**Product:** Smell Monitor v1.1 (one SKU)
**Firmware:** v1.2.0
**Companion software:** Osmograph desktop
**Interface standard:** OSM-1 (OpenSmell Module Standard v1)

---

## Notice

This manual describes the Smell Monitor, an open-source, modular,
sensor-agnostic digital olfaction acquisition platform. It is a research
instrument for controlled sample presentation and data capture. Use it within
its rated 5 V USB-C power and environmental range. Do not use it in explosive
atmospheres or for life-safety measurement.

The tray and lid are sealed PETG for an **inert gas path**. The inlet filter is a
**thin woven PTFE mesh** — cleanable, and replaced only if torn or permanently
clogged. A sealed SSD1306 OLED sits in a shallow bezel on the **fixed front
wall**; its 27 × 13 mm window is centred at shell (x=61, z=45), and its gasket is
outside the sample path. All four buttons are on that same front panel, and one
sealed 6 mm grommet at (82,45) carries the display and button harnesses into the
chamber. The lid is a plain flat plate with four M3 screws: no wires, no holes,
and no need to open the box to use the UI. There is no battery: plug-in USB-C
supplies power and data, and stable supply is the installer's responsibility.
Radios remain off until you enable them. Routine firmware updates arrive OTA;
the device verifies the host-signed manifest and SHA-256 image before install,
so you do not unscrew the box to flash. USB-C serial flashing is recovery only.

---

## 1. System Overview

```mermaid
flowchart TB
    subgraph sample ["Sample enters"]
        N[3 × Ø6 nostrils<br/>front wall]
        F[Thin woven PTFE mesh filter<br/>front drawer]
    end

    subgraph chamber ["Sealed chamber"]
        LW[Left wall: slots 1–4 (J2–J5)<br/>upright, inward, 24 mm pitch]
        RW[Right wall: slots 5–8 (J6–J9)<br/>upright, inward, 24 mm pitch]
        S[SHT31 T/RH<br/>reference on base]
        CH[Central channel<br/>gas flows front to rear]
    end

    subgraph exhaust ["Exhaust"]
        Fan[40 mm PWM fan<br/>rear, outside chamber]
    end

    subgraph base ["Base board (chamber floor)"]
        MCU[ESP32-WROOM-32E]
        ADC[ADS1115 ×2<br/>8 analog channels]
        Mux[TCA9548A I²C mux<br/>8 channels]
    end

    subgraph panel ["Fixed front wall (outside sample path)"]
        OLED[SSD1306 at master I²C 0x3C<br/>shallow bezel, 27 x 13 mm window]
        BTN[MEASURE/OK, MENU/BACK, BOOT, RESET<br/>one sealed harness grommet]
    end

    subgraph host ["Host and network"]
        UI[Osmograph: slot map, calibration,<br/>versioned profiles, QC, labels]
        NET[HTTP /data replay + retained MQTT/LWT<br/>Wi-Fi / BLE off until enabled]
    end

    N --> F --> CH --> Fan
    LW -.-> CH
    RW -.-> CH
    S -.-> MCU
    MCU --> ADC
    MCU --> Mux
    OLED -.-> MCU
    BTN --> MCU
    MCU -->|USB-C serial| UI
    MCU -.->|Wi-Fi / BLE, when enabled| NET
```

![Figure 1 — Plan and longitudinal section of the sample path](figures/cad/manual_linework.png)

**Figure 1.** The enclosure in plan (lid removed) and in section along the flow.
Air enters through three Ø6 nostrils centred on the channel, passes the cleanable
woven PTFE mesh, travels straight between two inward-facing rows of upright
breakout boards and exits through the rear 40 mm fan. Each card rises 32 mm and
has a 4.9 mm hood to the lid; 13 mm of wall clearance behind it leaves room for
rear pins. All eight sockets are identical and every header and pin is
silkscreened. The top face of the base board is the chamber floor. The lid is a
plain flat plate with four M3 screws; the display and all four buttons are on
the fixed front wall. The vector original is `figures/cad/manual_linework.svg`.

**What the device does.** Draws a controlled air sample through three front
nostrils, over eight interchangeable OSM-1 sensor cartridges, and records a
`.osmell` stream over USB-C. Raw gas channels (`ao[8]`, `adc[8]`, `do_[8]`),
temperature, humidity, slot index, sequence ID and `wall_clock` time stay
canonical. Identity and calibration fields are emitted as null and attached by
Osmograph from its slot map. pH is reported only when an ISFET cartridge is
fitted. When you install a versioned interpretation profile, the record also
carries additive fields marked `derived`.

---

## 2. What's in the Box

| Item | Qty | Purpose |
|------|-----|---------|
| Smell Monitor base unit (PCB + sealed PETG tray + sealed front-wall OLED bezel + plain four-screw lid) | 1 | Main instrument |
| Thin woven PTFE mesh filter | 1 | Stops droplets and dust; front drawer |
| USB-C data cable, 1 m | 1 | Power + data to host |
| USB-C panel pigtail, 0.3 m | 1 | Bulkhead feedthrough |
| M3 screws | 4 | Lid retention |
| Heat-set inserts | 4 | Lid threads in tray |
| Quick-reference card | 1 | Pinout, buttons and cycle states |

**Not included:** sensor cartridges. You supply the modules that match your use
case (MOX, MEMS, NDIR, electrochemical, piezo, QCM — any OSM-1-conforming
cartridge fits any slot).

---

## 3. Hardware Tour

All eight slots are identical: gas-cell socket **and** Qwiic port at every
position. Flow order is fixed front → rear; slot assignment is yours. The sealed
front-panel display is non-slot hardware outside the sample path; the lid is
plain.

| Part | What it is |
|------|------------|
| **Nostrils** | Three Ø6 holes in the front wall. Air enters here. |
| **Filter drawer** | Holds the cleanable thin woven PTFE mesh. Lift out with the lid off; rinse, dry, reinsert. |
| **Slots 1–8** | Keyed 1×6 gas-cell socket `+5V GND AO DO 3V3 ID` + Qwiic/STEMMA QT port `GND 3V3 SDA SCL` at every slot. Any OSM-1 cartridge fits any slot. |
| **SHT31** | Fixed temperature/humidity reference on the base board, soldered to the main I²C bus, logged at 1 Hz. |
| **Base board** | ESP32-WROOM-32E, two ADS1115s (8 channels), TCA9548A (8 channels). Its top face *is* the chamber floor. |
| **Fan** | 40 mm PWM exhaust on the rear wall, outside the chamber. Pulls air through. |
| **Front-panel display** | Sealed SSD1306 128×64 OLED on the master I²C bus at `0x3C`, in a shallow bezel on the fixed front wall. The 27 × 13 mm window is centred at shell (61,45); its gasket keeps it outside the sample path. |
| **Buttons** | All four are on that front wall and reachable with the lid closed: MEASURE/OK (88,49), MENU/BACK (100,49), BOOT (88,39) and RESET (100,39). One sealed 6 mm grommet at (82,45) carries the display and button harnesses. |
| **USB-C** | Plug-in 5 V power and always-on 115200 baud serial for data, profile push and recovery flashing. Routine updates are OTA. Wi-Fi and BLE are off until enabled. |

---

## 4. 5-Minute Quick Start

**Step 1 — Power.** Plug the USB-C cable into the Smell Monitor and into your
computer or a stable 5 V source. The status LED gives one slow blink (idle) and
the front-panel display shows the status screen.

**Step 2 — Open Osmograph.** Launch Osmograph on your computer. It opens the
serial port at 115200 baud automatically. Osmograph owns the slot map and
calibration; the front-panel display shows live status without a host.

**Step 3 — Insert cartridges.** Open the lid (four M3 screws). Plug your sensor
cartridges into any slots. Close the lid.

**Step 4 — Measure.** Press MEASURE/OK or click "Measure" in Osmograph. The LED
is solid while the ≈40 s cycle runs (10 s intake / 10 s hold / 20 s purge), then
gives a brief fast blink and a buzzer beep when results are ready. The front-panel
display shows the phase and T/RH during the cycle.

**Step 5 — Read the record.** Osmograph displays the `.osmell` record: slot
values, temperature, humidity, sequence ID and QC flags. A red QC flag means
"check this reading," not "the device is broken." The front-panel values screen
shows derived values when a profile is installed.

**First-time tip:** Run three clean-air cycles before your first measurement so
the chamber and sensors reach a stable baseline.

### Customising timing, fan and buzzer

Osmograph can change these over the same serial / Wi-Fi / BLE link used for
readings. Send one command per line; settings persist across power cycles.
`status` reports the current values.

| Command | Effect |
|---------|--------|
| `fan intake <0-255>` | PWM duty while drawing the sample in (default `128`) |
| `fan hold <0-255>` | PWM duty while sensors equilibrate (default `0`, still air) |
| `fan purge <0-255>` | PWM duty while flushing the chamber (default `255`) |
| `rate <20-5000>` | ADC read interval during HOLD in ms (default `125`) |
| `timing <intake> <hold> <purge>` | Phase lengths in ms (defaults `10000 10000 20000`) |
| `mute` / `unmute` | Disable / enable the end-of-cycle beep |
| `display <line1>|<line2>` | Persistent user text on the front-panel display; `display auto` returns to live screens |
| `status` | Report firmware version, radios, OTA state and all current settings |

---

## 5. Display Screens and Buttons

The sealed front-panel SSD1306 has four 16-character rows. Press **MENU/BACK**
briefly to step through screens:

| Screen | Content |
|--------|---------|
| Status | Phase, cycle state, T/RH, AQI label when a profile is active, fault marker |
| Values | Per-slot derived values from the active profile; with no profile, the status screen shows raw AO0 |
| User text | Two lines set with `display <line1>|<line2>` (skipped when empty) |

Button actions:

| Action | Result |
|--------|--------|
| MEASURE/OK, short press | Start a measurement, acknowledge a fault banner, or mute the beep during a cycle |
| MENU/BACK, short press | Next display screen |
| MENU/BACK, hold > 2 s | Open the password-protected Wi-Fi setup AP |
| MENU/BACK, hold > 5 s | Arm factory reset; MEASURE/OK confirms, MENU/BACK cancels |
| BOOT + RESET | Recovery access for USB-C serial flashing; no lid removal required |

The LED and buzzer keep the same indications as the status screen: slow blink =
idle, solid = sampling, brief fast blink plus beep = results ready.

---

## 6. Profiles and Derived Values

Raw `.osmell` values are canonical and are never rewritten. Osmograph pushes a
**versioned interpretation profile** that names each configured slot's zero,
span and label. Firmware computes additive derived fields only while a profile
is present and marks them `derived` in the record; the front-panel values screen
shows the same numbers. Local inference is bounded arithmetic and threshold logic;
heavy machine learning runs on the host.

| Command | Effect |
|---------|--------|
| `profile <json>` | Validate, persist and activate a profile |
| `profile get` | Print the installed profile JSON |
| `profile clear` | Remove the profile; derived fields become null |

With no profile installed, the device keeps its raw-only behavior: raw
records continue unchanged and derived fields are null.

---

## 7. OTA Updates

Routine firmware updates are OTA, so you do not unscrew the box to flash.
Osmograph prepares a manifest carrying a **SHA-256 digest and a signature made
with the host-held private key**. The device verifies that signature with its
embedded public key and checks the image's SHA-256 digest before installing; the
signing key never leaves the host.

| Command | Effect |
|---------|--------|
| `ota <url> <sha256>` | Queue an update from the HTTP image URL and its manifest digest |
| `ota status` | Report manifest state, version, progress and any error |

The device verifies the manifest signature with its embedded public key, checks
that the manifest digest matches the supplied digest and requires a strictly
greater version. It verifies the downloaded image against that SHA-256 digest
and size before installing, and switches the boot partition only after
verification. A successful boot confirms the image; three unconfirmed boots
select the previous partition. USB-C serial flashing remains the
recovery path if an update cannot complete.

---

## 8. Status, Replay and Telemetry

Every generated record carries a sequence ID and is persisted immediately, so a
power cut cannot lose a record that was already generated. Records are held in
an NVS ring buffer of the most recent 32. Wi-Fi and BLE stay off until you enable
them; the same record shape travels over every enabled transport.

| Interface | What it provides |
|-----------|------------------|
| `HTTP /data` | Latest record plus the 32-record replay buffer |
| `HTTP /data?since=<seq>` | Replay of records after that sequence ID, in order |
| MQTT retained `<topic>/status` | Connection status retained by the broker |
| MQTT LWT | Unexpected-disconnect notice |
| NTP | `wall_clock` timestamps alongside boot-relative time |
| USB serial, Wi-Fi MQTT, BLE notify | Realtime telemetry on enabled transports |

Use `status` to see the active firmware version, radio state, fan settings,
timing and OTA state. Physical acceptance of the sample path and these data
paths is specified in `docs/VALIDATION_SPECS.md`.

---

## 9. Module Swapping Guide (OSM-1)

Every slot carries both interfaces side by side:

| Interface | Pinout (keyed 1×6, 2.54 mm) | Serves |
|-----------|------------------------------|--------|
| **Gas cell** | `+5V GND AO DO 3V3 ID` | MOX, electrochemical, NDIR-with-Vout, catalytic, PID |
| **I²C port** | Qwiic / STEMMA QT (`GND 3V3 SDA SCL`) | NDIR CO₂, T/RH, VOC index, particulate |

```
Gas-cell socket pinout (looking at the base):
  Pin 1: +5V   (heater rail, ≤150 mA per slot)
  Pin 2: GND
  Pin 3: AO    (cell output, 0–5 V, divided 10k/10k into the ADC)
  Pin 4: DO    (comparator output or TTL serial RX, 3.3 V GPIO via 10k series)
  Pin 5: 3V3   (≤50 mA for cell converter)
  Pin 6: ID    (1-Wire shared bus; firmware emits null identity fields)
```

Each Qwiic port is one channel of the TCA9548A (channel *n* = slot *n*), so two
modules with the same I²C address can be used at once.

**How to swap a cartridge:**
1. Power down (unplug USB-C).
2. Remove the four M3 lid screws; lift the lid.
3. Lift the cartridge straight out of its socket.
4. Align the new cartridge's pin-1 chamfer with the socket key; press straight down.
5. Replace the lid, tighten four M3 screws.
6. Power on. The record carries the slot index; Osmograph attaches the sensor
   type and calibration from its slot map. No identity chip is required.

**No tools beyond a 2.5 mm hex key.** A swap takes under 60 seconds. Calibration
and exposure history are host-side data: update the slot map when you move a
cartridge to a different slot. The base needs no re-calibration.

---

## 10. Understanding QC Flags

Osmograph evaluates every record and appends red QC flags to affected slots.
Thresholds are set in Osmograph; adjust them against clean-air and known-bad data.

| Flag | What it means | What to check |
|------|---------------|---------------|
| `adc_saturation` | Slot voltage sits at 0 V or the ADC rail (2.5 V at the ADC = 5 V at the slot) for two consecutive cycles | Disconnected or shorted sensor; check wiring, reseat cartridge |
| `baseline_drift` | Hold-phase voltage slope exceeds 0.05 mV/s | Sensor warming up; allow 10 min warm-up; check temperature changes |
| `sht31_out_of_range` | Temperature or humidity jumped more than threshold in one cycle | Fan failure, seal leak, or rapid ambient change; check fan spins |
| `eeprom_mismatch` | Readings present but the host has no identity/calibration entry for that slot | Update Osmograph's slot map; data still works, flagged as uncalibrated |
| `flow_stagnation` | MOX resistance did not drop during intake (flat or rising) | Fan not spinning; filter mesh blocked; cartridge seated wrong |

**Rule of thumb:** A red flag means "verify before trusting."

---

## 11. Maintenance

The Smell Monitor has no scheduled consumables; the inlet mesh is cleanable and
is replaced only if damaged or permanently clogged.

| Task | Interval | How |
|------|----------|-----|
| Rinse filter mesh | When visibly dusty, or after smoke/dust exposure | Lift the lid, remove the drawer, rinse the woven PTFE mesh under tap water, air-dry, reinsert |
| Wipe chamber interior | Annually, or after strong odor events | Dry lint-free cloth only; no solvents |
| Check fan | If `flow_stagnation` appears | Verify fan spins freely; check connector |
| Check bezel gasket and grommet | Periodically | Confirm the front-wall bezel gasket and single harness grommet remain sealed; the lid carries no display or wires |
| Recalibrate cartridge | Per the host slot-map history | Follow the cartridge maker's procedure; update Osmograph's slot map |

**Never:** use compressed air on the sensors, spray solvent into the chamber, or
install silicone anywhere air touches. The gas path is inert-gas only; conformal
coat is acrylic or polyurethane, never silicone. Silicone vapour permanently
poisons SnO₂ MOX cells.

---

## 12. Specifications

| Parameter | Value |
|-----------|-------|
| Product | One SKU; eight uniform OSM-1 slots |
| Power | Plug-in USB-C 5 V (1.38 A worst case; 3 A source assumed); no battery; stable supply is installer responsibility |
| Idle power | < 1 W |
| Loaded power | ≈ 5 W starter pack; up to ≈ 8 W worst case (MOX heaters dominate) |
| Sensor ports | 8 identical OSM-1 slots: 1×6 gas-cell socket + Qwiic port at each; any mix |
| Local UI | Sealed SSD1306 128×64 OLED at master I²C `0x3C` in a shallow fixed-front-wall bezel (27 × 13 mm window at shell (61,45)), gasket outside the sample path; MEASURE/OK (88,49), MENU/BACK (100,49), BOOT (88,39) and RESET (100,39) on the same panel, one sealed 6 mm harness grommet at (82,45); plain four-screw lid |
| Acquisition | 2 × ADS1115 (8 channels), TCA9548A (8 channels), SHT31 at 1 Hz |
| Cycle time | ≈ 40 s (10 s intake / 10 s hold / 20 s purge) |
| Airflow | 15 L/min design purge; physical acceptance in `docs/VALIDATION_SPECS.md` |
| Filter | Thin woven PTFE mesh, cleanable; front drawer |
| Wetted surfaces | Sealed PETG tray, lid and filter drawer; inert gas path only; acrylic/PU conformal coat, never silicone |
| Lid | Flat lid, four M3 screws |
| Enclosure | 122 × 114 × 66 mm assembled (128 mm deep with rear fan) |
| Mass | ≈ 240 g |
| Operating range | 5–40 °C, 20–80% RH |
| Serial | USB-C 115200 baud (always on) |
| Wireless | Wi-Fi 2.4 GHz + Bluetooth LE (off until enabled) |
| Data format | `.osmell` v1.0: canonical raw gas + T/H, null identity/calibration, optional `derived` fields from a versioned profile |
| Telemetry | Sequence IDs, 32-record NVS replay via `/data` and `/data?since=<seq>`, retained MQTT status and LWT, NTP `wall_clock`, per-record power-fail flush |
| Updates | OTA: device verifies the host-signed manifest with its embedded public key and the SHA-256 image digest before install; version gate and rollback; USB-C serial recovery |
| Safety | Research instrument; 5 V USB-C; do not use in explosive atmospheres; keep from liquids |

---

## 13. Warranty & Support

Open-source hardware under CERN-OHL-S. Firmware and software under MIT.
Documentation under CC BY-SA 4.0.

Community support via the OpenSmell GitHub repository:
github.com/OpenSmell/smell-monitor

---

*End of manual — OSM-UM-001 Rev E*

