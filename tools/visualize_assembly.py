#!/usr/bin/env python3
"""Generate exploded assembly renders + flow/animation from CONST.

Everything drawn here comes from mechanical/constants.py: shell, lid, PCB,
filter, fan, the eight sockets, and the eight flat OSM-1 cartridges.  Nothing
is hand-placed.  Outputs land in docs/figures/cad/.

Run:  python tools/visualize_assembly.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST  # noqa: E402

OUT = os.path.join(ROOT, "docs", "figures", "cad")
os.makedirs(OUT, exist_ok=True)

SH, SW, SHH = CONST["SH"], CONST["SW"], CONST["SHH"]
PCB_X0 = (SH - CONST["PCB_X"]) / 2.0
PCB_Y0 = (SW - CONST["PCB_Y"]) / 2.0
PCB_Z0, PCB_Z1 = CONST["PCB_Z"], CONST["PCB_TOP"]
LID_Z0, LID_Z1 = CONST["LID_Z0"], CONST["LID_Z1"]
SOCK_TOP = PCB_Z1 + CONST["SOCK_H"]
CART_W, CART_L, CART_H = 20.0, 32.0, 21.0
FAN_Y0 = SW + CONST["FAN_PLATE_T"]

SOCKETS = ([(cx, CONST["A_Y0"], "A") for cx in CONST["A_X"]] +
           [(cx, CONST["D_Y0"], "D") for cx in CONST["D_X"]])

# Colours are deliberate: gas path parts cool/inert, hardware neutral,
# cartridges warm so their orientation is unmistakable.
COL = {
    "shell": (0.55, 0.62, 0.70, 0.18),
    "lid": (0.70, 0.78, 0.86, 0.30),
    "pcb": (0.10, 0.45, 0.27, 0.95),
    "socket": (0.10, 0.10, 0.12, 0.95),
    "cart_front": (0.95, 0.45, 0.15, 0.90),
    "cart_rear": (0.85, 0.25, 0.35, 0.90),
    "filter": (0.80, 0.85, 0.90, 0.35),
    "fan": (0.25, 0.30, 0.35, 0.90),
    "flow": (0.05, 0.55, 0.85, 1.00),
}


def cube(ax, x, y, z, dx, dy, dz, color, lw=0.6):
    """Draw one cuboid; x/y/z are the lower-front-left corner."""
    v = [(x, y, z), (x + dx, y, z), (x + dx, y + dy, z), (x, y + dy, z),
         (x, y, z + dz), (x + dx, y, z + dz),
         (x + dx, y + dy, z + dz), (x, y + dy, z + dz)]
    faces = [[v[i] for i in f] for f in (
        (0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
        (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))]
    ax.add_collection3d(Poly3DCollection(faces, facecolors=color,
                                        edgecolors=(0, 0, 0, 0.45),
                                        linewidths=lw))


def cylinder(ax, cx, cy, cz, r, length, color, axis="y", n=24):
    import numpy as np
    if axis == "y":
        th = np.linspace(0, 2 * np.pi, n)
        xs, zs = cx + r * np.cos(th), cz + r * np.sin(th)
        verts = [(xs[i], cy, zs[i]) for i in range(n)]
        ax.add_collection3d(Poly3DCollection([verts], facecolors=color,
                                            edgecolors=(0, 0, 0, 0.5),
                                            linewidths=0.6))
        ax.plot(xs, np.full_like(xs, cy + length), zs, color=(0, 0, 0, 0.5), lw=0.6)
        ax.plot([xs[0], xs[0]], [cy, cy + length], [zs[0], zs[0]], color="k", lw=0.6)
        ax.plot([xs[n // 2], xs[n // 2]], [cy, cy + length],
                [zs[n // 2], zs[n // 2]], color="k", lw=0.6)


def explode(t):
    """Return per-part offsets. t=0 assembled, t=1 fully exploded."""
    e = t * t * (3 - 2 * t)  # smoothstep
    return {
        "lid": (0, 0, 34.0 * e),
        "filter": (0, -18.0 * e, 6.0 * e),
        "cart": (0, 0, 22.0 * e),
        "fan": (0, 18.0 * e, 0),
        "pcb": (0, 0, -6.0 * e),
    }


def draw(ax, t=0.0, flow=True, labels=True, elev=24, azim=-58):
    ax.clear()
    ax.set_xlim(-6, SH + 8)
    ax.set_ylim(-28, FAN_Y0 + 26)
    ax.set_zlim(-10, SHH + 42)
    ax.set_box_aspect((SH + 14, SW + 54, SHH + 52))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()

    off = explode(t)
    # shell tray: floor + four walls (open top)
    cube(ax, 0, 0, 0, SH, CONST["WALL"], SHH, COL["shell"])          # front
    cube(ax, 0, SW - CONST["WALL"], 0, SH, CONST["WALL"], SHH, COL["shell"])
    cube(ax, 0, 0, 0, CONST["WALL"], SW, SHH, COL["shell"])
    cube(ax, SH - CONST["WALL"], 0, 0, CONST["WALL"], SW, SHH, COL["shell"])
    cube(ax, 0, 0, 0, SH, SW, CONST["FLOOR_T"], COL["shell"])

    # PCB on standoffs
    dz = off["pcb"][2]
    cube(ax, PCB_X0, PCB_Y0, PCB_Z0 + dz, CONST["PCB_X"], CONST["PCB_Y"],
         CONST["PCB_T"], COL["pcb"])
    # sockets
    for cx, cy, row in SOCKETS:
        cube(ax, cx - 7.0, cy - 1.27, PCB_Z1 + dz, 14.0, 2.54,
             CONST["SOCK_H"], COL["socket"], lw=0.3)

    # flat cartridges: 20 wide across X, 32 long toward +Y, 21 high
    for cx, cy, row in SOCKETS:
        col = COL["cart_front"] if row == "D" else COL["cart_rear"]
        cube(ax, cx - CART_W / 2.0, cy, SOCK_TOP + dz + off["cart"][2],
             CART_W, CART_L, CART_H, col, lw=0.7)

    # filter drawer, pulled out/front in exploded view
    fx, fy, fz = off["filter"]
    cube(ax, CONST["CX0"] + 1, CONST["FILT_Y0"] + fy,
         CONST["FILT_Z0"] + fz, CONST["CX"] - 2, CONST["FILT_T"], 23.0,
         COL["filter"])

    # rear fan plate + fan disc
    fy = off["fan"][1]
    cube(ax, CONST["FAN_X"] - CONST["FAN_R"] - 6, SW + fy, CONST["FAN_Z"] - CONST["FAN_R"] - 6,
         2 * CONST["FAN_R"] + 12, CONST["FAN_PLATE_T"], 2 * CONST["FAN_R"] + 12,
         COL["fan"])
    cylinder(ax, CONST["FAN_X"], SW + fy, CONST["FAN_Z"], CONST["FAN_R"],
             CONST["FAN_T"], (0.12, 0.14, 0.17, 0.95))

    # lid
    cube(ax, 0, 0, LID_Z0 + off["lid"][2], SH, SW, CONST["LID_T"], COL["lid"])

    if flow:
        import numpy as np
        for x in (30.0, 61.0, 92.0):
            ax.quiver(x, 8, 30, 0, 88, 0, length=1.0, normalize=False,
                      color=COL["flow"], linewidth=2.2, arrow_length_ratio=0.06)
        ax.text(61, 6, 36, "AIR IN  (3 nostrils, front)", color="tab:blue",
                fontsize=8, ha="center")
        ax.text(61, SW + 4, 47, "AIR OUT  (40 mm fan, rear)", color="tab:blue",
                fontsize=8, ha="center")

    if labels:
        ax.text(2, 2, SHH + 6 + off["lid"][2], "LID", fontsize=8, weight="bold")
        ax.text(PCB_X0, PCB_Y0 - 4, PCB_Z0 - 6 + dz, "PCB / OSM-1 SOCKETS",
                fontsize=7, color="darkgreen")
        ax.text(CONST["D_X"][0], CONST["D_Y0"] + CART_L / 2,
                SOCK_TOP + CART_H + 2 + off["cart"][2], "FRONT ROW",
                color="darkorange", fontsize=7, ha="center")
        ax.text(CONST["A_X"][0], CONST["A_Y0"] + CART_L / 2,
                SOCK_TOP + CART_H + 2 + off["cart"][2], "REAR ROW",
                color="firebrick", fontsize=7, ha="center")
        ax.set_title("OpenSmell v1.1  |  airflow: FRONT (bottom) -> REAR (top)\n"
                     "flat OSM-1 cartridges, 20 mm across x 32 mm downstream",
                     fontsize=9, pad=2)


def save_still(name, **kw):
    fig = plt.figure(figsize=(10, 8), dpi=130)
    ax = fig.add_subplot(111, projection="3d")
    draw(ax, **kw)
    fig.subplots_adjust(left=0, right=1, bottom=0, top=0.95)
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=130, facecolor="white")
    plt.close(fig)
    print("  wrote", path)


def main():
    print("visualising OpenSmell v1.1 from mechanical/constants.py")
    save_still("assembly_exploded_iso.png", t=1.0, elev=24, azim=-58)
    save_still("assembly_exploded_top.png", t=1.0, elev=78, azim=-90)
    save_still("assembly_exploded_side.png", t=1.0, elev=6, azim=0)
    save_still("assembly_assembled_iso.png", t=0.0, elev=24, azim=-58)
    save_still("assembly_flow_top.png", t=0.0, elev=82, azim=-90, flow=True)

    fig = plt.figure(figsize=(8, 6), dpi=110)
    ax = fig.add_subplot(111, projection="3d")

    def frame(i):
        t = i / 59.0
        draw(ax, t=t, flow=True, labels=(i % 10 == 0),
             elev=18 + 8 * t, azim=-58 + 50 * t)
        return ax.patch,

    anim = FuncAnimation(fig, frame, frames=60, interval=90, blit=False)
    gif = os.path.join(OUT, "assembly_animation.gif")
    anim.save(gif, writer=PillowWriter(fps=11))
    plt.close(fig)
    print("  wrote", gif)


if __name__ == "__main__":
    main()
