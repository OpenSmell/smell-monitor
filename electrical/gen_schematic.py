"""Emit a KiCad v1.1 schematic from the validated board model (board.py).

The board model owns the truth (which part, which pin, which net).  This
script turns that into a real `.kicad_sch` that KiCad can open, ERC, netlist
and hand to a fabricator.  Connectivity is carried by net-name labels placed
on every pin endpoint (the same idiom the v0 sheet used), so the file is a
faithful picture of board.py by construction - the two can never disagree.

Run:  python electrical/gen_schematic.py
Verify: python tools/verify_netlist.py   (netlist parity with board.py + ERC)
"""

import copy
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import board as B

import re

from kiutils.schematic import Schematic, SchematicSymbol
from kiutils.symbol import SymbolLib
from kiutils.items.schitems import (
    LocalLabel, NoConnect, SymbolProjectInstance, SymbolProjectPath,
    Rectangle, Text, Stroke, Fill, Connection,
)
from kiutils.items.common import (
    Position, Effects, Font, Property, PageSettings, TitleBlock, Justify,
)

KICAD_SYM = r"C:\Program Files\KiCad\10.0\share\kicad\symbols"
PROJECT = "smell_monitor_v1_1"
OUT_DIR = os.path.join(HERE, PROJECT)
OUT_SCH = os.path.join(OUT_DIR, PROJECT + ".kicad_sch")

# Functional grouping: one labelled block per subsystem so the sheet reads as
# an architecture, not an alphabetical parts dump.  Order here is the order the
# blocks are laid down on the sheet.
BLOCKS = [
    ("POWER SUPPLY", ["U7", "C7", "C9", "C10", "C11", "C12"]),
    ("USB \u2013 UART BRIDGE", ["J1", "U3", "R1", "R2", "C8"]),
    ("MICROCONTROLLER", ["U1", "C1", "C2", "R18", "R19", "R20", "SW1", "SW2",
                         "SW3"]),
    ("ANALOG INPUT  (ADS1115)", ["U2", "C3", "R3", "R4", "R5", "R6", "R7",
                                 "R8", "R9", "R10"]),
    ("I2C MULTIPLEXER  (TCA9548A)", ["U4", "C4", "R15", "R16", "R17"]),
    ("SENSOR / DISPLAY", ["U5", "U6", "C5", "C6"]),
    ("OUTPUTS", ["Q1", "R11", "Q2", "R12", "R13", "BZ1", "LED1", "R14", "J10"]),
    ("ANALOG SLOTS", ["J2", "J3", "J4", "J5"]),
    ("DIGITAL SLOTS", ["J6", "J7", "J8", "J9",
                       "R21", "R22", "R23", "R24", "R25", "R26", "R27", "R28"]),
]

_lib_cache = {}
_sym_cache = {}


def _u():
    return str(uuid.uuid4())


def _lib(nick):
    if nick not in _lib_cache:
        _lib_cache[nick] = SymbolLib.from_file(
            os.path.join(KICAD_SYM, nick + ".kicad_sym"))
    return _lib_cache[nick]


def _find(lib, entry):
    for s in lib.symbols:
        if s.entryName == entry:
            return s
    return None


def load_symbol(lib_id):
    """Return a flattened (extends-resolved) copy of the library symbol."""
    if lib_id in _sym_cache:
        return _sym_cache[lib_id]
    nick, entry = lib_id.split(":", 1)
    lib = _lib(nick)
    s = _find(lib, entry)
    if s is None:
        raise KeyError("%s not in %s" % (entry, nick))
    if s.extends:
        parent = _find(lib, s.extends)
        if parent is None:
            raise KeyError("%s extends missing %s" % (entry, s.extends))
        flat = copy.deepcopy(parent)
        flat.entryName = entry
        flat.libraryNickname = nick
        flat.extends = None
        props = {p.key: p for p in flat.properties}
        for p in s.properties:
            props[p.key] = p
        flat.properties = list(props.values())
        # unit sub-symbols must be named <child>_<unit>_<style>, not the parent's
        for u in flat.units:
            u.entryName = entry
    else:
        flat = copy.deepcopy(s)
        flat.libraryNickname = nick
    _sym_cache[lib_id] = flat
    return flat


