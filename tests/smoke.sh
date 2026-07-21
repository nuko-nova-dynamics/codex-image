#!/usr/bin/env bash
# Smoke test: drive the whole skill end-to-end against a real Codex auth.
# Requires: codex login complete; pillow installed; ~30-60s per call.
set -euo pipefail

OUT=/tmp/codex-image-smoke-$$
mkdir -p "$OUT"
# shellcheck disable=SC2064 # expand $OUT at trap-set time, not signal time
trap "rm -rf $OUT" EXIT

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GEN="$ROOT/scripts/generate.sh"

echo "1. simple PNG"
"$GEN" "a tiny red square" --out-dir "$OUT" --quality low --format png
ls "$OUT"/*.png >/dev/null

echo "2. JPEG"
"$GEN" "a tiny green square" --out-dir "$OUT" --quality low --format jpeg
ls "$OUT"/*.jpg >/dev/null

echo "3. WebP (Pillow conversion)"
"$GEN" "a tiny blue square" --out-dir "$OUT" --quality low --format webp
ls "$OUT"/*.webp >/dev/null

echo "4. transparent"
"$GEN" "a coffee mug" --out-dir "$OUT" --quality low --transparent --bg-tool chroma
# Should be RGBA after chroma-key
python3 -c "
from PIL import Image
import glob
imgs = glob.glob('$OUT/*coffee*.png')
assert imgs, 'no transparent PNG found'
img = Image.open(imgs[-1])
assert img.mode == 'RGBA', f'expected RGBA, got {img.mode}'
print(f'  OK {imgs[-1]} is RGBA')
"

echo "5. multi-turn (--from-last)"
"$GEN" "make it green" --from-last --out-dir "$OUT" --quality low
ls "$OUT"/*green*.png >/dev/null

echo "6. whoami"
"$GEN" "x" --whoami | grep -E 'email:|plan:'

echo
echo "all smoke tests passed"
