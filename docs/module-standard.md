# OpenSmell Module Standard v1 (OSM-1)

Status: **draft — target revision L.** The module rules below are settled; the
board in the tree is still the as-built revision that predates them (§9 lists
exactly what does not match yet). `mechanical/standard.py` is the same rules as
data, and `tools/verify_module_fit.py` checks the chamber, the socket contract
and the module database against it and prints the remaining gap — so this
document and the hardware cannot drift apart quietly.

## 1. Why a standard exists

Supporting every module on the market is not possible: there is one mechanical
socket (2.54 mm) and a wide range of board sizes and pin orders. Sensors are the
part that changes — a 2026 MOX cell will be replaced several times inside the
life of one base. What has to stay stable is the layer underneath:

* the **gas physics** — every cell sees a defined sample, in a defined order,
  with no memory of the previous one;
* the **slot** — one physical and electrical contract, so a cell designed next
  year by someone else plugs into a base built today;
* the **identity** — the base knows what is plugged in and what it has been
  through, so calibration and aging are handled in software.

Everything below serves those three. No specific sensor appears here on purpose.

## 2. There is one slot, and it is repeated

A slot is not "analog" or "digital". Every slot carries **both** interfaces over
the same window in the plate:

| Interface | Serves | Connector | Rail |
|-----------|--------|-----------|------|
| **Gas cell** | anything that outputs an analog voltage or TTL serial: MOX (SnO₂), electrochemical, NDIR with a Vout, catalytic, PID | 2.54 mm keyed 1×6 header | **5 V** (heater capable) |
| **I²C port** | anything with its own converter: NDIR CO₂, T/RH, VOC index, particulate | **Qwiic / STEMMA QT**, JST-SH 1.0 mm 4-pin, plus 0.1 in pads in parallel | **3.3 V** |

The user fills slots with whatever chemistry the job needs, in any mix, and
never has to know which slot is "the analog row". The module's identity decides
how the base talks to it.

The one thing the mix cannot change is physics: **the chamber is a cascade, not
eight parallel chambers.** The upstream row sees fresh sample; the downstream
row sees sample that has already passed the upstream cells. So the base reports
each record with its slot index and its position in the flow, and the software
models the depletion. Put the cells you trust most upstream.

### 2.1 Gas cell pinout (keyed 1×6, 2.54 mm)

| Pin | Net | Notes |
|-----|-----|-------|
| 1 | `+5V` | 5 V, ≤ 150 mA per slot for the heater |
| 2 | `GND` | |
| 3 | `AO` | cell output, **0–5 V**, divided 10k/10k into the ADC |
| 4 | `DO` | comparator output **or** TTL serial RX — a plain 3.3 V GPIO |
| 5 | `3V3` | 3.3 V, ≤ 50 mA, for the cell's own converter |
| 6 | `ID` | 1-Wire, the cartridge's identity EEPROM (§3) |

A 2.54 mm plug with no 6th pin is still a conforming cell: the base reads the ID
as absent and applies slot defaults (§3.4).

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

## 3. Identity: the cartridge EEPROM

A **1-Wire EEPROM, 1 kbit** (DS2431 / AT21CS01 class) on the `ID` pin. One pin
on the base serves every slot because every 1-Wire device carries a unique
64-bit ROM — no address scheme, no mux, no configuration. Cost is $0.15–0.50
per cartridge depending on the part; a ROM-only identity device halves it if
calibration is kept on the host.

The EEPROM is required on gas-cell cartridges. A Qwiic module does not need one:
it answers an I²C probe with its own `WHO_AM_I`, which is the identity its maker
already gives it.

### 3.1 Memory map

| Offset | Size | Contents |
|--------|------|----------|
| `0x00` | 4 | magic `"OSM1"` |
| `0x04` | 1 | standard revision (1) |
| `0x05` | 1 | kind (1 gas cell, 2 I²C module) |
| `0x06` | 1 | class (1 MOX, 2 EC, 3 NDIR, 4 PID, 5 T/RH, 6 PM, 7 other) |
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

### 3.2 Why calibration travels with the cell

MOX drift and aging is the field's dominant accuracy problem, and the common
practice is to recalibrate the *base* against a bottle of gas. If calibration and
exposure history travel **with the cell**, then:

* a lab can move cells between bases and keep its accuracy;
* the host can schedule a re-calibration from accumulated hours, not guesswork;
* a maker can ship a characterised cell and be judged on its calibration;
* a used or poisoned cell can be refused or de-rated instead of quietly
  corrupting a result.

This is the TEDS idea from IEEE 1451, in 1 kbit and one wire.

### 3.3 Calibration blob per class (v1)

| Class | Contents |
|-------|----------|
| MOX | `R0` in clean air, log-log slope, the gas it was characterised against, T/RH of that measurement |
| EC | sensitivity nA/ppm, zero offset, temperature coefficient |
| NDIR | factory span check value, pressure reference |
| T/RH | manufacturer ID plus last field check |

### 3.4 Behaviour with no ID (the "just works" rule)

A missing, blank or unreadable EEPROM is **not** an error. The base applies that
slot's defaults (MOX class, 5 V, 150 mA), reads the slot as a generic cell, and
marks it uncalibrated for the host. A user who solders a $2 MQ cell onto a blank
cartridge and plugs it in gets data immediately — flagged as uncalibrated rather
than silently trusted.

