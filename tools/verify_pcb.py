#!/usr/bin/env python3
"""Numeric verification of the routed PCB against the chamber contract.

The routed board is the one deliverable that goes to fabrication, so it is
checked with numbers rather than by looking at pictures:

  * placement - all 8 sensing headers sit exactly on
    ``interface.ANALOG_HEADERS`` / ``DIGITAL_HEADERS`` (the L2 contract), so a
    slot can never drift off its chamber well; the J19 display cable and J20
    button harness sit by the single front-wall grommet at ``UI_FEED_X`` and
    no SMD switches remain on the board,
  * net parity - every board.py (ref, pin) lands on the same pad/net on the
    real PCB, including the master-I2C display header and button harness,
  * fabrication - board outline = ``CONST['PCB_X'] x CONST['PCB_Y']`` with the
    four boss cut-outs the tray needs, no copper narrower than the board's own
    minimum track width, via stack sane,
  * routing - every net fully connected (0 unconnected),
  * DRC - ``kicad-cli pcb drc`` clean (0 violations / 0 unconnected /
    0 footprint errors), i.e. the board a fab house would accept.

pcbnew is only importable from KiCad's own interpreter, so this gate runs with
it (same as ``electrical/gen_pcb.py``):

  & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" tools/verify_pcb.py

If ``kicad-cli`` cannot be found the DRC row is reported SKIPPED (loudly) and
the rest of the gate still decides the exit code.
"""
import math
import os
import glob
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "electrical"))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
# KiCad ships its own interpreter, so the user site (kiutils, used by
# electrical/board.py) is not on its path by default: add every one we find.
for _p in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python3*\site-packages")):
    if os.path.isdir(_p):
        sys.path.append(_p)

import pcbnew  # noqa: E402
import interface as IF  # noqa: E402
import board as B  # noqa: E402
from constants import CONST  # noqa: E402

PROJECT = "smell_monitor_v1_1"
PCB = os.environ.get("SMELL_PCB") or os.path.join(
    ROOT, "electrical", PROJECT, PROJECT + ".kicad_pcb")
MIN_TRACK_MM = 0.15            # board design-rule minimum (netclass nominal 0.30)
FAILS = []
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    if not ok:
        FAILS.append(name)


def mm(v):
    return round(pcbnew.ToMM(v), 4)


board = pcbnew.LoadBoard(PCB)
B.build()                       # board.py builds PARTS/NETS on demand

# ------------------------------- placement ----------------------------------
# measure the outline from the Edge.Cuts segments themselves - the bounding box
# would include the 0.1 mm edge line width
edge = []
for d in board.GetDrawings():
    if d.GetLayer() == pcbnew.Edge_Cuts and isinstance(d, pcbnew.PCB_SHAPE):
        for pt in (d.GetStart(), d.GetEnd()):
            edge.append((mm(pt.x), mm(pt.y)))
w = max(p[0] for p in edge) - min(p[0] for p in edge)
h = max(p[1] for p in edge) - min(p[1] for p in edge)
# everything below is checked relative to the board's own outline origin, so
# dragging the board anywhere in the KiCad sheet (e.g. centring it) is safe
ox = min(p[0] for p in edge)
oy = min(p[1] for p in edge)

# what must land on a chamber well is the header's connector line (the pad
# centre), not the footprint origin
def pad_extent(fp):
    pts = [p.GetPosition() for p in fp.Pads()]
    xs = [mm(p.x) for p in pts]
    ys = [mm(p.y) for p in pts]
    return (sum(xs) / len(xs) - ox, sum(ys) / len(ys) - oy,
            max(xs) - min(xs), max(ys) - min(ys))


SOCKET_SPAN = 5 * 2.54                 # 1x6 at 2.54 pitch = 12.7 mm
rows = {"analog": IF.ANALOG_HEADERS, "digital": IF.DIGITAL_HEADERS}
for bank, want in rows.items():
    refs = [f"J{i}" for i in (range(2, 6) if bank == "analog" else range(6, 10))]
    got = []
    for ref in refs:
        fp = board.FindFootprintByReference(ref)
        got.append(None if fp is None else pad_extent(fp))
    ok = all(g is not None for g in got) and all(
        abs(g[0] - x) <= 0.01 and abs(g[1] - (CONST["PCB_Y"] - y)) <= 0.01
        for g, (x, y) in zip(got, want))
    check(f"{bank} sockets J{refs[0][1]}..J{refs[-1][1]} on the chamber contract",
          ok, "" if ok else str([(round(g[0], 2), round(CONST["PCB_Y"] - g[1], 2))
                                 for g in got if g]))

    # The pin line must run FRONT-TO-BACK (shell Y -> board KiCad Y) so a
    # straight-header breakout stands upright in the Y-Z plane and its face
    # looks inward across the central channel.  Only the span catches a
    # wrongly rotated footprint: the centre position is checked above.
    along = all(g is not None and abs(g[3] - SOCKET_SPAN) <= 0.05
                and g[2] <= 2.2 for g in got)
    check(f"{bank} socket pin line runs front-to-back (upright board)", along,
          "" if along else str([(round(g[2], 2), round(g[3], 2))
                                for g in got if g]))