def pins_of(sym):
    """(number, name, x, y, angle) for every pin, deduped by number.

    Unit 0 is the shared body but for single-unit symbols it also carries the
    pin (e.g. power symbols), so collect from every unit and dedupe.
    """
    out = []
    seen = set()
    for u in sym.units:
        for p in u.pins:
            if str(p.number) in seen:
                continue
            seen.add(str(p.number))
            out.append((p.number, p.name, p.position.X, p.position.Y,
                        p.position.angle or 0))
    for p in sym.pins:                       # some symbols keep pins at top level
        if str(p.number) in seen:
            continue
        seen.add(str(p.number))
        out.append((p.number, p.name, p.position.X, p.position.Y,
                    p.position.angle or 0))
    return out


def _abs(sym, px, py):
    """Absolute schematic coords of a pin.  Library +Y is up, sheet +Y is down."""
    return sym.position.X + px, sym.position.Y - py


def _property(key, value, x, y, pid, angle=0, hide=False):
    return Property(key=key, value=value, id=pid,
                    position=Position(X=x, Y=y, angle=angle),
                    effects=Effects(font=Font(height=1.27, width=1.27),
                                    hide=hide))


def _place_part(ref, lib_id, x, y, root, value=None, fp=None):
    data = load_symbol(lib_id)
    nick, entry = lib_id.split(":", 1)
    if value is None:
        value = B.PARTS[ref]["value"]
    if fp is None:
        fp = B.PARTS.get(ref, {}).get("footprint", "")
    props = [
        _property("Reference", ref, x + 3, y - 2, 0),
        _property("Value", value, x + 3, y + 2, 1),
        _property("Footprint", fp, x, y, 2, hide=True),
        _property("Datasheet", "", x, y, 3, hide=True),
    ]
    sym = SchematicSymbol(
        libraryNickname=nick, entryName=entry, libName=None,
        position=Position(X=x, Y=y, angle=0), unit=1,
        inBom=True, onBoard=True, dnp=False, fieldsAutoplaced=False,
        uuid=_u(), properties=props, pins={},
        mirror=None,
        instances=[SymbolProjectInstance(
            name=PROJECT,
            paths=[SymbolProjectPath(sheetInstancePath=root,
                                     reference=ref, unit=1)])],
    )
    for (num, _n, _x, _y, _a) in pins_of(data):
        sym.pins[str(num)] = _u()
    return sym, data


def _label(text, x, y):
    return LocalLabel(
        text=text, position=Position(X=x, Y=y, angle=0), uuid=_u(),
        effects=Effects(font=Font(height=1.27, width=1.27)),
        fieldsAutoplaced=False)


RAILS = ("GND", "+3V3", "+5V")
_PWR = [0]


def _place_power(sch, rail, x, y, pin_angle, root, stub=3.81):
    """Attach a standard power port to a pin: short stub wire + symbol.

    `pin_angle` is the library pin angle (0=left, 180=right, 270=top,
    90=bottom); the port is rotated to point away from the part.  A stub wire
    joins the two pin ends so connectivity is explicit, the way it is drawn by
    hand.
    """
    if pin_angle == 180:            # pin on the right -> port to the right
        dx, dy, ang = 1, 0, 270
    elif pin_angle == 0:            # pin on the left  -> port to the left
        dx, dy, ang = -1, 0, 90
    elif pin_angle == 270:          # pin on top       -> port above
        dx, dy, ang = 0, -1, (180 if rail == "GND" else 0)
    else:                           # pin on bottom    -> port below
        dx, dy, ang = 0, 1, (0 if rail == "GND" else 180)
    sx, sy = x + dx * stub, y + dy * stub
    if dx:
        vx, vy, vang = sx + dx * 3.0, sy, 0
    else:
        vx, vy, vang = sx, sy + dy * 3.0, 0
    ref = "#PWR%03d" % _PWR[0]
    _PWR[0] += 1
    sym = SchematicSymbol(
        libraryNickname="power", entryName=rail, libName=None,
        position=Position(X=sx, Y=sy, angle=ang), unit=1,
        inBom=False, onBoard=False, dnp=False, fieldsAutoplaced=False,
        uuid=_u(),
        properties=[
            _property("Reference", ref, sx, sy, 0, hide=True),
            _property("Value", rail, vx, vy, 1, angle=vang),
        ],
        pins={"1": _u()}, mirror=None,
        instances=[SymbolProjectInstance(
            name=PROJECT,
            paths=[SymbolProjectPath(sheetInstancePath=root,
                                     reference=ref, unit=1)])])
    sch.schematicSymbols.append(sym)
    sch.graphicalItems.append(Connection(
        type="wire", points=[Position(X=x, Y=y), Position(X=sx, Y=sy)],
        stroke=Stroke(width=0, type="default"), uuid=_u()))


