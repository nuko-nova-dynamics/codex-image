from __future__ import annotations

import json

import pytest
from sidecar import (
    GenerationRecord,
    load_last,
    write_record,
)


@pytest.fixture
def record():
    return GenerationRecord(
        image_path="/tmp/foo.png",
        prompt="a coffee mug",
        revised_prompt="A photorealistic coffee mug",
        size="1024x1024",
        quality="medium",
        format="png",
        is_transparent=False,
        input_image=None,
        response_id="resp_abc",
        ts="2026-05-04T13:08:42Z",
        account_id="aaaa-bbbb",
    )


def test_write_record_creates_per_image_sidecar(tmp_path, record):
    image = tmp_path / "img.png"
    image.touch()
    record.image_path = str(image)
    write_record(record, last_json_path=tmp_path / "last.json", per_image=True)
    sidecar = image.with_suffix(".png.json")
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["prompt"] == "a coffee mug"
    assert data["account_id"] == "aaaa-bbbb"


def test_write_record_updates_last_json(tmp_path, record):
    image = tmp_path / "img.png"
    image.touch()
    record.image_path = str(image)
    last_path = tmp_path / "last.json"
    write_record(record, last_json_path=last_path, per_image=True)
    last = json.loads(last_path.read_text())
    assert last["image_path"] == str(image)
    assert last["prompt"] == "a coffee mug"


def test_write_record_no_meta_skips_both(tmp_path, record):
    image = tmp_path / "img.png"
    image.touch()
    record.image_path = str(image)
    last_path = tmp_path / "last.json"
    write_record(record, last_json_path=last_path, per_image=False, update_last=False)
    assert not image.with_suffix(".png.json").exists()
    assert not last_path.exists()


def test_write_record_no_meta_preserves_existing_last(tmp_path, record):
    """--no-meta does not advance the pointer, even if last.json already exists."""
    image = tmp_path / "img.png"
    image.touch()
    record.image_path = str(image)
    last_path = tmp_path / "last.json"
    last_path.write_text('{"image_path":"/tmp/older.png","prompt":"older"}')
    write_record(record, last_json_path=last_path, per_image=False, update_last=False)
    assert json.loads(last_path.read_text())["prompt"] == "older"


def test_load_last_returns_none_when_absent(tmp_path):
    assert load_last(tmp_path / "last.json") is None


def test_load_last_returns_record(tmp_path, record):
    image = tmp_path / "img.png"
    image.touch()
    record.image_path = str(image)
    last_path = tmp_path / "last.json"
    write_record(record, last_json_path=last_path, per_image=False)
    loaded = load_last(last_path)
    assert loaded is not None
    assert loaded["image_path"] == str(image)


def test_load_last_returns_none_when_referenced_image_missing(tmp_path, record):
    """If last.json points to a now-missing image, treat as no pointer."""
    record.image_path = str(tmp_path / "vanished.png")  # no touch
    last_path = tmp_path / "last.json"
    write_record(record, last_json_path=last_path, per_image=False)
    assert load_last(last_path) is None