# ------------------------- v1.1 front-panel UI placement --------------------
# The buttons are panel-mounted in the FIXED FRONT WALL (CONST['BTN_FRONT']),
# so no SMD switches belong on this board.  Both harnesses leave the wall
# through ONE grommet at shell X = UI_FEED_X, hence both board connectors must
# sit in the front strip near the board projection of that grommet.
sw_refs = [r for r in ("SW1", "SW2", "SW3", "SW4")
           if board.FindFootprintByReference(r) is not None]
check("no board-mounted SMD switches (buttons are on the front panel)",
      not sw_refs, str(sw_refs))

feed_x = CONST["UI_FEED_X"] - (CONST["SH"] - CONST["PCB_X"]) / 2.0
for _ref in ("J19", "J20"):
    fp = board.FindFootprintByReference(_ref)
    if fp is None:
        check(f"{_ref} front-panel harness at the UI grommet", False,
              "missing " + _ref)
        continue
    cx, ky, _sx, _sy = pad_extent(fp)
    jy = CONST["PCB_Y"] - ky
    at_feed = abs(cx - feed_x) <= 7.0 and 5.0 <= jy <= 18.0
    check(f"{_ref} front-panel harness at the UI grommet", at_feed,
          f"board-local ({cx:.2f}, {jy:.2f}) mm vs shell feed x "
          f"{CONST['UI_FEED_X']:.1f} (board x {feed_x:.1f})")

# ------------------------------ fan harness ----------------------------------
# The fan is a d40 on the REAR plate at shell X = FAN_X, so its 2-pin harness
# must leave the board near that centre line, not at a far rear corner.  Measure
# the pad-field centre in the shell frame (the board is inset by PCB_X0/Y0) and
# gate on both axes so this cannot drift back to a corner during a re-route.
fp10 = board.FindFootprintByReference("J10")
if fp10 is None:
    check("J10 fan harness at the rear centre under FAN_X", False, "missing J10")
else:
    jx, ky, _sx, _sy = pad_extent(fp10)
    shell_x = CONST["PCB_X0"] + jx
    shell_y = CONST["PCB_Y0"] + (CONST["PCB_Y"] - ky)
    fan_ok = (abs(shell_x - CONST["FAN_X"]) <= 12.0 and shell_y >= 90.0)
    check("J10 fan harness at the rear centre under FAN_X", fan_ok,
          f"shell ({shell_x:.2f}, {shell_y:.2f}) mm vs FAN_X "
          f"{CONST['FAN_X']:.1f} +/- 12 and shell Y >= 90")

# ------------------------------ fabrication ---------------------------------
check(f"board outline = {CONST['PCB_X']:.0f} x {CONST['PCB_Y']:.0f} mm",
      abs(w - CONST["PCB_X"]) <= 0.01 and abs(h - CONST["PCB_Y"]) <= 0.01,
      f"{w} x {h}")

# ---------------------------- boss clearance --------------------------------
# The tray's four M3 bosses stand inside the board footprint (they carry the
# lid and run the full cavity height), so the board must have a circular cut-out
# at each one.  Measure that on the real Edge.Cuts geometry, not on a rectangle
# rebuilt from the constants: the gerbers are what the fab cuts.
poly = pcbnew.SHAPE_POLY_SET()
if not board.GetBoardPolygonOutlines(poly, True) or poly.OutlineCount() != 1:
    check("board outline is one closed polygon", False, "outline did not close")
