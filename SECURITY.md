# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability, please **do not** open a public GitHub issue. Instead, use GitHub's private vulnerability reporting: [**Security → Report a vulnerability**](https://github.com/nuko-nova-dynamics/codex-image/security/advisories/new).

Expect an initial acknowledgement within 72 hours.

## What's in scope

- Anything that could cause the skill to leak the user's `~/.codex/auth.json` access token, refresh token, or `id_token`
- Anything that lets a crafted prompt or input image execute arbitrary shell commands
- Anything that exfiltrates other files outside the configured `--out-dir`
- Path traversal in `--input` or `--out` handling
- Misuse of the bundled `remove_chroma_key.py` to read or write outside the intended file pair

## What's out of scope

- The behavior of the upstream OpenAI / Codex backend
- The behavior of `~/.codex/auth.json` itself (managed by Codex CLI, not by this skill)
- Local privilege escalation that requires the user to already have write access to their own home directory
- Attacks that require the attacker to already control the user's shell / Claude Code session

## Defensive practices already documented in the design

- Auth file is read-only — the skill never writes back to `~/.codex/auth.json`
- Token never echoed to logs or stdout (only its length and expiry, never the value)
- Input reference paths (`--input`, `--from-last`) are resolved to real paths before use; output paths are user-controlled by design (`--out` / `--out-dir`)
- Bundled `remove_chroma_key.py` is committed verbatim from openai/codex (Apache 2.0) with a provenance header; integrity is enforced by git history

These promises are enforced by the implementation and covered by the test suite (`tests/test_security.py`, `tests/test_redact.py`).
