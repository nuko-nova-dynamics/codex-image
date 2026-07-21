# Transparent images — when chroma-key fails, what to do

The `--transparent` flag uses a chroma-key workaround:

1. Generate the subject on a flat solid color (`#00ff00` by default)
2. Locally remove that color and replace with alpha

This is NOT native model transparency. `gpt-image-2` rejects `background: "transparent"`.

## When the chroma path works well (tested)

- Solid opaque subjects (mugs, products, vehicles, foods)
- Clear glass with content visible through it (wine glass, jar with liquid)
- Hair / fur with fly-aways (Pomeranian, wind-blown hair) — soft-matte preserves edges
- Smoke wisps and steam — semi-transparent edges survive
- Plants on a contrasting key (use `--key-color #ff00ff` for green subjects)

## When the chroma path will likely fail

- Truly translucent bodies (jellyfish, ice cubes, soap bubbles) — chroma punches through the body, not just around it
- Subjects with the key color baked in (a green frog on `#00ff00`, a pink rose on `#ff00ff`)
- Reflective objects with strong key-color reflections (chrome ball, mirror)
- Subjects against complex shadows the model insists on rendering

## Workarounds

- **Color conflict:** override with `--key-color #ff00ff` (magenta) or `#00ffff` (cyan). The skill auto-picks magenta for green-keyword prompts; you can force.
- **Translucent body:** use Adobe MCP background removal instead (`--bg-tool=adobe`). Adobe handles translucency much better than chroma-key.
- **Reflective key bleed:** re-generate at higher quality (`--quality medium`). Despill is applied automatically during chroma removal — there is no user-facing flag for it.

## When to give up on transparency

If two re-runs with different key colors and `--bg-tool=adobe` all produce a weak cutout, the subject probably needs manual masking in a real image editor. The skill is not a substitute for Photoshop on edge cases.
