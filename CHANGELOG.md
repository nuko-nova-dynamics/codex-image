# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-08-21

### Changed

- **`--transparent` now produces the model's own alpha channel instead of a chroma-keyed approximation.** Existing invocations are unchanged and keep working, but the artifact you get back is different and produced by a different mechanism. The request sends `background: "auto"` with a one-sentence transparency request appended to the prompt; the backend resolves `auto` to `transparent` and returns RGBA. `background: "transparent"` is never sent — it returns HTTP 400 on this transport. See [ADR-0001](docs/adr/0001-request-transparency-in-the-prompt.md).
- **`--transparent` no longer requires Pillow.** The native path writes the bytes the model returned. Pillow is still needed for `--format webp` and `--transparent-mode chroma`.
- **The prompt is no longer hijacked.** The old chroma template banned shadows, reflections, gradients and texture on the user's behalf. The native suffix bans nothing: ask for a drop shadow and it comes back rendered into the alpha, ask for in-image text and you get it.
- `--background` accepts `transparent` instead of rejecting it at parse time. It is passed through unchanged and the backend's real error is surfaced, rather than silently substituting a different value.
- `references/api-recipe.md` and `references/transparent-image-tips.md` rewritten around the actual mechanism. The previous "`background: transparent` is rejected, chroma-key replaces it" framing was literally true and badly misleading.

### Added

- `--transparent-mode {native,chroma}`, defaulting to `native`. The chroma path survives as an explicit fallback for subject classes native transparency is unverified on (hair, fur, smoke, glass, translucency). Passing `--bg-tool` implies chroma mode, so pre-0.2.0 invocations still route as before.
- Best-effort alpha verification. A transparent request whose result has no alpha channel, or an entirely opaque one, warns on stderr and still saves — the image is already paid for.
- The resolved image model and background mode are recorded in the sidecar. This replaces a "gpt-image-2" claim the skill had been repeating across three files without ever observing it; the backend actually routes to `gpt-image-2-codex`, which is why the transparent parameter is refused.
- `CONTEXT.md` glossary and `docs/adr/`. The glossary names the three transports that reach OpenAI image models, which is the distinction that makes this whole area confusing.

### Fixed

- Image results are accepted from `response.output_item.done` regardless of `status`. This backend emits the finished image while still reporting `status: "generating"`, and its `response.completed.output` arrives empty, so every successful generation was silently falling through to the last-resort partial frame. Both observed cases happened to be byte-identical, but a stale partial would have saved the wrong image.

## [0.1.5] - 2026-07-21

### Added

- `--edge-contract` and `--edge-feather` flags pass through to the bundled chroma-removal helper, enabling the standard fringe-fix retry (`--edge-contract 1`) and edge softening without leaving the CLI. Verified live against the backend.
- SKILL.md: post-generation validation loop (view the image, check subject/text/constraints, iterate one targeted change), non-destructive save policy (project-bound assets moved into the workspace; versioned siblings instead of overwrites), and reference-vs-edit intent labeling for multi-image inputs.

### Changed

- `references/prompting-cookbook.md` expanded with a prompt-specificity policy (when to augment vs normalize), composition/people guidance, ad-creative template, and per-template tips — adapted from the openai/codex imagegen skill (Apache-2.0), which this skill's chroma helper already comes from.
- `references/transparent-image-tips.md` now includes the full clean-keying prompt shape, an edge-refinement decision ladder, and notes `gpt-image-1.5 --background transparent` (API-key route) as the true-native-transparency fallback.

## [0.1.4] - 2026-07-21

### Added

