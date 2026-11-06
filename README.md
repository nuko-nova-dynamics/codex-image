# codex-image

> A Claude Code skill that generates and edits images with GPT Image, billed to your ChatGPT subscription. No `OPENAI_API_KEY` required.

[![skills.sh](https://skills.sh/b/nuko-nova-dynamics/codex-image)](https://skills.sh/nuko-nova-dynamics/codex-image)
[![release](https://img.shields.io/badge/release-v0.3.0-blue)](CHANGELOG.md)
[![tests](https://img.shields.io/badge/tests-177%20passing-success)](#development)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Why

This skill generates images through the same Images endpoints Codex's built-in image tool uses, billed to your ChatGPT subscription, from a single command in your agent session.

```
/codex-image "a yellow taxi at night in rain"
```

→ saves a PNG to `./generated_images/` in about 10 to 30 s. The backend picks the size from the prompt.

## Status

**v0.3.0** (2026-11-06). Requests now go to the Images endpoints (`images/generations`, `images/edits`) as Codex itself sends them, replacing the Codex Responses transport that ChatGPT and CLIProxyAPI began rejecting in November 2026. 177 tests passing; generation, edits and native transparency were confirmed live on chatgpt.com, a local relay and a CLIProxyAPI proxy.

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

Optional: `--format jpeg`, `--format webp` and `--transparent-mode chroma` need Pillow (`python3 -m pip install 'Pillow>=10'`); everything else, including plain `--transparent`, is stdlib-only.

## Quick start

```bash
# Generate
/codex-image "a coffee mug"

# Transparent background (native alpha from the model)
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
export CODEX_IMAGE_FORMAT="webp"
```

Recognized env vars: `CODEX_IMAGE_SIZE`, `CODEX_IMAGE_QUALITY`, `CODEX_IMAGE_FORMAT`, `CODEX_IMAGE_OUT_DIR`, `CODEX_IMAGE_MODEL` (maps to `--image-model`), and `CODEX_IMAGE_HOME` (state dir, default `~/.codex-image`). `CODEX_IMAGE_ORCHESTRATOR` is no longer read. Each flag-backed variable maps to the flag of the same name in [`scripts/generate.py`](scripts/generate.py).

## Stability

This skill sends its requests wherever Codex's own config sends Codex. It reads `$CODEX_HOME/config.toml` over `/etc/codex/config.toml`: a custom `model_provider` gets the request at its `base_url` with its key (no ChatGPT sign-in needed, so a proxy works); otherwise the request goes to `openai_base_url` when set, else `chatgpt.com/backend-api/codex/images/generations` (or `/images/edits`), authenticated by the auth file Codex maintains. Reading the config needs Python 3.11 or later; on 3.10 the skill stops if a Codex config file exists. A config file that exists but cannot be parsed also stops the run instead of falling back to chatgpt.com. That route is not a public, versioned API: a Codex update that changes token storage, required headers, or version gating can break the skill until it's patched. Treat it as tested-against-current-Codex rather than contractually stable; the durable fallback is the official OpenAI Images API with an `OPENAI_API_KEY`.

## Size, quality and model

On ChatGPT the backend chooses size, quality and image model from the prompt. `--size`, `--quality` and `--image-model` are sent but were not applied in checks on 2026-11-06; the script warns when the result differs and records the resolved values in the sidecar. Put the aspect ratio in the prompt ("square 1:1", "tall vertical 9:16"). On a proxy route the script sends the newest `gpt-image-*` model the proxy lists, because the proxy routes on it. See [`references/api-recipe.md`](references/api-recipe.md).

## Known limitations

- **Size, quality and model are the backend's choice:** inspect `resolved_size` and `resolved_quality` in the sidecar. The response does not name the image model.
- **Transparency needs the prompt sentence.** `--transparent` sends `background: "transparent"` and appends one sentence to the prompt; the parameter alone returns almost no fully transparent pixels. Verified on opaque subjects; hair, glass, smoke and translucency are untested, so the chroma path survives as `--transparent-mode chroma`. See [ADR-0002](docs/adr/0002-use-the-images-api.md).
- **No batch:** the backend ignores `n` and returns one image. Multiple images = multiple invocations.
- **PNG only from the backend:** `--format jpeg` and `--format webp` are converted locally and need Pillow.
- **No multi-turn via `previous_response_id`:** backend is stateless. Multi-turn is achieved by the agent re-passing the prior image (`--from-last` / `--input`, up to 16 references).
- **No token refresh:** the skill reads Codex CLI's `auth.json` as-is and never refreshes it. If the access token has expired, run any Codex command (or `codex login`) to rotate it, then retry.

See [`tests/`](tests/) for the full test suite and [`tests/smoke.sh`](tests/smoke.sh) for end-to-end coverage.

## References

- [`references/api-recipe.md`](references/api-recipe.md) — Images endpoint requests per route, and which fields the backend honors
- [`references/prompting-cookbook.md`](references/prompting-cookbook.md) — prompting fundamentals + templates
- [`references/transparent-image-tips.md`](references/transparent-image-tips.md) — how native transparency works, when it struggles, and the chroma fallback
- [`CONTEXT.md`](CONTEXT.md) — glossary; defines the transports that reach OpenAI image models
- [`docs/adr/`](docs/adr/) — architecture decisions

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

# End-to-end smoke test (real backend, ~6 generations, needs codex login + Pillow)
./tests/smoke.sh
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Nuko Nova Dynamics

Bundles `remove_chroma_key.py` from [`openai/codex`](https://github.com/openai/codex) (Apache 2.0, compatible).