else:
    check("board outline is one closed polygon", True, f"{poly.Area()/1e12:.1f} mm2")
    x0 = (CONST["SH"] - CONST["PCB_X"]) / 2.0
    y0 = (CONST["SW"] - CONST["PCB_Y"]) / 2.0
    V = pcbnew.VECTOR2I
    F = pcbnew.FromMM
    r_boss = CONST["BOSS_D"] / 2.0
    worst = 99.0
    worst_name = ""
    for sx, sy in ((CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
                   (CONST["SH"] - CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
                   (CONST["SH"] - CONST["BOSS_INSET"],
                    CONST["SW"] - CONST["BOSS_INSET"]),
                   (CONST["BOSS_INSET"], CONST["SW"] - CONST["BOSS_INSET"])):
        bx = ox + (sx - x0)
        by = oy + (CONST["PCB_Y"] - (sy - y0))
        # nearest board material to the boss axis, radial scan at 0.05 mm
        found = 8.0
        r = 0.0
        while r <= 8.0:
            if any(poly.Contains(V(F(bx + r * math.cos(2 * math.pi * k / 180)),
                                    F(by + r * math.sin(2 * math.pi * k / 180))))
                   for k in range(180)):
                found = r
                break
            r += 0.05
        if found < worst:
            worst, worst_name = found, f"({sx:.1f},{sy:.1f})"
    check(f"board clears the tray bosses (needs >= {r_boss + 0.2:.1f} mm)",
          worst >= r_boss + 0.2 - 1e-6,
          f"nearest material {worst:.2f} mm at {worst_name}")

tracks = [t for t in board.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
vias = [t for t in board.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
widths = sorted({mm(t.GetWidth()) for t in tracks})
check(f"no track below the {MIN_TRACK_MM} mm board minimum",
      bool(widths) and widths[0] >= MIN_TRACK_MM - 1e-6,
      f"min {widths[0]} mm of {len(widths)} widths={widths}")
via_pads = sorted({mm(v.GetWidth(pcbnew.F_Cu)) for v in vias})
via_drills = sorted({mm(v.GetDrillValue()) for v in vias})
check("via stack is a single sane size (0.6 / 0.3 mm)",
      via_pads == [0.6] and via_drills == [0.3],
      f"pads={via_pads} drills={via_drills}")

# -------------------------------- parity ------------------------------------
check("one footprint per board.py part",
      len(board.GetFootprints()) == len(B.PARTS),
      f"{len(board.GetFootprints())} vs {len(B.PARTS)}")
check("one net per board.py net",
      board.GetNetCount() - 1 == len(B.NETS),      # net 0 is the no-net sentinel
      f"{board.GetNetCount()-1} vs {len(B.NETS)}")

# Pin-level parity: the model's every (ref, pin) must land on a board pad with
# the same net.  Count-only checks above would not catch a swapped display pin.
def _pad_numbers(pin):
    s = str(pin)
    if s.startswith("[") and s.endswith("]"):
        return [n.strip() for n in s[1:-1].split(",") if n.strip()]
    return [s]


model_pins = {}
for _net, _conns in B.NETS.items():
    for _ref, _pin in _conns:
        for _num in _pad_numbers(_pin):
            _key = (_ref, _num)
            if _key in model_pins and model_pins[_key] != _net:
                check("board.py pin model is conflict-free", False, str(_key))
            model_pins[_key] = _net
board_pins = {}
for _fp in board.GetFootprints():
    for _pad in _fp.Pads():
        _key = (_fp.GetReference(), str(_pad.GetNumber()))
        _net = _pad.GetNetname()
        if _key in board_pins and board_pins[_key] != _net:
            check("duplicate pad numbers share one net", False, str(_key))
        board_pins[_key] = _net
wrong = sorted((k, model_pins[k], board_pins.get(k))
               for k in model_pins if board_pins.get(k) != model_pins[k])
check("board.py pin/net model equals the routed pad netlist",
      not wrong, f"{len(model_pins)} model pins checked"
      if not wrong else "; ".join(f"{r}.{p}: {a} -> {b}"
                                  for (r, p), a, b in wrong[:8]))

# --------------------------- v1.1 UI net checks ------------------------------
def _pad_nets(ref, allow_extra=()):
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        return {}
    out = {}
    for pad in fp.Pads():
        num = str(pad.GetNumber())
        if num in allow_extra:
            continue
        out.setdefault(num, set()).add(pad.GetNetname())
    return out


j19_nets = _pad_nets("J19", allow_extra=("MP",))
want_j19 = dict(zip(("1", "2", "3", "4"),
                    ("GND", "+3V3", "I2C_SDA", "I2C_SCL")))
j19_ok = all(j19_nets.get(p) == {n} for p, n in want_j19.items())
check("J19 carries master I2C / power / GND", j19_ok, str(j19_nets))

j20_nets = _pad_nets("J20")
want_j20 = dict(zip(("1", "2", "3", "4", "5"),
                    ("MEASURE", "BUTTON_MENU", "BOOT", "EN", "GND")))
j20_ok = all(j20_nets.get(p) == {n} for p, n in want_j20.items())
check("J20 carries MEASURE / BUTTON_MENU / BOOT / EN / GND", j20_ok,
      str(j20_nets))
menu_name = "IO%d" % IF.PINMAP["mcu"]["BUTTON_MENU"]
menu_pin = [n for n, nm in B.pin_numbers(B.PARTS["U1"]["lib"])
            if nm == menu_name][0]
u1_nets = _pad_nets("U1")
menu_ok = u1_nets.get(menu_pin) == {"BUTTON_MENU"}
check("U1 GPIO%d (%s, symbol pin %s) is BUTTON_MENU"
      % (IF.PINMAP["mcu"]["BUTTON_MENU"], menu_name, menu_pin),
      menu_ok, str(u1_nets.get(menu_pin)))
r54_nets = _pad_nets("R54")
pull_ok = set().union(*r54_nets.values()) == {"+3V3", "BUTTON_MENU"} \
    if r54_nets else False
check("R54 pulls BUTTON_MENU up to +3V3", pull_ok, str(r54_nets))

# ------------------------------- routing ------------------------------------
check("every net fully routed (0 unconnected)",
      board.GetConnectivity().GetUnconnectedCount(False) == 0,
      str(board.GetConnectivity().GetUnconnectedCount(False)))

# The 5 V trunk is a 0.30 mm trace (IPC-2221 ~21 C rise at 1.4 A); the return
# path is a filled B.Cu pour so ADC/mux/I2C references do not share trace R.
# tools/add_ground_pour.py is the reproducible step that creates it.
gnd_pours = [z for z in board.Zones()
             if z.GetLayer() == pcbnew.B_Cu and z.GetNetname() == "GND"]
check("filled bottom-layer GND return pour",
      len(gnd_pours) == 1 and gnd_pours[0].IsFilled(),
      f"{len(gnd_pours)} pour(s), filled="
      f"{gnd_pours[0].IsFilled() if gnd_pours else False}")

# Permanent identity on the assembled board, added by tools/add_board_markings.py
silk_text = [d.GetText() for d in board.GetDrawings()
             if isinstance(d, pcbnew.PCB_TEXT)
             and d.GetLayer() == pcbnew.F_SilkS]
check("board carries silkscreen branding",
      "OPEN SMELL" in silk_text and any("OSM-1" in t for t in silk_text),
      f"{len(silk_text)} F.SilkS text item(s)")

need_silk = (["OPEN SMELL", "OLED 0x3C", "BTN 1x05",
              "1x6: +5V GND AO DO 3V3 ID", "Qwiic: GND 3V3 SDA SCL"] +
             [f"S{i}" for i in range(8)] + [f"Q{i}" for i in range(8)])
missing_silk = [t for t in need_silk if t not in silk_text]
check("all permanent silk legends present (incl. J19 / J20)",
      not missing_silk, "all present" if not missing_silk
      else f"missing {missing_silk}")

# --------------------------------- DRC --------------------------------------
def kicad_cli():
    p = shutil.which("kicad-cli")
    if p:
        return p
    for cand in (r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
                 r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
                 "/usr/bin/kicad-cli"):
        if os.path.isfile(cand):
            return cand
    return None


cli = kicad_cli()
if cli is None:
    CHECKS.append(("kicad-cli DRC", None,
                   "SKIPPED - kicad-cli not found; run it before shipping"))
else:
    rpt = os.path.join(tempfile.gettempdir(), PROJECT + "-verify-drc.rpt")
    subprocess.run([cli, "pcb", "drc", "--format", "report", "--severity-all",
                    "-o", rpt, PCB], capture_output=True, text=True)
    txt = open(rpt, encoding="utf-8", errors="replace").read() \
        if os.path.isfile(rpt) else ""
    n_viol = txt.count("** Found 0 DRC violations") == 1
    n_unconn = txt.count("** Found 0 unconnected pads") == 1
    n_fp = txt.count("** Found 0 Footprint errors") == 1
    check("DRC clean (0 violations / 0 unconnected / 0 footprint errors)",
          n_viol and n_unconn and n_fp,
          " ".join(s for s, ok in (("violations", n_viol),
                                   ("unconnected", n_unconn),
                                   ("footprints", n_fp)) if not ok) or "clean")

# ------------------------------- report -------------------------------------
w = max(len(n) for n, _, _ in CHECKS) + 2
print(f"{'CHECK':<{w}} {'RESULT':<7} DETAIL")
for name, ok, detail in CHECKS:
    verdict = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
    print(f"{name:<{w}} {verdict:<7} {detail}")
print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    sys.exit(1)
print("ALL PASS - routed board consistent with the chamber contract")
