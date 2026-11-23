#!/usr/bin/env python3
"""Add the permanent silkscreen identity to the routed v1.1 board.

Reproducible step: it places two F.SilkS texts in a clear 34 x 5 mm band
between the two socket rows, in board-local coordinates.  Both positions were
chosen from KiCad item bounding boxes; tools/verify_pcb.py runs DRC so any
silkscreen/copper or silkscreen/silkscreen collision fails the gate.

Run with KiCad's Python:
  & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" tools/add_board_markings.py
"""
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BOARD = os.path.join(ROOT, "electrical", "smell_monitor_v1_1",
                     "smell_monitor_v1_1.kicad_pcb")

# text, board-local x, board-local y, height, thickness
MARKINGS = [
    ("OPEN SMELL", 78.0, 62.3, 2.4, 0.35),
    ("SMELL MONITOR v1.1  /  OSM-1", 78.0, 65.0, 1.3, 0.20),
]


def main():
    board = pcbnew.LoadBoard(BOARD)
    existing = {d.GetText(): d for d in board.GetDrawings()
                if isinstance(d, pcbnew.PCB_TEXT) and d.GetLayer() == pcbnew.F_SilkS}
    for text, x, y, size, thick in MARKINGS:
        item = existing.get(text)
        if item is None:
            item = pcbnew.PCB_TEXT(board)
            item.SetText(text)
            item.SetLayer(pcbnew.F_SilkS)
            board.Add(item)
            print("added:", text)
        else:
            print("updated:", text)
        item.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        item.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size),
                                          pcbnew.FromMM(size)))
        item.SetTextThickness(pcbnew.FromMM(thick))
        item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        item.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    pcbnew.SaveBoard(BOARD, board)


if __name__ == "__main__":
    main()
