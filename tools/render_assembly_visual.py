#!/usr/bin/env python3
"""Professional assembly + flow animation for OpenSmell v1.1.

Coded technical illustration: every PCB feature comes from the routed board via
``pcb_geometry.json`` and every enclosure/module number is derived from
``mechanical/constants.py`` plus the machine-readable OSM-1 envelope in
``mechanical/standard.py``.  The eight identical stations are clean parametric
OSM-1 representations: a keyed socket, an upright inward-facing card, a gas cell
and a Qwiic port.  Licensed vendor STEP models are not in this repo; module
shapes are parametric OSM-1 representations.

The v1.1 UI is on the fixed front wall: a sealed acrylic/gasket/bezel stack at
master I2C 0x3C, one harness grommet and four buttons.  The lid is a plain flat
plate with four M3 screws; no cable crosses the lid seam.

Run (after extract_pcb_geometry.py):
  python tools/render_assembly_visual.py
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST  # noqa: E402
from standard import CARTRIDGE, PORT  # noqa: E402

OUT = os.path.join(ROOT, "docs", "figures", "cad")
GEO = os.path.join(OUT, "pcb_geometry.json")
with open(GEO, encoding="utf-8") as f:
    PCB = json.load(f)
J10 = next(f for f in PCB["footprints"] if f["ref"] == "J10")
FAN_HARNESS = {"ref": J10["ref"], "value": J10["value"],
               "shell_x": J10["x"], "shell_y": J10["y"]}

# ---- geometry: a single derived record, embedded in every output ------------
# The card width is the OSM-1 envelope limit, not a typed drawing number; the
# remaining values are identities from CONST.  Nothing below re-states a
# dimension that CONST or CARTRIDGE already owns.
PCB_TOP = CONST["PCB_TOP"]
SOCK_TOP = PCB_TOP + CONST["SOCK_H"]
CART_W = CARTRIDGE["envelope"]["across"]
CART_H = CONST["CARD_H"]
CART_REACH = CONST["CARD_REACH"]
CARD_TOP = CONST["CARD_TOP"]
HOOD = CONST["HOOD"]
NO_X = [CONST["SH"] / 2.0 + k * CONST["NO_PITCH"] for k in (-1, 0, 1)]
SENSE_H = CONST["NO_Z"] - SOCK_TOP
CARD_T = CONST["PCB_T"]
CHAMFER = CONST["SOCK_P"] / 2.0
DISP_X0 = CONST["DISP_X"] - CONST["DISP_W"] / 2.0
DISP_X1 = CONST["DISP_X"] + CONST["DISP_W"] / 2.0
DISP_Z0 = CONST["DISP_Z"] - CONST["DISP_H"] / 2.0
DISP_Z1 = CONST["DISP_Z"] + CONST["DISP_H"] / 2.0
WIN_X0 = CONST["DISP_X"] - CONST["DISP_WIN_W"] / 2.0
WIN_X1 = CONST["DISP_X"] + CONST["DISP_WIN_W"] / 2.0
WIN_Z0 = CONST["DISP_Z"] - CONST["DISP_WIN_H"] / 2.0
WIN_Z1 = CONST["DISP_Z"] + CONST["DISP_WIN_H"] / 2.0
BTN_FRONT = {k: list(v) for k, v in CONST["BTN_FRONT"].items()}

GEOMETRY = {
    "source": "mechanical/constants.py + routed pcb_geometry.json",
    "SOCK_X_L": CONST["SOCK_X_L"],
    "SOCK_X_R": CONST["SOCK_X_R"],
    "ROW_Y": list(CONST["ROW_Y"]),
    "SOCK_N": CONST["SOCK_N"],
    "SOCK_P": CONST["SOCK_P"],
    "SOCK_H": CONST["SOCK_H"],
    "PCB_TOP": PCB_TOP,
    "SOCK_TOP": SOCK_TOP,
    "CARD_W": CART_W,
    "CARD_H": CART_H,
    "CARD_REACH": CART_REACH,
    "CARD_TOP": CARD_TOP,
    "HOOD": HOOD,
    "NO_X": NO_X,
    "NO_Z": CONST["NO_Z"],
    "NO_PITCH": CONST["NO_PITCH"],
    "NO_R": CONST["NO_R"],
    "FAN_X": CONST["FAN_X"],
    "FAN_Z": CONST["FAN_Z"],
    "FAN_R": CONST["FAN_R"],
    "FAN_HARNESS": FAN_HARNESS,
    "LID_Z0": CONST["LID_Z0"],
    "LID_Z1": CONST["LID_Z1"],
    "LID": {"type": "plain flat plate", "screws": 4, "fastener": "M3",
            "cables": 0},
    "DISP_X": CONST["DISP_X"],
    "DISP_Z": CONST["DISP_Z"],
    "DISP_W": CONST["DISP_W"],
    "DISP_H": CONST["DISP_H"],
    "DISP_WIN_W": CONST["DISP_WIN_W"],
    "DISP_WIN_H": CONST["DISP_WIN_H"],
    "DISP_POD_D": CONST["DISP_POD_D"],
    "DISP_GASKET": CONST["DISP_GASKET"],
    "UI_FEED_D": CONST["UI_FEED_D"],
    "UI_FEED_X": CONST["UI_FEED_X"],
    "UI_FEED_Z": CONST["UI_FEED_Z"],
    "BTN_HOLE_D": CONST["BTN_HOLE_D"],
    "BTN_FRONT": BTN_FRONT,
    "FRONT_PANEL_UI": {
        "wall": "fixed front wall",
        "panel_x": [DISP_X0, DISP_X1],
        "panel_z": [DISP_Z0, DISP_Z1],
        "aperture_x": [WIN_X0, WIN_X1],
        "aperture_z": [WIN_Z0, WIN_Z1],
        "stack": ["gasket", "acrylic", "OLED", "bezel"],
        "grommet": {"d": CONST["UI_FEED_D"],
                    "x": CONST["UI_FEED_X"], "z": CONST["UI_FEED_Z"]},
        "buttons": "four front-wall bores and caps",
    },
    "UI": {
        "oled": "0x3C",
        "bus": "master I2C",
        "user_buttons": ["MEASURE/OK", "MENU/BACK"],
        "service_buttons": ["BOOT", "RESET"],
        "update": "OTA",
    },
    "SHAPES": ["keyed_socket", "upright_card", "gas_cell", "qwiic_port",
               "nostrils", "central_channel", "rear_fan",
               "rear_centre_fan_harness", "front_panel_ui",
               "front_wall_display", "ui_harness_grommet",
               "front_panel_buttons", "plain_lid"],
    "CONNECTOR": CARTRIDGE["conn"],
    "QWIIC": PORT["conn"],
    "VISUAL_NOTE": "Licensed vendor STEP models are not in this repo; "
                   "module shapes are parametric OSM-1 representations.",
}

W, H = 1600, 1000
SCALE = 4.6
ZSCALE = 4.6
OX, OY = 800.0, 430.0
COS30 = math.cos(math.radians(30))
SIN30 = 0.5

# Deliberate palette: cool = gas path, green = board, warm = cartridges.
C_BG0 = (11, 18, 30)
C_BG1 = (18, 31, 48)
C_GRID = (45, 66, 92)
C_WHITE = (232, 241, 250)
C_MUTED = (150, 173, 197)
C_CYAN = (69, 206, 255)
C_CYAN_D = (24, 122, 184)
C_PCB = (18, 86, 56)
C_PCB_D = (10, 53, 35)
C_PCB_E = (73, 197, 133)
C_COPPER = (208, 143, 70)
C_GOLD = (246, 191, 82)
C_SHELL = (126, 154, 184)
C_LID = (168, 205, 236)
C_RED = (255, 76, 76)
C_GREEN = (80, 255, 150)

# Eight identical OSM-1 stations; the family is the standard, not a vendor part.
SENSOR_TYPES = [("S%d" % i, "OSM-1", (73, 197, 133)) for i in range(8)]


def geom_pnginfo():
    """Numeric contract attached to every still and to the header proof."""
    meta = PngImagePlugin.PngInfo()
    meta.add_text("OSM_GEOMETRY", json.dumps(GEOMETRY, sort_keys=True))
    meta.add_text("OSM_CART_W_MM", str(CART_W))
    meta.add_text("OSM_CART_L_MM", str(CART_H))
    meta.add_text("OSM_CART_H_MM", str(CART_REACH))
    meta.add_text("OSM_CART_ENVELOPE", json.dumps(CARTRIDGE["envelope"],
                                                 sort_keys=True))
    meta.add_text("OSM_CARD_TOP_MM", str(round(CARD_TOP, 3)))
    meta.add_text("OSM_HOOD_MM", str(round(HOOD, 3)))
    meta.add_text("OSM_SOURCE", "mechanical/constants.py + routed pcb_geometry.json")
    meta.add_text("OSM_VISUAL_REP", GEOMETRY["VISUAL_NOTE"])
    return meta


def font(size, bold=False, mono=False):
    name = "consola.ttf" if mono else ("segoeuib.ttf" if bold else "segoeui.ttf")
    path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


F_TITLE = font(31, True)
F_SUB = font(16)
F_BODY = font(15)
F_SMALL = font(12)
F_TINY = font(10)
F_MONO = font(13, mono=True)
F_PANEL = font(17, True)


def P(x, y, z):
    """Shell mm -> iso screen pixels.  +Y is rear, so invert it for the view."""
    yy = CONST["SW"] - y
    return (OX + (x - yy) * COS30 * SCALE,
            OY + (x + yy) * SIN30 * SCALE - z * ZSCALE)


def poly(d, pts, fill=None, outline=None, width=1):
    d.polygon([P(*p) for p in pts], fill=fill)
    if outline:
        d.line([P(*p) for p in pts] + [P(*pts[0])], fill=outline,
               width=width, joint="curve")


def ln(d, a, b, fill, width=1):
    d.line([P(*a), P(*b)], fill=fill, width=width)


def box(d, x, y, z, dx, dy, dz, top, side1, side2, edge=(6, 14, 24, 160), width=1):
    """Extruded rectangular structural part (shell, board, lid), not a module."""
    b = [(x, y, z), (x + dx, y, z), (x + dx, y + dy, z), (x, y + dy, z)]
    t = [(px, py, z + dz) for px, py, _ in b]
    poly(d, [b[1], b[2], t[2], t[1]], side1, edge, width)
    poly(d, [b[0], b[1], t[1], t[0]], side2, edge, width)
    poly(d, t, top, edge, width)


def hcircle(d, cx, cy, z, r, fill=None, outline=None, width=1, n=32):
    pts = [(cx + r * math.cos(2 * math.pi * i / n),
            cy + r * math.sin(2 * math.pi * i / n), z) for i in range(n)]
    poly(d, pts, fill, outline, width)


def vcircle(d, cx, y, cz, r, fill=None, outline=None, width=1, n=32):
    """Circle in the X-Z plane (front wall, fan, nostrils)."""
    pts = [(cx + r * math.cos(2 * math.pi * i / n), y,
            cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    poly(d, pts, fill, outline, width)


def yz_ellipse(d, x, y, z, ry, rz, fill=None, outline=None, width=1, n=24):
    """Circle/ellipse on a card face: the plane normal is along X."""
    pts = [(x, y + ry * math.cos(2 * math.pi * i / n),
            z + rz * math.sin(2 * math.pi * i / n)) for i in range(n)]
    poly(d, pts, fill, outline, width)


def x_can(d, x0, reach, y, z, ry, rz, face_col, side_col, face_in,
          outline=(*C_WHITE, 155), n=20):
    """Cylindrical gas cell extruded inward along X (never a square stand-in)."""
    xf = x0 + reach if face_in > 0 else x0 - reach
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = 2 * math.pi * (i + 1) / n
        shade = 0.68 + 0.32 * (0.5 + 0.5 * math.sin((a0 + a1) / 2))
        col = (int(side_col[0] * shade), int(side_col[1] * shade),
               int(side_col[2] * shade), side_col[3] if len(side_col) > 3 else 255)
        poly(d, [(x0, y + ry * math.cos(a0), z + rz * math.sin(a0)),
                 (x0, y + ry * math.cos(a1), z + rz * math.sin(a1)),
                 (xf, y + ry * math.cos(a1), z + rz * math.sin(a1)),
                 (xf, y + ry * math.cos(a0), z + rz * math.sin(a0))], col)
    yz_ellipse(d, xf, y, z, ry, rz, face_col, outline, 2)
    return xf


def xz_rect(d, x0, z0, x1, z1, y, fill=None, outline=None, width=1):
    """Rectangle in the fixed front wall (X-Z plane at constant Y)."""
    poly(d, [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)],
         fill, outline, width)


def txt(d, xy, s, f=F_SMALL, fill=C_WHITE, anchor=None):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def glow(d, x, y, color, r=28, rings=5):
    for i in range(rings, 0, -1):
        rr = r * i / rings
        a = int(110 * (1 - i / (rings + 1)))
        d.ellipse([x - rr, y - rr, x + rr, y + rr],
                  fill=(color[0], color[1], color[2], a))


def arrow2(d, a, b, color, width=2, head=8):
    d.line([a, b], fill=color, width=width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for off in (2.55, -2.55):
        d.line([b, (b[0] + head * math.cos(ang + off),
                    b[1] + head * math.sin(ang + off))],
               fill=color, width=width)


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def background(img):
    d = ImageDraw.Draw(img, "RGBA")
    for y in range(H):
        u = y / H
        d.line([(0, y), (W, y)], fill=(int(C_BG0[0] + (C_BG1[0] - C_BG0[0]) * u),
                                        int(C_BG0[1] + (C_BG1[1] - C_BG0[1]) * u),
                                        int(C_BG0[2] + (C_BG1[2] - C_BG0[2]) * u), 255))
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=(*C_GRID, 26), width=1)
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill=(*C_GRID, 26), width=1)
    d.rectangle([0, 0, W, 88], fill=(8, 14, 24, 225))
    d.line([(0, 88), (W, 88)], fill=(*C_CYAN_D, 190), width=2)
    txt(d, (34, 19), "OpenSmell v1.1  /  OSM-1 ASSEMBLY + FLOW", F_TITLE)
    txt(d, (36, 59),
        "Coded from CONST + the routed board  |  front inlet, centred channel, "
        "rear fan, front-wall UI, plain lid",
        F_SUB, C_MUTED)


def draw_shell_far(d):
    sh, sw, wall = CONST["SH"], CONST["SW"], CONST["WALL"]
    ztop = CONST["CAV_Z1"]
    poly(d, [(0, sw, 0), (sh, sw, 0), (sh, sw, ztop), (0, sw, ztop)],
         (C_SHELL[0], C_SHELL[1], C_SHELL[2], 46), (*C_SHELL, 105))
    poly(d, [(0, 0, 0), (0, sw, 0), (0, sw, ztop), (0, 0, ztop)],
         (C_SHELL[0], C_SHELL[1], C_SHELL[2], 42), (*C_SHELL, 100))
    box(d, 0, 0, 0, sh, sw, CONST["FLOOR_T"],
        (48, 63, 82, 190), (35, 48, 65, 190), (38, 52, 70, 190))
    inset, boss_r = CONST["BOSS_INSET"], CONST["BOSS_D"] / 2.0
    for bx, by in ((inset, inset), (sh - inset, inset),
                   (inset, sw - inset), (sh - inset, sw - inset)):
        hcircle(d, bx, by, CONST["FLOOR_T"], boss_r,
                (28, 39, 54, 230), (*C_SHELL, 150))


def draw_fan(d, angle, active):
    cx, cy, cz = CONST["FAN_X"], CONST["SW"] + CONST["FAN_PLATE_T"], CONST["FAN_Z"]
    r, plate = CONST["FAN_R"], CONST["FAN_PLATE"] / 2.0
    a = 165 if active else 80
    box(d, cx - plate, CONST["SW"], cz - plate, 2 * plate, CONST["FAN_PLATE_T"],
        2 * plate, (38, 48, 62, a), (28, 36, 48, a), (32, 41, 55, a), (*C_MUTED, a))
    vcircle(d, cx, cy + 0.3, cz, r + 1.5, (14, 20, 29, a), (*C_MUTED, a), 2)
    for k in range(5):
        th = angle + k * 2 * math.pi / 5
        p0 = (cx + (r * 0.24) * math.cos(th), cy + 0.4, cz + (r * 0.24) * math.sin(th))
        p1 = (cx + (r * 0.89) * math.cos(th + 0.22), cy + 0.4,
              cz + (r * 0.89) * math.sin(th + 0.22))
        p2 = (cx + (r * 0.89) * math.cos(th + 0.90), cy + 0.4,
              cz + (r * 0.89) * math.sin(th + 0.90))
        p3 = (cx + (r * 0.32) * math.cos(th + 0.52), cy + 0.4,
              cz + (r * 0.32) * math.sin(th + 0.52))
        poly(d, [p0, p1, p2, p3], (93, 112, 132, a), (*C_CYAN, min(220, a + 50)))
    vcircle(d, cx, cy + 0.6, cz, r * 0.27, (16, 23, 33, min(255, a + 70)),
            (*C_CYAN, a), 2)
    if active:
        for k in (1, 2):
            vcircle(d, cx, cy + 0.2, cz, r + k * (r * 0.21), None, (*C_CYAN, 48), 1)


def draw_fan_harness(d):
    """J10 and its lead come from the routed board, not a typed label."""
    jx, jy = FAN_HARNESS["shell_x"], FAN_HARNESS["shell_y"]
    rear = CONST["SW"] - CONST["WALL"]
    p0 = (jx, jy, PCB_TOP + 4.0)
    p1 = (jx, rear + CONST["WALL"] * 0.5, PCB_TOP + 5.5)
    p2 = (CONST["FAN_X"], CONST["SW"] + CONST["FAN_PLATE_T"] * 0.4,
          CONST["FAN_Z"] - CONST["FAN_R"] * 0.55)
    ln(d, p0, p1, (*C_GOLD, 235), 2)
    ln(d, p1, p2, (*C_GOLD, 215), 2)
    hcircle(d, jx, jy, PCB_TOP + 4.1, CONST["SOCK_P"] * 0.8,
            (18, 22, 28, 255), (*C_GOLD, 230), 2, 12)
    where = "REAR CENTRE" if abs(jx - CONST["FAN_X"]) < CONST["FAN_R"] else "REAR"
    p = P(CONST["FAN_X"], CONST["SW"] + CONST["FAN_PLATE_T"] + 1,
          CONST["FAN_Z"] + CONST["FAN_R"] * 1.18)
    txt(d, (p[0] - 34, p[1]), "%s J10 FAN HARNESS" % where,
        F_TINY, (*C_GOLD, 240), "mm")


def pcb_board_outline():
    o = PCB["outline"]
    return (o[1] + list(reversed(o[4])) + o[5] + list(reversed(o[7])) +
            o[6] + list(reversed(o[3])) + o[2] + list(reversed(o[0])))


def draw_pcb(d):
    outline = pcb_board_outline()
    lower = [(x, y, PCB_TOP - CONST["PCB_T"]) for x, y in outline]
    upper = [(x, y, PCB_TOP) for x, y in outline]
    poly(d, lower, (C_PCB_D[0], C_PCB_D[1], C_PCB_D[2], 230))
    poly(d, upper, (C_PCB[0], C_PCB[1], C_PCB[2], 248), (*C_PCB_E, 210), 2)
    for t in PCB["tracks"]:
        if t["layer"] != "F.Cu":
            continue
        col = (*C_COPPER, 96) if t["w"] < 0.25 else (*C_GOLD, 120)
        ln(d, (*t["a"], PCB_TOP + 0.05), (*t["b"], PCB_TOP + 0.05), col,
           1 if t["w"] < 0.25 else 2)
    for v in PCB["vias"]:
        hcircle(d, v["x"], v["y"], PCB_TOP + 0.08, v["d"] / 2,
                (*C_GOLD, 150), (*C_PCB_E, 130), 1, 10)
    for p in PCB["pads"]:
        w, h = max(p["w"], 0.5), max(p["h"], 0.5)
        col = (*C_GOLD, 205) if any(k in p["net"] for k in ("GND", "5V", "3V3")) else (*C_GOLD, 165)
        box(d, p["x"] - w / 2, p["y"] - h / 2, PCB_TOP, w, h, 0.18,
            col, col, col, (*C_PCB_D, 100), 0)
    heights = {"U1": 3.2, "U2": 1.1, "U8": 1.1, "U4": 1.2, "U5": 1.0,
               "U7": 1.3, "J1": 3.4, "J10": 4.0, "SW1": 1.6, "SW2": 1.6,
               "SW3": 1.6, "Q1": 1.0, "Q2": 1.0, "D1": 1.0, "R30": 0.8}
    big = {"U1", "U2", "U8", "U4", "U5", "U7", "J1", "J10", "SW1", "SW2", "SW3",
           "Q1", "Q2", "D1", "R30", "C9", "C10", "C11", "C12"}
    byref = {f["ref"]: f for f in PCB["footprints"]}
    for ref in sorted(big):
        f = byref.get(ref)
        if not f:
            continue
        x0, y0, x1, y1 = f["bbox"]
        dx, dy = max(x1 - x0, 1.2), max(y1 - y0, 1.2)
        hz = heights.get(ref, 0.8)
        top = (46, 55, 66, 245) if not ref.startswith("U") else (38, 47, 60, 250)
        box(d, x0, y0, PCB_TOP, dx, dy, hz, top,
            (25, 32, 43, 250), (32, 40, 52, 250), (*C_MUTED, 120))
        if ref in ("U1", "U2", "U8", "U4", "J1", "J10"):
            pp = P(x0 + dx / 2, y0 + dy / 2, PCB_TOP + hz + 0.4)
            txt(d, (pp[0], pp[1] - 7), ref, F_TINY, (*C_WHITE, 220), "mm")
    for ref in ("BZ1", "LED1"):
        f = byref.get(ref)
        if not f:
            continue
        x, y = f["x"], f["y"]
        if ref == "BZ1":
            for zz, rr in ((PCB_TOP, CONST["BOSS_D"] * 0.64),
                           (PCB_TOP + CONST["SOCK_H"], CONST["BOSS_D"] * 0.55)):
                hcircle(d, x, y, zz, rr, (44, 52, 62, 255), (*C_CYAN, 170), 2, 28)
            ln(d, (x, y, PCB_TOP + 0.1), (x, y, PCB_TOP + CONST["SOCK_H"]),
               (*C_MUTED, 220), 2)
        else:
            hcircle(d, x, y, PCB_TOP + 1.2, CONST["SOCK_P"] * 0.47,
                    (*C_RED, 255), (*C_WHITE, 200), 1, 12)


def draw_keyed_socket(d, cx, cy):
    """2.54 mm 1x6 receptacle: pin line front-to-back, pin-1 key slot."""
    half = CONST["SOCK_N"] * CONST["SOCK_P"] / 2.0
    box(d, cx - CONST["SOCK_P"] / 2, cy - half, PCB_TOP, CONST["SOCK_P"],
        2 * half, CONST["SOCK_H"], (23, 26, 32, 255), (12, 14, 19, 255),
        (16, 19, 25, 255), (*C_MUTED, 150))
    key_y = cy - half + CONST["SOCK_P"] * 0.5
    poly(d, [(cx - CONST["SOCK_P"] * 0.6, key_y - CONST["SOCK_P"] * 0.2, SOCK_TOP),
             (cx + CONST["SOCK_P"] * 0.6, key_y - CONST["SOCK_P"] * 0.2, SOCK_TOP),
             (cx + CONST["SOCK_P"] * 0.6, key_y + CONST["SOCK_P"] * 0.2, SOCK_TOP),
             (cx - CONST["SOCK_P"] * 0.6, key_y + CONST["SOCK_P"] * 0.2, SOCK_TOP)],
         (6, 8, 11, 255), (*C_GOLD, 190))
    for k in range(CONST["SOCK_N"]):
        py = cy + (k - (CONST["SOCK_N"] - 1) / 2.0) * CONST["SOCK_P"]
        box(d, cx - 0.55, py - 0.55, SOCK_TOP - 0.4, 1.1, 1.1, 0.6,
            (*C_GOLD, 255), (*C_GOLD, 220), (*C_GOLD, 220), None, 0)


def draw_upright_card(d, cx, cy, z_base, face_in):
    """Parametric upright OSM-1 carrier: chamfered, keyed, gold-fingered."""
    face_x = cx + face_in * CARD_T / 2.0
    back_x = cx - face_in * CARD_T / 2.0
    y0, y1 = cy - CART_W / 2.0, cy + CART_W / 2.0
    z0, z1 = z_base, z_base + CART_H
    outline = [(y0, z0), (y1, z0), (y1, z1 - CHAMFER), (y1 - CHAMFER, z1),
               (y0 + CHAMFER, z1), (y0, z1 - CHAMFER)]
    front = [(face_x, y, z) for y, z in outline]
    back = [(back_x, y, z) for y, z in outline]
    poly(d, [back[0], back[1], front[1], front[0]], (19, 62, 42, 245),
         (*C_PCB_E, 145))
    poly(d, front, (34, 92, 62, 242), (*C_PCB_E, 190), 2)
    notch_y = y0 + CONST["SOCK_P"] * 0.5
    poly(d, [(face_x, notch_y - CONST["SOCK_P"] * 0.2, z0 + 0.1),
             (face_x, notch_y + CONST["SOCK_P"] * 0.2, z0 + 0.1),
             (face_x, notch_y + CONST["SOCK_P"] * 0.2, z0 + CHAMFER),
             (face_x, notch_y - CONST["SOCK_P"] * 0.2, z0 + CHAMFER)],
         (8, 12, 16, 255), (*C_GOLD, 180))
    for k in range(CONST["SOCK_N"]):
        py = cy + (k - (CONST["SOCK_N"] - 1) / 2.0) * CONST["SOCK_P"]
        ln(d, (face_x, py, z0 + 0.2), (face_x, py, z0 + CHAMFER * 1.8),
           (*C_GOLD, 245), 2)
    qy = y1 - CONST["SOCK_P"] * 1.5
    qz = z0 + CART_H * 0.83
    poly(d, [(face_x, qy - CONST["SOCK_P"] * 0.8, qz - CONST["SOCK_P"] * 0.5),
             (face_x, qy + CONST["SOCK_P"] * 0.8, qz - CONST["SOCK_P"] * 0.5),
             (face_x, qy + CONST["SOCK_P"] * 0.8, qz + CONST["SOCK_P"] * 0.5),
             (face_x, qy - CONST["SOCK_P"] * 0.8, qz + CONST["SOCK_P"] * 0.5)],
         (12, 18, 24, 250), (*C_CYAN, 165))
    for k in range(4):
        py = qy + (k - 1.5) * CONST["SOCK_P"] * 0.38
        box(d, face_x, py - 0.25, qz - 0.25, 0.25, 0.5, 0.5,
            (*C_GOLD, 255), (*C_GOLD, 220), (*C_GOLD, 220), None, 0)
    return face_x, z0 + SENSE_H


def draw_gas_cell(d, face_x, cy, cz, col, face_in):
    """One clean parametric sensing cell inside the OSM-1 reach envelope."""
    R = lambda c, a=255: (c[0], c[1], c[2], a)
    ry = CART_W * 0.36
    xf = x_can(d, face_x, CART_REACH * 0.78, cy, cz, ry, ry,
               R((58, 62, 68)), R(col, 245), face_in)
    yz_ellipse(d, xf + face_in * 0.05, cy, cz, ry * 0.52, ry * 0.52,
               R((18, 20, 23)), R(C_WHITE, 170), 1)
    yz_ellipse(d, xf + face_in * 0.07, cy, cz, ry * 0.20, ry * 0.20,
               R(col, 235), None, 1)
    return CART_REACH


def draw_sockets_and_cartridges(d, module_u):
    """Two opposing side-wall rows of eight uniform, inward-facing stations."""
    slots = ([(CONST["SOCK_X_L"], y, i) for i, y in enumerate(CONST["ROW_Y"])] +
             [(CONST["SOCK_X_R"], y, i + len(CONST["ROW_Y"]))
              for i, y in enumerate(CONST["ROW_Y"])])
    for cx, cy, idx in slots:
        draw_keyed_socket(d, cx, cy)
        u = smooth((module_u - idx * 0.045) / 0.30)
        if u <= 0:
            continue
        lift = (1 - u) * CONST["CARD_H"] * 1.3
        face_in = 1 if cx < CONST["SH"] / 2.0 else -1
        face_x, cz = draw_upright_card(d, cx, cy, SOCK_TOP + lift, face_in)
        if u > 0.35:
            for k in range(CONST["SOCK_N"]):
                py = cy + (k - (CONST["SOCK_N"] - 1) / 2.0) * CONST["SOCK_P"]
                ln(d, (cx, py, SOCK_TOP + lift + 0.1), (cx, py, SOCK_TOP - 0.4),
                   (*C_GOLD, 235), 2)
        ref, label, col = SENSOR_TYPES[idx]
        draw_gas_cell(d, face_x, cy, cz, col, face_in)
        if u >= 0.999:
            pp = P(cx, cy, SOCK_TOP + CART_H + CART_W * 0.12)
            txt(d, (pp[0], pp[1]), "%s %s" % (ref, label), F_TINY,
                (*C_WHITE, 205), "mm")


def draw_filter(d, u):
    x0, x1 = CONST["CX0"], CONST["CX0"] + CONST["CX"]
    y0, z0 = CONST["FILT_Y0"], CONST["FILT_Z0"]
    h = CART_H * 0.72
    a = int(55 + 95 * u)
    poly(d, [(x0, y0, z0), (x1, y0, z0), (x1, y0, z0 + h), (x0, y0, z0 + h)],
         (150, 205, 225, a), (188, 229, 245, min(220, a + 80)), 2)


def catmull(points, u):
    u = max(0.0, min(0.99999, u)) * (len(points) - 1)
    i = int(u)
    t = u - i
    p0 = points[max(0, i - 1)]
    p1 = points[i]
    p2 = points[min(len(points) - 1, i + 1)]
    p3 = points[min(len(points) - 1, i + 2)]
    return tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t +
                        (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t * t +
                        (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t ** 3)
                 for k in range(3))


def flow_paths():
    paths = []
    for nx in NO_X:
        paths.append([
            (nx, -CONST["WALL"] * 4.7, CONST["NO_Z"]), (nx, 0, CONST["NO_Z"]),
            (nx, CONST["FILT_Y1"] + CONST["FILT_T"] * 0.5, CONST["NO_Z"]),
            (nx, CONST["SW"] * 0.30, CONST["NO_Z"]),
            (nx, CONST["SW"] * 0.60, CONST["NO_Z"]),
            (nx, CONST["SW"] * 0.85, CONST["NO_Z"]),
            (CONST["FAN_X"], CONST["SW"] - CONST["WALL"], CONST["FAN_Z"]),
        ])
    return paths


def draw_flow(d, t, strength):
    if strength <= 0.01:
        return
    paths = flow_paths()
    a = int(150 * strength)
    for pi, path in enumerate(paths):
        pts = [P(*catmull(path, k / 60)) for k in range(61)]
        d.line(pts, fill=(*C_CYAN, int(a * 0.55)), width=2, joint="curve")
        for q in range(0, 61, 12):
            p0, p1 = pts[q], pts[min(q + 2, 60)]
            arrow2(d, p0, p1, (*C_CYAN, a), 2, 6)
        for k in range(4):
            phase = (t * 0.21 + k / 4 + pi * 0.13) % 1.0
            sp = P(*catmull(path, phase))
            glow(d, sp[0], sp[1], C_CYAN, 13, 4)
            d.ellipse([sp[0] - 2.5, sp[1] - 2.5, sp[0] + 2.5, sp[1] + 2.5],
                      fill=(230, 250, 255, min(255, a + 80)))
    p = P(NO_X[0], -CONST["WALL"] * 2.7, CONST["NO_Z"] + CONST["NO_R"] * 2.3)
    txt(d, (p[0] - 36, p[1] - 12), "AIR IN · 3 x dia6", F_SMALL, (*C_CYAN, 235))
    q = P(CONST["FAN_X"], CONST["SW"] + CONST["WALL"] * 2.7,
          CONST["FAN_Z"] + CONST["FAN_R"] * 1.4)
    txt(d, (q[0], q[1]), "EXHAUST · 40 mm FAN", F_SMALL, (*C_CYAN, 235), "mm")


def draw_effects(d, t, led_on, buzz_on):
    byref = {f["ref"]: f for f in PCB["footprints"]}
    if led_on:
        f = byref["LED1"]
        p = P(f["x"], f["y"], PCB_TOP + 2)
        pulse = 0.65 + 0.35 * math.sin(t * 22)
        glow(d, p[0], p[1], C_RED, 26 * pulse, 5)
        d.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3], fill=(255, 235, 235, 255))
        txt(d, (p[0] + 12, p[1] - 10), "STATUS / QC", F_TINY, (*C_RED, 245))
    if buzz_on:
        f = byref["BZ1"]
        p = P(f["x"], f["y"], PCB_TOP + CONST["SOCK_H"] + 1.5)
        for k in range(3):
            ph = (t * 1.8 + k / 3) % 1
            rr = 8 + ph * 34
            a = int(175 * (1 - ph))
            d.arc([p[0] - rr, p[1] - rr * 0.62, p[0] + rr, p[1] + rr * 0.62],
                  200, 340, fill=(*C_GOLD, a), width=2)
        txt(d, (p[0] + 16, p[1] - 18), "BZ1 · ALERT", F_TINY, (*C_GOLD, 240))


def draw_shell_near(d):
    sh, sw, ztop = CONST["SH"], CONST["SW"], CONST["CAV_Z1"]
    poly(d, [(0, 0, 0), (sh, 0, 0), (sh, 0, ztop), (0, 0, ztop)],
         (C_SHELL[0], C_SHELL[1], C_SHELL[2], 44), (*C_SHELL, 120))
    poly(d, [(sh, 0, 0), (sh, sw, 0), (sh, sw, ztop), (sh, 0, ztop)],
         (C_SHELL[0], C_SHELL[1], C_SHELL[2], 38), (*C_SHELL, 110))
    for nx in NO_X:
        vcircle(d, nx, -0.3, CONST["NO_Z"], CONST["NO_R"],
                (5, 11, 19, 255), (*C_CYAN, 220), 2, 24)
    vcircle(d, CONST["USB_X"], -0.4, CONST["USB_Z"], CONST["USB_R"],
            (5, 11, 19, 255), (*C_GOLD, 190), 2, 24)
    p = P(CONST["USB_X"], -1, CONST["USB_Z"] - CONST["USB_R"] * 1.8)
    txt(d, (p[0], p[1]), "USB-C POWER + DATA", F_TINY, (*C_GOLD, 220), "mm")


def draw_front_panel_ui(d):
    """Sealed front-wall UI: gasket/acrylic/bezel stack, OLED, grommet, buttons."""
    gt = CONST["DISP_GASKET"]
    y_gasket = -0.05
    y_acrylic = -gt
    y_bezel = -(gt * 2 + CONST["DISP_POD_D"])
    # The stack layers sit at their true outward depths; the offsets are visible
    # in the iso view, so the drawing cannot imply a lid or a display enclosure.
    xz_rect(d, DISP_X0, DISP_Z0, DISP_X1, DISP_Z1, y_gasket,
            None, (*C_GOLD, 190), 2)
    xz_rect(d, DISP_X0, DISP_Z0, DISP_X1, DISP_Z1, y_acrylic,
            (168, 205, 236, 80), (*C_LID, 200), 2)
    xz_rect(d, DISP_X0, DISP_Z0, DISP_X1, DISP_Z1, y_bezel,
            (52, 66, 82, 245), (*C_LID, 235), 2)
    xz_rect(d, WIN_X0, WIN_Z0, WIN_X1, WIN_Z1, y_bezel - 0.05,
            (11, 27, 38, 250), (*C_CYAN, 235), 2)
    p = P(CONST["DISP_X"], y_bezel - 0.1, CONST["DISP_Z"])
    txt(d, (p[0], p[1]), "OLED 0x3C", F_TINY, (*C_CYAN, 245), "mm")
    q = P(CONST["DISP_X"], y_bezel - 0.1, DISP_Z1 + CONST["SOCK_P"] * 1.6)
    txt(d, (q[0], q[1]), "FRONT WALL UI", F_TINY, (*C_WHITE, 220), "mm")

    fx, fz = CONST["UI_FEED_X"], CONST["UI_FEED_Z"]
    vcircle(d, fx, y_gasket, fz, CONST["UI_FEED_D"] / 2.0,
            (10, 17, 25, 255), (*C_GOLD, 225), 2, 20)
    p = P(fx, y_gasket - 0.1, fz - CONST["UI_FEED_D"])
    txt(d, (p[0], p[1]), "dia6 HARNESS", F_TINY, (*C_GOLD, 230), "mm")

    for name, (bx, bz) in BTN_FRONT.items():
        user = name in ("MEASURE", "MENU")
        ring = (*C_CYAN, 225) if user else (*C_MUTED, 215)
        vcircle(d, bx, -CONST["DISP_GASKET"] - 0.05, bz, CONST["BTN_HOLE_D"],
                (30, 40, 52, 235), ring, 2, 18)
        vcircle(d, bx, y_gasket, bz, CONST["BTN_HOLE_D"] / 2.0,
                (8, 14, 20, 255), ring, 2, 18)
        p = P(bx, -CONST["DISP_GASKET"] - 0.1, bz - CONST["BTN_HOLE_D"] * 2)
        lab = {"MEASURE": "MEASURE/OK", "MENU": "MENU/BACK"}.get(name, name)
        txt(d, (p[0], p[1]), lab, F_TINY, ring, "mm")


def draw_ui_detail(d):
    """Flat elevation + depth stack, so the front panel reads without perspective."""
    x0, y0, x1, y1 = 28, 450, 330, 722
    d.rounded_rectangle([x0, y0, x1, y1], 10, fill=(8, 15, 26, 215),
                        outline=(*C_CYAN_D, 170), width=1)
    txt(d, (x0 + 16, y0 + 12), "FRONT WALL UI  /  ELEVATION", F_PANEL,
        (*C_CYAN, 255))
    S = 3.0

    def ux(x):
        return 56 + (x - 44) * S

    def uz(z):
        return 646 - (z - 34) * S

    d.rectangle([ux(46), uz(55), ux(106), uz(35)],
                fill=(58, 76, 98, 70), outline=(*C_SHELL, 200), width=1)
    d.rectangle([ux(DISP_X0 - 1), uz(DISP_Z1 + 1), ux(DISP_X1 + 1), uz(DISP_Z0 - 1)],
                outline=(*C_GOLD, 170), width=1)
    d.rectangle([ux(DISP_X0), uz(DISP_Z1), ux(DISP_X1), uz(DISP_Z0)],
                fill=(52, 66, 82, 235), outline=(*C_LID, 225), width=2)
    d.rectangle([ux(WIN_X0), uz(WIN_Z1), ux(WIN_X1), uz(WIN_Z0)],
                fill=(11, 27, 38, 255), outline=(*C_CYAN, 235), width=2)
    d.text((ux(CONST["DISP_X"]), uz(CONST["DISP_Z"]) - 6), "OLED 0x3C",
           font=F_TINY, fill=(*C_CYAN, 245), anchor="mm")
    fx, fz = CONST["UI_FEED_X"], CONST["UI_FEED_Z"]
    d.ellipse([ux(fx) - CONST["UI_FEED_D"] / 2 * S, uz(fz) - CONST["UI_FEED_D"] / 2 * S,
               ux(fx) + CONST["UI_FEED_D"] / 2 * S, uz(fz) + CONST["UI_FEED_D"] / 2 * S],
              fill=(10, 17, 25, 255), outline=(*C_GOLD, 225), width=2)
    for name, (bx, bz) in BTN_FRONT.items():
        user = name in ("MEASURE", "MENU")
        ring = C_CYAN if user else C_MUTED
        d.ellipse([ux(bx) - CONST["BTN_HOLE_D"] * S, uz(bz) - CONST["BTN_HOLE_D"] * S,
                   ux(bx) + CONST["BTN_HOLE_D"] * S, uz(bz) + CONST["BTN_HOLE_D"] * S],
                  outline=(*ring, 200), width=1)
        d.ellipse([ux(bx) - CONST["BTN_HOLE_D"] / 2 * S,
                   uz(bz) - CONST["BTN_HOLE_D"] / 2 * S,
                   ux(bx) + CONST["BTN_HOLE_D"] / 2 * S,
                   uz(bz) + CONST["BTN_HOLE_D"] / 2 * S],
                  fill=(8, 14, 20, 255), outline=(*ring, 235), width=2)
        lab = {"MEASURE": "MEAS", "MENU": "MENU"}.get(name, name)
        d.text((ux(bx), uz(bz) + CONST["BTN_HOLE_D"] * S + 3), lab,
               font=F_TINY, fill=(*ring, 230), anchor="ma")
    txt(d, (x0 + 16, 660),
        "gasket %.0f / acrylic %.0f / bezel %.0f mm" %
        (CONST["DISP_GASKET"], CONST["DISP_GASKET"], CONST["DISP_POD_D"]),
        F_SMALL, C_WHITE)
    txt(d, (x0 + 16, 682), "4 x dia3.4 front bores + caps", F_SMALL, C_WHITE)
    txt(d, (x0 + 16, 704), "dia6 harness passes the fixed front wall",
        F_SMALL, C_MUTED)


def draw_lid(d, lid_u):
    """Plain flat plate with four M3 screws: no UI, no holes, no cables."""
    z = 95.0 - (95.0 - CONST["LID_Z0"]) * smooth(lid_u)
    if lid_u <= 0.01:
        z = 95.0
    sh, sw, lt = CONST["SH"], CONST["SW"], CONST["LID_T"]
    box(d, 0, 0, z, sh, sw, lt,
        (C_LID[0], C_LID[1], C_LID[2], 74),
        (C_LID[0] - 20, C_LID[1] - 20, C_LID[2] - 20, 66),
        (C_LID[0] - 10, C_LID[1] - 10, C_LID[2] - 10, 70),
        (*C_LID, 185), 2)
    ang = lid_u * 4 * 2 * math.pi
    inset = CONST["BOSS_INSET"]
    for bx, by in ((inset, inset), (sh - inset, inset),
                   (inset, sw - inset), (sh - inset, sw - inset)):
        ln(d, (bx, by, z + lt), (bx, by, CONST["LID_Z0"] - CONST["WALL"]),
           (190, 200, 212, 210), 3)
        p = P(bx, by, z + lt + 1.5)
        d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6],
                  fill=(205, 214, 224, 245), outline=(90, 105, 122, 255), width=1)
        d.line([(p[0] - 4 * math.cos(ang), p[1] - 4 * math.sin(ang)),
                (p[0] + 4 * math.cos(ang), p[1] + 4 * math.sin(ang))],
               fill=(48, 60, 74, 255), width=2)
    if 0.02 < lid_u < 0.98:
        p = P(sh / 2, sw / 2, z + CONST["LID_T"] * 2)
        txt(d, (p[0], p[1]), "4 x M3  —  PLAIN FLAT LID",
            F_SMALL, (*C_WHITE, 235), "mm")
    return z


def draw_panels(d, phase):
    x0, y0, x1, y1 = 28, 118, 330, 430
    d.rounded_rectangle([x0, y0, x1, y1], 10, fill=(8, 15, 26, 205),
                        outline=(*C_CYAN_D, 170), width=1)
    y = y0 + 16
    txt(d, (x0 + 16, y), "WHAT YOU ARE SEEING", F_PANEL, (*C_CYAN, 255)); y += 30
    facts = [
        "8 identical OSM-1 slots (S0-S7)",
        "keyed 1x6 header, line front-to-back",
        "upright 20 x 32 card, 21 mm inward reach",
        "%.1f mm hood under the plain lid" % HOOD,
        "3 centred nostrils -> channel -> rear fan",
        "J10 fan harness at the rear centre",
        "front-wall OLED 0x3C + four buttons",
    ]
    for s in facts:
        d.ellipse([x0 + 17, y + 5, x0 + 22, y + 10], fill=(*C_CYAN, 230))
        txt(d, (x0 + 32, y), s, F_BODY, C_WHITE)
        y += 32

    x0, y0, x1, y1 = 1272, 118, 1574, 520
    d.rounded_rectangle([x0, y0, x1, y1], 10, fill=(8, 15, 26, 205),
                        outline=(*C_CYAN_D, 170), width=1)
    y = y0 + 16
    txt(d, (x0 + 16, y), "MODULE FAMILY", F_PANEL, (*C_CYAN, 255)); y += 30
    families = [("GAS CELL", "keyed 1x6, sensing face inward"),
                ("QWIIC I2C", "4-pin port beside every socket")]
    for label, desc in families:
        d.rounded_rectangle([x0 + 16, y + 1, x0 + 31, y + 16], 4,
                            fill=(*C_PCB_E, 255))
        txt(d, (x0 + 40, y), label, F_BODY, C_WHITE)
        txt(d, (x0 + 40, y + 18), desc, F_TINY, C_MUTED)
        y += 46
    d.line([(x0 + 16, y), (x1 - 16, y)], fill=(*C_CYAN_D, 150)); y += 12
    for s in ("Left wall S0-S3 | right wall S4-S7 -> channel",
              "SHT31 T/RH fixed at 0x44 (base board)",
              "Licensed vendor STEP models are not",
              "in this repo; shapes are parametric",
              "OSM-1 representations."):
        txt(d, (x0 + 16, y), s, F_SMALL, C_MUTED)
        y += 22

    caps = ["01  SHELL + BOARD", "02  PLUG ANY OSM-1 MODULE", "03  FAN + FLOW",
            "04  LED + BUZZER", "05  FRONT WALL UI", "06  RUN CLEAN"]
    idx = min(5, int(phase * 6))
    d.rounded_rectangle([650, 930, 950, 972], 8, fill=(8, 15, 26, 220),
                        outline=(*C_CYAN, 170))
    txt(d, (800, 951), caps[idx], F_PANEL, (*C_WHITE, 255), "mm")
    txt(d, (28, 958), "FRONT / INLET", F_SMALL, (*C_CYAN, 220))
    txt(d, (1572, 958), "REAR / FAN", F_SMALL, (*C_CYAN, 220), "ra")


def render_frame(i, total):
    t = i / (total - 1)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    background(img)
    d = ImageDraw.Draw(img, "RGBA")
    module_u = max(0.0, min(1.0, (t - 0.10) / 0.32))
    fan_active = t > 0.30
    flow_u = smooth((t - 0.36) / 0.12)
    led_on = 0.44 < t < 0.72 or t > 0.90
    buzz_on = 0.50 < t < 0.70
    lid_u = smooth((t - 0.70) / 0.20)
    draw_shell_far(d)
    draw_fan(d, t * 9 * math.pi, fan_active)
    draw_fan_harness(d)
    draw_pcb(d)
    draw_filter(d, min(1.0, t / 0.3))
    draw_sockets_and_cartridges(d, module_u)
    draw_flow(d, t, flow_u)
    draw_effects(d, t, led_on, buzz_on)
    draw_shell_near(d)
    draw_front_panel_ui(d)
    draw_lid(d, lid_u)
    draw_panels(d, t)
    draw_ui_detail(d)
    return img.convert("RGB")


def render_storyboard(frames, path):
    picks = [(0, "Shell + routed PCB"), (30, "Any OSM-1 module, any slot"),
             (52, "Fan pulls the sample"), (70, "Status + alert"),
             (86, "Front-wall UI + plain lid"), (len(frames) - 1, "Ready to run")]
    tw, th = 520, 325
    sheet = Image.new("RGB", (tw * 3 + 40, (th + 34) * 2 + 30), (9, 16, 27))
    d = ImageDraw.Draw(sheet)
    for k, (idx, cap) in enumerate(picks):
        im = frames[idx].resize((tw, th), Image.Resampling.LANCZOS)
        x = 10 + (k % 3) * (tw + 10)
        y = 10 + (k // 3) * (th + 34 + 10)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + th + 5), cap, font=F_BODY, fill=C_WHITE)
    sheet.save(path, pnginfo=geom_pnginfo())
    print("  wrote", path)


def render_header_proof(path):
    """Dimensioned section + plan + front-wall elevation, derived from CONST."""
    W2, H2 = 1400, 820
    im = Image.new("RGB", (W2, H2), (240, 244, 249))
    d = ImageDraw.Draw(im, "RGBA")
    S = 10.0                 # section scale, px per mm (view scale, not geometry)
    pcb_top = 660
    sock_top = pcb_top - CONST["SOCK_H"] * S
    card_top_px = sock_top - CART_H * S
    lid_under = pcb_top - (CONST["LID_Z0"] - PCB_TOP) * S
    lid_top = lid_under - CONST["LID_T"] * S

    def sz(z):
        return pcb_top - (z - PCB_TOP) * S

    d.text((42, 26), "OSM-1 HEADER PROOF  /  UPRIGHT INWARD-FACING CARRIER",
           font=F_TITLE, fill=(15, 35, 55))
    d.text((44, 67),
           "Section from CONST  |  keyed 1x6 line front-to-back, parametric gas "
           "cell, front-wall UI, rear-centre fan harness",
           font=F_SUB, fill=(70, 92, 116))

    d.rectangle([160, pcb_top, 1030, pcb_top + CONST["PCB_T"] * S],
                fill=(18, 86, 56), outline=(9, 52, 33), width=2)
    d.text((170, pcb_top + 8), "BASE PCB  (chamber floor)", font=F_SMALL,
           fill=(220, 255, 235))

    card_x0, card_x1 = 430.0, 430.0 + CART_W * S
    sock_w = CONST["SOCK_N"] * CONST["SOCK_P"] * S
    sock_x0 = card_x0 + (CART_W * S - sock_w) / 2.0
    sock_x1 = sock_x0 + sock_w
    d.rectangle([sock_x0, sock_top, sock_x1, pcb_top], fill=(28, 31, 38),
                outline=(10, 12, 16), width=2)
    key_x = sock_x0 + CONST["SOCK_P"] * S * 0.5
    d.rectangle([key_x - CONST["SOCK_P"] * S * 0.2, sock_top + 2,
                 key_x + CONST["SOCK_P"] * S * 0.2, sock_top + 10],
                fill=(6, 8, 11), outline=(246, 191, 82), width=1)
    d.text((250, (pcb_top + sock_top) / 2 - 8),
           "1x6 KEYED SOCKET  ·  %.1f mm" % CONST["SOCK_H"], font=F_SMALL,
           fill=(45, 52, 62))
    pin_x = [sock_x0 + (k + 0.5) * CONST["SOCK_P"] * S
             for k in range(CONST["SOCK_N"])]
    for kx in pin_x:
        d.line([(kx, sock_top), (kx, sock_top + CONST["SOCK_P"] * S * 0.4)],
               fill=(246, 191, 82), width=3)

    ch = CHAMFER * S
    d.polygon([(card_x0, sock_top), (card_x1, sock_top),
               (card_x1, card_top_px + ch), (card_x1 - ch, card_top_px),
               (card_x0 + ch, card_top_px), (card_x0, card_top_px + ch)],
              fill=(34, 92, 62), outline=(12, 68, 43))
    d.text((250, card_top_px + 20),
           "UPRIGHT BOARD  %.0f tall x %.0f along wall" % (CART_H, CART_W),
           font=F_SMALL, fill=(30, 80, 58))
    for kx in pin_x:
        d.line([(kx, sock_top), (kx, sock_top - CHAMFER * S * 2)],
               fill=(246, 191, 82), width=2)

    cell_cz = card_top_px + (CARD_TOP - CONST["NO_Z"]) * S
    cell_cz = max(card_top_px + CART_W * S * 0.3,
                  min(sock_top - CART_W * S * 0.3, cell_cz))
    cell_x0, cell_x1 = card_x1, card_x1 + CART_REACH * S
    d.rounded_rectangle([cell_x0, cell_cz - CART_W * S * 0.35,
                         cell_x1, cell_cz + CART_W * S * 0.35],
                        8, fill=(220, 126, 69), outline=(120, 62, 30), width=2)
    d.ellipse([cell_x1 - 16, cell_cz - 14, cell_x1 + 16, cell_cz + 14],
              fill=(42, 46, 52), outline=(206, 210, 215), width=2)
    d.text((cell_x0 + 22, cell_cz - 10),
           "SENSING CELL  ·  %.0f mm inward" % CART_REACH,
           font=F_BODY, fill=(255, 246, 238))
    d.text((cell_x0 + 22, cell_cz + 12),
           "centred on z = %.0f mm (nostril height)" % CONST["NO_Z"],
           font=F_SMALL, fill=(90, 60, 42))

    # Front wall aperture in section; the rest of the UI is dimensioned in the
    # elevation inset below.  The lid stays a plain plate.
    d.rectangle([160, lid_top, 1030, lid_under], fill=(168, 205, 236, 150),
                outline=(90, 130, 170), width=2)
    d.rectangle([160, sz(WIN_Z1), 160 + CONST["WALL"] * S, sz(WIN_Z0)],
                fill=(20, 32, 42), outline=(30, 150, 215), width=2)
    d.text((170, lid_top + 10), "PLAIN FLAT LID  z = %.1f mm" % CONST["LID_Z0"],
           font=F_SMALL, fill=(22, 58, 90))
    d.text((168, sz(WIN_Z1) - 18),
           "FRONT-WALL APERTURE %.0f x %.0f" %
           (CONST["DISP_WIN_W"], CONST["DISP_WIN_H"]),
           font=F_SMALL, fill=(18, 110, 165))

    xd = 900
    d.line([(xd, card_top_px), (xd, lid_under)], fill=(20, 90, 140), width=2)
    d.polygon([(xd, lid_under), (xd - 7, lid_under + 12), (xd + 7, lid_under + 12)],
              fill=(20, 90, 140))
    d.polygon([(xd, card_top_px), (xd - 7, card_top_px - 12),
               (xd + 7, card_top_px - 12)], fill=(20, 90, 140))
    d.text((xd + 14, (card_top_px + lid_under) / 2 - 10),
           "%.1f mm free hood" % HOOD, font=F_BODY, fill=(15, 80, 130))
    d.text((530, card_top_px - 34), "card top z = %.1f mm" % CARD_TOP,
           font=F_SMALL, fill=(15, 80, 130))

    for k in range(3):
        yy = cell_cz + 30 - k * 9
        d.line([(190, yy + 20), (390, yy), (830, yy), (1000, yy - 12)],
               fill=(30, 150, 215, 210), width=3)
        d.polygon([(1000, yy - 12), (986, yy - 18), (986, yy - 6)],
                  fill=(30, 150, 215, 230))
    d.text((190, cell_cz - 44), "SAMPLE AIR  ->  centred channel to the rear fan",
           font=F_BODY, fill=(18, 110, 165))

    ix, iy = 1090, 260
    sc = 2.0
    d.rounded_rectangle([ix - 20, iy - 34, ix + 280, iy + 244], 10,
                        fill=(255, 255, 255, 220), outline=(150, 170, 190), width=2)
    d.text((ix, iy - 24), "TOP VIEW  (flow = up)", font=F_PANEL, fill=(20, 44, 68))
    d.rectangle([ix + 25, iy + 8, ix + 25 + CONST["SW"] * sc,
                 iy + 8 + CONST["SH"] * sc], outline=(100, 120, 140), width=1)
    left_x = ix + 25 + CONST["SOCK_X_L"] * sc
    right_x = ix + 25 + CONST["SOCK_X_R"] * sc
    d.rectangle([left_x, iy + 8, left_x + CART_W * sc * 0.15,
                 iy + 8 + CONST["SW"] * sc], fill=(34, 92, 62))
    d.rectangle([right_x, iy + 8, right_x + CART_W * sc * 0.15,
                 iy + 8 + CONST["SW"] * sc], fill=(34, 92, 62))
    d.text((ix + 46, iy + 100), "CHANNEL", font=F_SMALL, fill=(20, 90, 140))
    for nx in NO_X:
        d.ellipse([ix + 25 + nx * sc - CONST["NO_R"] * sc,
                   iy + 8 - CONST["NO_R"] * sc,
                   ix + 25 + nx * sc + CONST["NO_R"] * sc,
                   iy + 8 + CONST["NO_R"] * sc], fill=(30, 150, 215))
    for y in CONST["ROW_Y"]:
        for wx in (left_x, right_x):
            d.rectangle([wx - 2, iy + 8 + y * sc - 7, wx + 4,
                         iy + 8 + y * sc + 7], fill=(12, 68, 43))
    fan_cx = ix + 25 + CONST["FAN_X"] * sc
    d.ellipse([fan_cx - CONST["FAN_R"] * sc, iy + 8 + CONST["SW"] * sc - 8,
               fan_cx + CONST["FAN_R"] * sc, iy + 8 + CONST["SW"] * sc + 8],
              fill=(90, 100, 110))
    jx = ix + 25 + FAN_HARNESS["shell_x"] * sc
    jy = iy + 8 + FAN_HARNESS["shell_y"] * sc
    d.ellipse([jx - 5, jy - 5, jx + 5, jy + 5], fill=(246, 191, 82))
    d.text((jx - 32, jy - 20), "%s rear centre" % FAN_HARNESS["ref"],
           font=F_TINY, fill=(120, 78, 20))
    d.text((ix + 8, iy + 150), "SOCK_X_L=%g" % CONST["SOCK_X_L"],
           font=F_TINY, fill=(30, 80, 58))
    d.text((ix + 185, iy + 150), "SOCK_X_R=%g" % CONST["SOCK_X_R"],
           font=F_TINY, fill=(30, 80, 58))
    d.text((ix + 105, iy + 200), "ROW_Y=%s" % CONST["ROW_Y"],
           font=F_TINY, fill=(30, 80, 58))

    # Front wall elevation: aperture, stack footprint, grommet and four buttons.
    d.text((ix, 546), "FRONT WALL UI  (ELEVATION)", font=F_PANEL,
           fill=(20, 44, 68))
    us = 1.6

    def ux(x):
        return 1098 + x * us

    def uz(z):
        return 646 - z * us

    d.rectangle([ux(0), uz(60), ux(CONST["SH"]), uz(0)],
                fill=(205, 220, 236), outline=(100, 120, 140), width=1)
    d.rectangle([ux(DISP_X0), uz(DISP_Z1), ux(DISP_X1), uz(DISP_Z0)],
                fill=(236, 240, 245), outline=(90, 130, 170), width=2)
    d.rectangle([ux(WIN_X0), uz(WIN_Z1), ux(WIN_X1), uz(WIN_Z0)],
                fill=(14, 32, 42), outline=(30, 150, 215), width=2)
    d.text((ux(CONST["DISP_X"]), uz(CONST["DISP_Z"]) - 6), "0x3C",
           font=F_TINY, fill=(210, 245, 255), anchor="mm")
    fx, fz = CONST["UI_FEED_X"], CONST["UI_FEED_Z"]
    fr = CONST["UI_FEED_D"] / 2.0
    d.ellipse([ux(fx - fr), uz(fz + fr), ux(fx + fr), uz(fz - fr)],
              fill=(246, 191, 82), outline=(120, 78, 20), width=1)
    for bx, bz in BTN_FRONT.values():
        br = CONST["BTN_HOLE_D"] / 2.0
        d.ellipse([ux(bx - br), uz(bz + br), ux(bx + br), uz(bz - br)],
                  fill=(20, 32, 42), outline=(30, 150, 215), width=1)
    d.text((1098, 654), "dia6 grommet at (%g,%g)  ·  four dia3.4 front buttons" %
           (fx, fz), font=F_TINY, fill=(45, 80, 110))

    notes = [
        "PIN LINE FRONT-TO-BACK  ->  boards stand upright and face inward",
        "NOSTRILS CENTRED ON THE CHANNEL  ->  straight to the rear fan",
        "ENVELOPE %.0f along wall x %.0f tall x %.0f reach  ->  %.1f mm hood" %
        (CART_W, CART_H, CART_REACH, HOOD),
        "FRONT WALL: OLED 0x3C, dia6 grommet, four buttons; plain lid, 4 x M3",
    ]
    y = 690
    for n in notes:
        d.ellipse([45, y + 5, 53, y + 13], fill=(30, 150, 215))
        d.text((66, y), n, font=F_BODY, fill=(25, 48, 72))
        y += 24
    d.text((66, y + 6), GEOMETRY["VISUAL_NOTE"], font=F_SMALL,
           fill=(76, 96, 116))
    im.save(path, pnginfo=geom_pnginfo())
    print("  wrote", path)


def main():
    os.makedirs(OUT, exist_ok=True)
    total = 96
    print("rendering %d frames from CONST + routed board geometry" % total)
    frames = [render_frame(i, total) for i in range(total)]
    gif = os.path.join(OUT, "assembly_animation.gif")
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=75,
                   loop=0, optimize=False, disposal=2,
                   comment=json.dumps(GEOMETRY, sort_keys=True))
    print("  wrote", gif)
    render_storyboard(frames, os.path.join(OUT, "assembly_storyboard.png"))
    for name, idx in (("assembly_assembled_iso.png", -1),
                      ("assembly_flow_top.png", 52),
                      ("assembly_exploded_iso.png", 30)):
        path = os.path.join(OUT, name)
        frames[idx].save(path, pnginfo=geom_pnginfo())
        print("  wrote", path)
    render_header_proof(os.path.join(OUT, "header_proof.png"))


if __name__ == "__main__":
    main()
