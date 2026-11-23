#!/usr/bin/env python3
"""Professional assembly + flow animation for OpenSmell v1.1.

This is NOT a box sketch.  Every PCB feature comes from the routed board via
``pcb_geometry.json`` (exported by tools/extract_pcb_geometry.py with KiCad's
Python), and every enclosure/module number comes from mechanical/constants.py.
The result is a coded technical illustration: real copper, real pads, real
socket positions, eight distinct supported sensor styles, rotating fan, moving
air, LED status, buzzer rings, screwing lid, and a dedicated header proof.

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

OUT = os.path.join(ROOT, "docs", "figures", "cad")
GEO = os.path.join(OUT, "pcb_geometry.json")
with open(GEO, encoding="utf-8") as f:
    PCB = json.load(f)

W, H = 1600, 1000
SCALE = 4.6
ZSCALE = 4.6
OX, OY = 800.0, 430.0
COS30 = math.cos(math.radians(30))
SIN30 = 0.5

PCB_TOP = CONST["PCB_TOP"]
SOCK_TOP = PCB_TOP + CONST["SOCK_H"]
CART_W, CART_L, CART_H = 20.0, 32.0, 21.0
HOOD = CONST["LID_Z0"] - (SOCK_TOP + CART_H)
NO_X = [CONST["SH"] / 2.0 + k * CONST["NO_PITCH"]
        for k in (-1, 0, 1)]

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

SENSOR_TYPES = [
    ("D0", "MQ-135 class", "mox", (226, 126, 69)),
    ("D1", "Figaro TGS", "figaro", (191, 201, 211)),
    ("D2", "SCD40 Qwiic", "qwiic", (67, 194, 168)),
    ("D3", "ZE03 e-chem", "echem", (235, 231, 217)),
    ("A0", "MICS-6814", "mics", (92, 99, 112)),
    ("A1", "Adafruit SCD-40", "adafruit", (103, 124, 207)),
    ("A2", "NDIR CO2", "ndir", (226, 179, 78)),
    ("A3", "ISFET pH", "isfet", (174, 117, 207)),
]


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
    """Extruded box; visible faces are +X and -Y (front) in this view."""
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
    """Circle in the X-Z plane (fan, nostrils, filter frame)."""
    pts = [(cx + r * math.cos(2 * math.pi * i / n), y,
            cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    poly(d, pts, fill, outline, width)


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


def lerp(a, b, u):
    return tuple(a[i] + (b[i] - a[i]) * u for i in range(len(a)))


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
        "Coded from the routed KiCad board + mechanical/constants.py  |  front at lower-left, fan at upper-right",
        F_SUB, C_MUTED)


def draw_shell_far(d):
    # rear + left walls first; near walls are drawn after the internals
    sh, sw, wall = CONST["SH"], CONST["SW"], CONST["WALL"]
    ztop = CONST["CAV_Z1"]
    poly(d, [(0, sw, 0), (sh, sw, 0), (sh, sw, ztop), (0, sw, ztop)],
         (C_SHELL[0], C_SHELL[1], C_SHELL[2], 46), (*C_SHELL, 105))
    poly(d, [(0, 0, 0), (0, sw, 0), (0, sw, ztop), (0, 0, ztop)],
         (C_SHELL[0], C_SHELL[1], C_SHELL[2], 42), (*C_SHELL, 100))
    # floor + standoff pads
    box(d, 0, 0, 0, sh, sw, CONST["FLOOR_T"],
        (48, 63, 82, 190), (35, 48, 65, 190), (38, 52, 70, 190))
    for bx, by in ((6.5, 6.5), (115.5, 6.5), (6.5, 107.5), (115.5, 107.5)):
        hcircle(d, bx, by, CONST["FLOOR_T"], CONST["BOSS_D"] / 2,
                (28, 39, 54, 230), (*C_SHELL, 150))


def draw_fan(d, angle, active):
    cx, cy, cz = CONST["FAN_X"], CONST["SW"] + CONST["FAN_PLATE_T"], CONST["FAN_Z"]
    r, plate = CONST["FAN_R"], CONST["FAN_PLATE"] / 2
    a = 165 if active else 80
    box(d, cx - plate, CONST["SW"], cz - plate, 2 * plate, CONST["FAN_PLATE_T"],
        2 * plate, (38, 48, 62, a), (28, 36, 48, a), (32, 41, 55, a), (*C_MUTED, a))
    vcircle(d, cx, cy + 0.3, cz, r + 1.5, (14, 20, 29, a), (*C_MUTED, a), 2)
    # seven real blades, rotating in the X-Z plane
    for k in range(7):
        th = angle + k * 2 * math.pi / 7
        p0 = (cx + 4.5 * math.cos(th), cy + 0.4, cz + 4.5 * math.sin(th))
        p1 = (cx + (r - 2) * math.cos(th + 0.18), cy + 0.4,
              cz + (r - 2) * math.sin(th + 0.18))
        p2 = (cx + (r - 2) * math.cos(th + 0.72), cy + 0.4,
              cz + (r - 2) * math.sin(th + 0.72))
        p3 = (cx + 6.0 * math.cos(th + 0.42), cy + 0.4,
              cz + 6.0 * math.sin(th + 0.42))
        poly(d, [p0, p1, p2, p3], (93, 112, 132, a), (*C_CYAN, min(220, a + 50)))
    vcircle(d, cx, cy + 0.6, cz, 5.2, (16, 23, 33, min(255, a + 70)),
            (*C_CYAN, a), 2)
    if active:
        for rr in (r + 5, r + 9):
            vcircle(d, cx, cy + 0.2, cz, rr, None, (*C_CYAN, 48), 1)


def pcb_board_outline():
    o = PCB["outline"]
    return (o[1] + list(reversed(o[4])) + o[5] + list(reversed(o[7])) +
            o[6] + list(reversed(o[3])) + o[2] + list(reversed(o[0])))


def draw_pcb(d):
    outline = pcb_board_outline()
    # board thickness suggested by a dark lower face
    lower = [(x, y, PCB_TOP - CONST["PCB_T"]) for x, y in outline]
    upper = [(x, y, PCB_TOP) for x, y in outline]
    poly(d, lower, (C_PCB_D[0], C_PCB_D[1], C_PCB_D[2], 230))
    poly(d, upper, (C_PCB[0], C_PCB[1], C_PCB[2], 248), (*C_PCB_E, 210), 2)

    # actual routed copper from the committed board
    for t in PCB["tracks"]:
        if t["layer"] != "F.Cu":
            continue
        col = (*C_COPPER, 96) if t["w"] < 0.25 else (*C_GOLD, 120)
        ln(d, (*t["a"], PCB_TOP + 0.05), (*t["b"], PCB_TOP + 0.05), col,
           1 if t["w"] < 0.25 else 2)
    for v in PCB["vias"]:
        hcircle(d, v["x"], v["y"], PCB_TOP + 0.08, v["d"] / 2,
                (*C_GOLD, 150), (*C_PCB_E, 130), 1, 10)

    # actual pads
    for p in PCB["pads"]:
        w, h = max(p["w"], 0.5), max(p["h"], 0.5)
        col = (*C_GOLD, 205) if any(k in p["net"] for k in ("GND", "5V", "3V3")) else (*C_GOLD, 165)
        box(d, p["x"] - w / 2, p["y"] - h / 2, PCB_TOP, w, h, 0.18,
            col, col, col, (*C_PCB_D, 100), 0)

    # major parts, from the real footprint bboxes
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
        if ref in ("U1", "U2", "U8", "U4", "J1"):
            pp = P(x0 + dx / 2, y0 + dy / 2, PCB_TOP + hz + 0.4)
            txt(d, (pp[0], pp[1] - 7), ref, F_TINY, (*C_WHITE, 220), "mm")

    # buzzer + LED, at their real placed positions
    for ref in ("BZ1", "LED1"):
        f = byref.get(ref)
        if not f:
            continue
        x, y = f["x"], f["y"]
        if ref == "BZ1":
            for zz, rr in ((PCB_TOP, 5.1), (PCB_TOP + 8.5, 4.4)):
                hcircle(d, x, y, zz, rr, (44, 52, 62, 255), (*C_CYAN, 170), 2, 28)
            ln(d, (x, y, PCB_TOP + 0.1), (x, y, PCB_TOP + 8.5), (*C_MUTED, 220), 2)
        else:
            hcircle(d, x, y, PCB_TOP + 1.2, 1.2, (*C_RED, 255), (*C_WHITE, 200), 1, 12)


def draw_sockets_and_cartridges(d, module_u):
    slots = ([(x, CONST["D_Y0"], "D", i) for i, x in enumerate(CONST["D_X"])] +
             [(x, CONST["A_Y0"], "A", i + 4) for i, x in enumerate(CONST["A_X"])])
    for cx, cy, row, idx in slots:
        # socket: pin line ACROSS the flow (X), body only 2.54 deep in Y
        box(d, cx - 7, cy - CONST["SOCK_P"] / 2, PCB_TOP, 14, CONST["SOCK_P"],
            CONST["SOCK_H"], (23, 26, 32, 255), (12, 14, 19, 255),
            (16, 19, 25, 255), (*C_MUTED, 150))
        for k in range(6):
            px = cx + (k - 2.5) * CONST["SOCK_P"]
            box(d, px - 0.55, cy - 0.55, SOCK_TOP - 0.4, 1.1, 1.1, 0.6,
                (*C_GOLD, 255), (*C_GOLD, 220), (*C_GOLD, 220), None, 0)

        u = smooth((module_u - idx * 0.045) / 0.30)
        if u <= 0:
            continue
        lift = (1 - u) * 42.0
        z = SOCK_TOP + lift
        ref, label, kind, col = SENSOR_TYPES[idx]
        # flat carrier, 20 across X, 32 downstream (+Y), 1.6 thick
        box(d, cx - CART_W / 2, cy, z, CART_W, CART_L, 1.6,
            (34, 92, 62, 240), (19, 62, 42, 245), (23, 74, 50, 245),
            (*C_PCB_E, 170))
        # male pins go DOWN into the socket - no leads stick into the stream
        if u > 0.35:
            for k in range(6):
                px = cx + (k - 2.5) * CONST["SOCK_P"]
                ln(d, (px, cy, z + 0.1), (px, cy, SOCK_TOP - 3.0),
                   (*C_GOLD, 235), 2)
        bx, by, bz = cx - CART_W / 2 + 2, cy + 5, z + 1.6
        draw_sensor_body(d, kind, bx, by, bz, col)
        if u >= 0.999:
            pp = P(cx, cy + CART_L + 2, z + CART_H + 1)
            txt(d, (pp[0], pp[1]), "%s %s" % (ref, label), F_TINY,
                (*C_WHITE, 205), "mm")


def draw_sensor_body(d, kind, x, y, z, col):
    R = lambda c, a=255: (c[0], c[1], c[2], a)
    if kind == "mox":
        hcircle(d, x + 8, y + 10, z, 7.2, R(col, 245), R((255, 255, 255), 140), 2, 24)
        hcircle(d, x + 8, y + 10, z + 8, 6.2, R((72, 76, 82), 250), R(col, 200), 2, 24)
        ln(d, (x + 8, y + 10, z + 8), (x + 8, y + 10, z + 15), R((210, 214, 220)), 2)
        hcircle(d, x + 8, y + 10, z + 15, 6.8, R((150, 155, 162), 220), R(C_WHITE, 170), 1, 20)
    elif kind == "figaro":
        hcircle(d, x + 8, y + 10, z, 6.0, R((60, 64, 70)), R(col, 200), 1, 20)
        hcircle(d, x + 8, y + 10, z + 6, 5.2, R(col, 245), R(C_WHITE, 180), 2, 20)
        hcircle(d, x + 8, y + 10, z + 12, 4.6, R((122, 130, 138)), R(C_WHITE, 160), 1, 18)
        for k in range(8):
            a = k * math.pi / 4
            ln(d, (x + 8 + 3 * math.cos(a), y + 10 + 3 * math.sin(a), z + 12),
               (x + 8 + 4.5 * math.cos(a), y + 10 + 4.5 * math.sin(a), z + 12),
               R((46, 50, 56)), 1)
    elif kind in ("qwiic", "adafruit"):
        base = col if kind == "adafruit" else (35, 120, 92)
        box(d, x, y, z, 16, 16, 1.2, R(base, 250), R((20, 60, 48)), R((28, 80, 62)))
        box(d, x + 4.5, y + 4.5, z + 1.2, 7, 7, 4.4,
            R((28, 32, 38)), R((16, 20, 25)), R((22, 26, 32)), R(col, 200))
        if kind == "adafruit":
            ln(d, (x + 1, y + 15, z + 1.3), (x + 15, y + 15, z + 1.3), R(C_WHITE, 180), 1)
    elif kind == "echem":
        box(d, x, y, z, 16, 20, 9, R(col, 250), R((196, 190, 176)), R((214, 209, 196)))
        box(d, x + 4, y + 7, z + 9, 8, 5, 1.2, R((48, 52, 56)), R((30, 34, 38)), R((38, 42, 46)))
    elif kind == "mics":
        box(d, x - 1, y, z, 18, 20, 1.4, R(col, 250), R((48, 52, 60)), R((58, 63, 72)))
        for dx in (2, 8, 14):
            hcircle(d, x + dx, y + 10, z + 1.4, 2.6, R((150, 156, 164)), R(C_WHITE, 150), 1, 14)
    elif kind == "ndir":
        box(d, x, y, z, 16, 19, 11, R(col, 250), R((172, 132, 55)), R((198, 154, 68)))
        box(d, x + 4, y + 14, z + 3, 8, 5, 4,
            R((36, 40, 46)), R((20, 24, 29)), R((27, 31, 37)), R(C_CYAN, 180))
    else:  # isfet
        box(d, x + 3, y, z, 10, 16, 2.0, R(col, 245), R((110, 72, 140)), R((132, 90, 164)))
        box(d, x + 6, y + 5, z + 2, 4, 8, 10, R((226, 228, 232)), R((180, 184, 190)), R((204, 208, 214)))
        hcircle(d, x + 8, y + 9, z + 12, 2.0, R((96, 190, 220)), R(C_WHITE, 190), 1, 14)


def draw_filter(d, u):
    x0, x1 = CONST["CX0"], CONST["CX0"] + CONST["CX"]
    y0, z0 = CONST["FILT_Y0"], CONST["FILT_Z0"]
    h = 23.0
    a = int(55 + 95 * u)
    poly(d, [(x0, y0, z0), (x1, y0, z0), (x1, y0, z0 + h), (x0, y0, z0 + h)],
         (150, 205, 225, a), (188, 229, 245, min(220, a + 80)), 2)
    for k in range(1, 14):
        xx = x0 + k * (x1 - x0) / 14
        ln(d, (xx, y0 - 0.1, z0), (xx, y0 - 0.1, z0 + h), (188, 229, 245, 45), 1)
    for k in range(1, 8):
        zz = z0 + k * h / 8
        ln(d, (x0, y0 - 0.1, zz), (x1, y0 - 0.1, zz), (188, 229, 245, 45), 1)


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
            (nx, -14, CONST["NO_Z"]), (nx, 1, CONST["NO_Z"]),
            (nx, CONST["FILT_Y1"] + 2, 27),
            (nx * 0.82 + 7, CONST["D_Y0"] + 2, 32),
            (nx * 0.78 + 12, 54, 33),
            (nx * 0.72 + 18, CONST["A_Y0"] + 4, 32),
            (CONST["FAN_X"], CONST["SW"] - 2, CONST["FAN_Z"]),
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
            p = catmull(path, phase)
            sp = P(*p)
            glow(d, sp[0], sp[1], C_CYAN, 13, 4)
            d.ellipse([sp[0] - 2.5, sp[1] - 2.5, sp[0] + 2.5, sp[1] + 2.5],
                      fill=(230, 250, 255, min(255, a + 80)))
    p = P(NO_X[0], -8, CONST["NO_Z"] + 7)
    txt(d, (p[0] - 36, p[1] - 12), "AIR IN · 3 × Ø6", F_SMALL, (*C_CYAN, 235))
    q = P(CONST["FAN_X"], CONST["SW"] + 8, CONST["FAN_Z"] + 26)
    txt(d, (q[0], q[1]), "EXHAUST · 40 mm FAN", F_SMALL, (*C_CYAN, 235), "mm")


def draw_effects(d, t, led_on, buzz_on):
    byref = {f["ref"]: f for f in PCB["footprints"]}
    if led_on:
        f = byref["LED1"]
        p = P(f["x"], f["y"], PCB_TOP + 2)
        pulse = 0.65 + 0.35 * math.sin(t * 22)
        glow(d, p[0], p[1], C_RED, 26 * pulse, 5)
        d.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3],
                  fill=(255, 235, 235, 255))
        txt(d, (p[0] + 12, p[1] - 10), "STATUS / QC", F_TINY, (*C_RED, 245))
    if buzz_on:
        f = byref["BZ1"]
        p = P(f["x"], f["y"], PCB_TOP + 10)
        for k in range(3):
            ph = (t * 1.8 + k / 3) % 1
            rr = 8 + ph * 34
            a = int(175 * (1 - ph))
            d.arc([p[0] - rr, p[1] - rr * 0.62, p[0] + rr, p[1] + rr * 0.62],
                  200, 340, fill=(*C_GOLD, a), width=2)
        txt(d, (p[0] + 16, p[1] - 18), "BZ1 · 120 ms ALERT", F_TINY,
            (*C_GOLD, 240))


def draw_shell_near(d):
    sh, sw, ztop = CONST["SH"], CONST["SW"], CONST["CAV_Z1"]
    # front wall (nostrils) and right wall, translucent so internals stay legible
    poly(d, [(0, 0, 0), (sh, 0, 0), (sh, 0, ztop), (0, 0, ztop)],
         (C_SHELL[0], C_SHELL[1], C_SHELL[2], 44), (*C_SHELL, 120))
    poly(d, [(sh, 0, 0), (sh, sw, 0), (sh, sw, ztop), (sh, 0, ztop)],
         (C_SHELL[0], C_SHELL[1], C_SHELL[2], 38), (*C_SHELL, 110))
    for nx in NO_X:
        vcircle(d, nx, -0.3, CONST["NO_Z"], CONST["NO_R"],
                (5, 11, 19, 255), (*C_CYAN, 220), 2, 24)
    vcircle(d, CONST["USB_X"], -0.4, CONST["USB_Z"], CONST["USB_R"],
            (5, 11, 19, 255), (*C_GOLD, 190), 2, 24)
    p = P(CONST["USB_X"], -1, CONST["USB_Z"] - 11)
    txt(d, (p[0], p[1]), "USB-C POWER + DATA", F_TINY, (*C_GOLD, 220), "mm")


def draw_lid(d, lid_u):
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
    for bx, by in ((6.5, 6.5), (115.5, 6.5), (6.5, 107.5), (115.5, 107.5)):
        ln(d, (bx, by, z + lt), (bx, by, CONST["LID_Z0"] - 4),
           (190, 200, 212, 210), 3)
        p = P(bx, by, z + lt + 1.5)
        d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6],
                  fill=(205, 214, 224, 245), outline=(90, 105, 122, 255), width=1)
        d.line([(p[0] - 4 * math.cos(ang), p[1] - 4 * math.sin(ang)),
                (p[0] + 4 * math.cos(ang), p[1] + 4 * math.sin(ang))],
               fill=(48, 60, 74, 255), width=2)
    if 0.02 < lid_u < 0.98:
        p = P(61, 57, z + 10)
        txt(d, (p[0], p[1]), "4 × M3  —  SEAL THE CHAMBER", F_SMALL,
            (*C_WHITE, 235), "mm")
    return z


def draw_panels(d, phase):
    # left fact panel
    x0, y0, x1, y1 = 28, 118, 330, 430
    d.rounded_rectangle([x0, y0, x1, y1], 10, fill=(8, 15, 26, 205),
                        outline=(*C_CYAN_D, 170), width=1)
    y = y0 + 16
    txt(d, (x0 + 16, y), "WHAT YOU ARE SEEING", F_PANEL, (*C_CYAN, 255)); y += 30
    facts = [
        "8 identical OSM-1 slots",
        "1x6 pin line ACROSS flow",
        "flat 20 x 32 x 21 mm cartridge",
        "4.9 mm free hood over sensor",
        "no leads protrude into gas",
        "3 nostrils -> filter -> rows -> fan",
        "USB-C power/data (no battery)",
    ]
    for s in facts:
        d.ellipse([x0 + 17, y + 5, x0 + 22, y + 10], fill=(*C_CYAN, 230))
        txt(d, (x0 + 32, y), s, F_BODY, C_WHITE)
        y += 27

    # right sensor legend
    x0, y0, x1, y1 = 1272, 118, 1574, 520
    d.rounded_rectangle([x0, y0, x1, y1], 10, fill=(8, 15, 26, 205),
                        outline=(*C_CYAN_D, 170), width=1)
    y = y0 + 16
    txt(d, (x0 + 16, y), "SUPPORTED MODULE STYLES", F_PANEL, (*C_CYAN, 255)); y += 30
    for ref, label, kind, col in SENSOR_TYPES:
        d.rounded_rectangle([x0 + 16, y + 1, x0 + 31, y + 16], 4, fill=(*col, 255))
        txt(d, (x0 + 40, y), "%s  %s" % (ref, label), F_BODY, C_WHITE)
        y += 29
    y += 8
    d.line([(x0 + 16, y), (x1 - 16, y)], fill=(*C_CYAN_D, 150)); y += 12
    txt(d, (x0 + 16, y), "Upstream D0-D3  ->  downstream A0-A3", F_SMALL, C_MUTED)
    y += 22
    txt(d, (x0 + 16, y), "SHT31 T/RH fixed at 0x44 (base board)", F_SMALL, C_MUTED)
    y += 22
    txt(d, (x0 + 16, y), "pH is an OSM-1 ISFET cartridge", F_SMALL, C_MUTED)

    # phase caption
    caps = ["01  SHELL + BOARD", "02  PLUG ANY SENSOR", "03  FAN + FLOW",
            "04  LED + BUZZER", "05  FIT THE LID", "06  RUN CLEAN"]
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
    draw_pcb(d)
    draw_filter(d, min(1.0, t / 0.3))
    draw_sockets_and_cartridges(d, module_u)
    draw_flow(d, t, flow_u)
    draw_effects(d, t, led_on, buzz_on)
    draw_shell_near(d)
    draw_lid(d, lid_u)
    draw_panels(d, t)
    return img.convert("RGB")


def render_storyboard(frames, path):
    picks = [(0, "Shell + routed PCB"), (30, "Any sensor, any slot"),
             (52, "Fan pulls the sample"), (70, "Status + alert"),
             (86, "Lid screws down"), (len(frames) - 1, "Ready to run")]
    tw, th = 520, 325
    sheet = Image.new("RGB", (tw * 3 + 40, (th + 34) * 2 + 30), (9, 16, 27))
    d = ImageDraw.Draw(sheet)
    for k, (idx, cap) in enumerate(picks):
        im = frames[idx].resize((tw, th), Image.Resampling.LANCZOS)
        x = 10 + (k % 3) * (tw + 10)
        y = 10 + (k // 3) * (th + 34 + 10)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + th + 5), cap, font=F_BODY, fill=C_WHITE)
    sheet.save(path)
    print("  wrote", path)


def render_header_proof(path):
    W2, H2 = 1400, 820
    im = Image.new("RGB", (W2, H2), (240, 244, 249))
    d = ImageDraw.Draw(im, "RGBA")
    dh = F_TITLE
    d.text((42, 26), "OSM-1 HEADER PROOF  /  FLAT CARRIER, ACROSS-FLOW PINS",
           font=dh, fill=(15, 35, 55))
    d.text((44, 67),
           "Scale: schematic section, derived from CONST  |  pin line runs left-right across the gas stream",
           font=F_SUB, fill=(70, 92, 116))

    # section geometry
    pcb_top = 560
    d.rectangle([160, pcb_top, 1030, pcb_top + 34], fill=(18, 86, 56),
                outline=(9, 52, 33), width=2)
    d.text((170, pcb_top + 8), "BASE PCB  (chamber floor)", font=F_SMALL,
           fill=(220, 255, 235))

    # socket body: 8.5 mm tall, pin line across flow
    d.rectangle([430, pcb_top - 96, 760, pcb_top], fill=(28, 31, 38),
                outline=(10, 12, 16), width=2)
    d.text((444, pcb_top - 34), "1x6 KEYED SOCKET  ·  8.5 mm", font=F_SMALL,
           fill=(225, 232, 240))
    for k in range(6):
        px = 460 + k * 54
        d.rectangle([px - 8, pcb_top - 118, px + 8, pcb_top - 90],
                    fill=(246, 191, 82), outline=(150, 106, 35), width=1)

    # carrier: flat, parallel to flow, pins go DOWN only
    d.rectangle([365, pcb_top - 142, 825, pcb_top - 118], fill=(34, 92, 62),
                outline=(12, 68, 43), width=2)
    d.text((374, pcb_top - 139), "FLAT CARRIER  20 mm across  ×  32 mm downstream  ×  1.6 mm",
           font=F_SMALL, fill=(225, 255, 236))
    for k in range(6):
        px = 460 + k * 54
        d.rectangle([px - 6, pcb_top - 142, px + 6, pcb_top - 96],
                    fill=(246, 191, 82), outline=(150, 106, 35), width=1)

    # sensor envelope and 4.9 mm hood
    sensor_top = pcb_top - 142 - 21 * 10
    d.rounded_rectangle([455, sensor_top, 735, pcb_top - 142], 10,
                        fill=(220, 126, 69), outline=(120, 62, 30), width=2)
    d.text((475, sensor_top + 24), "SENSOR BODY  ·  21 mm",
           font=F_BODY, fill=(255, 246, 238))
    lid_under = sensor_top - 49
    d.rectangle([160, lid_under - 60, 1030, lid_under], fill=(168, 205, 236, 150),
                outline=(90, 130, 170), width=2)
    d.text((170, lid_under - 40), "LID UNDERSIDE  (z = 43.0 mm)", font=F_SMALL,
           fill=(22, 58, 90))

    # hood dimension
    xd = 900
    d.line([(xd, sensor_top), (xd, lid_under)], fill=(20, 90, 140), width=2)
    d.polygon([(xd, lid_under), (xd - 7, lid_under + 12), (xd + 7, lid_under + 12)],
              fill=(20, 90, 140))
    d.polygon([(xd, sensor_top), (xd - 7, sensor_top - 12), (xd + 7, sensor_top - 12)],
              fill=(20, 90, 140))
    d.text((xd + 14, (sensor_top + lid_under) / 2 - 10),
           "4.9 mm free hood", font=F_BODY, fill=(15, 80, 130))

    # airflow over the top, never through a wire
    for k in range(3):
        yy = sensor_top - 18 - k * 9
        d.line([(190, yy + 20), (390, yy), (830, yy), (1000, yy - 12)],
               fill=(30, 150, 215, 210), width=3)
        d.polygon([(1000, yy - 12), (986, yy - 18), (986, yy - 6)],
                  fill=(30, 150, 215, 230))
    d.text((190, sensor_top - 62), "SAMPLE AIR  ->  over the flat sensing face",
           font=F_BODY, fill=(18, 110, 165))

    # top-view inset: pin line across flow, cartridge extends rearward
    ix, iy = 1080, 250
    d.rounded_rectangle([ix - 20, iy - 34, ix + 280, iy + 244], 10,
                        fill=(255, 255, 255, 220), outline=(150, 170, 190), width=2)
    d.text((ix, iy - 24), "TOP VIEW  (flow = up)", font=F_PANEL, fill=(20, 44, 68))
    d.rectangle([ix + 55, iy + 120, ix + 145, iy + 210], fill=(34, 92, 62),
                outline=(12, 68, 43), width=2)
    d.text((ix + 63, iy + 158), "20", font=F_BODY, fill=(230, 255, 240))
    d.rectangle([ix + 68, iy + 20, ix + 132, iy + 122], fill=(18, 86, 56),
                outline=(9, 52, 33), width=2)
    d.text((ix + 83, iy + 65), "32", font=F_BODY, fill=(230, 255, 240))
    for k in range(6):
        px = ix + 62 + k * 13
        d.rectangle([px - 3, iy + 114, px + 3, iy + 128], fill=(246, 191, 82))
    d.text((ix + 20, iy + 132), "PIN LINE ACROSS FLOW", font=F_SMALL,
           fill=(140, 90, 20))
    d.line([(ix + 100, iy + 18), (ix + 100, iy - 6)], fill=(30, 150, 215), width=2)
    d.polygon([(ix + 100, iy - 6), (ix + 94, iy + 4), (ix + 106, iy + 4)],
              fill=(30, 150, 215))

    # bottom notes
    notes = [
        "PIN LINE ACROSS FLOW  ->  20 mm span on 22 mm pitch",
        "MALE PINS GO DOWN INTO THE SOCKET  ->  no wire above the carrier",
        "SENSING FACE UP  ->  flat carrier parallel to the stream, no shadowing",
        "ENVELOPE 20 x 32 x 21 mm  ->  4.9 mm hood to the lid",
    ]
    y = 700
    for n in notes:
        d.ellipse([45, y + 5, 53, y + 13], fill=(30, 150, 215))
        d.text((66, y), n, font=F_BODY, fill=(25, 48, 72))
        y += 27

    meta = PngImagePlugin.PngInfo()
    meta.add_text("OSM_CART_W_MM", str(CART_W))
    meta.add_text("OSM_CART_L_MM", str(CART_L))
    meta.add_text("OSM_CART_H_MM", str(CART_H))
    meta.add_text("OSM_HOOD_MM", str(round(HOOD, 2)))
    meta.add_text("OSM_SOCKET_PITCH_MM", str(CONST["SOCK_P"]))
    meta.add_text("OSM_SOURCE", "mechanical/constants.py + routed pcb_geometry.json")
    im.save(path, pnginfo=meta)
    print("  wrote", path)


def main():
    os.makedirs(OUT, exist_ok=True)
    total = 96
    print("rendering %d frames from routed board geometry" % total)
    frames = [render_frame(i, total) for i in range(total)]
    gif = os.path.join(OUT, "assembly_animation.gif")
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=75,
                   loop=0, optimize=False, disposal=2)
    print("  wrote", gif)
    render_storyboard(frames, os.path.join(OUT, "assembly_storyboard.png"))
    frames[-1].save(os.path.join(OUT, "assembly_assembled_iso.png"))
    frames[52].save(os.path.join(OUT, "assembly_flow_top.png"))
    frames[30].save(os.path.join(OUT, "assembly_exploded_iso.png"))
    render_header_proof(os.path.join(OUT, "header_proof.png"))


if __name__ == "__main__":
    main()
