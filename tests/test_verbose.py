from __future__ import annotations

import re

from sse_parser import extract_response_metadata


def test_extract_metadata_pulls_revised_prompt(fixture_dir):
    raw = (fixture_dir / "sse_completed.txt").read_text()
    meta = extract_response_metadata(raw)
    assert meta["response_id"] == "resp_1"
    assert meta["revised_prompt"] == "A red circle"
    assert meta["resolved_size"] == "1024x1024"


def test_verbose_output_contains_no_token_substrings(tmp_path, fixture_dir, monkeypatch, capsys):
    """Smoke: --verbose dump must redact any access_token / refresh_token / Bearer."""
    import generate

    home = tmp_path / "fake-codex-home"
    home.mkdir()
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    import base64
    fake_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
    monkeypatch.setattr(generate, "post_responses", lambda **kw:
        f'event: response.created\ndata: {{"type":"response.created","response":{{"id":"r"}}}}\n\n'
        f'event: response.output_item.done\ndata: {{"type":"response.output_item.done","item":{{"id":"i","type":"image_generation_call","status":"completed","result":"{fake_b64}","revised_prompt":"X","quality":"medium","size":"1024x1024","output_format":"png","background":"opaque","action":"generate"}}}}\n\n'
    )

    result = generate.main([
        "x", "--verbose", "--quality", "low",
        "--out-dir", str(tmp_path / "out"),
    ])
    assert result == 0
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # Validate redaction: none of the secret prefixes should leak
    assert "Bearer eyJ" not in combined
    forbidden = re.compile(r"(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")
    assert not forbidden.search(combined), f"JWT-like substring leaked: {forbidden.search(combined).group()}"
