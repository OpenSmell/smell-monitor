# OpenSmell Module Standard v1 (OSM-1)

Status: **as built (OSM-1).** The board in the tree implements every rule below:
eight uniform keyed 1×6 sockets (J2–J9) and eight Qwiic ports (J11–J18), two
ADS1115s, 10 kΩ `DO` series resistors and a shared 1-Wire `ID` bus. §9 records
the conformance of that board. `mechanical/standard.py` is the same rules as
data, and `tools/verify_module_fit.py` checks the chamber, the socket contract
and the module database against it, so this document and the hardware cannot
drift apart quietly.

## 1. Why a standard exists

Supporting every module on the market is not possible: there is one mechanical
socket (2.54 mm) and a wide range of board sizes and pin orders. Sensors are the
part that changes — a 2026 MOX cell will be replaced several times inside the
life of one base. What has to stay stable is the layer underneath:

* the **gas physics** — every cell sees a defined sample, in a defined order,
  with no memory of the previous one;
* the **slot** — one physical and electrical contract, so a cell designed next
  year by someone else plugs into a base built today;
* the **identity** — the host knows which slot holds which module and what it
  has been through, so calibration and aging are handled in software.

Everything below serves those three. No specific sensor appears here on purpose.

## 2. There is one slot, and it is repeated

A slot is not "analog" or "digital". Every slot carries **both** interfaces, side
by side on the same footprint:

| Interface | Serves | Connector | Rail |
|-----------|--------|-----------|------|
| **Gas cell** | anything that outputs an analog voltage or TTL serial: MOX (SnO₂), electrochemical, NDIR with a Vout, catalytic, PID | 2.54 mm keyed 1×6 header | **5 V** (heater capable) |
| **I²C port** | anything with its own converter: NDIR CO₂, T/RH, VOC index, particulate | **Qwiic / STEMMA QT**, JST-SH 1.0 mm 4-pin (J11–J18 as built) | **3.3 V** |

The user fills slots with whatever chemistry the job needs, in any mix, and
never has to know which slot is "the analog row". The host slot map decides what
each slot means; the base only acquires. Every header and pin is permanently
silkscreened on the board.

The one thing the mix cannot change is geometry: the two side-wall rows face
each other across a central channel, so the record carries its slot index and
wall. The host map can model any uptake gradient between the banks; the base
does not prescribe which sensor goes where.

### 2.1 Gas cell pinout (keyed 1×6, 2.54 mm)

| Pin | Net | Notes |
|-----|-----|-------|
| 1 | `+5V` | 5 V, ≤ 150 mA per slot for the heater |
| 2 | `GND` | |
| 3 | `AO` | cell output, **0–5 V**, divided 10k/10k into the ADC |
| 4 | `DO` | comparator output **or** TTL serial RX — a plain 3.3 V GPIO |
| 5 | `3V3` | 3.3 V, ≤ 50 mA, for the cell's own converter |
| 6 | `ID` | 1-Wire, shared bus; optional identity device (§3) |

A 2.54 mm plug with no 6th pin is still a conforming cell: v1 firmware does not
enumerate identity devices at all, so it applies no ID-specific behaviour.

Pins 3 and 4 can both act as slow GPIO, which is how one socket runs a MOX cell
(AO), an electrochemical cell (AO) and a UART NDIR module (DO as RX). I²C cells
belong on the port that is built for I²C: §2.2.

### 2.2 I²C port pinout (Qwiic / STEMMA QT)

| Pin | Net | Wire colour |
|-----|-----|-------------|
| 1 | `GND` | black |
| 2 | `3V3` | red — **never 5 V** |
| 3 | `SDA` | blue |
| 4 | `SCL` | yellow |

Each slot's `SDA`/`SCL` passes through its own TCA9548A channel, so **two
identical modules with the same I²C address can be used at once** and there are
no address collisions to manage. Eight slots and eight mux channels is an exact
fit; nothing extra is needed to reach the full count.

Grove (2.0 mm JST-PH) and Gravity carry the same four signals in a different
order and work through an adapter cable.

## 3. Identity: host-managed in v1

The base wires all eight `ID` pins to one shared 1-Wire bus with a 4.7 k pull-up.
v1 firmware does **not** enumerate per-slot ROMs: all eight pins are in parallel,
so one device on that bus could not say which slot it occupies. The `.osmell`
`eeprom_id`, `sensor_model` and `calibration_date` fields are emitted as null by
firmware and attached by Osmograph (or any host) from its slot map.

This is deliberate, not a cut corner: every slot stays electrically identical,
any module goes in any slot, and the host owns the meaning. No extra GPIO,
expander or per-slot mux was added to solve a mapping problem in hardware.

### 3.1 Reserved optional cartridge memory (not required in v1)

A cartridge maker may later fit a 1 kbit 1-Wire device (DS2431 / AT21CS01 class).
The map below is reserved for that future option and is **not** a v1 conformance
requirement. No v1 gate assumes such a device is present.

