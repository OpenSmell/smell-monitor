#!/usr/bin/env python3
"""Emit the OpenFOAM dictionaries for the v1.1 chamber case.

Kept as a generator so every number is written once, next to the geometry it
belongs to.  Run it from the repo root, then delete nothing: the dicts it
writes are the case, and they are committed.

    python3 cfd/make_case.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- the fluid volume, straight off mechanical/constants.py -----------------
X0, X1 = 3.0, 119.0
Y0, Y1 = 3.0, 111.0
Z0, Z1 = 8.6, 43.0
NX, NY, NZ = 58, 54, 17          # 2 mm cells; snappy refines to 1 mm

INLETS = [(35.0, 30.0), (61.0, 30.0), (87.0, 30.0)]   # x, z on y = Y0
OUTLET = (44.0, 78.0, Z0, 40.0)                        # x0, x1, z0, z1 on y = Y1
PAD = (6.0, 116.0, Y0, 7.0, 20.0, Z1)                  # x0,x1,y0,y1,z0,z1

PROBES = [
    ("A0", (22.0, 91.0, 40.5)), ("A1", (48.0, 91.0, 40.5)),
    ("A2", (74.0, 91.0, 40.5)), ("A3", (100.0, 91.0, 40.5)),
    ("D0", (29.5, 49.0, 40.5)), ("D1", (50.5, 49.0, 40.5)),
    ("D2", (71.5, 49.0, 40.5)), ("D3", (92.5, 49.0, 40.5)),
    ("bypass", (61.0, 15.0, 14.0)),      # under the filter pad
    ("outlet", (61.0, 105.0, 25.0)),
]

Q_TOTAL = 2.5e-4          # 15 L/min, the design purge flow, m3/s
Q_INLET = Q_TOTAL / 3.0

HEADER = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      %s;
}
"""


def foam(obj, body):
    return HEADER % obj + body.lstrip("\n")


FILES = {}

FILES["system/blockMeshDict"] = foam("blockMeshDict", """
convertToMeters 1;

// Fluid volume: the tray cavity above the board.  The board top is the floor
// (z = 8.6) and the lid underside is the ceiling (z = 43), so this box is the
// whole sample path.  Nothing is added for the walls: they are the boundary.
vertices
(
    (%(X0)s %(Y0)s %(Z0)s)
    (%(X1)s %(Y0)s %(Z0)s)
    (%(X1)s %(Y1)s %(Z0)s)
    (%(X0)s %(Y1)s %(Z0)s)
    (%(X0)s %(Y0)s %(Z1)s)
    (%(X1)s %(Y0)s %(Z1)s)
    (%(X1)s %(Y1)s %(Z1)s)
    (%(X0)s %(Y1)s %(Z1)s)
);

blocks
(
    hex (0 1 2 3 4 5 6 7) (%(NX)d %(NY)d %(NZ)d) simpleGrading (1 1 1)
);

// inletFace and outletFace start as walls; topoSet + createPatch cut the three
// nostril squares and the fan square out of them (the mesh is a box, so the
// round holes become 6 x 6 mm and 34 x 30 mm patches - see README).
boundary
(
    inletFace  { type wall;  faces ((0 1 5 4)); }
    outletFace { type wall;  faces ((3 7 6 2)); }
    sideX0     { type wall;  faces ((0 4 7 3)); }
    sideX1     { type wall;  faces ((1 2 6 5)); }
    board      { type wall;  faces ((0 3 2 1)); }
    lid        { type wall;  faces ((4 5 6 7)); }
);
""" % dict(X0=X0, X1=X1, Y0=Y0, Y1=Y1, Z0=Z0, Z1=Z1, NX=NX, NY=NY, NZ=NZ))

_acts = []
for i, (x, z) in enumerate(INLETS):
    _acts.append("""
    {
        name    inlet%d;
        type    faceSet;
        action  new;
        source  patchToFace;
        patch   inletFace;
    }
    {
        name    inlet%d;
        type    faceSet;
        action  subset;
        source  boxToFace;
        box     (%.1f %.1f %.1f) (%.1f %.1f %.1f);
    }""" % (i, i, x - 3, Y0 - 1, z - 3, x + 3, Y0 + 1, z + 3))
_acts.append("""
    {
        name    outlet;
        type    faceSet;
        action  new;
        source  patchToFace;
        patch   outletFace;
    }
    {
        name    outlet;
        type    faceSet;
        action  subset;
        source  boxToFace;
        box     (%.1f %.1f %.1f) (%.1f %.1f %.1f);
    }""" % (OUTLET[0], Y1 - 1, OUTLET[2], OUTLET[1], Y1 + 1, OUTLET[3]))

FILES["system/topoSetDict"] = foam("topoSetDict", """
// Cut the three nostril patches and the fan outlet out of the box faces.
actions
(
%s
);
""" % "".join(_acts))

