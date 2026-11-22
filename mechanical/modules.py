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

SETTLED POSE (docs/module-standard.md, OpenSmell Module Standard v1): cards are
mounted **flat** on a right-angle header in a vertical socket - sensing face up,
directly under the window, removed upward - and the socket is repeated on every
slot. The vertical pose modelled below is the *as-built* revision that predates
the standard; it is kept because its measurements are what settled the question
(a standing 32-40 mm card needs 40-48 mm where only 37 mm exists). Both poses
are reported, so the gate shows the closed case and the open one side by side.

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

`unverified` marks fields that a sample would settle.  It is provenance, not a
gate: the OSM-1 verdict only asks whether a part's sensing element fits the
cartridge envelope (or reaches the base through a Qwiic carrier), so the vendor
breakout's own pose no longer decides the answer.
"""

SOCKET_STANDOFF = 8.5    # 2.54 mm female header: card's lower edge above the board
MODULE_REACH = 32.0      # a cartridge extends this far from its pin line


def _mq(name, card, src, pins="VCC GND DO AO"):
    """An MQ-family breakout: silver can, 4-pin 2.54 mm header on one edge.
    `pins` is the module's OWN order, quoted from the vendor.  It is recorded
    (not enforced) because the OSM-1 cartridge re-houses the element and
    presents the standard `+5V GND AO DO 3V3 ID` order regardless."""
    return dict(name=name, lane="analog", form="card", card=card, t=1.6,
                edge="short", conn=("2.54 hdr", 4), ao=1, pins=pins,
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
    # (the MH-Z19C flat module is listed with the vendor breakouts below)
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
    # ---- carrier boards: what the SMD parts actually arrive on ------------
    "SCD41-dev": dict(name="Sensirion SEK-SCD41 board", lane="digital",
                      form="card", card=(28.0, 24.0), t=8.0, edge="short", ao=0,
                      conn=("0.1 in (2.54) holes", 4), can=None, can_off=None,
                      basis="vendor", unverified=["edge"],
                      src="sensirion SEK-SCD41 tech description: 28 x 24 x 8 mm"),
    "SCD40-adafruit": dict(name="Adafruit SCD-40 / STEMMA QT class", lane="digital",
                           form="card", card=(25.4, 17.8), t=4.6, edge="long",
                           ao=0,
                           conn=("0.1 in (2.54) holes + JST SH 1.0 mm", 4),
                           can=None, can_off=None, basis="vendor",
                           unverified=["edge"],
                           src="adafruit 5187: STEMMA QT form factor, 1.0 x 0.7 in"),
    "TGS2600": dict(name="Figaro TGS2600 (bare TO-5)", lane="analog", form="smd",
                    card=(9.2, 9.2), t=9.0, edge=None, conn=("TO-5, 4 leads", 4),
                    ao=1, can=None, can_off=None, basis="vendor",
                    unverified=["card"],
                    src="figaro/arrow: TGS2600 is a 4-lead TO-5 can - needs a "
                        "carrier with the load resistor and heater drive"),
    "DFRobot-Gravity": dict(name="DFRobot Gravity MQ-2 (SEN0127)", lane="analog",
                            form="card", card=(33.0, 22.0), t=1.6, edge="long",
                            ao=1, pins="VCC GND AOUT",
                            conn=("JST-PH 2.0 Gravity, 3-pin", 3),
                            can=(19.0, 23.0), can_off=None, basis="vendor",
                            unverified=["card", "edge", "can_off"],
                            src="dfrobot SEN0127: Gravity 3-pin (JST-PH 2.0) "
                                "interface, no 2.54 header"),
    # ---- vendor breakouts whose shape is published -------------------------
    "MH-Z19C": dict(name="Winsen MH-Z19C (NDIR)", lane="analog", form="flat",
                    card=(38.8, 19.7), t=8.6, edge="flat", ao=1,
                    conn=("JST ZH 1.5 mm", 6), can=None, can_off=None,
                    basis="vendor", unverified=["can_off"],
                    src="winsen MH-Z19C manual / reichelt 297318: 38.8 x 19.7 x "
                        "8.6 mm, 6-pin 1.5 mm JST-ZH"),
}

# The modules blueprint 4.4 actually promises. The gate is strict about these.
STARTER_PACK = ["MQ-135-openimpulse", "MQ-136", "MICS-6814", "ZE03", "SCD40"]


# ---------------------------------------------------------------------------
# OSM-1 conformance - how does this part get into a slot?
# ---------------------------------------------------------------------------
# The slot is uniform, so "fit" is a property of the *module*, not of a bank:
#
#   CONFORMS  a gas-cell card/can whose sensing element fits the cartridge
#             envelope (20 x 32 x 21 mm), or a native Qwiic I2C module
#   CARRIER   usable, but only after being built into an OSM-1 cartridge or a
#             Qwiic carrier board (bare SMD part, non-2.54 connector, a
#             vendor board larger than the cartridge envelope)
#
# Both are supported paths: the standard's purpose is to make the *slot*
# uniform, not to declare every vendor breakout plug-compatible.  A part with
# a CARRIER verdict is not an open question - it is a documented build step.
def check(key, const=None):
    """Verdict for one database entry against the OSM-1 standard."""
    import os
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import standard as S

    env = S.CARTRIDGE["envelope"]
    m = MODULES[key]
    notes = []

    # 1. a bare die/package is never a plug-in module
    if m["form"] == "smd":
        notes.append("bare SMD part %.1fx%.1f mm: build it onto an OSM-1 "
                     "cartridge or a Qwiic carrier"
                     % (m["card"][0], m["card"][1]))
        return "CARRIER", notes

    # 2. a native I2C module reaches the base through the Qwiic port, so the
    #    cartridge envelope does not apply to it
    conn = m["conn"][0].lower()
    if m["lane"] == "digital" and ("jst" in conn or "0.1 in" in conn):
        notes.append("I2C module: plugs into any slot's Qwiic port")
        return "CONFORMS", notes

    # 3. anything else must present a 2.54 mm edge for the gas-cell socket
    if "2.54" not in m["conn"][0]:
        notes.append("connector %s: needs an OSM-1 cartridge or Qwiic carrier"
                     % m["conn"][0])
        return "CARRIER", notes

    # 4. the sensing element must live inside the cartridge envelope
    if m["form"] == "can":
        across, along = m["can"]
        notes.append("can d%.1f x %.1f mm" % (across, along))
        if across > env["across"]:
            notes.append("wider than the %g mm cartridge - use a Qwiic carrier"
                         % env["across"])
            return "CARRIER", notes
    else:
        l, w = m["card"]
        across, along = min(l, w), max(l, w)
        notes.append("board %.0f x %.0f mm" % (l, w))
        if across > env["across"] or along > env["along"]:
            notes.append("outside the %gx%g mm envelope: re-house the element "
                         "on a cartridge" % (env["across"], env["along"]))
            return "CARRIER", notes

    # 5. one AO per slot: a multi-output part needs an on-carrier ADC
    if m["lane"] == "analog" and m.get("ao", 1) > 1:
        notes.append("%d analog outputs: needs a carrier with an ADC (Qwiic)"
                     % m["ao"])
        return "CARRIER", notes

    notes.append("footprint fits the %gx%g envelope; the cartridge lays the "
                 "element within %g mm" % (env["across"], env["along"],
                                           env["height"]))
    return "CONFORMS", notes


def report(const=None):
    return [(k,) + check(k) for k in sorted(MODULES)]


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    for key, verdict, notes in report():
        print("%-20s %-9s %s" % (key, verdict, "; ".join(notes)))
