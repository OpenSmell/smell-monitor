#!/usr/bin/env python3
"""Numeric acceptance gate for the OpenSmell response-diversity analysis.

Fails (exit 1) unless the information analysis obeys its own invariants on the
real data AND on synthetic matrices whose answer is known by construction.
Mirrors tools/verify_sensor_matrix.py / verify_electrical.py / verify_cad.py:
a green run is the gate before the array-size conclusion is trusted.

Checks
  * effective rank lies in [1, min(rows, cols)] for every use case;
  * greedy gains are non-increasing; captured energy is monotone and reaches
    100% once the frame spans the row space;
  * a duplicated channel adds ~0 information and does not inflate the rank;
  * an exactly orthogonal set (identity) yields rank == number of channels;
  * knee(0.90) <= knee(0.95);
  * the recommended pack is genuinely non-redundant (max |cos| < 0.8).

Run:  python tools/verify_orthogonality.py
"""
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "electrical"))
import orthogonality as OR  # noqa: E402

EPS = 1e-9
MAX_COS_PACK = 0.8

fails = []


def check(ok, label, detail=""):
    tag = "ok  " if ok else "FAIL"
    if not ok:
        fails.append(label)
    print("[%s] %-52s %s" % (tag, label, detail))


def main():
    print("== synthetic invariants (known answers) ==")
    # 4 exactly-orthogonal channels -> rank 4, all gains exactly 1
    I = np.eye(4)
    pr, _ = OR.effective_rank(I)
    check(abs(pr - 4.0) < 1e-6, "identity: effective rank == n", "%.3f" % pr)
    order, gains, basis = OR.greedy(*OR._normalised(I))
    check(all(abs(g - 1.0) < 1e-6 for g in gains),
          "identity: every gain == 1", ", ".join("%.2f" % g for g in gains))

    # two identical rows -> rank 1, second gain ~0
    D = np.array([[1.0, 0.3, 0.0], [1.0, 0.3, 0.0]])
    pr, _ = OR.effective_rank(D)
    check(abs(pr - 1.0) < 1e-6, "duplicate rows: rank == 1", "%.3f" % pr)
    order, gains, basis = OR.greedy(*OR._normalised(D))
    check(len(gains) == 1 or abs(gains[1]) < 1e-6,
          "duplicate rows: 2nd gain ~ 0",
          ", ".join("%.3f" % g for g in gains))

    print("== real data: rank bounds per use case ==")
    cases = {}
    for uc, gases in OR.USE_CASES.items():
        r = OR.analyse_case(gases)
        cases[uc] = r
        M, avail = r["M"], r["avail"]
        hi = min(M.shape[0], M.shape[1])
        check(1.0 - EPS <= r["pr"] <= hi + EPS,
              "effective rank in [1, min(r,c)]: %s" % uc,
              "%.2f in [1, %d]" % (r["pr"], hi))
        check(r["pr"] <= len(gases) + EPS,
              "effective rank <= gases: %s" % uc,
              "%.2f <= %d" % (r["pr"], len(gases)))
        gains = r["gains"]
        mono = all(gains[i] >= gains[i + 1] - 1e-9
                   for i in range(len(gains) - 1))
        check(mono, "greedy gains non-increasing: %s" % uc,
              "%.2f -> %.2f" % (gains[0], gains[-1]) if gains else "n/a")
        cum = r["cum"]
        inc = all(cum[i] <= cum[i + 1] + 1e-9 for i in range(len(cum) - 1))
        check(inc, "captured energy monotone: %s" % uc)
        check(len(cum) == 0 or cum[-1] >= 1.0 - 1e-6,
              "frame spans row space (cum -> 1): %s" % uc,
              "%.4f" % (cum[-1] if len(cum) else 0.0))
        check(len(cum) == 0 or
              OR.knee(cum, 0.90) <= OR.knee(cum, 0.95),
              "knee90 <= knee95: %s" % uc,
              "%d <= %d" % (OR.knee(cum, 0.90) if len(cum) else 0,
                            OR.knee(cum, 0.95) if len(cum) else 0))

    print("== real data: duplication & pack redundancy ==")
    dup = list(OR.PREFERRED_PACK) + ["SCD40"]
    r = OR.analyse_case(OR.ANALYTES, pool=dup)
    pack_pr = OR.effective_rank(OR.matrix(OR.PREFERRED_PACK, OR.ANALYTES))[0]
    check(r["pr"] - pack_pr < 0.5,
          "duplicate keeps rank ~flat", "%.2f -> %.2f" % (pack_pr, r["pr"]))

    Mg = OR.matrix(OR.PREFERRED_PACK, OR.ANALYTES)
    C = OR.pairwise_cos(Mg)
    off = np.abs(C[~np.eye(len(OR.PREFERRED_PACK), dtype=bool)])
    check(float(off.max()) < MAX_COS_PACK,
          "recommended pack non-redundant (max |cos| < %.1f)" % MAX_COS_PACK,
          "%.2f" % float(off.max()))

    print("== real data: bank structure (why analog is binding) ==")
    an = [s["name"] for s in OR.SENSORS if s["slot"] == "analog"]
    di = [s["name"] for s in OR.SENSORS if s["slot"] == "digital"]
    ar = OR.effective_rank(OR.matrix(an, OR.ANALYTES))[0]
    dr = OR.effective_rank(OR.matrix(di, OR.ANALYTES))[0]
    check(ar > dr, "analog pool spans more than digital pool",
          "%.2f > %.2f (n=%d vs %d)" % (ar, dr, len(an), len(di)))
    cana = {g for n in an for g in OR.BY_NAME[n]["profile"]} & set(OR.ANALYTES)
    cdig = {g for n in di for g in OR.BY_NAME[n]["profile"]} & set(OR.ANALYTES)
    check(bool(cana - cdig), "some analytes are analog-only",
          ", ".join(sorted(cana - cdig)))
    check(OR.capture(OR.ANALYTES, 0, 8) < OR.capture(OR.ANALYTES, 6, 2),
          "digital-only bank is weaker than analog-heavy",
          "%.0f%% < %.0f%%" % (100 * OR.capture(OR.ANALYTES, 0, 8),
                               100 * OR.capture(OR.ANALYTES, 6, 2)))

    print()
    if fails:
        print("RESULT: FAIL (%d)" % len(fails))
        for f in fails:
            print("   -", f)
        return 1
    b = cases["broad"]
    print("RESULT: ALL PASS (broad eff.rk %.2f/%d gases; k90=%d k95=%d; "
          "pack max|cos| %.2f)"
          % (b["pr"], len(OR.ANALYTES), OR.knee(b["cum"], 0.90),
             OR.knee(b["cum"], 0.95), float(off.max())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
