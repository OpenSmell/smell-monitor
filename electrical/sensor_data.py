#!/usr/bin/env python3
"""OpenSmell sensor database (single source of physical sensor facts).

This is the *factual* layer: every market sensor we would consider, with the
numbers a rigorous array decision needs -- detection range, primary vs
cross-response, transduction principle, power, size, cost, and a source note.
It is deliberately kept separate from `sensor_matrix.py` (which owns the
coarse axis/persona/set-cover logic) and from `orthogonality.py` (which owns
the information analysis).

PROVENANCE -- WHAT IS DATA AND WHAT IS ESTIMATE (read before trusting a number)
------------------------------------------------------------------------------
* `profile` values are **interpretive compressions**, not datasheet numbers
  copied verbatim. A datasheet gives sensitivity curves (Rs-ratio or nA/ppm vs
  ppm) and sometimes a cross-sensitivity table; the 0.0-1.0 entries below are a
  hand-normalised summary of that shape. `basis="datasheet"` means such a table
  exists to anchor the shape; `basis="inferred"` means the shape is a
  principle/literature estimate. BOTH are approximations, not measurements.
* `src` is a **human note** -- it names the part and what its stated range or
  cross-sensitivity table says. `source` is the **cited document** for the
  product line (see `SOURCES`); every row carries one and the verify gate
  rejects `UNSOURCED`. `source` is family-level for now; tighten to a
  part+revision string when a profile is re-derived verbatim from one table.
* `gases` ranges are the datasheet detection ranges and ARE taken as stated.
* Because profiles are estimates, every downstream metric is re-run under
  x[0.7,1.3] jitter (`orthogonality.py --perturb`); conclusions that do not
  survive it are not load-bearing.
* `profile` keys MUST be a subset of `GASES`; a key outside is silently dropped
  by `orthogonality.matrix`, so `tools/verify_sensor_matrix.py` hard-fails on it.

WHY A SECOND, FINER ANALYSIS EXISTS
-----------------------------------
`sensor_matrix.py` answers "does *some* module touch each coarse axis?" -- a
coverage question. That is necessary but not sufficient: it cannot tell a
broad cross-sensitive MOX (MQ-135) from a selective NDIR (SCD40), and it
cannot tell two near-identical sensors apart, so it happily calls redundant
channels "coverage".

The real figure of merit for an array is *response diversity* across the
analyte space, i.e. the geometry of the response matrix R[sensor][gas]. Two
sensors whose rows are nearly parallel add almost no information regardless
of how many "axes" they nominally touch. `orthogonality.py` works on the
`profile` data below.

WHAT THE LITERATURE ACTUALLY SAYS (it is mixed -- the count is task-specific)
  * Pruning helps when channels are REDUNDANT:
      - Ren et al., ISOEN 2026, doi:10.1109/ISOEN68725.2026.11665159:
        13 -> 5 sensors raised classification 83.59% -> 89.69%.
      - Kong et al., Sensors 2025, doi:10.3390/s25051480 (PMC11902490):
        6 SnO2 MEMS, ReliefF-ranked; the 4 best beat all 6; extra hurt.
      - Oyster cold-chain, Sensors 2025 (PMC12730598): 10 (TGS+MQ) -> 5-6
        sensors, >40% redundancy removed, accuracy still >93%.
      - Sens. Actuators B 2024 (S0925400524003083): 8 -> 4, acc 0.905.
  * Adding sensors helps when the added channels are ORTHOGONAL, or when they
    average the noise of a single noisy channel:
      - PLOS One 2023, doi:10.1371/journal.pone.0295703: replicating each of
        6 heterogeneous types x5 raised accuracy 98.08% -> 99.78% (noise
        averaging, NOT new information).
      - Cyranose 320 ships 32 polymer sensors; the array is *deliberately*
        redundant and prunes at run time.
  => Sensor count and redundancy are different things. The right number is a
     per-task property set by the response-matrix rank vs the cost/heat/volume
     of a channel -- which is exactly what `orthogonality.py` computes.

ENCODING CONVENTIONS
  * profile: {gas: strength in [0,1]}, strength normalised to that sensor's
    strongest documented gas. 1.0 = calibrated/primary target. Values are
    taken from datasheets where a sensitivity curve or cross-sensitivity
    table exists; otherwise they are a literature/principle-based estimate
    and the sensor's `basis` field says which. This is stated honestly so the
    analysis can be re-run under uncertainty (see orthogonality.py --perturb).
  * gases: {gas: (lo, hi)} detection range in ppm (%RH / degC for the
    covariates). Used to reject a sensor at the analyte's reference level.
  * slot/iface/axes/power/cost/footprint match the sensor_matrix contract.
"""

