#!/usr/bin/env python3
"""Turn the tracer probes into exchange times.

The tracer run puts a unit step at the three inlets (T = 1 from t = 0) and
starts from T = 0 everywhere.  At any point, t63 - the time to reach 63 % of
the step - is that point's exchange time; t90 is the purge time for 90 %.

    python3 report.py [--end 40]

Reads postProcessing/probes/<time>/T (written by the probes function object in
system/controlDict.tracer).  No plotting, no dependencies.
"""
import argparse
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

LABELS = ["A0", "A1", "A2", "A3", "D0", "D1", "D2", "D3", "bypass", "outlet"]

# plug flow through the empty chamber: V = 116 x 108 x 34.4 mm3 at 15 L/min
VOL_L = 116.0 * 108.0 * 34.4 / 1e6
TAU = VOL_L / (15.0 / 60.0)


def read_probes(path):
    names, rows = [], []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                if "Probe" in line:
                    names.append(line.split("Probe")[1].split()[0])
                continue
            if not line:
                continue
            rows.append([float(v) for v in line.split()])
    return names, rows


def crossing(rows, col, level):
    prev = None
    for r in rows:
        if r[col] >= level:
            if prev is None:
                return r[0]
            t0, v0 = prev[0], prev[col]
            if r[col] == v0:
                return r[0]
            return t0 + (level - v0) * (r[0] - t0) / (r[col] - v0)
        prev = r
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", type=float, default=None,
                    help="run end time, for probes that never reach 63%%")
    args = ap.parse_args()

    hits = sorted(glob.glob(os.path.join(
        HERE, "postProcessing", "probes", "*", "T")))
    if not hits:
        sys.exit("no postProcessing/probes/*/T - run ./run.sh first")
    path = hits[-1]
    names, rows = read_probes(path)
    if not rows:
        sys.exit("%s has no data rows" % path)

    n = len(rows[0]) - 1
    labels = LABELS[:n] if n <= len(LABELS) else ["P%d" % i for i in range(n)]

    print("probes: %s  (%d samples, t = %.2f .. %.2f s)"
          % (os.path.relpath(path, HERE), len(rows), rows[0][0], rows[-1][0]))
    print()
    print("%-8s %8s %8s %8s" % ("probe", "t63/s", "t90/s", "t63/tau"))
    print("-" * 36)
    t63 = {}
    for i, name in enumerate(labels):
        a = crossing(rows, i + 1, 0.63)
        b = crossing(rows, i + 1, 0.90)
        t63[name] = a
        print("%-8s %8s %8s %8s"
              % (name,
                 "%.2f" % a if a is not None else "-",
                 "%.2f" % b if b is not None else "-",
                 "%.2f" % (a / TAU) if a is not None else "-"))

    print()
    print("plug-flow reference: V/Q = %.2f s at 15 L/min" % TAU)

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else None

    dig, ana = mean([t63.get("D%d" % i) for i in range(4)]), \
        mean([t63.get("A%d" % i) for i in range(4)])
    if dig is not None and ana is not None:
        print("upstream (digital) row t63 %.2f s, downstream (analog) %.2f s"
              % (dig, ana))
        print("  -> the downstream row sees the sample %.2f s later; that "
              "difference is the row-to-row cascade and it is what the record "
              "must carry (slot flow position)." % (ana - dig))
    by = t63.get("bypass")
    if by is not None and dig is not None:
        print("under-pad probe t63 %.2f s vs first row %.2f s" % (by, dig))
        if by < 0.8 * dig:
            print("  -> FASTER than the first row: the front slot is a bypass "
                  "around the filter. Seal the drawer's bottom gap.")
        else:
            print("  -> not a short-circuit: the filter pad is doing its job.")


if __name__ == "__main__":
    main()
