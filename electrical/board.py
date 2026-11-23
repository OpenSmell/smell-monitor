#!/usr/bin/env python3
"""OpenSmell v1.1 board model - components and nets (single source).

`interface.py` fixes the *contract* (slot pinout, I2C map, GPIO map, rails).
This module turns that contract plus the static topology of blueprint section 5
into an explicit **netlist**: the parts fitted to the board and the net every
pin lands on. It is the common origin for three deliverables, so they cannot
drift from each other:

  * the generated KiCad schematic   (`electrical/gen_schematic.py`)
  * the generated PCB               (`electrical/gen_pcb.py` placement, then
                                     `electrical/route_pcb.py` to route it)
  * the BOM                         (KiCad BOM export; `bom.csv` is regenerated,
                                     never hand-counted - hand counts drift)

One slot design, repeated (OSM-1): every slot is a 1x6 keyed gas-cell socket
plus a Qwiic port.  Analog output goes to one of eight ADS1115 channels; the
digital output goes through a series resistor to the MCU; identity is a single
shared 1-Wire bus.  I2C modules hang off their slot's TCA9548A segment.

Design notes that are *choices*, not contract, are marked ``CALL:`` and listed
in the docstring of ``DECISIONS`` so a reviewer can veto them cheaply.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "mechanical"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import interface as IF  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
KICAD_SYM = r"C:\Program Files\KiCad\10.0\share\kicad\symbols"

# ---------------------------------------------------------------------------
# model containers
# ---------------------------------------------------------------------------
PARTS = {}          # ref -> {"lib", "value", "footprint", "dnp"}
NETS = {}           # net -> [(ref, pin), ...]
_PIN_CACHE = {}     # libId -> [(number, name), ...]
_PIN_MIRROR = {}    # libId -> {name: [numbers]}

# Qwiic / STEMMA QT: JST-SH 1.0 mm, top entry (SparkFun's standard part).
QWIIC_FP = "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal"


def part(ref, lib, value, footprint):
    """Register a fitted component."""
    if ref in PARTS:
        raise ValueError("duplicate ref %s" % ref)
    PARTS[ref] = {"lib": lib, "value": value, "footprint": footprint}
    return ref


def connect(net, ref, pin):
    """Connect one pin (unambiguous) to a net."""
    NETS.setdefault(net, []).append((ref, str(pin)))


def _lib_of(ref):
    return PARTS[ref]["lib"]


_n = {"R": 0, "C": 0}


def new_r(value):
    _n["R"] += 1
    ref = "R%d" % _n["R"]
    part(ref, "Device:R", value, "Resistor_SMD:R_0603_1608Metric")
    return ref


def new_c(value):
    _n["C"] += 1
    ref = "C%d" % _n["C"]
    part(ref, "Device:C", value, "Capacitor_SMD:C_0603_1608Metric")
    return ref


def pull(net_a, net_b, value="10k"):
    """A two-terminal passive bridging two nets; returns its ref."""
    r = new_r(value)
    connect(net_a, r, "1")
    connect(net_b, r, "2")
    return r


def decouple(net, value="100nF"):
    c = new_c(value)
    connect(net, c, "1")
    connect("GND", c, "2")
    return c


# ---------------------------------------------------------------------------
# pin data: resolve a library symbol's pins (handles `extends`)
# ---------------------------------------------------------------------------
def _load_kicad_pins(lib_id):
    """Return [(number, name)] for `lib_id`, resolving `extends` chains."""
    if lib_id in _PIN_CACHE:
        return _PIN_CACHE[lib_id]
    nick, entry = lib_id.split(":", 1)
    path = os.path.join(KICAD_SYM, nick + ".kicad_sym")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    from kiutils.symbol import SymbolLib
    sl = SymbolLib.from_file(path)
    by_name = {s.entryName: s for s in sl.symbols}
    seen = set()
    sym = by_name.get(entry)
    while sym is not None and getattr(sym, "extends", None) and sym.entryName not in seen:
        seen.add(sym.entryName)
        sym = by_name.get(sym.extends)
    if sym is None:
        raise KeyError("%s not in %s" % (entry, nick))
    out = []

    def rec(x):
        for p in getattr(x, "pins", None) or []:
            out.append((str(p.number), p.name))
        for u in getattr(x, "units", None) or []:
            rec(u)
    rec(sym)
    _PIN_CACHE[lib_id] = out
    _PIN_MIRROR[lib_id] = {}
    for num, nm in out:
        _PIN_MIRROR[lib_id].setdefault(nm, []).append(num)
    return out


def pin_numbers(lib_id):
    """All pins of a library symbol, from the installed KiCad library."""
    return _load_kicad_pins(lib_id)


def pin_numbers_for(ref):
    return pin_numbers(_lib_of(ref))


def connect_name(net, ref, name):
    """Connect the single pin of `ref` named `name` to `net`."""
    matches = [n for n, nm in pin_numbers(_lib_of(ref)) if nm == name]
    if not matches:
        raise KeyError("%s (%s) has no pin named %r" % (ref, name, _lib_of(ref)))
    if len(matches) > 1:
        raise ValueError("%s has %d pins named %r; use connect_all()"
                         % (ref, len(matches), name))
    connect(net, ref, matches[0])


def connect_all(net, ref, name):
    """Connect *every* pin of `ref` named `name` (e.g. the several GNDs)."""
    matches = [n for n, nm in pin_numbers(_lib_of(ref)) if nm == name]
    if not matches:
        raise KeyError("%s (%s) has no pin named %r" % (ref, name, _lib_of(ref)))
    for m in matches:
        connect(net, ref, m)


# ---------------------------------------------------------------------------
# human-readable record of every judgement call made in this netlist
# ---------------------------------------------------------------------------
DECISIONS = [
    "OSM-1 slot: every position is one 1x6 keyed socket (+5V, GND, AO, DO, "
    "3V3, ID) plus one Qwiic port.  There is no analog/digital bank split, so "
    "a module cannot be plugged into the wrong row.  Contract owner: "
    "interface.SLOT / QWIC.",
    "Eight analog outputs need two ADS1115s (0x48 / 0x49); the second one is "
    "U8 and its ADDR pin is tied to +3V3.  The pair is cheaper and simpler "
    "than an 8-channel external mux and keeps every channel single-ended.",
    "Eight digital outputs fit the WROOM directly (GPIO 17..32 plus 16 for the "
    "shared 1-Wire ID bus), so the OSM-1 build carries no GPIO expander.  "
    "This is checked by interface.build_pinmap and verify_electrical.",
    "1-Wire ID: all eight slot ID pins are one open-drain bus with a single "
    "4.7k pull-up.  v1 firmware does not enumerate per-slot ROMs; the "
    "eeprom_id/calibration fields stay null and the host attaches that meaning "
    "to each slot.  An optional per-module EEPROM map is reserved, not required.",
    "DO series 10k per slot: a module's open-collector/TTL output can be "
    "pulled to 5 V by a fault; the series resistor bounds the current into "
    "the 3.3 V GPIO.  Analog threshold behaviour is unaffected.",
    "U3 CH340C USB-UART bridge: the module-side contract is JSON over a "
    "serial port, and native USB is not exposed by the WROOM footprint.  V3 "
    "is the bridge's own regulator output and is never tied to +3V3.",
    "BOOT (GPIO0) + RESET (EN) + MEASURE (GPIO23) buttons: no auto-reset "
    "transistors, so flashing = hold BOOT, tap RESET.",
    "USB-C CC1/CC2 5.1k pulldowns (R1, R2): required to draw VBUS from a "
    "C-to-C cable or any Type-C source.",
    "I2C pull-ups 4.7k on the master bus and on every TCA9548A channel.  A "
    "Qwiic module normally brings its own pull-ups; the board's per-channel "
    "pair keeps a bare module working without loading any other segment.",
    "AO input divider 10k/10k: maps the 0-5 V slot output to <=2.5 V at the "
    "ADS1115, one divider per slot.",
    "The on-board OLED is not fitted: v1 is headless and the UI is Osmograph. "
    "Removing it also removes the only display library dependency.",
]

N = IF.N_SLOTS


def build():
    """Populate PARTS/NETS. Idempotent (module-level single build)."""
    if PARTS:
        return

    # --- actives -----------------------------------------------------------
    part("U1", "RF_Module:ESP32-WROOM-32E", "ESP32-WROOM-32E",
         "RF_Module:ESP32-WROOM-32E")
    part("U2", "Analog_ADC:ADS1115IDGS", "ADS1115", 
         "Package_SO:MSOP-10_3x3mm_P0.5mm")
    part("U3", "Interface_USB:CH340C", "CH340C", "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm")
    part("U4", "Interface_Expansion:TCA9548APWR", "TCA9548A",
         "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm")
    part("U5", "Sensor_Humidity:SHT31-DIS", "SHT31-DIS-B",
         "Sensor_Humidity:Sensirion_DFN-8-1EP_2.5x2.5mm_P0.5mm_EP1.1x1.7mm")
    part("U7", "Regulator_Linear:AMS1117CD-3.3", "AMS1117-3.3",
         "Package_TO_SOT_SMD:SOT-223-3_TabPin2")
    part("U8", "Analog_ADC:ADS1115IDGS", "ADS1115",
         "Package_SO:MSOP-10_3x3mm_P0.5mm")

    part("J1", "Connector:USB_C_Receptacle_USB2.0_16P", "USB_C_16P",
         "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal")
    # Eight identical sensing sockets: J2..J5 = downstream row, J6..J9 =
    # upstream row.  Order is slot 0..7, matching the chamber contract.
    for k in range(N):
        part("J%d" % (2 + k), "Connector_Generic:Conn_01x06", "1x06 female",
             "Connector_PinSocket_2.54mm:PinSocket_1x06_P2.54mm_Vertical")
    part("J10", "Connector_Generic:Conn_01x02", "JST-PH 2P fan",
         "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical")
    # One Qwiic port per slot, J11..J18.
    for k in range(N):
        part("J%d" % (11 + k), "Connector_Generic:Conn_01x04", "Qwiic",
             QWIIC_FP)

    part("Q1", "Transistor_FET:Q_NMOS_GSD", "AO3400A", "Package_TO_SOT_SMD:SOT-23")
    part("Q2", "Transistor_BJT:Q_NPN_BCE", "MMBT3904", "Package_TO_SOT_SMD:SOT-23")
    part("D1", "Device:D", "SS14", "Diode_SMD:D_SOD-123")
    part("BZ1", "Device:Buzzer", "MBT-12A05", "Buzzer_Beeper:Buzzer_12x9.5RM7.6")
    part("LED1", "Device:LED", "Red", "LED_SMD:LED_0603_1608Metric")
    part("SW1", "Switch:SW_Push", "MEASURE", "Button_Switch_SMD:SW_SPST_TL3342")
    part("SW2", "Switch:SW_Push", "BOOT", "Button_Switch_SMD:SW_SPST_TL3342")
    part("SW3", "Switch:SW_Push", "RESET", "Button_Switch_SMD:SW_SPST_TL3342")

    # --- U1 ESP32 ----------------------------------------------------------
    connect_name("+3V3", "U1", "VDD")
    connect_all("GND", "U1", "GND")
    connect_name("EN", "U1", "EN")
    connect_name("BOOT", "U1", "IO0")
    connect_name("I2C_SDA", "U1", "IO21")
    connect_name("I2C_SCL", "U1", "IO22")
    connect_name("FAN_PWM", "U1", _gpio_name("FAN_PWM"))
    connect_name("BUZZER", "U1", _gpio_name("BUZZER"))
    connect_name("LED", "U1", _gpio_name("LED"))
    connect_name("MEASURE", "U1", _gpio_name("BUTTON"))
    connect_name("UART_TX", "U1", "TXD0/IO1")
    connect_name("UART_RX", "U1", "RXD0/IO3")
    connect_name("ONEWIRE", "U1", _gpio_name("ONEWIRE"))
    # DO lines and the shared 1-Wire bus come from the frozen pin map.
    for i in range(N):
        connect_name("DO%d" % i, "U1", _gpio_name("DO%d" % i))

    # --- U2 / U8 ADS1115 ---------------------------------------------------
    # Channels 0..3 on U2 (0x48), channels 4..7 on U8 (0x49).
    for ref, addr, base in (("U2", "GND", 0), ("U8", "+3V3", 4)):
        connect_name("GND", ref, "GND")
        connect_name("+3V3", ref, "VDD")
        connect_name("I2C_SDA", ref, "SDA")
        connect_name("I2C_SCL", ref, "SCL")
        connect_name(addr, ref, "ADDR")
        for i in range(4):
            connect_name("AIN%d" % (base + i), ref, "AIN%d" % i)

    # --- U3 CH340C ---------------------------------------------------------
    # Powered from 5 V (per CH340C datasheet: VCC=5 V, V3 = internal 3.3 V
    # regulator output, decoupled to GND).  V3 must NOT be tied to the +3V3
    # rail: it is a power_out, and the AMS1117 VO already drives +3V3.
    connect_name("GND", "U3", "GND")
    connect_name("+5V", "U3", "VCC")
    connect_name("U3_V3", "U3", "V3")
    connect_name("UART_TX", "U3", "RXD")       # module TX <- host RX side
    connect_name("UART_RX", "U3", "TXD")
    connect_name("D_P", "U3", "UD+")
    connect_name("D_N", "U3", "UD-")

    # --- U4 TCA9548A -------------------------------------------------------
    connect_name("+3V3", "U4", "VCC")
    connect_name("GND", "U4", "GND")
    connect_name("I2C_SDA", "U4", "SDA")
    connect_name("I2C_SCL", "U4", "SCL")
    connect_name("MUX_RESET", "U4", "~{RESET}")
    for a in ("A0", "A1", "A2"):
        connect_name("GND", "U4", a)           # 0x70
    for i in range(N):
        connect_name("SD%d" % i, "U4", "SD%d" % i)
        connect_name("SC%d" % i, "U4", "SC%d" % i)

    # --- U5 SHT31 ----------------------------------------------------------
    connect_name("+3V3", "U5", "VDD")
    connect_all("GND", "U5", "VSS")
    connect_name("I2C_SDA", "U5", "SDA")
    connect_name("I2C_SCL", "U5", "SCL")
    connect_name("GND", "U5", "ADDR")          # 0x44
    connect_name("+3V3", "U5", "~{RESET}")

    # --- U7 LDO ------------------------------------------------------------
    connect_name("GND", "U7", "GND")
    connect_name("+5V", "U7", "VI")
    connect_name("+3V3", "U7", "VO")

    # --- J1 USB-C ----------------------------------------------------------
    for p in ("A4", "A9", "B4", "B9"):
        connect("+5V", "J1", p)
    for p in ("A1", "A12", "B1", "B12", "SH"):
        connect("GND", "J1", p)
    connect("D_P", "J1", "A6"); connect("D_P", "J1", "B6")
    connect("D_N", "J1", "A7"); connect("D_N", "J1", "B7")
    for cc in ("A5", "B5"):
        r = new_r("5.1k")
        net = "CC1" if cc == "A5" else "CC2"
        connect(net, "J1", cc)
        connect(net, r, "1")
        connect("GND", r, "2")

    # --- sensing slots (OSM-1) ---------------------------------------------
    # Slot k: 6-pin socket J(2+k), Qwiic J(11+k).  Build AO first, then DO, so
    # the reference designators stay grouped by function (dividers R3..R18,
    # DO series R19..R26) and a reviewer can read the schematic by block.

    # analog output + 2:1 divider, slots 0..7
    for k in range(N):
        raw = "SLOT%d_AO" % k
        connect(raw, "J%d" % (2 + k),
                IF.SLOT.index("AO") + 1)
        _divider(raw, "AIN%d" % k)

    # digital output + 10k series, slots 0..7
    for k in range(N):
        raw = "SLOT%d_DO" % k
        connect(raw, "J%d" % (2 + k),
                IF.SLOT.index("DO") + 1)
        r = new_r("10k")
        connect(raw, r, "1")
        connect("DO%d" % k, r, "2")

    # rails + identity on the 6-pin socket, and the slot's Qwiic port
    for k in range(N):
        ref = "J%d" % (2 + k)
        for pin_no, name in enumerate(IF.SLOT, start=1):
            if name == "+5V":
                connect("+5V", ref, pin_no)
            elif name == "GND":
                connect("GND", ref, pin_no)
            elif name == "3V3":
                connect("+3V3", ref, pin_no)
            elif name == "ID":
                connect("ONEWIRE", ref, pin_no)
        qref = "J%d" % (11 + k)
        for name, pin_no in zip(IF.QWIC, (1, 2, 3, 4)):
            net = {"GND": "GND", "3V3": "+3V3",
                   "SDA": "SD%d" % k, "SCL": "SC%d" % k}[name]
            connect(net, qref, pin_no)

    # --- fan (J10) + Q1 ----------------------------------------------------
    connect("+5V", "J10", "1")
    connect("FAN_NEG", "J10", "2")
    connect("FAN_PWM", "Q1", "1")              # G  (Q_NMOS_GSD: 1=G,2=S,3=D)
    connect("GND", "Q1", "2")                  # S
    connect("FAN_NEG", "Q1", "3")              # D
    pull("FAN_PWM", "GND")                     # gate held low until firmware

    # --- buzzer + Q2 -------------------------------------------------------
    connect("+5V", "BZ1", "1")
    connect("BUZZ_NEG", "BZ1", "2")
    # D1 catches the buzzer coil's inductive kick when Q2 turns off, so the
    # spike cannot couple into the shared 5 V / ground used by the ADCs.
    connect("+5V", "D1", "1")                  # K
    connect("BUZZ_NEG", "D1", "2")              # A
    connect("BUZZ_NEG", "Q2", "2")             # C
    connect("GND", "Q2", "3")                  # E
    r = new_r("10k"); connect("BUZZER", r, "1"); connect("BUZZ_BASE", r, "2")
    connect("BUZZ_BASE", "Q2", "1")            # B
    pull("BUZZ_BASE", "GND")

    # --- LED ---------------------------------------------------------------
    # GPIO -> 330R -> anode; cathode -> GND  (LED1: 1=K, 2=A)
    lr = new_r("330")
    connect("LED", lr, "1")
    connect("LED_A", lr, "2")
    connect("LED_A", "LED1", "2")
    connect("GND", "LED1", "1")

    # --- buttons -----------------------------------------------------------
    connect("MEASURE", "SW1", "1"); connect("GND", "SW1", "2")
    connect("BOOT", "SW2", "1");    connect("GND", "SW2", "2")
    connect("EN", "SW3", "1");      connect("GND", "SW3", "2")

    # --- pull-ups / housekeeping -------------------------------------------
    pull("I2C_SDA", "+3V3", "4.7k")
    pull("I2C_SCL", "+3V3", "4.7k")
    pull("MUX_RESET", "+3V3")
    pull("EN", "+3V3")
    pull("BOOT", "+3V3")
    pull("MEASURE", "+3V3")
    pull("ONEWIRE", "+3V3", "4.7k")
    for i in range(N):                        # per-channel bus pull-ups
        pull("SD%d" % i, "+3V3", "4.7k")
        pull("SC%d" % i, "+3V3", "4.7k")

    # EN RC delay
    c = new_c("100nF"); connect("EN", c, "1"); connect("GND", c, "2")

    # --- decoupling --------------------------------------------------------
    for ref in ("U1", "U2", "U4", "U5", "U8"):
        decouple("+3V3")
    decouple("+5V")                            # U3 bridge runs from 5 V
    c = new_c("100nF"); connect("U3_V3", c, "1"); connect("GND", c, "2")
    decouple("+5V")                            # LDO input
    for _ in range(2):
        c = new_c("10uF"); connect("+3V3", c, "1"); connect("GND", c, "2")
    c = new_c("10uF"); connect("+5V", c, "1"); connect("GND", c, "2")


def _gpio_name(sig):
    """Signal name from the frozen pin map -> the ESP32 symbol pin name."""
    n = PM["mcu"][sig]
    return {36: "SENSOR_VP", 39: "SENSOR_VN"}.get(n, "IO%d" % n)


def _divider(ao, ain):
    """0-5 V slot output -> <=2.5 V ADS1115 input (blueprint 5.3)."""
    r1 = new_r("10k"); connect(ao, r1, "1"); connect(ain, r1, "2")
    r2 = new_r("10k"); connect(ain, r2, "1"); connect("GND", r2, "2")


PM = IF.PINMAP


# ---------------------------------------------------------------------------
# validation - the blind-safe check: every pin reference must resolve against
# the real library symbol, and no pin may sit on two nets.
# ---------------------------------------------------------------------------
def validate():
    build()
    errors = []
    seen = {}                        # (ref, pin) -> net

    for net, conns in sorted(NETS.items()):
        if not conns:
            errors.append("net %r is empty" % net)
        for ref, pin in conns:
            if ref not in PARTS:
                errors.append("net %r references unknown part %s" % (net, ref))
                continue
            nums = [n for n, _ in pin_numbers(PARTS[ref]["lib"])]
            if str(pin) not in nums:
                errors.append("net %r: %s has no pin %r (have %s)"
                              % (net, ref, pin, ",".join(nums)))
            key = (ref, str(pin))
            if key in seen and seen[key] != net:
                errors.append("pin %s.%s on two nets: %r and %r"
                              % (ref, pin, seen[key], net))
            seen[key] = net

    for req in ("+5V", "+3V3", "GND", "I2C_SDA", "I2C_SCL", "ONEWIRE"):
        if not NETS.get(req):
            errors.append("required net %r missing/empty" % req)

    # a fitted part must actually be wired to something
    wired = {ref for ref, _ in [(r, p) for cs in NETS.values() for r, p in cs]}
    for ref in sorted(PARTS):
        if ref not in wired:
            errors.append("part %s (%s) has no connections"
                          % (ref, PARTS[ref]["value"]))

    # the frozen contract must be honoured end-to-end: every slot pin, every
    # Qwiic pin, and the AO/DO/ID nets.
    for k in range(N):
        ref = "J%d" % (2 + k)
        for pin_no, name in enumerate(IF.SLOT, start=1):
            net = seen.get((ref, str(pin_no)))
            want = {"+5V": "+5V", "GND": "GND", "3V3": "+3V3", "ID": "ONEWIRE",
                    "AO": "SLOT%d_AO" % k, "DO": "SLOT%d_DO" % k}[name]
            if net != want:
                errors.append("slot %d pin %d (%s) -> %r, expected %r"
                              % (k, pin_no, name, net, want))
        qref = "J%d" % (11 + k)
        for name, pin_no in zip(IF.QWIC, (1, 2, 3, 4)):
            net = seen.get((qref, str(pin_no)))
            want = {"GND": "GND", "3V3": "+3V3",
                    "SDA": "SD%d" % k, "SCL": "SC%d" % k}[name]
            if net != want:
                errors.append("Qwiic %d pin %d (%s) -> %r, expected %r"
                              % (k, pin_no, name, net, want))

    return errors


def stats():
    build()
    return {
        "parts": len(PARTS),
        "nets": len(NETS),
        "connections": sum(len(v) for v in NETS.values()),
        "resistors": _n["R"],
        "capacitors": _n["C"],
    }


if __name__ == "__main__":
    errs = validate()
    s = stats()
    print("parts=%d nets=%d connections=%d (R=%d C=%d)"
          % (s["parts"], s["nets"], s["connections"],
             s["resistors"], s["capacitors"]))
    if errs:
        print("INVALID (%d):" % len(errs))
        for e in errs[:40]:
            print("  -", e)
        sys.exit(1)
    print("NETLIST OK - %d decisions on record" % len(DECISIONS))