FILES["system/createPatchDict"] = foam("createPatchDict", """
pointSync false;
patches
(
    { name inlet0; patchInfo { type patch; } }
    { name inlet1; patchInfo { type patch; } }
    { name inlet2; patchInfo { type patch; } }
    { name outlet; patchInfo { type patch; } }
);
""")

FILES["system/topoSetDict.pad"] = foam("topoSetDict", """
// The filter pad is a porous zone, not a solid: a Darcy-Forchheimer sink in
// the 4 mm slab the pad occupies, x 6..116, y 3..7, z 20..43.
actions
(
    {
        name    pad;
        type    cellSet;
        action  new;
        source  boxToCell;
        box     (%.1f %.1f %.1f) (%.1f %.1f %.1f);
    }
    {
        name    pad;
        type    cellZoneSet;
        action  new;
        source  setToCellZone;
        set     pad;
    }
);
""" % PAD)

FILES["system/snappyHexMeshDict"] = foam("snappyHexMeshDict", """
castellatedMesh true;
snap            true;
addLayers       false;

geometry
{
    cartridges
    {
        type triSurfaceMesh;
        name cartridges;
    }
}

castellatedMeshControls
{
    maxLocalCells       2000000;
    maxGlobalCells      4000000;
    minRefinementCells  10;
    maxLoadUnbalance    0.10;
    nCellsBetweenLevels 2;

    features ();

    refinementSurfaces
    {
        cartridges
        {
            // 2 mm background -> 1 mm on every socket, cartridge and boss
            level (1 1);
            patchInfo { type wall; }
        }
    }

    resolveFeatureAngle 30;
    refinementRegions   {}

    // a point in clear air between the digital row and the filter
    locationInMesh (61 12 30);

    allowFreeStandingZoneFaces true;
}

snapControls
{
    nSmoothPatch           3;
    tolerance              2.0;
    nSolveIter             30;
    nRelaxIter             5;
    nFeatureSnapIter       10;
    implicitFeatureSnap    false;
    explicitFeatureSnap    true;
    multiRegionFeatureSnap false;
}

addLayersControls
{
    relativeSizes          true;
    layers                 {}
    expansionRatio         1.0;
    finalLayerThickness    0.3;
    minThickness           0.1;
    nGrow                  0;
    featureAngle           60;
    slipFeatureAngle       30;
    nRelaxIter             3;
    nSmoothSurfaceNormals  1;
    nSmoothNormals         3;
    nSmoothThickness       10;
    maxFaceThicknessRatio  0.5;
    maxThicknessToMedialRatio 0.3;
    minMedialAxisAngle     90;
    nBufferCellsNoExtrude  0;
    nLayerIter             50;
}

meshQualityControls
{
    maxNonOrtho         65;
    maxBoundarySkewness 20;
    maxInternalSkewness 4;
    maxConcave          80;
    minVol              1e-13;
    minTetQuality       1e-30;
    minArea             -1;
    minTwist            0.02;
    minDeterminant      0.001;
    minFaceWeight       0.02;
    minVolRatio         0.01;
    minTriangleTwist    -1;
    nSmoothScale        4;
    errorReduction      0.75;
}

debug 0;
mergeTolerance 1e-6;
""")

FILES["system/fvSchemes"] = foam("fvSchemes", """
ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; }

divSchemes
{
    default                     none;
    div(phi,U)                  Gauss linearUpwind grad(U);
    div(phi,k)                  Gauss upwind;
    div(phi,omega)              Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}

laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }

wallDist        { method meshWave; }
""")

FILES["system/fvSolution"] = foam("fvSolution", """
solvers
{
    p
    {
        solver          GAMG;
        smoother        DIC;
        tolerance       1e-7;
        relTol          0.01;
    }
    "(U|k|omega)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0.1;
    }
}

SIMPLE
{
    nNonOrthogonalCorrectors 0;
    consistent      no;
    residualControl
    {
        p               1e-4;
        U               1e-5;
        "(k|omega)"     1e-4;
    }
}

relaxationFactors
{
    equations { U 0.9; "(k|omega)" 0.9; }
    fields    { p 0.7; }
}
""")

FILES["system/controlDict.flow"] = foam("controlDict", """
application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         3000;
deltaT          1;
writeControl    timeStep;
writeInterval   500;
purgeWrite      2;
writeFormat     ascii;
writePrecision  6;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

functions
{
    // p is kinematic (p/rho): multiply by 1.2 to compare with the NF1 bench.
    // The fan is not modelled as a curve; the flow rate is imposed, so this
    // number IS the system pressure drop at that flow.
    inletPressure
    {
        type    patchAverage;
        libs    ("libfieldFunctionObjects.so");
        patches (inlet0 inlet1 inlet2);
        fields  (p);
    }
}
""")

