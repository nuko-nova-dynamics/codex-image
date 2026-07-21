# Prompting cookbook for gpt-image-2

(Distilled from the official OpenAI image generation cookbook and the openai/codex
imagegen skill's prompting guidance (Apache-2.0), adapted for this skill.)

## Core fundamentals

- **Order:** background/scene → subject → key details → constraints → output intent
- **Photorealism:** include the literal word `photorealistic` (or "real photograph", "iPhone photo"), plus concrete real-world texture — pores, fabric wear, material grain, imperfect everyday detail
- **Latency vs fidelity:** start with `quality: low` (often good enough); escalate for dense text, close-up portraits, identity-sensitive edits, high-res output
- **Text in images:** wrap literal text in `"quotes"` or `ALL CAPS`, specify typography (font style, size, color, placement); spell out tricky brand names letter-by-letter; require verbatim rendering with no extra characters
- **Edits:** "change only X" + "keep everything else the same" + repeat the preserve-list each turn to prevent drift
- **Multi-image:** reference by index and role — `Image 1: edit target … Image 2: style reference … apply Image 2's style to Image 1`
- **Iterate, don't overload:** start clean, refine with single-change follow-ups via `--from-last`; re-specify critical constraints on every iteration
- **4K caveat:** for safe 4K use `3824x2144` (multiples of 16, well under the 3840 max-edge rule); the demo's `3840x2160` is right at the boundary

## Specificity policy — how much to augment the user's prompt

- If the user's prompt is already specific and detailed, normalize it into a clean spec — do not add creative requirements.
- If the prompt is generic, add tasteful detail only where it materially improves the result.

Allowed augmentation for generic prompts: composition/framing cues, intended-use or polish-level hints ("for a landing-page hero"), practical layout guidance, reasonable scene concreteness.

Never add: extra characters/props/objects the request doesn't imply, brand palettes/slogans/story beats, or arbitrary left/right placement the surrounding layout doesn't call for.

## Composition and layout

- Specify framing and viewpoint (close-up, wide, top-down) only when it materially helps.
- Call out negative space when the asset needs room for UI or copy.
- For people: describe body framing, scale, gaze, and object interaction when they matter (`full body visible`, `hands naturally gripping the handlebars`).

## Intent: edit vs generate with references

- Images provided for style, composition, or mood guidance — and not asked to be modified — mean **generate with references**, not edit.
- Preserving an existing image while changing specific parts means **edit**: state the single change and the invariants.
- For compositing, describe how the images interact (`place the subject from Image 2 into Image 1, matching its lighting and perspective`).

## Use-case templates

### Logo

```
Logo for <brand description>, simple flat geometric mark, strong silhouette,
single solid color, balanced negative space, scalable across sizes.
No text unless explicitly requested. Vector-friendly style.
```

For production logo work: generate explorations, iterate one change at a time,
and remind the user raster output needs vectorization for real brand use.

### Photorealistic product shot

```
Photorealistic studio shot of <subject>, soft diffuse key light from upper
left, subtle rim light, neutral seamless background, professional product
photography, sharp focus, natural materials and textures.
```

### UI mockup

```
A clean modern UI for <product>, <orientation> orientation, <screen> view,
flat design, generous whitespace, high contrast, real readable text labels
not lorem ipsum, balanced grid layout. Render as a high-fidelity mockup,
not a wireframe.
```

State the target fidelity first (shippable mockup vs low-fi wireframe); avoid concept-art language.

### Infographic

```
A flat-design infographic explaining <topic>, with <N> clearly labeled
sections, sans-serif typography, restricted three-color palette, simple
icons, generous spacing, no charts or photos. Quality: high.
```

Define the audience and layout flow; label parts explicitly; require verbatim text.

### Ad / marketing creative

Write it like a creative brief: brand positioning, audience, desired vibe,
scene, and the exact tagline in quotes if text must appear.

## What gpt-image-2 is bad at

- Tiny text (<12px equivalent) — illegible regardless of quality
- Hands and fingers in complex poses — still wonky at the edges
- Reading-direction logos (e.g. Hebrew/Arabic brand marks)
- Precise pixel-perfect color palettes (it interprets, doesn't paint)
- Vector / SVG output (it's a raster model — convert with vectorization tool after)
