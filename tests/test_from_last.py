from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import images_response


def _setup_auth(fixture_dir: Path, monkeypatch, tmp_path: Path):
    home = tmp_path / "fake-codex-home"
    home.mkdir()
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))


def test_from_last_uses_last_pointer(tmp_path, fixture_dir, monkeypatch):
    import generate
    _setup_auth(fixture_dir, monkeypatch, tmp_path)

    prior = tmp_path / "prior.png"
    prior.write_bytes(b"\x89PNG\r\n\x1a\nold")
    last = tmp_path / ".codex-image" / "last.json"
    last.parent.mkdir(parents=True, exist_ok=True)
    last.write_text(json.dumps({"image_path": str(prior), "prompt": "old"}))

    captured = {}
    def fake_post(*, body, headers, endpoint=None, timeout=None):
        captured["body"] = body
        captured["endpoint"] = endpoint
        return images_response()
    monkeypatch.setattr(generate, "post_images", fake_post)

    result = generate.main([
        "now make it green", "--from-last",
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    assert result == 0
    assert captured["endpoint"].endswith("/images/edits")
    assert len(captured["body"]["images"]) == 1
    assert captured["body"]["images"][0]["image_url"].startswith("data:image/png;base64,")


def test_from_last_errors_when_no_pointer(tmp_path, fixture_dir, monkeypatch, capsys):
    import generate
    _setup_auth(fixture_dir, monkeypatch, tmp_path)

    result = generate.main(["x", "--from-last", "--out-dir", str(tmp_path / "out")])
    captured = capsys.readouterr()
    assert result != 0
    assert "no last image" in captured.err.lower() or "from-last" in captured.err.lower()


def test_from_last_errors_when_pointer_image_missing(tmp_path, fixture_dir, monkeypatch, capsys):
    import generate
    _setup_auth(fixture_dir, monkeypatch, tmp_path)

    last = tmp_path / ".codex-image" / "last.json"
    last.parent.mkdir(parents=True, exist_ok=True)
    last.write_text(json.dumps({"image_path": str(tmp_path / "vanished.png"), "prompt": "x"}))

    result = generate.main(["x", "--from-last", "--out-dir", str(tmp_path / "out")])
    err = capsys.readouterr().err.lower()
    assert result != 0
    assert "no last image" in err or "missing" in err


def test_from_last_combines_with_input(tmp_path, fixture_dir, monkeypatch):
    import generate
    _setup_auth(fixture_dir, monkeypatch, tmp_path)

    prior = tmp_path / "prior.png"
    prior.write_bytes(b"\x89PNG\r\n\x1a\nA")
    extra = tmp_path / "extra.png"
    extra.write_bytes(b"\x89PNG\r\n\x1a\nB")
    last = tmp_path / ".codex-image" / "last.json"
    last.parent.mkdir(parents=True, exist_ok=True)
    last.write_text(json.dumps({"image_path": str(prior), "prompt": "x"}))

    captured = {}
    def fake_post(*, body, headers, endpoint=None, timeout=None):
        captured["body"] = body
        captured["endpoint"] = endpoint
        return images_response()
    monkeypatch.setattr(generate, "post_images", fake_post)

    result = generate.main([
        "merge them", "--from-last", "--input", str(extra),
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    assert result == 0
    assert len(captured["body"]["images"]) == 2


def test_combined_refs_exceeding_16_errors(tmp_path, fixture_dir, monkeypatch, capsys):
    import generate
    _setup_auth(fixture_dir, monkeypatch, tmp_path)

    prior = tmp_path / "prior.png"
    prior.write_bytes(b"\x89PNG\r\n\x1a\n")
    last = tmp_path / ".codex-image" / "last.json"
    last.parent.mkdir(parents=True, exist_ok=True)
    last.write_text(json.dumps({"image_path": str(prior), "prompt": "x"}))

    extras = []
    for i in range(16):
        e = tmp_path / f"r{i}.png"
        e.write_bytes(b"\x89PNG\r\n\x1a\n")
        extras += ["--input", str(e)]

    result = generate.main([
        "x", "--from-last", *extras, "--out-dir", str(tmp_path / "out"),
    ])
    assert result != 0
    assert "max is 16" in capsys.readouterr().err.lower()


def test_combined_16_refs_pass_local_validation(tmp_path, fixture_dir, monkeypatch):
    import generate
    _setup_auth(fixture_dir, monkeypatch, tmp_path)

    prior = tmp_path / "prior.png"
    prior.write_bytes(b"\x89PNG\r\n\x1a\n")
    last = tmp_path / ".codex-image" / "last.json"
    last.parent.mkdir(parents=True, exist_ok=True)
    last.write_text(json.dumps({"image_path": str(prior), "prompt": "x"}))

    extras = []
    for i in range(15):
        ref = tmp_path / f"r{i}.png"
        ref.write_bytes(b"\x89PNG\r\n\x1a\n")
        extras += ["--input", str(ref)]

    captured = {}

    def fake_post(*, body, headers, endpoint=None, timeout=None):
        captured["body"] = body
        captured["endpoint"] = endpoint
        return images_response()

    monkeypatch.setattr(generate, "post_images", fake_post)

    result = generate.main([
        "x", "--from-last", *extras,
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    assert result == 0
    assert len(captured["body"]["images"]) == 16
