#!/usr/bin/env python3
"""OpenSmell sensor selection: coarse axis coverage + recommended pack.

The physical sensor facts live in ``sensor_data.py`` (ranges, cross-response,
power, cost, citations). This module owns the *selection* logic only: the
coarse axis/persona model and an exact minimum set-cover that recommends a
pack. It answers a necessary-but-not-sufficient question -- "does some module
touch each required axis?" -- under the 4+4 bank capacities.

For the *sufficient* question -- "how much NEW information does each extra
channel add, and where is the diminishing-returns knee?" -- see
``orthogonality.py``, which works on the fine response profiles in
``sensor_data.py``. Coverage without orthogonality would call two near-
identical MOX channels "two axes"; those are different analyses on purpose.

Sensors are ordinary plug-in breakout modules. Bank topology (why a UART-only
5 V module can only live in an analog slot, why the digital bank is 3.3 V I2C
only) is documented in ``interface.py``.
"""
import os
import sys
from itertools import combinations

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "mechanical"))
from constants import CONST  # noqa: E402

from sensor_data import AXES, SENSORS, BY_NAME as _BYNAME

_AX = {s["name"]: set(s["axes"]) for s in SENSORS}

# physical slot banks: capacity per bank derived from the mechanical model
# (the single source), and the base (always-present) set. Changing A_X / D_X
# in constants.py changes the bank here -- nothing re-types the count.
BANK_CAP = {"analog": len(CONST["A_X"]), "digital": len(CONST["D_X"])}
BASE_SENSORS = [s["name"] for s in SENSORS if s["slot"] == "base"]

# --- personas: which axes a given user actually needs to distinguish --------
PERSONAS = {
    "lab_researcher":  ["reducing", "oxidising", "sulfur", "amine", "ir_active",
                        "voc_total", "alcohol", "humidity", "temperature"],
    "fermentation":    ["alcohol", "ir_active", "reducing", "humidity",
                        "temperature"],
    "cold_chain":      ["amine", "sulfur", "ir_active", "ethylene", "humidity",
                        "temperature"],
    "kitchen_fridge":  ["amine", "sulfur", "ir_active", "ethylene", "reducing",
                        "humidity", "temperature"],
    "personal_exp":    ["reducing", "voc_total", "humidity", "temperature"],
    "breath_analysis": ["alcohol", "amine", "ir_active", "reducing", "oxidising",
                        "humidity", "temperature"],
    "perfume":         ["voc_total", "reducing", "oxidising", "humidity",
                        "temperature"],
}
UNION_AXES = sorted({a for axes in PERSONAS.values() for a in axes})


def covered(names):
    """Union of axes covered by a set of sensor names."""
    out = set()
    for n in names:
        out.update(_AX[n])
    return out


def base_axes():
    """Axes always covered by the soldered base (SHT31)."""
    return covered(BASE_SENSORS)


def principle_diversity(names):
    return len({_BYNAME[n]["principle"] for n in names})


def _pool_pruned(bank, allow=None):
    """Bank pool with strictly-dominated sensors removed.

    Sensor X is dominated by Y (same bank) if Y covers a superset of X's axes
    and costs no more. X can then never beat Y in a minimum-cost cover, so
    dropping it is exact, not a heuristic -- and it keeps the brute-force
    cover tractable now that the pool is the whole market.
    """
    pool = [s["name"] for s in SENSORS
            if s["slot"] == bank and (allow is None or s["principle"] in allow)]
    dom = set()
    for x in pool:
        for y in pool:
            if x == y:
                continue
            cx, cy = _AX[x], _AX[y]
            if cx <= cy and _BYNAME[y]["cost"] <= _BYNAME[x]["cost"]:
                cheaper = _BYNAME[y]["cost"] < _BYNAME[x]["cost"]
                if cx != cy or cheaper or y < x:
                    dom.add(x)
                    break
    return sorted(n for n in pool if n not in dom)


def _subsets(pool, cap, max_size):
    """(size, names, coverage, cost) for every subset of ``pool`` up to size."""
    out = []
    for k in range(0, min(cap, max_size) + 1):
        for combo in combinations(pool, k):
            cov = set()
            cost = 0
            for n in combo:
                cov |= _AX[n]
                cost += _BYNAME[n]["cost"]
            out.append((k, combo, cov, cost))
    return out


