"""Output post-processing: passthrough for png/jpeg, Pillow PNG→WebP for webp."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Literal


class PostprocessError(Exception):
    pass


def convert_png_to_webp(src: Path, dst: Path, *, quality: int = 80) -> None:
    """Convert a PNG file to WebP via Pillow.

    Preserves alpha channel. Raises PostprocessError on missing Pillow.
    """
    try:
        from PIL import Image
    except ImportError as e:
        raise PostprocessError(
            "Pillow is required for --format webp. "
            "Install: pip install Pillow"
        ) from e

    with Image.open(src) as img:
        img.save(dst, format="WEBP", quality=quality, method=6)


def save_image(
    *,
    raw_bytes: bytes,
    target_path: Path,
    format: Literal["png", "jpeg", "webp"],
    webp_quality: int = 80,
) -> None:
    """Persist server bytes to disk in the requested format.

    - png/jpeg: write raw bytes (server already produced them).
    - webp: server returned PNG (we requested it that way); convert locally.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if format in ("png", "jpeg"):
        target_path.write_bytes(raw_bytes)
        return

    if format == "webp":
        try:
            from PIL import Image
        except ImportError as e:
            raise PostprocessError(
                "Pillow is required for --format webp. "
                "Install: pip install Pillow"
            ) from e
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img.save(target_path, format="WEBP", quality=webp_quality, method=6)
        return

    raise PostprocessError(f"unsupported format {format!r}")
