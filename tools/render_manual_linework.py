#!/usr/bin/env python3
"""Black-and-white line drawing of the v1.1 flow path for the user manual.

Three orthographic views generated from mechanical/constants.py, the OSM-1
machine-readable envelope and the routed board geometry, so the picture cannot
drift from the CAD:

  * PLAN, lid removed - centred nostrils, filter drawer, both side-wall socket
    rows, Qwiic ports, rear-centre J10 fan harness and USB-C
  * SECTION A-A along the flow - board-as-floor, keyed side-wall sockets,
    upright inward-facing parametric cartridges, flow hood, front-wall aperture
    and the rear fan
  * FRONT WALL UI elevation - sealed gasket/acrylic/bezel stack, OLED at master
    I2C 0x3C, Ø6 harness grommet and four button bores/caps; the lid is plain

Licensed vendor STEP models are not in this repo; module shapes are parametric
OSM-1 representations.

Output: docs/figures/cad/manual_linework.svg (vector) and .png (printable).
No third-party renderer: primitives are emitted straight to SVG and to Pillow.
"""
import html
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST  # noqa: E402
from standard import CARTRIDGE, PORT  # noqa: E402

OUT = os.path.join(ROOT, "docs", "figures", "cad")
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "pcb_geometry.json"), encoding="utf-8") as f:
    PCB = json.load(f)
J10 = next(f for f in PCB["footprints"] if f["ref"] == "J10")
FAN_HARNESS = {"ref": J10["ref"], "value": J10["value"],
               "shell_x": J10["x"], "shell_y": J10["y"]}

W, H = 1440, 1000
INK = "#101010"
GREY = "#707070"
LW = 2

# View transforms (mm -> px).  Plan looks down; section looks along +X.
PX0, PY0, PS = 78.0, 132.0, 3.55
SX0, SZ0, SS = 566.0, 404.0, 4.35
# Front-wall elevation transform.
LX0, LY0, LS = 94.0, 628.0, 3.05

CART_W = CARTRIDGE["envelope"]["across"]
CART_H = CONST["CARD_H"]
CART_REACH = CONST["CARD_REACH"]
SOCK_TOP = CONST["PCB_TOP"] + CONST["SOCK_H"]
CARD_TOP = CONST["CARD_TOP"]
HOOD = CONST["HOOD"]
NO_X = [CONST["SH"] / 2.0 + k * CONST["NO_PITCH"] for k in (-1, 0, 1)]
DISP_X0 = CONST["DISP_X"] - CONST["DISP_W"] / 2.0
DISP_X1 = CONST["DISP_X"] + CONST["DISP_W"] / 2.0
DISP_Z0 = CONST["DISP_Z"] - CONST["DISP_H"] / 2.0
DISP_Z1 = CONST["DISP_Z"] + CONST["DISP_H"] / 2.0
WIN_X0 = CONST["DISP_X"] - CONST["DISP_WIN_W"] / 2.0
WIN_X1 = CONST["DISP_X"] + CONST["DISP_WIN_W"] / 2.0
WIN_Z0 = CONST["DISP_Z"] - CONST["DISP_WIN_H"] / 2.0
WIN_Z1 = CONST["DISP_Z"] + CONST["DISP_WIN_H"] / 2.0
BTN_FRONT = {k: list(v) for k, v in CONST["BTN_FRONT"].items()}
VISUAL_NOTE = ("Licensed vendor STEP models are not in this repo; "
               "module shapes are parametric OSM-1 representations.")

GEOMETRY = {
    "source": "mechanical/constants.py + routed pcb_geometry.json",
    "SOCK_X_L": CONST["SOCK_X_L"],
    "SOCK_X_R": CONST["SOCK_X_R"],
    "ROW_Y": list(CONST["ROW_Y"]),
    "SOCK_N": CONST["SOCK_N"],
    "SOCK_P": CONST["SOCK_P"],
    "SOCK_H": CONST["SOCK_H"],
    "PCB_TOP": CONST["PCB_TOP"],
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
    "VISUAL_NOTE": VISUAL_NOTE,
}


