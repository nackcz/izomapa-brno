#!/bin/sh
# První spuštění (macOS / Linux / Windows v Git Bash): Python prostředí, Node balíčky a Chromium pro renderer.
# Předpoklad: Python 3.9+, Node 18+ (Mac: brew install python node)
set -e
cd "$(dirname "$0")"
PY=python3; $PY -c '' 2>/dev/null || PY=python      # Windows: python3 je jen odkaz do Microsoft Store
$PY -m venv .venv
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; else . .venv/Scripts/activate; fi   # Windows: Scripts
python -m pip install -q --upgrade pip
pip install -q shapely pyproj numpy pillow pyarrow pandas "laspy[lazrs]"
npm install
npx playwright install chromium
echo "Hotovo. Další krok: python novy_mesto.py \"Název obce\"  a pak  ./postav.sh"
