#!/usr/bin/env bash
# Downloads a small public IFC model into data/bim_models/.
# Source: buildingSMART "Sample-Test-Files" repository (IFC 4 reference models).
# If the URL moves, pick any .ifc from https://github.com/buildingSMART/Sample-Test-Files
set -euo pipefail

DEST="data/bim_models"
mkdir -p "$DEST"
URL="${1:-https://raw.githubusercontent.com/buildingSMART/Sample-Test-Files/main/IFC%204.0/BuildingSMARTSpec/wall-with-opening-and-window.ifc}"

echo "Downloading $URL"
curl -fL "$URL" -o "$DEST/sample.ifc"
echo "Saved to $DEST/sample.ifc"