## 4. Mechanical envelope

The cell is mounted **flat**: the card lies parallel to the board, sensing face
up, directly under its window, and comes out upward. Flat is not cosmetic:

* a MOX can's gas inlet is its **end face**, not its barrel. Standing a card in
  a socket points the inlet sideways at its neighbour instead of at the window;
* standing cards needed 40–48 mm of height where only 37 mm exists under the
  plate, so a 32–40 mm MQ card passed straight through the baffle. Flat, the
  same card is 25 mm tall and fits with room to spare.

| Quantity | Value |
|----------|-------|
| Cartridge outline | ≤ **22 mm** across the row × ≤ **40 mm** along the flow |
| Cartridge height (its own board plus the tallest cell) | ≤ **26 mm** |
| On the socket | the cartridge sits ≈8.5 mm up, so its top lands ≈33 mm above the chamber floor — about **4 mm under the plate** at 37 mm |
| Sensing element | centred in a **20 × 20 mm** zone, **16 mm downstream of the connector face**, on the slot centre line |
| Slot pitch | **24 mm** (cartridge 22 mm + 2 mm) |
| Window in the plate | **20 × 20 mm**, i.e. exactly the sensor zone |
| Keying | pin-1 chamfer plus a polarising slot in the socket wall |

The base socket is a **vertical 2.54 mm receptacle**; the cartridge carries a
**right-angle male header** on its edge. The cartridge therefore lies flat and
comes out straight up. **That makes the baffle plate the service lid**: with the
cartridge ~4 mm under it, a swap is an open-lid operation — remove the plate,
lift the cartridge. There is no in-plane room for a slide-out cartridge in a
two-row layout (a 40 mm cartridge would need 40 mm of pull room it does not
have), so the enclosure, not the socket, is what has to make a swap tool-free to
satisfy U1 of the blueprint.

Fixing the sensor zone at 16 mm downstream of the connector face is what makes
one window position work for every cartridge. The window **is** that zone: a
20 × 20 mm opening in the plate, centred 16 mm downstream of the socket line.

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

**Gas path:** a filter whose spec is set by blueprint §3.6 — hydrophobic PTFE
media (WEP ≥ 350 mbar) behind a 5–20 µm particulate pre-filter, pleated to
≥ 70 cm², spanning the **full lane cross-section** so no stream bypasses it.

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
| Slots | **8** — two rows of four, upstream row first |
| Slot pitch | 24 mm |
| Interfaces per slot | keyed 5 V gas-cell socket + 3.3 V Qwiic port |
| Windows | 8 × 20 × 20 mm, one per slot |
| Mux / ADC / 1-Wire channels | 8 / 2 / 1 |

Four slots at a 24 mm pitch span 96 mm inside the existing 106 mm cavity, so
uniformity costs **no size at all**: the same box, built from one repeat unit
instead of two different ones. That is also what makes it cheap to manufacture —
one socket, one window, one pocket, repeated eight times.

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

1. 2.54 mm keyed 1×6 header, pinout §2.1, right-angle on the card edge.
2. Outline ≤ 22 × 40 mm, ≤ 26 mm tall in the flat pose (§4).
3. Sensing element centred inside the 20 × 20 mm zone 16 mm downstream of the
   connector face.
4. EEPROM per §3.1, checksum valid, `kind` and `class` correct.
5. Output: 0–5 V analog on `AO`, or TTL serial 9600 8N1 on `DO`.
6. Power: ≤ 150 mA at 5 V, ≤ 50 mA at 3.3 V, inrush ≤ 300 mA.
7. Wetted materials per §5. No silicone, no PVC in the gas path.
8. Marked: part number, class, lot, polarity key.

## 8. Cost of being standardised

| Item | Per unit |
|------|----------|
| Qwiic / STEMMA QT port (JST-SH 4-pin) | $0.15–0.25 |
| Keyed 2.54 mm 1×6 socket | $0.10 |
| 10 kΩ series resistor on `DO` | $0.005 |
| 0.1 in pads in parallel | — |
| 1-Wire pull-up (one, for the whole base) | — |
| **Base overhead per slot** | **≈ $0.30** |
| 1-Wire EEPROM — *on the cartridge, not the base* | $0.15–0.50 |

Eight slots therefore add roughly $2.50 to the base. The cost that matters sits
on the module side, and it is one EEPROM, which is what makes per-cell
calibration possible.

## 9. What the current board does not match yet

`tools/verify_module_fit.py` reports these against the as-built revision; they
are the target revision L work, in this order:

| Gap | As-built | Standard |
|-----|----------|----------|
| `ID` pin on the gas-cell socket | 5 pins, no ID | 6 pins, §2.1 |
| Qwiic port at every slot | digital row only, 0.1 in headers | one JST-SH port per slot |
| Slot pitch | 26 mm analog / 21 mm digital | uniform 24 mm |
| Window | 22 × 18 and 18 × 16 mm | 20 × 20 mm at +16 mm offset |
| Mounting pose | vertical card sockets | right-angle headers, flat cartridges |
| Series protection on `DO` | direct to the GPIO | 10 kΩ in series |
| Analog inputs | one 4-channel ADC | two (8 slots) |
