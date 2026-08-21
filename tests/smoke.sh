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

echo "4a. transparent (native — the default path)"
"$GEN" "a coffee mug with a soft drop shadow" --out-dir "$OUT" --quality low --transparent
# Real alpha from the model, and the backend must report it resolved to transparent.
python3 -c "
from PIL import Image
import glob, json
imgs = sorted(glob.glob('$OUT/*coffee*.png'))
assert imgs, 'no transparent PNG found'
img = Image.open(imgs[-1])
assert img.mode == 'RGBA', f'expected RGBA, got {img.mode}'
alpha = img.getchannel('A')
clear = alpha.histogram()[0]
assert clear > 0, 'no fully transparent pixels — alpha channel is unused'
meta = json.load(open(imgs[-1] + '.json'))
assert meta['resolved_background'] == 'transparent', meta['resolved_background']
assert meta['transparency_mode'] == 'native', meta['transparency_mode']
pct = 100 * clear / (img.width * img.height)
print(f'  OK {imgs[-1]} is RGBA, {pct:.1f}%% clear, model={meta[\"image_model\"]}')
"

echo "4b. transparent (chroma fallback)"
# "leaf" is a green-family keyword, so this also exercises automatic key-colour
# selection (it should pick magenta, not #00ff00). Deliberately NOT "a green
# leaf": that filename would also match step 5's *green*.png assertion.
"$GEN" "a maple leaf" --out-dir "$OUT" --quality low --transparent-mode chroma
python3 -c "
from PIL import Image
import glob, json
imgs = sorted(glob.glob('$OUT/*leaf*.png'))
assert imgs, 'no chroma PNG found'
img = Image.open(imgs[-1])
assert img.mode == 'RGBA', f'expected RGBA, got {img.mode}'
meta = json.load(open(imgs[-1] + '.json'))
assert meta['transparency_mode'] == 'chroma', meta['transparency_mode']
print(f'  OK {imgs[-1]} is RGBA via chroma')
"

echo "5. multi-turn (--from-last)"
"$GEN" "make it green" --from-last --out-dir "$OUT" --quality low
ls "$OUT"/*green*.png >/dev/null

echo "6. whoami"
"$GEN" "x" --whoami | grep -E 'email:|plan:'

echo
echo "all smoke tests passed"
