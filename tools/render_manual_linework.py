#!/usr/bin/env python3
"""Black-and-white line drawing of the v1.1 flow path for the user manual.

Two orthographic views generated from mechanical/constants.py, so the picture
cannot drift from the CAD:

  * PLAN, lid removed - nostrils, filter drawer, both socket rows, fan, USB-C
  * SECTION A-A along the flow - board-as-floor, side-wall sockets, upright
    inward-facing cartridges, 4.9 mm flow hood, lid and the rear fan

Output: docs/figures/cad/manual_linework.svg (vector) and .png (printable).
No third-party renderer: primitives are emitted straight to SVG and to Pillow.
"""
import html
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST  # noqa: E402

OUT = os.path.join(ROOT, "docs", "figures", "cad")
os.makedirs(OUT, exist_ok=True)

W, H = 1440, 1000
INK = "#101010"
GREY = "#707070"
LW = 2

# View transforms (mm -> px).  Plan looks down; section looks along +X.
PX0, PY0, PS = 78.0, 132.0, 3.55
SX0, SZ0, SS = 566.0, 404.0, 4.35


def px(x):
    return PX0 + x * PS


def py(y):
    return PY0 + y * PS


def sx(y):
    return SX0 + y * SS


def sz(z):
    return SZ0 - z * SS


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

    def hatch(self, x, y, w, h, step=7, color=INK):
        self.items.append(("hatch", (x, y, w, h, step), False, 1, color))

    # -- SVG ---------------------------------------------------------------
    def svg(self):
        out = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d">' % (W, H, W, H),
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
                x1, y1, x2, y2, head = p
                out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" '
                           'stroke="%s" stroke-width="%g"/>'
                           % (x1, y1, x2, y2, color, lw or 2))
                import math
                a = math.atan2(y2 - y1, x2 - x1)
                for sgn in (-1, 1):
                    b = a + sgn * 0.42
                    out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" '
                               'stroke="%s" stroke-width="%g"/>'
                               % (x2, y2, x2 - head * math.cos(b),
                                  y2 - head * math.sin(b), color, lw or 2))
            elif kind == "hatch":
                x, y, w, h, step = p
                for k in range(-int(h), int(w), step):
                    x1, y1 = max(x, x + k), y + max(0, -k)
                    x2, y2 = min(x + w, x + k + h), y + min(h, w - k)
                    if x2 > x1 and y2 >= y1:
                        out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" '
                                   'y2="%.2f" stroke="%s" stroke-width="1"/>'
                                   % (x1, y1, x2, y2, color))
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
            elif kind == "hatch":
                x, y, bw, bh, step = p
                for k in range(-int(bh), int(bw), step):
                    x1, y1 = max(x, x + k), y + max(0, -k)
                    x2, y2 = min(x + bw, x + k + bh), y + min(bh, bw - k)
                    if x2 > x1 and y2 >= y1:
                        d.line((x1, y1, x2, y2), fill=color, width=1)
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
        meta = PngInfo = None
        im.save(path, "PNG", dpi=(300, 300), optimize=True)


c = Canvas()

# ---- sheet furniture ------------------------------------------------------
c.line(60, 92, 1380, 92, w=2)
c.text(60, 42, "OPEN SMELL  /  SMELL MONITOR v1.1", 27, True)
c.text(60, 70, "FIG 1   PLAN AND LONGITUDINAL SECTION - SAMPLE FLOW PATH", 15)
c.text(1380, 70, "SHEET 1 / 1", 15, anchor="ra")
c.text(60, 966, "ALL DIMENSIONS IN MILLIMETRES - GEOMETRY GENERATED FROM mechanical/constants.py",
       13, color=GREY)
c.line(60, 884, 1380, 884, w=2)
c.line(60, 936, 1380, 936, w=1, color=GREY)
for x in (60, 520, 900, 1380):
    c.line(x, 884, x, 952, w=1, color=GREY)
