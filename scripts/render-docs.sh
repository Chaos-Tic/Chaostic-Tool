#!/usr/bin/env bash
# Regenerates docs/media from synthetic demo data: no live target, tool or
# network request is ever executed. Needs ffmpeg and ImageMagick.
set -euo pipefail
cd "$(dirname "$0")/.."

export QT_QPA_PLATFORM=offscreen
export PYTHONUTF8=1
PYTHON_BIN="${PYTHON:-python3}"

echo "==> Generating vector and desktop icons"
"$PYTHON_BIN" scripts/make-icon.py

echo "==> Capturing deterministic UI screenshots"
"$PYTHON_BIN" scripts/capture-screens.py docs/images/linux
mkdir -p docs/media
cp docs/images/linux/liquid-glass-*.png docs/media/

echo "==> Generating demo animated GIF (Lyapunov standard)"
"$PYTHON_BIN" scripts/make-demo-gif.py

if command -v magick >/dev/null 2>&1; then
    echo "==> Optimizing PNG assets (lossless compression)"
    for f in docs/media/*.png; do
        [ -f "$f" ] && magick "$f" -strip -define png:compression-level=9 "$f"
    done
fi

echo "==> Documentation media ready in docs/media:"
ls -lh docs/media/