def pnginfo():
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
    meta.add_text("OSM_VISUAL_REP", VISUAL_NOTE)
    return meta


def px(x):
    return PX0 + x * PS


def py(y):
    return PY0 + y * PS


def sx(y):
    return SX0 + y * SS


def sz(z):
    return SZ0 - z * SS


def lx(x):
    return LX0 + x * LS


def lz(z):
    return LY0 + (CONST["SHH"] - z) * LS


class Canvas:
    def __init__(self):
        self.items = []

    def line(self, x1, y1, x2, y2, dash=False, w=LW, color=INK, lw=None):
        self.items.append(("line", (x1, y1, x2, y2), dash,
                           lw if lw is not None else w, color))

    def rect(self, x, y, w, h, dash=False, lw=LW, color=INK):
        self.items.append(("rect", (x, y, x + w, y + h), dash, lw, color))

    def circle(self, cx, cy, r, dash=False, lw=LW, color=INK):
        self.items.append(("circle", (cx, cy, r), dash, lw, color))

    def poly(self, pts, dash=False, lw=LW, color=INK):
        self.items.append(("poly", (tuple(pts),), dash, lw, color))

    def text(self, x, y, s, size=15, bold=False, color=INK, anchor="la"):
        self.items.append(("text", (x, y, s, size, bold, anchor), False, 0, color))

    def arrow(self, x1, y1, x2, y2, lw=LW, color=INK, head=9):
        """Line with a filled triangular head."""
        self.items.append(("arrow", (x1, y1, x2, y2, head), False, lw, color))

    # -- SVG ---------------------------------------------------------------
    def svg(self):
        out = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d">' % (W, H, W, H),
            '<metadata>%s</metadata>' % html.escape(json.dumps(GEOMETRY, sort_keys=True)),
            '<rect width="100%" height="100%" fill="#ffffff"/>',
            '<g stroke-linejoin="round" stroke-linecap="round">',
        ]
        for kind, p, dash, lw, color in self.items:
            d = ' stroke-dasharray="4 3"' if dash else ""
            st = 'stroke="%s" stroke-width="%g" fill="none"%s' % (color, lw or 1, d)
            if kind == "line":
                out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" %s/>'
                           % (p + (st,)))
            elif kind == "rect":
                x1, y1, x2, y2 = p
                out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" %s/>'
                           % (x1, y1, x2 - x1, y2 - y1, st))
            elif kind == "circle":
                out.append('<circle cx="%.2f" cy="%.2f" r="%.2f" %s/>'
                           % (p + (st,)))
            elif kind == "poly":
                pts = " ".join("%.2f,%.2f" % q for q in p[0])
                out.append('<polyline points="%s" %s/>' % (pts, st))
            elif kind == "arrow":
                import math
                x1, y1, x2, y2, head = p
                out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" '
                           'stroke="%s" stroke-width="%g"/>'
                           % (x1, y1, x2, y2, color, lw or 2))
                a = math.atan2(y2 - y1, x2 - x1)
                for sgn in (-1, 1):
                    b = a + sgn * 0.42
                    out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" '
                               'stroke="%s" stroke-width="%g"/>'
                               % (x2, y2, x2 - head * math.cos(b),
                                  y2 - head * math.sin(b), color, lw or 2))
            elif kind == "text":
                x, y, s, size, bold, anchor = p
                ha = {"l": "start", "m": "middle", "r": "end"}[anchor[0]]
                out.append('<text x="%.2f" y="%.2f" font-family="Arial,Helvetica,'
                           'sans-serif" font-size="%g" font-weight="%s" '
                           'text-anchor="%s" fill="%s">%s</text>'
                           % (x, y, size, "bold" if bold else "normal", ha,
                              color, html.escape(s)))
        out += ["</g>", "</svg>"]
        return "\n".join(out)

    # -- PNG ----------------------------------------------------------------
    def png(self, path):
        im = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(im)
        cache = {}

        def font(size, bold):
            key = (size, bold)
            if key not in cache:
                name = ("C:/Windows/Fonts/arialbd.ttf" if bold
                        else "C:/Windows/Fonts/arial.ttf")
                try:
                    cache[key] = ImageFont.truetype(name, size)
                except OSError:
                    cache[key] = ImageFont.load_default()
            return cache[key]

        for kind, p, dash, lw, color in self.items:
            w = max(1, int(lw or 1))
            if kind == "line":
                d.line(p[:4], fill=color, width=w)
            elif kind == "rect":
                d.rectangle(p, outline=color, width=w)
            elif kind == "circle":
                cx, cy, r = p
                d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=w)
            elif kind == "poly":
                d.line(list(p[0]), fill=color, width=w)
            elif kind == "arrow":
                import math
                x1, y1, x2, y2, head = p
                d.line((x1, y1, x2, y2), fill=color, width=w)
                a = math.atan2(y2 - y1, x2 - x1)
                for sgn in (-1, 1):
                    b = a + sgn * 0.42
                    d.line((x2, y2, x2 - head * math.cos(b),
                            y2 - head * math.sin(b)), fill=color, width=w)
            elif kind == "text":
                x, y, s, size, bold, anchor = p
                f = font(size, bold)
                box = d.textbbox((0, 0), s, font=f)
                tw, th = box[2] - box[0], box[3] - box[1]
                if anchor[0] == "m":
                    x -= tw / 2
                elif anchor[0] == "r":
                    x -= tw
                if anchor[1] == "m":
                    y -= th / 2
                d.text((x, y), s, fill=color, font=f)
        im.save(path, "PNG", dpi=(300, 300), optimize=True, pnginfo=pnginfo())