c.text(74, 900, "DRAWING  OSM-FIG-001", 14, True)
c.text(74, 924, "PLAN + SECTION A-A", 12, color=GREY)
c.text(534, 900, "PRODUCT  Smell Monitor v1.1", 14)
c.text(534, 924, "INTERFACE  OSM-1", 12, color=GREY)
c.text(914, 900, "REV  B", 14)
c.text(914, 924, "UNITS  mm", 12, color=GREY)

# ---- PLAN VIEW ------------------------------------------------------------
c.text(px(61), 112, "PLAN - LID REMOVED", 17, True, anchor="ma")

sh, sw = CONST["SH"], CONST["SW"]
c.rect(px(0), py(0), sh * PS, sw * PS)                      # shell outside
c.rect(px(3), py(3), CONST["CX"] * PS, CONST["CY"] * PS,
       dash=True, lw=1, color=GREY)                          # cavity inside
c.rect(px(4), py(4.5), CONST["PCB_X"] * PS, CONST["PCB_Y"] * PS,
       lw=1, color=GREY)                                     # board outline

# four lid bosses
for bx, by in ((CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
               (sh - CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
               (CONST["BOSS_INSET"], sw - CONST["BOSS_INSET"]),
               (sh - CONST["BOSS_INSET"], sw - CONST["BOSS_INSET"])):
    c.circle(px(bx), py(by), CONST["BOSS_D"] / 2 * PS, lw=1)

# nostrils in the front wall
for nx in [sh / 2 + k * CONST["NO_PITCH"] for k in (-1, 0, 1)]:
    c.circle(px(nx), py(1.5), CONST["NO_R"] * PS)

# filter drawer
fx, fw = 6.0, 110.0
fy, fh = CONST["FILT_Y0"], CONST["FILT_T"]
c.rect(px(fx), py(fy), fw * PS, fh * PS)
c.hatch(px(fx), py(fy), fw * PS, fh * PS, 8, GREY)

# sockets: 1x6, pin line front-to-back (Y) on the two inner side walls;
# boards stand upright in the Y-Z plane and face inward across the channel
for wall_x, ys, prefix, first in ((CONST["DI_X"], CONST["DI_Y"], "D", 1),
                                  (CONST["AN_X"], CONST["AN_Y"], "A", 5)):
    for i, yc in enumerate(ys):
        c.rect(px(wall_x - 1.27), py(yc - 6.35), 2.54 * PS, 12.7 * PS)
        for p in range(6):
            c.circle(px(wall_x), py(yc - 6.35 + p * 2.54), 1.1, lw=1, color=GREY)
        c.text(px(wall_x), py(yc - 10.0), "%s%d" % (prefix, i), 11, anchor="ma")

# SHT31 between the rows
c.rect(px(58), py(54), 6 * PS, 6 * PS, lw=1)
c.text(px(61), py(61), "SHT31", 10, anchor="ma", color=GREY)

# fan and USB-C on the rear wall (hidden behind it)
c.circle(px(CONST["FAN_X"]), py(sw), CONST["FAN_R"] * PS,
         dash=True, lw=1, color=GREY)
c.circle(px(CONST["USB_X"]), py(sw), CONST["USB_R"] * PS,
         dash=True, lw=1, color=GREY)

# flow arrows in the gaps between cartridges
for ax in (39.0, 61.0, 85.0):
    c.arrow(px(ax), py(17), px(ax), py(108), lw=1, color=GREY, head=6)

# leaders + labels
def leader(x1, y1, x2, y2, label, anchor="la"):
    c.line(x1, y1, x2, y2, lw=1, color=GREY)
    c.circle(x1, y1, 2, lw=1, color=GREY)
    c.text(x2 + (5 if anchor == "la" else -5), y2 - 3, label, 12, anchor=anchor)


leader(px(35), py(1.5), px(8), py(-13), "3 x dia6 nostrils")
leader(px(fx + 10), py(fy + 2), px(8), py(-6), "woven PTFE mesh filter")
leader(px(CONST["AN_X"]), py(CONST["AN_Y"][2]), px(-8), py(44),
       "left wall 5-8 (upright)", "ra")
leader(px(CONST["DI_X"]), py(CONST["DI_Y"][2]), px(127), py(86),
       "right wall 1-4 (upright)", "la")
leader(px(CONST["FAN_X"] + 14), py(sw - 6), px(127), py(62), "40 mm fan (rear)")
leader(px(CONST["USB_X"]), py(sw), px(127), py(96), "USB-C")

# overall dimensions
c.line(px(0), py(-9), px(sh), py(-9), lw=1, color=GREY)
c.line(px(0), py(-7), px(0), py(-11), lw=1, color=GREY)
c.line(px(sh), py(-7), px(sh), py(-11), lw=1, color=GREY)
c.text(px(sh / 2), py(-11), "122", 12, anchor="ma", color=GREY)
c.line(px(-9), py(0), px(-9), py(sw), lw=1, color=GREY)
c.line(px(-11), py(0), px(-7), py(0), lw=1, color=GREY)
c.line(px(-11), py(sw), px(-7), py(sw), lw=1, color=GREY)
c.text(px(-12), py(sw / 2), "114", 12, anchor="ma", color=GREY)

# ---- SECTION A-A ----------------------------------------------------------
c.text((sx(0) + sx(114)) / 2, 128, "SECTION A-A - ALONG THE FLOW", 17, True,
       anchor="ma")

c.rect(sx(0), sz(CONST["FLOOR_T"]),
       (sw) * SS, CONST["FLOOR_T"] * SS)                      # tray floor
c.rect(sx(0), sz(CONST["LID_Z0"]), CONST["WALL"] * SS,
       (CONST["LID_Z0"] - CONST["FLOOR_T"]) * SS)              # front wall
c.rect(sx(sw - CONST["WALL"]), sz(CONST["LID_Z0"]),
       CONST["WALL"] * SS,
       (CONST["LID_Z0"] - CONST["FLOOR_T"]) * SS)              # rear wall

# board on standoffs - its top face is the chamber floor
c.rect(sx(4.5), sz(CONST["PCB_TOP"]), 105 * SS, CONST["PCB_T"] * SS)
for sy in (14.0, 99.0):
    c.rect(sx(sy), sz(CONST["PCB_Z"]), 3.2 * SS,
           (CONST["PCB_Z"] - CONST["FLOOR_T"]) * SS, lw=1)

# nostril openings through the front wall
for zc in (CONST["NO_Z"] - CONST["NO_R"], CONST["NO_Z"] + CONST["NO_R"]):
    c.line(sx(0), sz(zc), sx(CONST["WALL"]), sz(zc), lw=1)

# filter drawer: thin mesh panel in its 4 mm slot
c.rect(sx(CONST["FILT_Y0"]), sz(CONST["LID_Z0"]),
       CONST["FILT_T"] * SS,
       (CONST["LID_Z0"] - CONST["FILT_Z0"]) * SS)
c.hatch(sx(CONST["FILT_Y0"]), sz(CONST["LID_Z0"]),
        CONST["FILT_T"] * SS,
        (CONST["LID_Z0"] - CONST["FILT_Z0"]) * SS, 8, GREY)

# upright breakout boards on the two side-wall rows (both project onto the
# same Y stations in this side view): 8.5 mm socket + 32 mm tall card
sock_top = CONST["PCB_TOP"] + CONST["SOCK_H"]
cart_top = sock_top + CONST["CARD_H"]
for pin_y in CONST["ROW_Y"]:
    c.rect(sx(pin_y - 1.27), sz(CONST["PCB_TOP"]), 2.54 * SS,
           CONST["SOCK_H"] * SS, lw=1)
    c.rect(sx(pin_y - 10), sz(sock_top), 20 * SS, CONST["CARD_H"] * SS)
    c.hatch(sx(pin_y - 6), sz(cart_top - 3), 12 * SS, 2.2 * SS, 5, GREY)

# lid with screw heads
c.rect(sx(0), sz(CONST["LID_Z1"]), sw * SS, CONST["LID_T"] * SS)
for sy in (CONST["BOSS_INSET"], sw - CONST["BOSS_INSET"]):
    c.line(sx(sy), sz(CONST["LID_Z1"] + 1), sx(sy), sz(CONST["LID_Z0"] - 1), lw=1)
    c.line(sx(sy - 2.5), sz(CONST["LID_Z1"] + 1),
           sx(sy + 2.5), sz(CONST["LID_Z1"] + 1), lw=2)

# fan housing behind the rear wall
c.rect(sx(sw), sz(CONST["FAN_Z"] + CONST["FAN_R"]),
       CONST["FAN_T"] * SS, 2 * CONST["FAN_R"] * SS, dash=True, lw=1,
       color=GREY)

# flow path: inlets -> filter -> hood over both rows -> fan
for z0 in (CONST["NO_Z"] - 1.5, CONST["NO_Z"] + 1.5):
    c.arrow(sx(-7), sz(z0), sx(8), sz(z0), lw=1, color=GREY, head=7)
c.arrow(sx(17), sz(40.5), sx(108), sz(40.5), lw=2, head=11)
c.arrow(sx(108), sz(40), sx(116), sz(CONST["FAN_Z"] + 8), lw=2, head=11)

# hood dimension
c.line(sx(70), sz(cart_top), sx(78), sz(cart_top), lw=1, color=GREY)
c.line(sx(70), sz(CONST["LID_Z0"]), sx(78), sz(CONST["LID_Z0"]),
       lw=1, color=GREY)
c.line(sx(74), sz(cart_top), sx(74), sz(CONST["LID_Z0"]),
       lw=1, color=GREY)
c.text(sx(79), sz((cart_top + CONST["LID_Z0"]) / 2), "4.9 hood", 11,
       color=GREY)

# section labels
def slabel(y, z, text, dx=0, dy=0):
    c.text(sx(y) + dx, sz(z) + dy, text, 12, anchor="ma")


slabel(1.5, CONST["NO_Z"] + 7, "3 x dia6 inlet")
slabel(12.8, CONST["LID_Z0"] + 5, "PTFE mesh")
slabel(49, cart_top + 7, "left-wall cards")
slabel(91, cart_top + 7, "right-wall cards")
slabel(61, 5.5, "PCB = chamber floor")
slabel(61, CONST["LID_Z1"] + 4, "lid, 4 x M3 screws")
c.text(sx(sw + CONST["FAN_T"]) + 6, sz(CONST["FAN_Z"]),
       "40 mm", 12, anchor="la")
c.text(sx(sw + CONST["FAN_T"]) + 6, sz(CONST["FAN_Z"]) + 16,
       "PWM fan", 12, anchor="la")

# ---- numbered legend ------------------------------------------------------
c.line(566, 470, 1360, 470, w=1, color=GREY)
c.text(566, 496, "KEY", 15, True)
legend = [
    ("1", "Three dia6 nostrils, front wall - sample entry"),
    ("2", "Cleanable woven PTFE mesh filter, front drawer"),
    ("3", "Eight identical keyed 1x6 OSM-1 gas-cell sockets"),
    ("4", "Qwiic port beside every socket (own mux channel)"),
    ("5", "Upright cartridges facing inward across the central channel"),
    ("6", "SHT31 temperature / humidity reference, 1 Hz"),
    ("7", "ESP32 + two ADS1115s; board top is the chamber floor"),
    ("8", "40 mm PWM exhaust fan, outside the chamber"),
    ("9", "Lid on four M3 screws - the only service operation"),
    ("10", "USB-C power and data; no battery in the gas path"),
]
for i, (n, txt) in enumerate(legend):
    yy = 524 + i * 31
    c.text(578, yy, n, 13, True, color=GREY)
    c.text(604, yy, txt, 14)

svg_path = os.path.join(OUT, "manual_linework.svg")
png_path = os.path.join(OUT, "manual_linework.png")
with open(svg_path, "w", encoding="utf-8") as f:
    f.write(c.svg())
c.png(png_path)
print("wrote", os.path.relpath(svg_path, ROOT))
print("wrote", os.path.relpath(png_path, ROOT))