def _natkey(ref):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", ref)]


def _text(s, x, y, h=2.0, bold=False):
    return Text(
        text=s, position=Position(X=x, Y=y, angle=0), uuid=_u(),
        effects=Effects(font=Font(height=h, width=h, bold=bold),
                        justify=Justify(horizontally="left", vertically="top")))


def _rect(x0, y0, x1, y1, w=0.4):
    return Rectangle(
        start=Position(X=x0, Y=y0), end=Position(X=x1, Y=y1), uuid=_u(),
        stroke=Stroke(width=w, type="default"),
        fill=Fill(type="none"))


def _part_bbox(sym, data, margin=13.0):
    """Absolute bounding box of a placed symbol, from its true pin extents."""
    xs, ys = [], []
    for (_n, _nm, px, py, _a) in pins_of(data):
        ax, ay = _abs(sym, px, py)
        xs.append(ax)
        ys.append(ay)
    return (min(xs) - margin, min(ys) - margin,
            max(xs) + margin, max(ys) + margin)


def build():
    B.build()
    sch = Schematic.create_new()
    sch.version = 20260306
    sch.generator = "eeschema"
    sch.uuid = _u()
    sch.paper = PageSettings(paperSize="A1")
    sch.titleBlock = TitleBlock(
        title="OpenSmell v1.1  \u2013 e-nose sensing platform (sheet 1 of 1)",
        date="2026-10-16", revision="A",         company="OpenSmell",
        comments={1: "Controller, 4 analog + 4 digital sensor slots",
                  2: "Connectivity is net-name based; authoritative model = board.py"})
    root = "/" + sch.uuid

    # --- library symbols (one per unique lib id, PWR_FLAG included) ---------
    lib_ids = []
    for ref in sorted(B.PARTS):
        lid = B.PARTS[ref]["lib"]
        if lid not in lib_ids:
            lib_ids.append(lid)
    if "power:PWR_FLAG" not in lib_ids:
        lib_ids.append("power:PWR_FLAG")
    for rail in RAILS:
        if "power:" + rail not in lib_ids:
            lib_ids.append("power:" + rail)
    sch.libSymbols = [load_symbol(lid) for lid in lib_ids]

    # --- layout: two macro-columns, one horizontal band per subsystem -------
    # A1 is 841 x 594.  Blocks are stacked as full-width bands so nothing can
    # overlap; two macro-columns keep the stack short enough to clear the title
    # block.  Each part is normalised to its true pin bounding box so labels
    # never collide with the neighbouring cell.
    block_refs = {t: sorted(r, key=_natkey) for t, r in BLOCKS}
    col_left = ["POWER SUPPLY", "USB \u2013 UART BRIDGE", "MICROCONTROLLER",
                "ANALOG INPUT  (ADS1115)"]
    col_right = ["I2C MULTIPLEXER  (TCA9548A)", "SENSOR / DISPLAY", "OUTPUTS",
                 "ANALOG SLOTS", "DIGITAL SLOTS"]

    SX, COLS = 64.0, 6
    TOPPAD, BOTPAD, ROWP, LEFTPAD, GAP = 15.0, 6.0, 22.0, 8.0, 5.0
    MARGINS = {"left": (22.0, 418.0), "right": (424.0, 820.0)}
    STARTS = {"left": 30.0, "right": 424.0}

    placed = {}
    block_pts = {}

    def lay(side, titles, y_top):
        x0, x1 = MARGINS[side]
        start = STARTS[side]
        for title in titles:
            rlist = list(block_refs[title])
            if title == "POWER SUPPLY":
                rlist += ["#FLG00", "#FLG01"]
            n = len(rlist)
            nrows = (n + COLS - 1) // COLS
            maxh = 0.0
            ext = {}
            for ref in rlist:
                lid = "power:PWR_FLAG" if ref.startswith("#") else B.PARTS[ref]["lib"]
                data = load_symbol(lid)
                xs = [p[2] for p in pins_of(data)]
                ys = [p[3] for p in pins_of(data)]
                ext[ref] = (min(xs), max(xs), min(ys), max(ys))
                maxh = max(maxh, max(ys) - min(ys))
            band_h = TOPPAD + (nrows - 1) * ROWP + maxh + BOTPAD
            for k, ref in enumerate(rlist):
                c, rr = k % COLS, k // COLS
                mnx, _mxx, mny, mxy = ext[ref]
                cx = start + LEFTPAD + c * SX
                cy = y_top + TOPPAD + rr * ROWP
                if ref.startswith("#"):
                    rail = "+5V" if ref.endswith("0") else "GND"
                    sym, data = _place_part(ref, "power:PWR_FLAG",
                                            cx - mnx, cy + mxy, root,
                                            value="PWR_FLAG")
                    sch.schematicSymbols.append(sym)
                    block_pts.setdefault(title, []).append((sym, data))
                    (num, _n, px, py, _a) = pins_of(data)[0]
                    ax, ay = _abs(sym, px, py)
                    sch.labels.append(_label(rail, ax, ay))
                    continue
                sym, data = _place_part(ref, B.PARTS[ref]["lib"],
                                        cx - mnx, cy + mxy, root)
                sch.schematicSymbols.append(sym)
                placed[ref] = (sym, data)
                block_pts.setdefault(title, []).append((sym, data))
            sch.shapes.append(_rect(x0, y_top, x1, y_top + band_h))
            sch.texts.append(_text(title, x0 + 3, y_top + 3, h=3.0, bold=True))
            y_top += band_h + GAP
        return y_top

    lay("left", col_left, 34.0)
    lay("right", col_right, 34.0)

    # --- notes + slot key (fills the lower sheet, aids bring-up) -----------
    notes = [
        "+3V3 is generated by U7 (AMS1117CD-3.3) from the USB-C +5V rail; "
        "every IC has a 100nF decoupling cap at its supply pin.",
        "ANALOG SLOTS  J2..J5 = 1:+5V  2:GND  3:AO  4:DO  5:3V3   "
        "(MQ-type module seats on pins 1-4).",
        "DIGITAL SLOTS  J6..J9 = 1:3V3  2:GND  3:SDA  4:SCL  5:INT  6:CTRL  "
        "(each slot is one TCA9548A channel).",
        "I2C ADDRESSES  ADS1115 0x48   TCA9548A 0x70   SHT31 0x44   OLED 0x3C.",
        "S1 = MEASURE (start a sniff cycle)   S2 = BOOT   S3 = RESET.   "
        "Manual flashing, no auto-reset transistors.",
        "Connectivity is carried by net-name labels; the authoritative "
        "pin/net model is electrical/board.py (validated, ERC-clean).",
        "NC = not connected (no-connect flag placed).   All dimensions mm; "
        "passives 0603 unless noted.",
    ]
    nx0, ny0, ny1 = 22.0, 470.0, 590.0
    sch.shapes.append(_rect(nx0, ny0, 700.0, ny1))
    sch.texts.append(_text("NOTES", nx0 + 3, ny0 + 3, h=3.0, bold=True))
    for i, line in enumerate(notes):
        sch.texts.append(_text("%d.  %s" % (i + 1, line), nx0 + 5,
                               ny0 + 12 + i * 9.0, h=2.2))

    # --- connectivity ------------------------------------------------------
    # Rails become standard power ports (GND / +3V3 / +5V) on a short stub, the
    # way a hand-drawn sheet shows them; every other net keeps a net-name label
    # (the idiom for signals that cross between blocks).
    for net, conns in B.NETS.items():
        for ref, pin in conns:
            if ref not in placed:
                continue
            sym, data = placed[ref]
            hit = [t for t in pins_of(data) if str(t[0]) == str(pin)]
            if not hit:
                raise KeyError("%s has no pin %s" % (ref, pin))
            _n, _nm, px, py, pa = hit[0]
            ax, ay = _abs(sym, px, py)
            if net in RAILS:
                _place_power(sch, net, ax, ay, pa or 0, root)
            else:
                sch.labels.append(_label(net, ax, ay))

    # --- no-connect markers on every pin the model leaves unwired ----------
    used = {(ref, str(pin)) for cs in B.NETS.values() for ref, pin in cs}
    for ref, (sym, data) in placed.items():
        for (num, _n, px, py, _a) in pins_of(data):
            if (ref, str(num)) in used:
                continue
            ax, ay = _abs(sym, px, py)
            sch.noConnects.append(NoConnect(
                position=Position(X=ax, Y=ay, angle=0), uuid=_u()))

    os.makedirs(OUT_DIR, exist_ok=True)
    sch.to_file(OUT_SCH)
    return sch, OUT_SCH


if __name__ == "__main__":
    sch, path = build()
    print("wrote %s" % path)
    print("  libSymbols=%d symbols=%d labels=%d noConnects=%d"
          % (len(sch.libSymbols), len(sch.schematicSymbols),
             len(sch.labels), len(sch.noConnects)))
