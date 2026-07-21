# Pull Request

## What this changes

<!-- One-sentence summary -->

## Why

<!-- Link the issue or describe the user need -->

Fixes #

## Testing

- [ ] `shellcheck scripts/*.sh` is clean
- [ ] `ruff check scripts/` is clean
- [ ] Manual smoke test with `/codex-image "test prompt"` succeeds
- [ ] If touching auth: tested with valid token, expired token, and missing auth.json
- [ ] If touching transparency: tested with at least one hard case (fur, smoke, glass)

## Notes for reviewer

<!-- Anything non-obvious, alternative approaches considered, or known limitations -->

## Checklist

- [ ] Updated `CHANGELOG.md` under `[Unreleased]`
- [ ] Updated `SKILL.md` / `README.md` / `references/` if behavior changed
- [ ] No tokens, account IDs, or PII in commits
- [ ] Conventional Commit message
