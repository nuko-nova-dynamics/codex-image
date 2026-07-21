# Transparent images — when chroma-key fails, what to do

(Chroma prompt and edge-refinement guidance adapted from the openai/codex
imagegen skill, Apache-2.0.)

The `--transparent` flag uses a chroma-key workaround:

1. Generate the subject on a flat solid color (`#00ff00` by default)
2. Locally remove that color and replace with alpha

This is NOT native model transparency. `gpt-image-2` rejects `background: "transparent"`.

## Prompt shape that keys cleanly

The script appends a chroma suffix automatically, but when you write or augment the prompt yourself, aim for:

```text
<subject> on a perfectly flat solid #00ff00 chroma-key background.
The background must be one uniform color with no shadows, gradients, texture,
reflections, floor plane, or lighting variation. Keep the subject fully
separated from the background with crisp edges and generous padding.
Do not use #00ff00 anywhere in the subject. No cast shadow, no contact
shadow, no reflection, no watermark.
```

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

## Validate, then refine the edge

After removal, check: alpha channel present, transparent corners, plausible subject coverage, no key-color fringe.

- **Thin green/magenta fringe:** re-run once with `--edge-contract 1` (shrinks the alpha edge by 1 px).
- **Stair-stepped edges on matte, non-reflective subjects:** add `--edge-feather 0.25`. Avoid feathering shiny or reflective subjects.
- **Reflective key bleed:** re-generate at higher quality (`--quality medium`). Despill is applied automatically during chroma removal — there is no user-facing flag for it.
- **Color conflict:** override with `--key-color #ff00ff` (magenta) or `#00ffff` (cyan). The skill auto-picks magenta for green-keyword prompts; you can force.
- **Translucent body:** use Adobe MCP background removal instead (`--bg-tool=adobe`). Adobe handles translucency much better than chroma-key.

## When to give up on transparency

If two re-runs with different key colors and `--bg-tool=adobe` all produce a weak cutout, the subject probably needs manual masking in a real image editor, or true native transparency: `gpt-image-1.5` supports `background: "transparent"` via the official Images API — but that path requires an `OPENAI_API_KEY`, which is outside this skill's OAuth route. The skill is not a substitute for Photoshop on edge cases.
