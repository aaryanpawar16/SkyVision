#!/usr/bin/env bash
set -euo pipefail

# Convert a short MP4 screen recording to a small, looped GIF optimized for README.md.
# Requires ffmpeg (and optionally gifski for higher quality).

IN=${1:-demo.mp4}
OUT=${2:-demo.gif}
FPS=${FPS:-12}
SCALE=${SCALE:-1280} # width, keeps aspect ratio

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "✖ ffmpeg not found. Please install ffmpeg."
  exit 1
fi

echo "→ Converting ${IN} → ${OUT} (fps=${FPS}, width=${SCALE})…"
# Palette + dither method for decent quality with small size.
ffmpeg -y -i "${IN}" -vf "fps=${FPS},scale=${SCALE}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5" -loop 0 "${OUT}"

echo "✔ Wrote ${OUT}"
