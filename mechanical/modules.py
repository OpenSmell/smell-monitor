#!/usr/bin/env python3
"""Mechanical + connector truth for the plug-in sensor modules (mm).

`electrical/interface.py` owns the *electrical* slot contract (pin order, rails).
This file owns the *mechanical* half: what physically hangs off the header when a
module is plugged in, per module family, each with a source -- the same
discipline `sensor_data.py` uses for electrical facts.

WHY THIS EXISTS
---------------
The chamber was sized from an assumed "worst-case analog module 22 x 35 x 23".
Checking real vendors, that is a lottery, not a fact:

  * the same MQ-135 is sold as 32x20, 32x22, 36x24 and 40x21 mm boards;
  * the same MQ-135 pinout is sold as `VCC GND AO DO` *and* `VCC GND DO AO`, so
    a passive 2.54 mm socket cannot promise the right signal on the right pin;
  * the Winsen ZE03 is not a card at all -- it is a 23.5 mm diameter can;
  * the MH-Z19C-PC is 38.8 mm long with a 1.5 mm JST-ZH connector, not 2.54 mm;
  * MICS-6814 has THREE analog outputs, so it cannot be read by a one-AO slot;
  * SCD4x / SGP4x / BME688 / MICS-6814 are SMD parts: they only exist as
    plug-in modules when somebody puts them on a carrier board.

So "one slot that fits everything" is not achievable. What *is* achievable is a
documented slot standard plus carriers, and a gate that proves a named module
fits the actual chamber. This file feeds `tools/verify_module_fit.py`.

MOUNTED POSE (blueprint 4.5): the receptacle is a vertical strip, so a module's
connector edge is horizontal and its card stands up like a card, plane parallel
to the flow (header line along Y). Read in that pose:

  card      (long, short) board outline
  edge      which card edge carries the connector:
              "long"  -> the card stands on its wide edge (low profile)
              "short" -> it stands on its narrow edge (long edge vertical -> tall)
              "flat"  -> the card lies parallel to the board (right-angle socket)
  conn      connector class + pin count
  ao        how many *analog outputs* the module presents (analog bank only)
  can       (diameter, length) of the sensing element where it protrudes out of
            the card plane. Its LENGTH is what an in-row pitch must clear; its
            diameter is what an aperture must cover. None -> flush module.
  can_off   mm from the connector edge to the sensing element's centre along the
            card's LONG axis. With edge="long" the long axis is horizontal, so
            this is the y-offset between the aperture and the header line; with
            edge="short" the long axis is vertical, so it is a height instead.

`basis` records how a number was obtained (as in sensor_data.py):
  "vendor"   a vendor datasheet/page states it
  "measured" measured on a physical sample with calipers
  "inferred" derived from a vendor photo/drawing by the author, NOT confirmed
Any entry with `unverified` fields cannot be signed off: the gate reports it as
MEASURE, and blueprint 14 lists it as an open item.
"""

SOCKET_STANDOFF = 8.5    # 2.54 mm female header: card's lower edge above the board
MIN_LATERAL_GAP = 2.0    # clearance we want between a can and the next card
WALL_GAP = 2.0           # clearance between the end of a row and the cavity wall


def _mq(name, card, src):
    """An MQ-family breakout: silver can, 4-pin 2.54 mm header on one edge."""
    return dict(name=name, lane="analog", form="card", card=card, t=1.6,
                edge="short", conn=("2.54 hdr", 4), ao=1,
                can=(19.0, 23.0), can_off=16.0, basis="vendor", src=src,
                unverified=["edge", "can_off"])


