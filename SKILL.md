---
name: codex-image
description: Generate or edit images with gpt-image-2, billed to the user's ChatGPT subscription via Codex CLI OAuth — no OPENAI_API_KEY needed. Use whenever the user wants to generate, create, draw, edit, or modify an image, picture, photo, logo, icon, illustration, product shot, UI mockup, wallpaper, or infographic — including transparent-background / cutout PNGs. Trigger on phrasing like "make me an image of X", "draw a logo for Y", "generate a picture of Z", "now make it darker", "remove the background", or an explicit /codex-image invocation.
license: MIT
metadata:
  author: nuko-nova-dynamics
  version: "0.1.4"
---

# codex-image

Generate and edit images with `gpt-image-2` via the user's ChatGPT subscription. Output lands in `./generated_images/` (or `--out-dir` / `--out`).

## How to run

Everything goes through one script. Resolve the absolute directory containing this SKILL.md (your harness announces it when the skill loads — below it's written `<skill-dir>`), then:

```bash
bash "<skill-dir>/scripts/generate.sh" "<prompt>" [flags]
```

Never invoke a bare relative `scripts/generate.sh`: your working directory is the user's project, not the skill's install location (which varies by agent — `~/.claude/skills/`, `~/.agents/skills/`, `~/.opencode/skills/`, a project-local `.claude/skills/`, …).

Requirements the script checks for you:

- `python3` ≥ 3.10 on PATH (bash + stdlib Python otherwise).
- **Pillow — only for `--format webp` and `--transparent`.** Not installed by default; those runs fail fast with the install command (`python3 -m pip install 'Pillow>=10'`). Mention this prerequisite before first use of either flag.
- Codex CLI signed in. If it isn't, the script exits with `Run: codex login` — relay that to the user rather than touching auth yourself.

`bash "<skill-dir>/scripts/generate.sh" --help` prints the full flag surface; consult it before improvising flags. Where the host agent supports typed slash commands, `/codex-image "<prompt>" --flags` is user-facing shorthand for exactly this script call.

The script is mechanical — it does no semantic routing. Continuation handling, batch decisions, and background-removal dispatch are YOUR job, based on the conversation.

## Continuation handling

When the request modifies the image generated in the immediately-preceding turn ("make it darker", "now add a hat", "more contrast"), pass `--from-last` — the script re-uses the last generation automatically (tracked in `~/.codex-image/last.json`), so you don't have to recover the path from the transcript.

For edits to an explicit file or an older generation, pass `--input <path|url>` instead (repeatable; max 16 references combined with `--from-last` — the gpt-image-2 model limit).

When the request is a fresh subject — even if phrased "now make…" — pass neither and generate from scratch. If you guess wrong and the user says "no, I meant a new one", re-run without references.

## Background removal dispatch

When the user wants a transparent background, add `--transparent`. Resolve `--bg-tool` (default `auto`) yourself:

| `--bg-tool` value | Your action |
| --- | --- |
| `none` | Leave the chroma-keyed PNG as-is; report path to user |
| `chroma` | Pass `--bg-tool=chroma`; the script runs local chroma-key removal (needs Pillow) |
| `adobe` | Two steps: (1) run with `--transparent --bg-tool=none` to produce the chroma-keyed PNG. (2) Call whatever Adobe background-removal tool is exposed in this session — the tool id varies by host, so look for an Adobe MCP tool whose name contains `remove_background` (e.g. `image_remove_background` on the Adobe-for-creativity server) and overwrite the file with the alpha result. If no such tool exists, error: "Adobe MCP not available; install adobe-for-creativity or pass --bg-tool=chroma." |
| `auto` (default) | Same two-step Adobe attempt; if no Adobe tool is exposed, pass `--bg-tool=chroma` directly (one step, no error) |

The script never sees `auto` or `adobe` — you resolve those upstream. This is a chroma-key workaround, not native model transparency (`gpt-image-2` rejects `background: "transparent"`); tell the user this the first time they ask for transparency.

## Quality, cost & time guardrails

- The flag default is `--quality high`, but the OAuth route silently caps it to `medium` — requesting `high` buys nothing here (true `high` needs an API key). For iteration, pass `--quality low`: it's much faster and often good enough. Escalate only for final output, dense in-image text, or close-up faces.
- Each image takes ~15–60 s of wall time and counts against the user's ChatGPT plan rate limits (subscription usage, not per-image dollar billing).
- Before generating more than 3 images for a single request, confirm with the user first.
- Never loop indefinitely. "Many" / "a whole set" → pick a sensible default (4) and offer to continue.
- HTTP 429 from the backend = stop immediately, do not retry.

## Common workflows

```bash
# Single generation
bash "<skill-dir>/scripts/generate.sh" "a yellow taxi at night in rain"

# Continuation of the prior generation
bash "<skill-dir>/scripts/generate.sh" "now add steam rising" --from-last

# Edit an explicit reference image
bash "<skill-dir>/scripts/generate.sh" "make it blue" --input ./mug.png

# Transparent background (chroma-key; needs Pillow)
bash "<skill-dir>/scripts/generate.sh" "a coffee mug" --transparent

# Different size / format / quality
bash "<skill-dir>/scripts/generate.sh" "hero banner" --size 2048x1152 --format webp --quality low
```

## Token redaction (security)

NEVER print or log the user's `access_token`, `id_token`, `refresh_token`, or any `Authorization: Bearer ...` header. The skill's Python modules redact automatically; you must not undo that by reading `~/.codex/auth.json` yourself or echoing tokens in error messages.

## When NOT to invoke

- Vector art, SVG, ASCII art, or LaTeX diagrams → not `gpt-image-2`'s strength; use a dedicated tool.
- The user explicitly wants a different model or product (DALL-E, Stable Diffusion, Midjourney) → defer to that.

For production logo/brand work, do invoke — but set expectations: generate explorations and refine with single-change `--from-last` iterations rather than promising a final asset in one shot (templates in `references/prompting-cookbook.md`).

## References

When you need more depth, read from `<skill-dir>/references/`:

- `api-recipe.md` — canonical request body, headers, rejected fields, SSE parsing
- `prompting-cookbook.md` — prompting fundamentals + use-case templates (logo, product shot, UI mockup, infographic)
- `transparent-image-tips.md` — when chroma-key fails and what to do
