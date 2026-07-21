"""Filename composition for generated images.

Pattern: YYYY-MM-DD-HHMM-<slug>.<ext>  (UTC).
Slug = first 6 words of prompt, [a-z0-9]-only, max 40 chars, fallback "image".
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

_EXT_MAP = {"png": "png", "jpeg": "jpg", "jpg": "jpg", "webp": "webp"}


def slugify(prompt: str) -> str:
    """Slugify a prompt per spec §9. Returns 'image' on empty result.

    Rules:
    - lowercase, split on whitespace, take first 6 words
    - drop any word containing a non-ASCII character (so "café" / emoji vanish)
    - within each remaining word, strip everything that isn't [a-z0-9]
    - drop words that became empty, join survivors with "-"
    - truncate to 40 chars, strip trailing "-", fall back to "image"
    """
    lowered = prompt.lower()
    cleaned: list[str] = []
    for word in lowered.split()[:6]:
        if any(ord(c) > 127 for c in word):
            continue
        stripped = re.sub(r"[^a-z0-9]", "", word)
        if stripped:
            cleaned.append(stripped)
    slug = "-".join(cleaned)[:40].strip("-")
    return slug or "image"


def output_filename(prompt: str, fmt: str, now: datetime | None = None) -> str:
    """Return the canonical filename for a generation."""
    if now is None:
        now = datetime.now(timezone.utc)
    ext = _EXT_MAP.get(fmt.lower(), fmt.lower())
    return f"{now.strftime('%Y-%m-%d-%H%M')}-{slugify(prompt)}.{ext}"


def resolve_collision(path: Path) -> Path:
    """If `path` exists, return a numeric-suffix variant (...-2, ...-3, ...).

    Numeric suffix scans up to 9999 then raises FileExistsError as a guardrail.
    """
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    n = 2
    while n < 10_000:
        candidate = parent / f"{stem}-{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1
    raise FileExistsError(f"too many collisions for {path} (10000+ files share this stem)")
