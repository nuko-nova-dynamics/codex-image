# Transparent images

`--transparent` asks the model for a real alpha channel. It does **not** run a background-removal step.

Mechanism: the request sends `background: "auto"` and appends one sentence to your prompt. The backend reads the prompt, resolves `auto` to `transparent`, and returns RGBA. Never send `background: "transparent"` — it returns HTTP 400 on this transport. Full reasoning in [ADR-0001](../docs/adr/0001-request-transparency-in-the-prompt.md).

No Pillow needed. The native path writes the bytes the model returned.

## The prompt is the mechanism

The appended sentence is what triggers transparency:

```text
Output the isolated subject on a genuinely transparent background with actual alpha.
```

Two consequences worth knowing.

**Your prompt keeps full creative control.** The suffix bans nothing. Ask for a soft drop shadow and you get one, rendered *into* the alpha as semi-transparent pixels, so it composites correctly over dark backgrounds as well as light. Ask for in-image text or a label and you get it. Earlier versions of this skill silently forbade all of that; it no longer does.

**A prompt that describes a backdrop can defeat it.** Prompt instructions outrank the request parameter. "A mug on a wooden table in a sunlit studio" describes a scene, and the model may render that scene instead of isolating the subject. If you want a cutout, describe the subject, not its surroundings.

## Validate the result

The skill checks the saved file and warns on stderr if the result has no alpha channel, or has one that is entirely opaque. It still saves the image, because you have already paid for it.

On a warning, re-run with **one** targeted change — usually removing scene language from the prompt — rather than stacking corrections.

## When native transparency struggles

Verified so far on opaque glazed ceramic. Unverified on hair, fur, feathers, smoke, glass, liquids, and translucent bodies. Those were the historical weak spots of the chroma path and there is no evidence yet either way for native.

If a cutout disappoints, escalate in this order:

1. **Re-prompt.** Strip scene and backdrop language; name the subject and nothing else.
2. **Raise quality.** `--quality medium` for fine edges and small text.
3. **Chroma fallback.** `--transparent-mode chroma` (needs Pillow). You control the key plate, which helps when the model insists on grounding the subject with a shadow you do not want.
4. **Adobe MCP.** `--transparent-mode chroma --bg-tool adobe`. Better than chroma-key on translucency.

## Chroma fallback details

The chroma path generates the subject on a flat key colour and strips it locally.

- **Key colour** is auto-selected to avoid the subject (`--key-color` to force). Green subjects get magenta, magenta subjects get green.
- **Thin key-coloured fringe:** re-run with `--edge-contract 1`.
- **Stair-stepped edges on matte, non-reflective subjects:** add `--edge-feather 0.25`. Avoid on shiny or reflective subjects.
- **Despill** is applied automatically; there is no flag.

Where chroma reliably fails: truly translucent bodies (the key punches through the subject, not just around it), subjects containing the key colour, and reflective objects with strong key-colour reflections.

## Formats

PNG (default) and WebP carry alpha. JPEG cannot, and `--transparent --format jpeg` fails before spending a generation.

## A note on size

Requested `size` and `quality` are advisory on this transport. Transparent runs have come back at resolutions that were neither requested nor documented presets. Check the saved file rather than assuming.
