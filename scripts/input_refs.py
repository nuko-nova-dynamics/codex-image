"""Resolve --input values (path | URL | data:) to a data URL the API accepts."""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

MAX_BYTES = 50 * 1024 * 1024  # 50 MB per spec
_ALLOWED_MIMES = {"image/png", "image/jpeg", "image/webp"}


class InputRefError(Exception):
    pass


def resolve_to_data_url(ref: str) -> str:
    """Convert a --input value into something the API can consume.

    - data: URL → returned as-is
    - http(s) URL → returned as-is (backend can fetch it)
    - local path → read, mime-sniff, base64 → data URL
    """
    if ref.startswith("data:"):
        return ref
    if ref.startswith("http://") or ref.startswith("https://"):
        return ref

    path = Path(ref).expanduser().resolve()
    if not path.is_file():
        raise InputRefError(f"--input file not found: {ref}")

    size = path.stat().st_size
    if size > MAX_BYTES:
        raise InputRefError(f"--input too large: {size:,} bytes (max {MAX_BYTES:,})")

    mime, _ = mimetypes.guess_type(path.name)
    if mime not in _ALLOWED_MIMES:
        raise InputRefError(
            f"--input unsupported file type {path.suffix!r}; allowed: png, jpeg, webp"
        )

    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"