c = Canvas()

# ---- sheet furniture ------------------------------------------------------
c.line(60, 92, 1380, 92, w=2)
c.text(60, 42, "OPEN SMELL  /  SMELL MONITOR v1.1", 27, True)
c.text(60, 70, "FIG 1   PLAN, FLOW SECTION AND FRONT WALL UI - OSM-1", 15)
c.text(1380, 70, "SHEET 1 / 1", 15, anchor="ra")
c.text(60, 966, "ALL DIMENSIONS IN MILLIMETRES - GEOMETRY GENERATED FROM "
       "mechanical/constants.py AND routed pcb_geometry.json", 13, color=GREY)
c.line(60, 884, 1380, 884, w=2)
c.line(60, 936, 1380, 936, w=1, color=GREY)
for x in (60, 520, 900, 1380):
    c.line(x, 884, x, 952, w=1, color=GREY)
c.text(74, 900, "DRAWING  OSM-FIG-001", 14, True)
c.text(74, 924, "PLAN + SECTION A-A + FRONT WALL UI", 12, color=GREY)
c.text(534, 900, "PRODUCT  Smell Monitor v1.1", 14)
c.text(534, 924, "INTERFACE  OSM-1", 12, color=GREY)
c.text(914, 900, "REV  B", 14)
c.text(914, 924, "UNITS  mm", 12, color=GREY)

# ---- PLAN VIEW ------------------------------------------------------------
c.text(px(CONST["SH"] / 2), 112, "PLAN - LID REMOVED", 17, True, anchor="ma")

sh, sw = CONST["SH"], CONST["SW"]
c.rect(px(0), py(0), sh * PS, sw * PS)                      # shell outside
c.rect(px(CONST["WALL"]), py(CONST["WALL"]), CONST["CX"] * PS,
       CONST["CY"] * PS, dash=True, lw=1, color=GREY)        # cavity inside
c.rect(px(CONST["PCB_X0"]), py(CONST["PCB_Y0"]), CONST["PCB_X"] * PS,
       CONST["PCB_Y"] * PS, lw=1, color=GREY)               # board outline

inset = CONST["BOSS_INSET"]
for bx, by in ((inset, inset), (sh - inset, inset),
               (inset, sw - inset), (sh - inset, sw - inset)):
    c.circle(px(bx), py(by), CONST["BOSS_D"] / 2 * PS, lw=1)

for nx in NO_X:
    c.circle(px(nx), py(CONST["WALL"] / 2), CONST["NO_R"] * PS)

fx, fw = 6.0, 110.0
fy, fh = CONST["FILT_Y0"], CONST["FILT_T"]
c.rect(px(fx), py(fy), fw * PS, fh * PS)