def select(required, max_slots=8, allow=None, prefer=None, within=None):
    """Exact minimum set cover under the 4+4 bank capacities.

    Base sensors (SHT31) are always present and consume no slot; their axes are
    pre-covered. Searches every (analog subset, digital subset) pair within the
    bank capacities and returns the smallest pack. ``prefer`` (module names) is
    a tie-break *after* count: among packs of equal size, the one using more of
    ``prefer`` wins, then the cheaper one. ``within`` restricts the search to a
    given module set (used to show a persona's subset of the starter pack).

    Returns (names, uncovered_axes).
    """
    req = set(required) - base_axes()
    if not req:
        return [], []
    pref = set(prefer) if prefer else set()
    wset = set(within) if within else None

    def _pick(bank, allow_):
        pool = _pool_pruned(bank, allow_)
        return [n for n in pool if wset is None or n in wset]

    analog_pool = _pick("analog", allow)
    digital_pool = _pick("digital", allow)
    dig = _subsets(digital_pool, BANK_CAP["digital"], max_slots)

    best = None
    for na in range(0, min(BANK_CAP["analog"], max_slots) + 1):
        for a in combinations(analog_pool, na):
            cov_a = set()
            cost_a = 0
            for n in a:
                cov_a |= _AX[n]
                cost_a += _BYNAME[n]["cost"]
            need = req - cov_a
            for nd, d, cov_d, cost_d in dig:
                if na + nd == 0 or na + nd > max_slots:
                    continue
                if need <= cov_d:
                    names = a + d
                    key = (na + nd,
                           -sum(1 for n in names if n in pref),
                           cost_a + cost_d)
                    if best is None or key < best[0]:
                        best = (key, names)
    if best is None:
        return [], sorted(req)
    names = list(best[1])
    return names, sorted(req - covered(names))


def recommended_pack():
    """Starter pack: covers every persona, fits the fixed 8-slot bank.

    Coverage alone leaves many equal-size covers; among them we prefer this
    engineering choice (broad multi-axis MOX selectors + one true-NDIR CO2 +
    an electrochemical ethylene cell), which maximises principle diversity.
    The preference is a *tie-break after count*, so the pack is still the
    minimum-size cover -- it just breaks ties toward the diverse parts.
    """
    return select(UNION_AXES, max_slots=sum(BANK_CAP.values()),
                  prefer=PREFERRED_PACK)


PREFERRED_PACK = ["MQ-135", "MICS-6814", "MQ-136", "ZE03-C2H4", "SCD40"]

RECOMMENDED_PACK, RECOMMENDED_MISSING = recommended_pack()


def report():
    print("OpenSmell sensor selection")
    print("  sensors in pool : %d" % len(SENSORS))
    print("  axes            : %d -> %s" % (len(AXES), ", ".join(AXES)))
    print("  personas        : %d" % len(PERSONAS))
    print("  banks           : analog %d + digital %d; base %s (always on)"
          % (BANK_CAP["analog"], BANK_CAP["digital"], ", ".join(BASE_SENSORS)))
    print()
    for p, axes in PERSONAS.items():
        names, miss = select(axes, prefer=RECOMMENDED_PACK,
                             within=RECOMMENDED_PACK)
        gmin, gmiss = select(axes)
        tag = "OK" if not miss else "MISS %s" % miss
        note = "" if set(gmin) <= set(RECOMMENDED_PACK) else \
            "  [market min %d: %s]" % (len(gmin), ", ".join(gmin))
        print("  %-16s %d from pack %s%s" % (p, len(names), tag, note))
        print("     %s" % ", ".join(names))
    print()
    print("RECOMMENDED PACK (%d slot modules + base): %s"
          % (len(RECOMMENDED_PACK), ", ".join(RECOMMENDED_PACK)))
    print("  covers all personas : %s" % (not RECOMMENDED_MISSING))
    print("  principle diversity : %d" % principle_diversity(RECOMMENDED_PACK))
    for n in RECOMMENDED_PACK:
        s = _BYNAME[n]
        print("    - %-12s %-15s %-6s %-22s %.2f W  $%s"
              % (n, s["principle"], s["slot"], "+".join(s["axes"]),
                 s["power"] / 1000.0, s["cost"]))


if __name__ == "__main__":
    report()
