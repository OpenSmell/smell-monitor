#!/usr/bin/env python3
"""Numeric gate for the coded assembly visuals.

The images are illustration, not fabrication geometry, but they must still be
traceable: PCB features come from the routed board, the eight upright OSM-1
stations from CONST + the standard envelope, and the front-wall UI from the
locked local-interface constants.  Outputs have to be freshly regenerated
assets, with a real multi-frame animation.

Run:  python tools/verify_visuals.py       (exit 0 = all PASS)
"""
import csv
import json
import os
import re
import sys

from PIL import Image, ImageChops, ImageStat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST  # noqa: E402
from standard import CARTRIDGE, PORT  # noqa: E402

OUT = os.path.join(ROOT, "docs", "figures", "cad")
TOOLS = os.path.join(ROOT, "tools")
FAILS, CHECKS = [], []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    if not ok:
        FAILS.append(name)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def geometry_from_source():
    """The contract the outputs must carry, rebuilt independently from source."""
    pcb_path = os.path.join(OUT, "pcb_geometry.json")
    with open(pcb_path, encoding="utf-8") as f:
        pcb = json.load(f)
    j10 = next(fp for fp in pcb["footprints"] if fp["ref"] == "J10")
    fw = CONST["DISP_WIN_W"] / 2.0
    fh = CONST["DISP_WIN_H"] / 2.0
    pw = CONST["DISP_W"] / 2.0
    ph = CONST["DISP_H"] / 2.0
    return {
        "source": "mechanical/constants.py + routed pcb_geometry.json",
        "SOCK_X_L": CONST["SOCK_X_L"],
        "SOCK_X_R": CONST["SOCK_X_R"],
        "ROW_Y": list(CONST["ROW_Y"]),
        "SOCK_N": CONST["SOCK_N"],
        "SOCK_P": CONST["SOCK_P"],
        "SOCK_H": CONST["SOCK_H"],
        "PCB_TOP": CONST["PCB_TOP"],
        "SOCK_TOP": CONST["PCB_TOP"] + CONST["SOCK_H"],
        "CARD_W": CARTRIDGE["envelope"]["across"],
        "CARD_H": CONST["CARD_H"],
        "CARD_REACH": CONST["CARD_REACH"],
        "CARD_TOP": CONST["CARD_TOP"],
        "HOOD": CONST["HOOD"],
        "NO_X": [CONST["SH"] / 2.0 + k * CONST["NO_PITCH"] for k in (-1, 0, 1)],
        "NO_Z": CONST["NO_Z"],
        "NO_PITCH": CONST["NO_PITCH"],
        "NO_R": CONST["NO_R"],
        "FAN_X": CONST["FAN_X"],
        "FAN_Z": CONST["FAN_Z"],
        "FAN_R": CONST["FAN_R"],
        "FAN_HARNESS": {"ref": j10["ref"], "value": j10["value"],
                        "shell_x": j10["x"], "shell_y": j10["y"]},
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
        "BTN_FRONT": {k: list(v) for k, v in CONST["BTN_FRONT"].items()},
        "FRONT_PANEL_UI": {
            "wall": "fixed front wall",
            "panel_x": [CONST["DISP_X"] - pw, CONST["DISP_X"] + pw],
            "panel_z": [CONST["DISP_Z"] - ph, CONST["DISP_Z"] + ph],
            "aperture_x": [CONST["DISP_X"] - fw, CONST["DISP_X"] + fw],
            "aperture_z": [CONST["DISP_Z"] - fh, CONST["DISP_Z"] + fh],
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


EXPECTED_GEOM = geometry_from_source()

# Detection patterns only.  Escape the stale words so a plain-language scan of
# this gate does not itself report the claims it is built to reject.
STALE = [
    r"DISPLAY\s+\x50OD", r"OLED\s+\x50OD", r"sealed\s+\x50OD",
    r"DISP_\x50OD_H", r"BTN_\x50OS", r"DISP_Y", r"DISP_FEED_Y",
    r"lid\s+button", r"lid\s+UI", r"LID\s+/\s+UI",
    r"head" + "less", r"no[ -]OLED", r"pric(e|ing)",
    r"part" + "ner", r"strateg" + "ic", r"intern" + r"al\s+note",
    r"AI\s+note", r"vendor\s+CAD", r"two\s+user\s+buttons\s+total",
]


def stale_hits(text):
    return [p for p in STALE if re.search(p, text, re.I)]


def same(a, b):
    if isinstance(b, str):
        return isinstance(a, str) and a == b
    if isinstance(b, bool):
        return isinstance(a, bool) and a == b
    if isinstance(b, (int, float)):
        return (isinstance(a, (int, float)) and not isinstance(a, bool)
                and abs(a - b) < 0.001)
    if isinstance(b, list):
        return (isinstance(a, list) and len(a) == len(b)
                and all(same(x, y) for x, y in zip(a, b)))
    if isinstance(b, dict):
        return (isinstance(a, dict) and set(a) == set(b)
                and all(same(a[k], b[k]) for k in b))
    return a == b


def payload(info):
    """Pull the embedded OSM_GEOMETRY contract from PIL metadata."""
    raw = info.get("OSM_GEOMETRY")
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    try:
        return json.loads(raw)
    except ValueError:
        return None


def matches_source(meta):
    """Exact recursive comparison of every geometry key, including nested ones."""
    if not isinstance(meta, dict):
        return False, "missing OSM_GEOMETRY payload"
    bad = []
    for key, want in EXPECTED_GEOM.items():
        if not same(meta.get(key), want):
            bad.append("%s=%r != %r" % (key, meta.get(key), want))
    return not bad, "; ".join(bad[:4]) or ("%d keys" % len(EXPECTED_GEOM))


def svg_metadata(text):
    try:
        raw = re.search(r"<metadata>(.*?)</metadata>", text, re.S).group(1)
    except AttributeError:
        return None
    for a, b in (("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")):
        raw = raw.replace(a, b)
    try:
        return json.loads(raw)
    except ValueError:
        return None


# --- the render bridge must describe the committed board -------------------
geo_path = os.path.join(OUT, "pcb_geometry.json")
geo = json.load(open(geo_path, encoding="utf-8"))
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
j10 = next(f for f in geo["footprints"] if f["ref"] == "J10")
check("J10 fan harness is routed at the rear centre",
      abs(j10["x"] - CONST["FAN_X"]) < 2.0 and j10["y"] >= 90.0,
      "shell (%.1f, %.1f) mm" % (j10["x"], j10["y"]))

# --- generator sources: parametric OSM-1 parts, front-wall UI ---------------
asm_src = read(os.path.join(TOOLS, "render_assembly_visual.py"))
lw_src = read(os.path.join(TOOLS, "render_manual_linework.py"))
for name, src in (("assembly", asm_src), ("manual linework", lw_src)):
    check("%s generator has no block placeholders" % name,
          re.search(r"\bcube\b", src, re.I) is None
          and "draw_sensor_body" not in src,
          "no cube / generic sensor body")
    hits = stale_hits(src)
    check("%s generator has no stale display-enclosure language" % name,
          not hits, ", ".join(hits) or "clean")
    check("%s generator has no decorative hatch or fanout" % name,
          re.search(r"\bhatch\s*\(", src, re.I) is None
          and "fan-out" not in src.lower()
          and "cross-hatch" not in src.lower(),
          "clean parametric shapes")
    check("%s generator reads J10 from routed geometry" % name,
          "pcb_geometry.json" in src and '"J10"' in src and "FAN_HARNESS" in src,
          "no typed connector label")
    check("%s generator draws the fixed front-wall UI" % name,
          all(s in src for s in ("BTN_FRONT", "UI_FEED_X", "UI_FEED_Z",
                                 "DISP_POD_D", "front_panel_ui", "0x3C")),
          "aperture, grommet, four buttons, OLED")
    check("%s generator states the parametric representation" % name,
          "Licensed vendor STEP models are not in this repo" in src
          and "parametric OSM-1 representations" in src,
          "plain representation statement")

for sym in ("draw_keyed_socket", "draw_upright_card", "draw_gas_cell",
            "draw_fan_harness", "draw_front_panel_ui", "draw_nostril_callout",
            "geom_pnginfo"):
    check("assembly generator defines %s" % sym,
          re.search(r"def\s+%s\s*\(" % sym, asm_src) is not None,
          "parametric primitive")
for token in ("front_panel_ui", "front_wall_display", "ui_harness_grommet",
              "front_panel_buttons", "plain_lid", "rear_centre_fan_harness",
              "keyed_socket", "upright_card", "gas_cell", "qwiic_port"):
    check("visual metadata names %s" % token,
          token in asm_src and token in lw_src, "in both generators")
check("assembly keeps nostrils visible below the front UI",
      "3 x dia6 NOSTRILS (INLET, BELOW UI)" in asm_src
      and "3 x dia6 inlet nostrils remain clear below the panel" in asm_src
      and "draw_nostril_callout(d)" in asm_src,
      "iso callout + front elevation + panel gap")
check("assembly uses canonical wall/row constants",
      all(k in asm_src for k in ("SOCK_X_L", "SOCK_X_R", "ROW_Y", "NO_Z",
                                 "NO_PITCH", "FAN_Z", "CARD_TOP")),
      "CONST identities, not mirrored numbers")
check("manual linework keeps nostrils below the front UI",
      "3 x dia6 nostrils, clear below panel" in lw_src
      and "for nx in NO_X:" in lw_src,
      "front-wall elevation shows the inlet bores")
check("manual linework uses canonical wall/row constants",
      all(k in lw_src for k in ("SOCK_X_L", "SOCK_X_R", "ROW_Y", "NO_Z",
                                "CARD_TOP", "BTN_FRONT", "DISP_WIN_W")),
      "CONST identities, not mirrored numbers")
check("locked four-button map with two user controls",
      len(CONST["BTN_FRONT"]) == 4
      and set(CONST["BTN_FRONT"]) == {"MEASURE", "MENU", "BOOT", "RESET"}
      and EXPECTED_GEOM["UI"]["user_buttons"] == ["MEASURE/OK", "MENU/BACK"]
      and EXPECTED_GEOM["UI"]["service_buttons"] == ["BOOT", "RESET"],
      "MEASURE/MENU user, BOOT/RESET service")

# --- image assets ----------------------------------------------------------
needs = {
    "assembly_animation.gif": (1200, 700, 60),
    "assembly_storyboard.png": (1200, 600, 1),
    "header_proof.png": (1200, 700, 1),
    "assembly_assembled_iso.png": (1200, 700, 1),
    "assembly_flow_top.png": (1200, 700, 1),
    "assembly_exploded_iso.png": (1200, 700, 1),
    "manual_linework.png": (1200, 800, 1),
}
generator_stamp = max(os.path.getmtime(os.path.join(TOOLS, "render_assembly_visual.py")),
                      os.path.getmtime(os.path.join(TOOLS, "render_manual_linework.py")))
for name, (mw, mh, mf) in needs.items():
    path = os.path.join(OUT, name)
    if not os.path.isfile(path):
        check(f"{name} exists", False, "missing")
        continue
    with Image.open(path) as im:
        frames = getattr(im, "n_frames", 1)
        ok = im.width >= mw and im.height >= mh and frames >= mf
        check(f"{name} is a real render", ok,
              f"{im.width}x{im.height}, {frames} frames")
        if name != "assembly_animation.gif":
            stat = ImageStat.Stat(im.convert("L"))
            check(f"{name} is not blank", stat.stddev[0] > 18,
                  f"luma stddev {stat.stddev[0]:.1f}")
        fresh = os.path.getmtime(path) + 1.0 >= generator_stamp
        check(f"{name} was regenerated after the generators", fresh,
              "asset mtime follows generator mtime")
        info = dict(im.info)
        if name.endswith(".gif"):
            comment = info.get("comment")
            if isinstance(comment, bytes):
                comment = comment.decode("utf-8", "replace")
            info["OSM_GEOMETRY"] = comment
        ok, detail = matches_source(payload(info))
        check("%s geometry matches CONST + routed board" % name, ok, detail)
        blob = json.dumps({k: str(v) for k, v in info.items()}, sort_keys=True)
        hits = stale_hits(blob)
        check("%s metadata has no stale display-enclosure language" % name,
              not hits, ", ".join(hits) or "clean")

# a single static frame must not pass as the animation
gif_path = os.path.join(OUT, "assembly_animation.gif")
if os.path.isfile(gif_path):
    with Image.open(gif_path) as im:
        frames = getattr(im, "n_frames", 1)
        check("animation has many distinct frames", frames >= 60,
              f"{frames} frames")
        samples = []
        for idx in (0, frames // 2, frames - 1):
            im.seek(idx)
            samples.append(im.convert("RGB").copy())
        diffs = [sum(ImageStat.Stat(ImageChops.difference(samples[0], s)).mean) / 3
                 for s in samples[1:]]
        check("animation frames actually change", all(v > 1.0 for v in diffs),
              "mean pixel delta %.1f / %.1f" % tuple(diffs))

# --- header proof: the numeric contract visible in the picture -------------
meta = Image.open(os.path.join(OUT, "header_proof.png")).info
check("header proof hood matches the geometry",
      abs(float(meta.get("OSM_HOOD_MM", -1)) - CONST["HOOD"]) < 0.01,
      f"{meta.get('OSM_HOOD_MM')} vs {CONST['HOOD']:.2f} mm")
check("header proof card top matches the geometry",
      abs(float(meta.get("OSM_CARD_TOP_MM", -1)) - CONST["CARD_TOP"]) < 0.01,
      f"{meta.get('OSM_CARD_TOP_MM')} vs {CONST['CARD_TOP']:.2f} mm")
try:
    envelope = json.loads(meta["OSM_CART_ENVELOPE"])
except (KeyError, ValueError):
    envelope = None
check("header proof carries OSM_CART envelope keys",
      envelope is not None
      and all(same(envelope.get(k), v) for k, v in CARTRIDGE["envelope"].items()),
      json.dumps(envelope, sort_keys=True) if envelope else "missing")
hmeta = payload(meta) or {}
check("header proof names the clean OSM-1 shapes",
      set(("keyed_socket", "upright_card", "gas_cell", "qwiic_port",
           "nostrils", "central_channel", "rear_fan",
           "rear_centre_fan_harness", "front_panel_ui",
           "front_wall_display", "ui_harness_grommet",
           "front_panel_buttons", "plain_lid")) <= set(hmeta.get("SHAPES", [])),
      "no placeholder shapes")
check("header proof front UI is on the fixed front wall",
      same(hmeta.get("FRONT_PANEL_UI"), EXPECTED_GEOM["FRONT_PANEL_UI"]),
      "aperture %.1f..%.1f x %.1f..%.1f" %
      tuple(EXPECTED_GEOM["FRONT_PANEL_UI"]["aperture_x"]
            + EXPECTED_GEOM["FRONT_PANEL_UI"]["aperture_z"]))
check("header proof has plain lid and rear-centre J10",
      same(hmeta.get("LID"), EXPECTED_GEOM["LID"])
      and same(hmeta.get("FAN_HARNESS"), EXPECTED_GEOM["FAN_HARNESS"]),
      "4 x M3, no lid cables; J10 at (%.1f, %.1f)" %
      (j10["x"], j10["y"]))
check("header proof OLED and buttons match the locked UI",
      same(hmeta.get("UI"), EXPECTED_GEOM["UI"])
      and same(hmeta.get("BTN_FRONT"), EXPECTED_GEOM["BTN_FRONT"])
      and hmeta.get("UI", {}).get("oled") == "0x3C",
      "0x3C, 2 user + 2 service buttons, 4 front bores")
check("header proof states the parametric representation",
      hmeta.get("VISUAL_NOTE") == EXPECTED_GEOM["VISUAL_NOTE"]
      or meta.get("OSM_VISUAL_REP") == EXPECTED_GEOM["VISUAL_NOTE"],
      "plain parametric statement")

# --- manual line drawing: monochrome and carrying the same contract --------
lw_png = os.path.join(OUT, "manual_linework.png")
lw_svg = os.path.join(OUT, "manual_linework.svg")
check("manual linework vector source exists", os.path.isfile(lw_svg),
      "manual_linework.svg")
if os.path.isfile(lw_svg):
    check("manual linework SVG was regenerated",
          os.path.getmtime(lw_svg) + 1.0 >= generator_stamp,
          "asset mtime follows generator mtime")
if os.path.isfile(lw_png):
    check("manual linework PNG was regenerated",
          os.path.getmtime(lw_png) + 1.0 >= generator_stamp,
          "asset mtime follows generator mtime")
    im = Image.open(lw_png).convert("RGB")
    pixels = list(im.get_flattened_data())
    check("manual linework is black on white",
          all(r == g == b for r, g, b in pixels)
          and 0.01 < sum(1 for r, _, _ in pixels if r < 128) / len(pixels) < 0.20,
          "greyscale, printable line art")
svg_text = read(lw_svg)
check("manual linework references the hood and nostril count",
      all(s in svg_text for s in ("4.9 hood", "3 x dia6", "SECTION A-A")),
      "4.9 mm hood, 3 nostrils, section view")
check("manual linework front elevation shows nostrils below the UI",
      "3 x dia6 nostrils, clear below panel" in svg_text,
      "three inlet bores in the same elevation as OLED and buttons")
check("manual linework carries the front-wall UI and side-wall rows",
      all(s in svg_text for s in ("FRONT WALL UI", "OLED 0x3C", "MEASURE/OK",
                                  "MENU/BACK", "BOOT", "RESET", "OTA", "J10",
                                  "plain lid", "left wall S0-S3",
                                  "right wall S4-S7")),
      "front-wall display, four buttons, OTA, both wall rows")
check("manual linework states the parametric representation",
      EXPECTED_GEOM["VISUAL_NOTE"] in svg_text,
      "plain parametric statement")
hits = stale_hits(svg_text)
check("manual linework has no stale display-enclosure language", not hits,
      ", ".join(hits) or "clean")
svg_geom = svg_metadata(svg_text)
svg_ok, svg_detail = matches_source(svg_geom)
check("manual linework SVG geometry matches CONST + routed board",
      svg_ok, svg_detail)
check("manual linework names the clean OSM-1 shapes",
      set(("keyed_socket", "upright_card", "gas_cell", "qwiic_port",
           "front_panel_ui", "front_wall_display", "ui_harness_grommet",
           "front_panel_buttons", "plain_lid", "rear_centre_fan_harness"))
      <= set((svg_geom or {}).get("SHAPES", [])),
      "no placeholder shapes")

w = max(len(n) for n, _, _ in CHECKS) + 2
print(f"{'CHECK':<{w}} {'RESULT':<7} DETAIL")
for name, ok, detail in CHECKS:
    print(f"{name:<{w}} {'PASS' if ok else 'FAIL':<7} {detail}")
print()
if FAILS:
    print(f"{len(FAILS)} FAILED: " + ", ".join(FAILS))
    sys.exit(1)
print("ALL PASS - visuals trace to the routed board, front-wall UI and "
      "locked constants")
