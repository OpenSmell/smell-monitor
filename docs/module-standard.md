# OpenSmell Module Standard v1 (OSM-1)

Status: **as built (OSM-1).** One SKU implements every rule below: eight uniform
keyed 1×6 sockets (J2–J9) and eight Qwiic ports (J11–J18), two ADS1115s, 10 kΩ
`DO` series resistors and a shared 1-Wire `ID` bus. A sealed SSD1306 display in a
shallow bezel on the fixed front wall (master I²C `0x3C`, 27 × 13 mm window at
shell (61,45)) and four front-panel buttons — MEASURE/OK (88,49), MENU/BACK
(100,49), BOOT (88,39) and RESET (100,39) — are **non-slot hardware**. One sealed
6 mm grommet at (82,45) carries their harnesses; the lid is plain with four M3
screws and no wires or holes. They do not change the slot contract. §9 records
the as-built conformance. `mechanical/standard.py` carries the same rules as
data, and `tools/verify_module_fit.py` checks the chamber, the socket contract
and the module database against it.

## 1. Scope

The standard fixes the layer underneath the sensor:

* the **gas physics** — every cell sees a defined sample, in a defined order,
  with no memory of the previous one;
* the **slot** — one physical and electrical contract, so a cell designed by
  another maker plugs into a base built today;
* the **identity** — the host knows which slot holds which module and what it
  has been through, so calibration and aging are handled in software.

Sensor chemistry is selected by the user; no specific sensor is required here.

## 2. There is one slot, and it is repeated

Every slot carries **both** interfaces, side by side on the same footprint:

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
| 6 | `ID` | 1-Wire, shared bus; identity device (§3) |

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
Firmware does **not** enumerate per-slot ROMs: all eight pins are in parallel,
so one device on that bus could not say which slot it occupies. The `.osmell`
identity and calibration fields are emitted as null by firmware and attached by
Osmograph (or any host) from its slot map. The host owns slot map, module type,
specification and calibration.

Raw `ao`, `adc` and `do_` values stay canonical in every record. Osmograph pushes
a versioned interpretation profile; firmware computes additive derived fields
only when a profile is present and marks them `derived`. Without a profile,
derived fields are null and the device keeps its raw-only behavior. Local
inference is bounded arithmetic and threshold logic; heavy ML is host-side.

Every slot stays electrically identical, any module goes in any slot, and the
host owns the meaning. No extra GPIO, expander or per-slot mux was added to
solve a mapping problem in hardware.

### 3.1 Where calibration lives

Calibration and exposure history are **host-side data in v1**. The host keeps a
slot map (part number, class, calibration date, accumulated hours) and writes it
into each `.osmell` record. Qwiic modules can additionally answer an I²C
`WHO_AM_I` probe through their own mux channel.

Calibration data by class:

| Class | Contents |
|-------|----------|
| MOX | `R0` in clean air, log-log slope, the gas it was characterised against, T/RH of that measurement |
| EC | sensitivity nA/ppm, zero offset, temperature coefficient |
| NDIR | factory span check value, pressure reference |
| T/RH | manufacturer ID plus last field check |
| pH/ISFET | two-point buffer calibration (offset at pH 7, slope mV/pH), last buffer date and temperature |

### 3.2 Behaviour with no identity device

No identity device is required. A user who solders an inexpensive MQ cell onto a
blank board and plugs it in gets data immediately. The record carries the slot index
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

**There is no chamber window or baffle.** The sealed SSD1306 display sits in a
shallow bezel on the fixed front wall, with its window and gasket outside the
sample path and a single harness grommet at (82,45); it is non-slot hardware and
does not open into the chamber. The lid is a plain flat plate. A cartridge
plugged into its socket already has unobstructed air in the channel. The standard
constrains the cartridge's outline, reach and connector.

A bare MQ-135 card (32 × 20 mm, can Ø19, element 16 mm from its header) *is* a
conforming cartridge once its header is re-pinned to §2.1. TO-5 cans, Ø23.5 mm
Winsen cans, bare SMD parts and piezo film use the **OpenSmell carrier**: one
blank PCB that presents this socket and this sensor zone.

## 5. Wetted-material rules

The gas path is for **inert gas only**. The classic MOX field death is
**silicone poisoning**: silicone vapour decomposes on the hot SnO₂ surface into
a silica layer that permanently kills the response. It comes from the assembly,
not from the sample. Conformal coat is acrylic or polyurethane; never silicone.
The front-bezel window gasket and harness grommet are outside the wetted path.

**Banned anywhere the gas touches:** silicone (sealant, adhesive, grease,
tubing, wire insulation, conformal coat), PVC tubing or insulation, bare zinc,
paper or card, foam.

**Allowed:** PTFE, PFA/FEP, PVDF, borosilicate glass, 316 stainless, gold- or
nickel-plated contacts, PTFE-insulated wire, non-silicone epoxy outside the path.

**Gas path:** a **thin woven PTFE mesh** filter (hydrophobic, WEP ≥ 350 mbar)
with a 5–20 µm particulate pre-screen, spanning the full inlet cross-section so
no stream bypasses it; cleanable, and replaced only if torn or clogged (blueprint
§3.6).