# --- coarse axes (design descriptors; consumed by sensor_matrix.py) ---------
AXES = {
    "reducing":    "reducing gases: H2, CO, CH4, HCs, general VOCs (SnO2 redox)",
    "oxidising":   "oxidising gases: NO2, O3",
    "sulfur":      "sulfur volatiles: H2S, mercaptans, DMS/DMDS (protein/garlic)",
    "amine":       "amines/ammonia: NH3, TMA, cadaverine (protein spoilage)",
    "ir_active":   "IR-absorbing species: CO2 (4.26um), CH4",
    "voc_total":   "broad total-VOC / odour intensity",
    "ethylene":    "ethylene (fruit ripening / cold chain)",
    "alcohol":     "ethanol/methanol (fermentation, breath)",
    "humidity":    "relative humidity (covariate + compensation)",
    "temperature": "temperature (covariate + compensation)",
}

# --- fine analyte space (orthogonality dimensions) --------------------------
# ref = reference level the sensor must see to contribute (from use-case lit).
GASES = {
    "ammonia":    dict(ref=50,    unit="ppm", note="protein/TVB-N spoilage; MQ-135 calibrant"),
    "tma":        dict(ref=10,    unit="ppm", note="trimethylamine, fish spoilage (FAO)"),
    "h2s":        dict(ref=10,    unit="ppm", note="H2S, protein/sulfur spoilage"),
    "mercaptan":  dict(ref=5,     unit="ppm", note="methyl mercaptan, sulfur volatile"),
    "ethanol":    dict(ref=50,    unit="ppm", note="fermentation / breath / spoilage"),
    "methanol":   dict(ref=50,    unit="ppm", note="fermentation by-product"),
    "acetone":    dict(ref=50,    unit="ppm", note="ketosis breath, spoilage ketone"),
    "toluene":    dict(ref=10,    unit="ppm", note="VOC/odour proxy"),
    "co2":        dict(ref=2000,  unit="ppm", note="respiration/fermentation; NDIR 4.26um"),
    "ethylene":   dict(ref=10,    unit="ppm", note="fruit ripening / cold chain"),
    "co":         dict(ref=50,    unit="ppm", note="combustion; heme catabolism"),
    "no2":        dict(ref=1,     unit="ppm", note="oxidising gas, air quality"),
    "o3":         dict(ref=0.2,   unit="ppm", note="oxidising gas, air quality"),
    "so2":        dict(ref=5,     unit="ppm", note="sulfur dioxide; wine/dried fruit, indoor air"),
    "hcho":       dict(ref=1,     unit="ppm", note="formaldehyde, wood/indoor VOC"),
    "h2":         dict(ref=100,   unit="ppm", note="fermentation headspace"),
    "methane":    dict(ref=1000,  unit="ppm", note="anaerobic decomposition"),
    "humidity":   dict(ref=60,    unit="%RH", note="covariate / compensation"),
    "temperature":dict(ref=25,    unit="degC",note="covariate / compensation"),
}


# --- citable documents ------------------------------------------------------
# One reference per product line. `source` is auto-attached to every record by
# name prefix so each row points at a real document; `basis` says how the
# profile was derived from it. Family-level (not per-revision) for now; refine
# to a part+revision string when a profile is re-derived verbatim.
# Part-level citations for sensors whose exact document we have verified.
# Checked before the family prefix in `_source_for`.
SOURCE_OVERRIDE = {
    "MQ-7":      "Hanwei MQ-7 datasheet (laskakit.cz/user/related_files/mq-7.pdf; hwsensor.com)",
    "MQ-135":    "Winsen MQ135 Manual Ver1.6 (winsen-sensor.com/d/files/manual/mq135.pdf)",
    "MQ-136":    "Winsen MQ136 Manual Ver1.6 (winsen-sensor.com/d/files/mq136-(ver1_6)---manual.pdf)",
    "MICS-2714": "SGX MiCS-2714 Datasheet 1107 rev 6 (sgxsensortech.com, 2014)",
    "MICS-6814": "SGX MiCS-6814 Datasheet 1143 rev 8 (sgxsensortech.com, 2015)",
    "ZE03-C2H4": "Winsen ZE03 Electrochemical Module Manual V2.8 (winsen-sensor.com)",
    "SCD40":     "Sensirion SCD4x Datasheet Ver1.5 (sensirion.com, doc 48C4B7FB)",
    "CO-A4":     "Alphasense CO-A4 datasheet, Doc. Ref. CO-A4 (alphasense.com)",
    "H2S-A4":    "Alphasense H2S-A4 datasheet, Doc. Ref. H2S-A4/SEPT19 (alphasense.com)",
    "NO2-B43F":  "Alphasense NO2-B43F datasheet, Doc. Ref. NO2-B43F/JUL19 (alphasense.com)",
}

