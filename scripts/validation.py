"""Argument validation per spec §6 (size, compression ranges)."""
from __future__ import annotations

import re

_SIZE_RE = re.compile(r"^(\d+)x(\d+)$")


class SizeError(ValueError):
    pass


def validate_size(value: str) -> str:
    """Accept the 7 official presets, 'auto', or custom WxH meeting all constraints.

    Constraints (spec §6, §4):
    - Both edges multiple of 16
    - Max edge ≤ 3840 px
    - Long edge / short edge ratio ≤ 3:1
    """
    if value == "auto":
        return value
    m = _SIZE_RE.match(value)
    if not m:
        raise SizeError(
            f"--size: invalid format {value!r}; expected WxH (e.g. 1024x1024) or 'auto'"
        )
    w, h = int(m.group(1)), int(m.group(2))
    if w % 16 != 0 or h % 16 != 0:
        raise SizeError(f"--size {value}: both edges must be a multiple of 16")
    if max(w, h) > 3840:
        raise SizeError(f"--size {value}: max edge must be ≤ 3840 px (got {max(w, h)})")
    long_edge, short_edge = max(w, h), min(w, h)
    if long_edge > 3 * short_edge:
        raise SizeError(f"--size {value}: aspect ratio must be ≤ 3:1 (got {long_edge}:{short_edge})")
    return value


def validate_compression(value: int, flag_name: str) -> int:
    if not (0 <= value <= 100):
        raise ValueError(f"{flag_name}: must be in 0-100 (got {value})")
    return value
