"""Emit a KiCad v1.1 schematic from the validated board model (board.py).

The board model owns the truth (which part, which pin, which net).  This
script turns that into a real `.kicad_sch` that KiCad can open, ERC, netlist
and hand to a fabricator.  Connectivity is carried by net-name labels placed
on every pin endpoint (the same idiom the v0 sheet used), so the file is a
faithful picture of board.py by construction - the two can never disagree.

Run:  python electrical/gen_schematic.py
Then: "C:\\Program Files\\KiCad\\10.0\\bin\\kicad-cli.exe" sch erc \
        --exit-code-violations --severity-error <file>
"""

import copy
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import board as B

from kiutils.schematic import Schematic, SchematicSymbol
from kiutils.symbol import SymbolLib
from kiutils.items.schitems import (
    LocalLabel, NoConnect, SymbolProjectInstance, SymbolProjectPath,
)
from kiutils.items.common import Position, Effects, Font, Property, PageSettings

KICAD_SYM = r"C:\Program Files\KiCad\10.0\share\kicad\symbols"
PROJECT = "smell_monitor_v1_1"
OUT_DIR = os.path.join(HERE, PROJECT)
OUT_SCH = os.path.join(OUT_DIR, PROJECT + ".kicad_sch")

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


def _property(key, value, x, y, pid):
    return Property(key=key, value=value, id=pid,
                    position=Position(X=x, Y=y, angle=0),
                    effects=Effects(font=Font(height=1.27, width=1.27)))


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
        _property("Footprint", fp, x, y, 2),
        _property("Datasheet", "", x, y, 3),
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


def build():
    B.build()
    sch = Schematic.create_new()
    sch.version = 20260306
    sch.generator = "eeschema"
    sch.uuid = _u()
    sch.paper = PageSettings(paperSize="A1")
    root = "/" + sch.uuid

    # --- library symbols (one per unique lib id) ---------------------------
    lib_ids = []
    for ref in sorted(B.PARTS):
        lid = B.PARTS[ref]["lib"]
        if lid not in lib_ids:
            lib_ids.append(lid)
    if "power:PWR_FLAG" not in lib_ids:
        lib_ids.append("power:PWR_FLAG")
    sch.libSymbols = [load_symbol(lid) for lid in lib_ids]

    # --- place every part on a (deliberately generous) grid ----------------
    cols = 6
    placed = {}
    for i, ref in enumerate(sorted(B.PARTS)):
        x = 40 + (i % cols) * 95
        y = 40 + (i // cols) * 75
        sym, data = _place_part(ref, B.PARTS[ref]["lib"], x, y, root)
        placed[ref] = (sym, data)
        sch.schematicSymbols.append(sym)

    # --- power flags so ERC sees every rail driven -------------------------
    # '+3V3' is already driven by the AMS1117 VO (power_out): a flag there
    # would be a second power_out on the same net.  '+5V' (USB VBUS) and 'GND'
    # have no power_out source, so they get a PWR_FLAG.
    rail_y = 40 + ((len(B.PARTS) + cols - 1) // cols) * 75 + 30
    for j, rail in enumerate(("+5V", "GND")):
        ref = "#FLG%02d" % j
        flag, fdata = _place_part(ref, "power:PWR_FLAG", 40 + j * 40, rail_y,
                                  root, value="PWR_FLAG")
        sch.schematicSymbols.append(flag)
        (num, _n, px, py, _a) = pins_of(fdata)[0]
        ax, ay = _abs(flag, px, py)
        sch.labels.append(_label(rail, ax, ay))

    # --- one label per (part, pin) -> connectivity by net name -------------
    for net, conns in B.NETS.items():
        for ref, pin in conns:
            sym, data = placed[ref]
            hit = [t for t in pins_of(data) if str(t[0]) == str(pin)]
            if not hit:
                raise KeyError("%s has no pin %s" % (ref, pin))
            _n, _nm, px, py, _a = hit[0]
            ax, ay = _abs(sym, px, py)
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
