#!/usr/bin/env python3
"""Add the permanent silkscreen identity and slot labelling to the routed board.

Reproducible step: branding, a slot number beside every gas-cell socket, a
Qwiic number beside every Qwiic port, and the two pin-order legends.  Positions
are board-local; tools/verify_pcb.py runs full DRC, so any silkscreen/copper or
silkscreen/silkscreen collision fails the gate.

Run with KiCad's Python:
  & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" tools/add_board_markings.py
"""
import os
import sys

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
from constants import CONST  # noqa: E402

BOARD = os.path.join(ROOT, "electrical", "smell_monitor_v1_1",
                     "smell_monitor_v1_1.kicad_pcb")
PCB_X, PCB_Y = CONST["PCB_X"], CONST["PCB_Y"]
PCB_X0, PCB_Y0 = (CONST["SH"] - PCB_X) / 2.0, (CONST["SW"] - PCB_Y) / 2.0


def board_xy(shell_x, shell_y):
    """Shell coordinate -> board-local KiCad coordinate (Y is mirrored)."""
    return (shell_x - PCB_X0, PCB_Y - (shell_y - PCB_Y0))


# text, board-local x, board-local y, height, thickness
MARKINGS = [
    ("OPEN SMELL", 78.0, 62.3, 2.4, 0.35),
    ("SMELL MONITOR v1.1  /  OSM-1", 78.0, 65.0, 1.3, 0.20),
    # gas-cell socket legends: the pin order is printed once per wall
    ("1x6: +5V GND AO DO 3V3 ID", 46.0, 88.0, 1.0, 0.16),
    ("Qwiic: GND 3V3 SDA SCL", 80.0, 88.0, 1.0, 0.16),
]

# slot numbers beside each socket, on the outside of each wall row
for i, y in enumerate(CONST["AN_Y"]):
    MARKINGS.append((f"S{i}", *board_xy(CONST["AN_X"] - 7.0, y), 1.5, 0.25))
for i, y in enumerate(CONST["DI_Y"]):
    _x, _y = board_xy(CONST["DI_X"] + 10.0, y)
    MARKINGS.append((f"S{i+4}", _x, _y - 4.0, 1.5, 0.25))

# Qwiic port numbers on the proven interior grid
for i, (x, y) in enumerate([(18.0, 64.0), (44.0, 64.0),
                            (70.0, 64.0), (96.0, 64.0),
                            (25.5, 22.0), (47.5, 22.0),
                            (69.5, 22.0), (91.5, 22.0)]):
    MARKINGS.append((f"Q{i}", x, PCB_Y - (y - PCB_Y0) - 4.0, 1.1, 0.18))


# Footprint reference fields that land on a neighbour's silk/pad after the
# side-wall move.  Keep the part where it belongs and move only its label.
# (ref, kicad x, kicad y, angle degrees)
REF_PLACEMENT = [
    ("J3", 7.0, 61.5, 90),
    ("J4", 7.0, 37.5, 90),
    ("BZ1", 24.0, 30.0, 0),
]


def main():
    board = pcbnew.LoadBoard(BOARD)
    for ref, x, y, angle in REF_PLACEMENT:
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            continue
        fp.Reference().SetPosition(
            pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        fp.Reference().SetTextAngleDegrees(angle)
    existing = {d.GetText(): d for d in board.GetDrawings()
                if isinstance(d, pcbnew.PCB_TEXT) and d.GetLayer() == pcbnew.F_SilkS}
    for text, x, y, size, thick in MARKINGS:
        item = existing.get(text)
        if item is None:
            item = pcbnew.PCB_TEXT(board)
            item.SetText(text)
            item.SetLayer(pcbnew.F_SilkS)
            board.Add(item)
        item.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        item.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size),
                                          pcbnew.FromMM(size)))
        item.SetTextThickness(pcbnew.FromMM(thick))
        item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        item.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    pcbnew.SaveBoard(BOARD, board)
    print("silkscreen: %d permanent texts" % len(MARKINGS))


if __name__ == "__main__":
    main()