SOURCES = {
    "MQ-":     "Hanwei/Winsen MQ-series datasheet (winsen-sensor.com, 'MQ manual')",
    "TGS":     "Figaro TGS-series datasheet (figarosensor.com product page)",
    "ZE03":    "Winsen ZE03-series datasheet, ver 1.x (winsen-sensor.com)",
    "ME3":     "Winsen ME3-series electrochemical datasheet (winsen-sensor.com)",
    "MICS":    "Amphenol SGX MICS-series datasheet (sgxsensortech.com)",
    "SGP":     "Sensirion SGP4x datasheet (sensirion.com)",
    "SCD":     "Sensirion SCD4x datasheet (sensirion.com)",
    "BME":     "Bosch Sensortec BME688 datasheet (bosch-sensortec.com)",
    "ZMOD":    "Renesas ZMOD44xx/ZMOD45xx datasheet (renesas.com)",
    "ENS":     "ScioSense ENS160 datasheet (sciosense.com)",
    "CCS":     "ams OSRAM CCS811 datasheet (ams-osram.com)",
    "NO2-":    "Alphasense NO2-B43F datasheet, Doc. Ref. NO2-B43F/JUL19 (alphasense.com)",
    "CO-":     "Alphasense CO-A4 datasheet, Doc. Ref. CO-A4 (alphasense.com)",
    "H2S-":    "Alphasense H2S-A4 datasheet, Doc. Ref. H2S-A4/SEPT19 (alphasense.com)",
    "NH3-":    "Alphasense NH3-A4 datasheet, Doc. Ref. NH3-A4 (alphasense.com)",
    "O3-":     "Alphasense OX-B431 datasheet (alphasense.com)",
    "SO2-":    "Alphasense SO2-A4 datasheet (alphasense.com)",
    "MiniPID": "Ion Science MiniPID 2 datasheet (ionscience.com)",
    "MH-Z19":  "Winsen MH-Z19C datasheet (winsen-sensor.com)",
    "Sensair": "Cubic Sensair S8 datasheet (cubic-sensor.com)",
    "SHT":     "Sensirion SHT3x datasheet (sensirion.com)",
}


def _source_for(name):
    if name in SOURCE_OVERRIDE:
        return SOURCE_OVERRIDE[name]
    for prefix, ref in SOURCES.items():
        if name.startswith(prefix):
            return ref
    return "UNSOURCED"


# --- how strong a claim the `profile` shape actually is ----------------------
# A datasheet rarely publishes a cross-sensitivity *table*. Sorting the pool by
# what the document really contains is the honest provenance, so a reviewer can
# see at a glance which rows are quantitative:
#   table    -- a numeric cross-sensitivity / response-factor table exists
#               (Alphasense electrochemical cells, Ion Science MiniPID).
#   curve    -- a multi-gas sensitivity curve exists; relative shape is readable
#               but not tabulated (MOX: MQ, TGS, MICS).
#   list     -- only a qualitative "sensitive to ..." gas list and/or the
#               detection range is stated (Winsen ZE03/ME3, NDIR, SGP VOC).
#   inferred -- no selectivity data in the document; principle/literature guess.
_TABLE_FAMILIES = ("NO2-", "CO-", "H2S-", "NH3-", "O3-", "SO2-", "MiniPID")
_CURVE_FAMILIES = ("MQ-", "TGS", "MICS")


def _basis_for(name, stated):
    if stated == "inferred":
        return "inferred"
    if name.startswith(_TABLE_FAMILIES):
        return "table"
    if name.startswith(_CURVE_FAMILIES):
        return "curve"
    return "list"


def _s(name, mfr, principle, iface, slot, foot, power, cost, axes,
       profile, gases, basis, src, inferred=()):
    """Assemble one sensor record; keep field order stable for diffs.

    `inferred` names the profile keys that are NOT backed by this sensor's
    datasheet (chemistry/literature guesses) so a `basis="table"` row can still
    flag its un-sourced entries instead of hiding them.
    """
    return dict(name=name, mfr=mfr, principle=principle, iface=iface,
                slot=slot, footprint=foot, power=power, cost=cost, axes=axes,
                profile=profile, gases=gases, basis=_basis_for(name, basis),
                src=src, source=_source_for(name), inferred=list(inferred))