| Offset | Size | Contents |
|--------|------|----------|
| `0x00` | 4 | magic `"OSM1"` |
| `0x04` | 1 | standard revision (1) |
| `0x05` | 1 | kind (1 gas cell, 2 I²C module) |
| `0x06` | 1 | class (1 MOX, 2 EC, 3 NDIR, 4 PID, 5 T/RH, 6 PM, 7 other, 8 pH/ISFET) |
| `0x07` | 1 | flags: heater, needs purge, needs 5 V |
| `0x08` | 8 | part number, ASCII |
| `0x10` | 4 | lot / serial |
| `0x14` | 2 | first use, year+month (0 = virgin) |
| `0x16` | 4 | accumulated exposure hours |
| `0x1A` | 2 | peak temperature seen, int16 in 0.1 °C |
| `0x1C` | 4 | rail requirement: mV, mA |
| `0x20` | 32 | calibration blob, defined per class |
| `0x40` | 63 | reserved for the module maker |
| `0x7F` | 1 | checksum over `0x00`–`0x7E` |

### 3.2 Where calibration lives

Calibration and exposure history are **host-side data in v1**. The host keeps a
slot map (part number, class, calibration date, accumulated hours) and writes it
into each `.osmell` record. Qwiic modules can additionally answer an I²C
`WHO_AM_I` probe through their own mux channel.

If a future cartridge uses the reserved memory above, the same host map can be
seeded from it; that is an addition, not a change to the slot or the firmware.

### 3.3 Calibration blob per class (reserved map)

| Class | Contents |
|-------|----------|
| MOX | `R0` in clean air, log-log slope, the gas it was characterised against, T/RH of that measurement |
| EC | sensitivity nA/ppm, zero offset, temperature coefficient |
| NDIR | factory span check value, pressure reference |
| T/RH | manufacturer ID plus last field check |
| pH/ISFET | two-point buffer calibration (offset at pH 7, slope mV/pH), last buffer date and temperature |

### 3.4 Behaviour with no identity device (the "just works" rule)

No identity device is required. A user who solders an inexpensive MQ cell onto a
blank carrier and plugs it in gets data immediately. The record carries the slot index
and flow position; the host decides whether that slot is calibrated. Missing
identity is not a hardware error.

## 4. Mechanical envelope

The cell is mounted **upright on an inner side wall**: the card stands in the
Y-Z plane, its 1×6 pin line front-to-back, and its sensing face looks **inward**
across the central channel. Gas enters at the centred nostrils, runs straight
between the two facing rows and leaves through the rear fan. Every socket is
inset 13 mm from its wall so a board with rear pins or a tall part on its back
never touches the wall.

| Quantity | Value |
|----------|-------|
| Cartridge outline | ≤ **20 mm** along the wall × ≤ **32 mm** tall |
| Cell reach into the channel | ≤ **21 mm** from the board face |
| On the socket | the card rises 8.5 + 32 = 40.5 mm above the board (top z = 49.1), leaving a 4.9 mm flow hood under the lid at z = 54 |
| Sensing element | on the inward face, centred at roughly z = 33; it needs clear air in the channel |
| Slot pitch | **24 mm** on stations 24 / 48 / 72 / 96 along each wall; a card is ≤ 20 mm wide so it clears its neighbour |
| Wall clearance | **13 mm** behind every socket for rear pins/hardware |
| Keying | pin-1 chamfer plus a polarising slot in the socket wall |

The base socket is a **vertical 2.54 mm receptacle**; the cartridge carries a
**straight male header** on its edge. The card therefore stands upright and
comes out straight up. Swapping is tool-free: four M3 screws, lid off, lift the
cartridge.

**There is no window or baffle.** An earlier revision required each cartridge's
sensing element to sit in a plate opening above the board. That plate has been
removed. A cartridge plugged into its socket already has unobstructed air in the
channel, and the plate only added a part, a liner and a recess. The standard
therefore constrains the cartridge's outline, reach and connector — not the
position of its element.

A bare MQ-135 card (32 × 20 mm, can Ø19, element 16 mm from its header) *is* a
conforming cartridge once its header is re-pinned to §2.1. Anything that is not
a card — a TO-5 can, a Ø23.5 Winsen can, a bare SMD part, a piezo film — goes on
the **OpenSmell carrier**: one blank PCB that accepts any of them and presents
this socket and this sensor zone. The carrier is shared, so a new sensor needs no
base change.

## 5. Wetted-material rules

The classic MOX field death is **silicone poisoning**: silicone vapour
decomposes on the hot SnO₂ surface into a silica layer that permanently kills
the response. It comes from the assembly, not from the sample.

**Banned anywhere the gas touches:** silicone (sealant, adhesive, grease,
tubing, wire insulation, conformal coat), PVC tubing or insulation, bare zinc,
paper or card, foam.

**Allowed:** PTFE, PFA/FEP, PVDF, borosilicate glass, 316 stainless, gold- or
nickel-plated contacts, PTFE-insulated wire, non-silicone epoxy outside the path.

**Gas path:** a **thin woven PTFE mesh** filter (hydrophobic, WEP ≥ 350 mbar)
with a 5–20 µm particulate pre-screen, spanning the full inlet cross-section so
no stream bypasses it; cleanable, and replaced only if torn or clogged (blueprint
§3.6).