# keyed sockets: 1x6, pin line front-to-back (Y), on both inner side walls.
# Every socket also has a Qwiic port on the same uniform OSM-1 footprint.
for wall_x, prefix, first in ((CONST["SOCK_X_L"], "D", 1),
                              (CONST["SOCK_X_R"], "A", 5)):
    for i, yc in enumerate(CONST["ROW_Y"]):
        half = CONST["SOCK_N"] * CONST["SOCK_P"] / 2.0
        c.rect(px(wall_x - CONST["SOCK_P"] / 2), py(yc - half),
               CONST["SOCK_P"] * PS, 2 * half * PS)
        c.rect(px(wall_x - CONST["SOCK_P"] * 0.6),
               py(yc - half + CONST["SOCK_P"] * 0.3),
               CONST["SOCK_P"] * 1.2 * PS, CONST["SOCK_P"] * 0.4 * PS,
               lw=1, color=GREY)  # polarising key
        for p in range(CONST["SOCK_N"]):
            c.circle(px(wall_x), py(yc - half + (p + 0.5) * CONST["SOCK_P"]),
                     1.1, lw=1, color=GREY)
        c.rect(px(wall_x + CONST["WALL_GAP"] * 0.25), py(yc + CART_W * 0.30),
               CONST["SOCK_P"] * 1.5 * PS, CONST["SOCK_P"] * PS, lw=1, color=GREY)
        c.text(px(wall_x), py(yc - half - CONST["SOCK_P"] * 1.6),
               "%s%d" % (prefix, first + i), 11, anchor="ma")

c.rect(px(58), py(54), CONST["BOSS_D"] * 0.75 * PS,
       CONST["BOSS_D"] * 0.75 * PS, lw=1)
c.text(px(61), py(61), "SHT31", 10, anchor="ma", color=GREY)

c.circle(px(CONST["FAN_X"]), py(sw), CONST["FAN_R"] * PS,
         dash=True, lw=1, color=GREY)
c.circle(px(CONST["USB_X"]), py(sw), CONST["USB_R"] * PS,
         dash=True, lw=1, color=GREY)
jx, jy = FAN_HARNESS["shell_x"], FAN_HARNESS["shell_y"]
c.circle(px(jx), py(jy), 3.2)

for ax in NO_X:
    c.arrow(px(ax), py(CONST["FILT_Y1"] + CONST["FILT_T"]), px(ax),
            py(sw - CONST["WALL"] * 2), lw=1, color=GREY, head=6)


def leader(x1, y1, x2, y2, label, anchor="la"):
    c.line(x1, y1, x2, y2, lw=1, color=GREY)
    c.circle(x1, y1, 2, lw=1, color=GREY)
    c.text(x2 + (5 if anchor == "la" else -5), y2 - 3, label, 12, anchor=anchor)


leader(px(NO_X[0]), py(CONST["WALL"] / 2), px(8), py(-13),
       "3 x dia6 nostrils, centred")
leader(px(fx + 10), py(fy + 2), px(8), py(-6), "woven PTFE mesh filter")
leader(px(CONST["SOCK_X_R"]), py(CONST["ROW_Y"][2]), px(127), py(86),
       "right wall S4-S7 (upright)", "la")
leader(px(CONST["SOCK_X_L"]), py(CONST["ROW_Y"][2]), px(-8), py(44),
       "left wall S0-S3 (upright)", "ra")
leader(px(jx), py(jy), px(127), py(101), "J10 fan harness, rear centre")
leader(px(CONST["USB_X"]), py(sw), px(127), py(96), "USB-C")

# overall dimensions straight from CONST
c.line(px(0), py(-9), px(sh), py(-9), lw=1, color=GREY)
c.line(px(0), py(-7), px(0), py(-11), lw=1, color=GREY)
c.line(px(sh), py(-7), px(sh), py(-11), lw=1, color=GREY)
c.text(px(sh / 2), py(-11), "%g" % sh, 12, anchor="ma", color=GREY)
c.line(px(-9), py(0), px(-9), py(sw), lw=1, color=GREY)
c.line(px(-11), py(0), px(-7), py(0), lw=1, color=GREY)
c.line(px(-11), py(sw), px(-7), py(sw), lw=1, color=GREY)
c.text(px(-12), py(sw / 2), "%g" % sw, 12, anchor="ma", color=GREY)

