"""Parity + ERC gate: the KiCad-exported netlist must equal the board.py model.

board.py is the design's source of truth; gen_schematic.py turns it into a
KiCad sheet.  This gate re-exports the netlist from that sheet with KiCad's own
tool and checks every net's pin list against the model, so the schematic can
never silently drift from the model (or vice versa).  It then runs KiCad's ERC
on the same sheet, so "ERC clean" is verified rather than asserted by hand.

Run:  python tools/verify_netlist.py
Needs kicad-cli on PATH or at the default install location.
"""

import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "electrical"))
import board as B  # noqa: E402
import interface as IF  # noqa: E402

KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
SCH = os.path.join(ROOT, "electrical", "smell_monitor_v1_1",
                   "smell_monitor_v1_1.kicad_sch")


# --- tiny s-expression reader ---------------------------------------------
def _tokenize(text):
    tok = ""
    inq = False
    for ch in text:
        if inq:
            tok += ch
            if ch == '"':
                inq = False
            continue
        if ch == '"':
            inq = True
            tok += ch
        elif ch in "()":
            if tok:
                yield tok
                tok = ""
            yield ch
        elif ch.isspace():
            if tok:
                yield tok
                tok = ""
        else:
            tok += ch
    if tok:
        yield tok


def _parse(tokens):
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            node = stack.pop()
            stack[-1].append(node)
        else:
            stack[-1].append(t)
    return stack[0]


def _find_all(node, key):
    out = []
    if isinstance(node, list):
        if node and node[0] == key:
            out.append(node)
        for c in node:
            out.extend(_find_all(c, key))
    return out


def _dq(s):
    if isinstance(s, str) and len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def _field(node, key):
    for c in node:
        if isinstance(c, list) and c and c[0] == key and len(c) > 1:
            return _dq(c[1])
    return None


def _model_pins(ref, pin):
    """Map a model pin token to individual KiCad pin numbers.

    board.py may store a pin as a number ('5'), a symbol pin name ('GND'), or
    a grouped numeric list ('[1,15,38,39]' for the ESP32 ground pins).
    """
    pairs = B.pin_numbers(B.PARTS[ref]["lib"])
    s = str(pin)
    if s.startswith("[") and s.endswith("]"):
        return [n.strip() for n in s[1:-1].split(",") if n.strip()]
    for n, _nm in pairs:
        if str(n) == s:
            return [str(n)]
    return [str(n) for n, nm in pairs if nm == s]


def exported_nets(path):
    text = open(path, encoding="utf-8").read()
    doc = _parse(_tokenize(text))
    nets = {}
    for net in _find_all(doc, "net"):
        name = _field(net, "name")
        if name is None:
            continue
        name = name[1:] if name.startswith("/") else name
        if name.startswith("unconnected-"):              # KiCad NC auto-net
            continue
        pins = set()
        for node in [c for c in net if isinstance(c, list) and c[0] == "node"]:
            ref = _field(node, "ref")
            pin = _field(node, "pin")
            if ref and not ref.startswith("#"):         # skip PWR_FLAG etc.
                pins.add((ref, str(pin)))
        nets[name] = pins
    return nets


def _net_of(pinmap, ref, pin):
    """Return the single net carrying (ref, pin) in a ref->pin set map."""
    hits = [name for name, pins in pinmap.items()
            if (ref, str(pin)) in pins]
    return hits[0] if len(hits) == 1 else None