**There is deliberately no carbon in series with the sample.** Carbon is what
would remove silicone and sulfur — and the analytes too, which is the whole
point of the instrument. Carbon belongs on a *reference-air* path (blueprint
§13's zero/baseline line), never in the sample path; blueprint §6.3 forbids
adsorbing media there for exactly this reason. So silicone poisoning is defended
in three ways that do not cost sensitivity:

1. the ban above — the poisoning source is the assembly, and it is removable;
2. the cartridge's own **exposure history** (§3.1 `0x16`): a cell that has been
   through a silicone event is de-rated or refused instead of quietly trusted;
3. limitation reporting — in an atmosphere that is genuinely full of silicone
   vapour (a workshop mid-sealant), a MOX instrument does not measure well, and
   the platform reports that rather than emitting an unqualified number.

## 6. Slot count and the "never stranded" rule

| Quantity | Reference base |
|----------|----------------|
| Slots | **8 identical** — left wall (slots 0–3), right wall (slots 4–7) |
| Slot pitch | 24 mm on Y stations 24 / 48 / 72 / 96 (a base parameter) |
| Interfaces per slot | keyed 5 V gas-cell socket + 3.3 V Qwiic port |
| Chamber | 116 × 108 × 51, board top as the floor, lid as the ceiling |
| Mux / ADC / 1-Wire channels | 8 / 2 / 1 |

Four slots at 24 mm pitch span 92 mm inside the 108 mm cavity depth, with 13 mm
of wall clearance behind each card for rear hardware. That is also what makes it
cheap to manufacture: one socket, one standoff, one repeat unit, eight times,
with no machined parts and no windows to align.

Scaling is a constant, not a redesign:

* a base with more slots is a wider base — one constants change plus a
  regenerate;
* beyond that, an **expansion port** (I²C, 1-Wire, 5 V, 3.3 V, trigger) drives a
  second head on the same sample line: in series for sequential chemistry, in
  parallel where the flow can spare it, with the split confirmed by CFD before
  it ships;
* a cell moves with the user, because the socket never changes between sizes
  and the calibration is on the cartridge.

Nothing in the host software depends on the slot count. A record is
`{slot, slot_index, cell_id, class, value, temperature, humidity, time}` plus
raw counts and module metadata, so an 8-slot base and a 32-slot base produce the
same schema.

## 7. Conformance checklist (for a module maker)

1. 2.54 mm keyed 1×6 header, pinout §2.1, straight on the card edge.
2. Outline ≤ 20 mm along the wall × ≤ 32 mm tall, reach ≤ 21 mm into the channel,
   upright and inward-facing (§4).
3. Sensing element on the inward face, centred near z = 33, with clear channel
   air in front of it. Rear pins need the 13 mm wall clearance the base provides.
4. Identity registered in the host slot map; an EEPROM is optional (reserved §3.1).
5. Output: 0–5 V analog on `AO`, or TTL serial 9600 8N1 on `DO`.
6. Power: ≤ 150 mA at 5 V, ≤ 50 mA at 3.3 V, inrush ≤ 300 mA.
7. Wetted materials per §5. No silicone, no PVC in the gas path.
8. Marked: part number, class, lot, polarity key.

## 8. Overhead of being standardised

Each slot adds only fixed, explainable hardware: a keyed 2.54 mm 1×6 socket, a
JST-SH Qwiic port, a 10 kΩ `DO` series resistor, and one shared 1-Wire pull-up
for the whole base. There is no per-slot EEPROM, mux or expander required by the
v1 build. Pricing is intentionally not published here; use the build BOMs when
sourcing parts.

## 9. As-built conformance (OSM-1 board)

`tools/verify_module_fit.py` checks the chamber, the socket contract and the
module database. The four gaps that existed before OSM-1 are closed on the board
in the tree:

| Earlier gap | As-built OSM-1 board |
|-------------|----------------------|
| `ID` pin on the gas-cell socket | 1×6 keyed socket at all eight slots (J2–J9), pin 6 `ID` on one shared 1-Wire bus with one 4.7 kΩ pull-up (GPIO 33), §2.1 |
| Qwiic port at every slot | J11–J18, one JST-SH 4-pin port per slot, each on its own TCA9548A channel |
| Series protection on `DO` | 10 kΩ in series per slot before the ESP32 GPIO |
| Analog inputs | two ADS1115s: U2 `0x48` slots 0–3, U8 `0x49` slots 4–7, with 10 k/10 k AO dividers |

The board outline fits the tray: `Edge.Cuts` carries the four boss cut-outs
(r = 4.3 mm) and `J1` sits at (14, 6) behind the Ø12 bulkhead hole. Both are
measured by `tools/verify_pcb.py`. The board is headless: no OLED is fitted.

What remains is on the module side, not the base board: three caliper numbers per
module are a module maker's conformance check, and a bare SMD part, a TO-5 can or
a Ø23.5 mm Winsen can goes on an OSM-1 carrier. The base's side-wall sockets take
an upright carrier with its pin line front-to-back and its face toward the
channel; §4 is where that rule lives.
