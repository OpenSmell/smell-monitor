#!/usr/bin/env python3
"""Write the solid obstacles of the v1.1 chamber as one ASCII STL.

The fluid volume is the tray cavity above the board - x 3..119, y 3..111,
z 8.6..54 - so the obstacles are the things the gas cannot pass through:

  * eight 1x6 sockets on the two inner side walls, standing 8.5 mm off the board;
  * eight UPRIGHT breakout boards on them, standing 32 mm tall and reaching
    21 mm into the central channel, their faces looking at each other;
  * four corner bosses for the lid screws.

    python3 gen_geometry.py                # the reference build, 8 slots filled
    python3 gen_geometry.py --omit 3,6     # leave slots 3 and 6 empty

--omit exists so the same case answers the interference question: run it with
all eight filled, then with one empty, and compare the tracer arrival at the
neighbours.  Slots 0-3 are the left wall, 4-7 the right wall.

Everything is read from mechanical/constants.py and mechanical/standard.py, so
the case cannot drift from the enclosure.
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))

from constants import CONST  # noqa: E402
from standard import CARTRIDGE, SLOTS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "constant", "triSurface", "cartridges.stl")

Z0 = CONST["PCB_TOP"]
Z1 = Z0 + CONST["SOCK_H"]
H = CARTRIDGE["envelope"]["height"]   # vertical: an upright card stands 32 mm
W = CARTRIDGE["envelope"]["across"]   # along the wall (Y), <= 20 mm
R = CARTRIDGE["envelope"]["reach"]    # into the channel (X), <= 21 mm


def box(x0, x1, y0, y1, z0, z1):
    """Twelve triangles, outward normals, no shared vertices."""
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = []
    for a, b, c, d in quads:
        tris.append((v[a], v[b], v[c]))
        tris.append((v[a], v[c], v[d]))
    return tris


def prism(cx, cy, r, z0, z1, n=12):
    """A boss: n-sided prism, enough for snappy to snap to."""
    ring = [(cx + r * math.cos(2 * math.pi * i / n),
             cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    tris = []
    for i in range(n):
        (xa, ya), (xb, yb) = ring[i], ring[(i + 1) % n]
        tris.append(((cx, cy, z0), (xb, yb, z0), (xa, ya, z0)))
        tris.append(((cx, cy, z1), (xa, ya, z1), (xb, yb, z1)))
        tris.append(((xa, ya, z0), (xb, yb, z0), (xb, yb, z1)))
        tris.append(((xa, ya, z0), (xb, yb, z1), (xa, ya, z1)))
    return tris


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--omit", default="",
                    help="comma-separated slot indices to leave empty (0-7)")
    args = ap.parse_args()
    omit = {int(s) for s in args.omit.split(",") if s.strip()}

    slots = ([(CONST["AN_X"], y) for y in CONST["AN_Y"]]
             + [(CONST["DI_X"], y) for y in CONST["DI_Y"]])
    assert len(slots) == SLOTS["reference_count"]

    tris = []
    for i, (cx, cy) in enumerate(slots):
        # Pin line runs FRONT-TO-BACK (along Y): the socket block is narrow in
        # X and W mm long in Y.  A straight-header board therefore stands in
        # the Y-Z plane, its face normal along X, looking inward.
        tris += box(cx - CONST["SOCK_P"] / 2.0, cx + CONST["SOCK_P"] / 2.0,
                    cy - CONST["SOCK_N"] * CONST["SOCK_P"] / 2.0,
                    cy + CONST["SOCK_N"] * CONST["SOCK_P"] / 2.0,
                    Z0, Z1)
        if i in omit:
            continue
        # upright board: W across the wall (Y), R into the channel (X), H tall
        face_in = 1 if cx < CONST["SH"] / 2.0 else -1
        x0, x1 = (cx, cx + R) if face_in > 0 else (cx - R, cx)
        tris += box(x0, x1, cy - W / 2.0, cy + W / 2.0, Z1, Z1 + H)

    for bx, by in ((CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
                   (CONST["SH"] - CONST["BOSS_INSET"], CONST["BOSS_INSET"]),
                   (CONST["BOSS_INSET"], CONST["SW"] - CONST["BOSS_INSET"]),
                   (CONST["SH"] - CONST["BOSS_INSET"],
                    CONST["SW"] - CONST["BOSS_INSET"])):
        tris += prism(bx, by, CONST["BOSS_D"] / 2.0, Z0, CONST["CAV_Z1"])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("solid obstacles\n")
        for a, b, c in tris:
            f.write("facet normal 0 0 0\n outer loop\n")
            for p in (a, b, c):
                f.write("  vertex %.6f %.6f %.6f\n" % p)
            f.write(" endloop\nendfacet\n")
        f.write("endsolid obstacles\n")

    print("wrote %s: %d triangles, %d slot(s) empty"
          % (OUT, len(tris), len(omit)))


if __name__ == "__main__":
    main()