def main():
    B.build()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "v1.net")
        subprocess.run([KICAD_CLI, "sch", "export", "netlist",
                        "--format", "kicadsexpr", "-o", out, SCH],
                       check=True, capture_output=True)
        got = exported_nets(out)

        # ERC at the same time: the sheet is generated, so "ERC clean" is a
        # property of the generator and belongs in the gate, not in a manual
        # step that leaves a report lying in the working tree.
        erc = os.path.join(tmp, "erc.rpt")
        rc = subprocess.run([KICAD_CLI, "sch", "erc", "--severity-error",
                             "--exit-code-violations", "-o", erc, SCH],
                            capture_output=True).returncode
        erc_txt = (open(erc, encoding="utf-8", errors="replace").read()
                   if os.path.isfile(erc) else "")
        erc_line = next((ln.strip() for ln in erc_txt.splitlines()
                         if "ERC messages:" in ln), "")

    want = {}
    for net, conns in B.NETS.items():
        want[net] = set()
        for ref, pin in conns:
            for num in _model_pins(ref, pin):
                want[net].add((ref, num))

    errors = []
    for net in sorted(set(want) | set(got)):
        w = want.get(net, set())
        g = {p for p in got.get(net, set())}
        # flags are model-external; drop them from the exported side too
        g = {(r, p) for (r, p) in g if not r.startswith("#")}
        if w != g:
            missing = sorted(w - g)
            extra = sorted(g - w)
            if missing or extra:
                errors.append("net %-12s  model-only=%s  sheet-only=%s"
                              % (net, missing, extra))

    # v1.1 local UI: the display header must be on the MASTER I2C bus, and
    # MENU must be its own GPIO input with a pull-up - not a slot DO line.
    display_want = dict(zip((1, 2, 3, 4),
                            ("GND", "+3V3", "I2C_SDA", "I2C_SCL")))
    got_display = {p: _net_of(got, "J19", p) for p in (1, 2, 3, 4)}
    model_display = {p: _net_of(want, "J19", p) for p in (1, 2, 3, 4)}
    if got_display != display_want or model_display != display_want:
        errors.append("J19 display header: sheet=%s model=%s expected=%s"
                      % (got_display, model_display, display_want))

    # v1.1 front-panel UI: the buttons are panel-mounted and reach the board
    # through ONE 1x05 harness.  Its pin order is part of the contract.
    panel_pins = (1, 2, 3, 4, 5)
    panel_want = dict(zip(panel_pins, ("MEASURE", "BUTTON_MENU", "BOOT", "EN",
                                       "GND")))
    got_panel = {p: _net_of(got, "J20", p) for p in panel_pins}
    model_panel = {p: _net_of(want, "J20", p) for p in panel_pins}
    if got_panel != panel_want or model_panel != panel_want:
        errors.append("J20 button harness: sheet=%s model=%s expected=%s"
                      % (got_panel, model_panel, panel_want))
    for ref in ("SW1", "SW2", "SW3", "SW4"):
        if ref in B.PARTS or any(r == ref for pins in got.values()
                                 for r, _ in pins):
            errors.append("board-mounted switch %s must not be fitted" % ref)
    menu_name = "IO%d" % IF.PINMAP["mcu"]["BUTTON_MENU"]
    menu_pin = [n for n, nm in B.pin_numbers(B.PARTS["U1"]["lib"])
                if nm == menu_name][0]
    if _net_of(got, "U1", menu_pin) != "BUTTON_MENU":
        errors.append("U1.%s (%s, GPIO%d) is not BUTTON_MENU on the sheet"
                      % (menu_pin, menu_name,
                         IF.PINMAP["mcu"]["BUTTON_MENU"]))
    if sorted({_net_of(got, "R54", 1), _net_of(got, "R54", 2)}) != \
            ["+3V3", "BUTTON_MENU"]:
        errors.append("R54 must pull BUTTON_MENU up to +3V3")

    print("model nets=%d  sheet nets=%d" % (len(want), len(got)))
    print("J19 (master bus): %s" % got_display)
    print("J20 (front-panel harness): %s" % got_panel)
    print("U1.%s=%s" % (menu_pin, _net_of(got, "U1", menu_pin)))
    if erc_line:
        print("ERC: %s" % erc_line)
    if rc != 0 and not errors:
        print("ERC FAILED (%d)" % rc)
        print(erc_txt[-2000:])
    if errors:
        print("MISMATCH (%d):" % len(errors))
        for e in errors[:40]:
            print("  -", e)
    if errors or rc != 0:
        sys.exit(1)
    print("NETLIST PARITY OK - ERC clean")


if __name__ == "__main__":
    main()