FILES["system/controlDict.tracer"] = foam("controlDict", """
// Second run, on the converged flow field: a unit step of a passive tracer at
// the inlets.  t63 at a probe is that point's exchange time.
application     scalarTransportFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         40;
deltaT          0.02;
writeControl    runTime;
writeInterval   1;
purgeWrite      0;
writeFormat     ascii;
writePrecision  6;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

functions
{
    probes
    {
        type            probes;
        libs            ("libsampling.so");
        fields          (T);
        probeLocations
        (
%s        );
    }
}
""" % "".join("            (%.1f %.1f %.1f)   // %s\n" % (p[0], p[1], p[2], n)
              for n, p in PROBES))

FILES["constant/transportProperties"] = foam("transportProperties", """
nu              1.5e-05;    // air at 20 C
DT              1e-05;      // passive tracer, used by the second run
""")

FILES["constant/turbulenceProperties"] = foam("turbulenceProperties", """
simulationType  RAS;
RAS
{
    RASModel        kOmegaSST;
    turbulence      on;
    printCoeffs     on;
}
""")

FILES["constant/fvOptions"] = foam("fvOptions", """
// Filter pad.  d = 7e7 1/m2 is a 4 mm non-woven at ~3 Pa per 0.6 m/s; that is
// the only number here that a bench measurement should replace (NF1).
porosity
{
    type            explicitPorositySource;
    active          yes;
    selectionMode   cellZone;
    cellZone        pad;
    explicitPorositySourceCoeffs
    {
        type            DarcyForchheimer;
        d               d [0 -2 0 0 0 0 0] (7e7 7e7 7e7);
        f               f [0 -1 0 0 0 0 0] (0 0 0);
        coordinateSystem
        {
            origin (0 0 0);
            e1     (1 0 0);
            e2     (0 1 0);
        }
    }
}
""")

FILES["0/U"] = foam("U", """
dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);

boundaryField
{
    inlet0  { type flowRateInletVelocity; volumetricFlowRate %(q).6e; value uniform (0 2.3 0); }
    inlet1  { type flowRateInletVelocity; volumetricFlowRate %(q).6e; value uniform (0 2.3 0); }
    inlet2  { type flowRateInletVelocity; volumetricFlowRate %(q).6e; value uniform (0 2.3 0); }
    outlet  { type inletOutlet; inletValue uniform (0 0 0); value uniform (0 0 0); }
    "(sideX0|sideX1|board|lid|cartridges)" { type noSlip; }
}
""" % dict(q=Q_INLET))

FILES["0/p"] = foam("p", """
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform 0;

boundaryField
{
    outlet  { type fixedValue; value uniform 0; }
    "(inlet0|inlet1|inlet2|sideX0|sideX1|board|lid|cartridges)"
    {
        type zeroGradient;
    }
}
""")

FILES["0/k"] = foam("k", """
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform 0.02;

boundaryField
{
    "(inlet0|inlet1|inlet2)"
    {
        type        turbulentIntensityKineticEnergyInlet;
        intensity   0.05;
        value       uniform 0.02;
    }
    outlet  { type inletOutlet; inletValue uniform 0.02; value uniform 0.02; }
    "(sideX0|sideX1|board|lid|cartridges)"
    {
        type        kqRWallFunction;
        value       uniform 0.02;
    }
}
""")

FILES["0/omega"] = foam("omega", """
dimensions      [0 0 -1 0 0 0 0];
internalField   uniform 256;

boundaryField
{
    "(inlet0|inlet1|inlet2)"
    {
        type            turbulentMixingLengthFrequencyInlet;
        mixingLength    0.001;
        value           uniform 256;
    }
    outlet  { type inletOutlet; inletValue uniform 256; value uniform 256; }
    "(sideX0|sideX1|board|lid|cartridges)"
    {
        type        omegaWallFunction;
        value       uniform 256;
    }
}
""")

FILES["0/nut"] = foam("nut", """
dimensions      [0 2 -1 0 0 0 0];
internalField   uniform 0;

boundaryField
{
    "(inlet0|inlet1|inlet2|outlet)" { type calculated; value uniform 0; }
    "(sideX0|sideX1|board|lid|cartridges)"
    {
        type        nutkWallFunction;
        value       uniform 0;
    }
}
""")

FILES["0/T"] = foam("T", """
dimensions      [0 0 0 0 0 0 0];
internalField   uniform 0;

boundaryField
{
    "(inlet0|inlet1|inlet2)" { type fixedValue; value uniform 1; }
    outlet  { type inletOutlet; inletValue uniform 0; value uniform 0; }
    "(sideX0|sideX1|board|lid|cartridges)" { type zeroGradient; }
}
""")

# a bare `simpleFoam` in this directory also runs: controlDict is the flow one
FILES["system/controlDict"] = FILES["system/controlDict.flow"]

for rel, text in FILES.items():
    path = os.path.join(HERE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as f:
        f.write(text)
    print("wrote", rel)
print("%d files" % len(FILES))
