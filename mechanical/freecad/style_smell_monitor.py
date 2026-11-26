#!/usr/bin/env python3
"""Paint the smell_monitor.FCStd so internals are visible on first open.

freecadcmd.exe has no Gui module, so ViewProvider appearance (transparency
and colour) must be set through the real GUI application:

    "C:\\Program Files\\FreeCAD 1.1\\bin\\freecad.exe" style_smell_monitor.py

Run this AFTER build_smell_monitor.py whenever the model is rebuilt. The outer
shell is painted translucent; the plain lid, board, filter drawer, fan and screws
keep distinct colours, and the front-panel stack reads from the wall outward.
"""
import os

import FreeCAD as App

HERE = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(HERE, "smell_monitor.FCStd")

d = App.openDocument(path)

style = {
    "Shell":  ((0.72, 0.74, 0.78), 55),  # translucent grey outer shell
    "Lid":    ((0.62, 0.68, 0.76), 45),  # translucent grey lid
    "PCB":    ((0.10, 0.50, 0.20), 0),   # green chamber floor
    "Filter": ((0.90, 0.80, 0.30), 25),  # translucent yellow mesh drawer
    "Fan":    ((0.20, 0.35, 0.80), 20),  # translucent blue fan + shroud
    "Screws": ((0.55, 0.55, 0.60), 0),   # steel M3 screws
    "DisplayGasket": ((0.95, 0.95, 0.92), 0),  # PTFE ring on the front wall
    "DisplayWindow": ((0.70, 0.85, 0.95), 20),  # acrylic, the wetted face
    "DisplayBezel": ((0.30, 0.32, 0.36), 10),  # PETG ring outside the wall
    "DisplayOLED": ((0.08, 0.08, 0.12), 0),  # module behind the acrylic
    "ButtonCaps": ((0.85, 0.85, 0.88), 0),  # four front-panel switch caps
}

for name, (color, transparency) in style.items():
    obj = d.getObject(name)
    if obj is None:
        print("skip (not in model):", name)
        continue
    vp = obj.ViewObject
    vp.ShapeColor = color
    vp.Transparency = transparency
    vp.LineColor = (0.15, 0.15, 0.15)
    vp.LineWidth = 0.6
    vp.Visibility = True
    print("styled", name)

d.recompute()
d.save()
print("saved", path)
os._exit(0)