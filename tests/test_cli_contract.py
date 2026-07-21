from __future__ import annotations

import generate
import pytest


def _parse(*args):
    return generate.parse_args(list(args))


def test_orchestrator_default_and_choices():
    assert _parse("x").orchestrator == "gpt-5.5"
    assert _parse("x", "--orchestrator", "gpt-5.4").orchestrator == "gpt-5.4"
    assert _parse("x", "--orchestrator", "gpt-5.4-mini").orchestrator == "gpt-5.4-mini"
    with pytest.raises(SystemExit):
        _parse("x", "--orchestrator", "gpt-7-imaginary")


def test_effort_default_xhigh_and_choices():
    assert _parse("x").effort == "xhigh"
    assert _parse("x", "--effort", "low").effort == "low"
    assert _parse("x", "--effort", "medium").effort == "medium"
    assert _parse("x", "--effort", "high").effort == "high"
    with pytest.raises(SystemExit):
        _parse("x", "--effort", "minimal")
    with pytest.raises(SystemExit):
        _parse("x", "--effort", "none")


def test_moderation_default_auto_and_choices():
    assert _parse("x").moderation == "auto"
    assert _parse("x", "--moderation", "low").moderation == "low"
    with pytest.raises(SystemExit):
        _parse("x", "--moderation", "off")


def test_background_default_opaque_and_choices():
    assert _parse("x").background == "opaque"
    assert _parse("x", "--background", "auto").background == "auto"
    with pytest.raises(SystemExit):
        _parse("x", "--background", "transparent")


def test_size_invalid_format_rejected_at_parse(capsys):
    with pytest.raises(SystemExit):
        _parse("x", "--size", "tiny")


def test_size_custom_wxh_accepted_when_valid():
    args = _parse("x", "--size", "1280x720")
    assert args.size == "1280x720"


def test_jpeg_compression_range_enforced(capsys):
    with pytest.raises(SystemExit):
        _parse("x", "--quality-jpeg", "150")


def test_high_quality_advisory_printed(tmp_path, fixture_dir, monkeypatch, capsys):
    """Spec §6: when user passes --quality high, the skill notes the OAuth cap."""
    home = tmp_path / "fake-codex-home"
    home.mkdir()
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    import base64
    fake_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
    monkeypatch.setattr(generate, "post_responses", lambda **kw:
        f'event: response.output_item.done\ndata: {{"type":"response.output_item.done","item":{{"id":"i","type":"image_generation_call","status":"completed","result":"{fake_b64}"}}}}\n\n'
    )

    rc = generate.main(["x", "--quality", "high", "--out-dir", str(tmp_path / "out")])
    assert rc == 0
    err = capsys.readouterr().err
    assert "caps to medium" in err.lower() or "capped to medium" in err.lower()


def test_orchestrator_passed_through_to_body(tmp_path, fixture_dir, monkeypatch):
    home = tmp_path / "fake-codex-home"
    home.mkdir()
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    import base64
    fake_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
    captured = {}
    def fake_post(*, body, headers, **kw):
        captured["body"] = body
        return f'event: response.output_item.done\ndata: {{"type":"response.output_item.done","item":{{"id":"i","type":"image_generation_call","status":"completed","result":"{fake_b64}"}}}}\n\n'
    monkeypatch.setattr(generate, "post_responses", fake_post)

    generate.main(["x", "--orchestrator", "gpt-5.4-mini", "--effort", "low",
                   "--moderation", "low", "--background", "auto",
                   "--out-dir", str(tmp_path / "out"), "--quality", "low"])
    body = captured["body"]
    assert body["model"] == "gpt-5.4-mini"
    assert body["reasoning"] == {"effort": "low"}
    tool = body["tools"][0]
    assert tool["moderation"] == "low"
    assert tool["background"] == "auto"


def test_missing_codex_cli_fails_closed(
    tmp_path, fixture_dir, monkeypatch, capsys
):
    import subprocess

    home = tmp_path / "fake-codex-home"
    home.mkdir()
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    def missing(*args, **kwargs):
        raise FileNotFoundError("codex")

    called = {"post": False}

    def post(**kwargs):
        called["post"] = True
        raise AssertionError("request must not be sent without a detected CLI version")

    monkeypatch.setattr(subprocess, "run", missing)
    monkeypatch.setattr(generate, "post_responses", post)

    result = generate.main([
        "x", "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    err = capsys.readouterr().err
    assert result != 0
    assert called["post"] is False
    assert "✗" in err
    assert "codex cli is required" in err.lower()
    assert "codex --version" in err.lower()


def test_unparseable_codex_cli_version_fails_closed(monkeypatch):
    import subprocess

    class Result:
        stdout = "codex-cli unknown\n"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Result())
    with pytest.raises(generate.CodexCliError, match="unrecognized version"):
        generate._detect_codex_cli_version()
