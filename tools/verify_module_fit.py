#!/usr/bin/env python3
"""Gate: do real plug-in modules actually fit the chamber?

`mechanical/modules.py` records what the market sells; this gate checks each
entry against the geometry in `mechanical/constants.py` and against the slot
contract in `electrical/interface.py`.

Run:
    python tools/verify_module_fit.py            # report (exit 0)
    python tools/verify_module_fit.py --strict   # exit 1 while any promised
                                                 # module is not a clean FITS

It is deliberately non-strict by default: three of the facts that decide the
answer (which card edge carries an MQ breakout's connector, where a flat NDIR
module puts its gas port, and the real envelope of the carriers) can only be
settled with calipers on a sample. Those show up as MEASURE, and blueprint 14
lists them as the top open mechanical item. `--strict` is what CI should run
once they are measured.

It also checks the as-built chamber and socket contract against the OpenSmell
Module Standard v1 (`docs/module-standard.md`, data in `mechanical/standard.py`)
and prints every remaining gap as an OPEN item, so the standard and the hardware
cannot drift apart quietly.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
sys.path.insert(0, os.path.join(ROOT, "electrical"))

from constants import CONST            # noqa: E402
import modules as M                    # noqa: E402

CHECKS = []
FAILS = []
HARD = []


def check(name, ok, detail="", hard=False):
    """hard=True -> a defect in this repository (fails even non-strict).
    hard=False -> an open product question, reported but not fatal."""
    CHECKS.append((name, bool(ok), detail, hard))
    if not ok:
        FAILS.append(name)
        if hard:
            HARD.append(name)


# ------------------------------- schema -------------------------------------
bad = [k for k, m in M.MODULES.items()
       if m["form"] not in ("card", "can", "flat", "smd")
       or (m["form"] == "card" and m["edge"] not in ("short", "long"))]
check("every module has a recognised form/pose", not bad, str(bad), hard=True)
check("every starter-pack module is in the database",
      all(k in M.MODULES for k in M.STARTER_PACK),
      str([k for k in M.STARTER_PACK if k not in M.MODULES]), hard=True)

# ------------------------------- fit ----------------------------------------
lim = M.limits(CONST)
RESULTS = {k: M.check(k, CONST) for k in sorted(M.MODULES)}

check("the database records a source for every module",
      all(m.get("src") for m in M.MODULES.values()),
      str([k for k, m in M.MODULES.items() if not m.get("src")]), hard=True)

# ------------------------- socket vs module pin order -----------------------
# A passive 2.54 mm receptacle has no idea what is plugged into it. Where a
# vendor publishes the module's own pin order, compare the two as *roles* and
# report a transposition: an analog output landing on the slot's DO pin is a
# 0-5 V signal on a 3.3 V ESP32 GPIO.
import interface as IF                                              # noqa: E402

ROLE = {"VCC": "PWR", "VDD": "PWR", "VIN": "PWR", "+5V": "PWR", "5V": "PWR",
        "3V3": "PWR", "VSS": "GND", "AO": "AO", "AOUT": "AO", "VOUT": "AO",
        "DO": "DO", "DOUT": "DO"}


def roles(pins):
    out = []
    for p in pins:
        out.append(ROLE.get(p, p))
    return out


SLOT = {"analog": roles(IF.SLOT_ANALOG), "digital": roles(IF.SLOT_DIGITAL)}
transposed = []
for key, m in M.MODULES.items():
    pins = m.get("pins")
    if not pins:
        continue
    if roles(pins.split()) != SLOT[m["lane"]][:len(pins.split())]:
        transposed.append((key, pins, " ".join(IF.SLOT_ANALOG
                                               if m["lane"] == "analog"
                                               else IF.SLOT_DIGITAL)))
check("published module pin orders match the socket order", not transposed,
      "; ".join("%s is [%s] vs slot [%s]" % t for t in transposed))

# ------------------------- the module standard (OSM-1) ----------------------
# docs/module-standard.md is prose; mechanical/standard.py is the same rules as
# data. These checks are what keep the document and the hardware honest.
import standard as S                                                # noqa: E402

std_pins = S.CARTRIDGE["pins"]
check("the gas-cell socket implements the standard pinout",
      list(IF.SLOT_ANALOG) == std_pins,
      "as-built [%s] vs standard [%s] - the ID pin is target revision L"
      % (" ".join(IF.SLOT_ANALOG), " ".join(std_pins)))

_win = {}
for _bank, _x0, _sx, _sy in (("analog", "A_X", "A_SX", "A_SY"),
                             ("digital", "D_X", "D_SX", "D_SY")):
    _xs = CONST[_x0]
    _win[_bank] = dict(pitch=_xs[1] - _xs[0], win=(CONST[_sx], CONST[_sy]))

_lowp = {k: v["pitch"] for k, v in _win.items() if v["pitch"] < S.SLOTS["pitch"]}
check("every row's pitch meets the %.0f mm standard" % S.SLOTS["pitch"],
      not _lowp, "rows below standard: %s (uniform pitch is revision L)" % _lowp)

_small = {k: v["win"] for k, v in _win.items()
          if min(v["win"]) < min(S.SLOTS["window"])}
check("every window meets the %gx%g mm standard" % S.SLOTS["window"],
      not _small, "windows below standard: %s" % _small)

_nslots = IF.N_ANALOG + IF.N_DIGITAL
check("the base carries the standard's %d slots" % S.SLOTS["reference_count"],
      _nslots == S.SLOTS["reference_count"], "%d slots as built" % _nslots)

_ch = S.SLOTS["channels"]
check("8 uniform slots close on the existing I2C topology",
      "TCA9548A" in IF.I2C and _ch["mux"] <= 8
      and (_ch["adc"] <= 1 or "ADS1115.2" in IF.I2C_EXPANSION),
      "%d mux channels / %d ADC(s) need only the planned second ADS1115"
      % (_ch["mux"], _ch["adc"]))

# every *gas-cell* card must also fit the cartridge envelope; a cabled I2C
# module has no envelope, which is the point of the port in 2.2
_env = S.CARTRIDGE["envelope"]
_badenv = []
for _k, _m in M.MODULES.items():
    if _m["lane"] != "analog" or _m["form"] != "card":
        continue
    _l, _w = _m["card"]
    _across, _along = min(_l, _w), max(_l, _w)
    if _across > _env["across"] or _along > _env["along"]:
        _badenv.append("%s is %g across / %g along" % (_k, _across, _along))
check("gas-cell cards fit the %gx%g mm cartridge envelope"
      % (_env["across"], _env["along"]), not _badenv, "; ".join(_badenv))

for key in M.STARTER_PACK:
    verdict, notes = RESULTS[key]
    ok = verdict == "FITS"
    check("starter pack %-18s -> %s" % (M.MODULES[key]["name"], verdict), ok,
          "" if ok else notes[0] + ("" if len(notes) == 1 else " (+%d more)"
                                    % (len(notes) - 1)))

# the envelope the chamber was sized from, as a sanity anchor
env = M.mounted(M.MODULES["MQ-135-openimpulse"], lim)
check("a 32x20 MQ breakout in the standing pose fits under the plate",
      env["height"] <= lim["h_clear"],
      "needs %.1f mm, %.1f mm available - measure the real module first"
      % (env["height"], lim["h_clear"]))

# ------------------------------- report -------------------------------------
print("module                    verdict   detail")
for key, (verdict, notes) in RESULTS.items():
    print("%-24s %-9s %s" % (key, verdict, "; ".join(notes[:2])))
print()
w = max(len(n) for n, _, _, _ in CHECKS) + 2
print(f"{'CHECK':<{w}} {'RESULT':<7} DETAIL")
for name, ok, detail, hard in CHECKS:
    tag = "PASS" if ok else ("FAIL" if hard else "OPEN")
    print(f"{name:<{w}} {tag:<7} {detail}")
print()

open_items = [k for k, (v, _) in RESULTS.items() if v in ("MEASURE", "CARRIER")]
if open_items:
    print("OPEN ITEMS (must be closed before the module envelope is frozen):")
    for k in open_items:
        print("  %-24s %s" % (k, RESULTS[k][0]))
    print()

if "--strict" in sys.argv:
    if FAILS:
        print("%d FAILED (strict)" % len(FAILS))
        sys.exit(1)
    print("ALL PASS - every database module fits the chamber")
    sys.exit(0)

if HARD:
    print("%d DATABASE FAILURE(S): %s" % (len(HARD), ", ".join(HARD)))
    sys.exit(1)
print("report complete - %d open item(s); run --strict once measured"
      % len(open_items))
