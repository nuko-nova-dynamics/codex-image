"""Output post-processing: PNG passthrough, Pillow PNG→JPEG/WebP conversion."""
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


def _is_png(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def save_image(
    *,
    raw_bytes: bytes,
    target_path: Path,
    format: Literal["png", "jpeg", "webp"],
    webp_quality: int = 80,
    jpeg_quality: int = 90,
) -> None:
    """Persist server bytes to disk in the requested format.

    The Images API returns PNG whatever output_format is asked for, so png is
    written as-is and jpeg/webp are converted locally with Pillow. Bytes that
    are already in the target format (not PNG) are written unchanged.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if format == "png" or (format == "jpeg" and not _is_png(raw_bytes)):
        target_path.write_bytes(raw_bytes)
        return

    if format not in ("jpeg", "webp"):
        raise PostprocessError(f"unsupported format {format!r}")
    try:
        from PIL import Image
    except ImportError as e:
        raise PostprocessError(
            f"Pillow is required for --format {format}. "
            "Install: pip install Pillow"
        ) from e
    with Image.open(io.BytesIO(raw_bytes)) as img:
        if format == "webp":
            img.save(target_path, format="WEBP", quality=webp_quality, method=6)
        else:
            img.convert("RGB").save(target_path, format="JPEG", quality=jpeg_quality)
