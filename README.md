# codex-image

> A Claude Code skill that generates and edits images with `gpt-image-2`, billed to your ChatGPT subscription. No `OPENAI_API_KEY` required.

[![skills.sh](https://skills.sh/b/nuko-nova-dynamics/codex-image)](https://skills.sh/nuko-nova-dynamics/codex-image)
[![release](https://img.shields.io/badge/release-v0.1.5-blue)](CHANGELOG.md)
[![tests](https://img.shields.io/badge/tests-132%20passing-success)](#development)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Why

The Codex desktop app and Codex CLI both generate images via `gpt-image-2`, billed to your ChatGPT subscription. But opening the app to make one image is friction. This skill lets you do it from any Claude Code session in a single slash command.

```
/codex-image "a yellow taxi at night in rain"
```

→ saves a 1024×1024 PNG to `./generated_images/`, ~30s.

## Status

**v0.1.5 released** (2026-07-21). 132 tests passing, smoke test green against the real backend.

See [`CHANGELOG.md`](CHANGELOG.md) for what's in this release, [`SKILL.md`](SKILL.md) for the contract Claude reads, and [`references/`](references/) for the canonical request recipe and prompting cookbook.

## Install

The quickest path is the [skills.sh](https://skills.sh) CLI, which installs the skill into Claude Code, Codex CLI, Cursor, opencode, and 70+ other agents:

```bash
npx skills add nuko-nova-dynamics/codex-image        # project install
npx skills add nuko-nova-dynamics/codex-image -g     # global (all projects)
```

Manual install (Claude Code):

```bash
git clone https://github.com/nuko-nova-dynamics/codex-image
ln -s "$(pwd)/codex-image" ~/.claude/skills/codex-image
```

Either way, the skill auto-detects Codex CLI's auth at `~/.codex/auth.json`. Make sure you're signed in:

```bash
codex login
```

Optional: `--format webp` and `--transparent` need Pillow (`python3 -m pip install 'Pillow>=10'`); everything else is stdlib-only.

## Quick start

```bash
# Generate
/codex-image "a coffee mug"

# Transparent background (chroma-key workflow)
/codex-image "a coffee mug" --transparent

# Edit a reference image
/codex-image "make it blue" --input ./mug.png

# Multi-turn (the agent passes --from-last to reuse the prior generation)
/codex-image "now add steam rising"

# Different size + format
/codex-image "hero banner" --size 2048x1152 --format webp
```

Full flag reference: `scripts/generate.sh --help`.

## Configuration

Defaults can be overridden via env vars:

```bash
export CODEX_IMAGE_OUT_DIR="./assets/"
export CODEX_IMAGE_QUALITY="medium"
export CODEX_IMAGE_FORMAT="webp"
```

Recognized env vars: `CODEX_IMAGE_SIZE`, `CODEX_IMAGE_QUALITY`, `CODEX_IMAGE_FORMAT`, `CODEX_IMAGE_OUT_DIR`, and `CODEX_IMAGE_HOME` (state dir, default `~/.codex-image`). Each maps to the flag of the same name in [`scripts/generate.py`](scripts/generate.py).

## Stability

This skill talks to the same backend route the Codex CLI itself uses (`chatgpt.com/backend-api/codex/responses`), authenticated by the auth file Codex maintains. That route is not a public, versioned API: a Codex update that changes token storage, required headers, or version gating can break the skill until it's patched. Treat it as tested-against-current-Codex rather than contractually stable; the durable fallback is the official OpenAI Images API with an `OPENAI_API_KEY`.

## Known limitations

- **Quality cap:** the OAuth route silently caps `quality: high` to `medium` regardless of plan (Plus, Pro, Business). True `high` requires `OPENAI_API_KEY`.
- **No native transparency:** `gpt-image-2` rejects `background: "transparent"`. The `--transparent` flag uses a chroma-key workaround (tested clean on hard cases — fly-away fur, smoke, glass — but fails on truly translucent bodies like jellyfish).
- **No batch:** the backend rejects `n`. Multiple images = multiple invocations.
- **No multi-turn via `previous_response_id`:** backend is stateless. Multi-turn is achieved by the agent re-passing the prior image (`--from-last` / `--input`, up to 16 references).
- **No token refresh:** the skill reads Codex CLI's `auth.json` as-is and never refreshes it. If the access token has expired, run any Codex command (or `codex login`) to rotate it, then retry.

See [`tests/`](tests/) for the full test suite and [`tests/smoke.sh`](tests/smoke.sh) for end-to-end coverage.

## References

- [`references/api-recipe.md`](references/api-recipe.md) — canonical Codex Responses request shape
- [`references/prompting-cookbook.md`](references/prompting-cookbook.md) — prompting fundamentals + templates
- [`references/transparent-image-tips.md`](references/transparent-image-tips.md) — chroma-key edge cases and Adobe fallback guidance

## Other agents

`npx skills add nuko-nova-dynamics/codex-image` handles placement for Codex CLI, Cursor, opencode, and the rest of the [skills.sh-supported agents](https://github.com/vercel-labs/skills#supported-agents) — no manual symlinking needed. The primary tested target is Claude Code; behavior in other agents is community-verified, and cross-CLI fixes are welcome via PR.

## Development

```bash
# Lint shell scripts
shellcheck scripts/*.sh

# Lint python
ruff check scripts/

# Unit tests (offline, mocked HTTP)
python3 -m pytest tests/ -q

# End-to-end smoke test (real backend, ~5 generations, needs codex login + Pillow)
./tests/smoke.sh
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Nuko Nova Dynamics

Bundles `remove_chroma_key.py` from [`openai/codex`](https://github.com/openai/codex) (Apache 2.0, compatible).