# ---- SECTION A-A ----------------------------------------------------------
c.text((sx(0) + sx(sw)) / 2, 128, "SECTION A-A - ALONG THE FLOW", 17, True,
       anchor="ma")
c.rect(sx(0), sz(CONST["FLOOR_T"]), sw * SS, CONST["FLOOR_T"] * SS)
c.rect(sx(0), sz(CONST["LID_Z0"]), CONST["WALL"] * SS,
       (CONST["LID_Z0"] - CONST["FLOOR_T"]) * SS)
c.rect(sx(sw - CONST["WALL"]), sz(CONST["LID_Z0"]), CONST["WALL"] * SS,
       (CONST["LID_Z0"] - CONST["FLOOR_T"]) * SS)

c.rect(sx(CONST["PCB_Y0"]), sz(CONST["PCB_TOP"]), CONST["PCB_Y"] * SS,
       CONST["PCB_T"] * SS)
for sy in (CONST["BOSS_INSET"] * 2, sw - CONST["BOSS_INSET"] * 2):
    c.rect(sx(sy), sz(CONST["PCB_Z"]), CONST["STANDOFF_D"] * SS,
           (CONST["PCB_Z"] - CONST["FLOOR_T"]) * SS, lw=1)

for zc in (CONST["NO_Z"] - CONST["NO_R"], CONST["NO_Z"] + CONST["NO_R"]):
    c.line(sx(0), sz(zc), sx(CONST["WALL"]), sz(zc), lw=1)

c.rect(sx(CONST["FILT_Y0"]), sz(CONST["LID_Z0"]), CONST["FILT_T"] * SS,
       (CONST["LID_Z0"] - CONST["FILT_Z0"]) * SS)

# Four stations per wall: keyed socket + chamfered upright card + clean gas cell
# at the nostril height.  Both rows project onto the same Y stations in section.
ch = CONST["SOCK_P"] / 2.0
for pin_y in CONST["ROW_Y"]:
    c.rect(sx(pin_y - CONST["SOCK_N"] * CONST["SOCK_P"] / 2),
           sz(CONST["PCB_TOP"]), CONST["SOCK_N"] * CONST["SOCK_P"] * SS,
           CONST["SOCK_H"] * SS, lw=1)
    y0, y1 = pin_y - CART_W / 2, pin_y + CART_W / 2
    c.poly([(sx(y0), sz(SOCK_TOP)), (sx(y1), sz(SOCK_TOP)),
            (sx(y1), sz(CARD_TOP - ch)), (sx(y1 - ch), sz(CARD_TOP)),
            (sx(y0 + ch), sz(CARD_TOP)), (sx(y0), sz(CARD_TOP - ch))])
    # circular sensing cell on the inward face, centred at NO_Z
    c.circle(sx(pin_y), sz(CONST["NO_Z"]),
             min(CART_W, CONST["NO_Z"] - SOCK_TOP) * SS * 0.30, lw=1)
    c.circle(sx(pin_y), sz(CONST["NO_Z"]),
             min(CART_W, CONST["NO_Z"] - SOCK_TOP) * SS * 0.15,
             lw=1, color=GREY)
    c.rect(sx(pin_y + CART_W * 0.25), sz(SOCK_TOP + CART_H * 0.86),
           CONST["SOCK_P"] * 1.4 * SS, CONST["SOCK_P"] * SS, lw=1, color=GREY)

c.rect(sx(0), sz(CONST["LID_Z1"]), sw * SS, CONST["LID_T"] * SS)
for sy in (inset, sw - inset):
    c.line(sx(sy), sz(CONST["LID_Z1"] + 1), sx(sy), sz(CONST["LID_Z0"] - 1), lw=1)
    c.line(sx(sy - CONST["SCREW_D"] * 0.8), sz(CONST["LID_Z1"] + 1),
           sx(sy + CONST["SCREW_D"] * 0.8), sz(CONST["LID_Z1"] + 1), lw=2)

