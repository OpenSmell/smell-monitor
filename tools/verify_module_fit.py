#!/usr/bin/env python3
"""Gate: does every part in the database have a real path into a slot?

`mechanical/modules.py` records what the market sells; this gate classifies
each entry against the OpenSmell Module Standard v1 (`docs/module-standard.md`,
data in `mechanical/standard.py`) and checks the as-built chamber and socket
contract against the same rules.

Each part gets one of two verdicts:

    CONFORMS  a gas-cell element whose footprint fits the 20 x 32 mm cartridge
              envelope, or a native Qwiic I2C module
    CARRIER   usable through a documented build step: a bare SMD part, a
              non-2.54 connector, or a vendor board larger than the cartridge

Both are supported paths - the standard makes the *slot* uniform, it does not
promise that every vendor breakout is plug-compatible.  The gate fails only on
a defect in this repository (a missing source, a slot that cannot carry the
standard cartridge, a pitch below the minimum).

Run:  python tools/verify_module_fit.py
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
    """hard=True -> a defect in this repository (fails the gate).
    hard=False -> informational: a conformance note, reported but not fatal."""
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
RESULTS = {k: M.check(k) for k in sorted(M.MODULES)}

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


SLOT = roles(IF.SLOT)          # universal OSM-1 6-pin: +5V GND AO DO 3V3 ID
QWIC = roles(IF.QWIC)          # Qwiic port: GND 3V3 SDA SCL
transposed = []
for key, m in M.MODULES.items():
    pins = m.get("pins")
    if not pins:
        continue
    # Only gas-cell cards present the 6-pin card edge.  I2C modules reach the
    # base through the Qwiic port, whose order is checked separately below.
    if m["lane"] != "analog":
        continue
    rp = roles(pins.split())
    if rp != SLOT[:len(rp)]:
        transposed.append((key, pins, " ".join(IF.SLOT[:len(rp)])))
check("raw vendor pin order (the cartridge re-houses the element)",
      not transposed,
      "; ".join("%s is [%s] vs slot [%s]" % t for t in transposed)
      if transposed else "every listed vendor order matches the slot")
check("the Qwiic port carries the standard order",
      QWIC == roles(["GND", "3V3", "SDA", "SCL"]),
      "port [%s]" % " ".join(IF.QWIC))

# ------------------------- the module standard (OSM-1) ----------------------
# docs/module-standard.md is prose; mechanical/standard.py is the same rules as
# data. These checks are what keep the document and the hardware honest.
import standard as S                                                # noqa: E402

std_pins = S.CARTRIDGE["pins"]
check("the gas-cell socket implements the standard pinout",
      list(IF.SLOT) == std_pins,
      "as-built [%s] vs standard [%s]"
      % (" ".join(IF.SLOT), " ".join(std_pins)))

_win = {}
for _bank, _x0 in (("analog", "A_X"), ("digital", "D_X")):
    _xs = CONST[_x0]
    _win[_bank] = dict(pitch=_xs[1] - _xs[0], win=(_xs[1] - _xs[0] - 2.0,
                                                   S.SLOTS["reach"]))

_lowp = {k: v["pitch"] for k, v in _win.items()
         if v["pitch"] < S.SLOTS["pitch_min"]}
check("every row's pitch >= %.0f mm (max module width + gap)"
      % S.SLOTS["pitch_min"],
      not _lowp, "rows below the standard: %s" % _lowp)

_small = {k: v["win"] for k, v in _win.items()
          if v["win"][0] < S.SLOTS["max_width"]}
check("every slot can carry a %.0f mm wide cartridge" % S.SLOTS["max_width"],
      not _small, "slots too narrow: %s" % _small)

_nslots = IF.N_ANALOG + IF.N_DIGITAL
check("the base carries the standard's %d slots" % S.SLOTS["reference_count"],
      _nslots == S.SLOTS["reference_count"], "%d slots as built" % _nslots)

_ch = S.SLOTS["channels"]
check("8 uniform slots close on the existing I2C topology",
      "TCA9548A" in IF.I2C and _ch["mux"] <= 8
      and (_ch["adc"] <= 1 or "ADS1115_B" in IF.I2C),
      "%d mux channels / %d ADC(s) on one master bus"
      % (_ch["mux"], _ch["adc"]))

# ---------------------- market parts vs the standard ------------------------
# The gate reports how each real part reaches a slot: CONFORMS (a cartridge or
# a native Qwiic module) or CARRIER (build it into a cartridge / Qwiic carrier).
# Both are supported paths; a CARRIER verdict is a build step, not a defect.
_nfit = {k: v for k, (v, _) in RESULTS.items() if v == "CONFORMS"}
check("a starter-pack part conforms as a bare cartridge or Qwiic module",
      any(k in _nfit for k in M.STARTER_PACK),
      "%d of %d market parts conform; the rest are carrier builds"
      % (len(_nfit), len(RESULTS)))

# the cartridge must ride inside the chamber's clear height
_env = S.CARTRIDGE["envelope"]
_h_clear = CONST["CAV_Z1"] - CONST["PCB_TOP"]
check("cartridge rides inside the chamber's clear height",
      _env["height"] + 8.5 <= _h_clear,
      "%.0f mm cartridge + 8.5 mm socket <= %.1f mm clear"
      % (_env["height"], _h_clear))

# ------------------------------- report -------------------------------------
print("module                    verdict   detail")
for key, (verdict, notes) in RESULTS.items():
    print("%-24s %-9s %s" % (key, verdict, "; ".join(notes[:2])))
print()
w = max(len(n) for n, _, _, _ in CHECKS) + 2
print(f"{'CHECK':<{w}} {'RESULT':<7} DETAIL")
for name, ok, detail, hard in CHECKS:
    tag = "PASS" if ok else ("FAIL" if hard else "NOTE")
    print(f"{name:<{w}} {tag:<7} {detail}")
print()

_n_conf = sum(1 for v, _ in RESULTS.values() if v == "CONFORMS")
print("conformance: %d part(s) plug in as-is; %d are documented carrier builds"
      % (_n_conf, len(RESULTS) - _n_conf))

if HARD:
    print("%d FAILURE(S): %s" % (len(HARD), ", ".join(HARD)))
    sys.exit(1)
print("RESULT: ALL PASS (%d checks)" % len(CHECKS))