# profile strengths: 1.0 primary, ~0.6 documented secondary, ~0.25 inferred
# broad MOX response, ~0 for a documented near-zero cross-sensitivity.
SENSORS = [
    # ---- Winsen / Hanwei MQ series (MOX, 5V analog) -----------------------
    _s("MQ-2", "Hanwei", "MOX", "analog", "analog", (22, 16), 900, 2,
       ["reducing"],
       {"methane": 1.0, "h2": 0.7, "co": 0.5, "ethanol": 0.4},
       {"methane": (300, 10000), "h2": (300, 5000), "ethanol": (100, 2000)},
       "datasheet",
       "Hanwei/Winsen MQ-2: flammable gas 300-10000ppm, sensitivity to "
       "propane/smoke/natural gas; curve gases H2,LPG,CH4,CO,alcohol,smoke,"
       "propane (Ro@1000ppm H2)"),
    _s("MQ-3", "Hanwei", "MOX", "analog", "analog", (22, 16), 900, 2,
       ["alcohol", "reducing"],
       {"ethanol": 1.0, "methanol": 0.5, "methane": 0.2, "co": 0.2},
       {"ethanol": (20, 2000)},
       "datasheet",
       "Hanwei MQ-3: alcohol 0.04-4mg/L (~20-2000ppm, cal 0.4mg/L~200ppm); "
       "curve gases alcohol,benzine,CH4,hexane,LPG,CO",
       inferred=("methanol",)),
    _s("MQ-7", "Hanwei", "MOX", "analog", "analog", (22, 16), 900, 2,
       ["reducing"],
       {"co": 1.0, "h2": 0.5, "methane": 0.3, "ethanol": 0.25},
       {"co": (20, 2000)},
       "datasheet",
       "Hanwei MQ-7: CO 20-2000ppm (cycled 5V/1.4V heater); curve gases "
       "CO,H2,LPG,CH4,alcohol; Ro at 100ppm CO"),
    _s("MQ-8", "Hanwei", "MOX", "analog", "analog", (22, 16), 900, 2,
       ["reducing"],
       {"h2": 1.0, "co": 0.3, "methane": 0.3, "ethanol": 0.2},
       {"h2": (100, 1000)},
       "datasheet",
       "Winsen MQ-8 ver1.6: H2 100-1000ppm (older Hanwei rev 100-10000); curve "
       "gases H2,LPG,CH4,CO,alcohol (Ro@1000ppm H2)"),
    _s("MQ-9", "Hanwei", "MOX", "analog", "analog", (22, 16), 900, 2,
       ["reducing"],
       {"co": 1.0, "methane": 0.7, "h2": 0.4},
       {"co": (10, 1000), "methane": (300, 10000), "h2": (500, 10000)},
       "datasheet",
       "Hanwei/Winsen MQ-9: CO/CH4/LPG/H2 combustibles; CO 10-1000ppm, "
       "CH4 300-10000ppm"),
    _s("MQ-131", "Winsen", "MOX", "analog", "analog", (22, 16), 900, 4,
       ["oxidising"],
       {"o3": 1.0, "no2": 0.4},
       {"o3": (0.01, 1.0)},
       "datasheet",
       "Winsen MQ-131-L low-conc: O3 10-1000ppb (high-conc variant 10-1000ppm); "
       "strong sensitivity to oxides Cl2,NO2 (o3 1.0, no2 0.4)"),
    _s("MQ-135", "Hanwei", "MOX", "analog", "analog", (22, 16), 900, 2,
       ["amine", "reducing", "voc_total", "alcohol"],
       {"ammonia": 1.0, "toluene": 0.8, "acetone": 0.7, "ethanol": 0.6,
        "co": 0.4, "co2": 0.3, "h2s": 0.3},
       {"ammonia": (10, 300), "toluene": (10, 1000), "ethanol": (10, 300)},
       "curve",
       "Winsen MQ135 Ver1.6: Rs(air)/Rs(400ppm H2)>=5; range 10-1000ppm NH3/toluene/H2/smoke; "
       "curve gases NH3,sulfide,toluene,acetone,CO,CO2 (Hanwei variant calibrates 100ppm NH3)"),
    _s("MQ-136", "Winsen", "MOX", "analog", "analog", (22, 16), 950, 3,
       ["sulfur"],
       {"h2s": 1.0, "mercaptan": 0.6, "co": 0.35},
       {"h2s": (1, 200), "mercaptan": (1, 100)},
       "curve",
       "Winsen MQ136 Ver1.6: Rs(air)/Rs(50ppm H2S)>=3; range 1-200ppm H2S; "
       "curve gases H2S,CO + 'organic vapour incl. sulfur' (no H2/toluene claim)"),
    _s("MQ-137", "Winsen", "MOX", "analog", "analog", (22, 16), 950, 3,
       ["amine"],
       {"ammonia": 1.0, "tma": 0.6, "mercaptan": 0.25},
       {"ammonia": (5, 500), "tma": (5, 500)},
       "datasheet", "Winsen MQ137: NH3/amine, 5-500ppm"),
    _s("MQ-138", "Winsen", "MOX", "analog", "analog", (22, 16), 950, 3,
       ["voc_total", "reducing"],
       {"toluene": 1.0, "ethanol": 0.6, "acetone": 0.6, "hcho": 0.4, "h2": 0.3},
       {"toluene": (5, 500)},
       "datasheet",
       "Winsen MQ-138: toluene/acetone/alcohol/H2, 5-500ppm VOC; high sens to "
       "toluene/acetone/EtOH/HCHO (Ro@50ppm toluene)"),
    # ---- Figaro TGS series (MOX, 5V analog) -------------------------------
    _s("TGS2600", "Figaro", "MOX", "analog", "analog", (9, 9), 210, 5,
       ["reducing"],
       {"h2": 1.0, "co": 0.8, "ethanol": 0.5, "methane": 0.5},
       {"h2": (1, 30), "co": (1, 30)},
       "datasheet",
       "Figaro TGS2600: 1-30ppm H2; Rs 0.3-0.6@10ppm H2"),
    _s("TGS2602", "Figaro", "MOX", "analog", "analog", (9, 9), 280, 6,
       ["amine", "sulfur", "voc_total"],
       {"ammonia": 1.0, "h2s": 0.8, "toluene": 0.7, "ethanol": 0.6, "h2": 0.5},
       {"ethanol": (1, 30), "ammonia": (1, 30)},
       "datasheet",
       "Figaro TGS2602: 1-30ppm EtOH; NH3/H2S/toluene/H2"),
    _s("TGS2603", "Figaro", "MOX", "analog", "analog", (9, 9), 240, 6,
       ["amine", "sulfur"],
       {"tma": 1.0, "mercaptan": 0.9, "h2s": 0.7, "h2": 0.4, "ethanol": 0.4},
       {"tma": (1, 10), "mercaptan": (1, 10), "h2s": (1, 10)},
       "datasheet",
       "Figaro TGS2603: TMA/methyl mercaptan/H2S; 1-10ppm EtOH"),
    _s("TGS2620", "Figaro", "MOX", "analog", "analog", (9, 9), 210, 5,
       ["alcohol", "voc_total"],
       {"ethanol": 1.0, "methanol": 0.7, "acetone": 0.6, "toluene": 0.5},
       {"ethanol": (50, 5000)},
       "datasheet",
       "Figaro TGS2620 Product Info rev: alcohol/solvent, 50-5000ppm EtOH; "
       "curve characterises ethanol only",
       inferred=("methanol", "acetone", "toluene")),
    _s("TGS826", "Figaro", "MOX", "analog", "analog", (9, 9), 210, 6,
       ["amine"],
       {"ammonia": 1.0, "tma": 0.5},
       {"ammonia": (10, 300)},
       "datasheet",
       "Figaro TGS826 Product Info rev01: ammonia 10-300ppm; curve gases "
       "isobutane/H2/NH3/ethanol",
       inferred=("tma",)),
    # ---- Winsen ZE03 electrochemical (5V module, analog Vout) -------------
    _s("ZE03-NH3", "Winsen", "Electrochemical", "analog", "analog", (24, 25), 30, 15,
       ["amine"],
       {"ammonia": 1.0, "tma": 0.3},
       {"ammonia": (0, 100)},
       "datasheet", "Winsen ZE03: NH3 0-100ppm, res 1ppm, T90<=150s"),
    _s("ZE03-H2S", "Winsen", "Electrochemical", "analog", "analog", (24, 25), 30, 15,
       ["sulfur"],
       {"h2s": 1.0, "mercaptan": 0.4},
       {"h2s": (0, 100)},
       "datasheet", "Winsen ZE03: H2S 0-100ppm, res 1ppm, T90<=30s"),
    _s("ZE03-C2H4", "Winsen", "Electrochemical", "analog", "analog", (24, 25), 30, 20,
       ["ethylene"],
       {"ethylene": 1.0},
       {"ethylene": (0, 100)},
       "list", "Winsen ZE03 V2.8: C2H4 0-100ppm, res 0.1ppm, Vout 0.6-3V, T90<=30s; "
       "no cross-sensitivity table published"),
    _s("ZE03-CO", "Winsen", "Electrochemical", "analog", "analog", (24, 25), 30, 15,
       ["reducing"],
       {"co": 1.0, "h2": 0.3},
       {"co": (0, 1000)},
       "datasheet", "Winsen ZE03: CO 0-1000ppm, res 1ppm, T90<=30s"),
    _s("ZE03-NO2", "Winsen", "Electrochemical", "analog", "analog", (24, 25), 30, 20,
       ["oxidising"],
       {"no2": 1.0, "o3": 0.3},
       {"no2": (0, 20)},
       "datasheet", "Winsen ZE03: NO2 0-20ppm, res 0.1ppm, T90<=30s"),
    _s("ZE03-O3", "Winsen", "Electrochemical", "analog", "analog", (24, 25), 30, 20,
       ["oxidising"],
       {"o3": 1.0, "no2": 0.4},
       {"o3": (0, 10)},
       "datasheet", "Winsen ZE03: O3 0-10ppm, res 0.1ppm, T90<=120s"),
    _s("ZE03-SO2", "Winsen", "Electrochemical", "analog", "analog", (24, 25), 30, 20,
       ["oxidising"],
       {"so2": 1.0},
       {"so2": (0, 20)},
       "datasheet", "Winsen ZE03: SO2 0-20ppm, res 0.1ppm, T90<=30s"),
    _s("ZE03-HCHO", "Winsen", "Electrochemical", "analog", "analog", (24, 25), 30, 20,
       ["voc_total"],
       {"hcho": 1.0},
       {"hcho": (0, 50)},
       "datasheet", "Winsen ZE03: HCHO 0-50ppm, res 0.1ppm, T90<=30s"),
    _s("ME3-C2H5OH", "Winsen", "Electrochemical", "analog", "analog", (20, 20), 25, 12,
       ["alcohol"],
       {"ethanol": 1.0, "methanol": 0.5},
       {"ethanol": (0, 500)},
       "inferred", "Winsen ME3-C2H5OH electrochemical ethanol cell (needs bias+amp)"),
    # ---- Amphenol SGX MICS (MOX, 5V analog) -------------------------------
    _s("MICS-6814", "SGX", "MOX", "analog", "analog", (10, 10), 500, 12,
       ["reducing", "oxidising", "amine"],
       {"co": 1.0, "no2": 0.9, "ammonia": 0.8, "ethanol": 0.4, "h2": 0.4,
        "methane": 0.3, "h2s": 0.3},
       {"co": (1, 1000), "no2": (0.05, 10), "ammonia": (1, 500),
        "methane": (1000, 10000)},
       "curve",
       "SGX MiCS-6814 rev8 3-in-1 (OX/RED/NH3 elements); CO 1-1000, NO2 0.05-10, "
       "C2H5OH 10-500, H2 1-1000, NH3 1-500, CH4>1000; RED curve also H2S"),
    _s("MICS-2714", "SGX", "MOX", "analog", "analog", (5, 7), 300, 8,
       ["oxidising"],
       {"no2": 1.0, "h2": 0.6},
       {"no2": (0.05, 10), "h2": (1, 1000)},
       "datasheet",
       "SGX MiCS-2714 1107 rev6: NO2 0.05-10ppm, H2 1-1000ppm; curve also NO "
       "(NO not in GASES); no O3 selectivity published"),
    _s("MICS-5524", "SGX", "MOX", "analog", "analog", (5, 7), 400, 8,
       ["reducing"],
       {"co": 1.0, "h2": 0.6, "ethanol": 0.4, "methane": 0.3, "ammonia": 0.3},
       {"co": (1, 1000), "h2": (1, 1000), "ethanol": (10, 500),
        "ammonia": (1, 500)},
       "datasheet",
       "SGX MiCS-5524 1084 rev8 RED: CO 1-1000, H2 1-1000, EtOH 10-500, "
       "NH3 1-500, CH4>1000ppm; curve also propane,iso-butane,H2S"),
    # ---- Sensirion CMOS (MOX VOC, 3V3 I2C digital) ------------------------
    _s("SGP40", "Sensirion", "MOX", "i2c", "digital", (3, 3), 48, 5,
       ["voc_total"],
       {"ethanol": 1.0, "toluene": 0.6, "acetone": 0.6, "methanol": 0.5},
       {"ethanol": (0.3, 30)},
       "datasheet",
       "Sensirion SGP40 VOC-index (ethanol+RH referenced); non-ethanol "
       "contributions inferred; I2C 0x59",
       inferred=("toluene", "acetone", "methanol")),
    _s("SGP41", "Sensirion", "MOX", "i2c", "digital", (3, 3), 52, 6,
       ["voc_total", "oxidising"],
       {"ethanol": 1.0, "toluene": 0.6, "acetone": 0.6, "no2": 0.7, "o3": 0.5},
       {"ethanol": (0.5, 10), "no2": (0.05, 0.65)},
       "datasheet",
       "Sensirion SGP41 VOC+NOx index (ethanol & NO2 referenced); VOC-organics "
       "and O3 inferred; I2C 0x59",
       inferred=("toluene", "acetone", "o3")),
    _s("SGP30", "Sensirion", "MOX", "i2c", "digital", (3, 3), 48, 6,
       ["voc_total"],
       {"ethanol": 1.0, "toluene": 0.6, "h2": 0.5},
       {"ethanol": (0.3, 30)},
       "datasheet",
       "Sensirion SGP30 VOC (ethanol referenced) + eCO2 (derived, NOT NDIR); "
       "toluene/H2 contributions inferred",
       inferred=("toluene", "h2")),
    _s("SCD40", "Sensirion", "NDIR", "i2c", "digital", (10, 10), 15, 25,
       ["ir_active"],
       {"co2": 1.0},
       {"co2": (400, 2000)},
       "datasheet",
       "Sensirion SCD40 photoacoustic NDIR CO2 400-2000ppm; I2C 0x62"),
    # ---- Bosch / Renesas / AMS gas+environment (MOX, 3V3 I2C) -------------
    _s("BME688", "Bosch", "MOX", "i2c", "digital", (3, 3), 15, 10,
       ["voc_total", "humidity", "temperature"],
       {"ethanol": 1.0, "toluene": 0.6},
       {"ethanol": (0.3, 30)},
       "inferred",
       "Bosch BME688: gas (BSEC) + T/RH/P; VOC-index (no true CO2), I2C 0x76/0x77"),
    _s("ZMOD4410", "Renesas", "MOX", "i2c", "digital", (3, 3), 40, 6,
       ["voc_total"],
       {"ethanol": 1.0, "toluene": 0.6},
       {"ethanol": (0.3, 30)},
       "inferred", "Renesas ZMOD4410: TVOC + eCO2 (derived); I2C 0x32"),
    _s("ZMOD4510", "Renesas", "MOX", "i2c", "digital", (3, 3), 40, 6,
       ["oxidising"],
       {"no2": 1.0, "o3": 0.9},
       {"no2": (0.01, 1.0), "o3": (0.01, 1.0)},
       "inferred", "Renesas ZMOD4510: outdoor O3/NO2; I2C 0x33"),
    _s("ENS160", "ScioSense", "MOX", "i2c", "digital", (3, 3), 30, 8,
       ["voc_total", "oxidising"],
       {"ethanol": 1.0, "toluene": 0.6, "no2": 0.4},
       {"ethanol": (0.3, 30)},
       "inferred", "ScioSense ENS160: TVOC/eCO2(derived)/NOx/AQI; I2C 0x52/0x53"),
    _s("CCS811", "AMS", "MOX", "i2c", "digital", (3, 3), 30, 8,
       ["voc_total"],
       {"ethanol": 1.0, "toluene": 0.6},
       {"ethanol": (0.3, 30)},
       "inferred", "AMS CCS811: TVOC + eCO2 (derived); I2C 0x5A/0x5B"),
    # ---- Alphasense electrochemical (4-elec ppb; needs AFE, analog) -------
    _s("NO2-B43F", "Alphasense", "Electrochemical", "analog", "analog", (20, 17), 25, 25,
       ["oxidising"],
       {"no2": 1.0, "h2s": 0.8, "o3": 0.02, "so2": 0.03, "co": 0.03,
        "h2": 0.001, "ethylene": 0.001, "ammonia": 0.001,
        "co2": 0.001},
       {"no2": (0.005, 20)},
       "table",
       "Alphasense NO2-B43F/JUL19 cross-sens (% measured gas): H2S<-80@5ppm, "
       "Cl2<100@5ppm, SO2<-3@5ppm, CO<-3@5ppm, NO<5@5ppm, H2<0.1@100ppm, "
       "C2H4<0.1@100ppm, NH3<0.1@20ppm; O3 filtered (>500 ppm.hr); sens -200..-650 nA/ppm@2ppm"),
    _s("CO-A4", "Alphasense", "Electrochemical", "analog", "analog", (20, 17), 25, 25,
       ["reducing"],
       {"co": 1.0, "h2": 0.10, "no2": 0.02, "so2": 0.001},
       {"co": (0, 500)},
       "table",
       "Alphasense CO-A4 cross-sens (% measured gas): H2<10@100ppm, NO2<-2@5ppm, "
       "SO2<0.1@5ppm, H2S<0.1@5ppm, Cl2<0.1@5ppm, NO<-2@5ppm, C2H4<0.5@100ppm, "
       "NH3<0.1@20ppm; sens 220-375 nA/ppm@2ppm; range 0-500ppm"),
    _s("H2S-A4", "Alphasense", "Electrochemical", "analog", "analog", (20, 17), 25, 25,
       ["sulfur"],
       {"h2s": 1.0, "so2": 0.20, "no2": 0.10, "co": 0.03, "mercaptan": 0.5},
       {"h2s": (0, 50)},
       "table",
       "Alphasense H2S-A4 cross-sens (% measured gas): SO2<20@5ppm, NO2<-10@5ppm, "
       "Cl2<-12@5ppm, NO<12@5ppm, CO<3@5ppm, H2<0.5@100ppm, C2H4<0.1; "
       "sens 1400-1850 nA/ppm@2ppm; range 0-50ppm",
       inferred=("mercaptan",)),
    _s("NH3-A4", "Alphasense", "Electrochemical", "analog", "analog", (20, 17), 25, 25,
       ["amine"],
       {"ammonia": 1.0, "tma": 0.2},
       {"ammonia": (0, 100)},
       "table",
       "Alphasense NH3-A4: 0-100ppm NH3 (amine-class EC cell; tma not in datasheet)",
       inferred=("tma",)),
    _s("O3-B431", "Alphasense", "Electrochemical", "analog", "analog", (20, 17), 25, 25,
       ["oxidising"],
       {"o3": 1.0, "no2": 0.89, "h2s": 0.80, "so2": 0.03, "co": 0.03},
       {"o3": (0.005, 20)},
       "table",
       "Alphasense OX-B431 cross-sens (% measured gas): H2S<-80@5ppm, NO<5@5ppm, "
       "Cl2<100@5ppm, SO2<-3@5ppm, CO<-3@5ppm, H2<0.1@100ppm, C2H4<0.1, NH3<0.1; "
       "O3 sens -225..-750 nA/ppm@1ppm, NO2 -250..-750 nA/ppm@2ppm (dual-target)"),
    _s("SO2-A4", "Alphasense", "Electrochemical", "analog", "analog", (20, 17), 25, 25,
       ["oxidising"],
       {"so2": 1.0, "no2": 1.2, "o3": 1.2, "co": 0.03, "h2s": 0.02},
       {"so2": (0, 20)},
       "table",
       "Alphasense SO2-A4 cross-sens (% measured gas): NO2<-120@5ppm, O3<-120@0.5ppm, "
       "H2S<2@5ppm, Cl2<-80@5ppm, NO<-4@5ppm, CO<3@5ppm, H2<1@100ppm, C2H4<1, "
       "NH3<0.1; sens 320-480 nA/ppm@2ppm; range 0-20ppm"),
    # ---- PID (total VOC, ppb; analog) -------------------------------------
    _s("MiniPID", "Ion Science", "PID", "analog", "analog", (20, 20), 300, 120,
       ["voc_total"],
       {"toluene": 1.0, "acetone": 0.80, "ethanol": 0.06},
       {"toluene": (0.001, 100)},
       "table",
       "Ion Science MiniPID 2 (TA-02 response factors, 10.6 eV): RF isobutylene=1.0 "
       "(ref), toluene=0.56, acetone=0.70, ethanol~9; relative sens = 1/RF, "
       "normalised to toluene", inferred=("acetone", "ethanol")),
    # ---- NDIR CO2 modules (5V, analog Vout) -------------------------------
    _s("MH-Z19C", "Winsen", "NDIR", "analog", "analog", (33, 20), 100, 18,
       ["ir_active"],
       {"co2": 1.0},
       {"co2": (400, 5000)},
       "datasheet",
       "Winsen MH-Z19C: 5.0+/-0.1V, analog out 0.4-2V; CO2 400-5000ppm"),
    _s("Sensair-S8", "Cubic", "NDIR", "analog", "analog", (33, 20), 100, 20,
       ["ir_active"],
       {"co2": 1.0},
       {"co2": (400, 2000)},
       "datasheet", "Cubic Sensair S8: NDIR CO2 400-2000ppm, UART/PWM (Vout variant)"),
    # ---- base (soldered, master I2C, always present) ----------------------
    _s("SHT31", "Sensirion", "T/RH", "i2c", "base", (3, 3), 1, 4,
       ["humidity", "temperature"],
       {"humidity": 1.0, "temperature": 1.0},
       {"humidity": (0, 100), "temperature": (-40, 125)},
       "datasheet", "Sensirion SHT31 T/RH, I2C 0x44"),
]

BY_NAME = {s["name"]: s for s in SENSORS}
BASE_SENSORS = [s["name"] for s in SENSORS if s["slot"] == "base"]
