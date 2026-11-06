---
name: codex-image
description: "Use when the user asks to generate or edit an image of any kind, whatever it is for: a logo, icon, photo, illustration, mockup, texture, or reference picture. Also use for follow-up edits to the last image, such as \"make it darker\" or \"remove the background\", and for transparent PNG cutouts."
license: MIT
metadata:
  author: nuko-nova-dynamics
  version: "0.3.0"
---

# codex-image

Generate and edit images with GPT Image via the user's ChatGPT subscription. The script calls the Images endpoints (`images/generations`, `images/edits`) the same way Codex's built-in image tool does, on whatever route Codex's own config uses: chatgpt.com, a relay, or a proxy. Output lands in `./generated_images/` (or `--out-dir` / `--out`).

## How to run

Everything goes through one script. Resolve the absolute directory containing this SKILL.md (your harness announces it when the skill loads — below it's written `<skill-dir>`), then:

```bash
bash "<skill-dir>/scripts/generate.sh" "<prompt>" [flags]
```

Never invoke a bare relative `scripts/generate.sh`: your working directory is the user's project, not the skill's install location (which varies by agent — `~/.claude/skills/`, `~/.agents/skills/`, `~/.opencode/skills/`, a project-local `.claude/skills/`, …).

Requirements the script checks for you:

- `python3` ≥ 3.10 on PATH (bash + stdlib Python otherwise).
- **Pillow — only for `--format jpeg`, `--format webp` and `--transparent-mode chroma`.** The backend always returns PNG, so other formats are converted locally. Not installed by default; those runs fail fast with the install command (`python3 -m pip install 'Pillow>=10'`). Plain `--transparent` does **not** need it. Mention this prerequisite before first use.
- Codex CLI signed in. If it isn't, the script exits with `Run: codex login` — relay that to the user rather than touching auth yourself.

`bash "<skill-dir>/scripts/generate.sh" --help` prints the full flag surface; consult it before improvising flags. Where the host agent supports typed slash commands, `/codex-image "<prompt>" --flags` is user-facing shorthand for exactly this script call.

The script is mechanical — it does no semantic routing. Continuation handling, batch decisions, and background-removal dispatch are YOUR job, based on the conversation.

## Size, quality and model

The backend picks size, quality and image model from the prompt. `--size`, `--quality` and `--image-model` are sent when given, but on ChatGPT they are currently ignored (verified 2026-11-06), and the script warns when the result differs. To get a shape, say it in the prompt: "square 1:1 …" or "tall vertical 9:16 …". Dense text and transparent subjects come back at `medium`; simple scenes often at `low`. Check `resolved_size` and `resolved_quality` in the sidecar before claiming either.

Leave `--image-model` out. On a proxy route the script sends the newest `gpt-image-*` model the proxy lists, which the proxy needs for routing. `--orchestrator` and `--effort` are deprecated no-ops: there is no chat model in this request. Details: [API recipe](references/api-recipe.md).

## Continuation handling

When the request modifies the image generated in the immediately-preceding turn ("make it darker", "now add a hat", "more contrast"), pass `--from-last` — the script re-uses the last generation automatically (tracked in `~/.codex-image/last.json`), so you don't have to recover the path from the transcript.

For edits to an explicit file or an older generation, pass `--input <path|url>` instead (repeatable; max 16 references combined with `--from-last`; the skill reference cap).

When the request is a fresh subject — even if phrased "now make…" — pass neither and generate from scratch. If you guess wrong and the user says "no, I meant a new one", re-run without references.

Images the user provides only for style, composition, or mood are **references for a generation, not edit targets** — pass them via `--input` but phrase the prompt as a new image ("in the style of Image 2"). When mixing several inputs, label each by index and role in the prompt (`Image 1: edit target, Image 2: style reference`).

## After generating: look, then report

Before telling the user you're done, view the saved image file and check it against the request: subject, composition, any literal text rendered verbatim, and every constraint the user stated. If something is off, iterate with ONE targeted change (via `--from-last`), re-stating the invariants that must not drift. Don't stack multiple corrections into one re-run, and don't report a path you haven't looked at.

Saving discipline: output defaults to `./generated_images/`. If the image is destined for the user's project, copy or move it to its real place (and update any code that references it) — don't leave a project asset only in the scratch dir. Never overwrite an existing asset the user didn't ask to replace; write a versioned sibling (`hero-v2.png`) instead.

## Transparent images

When the user wants a transparent background, add `--transparent`. That's it — no dispatch decision, no Pillow, no post-processing step for you to orchestrate.

The script asks the model for alpha directly: it sends `background: "transparent"` and appends one sentence to the prompt, and the backend returns RGBA. The sentence does most of the work: the parameter alone returns an alpha channel with almost no fully transparent pixels (`docs/adr/0002-use-the-images-api.md`). `--background transparent` is the same as `--transparent`.

Advice that native transparency needs `gpt-image-1.5` or an `OPENAI_API_KEY` is wrong for this skill. Check `metadata.version` in this file: it should be `0.3.0` or later.

Two things to get right when you write the prompt:

- **Describe the subject, not a scene.** Prompt beats parameter. "A mug on a wooden table in a sunlit studio" may render that studio instead of isolating the mug. Name the subject and its material; leave the surroundings out.
- **Don't add your own bans.** The suffix deliberately forbids nothing. If the user asked for a drop shadow, let them have it — it comes back rendered into the alpha and composites correctly. Adding "no shadow, no background" yourself overrides their intent.

After generating, view the file and check the alpha actually arrived. The script warns on stderr when the result has no alpha or is fully opaque; treat that as a signal to re-run with ONE targeted change, usually removing scene language.

**Fallback ladder**, only when native disappoints (verified on opaque subjects; hair, glass, smoke and translucency are untested):

| Escalation | Action |
| --- | --- |
| Re-prompt | Strip scene/backdrop language, name the subject alone |
| Chroma | `--transparent-mode chroma` (needs Pillow) — you control the key plate |
| Adobe MCP | `--transparent-mode chroma --bg-tool=none`, then call whatever Adobe background-removal tool this session exposes (look for an MCP tool whose name contains `remove_background`) and overwrite the file with the alpha result. Best option for translucency |

Chroma edge repair: thin fringe → `--edge-contract 1`; stair-stepped edges on matte subjects → `--edge-feather 0.25`. Deeper failure modes: `references/transparent-image-tips.md`.

## Quality, cost & time guardrails

- Quality is chosen by the backend; there is no reliable way to force a draft or a high-quality render. Inspect `resolved_quality` in the sidecar or `--verbose` output before claiming a level.
- Generations count against the user's ChatGPT plan limits. Latency varies by model, prompt, quality, and service load.
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

# Transparent background (native alpha from the model; no Pillow)
bash "<skill-dir>/scripts/generate.sh" "a coffee mug" --transparent

# Transparent, with a shadow the user asked for (survives into the alpha)
bash "<skill-dir>/scripts/generate.sh" "a coffee mug with a soft drop shadow" --transparent

# Chroma fallback, when native disappoints (needs Pillow)
bash "<skill-dir>/scripts/generate.sh" "a glass jar" --transparent --transparent-mode chroma

# A shape and a format: say the shape in the prompt; webp is converted locally (needs Pillow)
bash "<skill-dir>/scripts/generate.sh" "wide 16:9 hero banner of a mountain lake at dawn" --format webp
```

## Token redaction (security)

NEVER print or log the user's `access_token`, `id_token`, `refresh_token`, or any `Authorization: Bearer ...` header. The skill's Python modules redact automatically; you must not undo that by reading `~/.codex/auth.json` yourself or echoing tokens in error messages.

## When NOT to invoke

- Vector art, SVG, ASCII art, or LaTeX diagrams → use a dedicated vector or diagram tool.
- The user explicitly wants a different model or product (DALL-E, Stable Diffusion, Midjourney) → defer to that.

For production logo/brand work, do invoke — but set expectations: generate explorations and refine with single-change `--from-last` iterations rather than promising a final asset in one shot (templates in `references/prompting-cookbook.md`).

## References

When you need more depth, read from `<skill-dir>/references/`:

- `api-recipe.md` — endpoints per route, request and response bodies, which fields the backend honors, transparency mechanism
- `prompting-cookbook.md` — prompting fundamentals + use-case templates (logo, product shot, UI mockup, infographic)
- `transparent-image-tips.md` — how native transparency works, when it struggles, and the chroma fallback

Repo-level context: `CONTEXT.md` (glossary, including the transports) and `docs/adr/` (why the skill uses the Images endpoints, and why transparency still needs the prompt sentence).
