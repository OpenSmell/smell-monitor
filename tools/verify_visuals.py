#!/usr/bin/env python3
"""Numeric gate for the coded assembly visuals.

The images are illustration, not fabrication geometry, but they must still be
traceable: the PCB features have to come from the routed board, the cart/hood
numbers from mechanical/constants.py, and the output has to be a real animation
rather than a single static frame.

Run:  python tools/verify_visuals.py       (exit 0 = all PASS)
"""
import csv
import json
import os
import sys

from PIL import Image, ImageStat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST  # noqa: E402

OUT = os.path.join(ROOT, "docs", "figures", "cad")
FAILS, CHECKS = [], []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    if not ok:
        FAILS.append(name)


# --- the render bridge must describe the committed board -------------------
geo = json.load(open(os.path.join(OUT, "pcb_geometry.json"), encoding="utf-8"))
bom = list(csv.DictReader(open(os.path.join(ROOT, "electrical", "bom.csv"),
                               encoding="utf-8-sig")))
expected_fp = sum(int(r["Quantity"]) for r in bom)
check("rendered board has one footprint per BOM part",
      geo["counts"]["footprints"] == expected_fp,
      f"{geo['counts']['footprints']} vs {expected_fp}")
check("rendered board carries real routed copper",
      geo["counts"]["tracks"] > 1200 and geo["counts"]["nets"] >= 70,
      f"{geo['counts']['tracks']} tracks / {geo['counts']['nets']} nets")
check("rendered board carries the eight sockets",
      sum(1 for f in geo["footprints"]
          if f["ref"] in {"J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9"}) == 8,
      "J2..J9")

# --- image assets ----------------------------------------------------------
needs = {
    "assembly_animation.gif": (1200, 700, 60),
    "assembly_storyboard.png": (1200, 600, 1),
    "header_proof.png": (1200, 700, 1),
    "assembly_assembled_iso.png": (1200, 700, 1),
    "assembly_flow_top.png": (1200, 700, 1),
    "manual_linework.png": (1200, 800, 1),
}
for name, (mw, mh, mf) in needs.items():
    path = os.path.join(OUT, name)
    if not os.path.isfile(path):
        check(f"{name} exists", False, "missing")
        continue
    im = Image.open(path)
    ok = im.width >= mw and im.height >= mh and getattr(im, "n_frames", 1) >= mf
    check(f"{name} is a real render", ok,
          f"{im.width}x{im.height}, {getattr(im, 'n_frames', 1)} frames")
    if name != "assembly_animation.gif":
        stat = ImageStat.Stat(im.convert("L"))
        check(f"{name} is not blank", stat.stddev[0] > 18,
              f"luma stddev {stat.stddev[0]:.1f}")

# header proof metadata is the numeric contract visible in the picture
meta = Image.open(os.path.join(OUT, "header_proof.png")).info
hood = CONST["HOOD"]
check("header proof hood matches the geometry",
      abs(float(meta.get("OSM_HOOD_MM", -1)) - hood) < 0.01,
      f"{meta.get('OSM_HOOD_MM')} vs {hood:.2f} mm")
# the manual line drawing must be monochrome and carry the locked numbers
lw_png = os.path.join(OUT, "manual_linework.png")
lw_svg = os.path.join(OUT, "manual_linework.svg")
check("manual linework vector source exists", os.path.isfile(lw_svg),
      "manual_linework.svg")
_lw = Image.open(lw_png).convert("RGB")
_lw_px = list(_lw.getdata())
check("manual linework is black on white",
      all(r == g == b for r, g, b in _lw_px)
      and 0.01 < sum(1 for r, _, _ in _lw_px if r < 128) / len(_lw_px) < 0.20,
      "greyscale, printable line art")
check("manual linework references the flow hood and nostril count",
      all(s in open(lw_svg, encoding="utf-8").read()
          for s in ("4.9 hood", "3 x dia6", "SECTION A-A")),
      "4.9 mm hood, 3 nostrils, section view")

check("header proof cartridge envelope matches the standard",
      all(abs(float(meta.get(k, -1)) - v) < 0.01 for k, v in (
          ("OSM_CART_W_MM", 20.0), ("OSM_CART_L_MM", 32.0),
          ("OSM_CART_H_MM", 21.0))),
      "20 x 32 x 21 mm")

w = max(len(n) for n, _, _ in CHECKS) + 2
print(f"{'CHECK':<{w}} {'RESULT':<7} DETAIL")
for name, ok, detail in CHECKS:
    print(f"{name:<{w}} {'PASS' if ok else 'FAIL':<7} {detail}")
print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    sys.exit(1)
print("ALL PASS - visuals trace to the routed board and locked constants")
