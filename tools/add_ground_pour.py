#!/usr/bin/env python3
"""Add the bottom-layer ground return pour to the routed OSM-1 board.

Routing is done by ``electrical/route_pcb.py``; a ground plane is deliberately
not part of the FreeRouting netlist (it would route hundreds of spokes instead
of using copper).  This script is the reproducible final step: it replaces any
existing B.Cu GND pour, pours a new one inside the board outline, fills it with
KiCad's own zone filler and saves the board.  Gerber export then picks it up.

The pour is not a substitute for the 5 V trunk: eight 150 mA cells still put
up to 1.4 A through the 0.30 mm 5 V trace.  It is the low-impedance return for
the ADC/mux/I2C ground references and for the motor/buzzer switching currents.

Run with KiCad's own Python (pcbnew is not importable from system Python):

    & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" tools/add_ground_pour.py

The script is idempotent: running it again replaces the pour, never stacks a
second copy on top of it.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PCB = os.environ.get("SMELL_PCB") or os.path.join(
    ROOT, "electrical", "smell_monitor_v1_1", "smell_monitor_v1_1.kicad_pcb")

import pcbnew  # noqa: E402

INSET_MM = 0.6          # inside Edge.Cuts; KiCad also clips to the real outline
CLEARANCE_MM = 0.25     # > the 0.15 mm design-rule minimum


def mm(v):
    return pcbnew.ToMM(v)


def board_bounds(board):
    pts = []
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts and isinstance(d, pcbnew.PCB_SHAPE):
            pts.extend((d.GetStart(), d.GetEnd()))
    if not pts:
        raise SystemExit("no Edge.Cuts geometry - refusing to pour")
    return (min(p.x for p in pts), min(p.y for p in pts),
            max(p.x for p in pts), max(p.y for p in pts))


def main():
    if not os.path.isfile(PCB):
        raise SystemExit("no board at %s" % PCB)
    board = pcbnew.LoadBoard(PCB)
    gnd = board.FindNet("GND")
    if gnd is None:
        raise SystemExit("no GND net on the board - refusing to pour")

    # Remove only a previous B.Cu GND pour; leave the ESP32 antenna keep-out
    # and any other zones exactly where they are.
    removed = 0
    for zone in list(board.Zones()):
        if zone.GetLayer() == pcbnew.B_Cu and zone.GetNetname() == "GND":
            board.Remove(zone)
            removed += 1

    x0, y0, x1, y1 = board_bounds(board)
    i = pcbnew.FromMM(INSET_MM)
    zone = pcbnew.ZONE(board)
    zone.SetLayer(pcbnew.B_Cu)
    zone.SetNet(gnd)
    zone.SetLocalClearance(pcbnew.FromMM(CLEARANCE_MM))
    # Ground is the only net with a pour, so solid connections are safe and
    # avoid a `starved_thermal` error where a socket pad is boxed in by signal
    # tracks on B.Cu (one 0603 pad, J8 pin 2, was exactly that case).
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    zone.SetMinThickness(pcbnew.FromMM(0.25))
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in ((x0 + i, y0 + i), (x1 - i, y0 + i),
                 (x1 - i, y1 - i), (x0 + i, y1 - i)):
        outline.Append(x, y)
    zone.SetOutline(outline)
    board.Add(zone)

    filler = pcbnew.ZONE_FILLER(board)
    if not filler.Fill(board.Zones()):
        raise SystemExit("zone fill failed - board not saved")

    board.Save(PCB)
    area = zone.GetFilledArea() / 1e12     # KiCad area is in nm^2
    print("bottom GND pour: replaced %d, %.1f mm2 filled" % (removed, area))
    return 0


if __name__ == "__main__":
    sys.exit(main())