MODULES = {
    # ---- MQ family: the analog workhorses ---------------------------------
    # can = the MQ-x package: dia 19 +/-0.5, 23 +/-0.3 long, dia 9.5 mesh cap
    # (the gas INLET is that end face), 6 pins on a 4.5 mm circle.
    "MQ-135-openimpulse": _mq("MQ-135 (32x20)", (32.0, 20.0),
                              "openimpulse: board 32x20x24 mm"),
    "MQ-135-dilson": _mq("MQ-135 (32x22)", (32.0, 22.0),
                         "dilson/electronation: 32x22x27 mm"),
    "MQ-135-dhm": _mq("MQ-135 (36x24)", (36.0, 24.0),
                      "dhm-online: 36x24x25 mm"),
    "MQ-135-waveshare": _mq("MQ-135 (40x21)", (40.0, 21.0),
                            "waveshare: 40.0 x 21.0 mm"),
    "MQ-136": _mq("MQ-136 (32x22)", (32.0, 22.0),
                  "same breakout class as MQ-135; vendor board 32x22x27"),
    # ---- electrochemical ---------------------------------------------------
    "ZE03": dict(name="Winsen ZE03 (EC)", lane="analog", form="can", card=None,
                 t=0.0, edge=None, conn=("2.54 hdr", 5), ao=1, can=(23.5, 24.5),
                 can_off=0.0, basis="vendor",
                 src="winsen ZE03 page: d23.5 x 24.5 mm, 3V UART + Vout",
                 unverified=[]),
    # ---- NDIR --------------------------------------------------------------
    "MH-Z19C-PC": dict(name="MH-Z19C-PC (NDIR)", lane="analog", form="flat",
                       card=(38.8, 19.7), t=8.6, edge="flat", ao=1, can=None,
                       conn=("JST ZH 1.5 mm", 6), can_off=None,
                       basis="vendor",
                       src="reichelt 297318: 38.8x19.7x8.6 mm, JST ZH 6p",
                       unverified=["can_off"]),
    # ---- SMD parts: pluggable only as somebody's carrier -------------------
    "SCD40": dict(name="Sensirion SCD40/41 (SMD)", lane="digital", form="smd",
                  card=(10.1, 10.1), t=6.5, edge=None, conn=("SMD", 0), ao=0,
                  can=None, can_off=None, basis="vendor",
                  src="sensirion SCD4x: 10.1x10.1x6.5 mm SMD", unverified=[]),
    "SGP40": dict(name="Sensirion SGP40/41 (SMD)", lane="digital", form="smd",
                  card=(2.45, 2.45), t=0.85, edge=None, conn=("SMD", 0), ao=0,
                  can=None, can_off=None, basis="vendor",
                  src="sensirion SGP4x: 2.45x2.45x0.85 mm DFN", unverified=[]),
    "BME688": dict(name="Bosch BME688 (SMD)", lane="digital", form="smd",
                   card=(3.0, 3.0), t=0.93, edge=None, conn=("SMD", 8), ao=0,
                   can=None, can_off=None, basis="vendor",
                   src="bosch BME688: 3.0x3.0x0.93 mm LGA", unverified=[]),
    "MICS-6814": dict(name="SGX MICS-6814 (SMD, 3 outputs)", lane="analog",
                      form="smd", card=(5.5, 7.5), t=2.55, edge=None,
                      conn=("SMD", 10), ao=3, can=None, can_off=None,
                      basis="vendor",
                      src="SGX 1143 rev 8: cavity 5.5x7.5x2.55 mm, 10 terminals",
                      unverified=[]),
    # ---- vendor breakouts whose shape is published -------------------------
    "STEMMA-QT": dict(name="Adafruit STEMMA QT board", lane="digital",
                      form="card", card=(25.4, 17.8), t=4.6, edge="long", ao=0,
                      conn=("0.1 in (2.54) holes + JST SH 1.0 mm", 4), can=None,
                      can_off=None, basis="vendor",
                      src="adafruit: 1.0 x 0.7 in board, STEMMA QT + 0.1in holes",
                      unverified=["edge", "can_off"]),
}

# The modules blueprint 4.4 actually promises. The gate is strict about these.
STARTER_PACK = ["MQ-135-openimpulse", "MQ-136", "MICS-6814", "ZE03", "SCD40"]


# ---------------------------------------------------------------------------
# what the chamber gives a module
# ---------------------------------------------------------------------------
def limits(const, n_rows=4):
    """Clearances a module must live inside, from the geometry constants."""
    lane = {}
    for bank, x0, sx, sy, y0 in (("analog", "A_X", "A_SX", "A_SY", "A_Y0"),
                                 ("digital", "D_X", "D_SX", "D_SY", "D_Y0")):
        xs = const[x0]
        lane[bank] = dict(
            pitch=xs[1] - xs[0], n=len(xs), row=(min(xs), max(xs)),
            aperture=(const[sx], const[sy]), ap_y=(const[y0], const[y0] + const[sy]),
            row_y=const[y0] + const[sy] / 2.0)
    return dict(h_clear=const["BAFFLE_Z"] - const["FLOOR"],   # 37 mm to the plate
                recess=8.0, cavity_x=const["CX"], cavity_y=const["CY"],
                cavity_x_range=(const["WSIDE"], const["WSIDE"] + const["CX"]),
                cavity_z=(const["FLOOR"], const["BAFFLE_Z"]), lane=lane)


