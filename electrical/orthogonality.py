#!/usr/bin/env python3
"""OpenSmell response-diversity analysis (the *sufficient* question).

`sensor_matrix.py` answers "does some module touch each coarse axis?" This
module answers the question that actually decides array size: **how much NEW,
independent information does each extra channel add, and where does the return
flatten out?**

The model is deliberately small and honest:

  * Every sensor is a row vector over the fine analyte space (``sensor_data``
    ``profile``). Row r_i[g] = that sensor's documented/admitted response
    strength to gas g, zeroed if g lies outside the sensor's stated range.
  * Two sensors whose (normalised) rows are parallel carry the SAME
    information no matter how many coarse "axes" they nominally touch. So the
    figure of merit is the geometry of R, not a count of sensors and not a
    count of axes.
  * We greedily add the sensor whose row has the largest component orthogonal
    to everything already chosen. That component (the *marginal gain*, in
    [0,1] after unit-normalising rows) is exactly the independent information
    the channel contributes. A duplicate sensor gains ~0.

Outputs per use case: the whole-market effective rank (participation ratio,
i.e. how many truly independent channels the market offers), the greedy
array-size curve, and the knee (smallest k reaching 90 / 95 % of the documented
response energy) with its cost / power / slot mix.

This is the metric that makes "4 + 4 slots" a *derived* number rather than an
asserted one. It runs on the same ``sensor_data`` facts as the selector, so the
two can never disagree about a sensor's *placement* (the selector's axis logic
and this module's analyte logic are different views of the same record).
"""
import argparse
import sys

import numpy as np

from sensor_data import GASES, BY_NAME, SENSORS

# covariates, not odour dimensions: handled by the base SHT31, excluded here
COVARIATES = ("humidity", "temperature")
ANALYTES = [g for g in GASES if g not in COVARIATES]

# fine-grained use cases: the gases a given user must actually resolve.
# (This is the analyte-level refinement of the personas in sensor_matrix.py.)
USE_CASES = {
    "indoor_air":    ["toluene", "hcho", "no2", "o3", "co", "ethanol"],
    "fermentation":  ["ethanol", "methanol", "acetone", "co2", "h2"],
    "cold_chain":    ["ethylene", "co2", "ethanol", "ammonia", "h2s", "tma"],
    "kitchen_fridge": ["ammonia", "tma", "h2s", "mercaptan", "co2",
                       "ethylene", "ethanol"],
    "breath":        ["acetone", "ethanol", "ammonia", "co", "no2", "h2"],
    "perfume":       ["toluene", "ethanol", "acetone", "hcho", "methanol"],
    "broad":         ANALYTES,
}

PREFERRED_PACK = ["MQ-135", "MICS-6814", "MQ-136", "ZE03-C2H4", "SCD40"]


# --- response matrix --------------------------------------------------------

def _in_range(name, gas):
    """Is gas at its reference level inside this sensor's stated range?"""
    rng = BY_NAME[name]["gases"].get(gas)
    if rng is None:
        return True                     # no range given -> profile stands
    return rng[0] <= GASES[gas]["ref"] <= rng[1]


def matrix(names, analytes):
    """R[i][j] response of sensor i to analyte j (0 if absent/out of range)."""
    M = np.zeros((len(names), len(analytes)))
    for i, n in enumerate(names):
        prof = BY_NAME[n]["profile"]
        for j, g in enumerate(analytes):
            if g in prof and _in_range(n, g):
                M[i, j] = prof[g]
    return M


def _normalised(M):
    """Return (Z, keep): rows scaled to unit length; keep = nonzero rows."""
    norm = np.linalg.norm(M, axis=1)
    keep = norm > 1e-12
    Z = np.zeros_like(M)
    Z[keep] = M[keep] / norm[keep, None]
    return Z, keep


# --- information metrics ----------------------------------------------------

