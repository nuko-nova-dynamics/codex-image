"""Per-image JSON sidecar + ~/.codex-image/last.json pointer.

Spec §9: write both by default; --no-meta skips both AND does not advance the pointer.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class GenerationRecord:
    image_path: str
    prompt: str
    revised_prompt: str
    size: str
    quality: str
    format: str
    is_transparent: bool
    input_image: str | None
    response_id: str
    ts: str
    account_id: str


def write_record(
    record: GenerationRecord,
    last_json_path: Path,
    *,
    per_image: bool = True,
    update_last: bool = True,
) -> None:
    """Write per-image sidecar (next to image) and/or update last.json pointer.

    --no-meta in the CLI maps to per_image=False, update_last=False.
    """
    payload = asdict(record)
    if per_image:
        image = Path(record.image_path)
        sidecar = image.with_suffix(image.suffix + ".json")
        sidecar.write_text(json.dumps(payload, indent=2))
    if update_last:
        last_json_path.parent.mkdir(parents=True, exist_ok=True)
        last_json_path.write_text(json.dumps(payload, indent=2))


def load_last(last_json_path: Path) -> dict | None:
    """Return last.json content, or None if missing / invalid / referenced image gone."""
    if not last_json_path.exists():
        return None
    try:
        data = json.loads(last_json_path.read_text())
    except json.JSONDecodeError:
        return None
    image_path = data.get("image_path")
    if not image_path or not Path(image_path).exists():
        return None
    return data