def mounted(m, lim):
    """Envelope of a module in the mounted pose, or None if it has no pose."""
    form = m["form"]
    if form == "smd":
        return None
    if form == "can":                       # a cylinder sitting on a socket
        return dict(height=SOCKET_STANDOFF + m["can"][1], across=m["can"][0],
                    along_flow=m["can"][0], long_axis="vertical")
    l, w = m["card"]
    k = 0.0 if not m["can"] else m["can"][1]
    if form == "flat":                      # card lies parallel to the board
        return dict(height=m["t"] + k, across=m["can"][0] if m["can"] else l,
                    along_flow=l, long_axis="horizontal")
    if m["edge"] == "short":                # stands on its narrow edge -> tall
        return dict(height=SOCKET_STANDOFF + l, across=m["t"] + k,
                    along_flow=w, long_axis="vertical")
    if m["edge"] == "long":                 # stands on its wide edge -> low
        return dict(height=SOCKET_STANDOFF + w, across=m["t"] + k,
                    along_flow=l, long_axis="horizontal")
    return None


def check(key, const):
    """Per-module verdict: FITS | CARRIER | CONFLICT | MEASURE + notes."""
    m, lim = MODULES[key], limits(const)
    notes, hard, measure = [], False, False
    lane = lim["lane"][m["lane"]]
    env = mounted(m, lim)

    # 1. can this module present a 2.54 mm male header at all?
    pluggable = "2.54" in m["conn"][0] and m["form"] != "smd"
    if not pluggable:
        notes.append("connector %s / %s: needs a carrier or pigtail"
                     % (m["conn"][0], m["form"]))
        return "CARRIER", notes

    # 2. analog output count: one analog slot reads ONE AO
    if m["lane"] == "analog" and m.get("ao", 1) > 1:
        notes.append("has %d analog outputs; the analog slot reads 1 - needs a "
                     "summing carrier or %d slots" % (m["ao"], m["ao"]))
        hard = True

    # 3. height under the baffle plate
    if env:
        top = env["height"]
        notes.append("height above board %.1f mm (plate is %.1f mm up, spec "
                     "leaves a %.1f mm recess)" % (top, lim["h_clear"], lim["recess"]))
        risky = top > lim["h_clear"] - lim["recess"]
        bad = top > lim["h_clear"]
        if bad:
            notes.append("COLLIDES with the plate" if m["basis"] == "measured"
                         else "would COLLIDE with the plate")
        elif risky:
            notes.append("leaves only %.1f mm of the %.1f mm sensor recess"
                         % (lim["h_clear"] - top, lim["recess"]))
        if (bad or risky) and "edge" in m["unverified"]:
            measure = True
            notes.append("depends on which card edge carries the connector - "
                         "unverified, measure a sample")
        elif bad:
            hard = True

        # 4. in-row pitch: a sideways can must clear the next card
        gap = lane["pitch"] - env["across"]
        if gap < MIN_LATERAL_GAP:
            notes.append("lateral %.1f mm in a %.0f mm pitch -> %.1f mm gap "
                         "(want >= %.1f)" % (env["across"], lane["pitch"], gap,
                                             MIN_LATERAL_GAP))
            if gap < 0:
                hard = True

        # 5. row extremes: with one-sided cans the chain must stay inside the walls
        x0, x1 = lane["row"]
        cx0, cx1 = lim["cavity_x_range"]
        if m["form"] == "card" and (x0 - env["across"] < cx0 + WALL_GAP
                                    or x1 + env["across"] > cx1 - WALL_GAP):
            notes.append("one-sided cans would reach x=%.1f..%.1f; the cavity is "
                         "x=%.1f..%.1f - the end modules' cans must point inward"
                         % (x0 - env["across"], x1 + env["across"], cx0, cx1))

        # 6. aperture alignment: is the window over the sensing element?
        if m["can"]:
            if env["long_axis"] == "horizontal" and m.get("can_off"):
                notes.append("sensing element sits %.0f mm downstream of the header "
                             "line; the aperture is centred ON it -> offset the "
                             "aperture or the window misses the sensor"
                             % m["can_off"])
            elif env["long_axis"] == "vertical":
                notes.append("sensing element is centred on the header line: "
                             "aperture centring is right")
            notes.append("aperture %gx%g mm vs a %.1f mm element: %s"
                         % (lane["aperture"][0], lane["aperture"][1],
                            m["can"][0],
                            "window is smaller than the element (acts as a shroud)"
                            if m["can"][0] > lane["aperture"][1]
                            else "window is larger than the element"))
    if measure and not hard:
        return "MEASURE", notes
    return ("CONFLICT" if hard else "FITS"), notes


def report(const):
    return [(k,) + check(k, const) for k in sorted(MODULES)]


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from constants import CONST
    for key, verdict, notes in report(CONST):
        print("%-20s %-9s %s" % (key, verdict, "; ".join(notes)))
