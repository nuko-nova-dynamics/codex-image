from __future__ import annotations

import base64

import pytest
from input_refs import InputRefError, resolve_to_data_url


def test_resolve_passes_through_data_url():
    url = "data:image/png;base64,QUFBQQ=="
    assert resolve_to_data_url(url) == url


def test_resolve_passes_through_http_url():
    url = "https://example.com/img.png"
    assert resolve_to_data_url(url) == url


def test_resolve_local_png_to_data_url(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nDATA")
    out = resolve_to_data_url(str(img))
    assert out.startswith("data:image/png;base64,")
    decoded = base64.b64decode(out.split(",", 1)[1])
    assert decoded.startswith(b"\x89PNG")


def test_resolve_local_jpeg(tmp_path):
    img = tmp_path / "x.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0FAKE")
    out = resolve_to_data_url(str(img))
    assert out.startswith("data:image/jpeg;base64,")


def test_resolve_missing_file_raises(tmp_path):
    with pytest.raises(InputRefError, match="not found"):
        resolve_to_data_url(str(tmp_path / "missing.png"))


def test_resolve_unsupported_extension_raises(tmp_path):
    bad = tmp_path / "x.txt"
    bad.write_text("hi")
    with pytest.raises(InputRefError, match="unsupported"):
        resolve_to_data_url(str(bad))


def test_resolve_oversized_raises(tmp_path):
    huge = tmp_path / "huge.png"
    huge.write_bytes(b"\x89PNG" + b"\x00" * (51 * 1024 * 1024))
    with pytest.raises(InputRefError, match="too large"):
        resolve_to_data_url(str(huge))
