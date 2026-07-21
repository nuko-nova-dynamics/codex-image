# Contributing

Thanks for considering a contribution. The skill is shipped (v0.1.x); the most useful contributions are bug reports, cross-CLI compatibility fixes, and improvements to `SKILL.md` / `references/`.

## Reporting bugs

Open an issue using the bug report template. Include:

- Claude Code version (`claude --version`)
- Codex CLI version (`codex --version`)
- Output of `/codex-image --whoami --verbose`
- The exact prompt + flags that reproduced the issue
- Expected vs actual behavior

## Proposing changes

1. Open an issue with the "feature request" template before writing code — alignment first
2. Fork and create a topic branch: `git checkout -b feat/short-description`
3. Run linters: `shellcheck scripts/*.sh && ruff check scripts/`
4. Submit a PR using the template; reference the issue

## Development workflow

```bash
git clone https://github.com/nuko-nova-dynamics/codex-image
cd codex-image

# Symlink into your agent's skill dir to test (Claude Code shown;
# use ~/.agents/skills, ~/.opencode/skills, etc. for other agents)
ln -s "$(pwd)" ~/.claude/skills/codex-image

# Sign into Codex
codex login

# Iterate
$EDITOR SKILL.md scripts/generate.sh
# (changes are picked up immediately via the symlink)
```

## Code style

- **Bash:** `shellcheck`-clean, `set -euo pipefail` on every script, no command substitution in conditionals
- **Python:** `ruff`-clean, type hints on all functions, no `print` outside the entrypoint
- **Markdown:** one sentence per line in long-form docs (so diffs are clean)

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat: add --quality-webp flag`
- `fix: handle missing tokens.account_id field`
- `docs: clarify chroma-key fallback behavior`
- `chore: bump shellcheck to 0.10.0`
- `refactor: split api_client into auth + transport`

## Cross-CLI compatibility

Primary target is Claude Code. Cross-CLI patches (Codex CLI, opencode, Pi, Gemini CLI) are welcome but should:

- Not regress Claude Code behavior
- Add CLI-specific notes to the README "Other CLIs" section
- Include a manual test note in the PR description (e.g., "tested on Codex CLI v0.128.0")

## Code of conduct

Be kind. Be specific. Disagree on substance, not people.