# The front-wall aperture is a through-cut in the fixed wall, not in the lid.
c.rect(sx(0), sz(WIN_Z1), CONST["WALL"] * SS,
       (WIN_Z1 - WIN_Z0) * SS, lw=1)
c.text(sx(CONST["WALL"] * 1.4), sz(WIN_Z1) + 4,
       "front-wall OLED aperture %.0f x %.0f" %
       (CONST["DISP_WIN_W"], CONST["DISP_WIN_H"]), 10, color=GREY)

c.rect(sx(sw), sz(CONST["FAN_Z"] + CONST["FAN_R"]), CONST["FAN_T"] * SS,
       2 * CONST["FAN_R"] * SS, dash=True, lw=1, color=GREY)

for z0 in (CONST["NO_Z"] - CONST["NO_R"] * 0.5,
           CONST["NO_Z"] + CONST["NO_R"] * 0.5):
    c.arrow(sx(-CONST["WALL"] * 2), sz(z0), sx(CONST["WALL"] * 2), sz(z0),
            lw=1, color=GREY, head=7)
c.arrow(sx(CONST["FILT_Y1"] + CONST["FILT_T"]), sz(CONST["NO_Z"] + CART_W * 0.2),
        sx(sw - CONST["WALL"] * 3), sz(CONST["NO_Z"] + CART_W * 0.2), lw=2, head=11)
c.arrow(sx(sw - CONST["WALL"] * 3), sz(CONST["NO_Z"]),
        sx(sw + CONST["FAN_T"] * 0.6), sz(CONST["FAN_Z"] + CONST["NO_R"] * 2),
        lw=2, head=11)

c.line(sx(sw * 0.61), sz(CARD_TOP), sx(sw * 0.69), sz(CARD_TOP), lw=1, color=GREY)
c.line(sx(sw * 0.61), sz(CONST["LID_Z0"]), sx(sw * 0.69), sz(CONST["LID_Z0"]),
       lw=1, color=GREY)
c.line(sx(sw * 0.65), sz(CARD_TOP), sx(sw * 0.65), sz(CONST["LID_Z0"]),
       lw=1, color=GREY)
c.text(sx(sw * 0.70), sz((CARD_TOP + CONST["LID_Z0"]) / 2),
       "%.1f hood" % HOOD, 11, color=GREY)


def slabel(y, z, text, dx=0, dy=0):
    c.text(sx(y) + dx, sz(z) + dy, text, 12, anchor="ma")


slabel(CONST["WALL"] / 2, CONST["NO_Z"] + CONST["NO_R"] * 2.5, "3 x dia6 inlet")
slabel(CONST["FILT_Y0"], CONST["LID_Z0"] + CONST["FILT_T"] * 1.5, "PTFE mesh")
slabel(CONST["ROW_Y"][1], CARD_TOP + CONST["NO_R"] * 2.5, "upright OSM-1 cards")
slabel(sw * 0.55, CONST["PCB_TOP"] - CONST["PCB_T"] * 2, "PCB = chamber floor")
slabel(sw * 0.5, CONST["LID_Z1"] + CONST["FAN_T"] * 0.4,
       "plain flat lid, 4 x M3")
c.text(sx(sw + CONST["FAN_T"]) + 6, sz(CONST["FAN_Z"]), "%g mm" % (2 * CONST["FAN_R"]),
       12, anchor="la")
c.text(sx(sw + CONST["FAN_T"]) + 6, sz(CONST["FAN_Z"]) + 16, "PWM fan, J10 at rear centre",
       12, anchor="la")

# ---- FRONT WALL UI / ELEVATION -------------------------------------------
c.text(lx(sh / 2), 606, "FRONT WALL UI - ELEVATION", 17, True, anchor="ma")
c.rect(lx(0), lz(60), sh * LS, 60 * LS)
for nx in NO_X:
    c.circle(lx(nx), lz(CONST["NO_Z"]), CONST["NO_R"] * LS)