def effective_rank(M):
    """Participation ratio (sum s^2)^2 / sum s^4 of the singular values.

    =1 for a single direction; =number of rows for a fully orthogonal set;
    small when the rows are near-parallel (redundant). The number of *real*
    independent channels, as opposed to the number of sensors.
    """
    if M.shape[0] == 0 or not np.any(M):
        return 0.0, np.zeros(0)
    s = np.linalg.svd(M, compute_uv=False)
    e = s ** 2
    denom = float((e ** 2).sum())
    return (float(e.sum()) ** 2) / denom if denom else 0.0, s


def greedy(Z, keep, tol=1e-9):
    """Greedy max-marginal-information order over unit-normalised rows.

    Returns (order, gains, basis): order is indices into Z, gains[i] is the
    orthogonal component of the i-th pick (1 = brand-new direction, 0 = fully
    redundant), and basis is the orthonormal frame the picks span.
    """
    idx = list(np.where(keep)[0])
    basis, order, gains = [], [], []
    while idx:
        best, bestg, bestr = None, -1.0, None
        for i in idx:
            r = Z[i] - sum((Z[i] @ b) * b for b in basis) if basis else Z[i]
            g = float(np.linalg.norm(r))
            if g > bestg:
                best, bestg, bestr = i, g, r
        if bestg < tol:
            break
        order.append(best)
        gains.append(bestg)
        basis.append(bestr / bestg)
        idx.remove(best)
    return order, gains, basis


def pairwise_cos(M):
    """Cosine similarity of every row pair (unit-normalised rows)."""
    Z, keep = _normalised(M)
    Z = Z[keep]
    if len(Z) < 2:
        return np.zeros((0, 0))
    return Z @ Z.T


def knee(cum, frac):
    """Smallest k (1-based) with cumulative fraction >= frac."""
    for k, c in enumerate(cum, 1):
        if c >= frac:
            return k
    return len(cum)


def loadout(names):
    """Physical cost of a channel set: power (mW), cost ($), footprint (mm^2),
    and the analog/digital/base slot mix."""
    p = sum(BY_NAME[n]["power"] for n in names)
    c = sum(BY_NAME[n]["cost"] for n in names)
    a = sum(BY_NAME[n]["footprint"][0] * BY_NAME[n]["footprint"][1]
            for n in names)
    mix = {"analog": 0, "digital": 0, "base": 0}
    for n in names:
        mix[BY_NAME[n]["slot"]] += 1
    return dict(power_w=p / 1000.0, cost=c, area_mm2=a, mix=mix)


def bank_greedy(gases, cap_analog, cap_digital, pool=None, tol=1e-9):
    """Greedy max-marginal-information under hard bank capacities.

    At each step the best remaining sensor is chosen among banks that still
    have a free slot, so the *shape* of the bank (how many of each) constrains
    how much independent information is reachable. Returns the picks, gains,
    cumulative captured fraction, and the per-bank usage.
    """
    names = pool if pool else [s["name"] for s in SENSORS]
    names = [n for n in names if BY_NAME[n]["slot"] != "base"]
    M = matrix(names, gases)
    Z, keep = _normalised(M)
    slot = [BY_NAME[n]["slot"] for n in names]
    cap = {"analog": cap_analog, "digital": cap_digital}
    idx = set(np.where(keep)[0].tolist())
    basis, order, gains = [], [], []
    used = {"analog": 0, "digital": 0}
    while idx:
        best, bestg, bestr = None, -1.0, None
        for i in idx:
            if used[slot[i]] >= cap[slot[i]]:
                continue
            r = Z[i] - sum((Z[i] @ b) * b for b in basis) if basis else Z[i]
            g = float(np.linalg.norm(r))
            if g > bestg:
                best, bestg, bestr = i, g, r
        if best is None or bestg < tol:
            break
        order.append(best)
        gains.append(bestg)
        basis.append(bestr / bestg)
        used[slot[best]] += 1
        idx.discard(best)
    Mn = Z[keep]
    total = float((Mn ** 2).sum())
    cum = np.cumsum(captured_energy(Mn, basis)) / total if total else np.array([])
    return dict(picks=[names[i] for i in order], gains=gains, cum=cum, used=used)