- skills.sh distribution: install with `npx skills add nuko-nova-dynamics/codex-image` (or `-g` for global) into any of the 70+ agents the [skills CLI](https://github.com/vercel-labs/skills) supports.
- SKILL.md now states the exact command an agent should execute (`scripts/generate.sh` relative to the skill's base directory), valid for both symlinked and copied installs.

### Changed

- README install section leads with the skills.sh CLI; the "Other CLIs (untested)" section is replaced by skills.sh-managed placement notes.
- SECURITY.md vulnerability contact moved from a personal email address to GitHub private vulnerability reporting; the path-traversal claim narrowed to what the code actually resolves (input refs).
- SKILL.md rewritten for cross-agent distribution: broader trigger description, `--from-last` documented as the preferred continuation path, Pillow prerequisite stated, Adobe MCP tool discovered by name pattern instead of a hardcoded Claude-specific id, quality/cost guardrails aligned with the OAuth medium cap, slash-command syntax marked host-dependent.
- `generate.py` chroma subprocess now uses `sys.executable` instead of a hardcoded `python3`, and its `--bg-tool=adobe` error message is agent-neutral.
- Repository history squashed for the public release (prior private history referenced local filesystem paths). Release history before 0.1.4 is preserved in this changelog.

### Fixed

- **Input-reference cap raised 5 → 16**, the documented gpt-image-2 edit limit (per the official OpenAI image-edit types), confirmed against the live backend with a 6-reference edit. Enforced consistently in `api_client.py`, `generate.py`, docs, and boundary tests.
- **Empty-stream retry no longer drops edit references.** Previously a stream with no image was retried once with `--input` references removed, silently turning an edit into an unrelated fresh generation; edits now fail cleanly instead. (Reference-free generations keep the single retry.)
- **Partial-image fallback gated on stream integrity**: a `partial_image` frame is only accepted as the result when the stream terminated normally with `response.completed`; truncated streams now error instead of saving a preview.
- Broader token redaction (case-insensitive keys, `key=value` and single-quoted encodings, bare JWTs, recursive dict redaction), redacted `AuthFile` repr, and `--verbose` server-derived strings routed through the redactor.
- `Retry-After` honored on retryable HTTP errors; DNS/connection/timeout failures produce clean redacted errors instead of raw tracebacks.
- Codex CLI version detection now fails closed with an actionable error instead of impersonating a stale hardcoded version when `codex --version` is unavailable.
- Bundled `remove_chroma_key.py` now ships with the full Apache-2.0 license text (`LICENSES/Apache-2.0.txt`) and an SPDX provenance header, as its license requires.
- `references/transparent-image-tips.md` no longer presents the internal `--despill` option as a user-facing flag.
- `references/api-recipe.md` explains the orchestrator-vs-image-model naming (`gpt-5.5` on the wire, `gpt-image-2` doing the image) and how `--format webp` really works (PNG on the wire, local Pillow conversion).
- README env-var list now matches the five vars `generate.py` actually reads; bug-report template no longer references a `.captures/` dir that was never implemented.

## [0.1.3] - 2026-05-04

### Removed

- `docs/design.md` and `docs/plan.md` — internal process artifacts from the brainstorm/plan/build cycle. The implementation, `SKILL.md`, `references/`, and the test suite are the contract going forward.

### Fixed

- Scrubbed personal absolute paths (`/Users/.../sandbox/codex-research/...`) from `README.md` that referenced internal-only research output. Public-facing docs no longer leak local filesystem layout.
- `README.md`, `CONTRIBUTING.md`, and the `.github/` templates updated to point at the surviving in-repo references (`SKILL.md`, `references/`, `tests/`) instead of the now-deleted `docs/`.

## [0.1.2] - 2026-05-04

### Fixed

- `--whoami` token expiry now reads from `access_token` (the credential the API actually validates), not `id_token` (which can rotate independently).
- CI markdownlint failures: blank lines around headings/lists in CHANGELOG, top-level heading in PR template.

### CI

- Bumped `actions/checkout` to v5 and `actions/setup-python` to v6 (Node.js 20 deprecation).
- markdownlint MD024 set to `siblings_only` to allow standard Keep-a-Changelog repeated `### Added` / `### Fixed` headings.

## [0.1.1] - 2026-05-04

### Fixed

- Sidecar metadata now stores the user's original `--input` ref (path/URL) instead of the expanded data URL — prevents `last.json` and per-image `.json` files from bloating with base64 image content.
- `--transparent + --format jpeg` is now rejected before the API call (was rejected after a paid POST).
- Empty-SSE retry on the second call now goes through the normal HTTP error handler (401/429/network produce a clean error, not a raw exception).
- `pick_key_color` now picks a candidate that conflicts with NEITHER green nor magenta when both are mentioned (was picking magenta on conflict).
- SSE idle timeout is 300s per spec (was 360s); `TimeoutError` is no longer retried.

### Documentation

- README Status section updated to reflect the v0.1.0 release.
- SECURITY.md: removed false claim about MD5 verification of the bundled chroma-key script; integrity is enforced by git history.
- SKILL.md: Adobe MCP dispatch now has explicit two-step instructions ("`--bg-tool=none` first, then call MCP").

## [0.1.0] - 2026-05-04

### Added

- `/codex-image <prompt>` slash command via SKILL.md
- All seven `gpt-image-2` resolutions plus custom `WxH`
- Output formats: PNG, JPEG (server `output_compression`), WebP (local Pillow conversion)
- `--input <path|url|data:>` for edit mode (up to 5 references)
- `--from-last` for multi-turn continuation
- `--transparent` with bundled `remove_chroma_key.py` (chroma fallback) and Adobe MCP dispatch (Claude-orchestrated)
- `--whoami` and first-use account banner (6h TTL, resets on workspace change)
- `--verbose` mode with token redaction guarantees
- Read-only auth from discovery chain (`$CODEX_HOME` → `$CHATGPT_LOCAL_HOME` → `~/.codex` → `~/.chatgpt-local`)
- Per-image sidecar JSON + `~/.codex-image/last.json` pointer
- Retry on 5xx + network with exponential backoff + jitter
- Empty-SSE recovery: drop refs and retry once
- `references/api-recipe.md`, `prompting-cookbook.md`, `transparent-image-tips.md`
- Security: auth.json permission warning, `set -x` ban scan, HTTP-error body redaction
- CI lint workflow (shellcheck + ruff + markdownlint)
- `tests/smoke.sh` end-to-end smoke test against real Codex auth

### Fixed

- Plain `--format webp` (without `--transparent`) no longer applies the
  chroma-key prompt suffix or prints the transparency workaround warning
  (regression caught by smoke run; covered by
  `test_plain_webp_does_not_apply_chroma_key`).

[Unreleased]: https://github.com/nuko-nova-dynamics/codex-image/compare/v0.1.5...HEAD
[0.1.5]: https://github.com/nuko-nova-dynamics/codex-image/releases/tag/v0.1.5
[0.1.4]: https://github.com/nuko-nova-dynamics/codex-image/releases/tag/v0.1.4
