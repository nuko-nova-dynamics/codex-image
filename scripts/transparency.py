"""Chroma-key transparency workflow (spec §8).

Per architecture rule: shell does chroma/none; Adobe MCP routing is Claude's
responsibility via SKILL.md. This module only handles the chroma path.
"""
from __future__ import annotations

import re

CHROMA_TEMPLATE = (
    "Create the subject on a perfectly flat solid {key} chroma-key background "
    "for background removal. The background must be one uniform color with no "
    "shadows, gradients, texture, reflections, floor plane, or lighting variation. "
    "Keep the subject fully separated with crisp edges and generous padding. "
    "Do not use {key} anywhere in the subject; no cast shadow, no contact shadow, "
    "no reflection, no watermark, and no text."
)

_GREEN_WORDS = re.compile(
    r"\b(green|grass|leaf|leaves|forest|moss|fern|monstera|emerald|lime)\b",
    re.IGNORECASE,
)
_MAGENTA_WORDS = re.compile(
    r"\b(pink|magenta|rose|fuchsia|coral|salmon)\b",
    re.IGNORECASE,
)
_CYAN_WORDS = re.compile(
    r"\b(cyan|turquoise|teal)\b",
    re.IGNORECASE,
)


class ChromaKeyError(Exception):
    pass


def pick_key_color(prompt: str) -> str:
    """Pick a chroma key likely to not appear in the subject (spec §8).

    When the prompt mentions multiple color families, prefer the candidate
    that matches NONE of them. If all three families appear, fall back to
    green and let warn_subject_key_conflict surface the residual clash.
    """
    has_green = bool(_GREEN_WORDS.search(prompt))
    has_magenta = bool(_MAGENTA_WORDS.search(prompt))
    has_cyan = bool(_CYAN_WORDS.search(prompt))
    # Try each candidate in order; pick the first one whose family is absent.
    for candidate, conflict in [
        ("#00ff00", has_green),
        ("#ff00ff", has_magenta),
        ("#00ffff", has_cyan),
    ]:
        if not conflict:
            return candidate
    # All three families present — fall back to green (spec §8 default).
    return "#00ff00"


def apply_chroma_key_suffix(prompt: str, key_color: str) -> str:
    """Append the chroma-key template to the user prompt."""
    return f"{prompt}. {CHROMA_TEMPLATE.format(key=key_color)}"


def warn_subject_key_conflict(prompt: str, key_color: str) -> str | None:
    """Return a warning string if the prompt's subject color overlaps the key.

    Returns None when no clash is detected.
    """
    key = key_color.lower()
    if key == "#00ff00" and _GREEN_WORDS.search(prompt):
        return "subject mentions green and key is #00ff00; consider --key-color #ff00ff"
    if key == "#ff00ff" and _MAGENTA_WORDS.search(prompt):
        return "subject mentions pink/magenta and key is #ff00ff; consider --key-color #00ffff"
    if key == "#00ffff" and _CYAN_WORDS.search(prompt):
        return "subject mentions cyan/turquoise and key is #00ffff; consider --key-color #00ff00"
    return None


def pillow_available() -> bool:
    """Check Pillow without importing it persistently."""
    try:
        from PIL import Image  # noqa: F401
        return True
    except ImportError:
        return False


def require_pillow_or_die(reason: str) -> None:
    """Spec §8 preflight: never spend a paid API call when post-process can't run."""
    if pillow_available():
        return
    raise ChromaKeyError(
        f"Pillow is required for {reason}. "
        "Install: pip install Pillow  (or: pipx install Pillow). "
        "Skipping the API call to avoid spending a generation on a post-process that won't run."
    )