def capture(gases, cap_analog, cap_digital, pool=None):
    r = bank_greedy(gases, cap_analog, cap_digital, pool)
    return float(r["cum"][-1]) if len(r["cum"]) else 0.0


# --- analysis ---------------------------------------------------------------

def captured_energy(Mn, basis):
    """Energy of ``Mn`` captured by the orthonormal frame ``basis`` (per pick).

    Captured_k = sum over frame vectors b of ||Mn b||^2. This is the proper
    PCA-style variance explained: it counts ALL rows' energy, reaches the total
    Frobenius energy once the frame spans the row space, and is what makes a
    meaningful elbow.
    """
    return [float(np.linalg.norm(Mn @ b) ** 2) for b in basis]


def analyse_case(gases, pool=None):
    """Full greedy analysis of one analyte set over the market pool."""
    names = pool if pool else [s["name"] for s in SENSORS]
    names = [n for n in names if BY_NAME[n]["slot"] != "base"]
    M = matrix(names, gases)
    Z, keep = _normalised(M)
    pr, s = effective_rank(M)
    order, gains, basis = greedy(Z, keep)
    Mn = Z[keep]
    total = float((Mn ** 2).sum())
    cum = np.cumsum(captured_energy(Mn, basis)) / total if total else np.array([])
    picks = [names[i] for i in order]
    return dict(gases=gases, names=names, M=M, pr=pr, sv=s, picks=picks,
                gains=gains, cum=cum, avail=int(keep.sum()))


def report(pool=None, perturb=0):
    print("OpenSmell response-diversity analysis")
    print("  analyte space : %d gases (%s)" % (len(ANALYTES), ", ".join(ANALYTES)))
    print("  covariates    : %s (base SHT31)" % ", ".join(COVARIATES))
    pool_n = len([s for s in SENSORS if s["slot"] != "base"])
    print("  market pool   : %d slot modules" % pool_n)
    print()

    print("== whole-market information per use case ==")
    print("  %-15s %5s %6s   %s" % ("use case", "gases", "eff.rk", "independent channels available"))
    for uc, gases in USE_CASES.items():
        r = analyse_case(gases, pool)
        print("  %-15s %5d %6.2f   %s"
              % (uc, len(gases), r["pr"], "%.2f of %d sensors"
                 % (r["pr"], r["avail"])))
    print()

    print("== array-size curve (use case: broad = all analytes) ==")
    broad = analyse_case(ANALYTES, pool)
    cum = broad["cum"]
    k90, k95 = knee(cum, 0.90), knee(cum, 0.95)
    print("  k for 90%% of response energy : %d" % k90)
    print("  k for 95%% of response energy : %d" % k95)
    print("  %-3s %-12s %6s %7s %5s  %s"
          % ("#", "sensor", "gain", "cum", "slot", "principle"))
    for i, n in enumerate(broad["picks"][:k95 + 2]):
        g = broad["gains"][i]
        c = cum[i] if i < len(cum) else cum[-1]
        s = BY_NAME[n]
        print("  %-3d %-12s %6.2f %6.1f%% %5s  %s"
              % (i + 1, n, g, 100 * c, s["slot"], s["principle"]))
    print()

    print("== per use case: where the return flattens ==")
    print("  %-15s %4s %4s  %-38s %8s %7s"
          % ("use case", "k90", "k95", "pack at k95 (greedy)", "cost($)", "power(W)"))
    for uc, gases in USE_CASES.items():
        r = analyse_case(gases, pool)
        cum = r["cum"]
        k95 = knee(cum, 0.95) if len(cum) else 0
        picks = r["picks"][:k95]
        lo = loadout(picks)
        disp = ", ".join(picks)
        if len(disp) > 38:
            disp = disp[:35] + "..."
        print("  %-15s %4d %4d  %-38s %8d %7.2f"
              % (uc, knee(cum, 0.90) if len(cum) else 0, k95, disp,
                 lo["cost"], lo["power_w"]))
    print()

    print("== recommended pack: is it actually non-redundant? ==")
    Mg = matrix(PREFERRED_PACK, ANALYTES)
    pr, _ = effective_rank(Mg)
    C = pairwise_cos(Mg)
    off = C[~np.eye(len(PREFERRED_PACK), dtype=bool)] if C.size else np.array([0.0])
    print("  pack            : %s" % ", ".join(PREFERRED_PACK))
    print("  effective rank  : %.2f of %d channels" % (pr, len(PREFERRED_PACK)))
    print("  mean |cos|      : %.2f   max |cos| : %.2f"
          % (float(np.abs(off).mean()), float(np.abs(off).max())))
    for i, a in enumerate(PREFERRED_PACK):
        for j in range(i + 1, len(PREFERRED_PACK)):
            c = float(C[i, j])
            if abs(c) >= 0.6:
                flag = "  <-- correlated"
            else:
                flag = ""
            print("    cos(%-10s,%-10s) = %+.2f%s"
                  % (a, PREFERRED_PACK[j], c, flag))
    print()

    print("== sanity: duplication adds information? ==")
    dup = PREFERRED_PACK + ["SCD40"]
    r = analyse_case(ANALYTES, pool=dup)
    print("  adding a 2nd SCD40 -> gain of the duplicate = %.3f (expect ~0)"
          % (r["gains"][5] if len(r["gains"]) > 5 else 0.0))
    print("  pack eff. rank %d ch -> %.2f ; +dup %d ch -> %.2f (expect ~flat)"
          % (len(PREFERRED_PACK), effective_rank(Mg)[0],
             len(dup), r["pr"]))

    if perturb:
        _perturb_report(pool, perturb)
    return broad, k90, k95