**No carbon is placed in series with the sample.** Carbon removes the analytes
along with interferents. Carbon belongs on a *reference-air* path, never in the
sample path; blueprint §6.3 forbids adsorbing media there. Silicone poisoning is
controlled by:

1. the material ban above — the poisoning source is in the assembly and is removable;
2. the host slot map (§3.1) — exposure hours and calibration are recorded, and a
   cell that has been through a silicone event is de-rated or refused by the host.

## 6. Slot count

| Quantity | Reference base |
|----------|----------------|
| Slots | **8 identical** — left wall (slots 0–3), right wall (slots 4–7) |
| Slot pitch | 24 mm on Y stations 24 / 48 / 72 / 96 (a base parameter) |
| Interfaces per slot | keyed 5 V gas-cell socket + 3.3 V Qwiic port |
| Chamber | 116 × 108 × 51, board top as the floor, lid as the ceiling |
| Mux / ADC / 1-Wire channels | 8 / 2 / 1 |

The front-wall SSD1306 (`0x3C` on the master bus), its bezel window and gasket,
the single harness grommet and the four front-panel buttons are outside the slot
count and outside the sample path. They add no socket, mux channel or wetted
surface; the lid stays plain.

Four slots at 24 mm pitch span 92 mm inside the 108 mm cavity depth, with 13 mm
of wall clearance behind each card for rear hardware. That is also what makes the
repeat unit simple: one socket, one standoff and one repeat unit, eight times,
with no machined parts and no chamber windows to align.

A cartridge moves with the user: the socket is identical in all eight slots and
the host slot map carries its calibration. Each record carries
`slot`, `slot_index`, `cell_id`, `class`, value, temperature, humidity and time,
plus raw counts and module metadata.

## 7. Conformance checklist (for a module maker)

1. 2.54 mm keyed 1×6 header, pinout §2.1, straight on the card edge.
2. Outline ≤ 20 mm along the wall × ≤ 32 mm tall, reach ≤ 21 mm into the channel,
   upright and inward-facing (§4).
3. Sensing element on the inward face, centred near z = 33, with clear channel
   air in front of it. Rear pins need the 13 mm wall clearance the base provides.
4. Identity and calibration registered in the host slot map (§3.1).
5. Output: 0–5 V analog on `AO`, or TTL serial 9600 8N1 on `DO`.
6. Power: ≤ 150 mA at 5 V, ≤ 50 mA at 3.3 V, inrush ≤ 300 mA.
7. Wetted materials per §5. Inert gas path only; no silicone, no PVC, acrylic or
   polyurethane conformal coat.
8. Marked: part number, class, lot, polarity key.

The fixed front-panel UI is outside this checklist: SSD1306 at master `0x3C` in
a shallow sealed bezel (27 × 13 mm window at shell (61,45)), MEASURE/OK,
MENU/BACK, BOOT and RESET all reachable with the lid closed, and one sealed 6 mm
grommet at (82,45). It adds no slot and does not alter the module contract.

## 8. Per-slot hardware

Each slot carries a keyed 2.54 mm 1×6 socket, a JST-SH Qwiic port, a 10 kΩ `DO`
series resistor, and one shared 1-Wire pull-up for the whole base. There is no
per-slot EEPROM, mux or expander. Use the build BOMs when sourcing parts.

## 9. As-built conformance (OSM-1 board)

`tools/verify_module_fit.py` checks the chamber, the socket contract and the
module database. The as-built board implements:

| Item | As-built OSM-1 board |
|------|----------------------|
| `ID` pin on the gas-cell socket | 1×6 keyed socket at all eight slots (J2–J9), pin 6 `ID` on one shared 1-Wire bus with one 4.7 kΩ pull-up (GPIO 16), §2.1 |
| Qwiic port at every slot | J11–J18, one JST-SH 4-pin port per slot, each on its own TCA9548A channel |
| Series protection on `DO` | 10 kΩ in series per slot before the ESP32 GPIO |
| Analog inputs | two ADS1115s: U2 `0x48` slots 0–3, U8 `0x49` slots 4–7, with 10 k/10 k AO dividers |

The board outline fits the tray: `Edge.Cuts` carries the four boss cut-outs
(r = 4.3 mm) and `J1` sits at (14, 6) behind the Ø12 bulkhead hole. Both are
measured by `tools/verify_pcb.py`. The SSD1306 display is fixed front-wall
hardware on the master I²C bus at `0x3C`; its bezel window and gasket and the
single harness grommet stay outside the sample path, and it occupies no OSM-1
slot. The lid carries four M3 screws and no wires or holes.

What remains is on the module side, not the base board: three caliper numbers per
module are a module maker's conformance check, and a bare SMD part, a TO-5 can or
a Ø23.5 mm Winsen can goes on an OSM-1 carrier. The base's side-wall sockets take
an upright module with its pin line front-to-back and its face toward the
channel; §4 is where that rule lives.
