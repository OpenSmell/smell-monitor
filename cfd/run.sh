#!/usr/bin/env bash
# OpenFOAM case for the OpenSmell v1.1 chamber.
#
#   bash run.sh                8 slots filled (the reference build)
#   bash run.sh --omit 3,6     leave slots 3 and 6 empty (interference study)
#
# Two solves: steady flow (simpleFoam, k-omega SST), then a unit step of a
# passive tracer on that frozen field (scalarTransportFoam).  report.py turns
# the tracer probes into exchange times.
set -euo pipefail
cd "$(dirname "$0")"

python3 gen_geometry.py "$@"

cp system/controlDict.flow system/controlDict

echo "== mesh =="
blockMesh                     > log.blockMesh 2>&1
topoSet -dict system/topoSetDict > log.topoSet 2>&1
createPatch -overwrite        > log.createPatch 2>&1
snappyHexMesh -overwrite      > log.snappyHexMesh 2>&1
topoSet -dict system/topoSetDict.pad > log.topoSet.pad 2>&1
checkMesh -allGeometry -allTopology > log.checkMesh 2>&1 || true
grep -E "cells:|Mesh OK|Failed" log.checkMesh || true

echo "== flow (steady) =="
simpleFoam > log.simpleFoam 2>&1
tail -n 25 log.simpleFoam

latest=$(foamListTimes | tail -1)
echo "converged field at t=$latest"

echo "== tracer (unit step at the inlets) =="
cp "$latest/U" 0/U
cp system/controlDict.tracer system/controlDict
scalarTransportFoam > log.tracer 2>&1
tail -n 5 log.tracer

python3 report.py
