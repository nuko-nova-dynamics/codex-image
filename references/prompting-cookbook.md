# Prompting cookbook for gpt-image-2

(Distilled from the official OpenAI image generation cookbook + Codex CLI's bundled prompting guide.)

## Core fundamentals

- **Order:** background/scene → subject → key details → constraints
- **Photorealism:** include the literal word `photorealistic` (or "real photograph", "iPhone photo")
- **Latency vs fidelity:** start with `quality: low` (often good enough); escalate for dense text, close-up portraits, identity-sensitive edits, high-res output
- **Text in images:** wrap literal text in `"quotes"` or `ALL CAPS`; spell out tricky brand names letter-by-letter
- **Edits:** "change only X" + "keep everything else the same" + repeat the preserve-list each turn to prevent drift
- **Multi-image:** reference by index — `Image 1: product photo … Image 2: style reference … apply Image 2's style to Image 1`
- **Iterate, don't overload:** start clean, refine with single-change follow-ups via `--input`
- **4K caveat:** for safe 4K use `3824x2144` (multiples of 16, well under the 3840 max-edge rule); the demo's `3840x2160` is right at the boundary

## Use-case templates

### Logo

```
Logo for <brand description>, simple flat geometric mark, strong silhouette,
single solid color, balanced negative space, scalable across sizes.
No text unless explicitly requested. Vector-friendly style.
```

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

### Infographic

```
A flat-design infographic explaining <topic>, with <N> clearly labeled
sections, sans-serif typography, restricted three-color palette, simple
icons, generous spacing, no charts or photos. Quality: high.
```

## What gpt-image-2 is bad at

- Tiny text (<12px equivalent) — illegible regardless of quality
- Hands and fingers in complex poses — still wonky at the edges
- Reading-direction logos (e.g. Hebrew/Arabic brand marks)
- Precise pixel-perfect color palettes (it interprets, doesn't paint)
- Vector / SVG output (it's a raster model — convert with vectorization tool after)