def min_analog(gases, d=8, frac=0.95):
    """Fewest analog slots that SUFFICE (greedy certificate) for a use case,
    given ``d`` digital slots available. A valid *upper* bound on the true
    minimum (if the greedy set works, A analog is enough)."""
    for a in range(0, 13):
        if capture(gases, a, d) >= frac - 1e-9:
            return a
    return 13


def slots_report():
    """Derive the slot count from reachable information (order-robust).

    Two order-independent anchors: (1) the whole market spans only ~8
    independent dimensions for the broad analyte set, so slots beyond that buy
    nothing; (2) the digital market spans only ~3.4 and cannot see the "hard"
    gases, so the scarce resource is ANALOG. Then a greedy certificate fixes
    the analog floor: the fewest analog slots that bring every single-domain
    use case to its 95% knee. Every printed number is computed, not asserted.
    """
    huge = len(SENSORS)
    print("== slot count derivation ==")
    an = [s["name"] for s in SENSORS if s["slot"] == "analog"]
    di = [s["name"] for s in SENSORS if s["slot"] == "digital"]
    ar = effective_rank(matrix(an, ANALYTES))[0]
    dr = effective_rank(matrix(di, ANALYTES))[0]
    cana = {g for n in an for g in BY_NAME[n]["profile"]} & set(ANALYTES)
    cdig = {g for n in di for g in BY_NAME[n]["profile"]} & set(ANALYTES)
    broad_rank = effective_rank(
        matrix([s["name"] for s in SENSORS if s["slot"] != "base"],
               ANALYTES))[0]
    print("  anchor 1: broad independent dimensions (market) = %.2f"
          "  -> slots beyond ~%.0f add nothing"
          % (broad_rank, round(broad_rank)))
    print("  anchor 2: analog pool n=%d eff.rank %.2f  vs  digital pool n=%d "
          "eff.rank %.2f" % (len(an), ar, len(di), dr))
    print("            gases only analog can see: %s"
          % ", ".join(sorted(cana - cdig)))
    print("            digital-only bank (0A+%dD) captures just %.0f%% of broad"
          % (len(di), 100 * capture(ANALYTES, 0, len(di))))
    print()

    print("  per use case: analog floor (D=%d) and capture at candidate banks"
          % len(di))
    print("  %-15s %8s %8s %8s %8s"
          % ("use case", "A_floor", "4A+4D", "5A+3D", "6A+2D"))
    floor = 0
    for uc, gases in USE_CASES.items():
        if uc == "broad":
            continue                    # multi-domain, handled on its own row
        a = min_analog(gases)
        floor = max(floor, a)
        print("  %-15s %8d %7.0f%% %7.0f%% %7.0f%%"
              % (uc, a, 100 * capture(gases, 4, 4),
                 100 * capture(gases, 5, 3), 100 * capture(gases, 6, 2)))
    print("  %-15s %8d %7.0f%% %7.0f%% %7.0f%%"
          % ("broad", min_analog(ANALYTES), 100 * capture(ANALYTES, 4, 4),
             100 * capture(ANALYTES, 5, 3), 100 * capture(ANALYTES, 6, 2)))
    print()
    print("  => analog floor to serve every SINGLE-domain use case = %d" % floor)
    print("  => the %d-gas 'broad' set needs %d analog and does not fit the bank"
          " (deliberate limitation)" % (len(ANALYTES), min_analog(ANALYTES)))
    print("  => digital pool rank %.1f, VOC-clustered; it cannot see the "
          "analog-only gases above" % dr)
    # recommended: floor analog + most digital that still closes the MCU pins
    rec_d = max(d for d in range(0, len(di) + 1) if _pins(floor, d) <= 17)
    print("  => MCU-only max digital with %d analog = %d (pins %d/17)"
          % (floor, rec_d, _pins(floor, rec_d)))
    print("  => recommended bank: %dA + %dD (see --banks / --lane for the full "
          "constraint set)" % (floor, rec_d))