c.text(lx(NO_X[0]), lz(CONST["NO_Z"]) + 18, "3 x dia6 nostrils, clear below panel",
       10, color=GREY)
c.rect(lx(DISP_X0), lz(DISP_Z1), CONST["DISP_W"] * LS,
       CONST["DISP_H"] * LS, lw=1, color=GREY)
c.rect(lx(WIN_X0), lz(WIN_Z1), CONST["DISP_WIN_W"] * LS,
       CONST["DISP_WIN_H"] * LS)
c.text(lx(CONST["DISP_X"]), lz(CONST["DISP_Z"]) + 4, "OLED 0x3C", 11,
       anchor="ma")

gx, gz = CONST["UI_FEED_X"], CONST["UI_FEED_Z"]
c.circle(lx(gx), lz(gz), CONST["UI_FEED_D"] / 2 * LS, lw=1, color=GREY)
c.text(lx(gx), lz(gz) - 15, "dia6", 9, anchor="ma", color=GREY)

for name, (bx, bz) in BTN_FRONT.items():
    c.circle(lx(bx), lz(bz), CONST["BTN_HOLE_D"] * LS, lw=1, color=GREY)
    c.circle(lx(bx), lz(bz), CONST["BTN_HOLE_D"] / 2 * LS)
    label = {"MEASURE": "MEAS", "MENU": "MENU"}.get(name, name)
    c.text(lx(bx), lz(bz) + 15, label, 9, anchor="ma", color=GREY)

# layer order from the wall outward: gasket, acrylic, bezel; OLED is inside.
sx_stack = 486
c.text(sx_stack, 628, "STACK", 13, True)
for i, (name, depth) in enumerate((
        ("gasket", CONST["DISP_GASKET"]),
        ("acrylic", CONST["DISP_GASKET"]),
        ("bezel", CONST["DISP_POD_D"]))):
    yy = 650 + i * 28
    c.rect(sx_stack, yy, max(6, depth * 8), 16, lw=1, color=GREY)
    c.text(sx_stack + max(6, depth * 8) + 5, yy + 12,
           "%s %.1f" % (name, depth), 10, color=GREY)
c.text(sx_stack, 746, "OLED 0x3C (dry side)", 10, color=GREY)
c.text(sx_stack, 764, "plain lid, 4 x M3", 10, color=GREY)

# ---- numbered legend ------------------------------------------------------
c.line(566, 470, 1360, 470, w=1, color=GREY)
c.text(566, 496, "KEY", 15, True)
legend = [
    ("1", "Three dia6 nostrils, front wall - sample entry"),
    ("2", "Cleanable woven PTFE mesh filter, front drawer"),
    ("3", "Eight identical keyed 1x6 OSM-1 sockets"),
    ("4", "Qwiic port beside every socket (own mux channel)"),
    ("5", "Upright parametric cartridges facing the central channel"),
    ("6", "SHT31 temperature / humidity reference, 1 Hz"),
    ("7", "ESP32 + two ADS1115s; board top is the chamber floor"),
    ("8", "40 mm PWM exhaust fan, J10 harness at rear centre"),
    ("9", "Front-wall OLED 0x3C, sealed gasket/acrylic/bezel stack"),
    ("10", "dia6 grommet; four front buttons MEASURE/OK, MENU/BACK, BOOT, "
           "RESET; plain lid"),
]
for i, (n, txt) in enumerate(legend):
    yy = 524 + i * 31
    c.text(578, yy, n, 13, True, color=GREY)
    c.text(604, yy, txt, 14)
c.text(566, 830, "MEASURE/OK + MENU/BACK are user buttons; BOOT/RESET are "
       "service buttons; OTA updates", 12, color=GREY)
c.text(566, 852, VISUAL_NOTE, 12, color=GREY)

svg_path = os.path.join(OUT, "manual_linework.svg")
png_path = os.path.join(OUT, "manual_linework.png")
with open(svg_path, "w", encoding="utf-8") as f:
    f.write(c.svg())
c.png(png_path)
print("wrote", os.path.relpath(svg_path, ROOT))
print("wrote", os.path.relpath(png_path, ROOT))
