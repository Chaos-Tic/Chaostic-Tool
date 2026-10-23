#!/bin/sh
# Regenerate public visuals from synthetic data without starting an operation.
set -eu
cd "$(dirname "$0")/.."
export QT_QPA_PLATFORM=offscreen
export PYTHONUTF8=1
"${PYTHON:-python3}" scripts/make-icon.py
"${PYTHON:-python3}" scripts/capture-screens.py "${1:-docs/images/linux}"