def _pins(a, d):
    return 4 + a + 2 * d          # 3 fixed outputs + button + 1/analog + 2/digital


def _pitch(a):
    return (106.0 - 22.0) / (a - 1) if a > 1 else 0.0


def banks_report():
    """Multi-constraint trade study of candidate banks.

    A slot count is only 'optimal' if it closes on *all* budgets at once:
      information (orthogonality), MCU pins, ADC channels (4 per ADS1115),
      I2C mux channels (8 per TCA9548A), worst-case 5 V heater load, and the
      106 mm analog lane. This prints the feasible frontier so the choice is
      argued from numbers, not taste.
    """
    print("== bank trade study: every budget at once ==")
    print("  %-6s %4s %-9s %4s %3s %7s %6s %6s %6s"
          % ("bank", "pins", "MCU?", "ADCs", "TCA", "heat5V", "pitch",
             "broad", "minUse"))
    for a in range(3, 8):
        for d in range(0, 9):
            if a + d > 12:
                continue
            p = _pins(a, d)
            mcu = "MCU" if p <= 17 else "expander"
            adcs = -(-a // 4)
            heat = 0.9 * a
            pitch = _pitch(a)
            cap = 100 * capture(ANALYTES, a, d)
            minu = min(100 * capture(g, a, d)
                       for uc, g in USE_CASES.items() if uc != "broad")
            if (a, d) in ((4, 4), (5, 3), (5, 4), (6, 3), (6, 4), (4, 6),
                          (5, 6), (4, 8)):
                print("  %-6s %4d %-9s %4d %3d %6.1fW %6.1f %5.0f%% %5.0f%%"
                      % ("%dA+%dD" % (a, d), p, mcu, adcs, d, heat, pitch,
                         cap, minu))
    print("  note: analog modules are the wide ones (MQ ~22 mm, NDIR 33 mm);")
    print("        a 5th *full-width* analog slot needs pitch 21 < 22 mm, so")
    print("        the 106 mm lane caps FULL-WIDTH analog at 4 unless the")
    print("        modules are narrower or staggered across depth.")


def lane_report():
    """Analog-lane feasibility: can the derived analog count physically fit?

    The information analysis says *how many* analog channels are worth having;
    it cannot say whether they fit. This checks the 106 mm lane against the real
    module footprints in ``sensor_data`` at a range of inter-module gaps, and
    tests the depth-stagger fallback. Reads the same CONST as the CAD model.
    """
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "mechanical"))
    from constants import CONST
    cx = float(CONST["CX"])
    wall = 3.0
    usable = cx - 2.0 * wall
    analog = [s for s in SENSORS if s.get("iface") == "analog"]
    print("== analog lane feasibility ==")
    print("  chamber CX %.0f mm; usable %.0f mm (%.0f mm wall each side)"
          % (cx, usable, wall))
    print("  %-9s %-22s %-10s %s"
          % ("in-row w", "n fit @ gap 0/2/4", "max@2mm", "examples"))
    for w in sorted({s["footprint"][0] for s in analog}):
        fits = [int((usable + g) // (w + g)) for g in (0, 2, 4)]
        ex = ", ".join(sorted(s["name"] for s in analog
                              if s["footprint"][0] == w)[:3])
        print("  %-9s %-22s %-10d %s"
              % ("%d mm" % w, "%d / %d / %d" % tuple(fits), fits[1], ex))
    deep = float(CONST["NOSEY"]) - float(CONST["FLOOR"])
    print("  analog depth available %.0f mm (FLOOR %.0f -> NOSEY %.0f);"
          % (deep, CONST["FLOOR"], CONST["NOSEY"]))
    print("  two stacked sub-rows of 18 mm => 2x the single-row count.")


def _perturb_report(pool, n=200, lo=0.7, hi=1.3, seed=0):
    """Re-run the broad-set knee under multiplicative uncertainty on the
    *inferred* (non-datasheet) rows, to show the knee is stable."""
    rng = np.random.default_rng(seed)
    inferred = [s["name"] for s in SENSORS if s["basis"] != "datasheet"]
    ks = []
    for _ in range(n):
        names = [s["name"] for s in SENSORS if s["slot"] != "base"]
        M = matrix(names, ANALYTES)
        for i, nm in enumerate(names):
            if nm in inferred:
                M[i] *= rng.uniform(lo, hi, size=M.shape[1])
        Z, keep = _normalised(M)
        _, gains, basis = greedy(Z, keep)
        Mn = Z[keep]
        total = float((Mn ** 2).sum())
        cum = (np.cumsum(captured_energy(Mn, basis)) / total
               if total else np.array([]))
        ks.append(knee(cum, 0.90) if len(cum) else 0)
    ks = np.array(ks)
    print()
    print("== uncertainty (%d trials; inferred rows x[%.1f,%.1f]) =="
          % (n, lo, hi))
    print("  k90 broad: mean %.2f  median %d  p5 %d  p95 %d"
          % (ks.mean(), int(np.median(ks)), int(np.percentile(ks, 5)),
             int(np.percentile(ks, 95))))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--perturb", type=int, default=0,
                    help="Monte-Carlo trials for knee stability (0=off)")
    ap.add_argument("--slots", action="store_true",
                    help="sweep bank (analog,digital) sizes (slot-count derivation)")
    ap.add_argument("--banks", action="store_true",
                    help="multi-constraint bank trade study")
    ap.add_argument("--lane", action="store_true",
                    help="analog-lane packing feasibility")
    ap.add_argument("--pool", default=None,
                    help="comma-separated module subset (default: whole market)")
    a = ap.parse_args(argv)
    pool = a.pool.split(",") if a.pool else None
    report(pool, a.perturb)
    if a.slots:
        print()
        slots_report()
    if a.banks:
        print()
        banks_report()
    if a.lane:
        print()
        lane_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
