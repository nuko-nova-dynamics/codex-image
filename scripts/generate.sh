#!/usr/bin/env bash
# generate.sh — entrypoint invoked by SKILL.md / users.
# Delegates everything to scripts/generate.py.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/generate.py" "$@"
