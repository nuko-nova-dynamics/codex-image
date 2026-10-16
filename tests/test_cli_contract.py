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
    # 0.2.0: accepted as a raw passthrough rather than rejected at parse time.
    # The backend refuses it; we surface that error instead of substituting a
    # different value behind the user's back. See docs/adr/0001.
    assert _parse("x", "--background", "transparent").background == "transparent"
    with pytest.raises(SystemExit):
        _parse("x", "--background", "translucent")


def test_transparent_mode_defaults_to_native():
    assert _parse("x").transparent_mode is None
    assert _parse("x", "--transparent-mode", "chroma").transparent_mode == "chroma"
    with pytest.raises(SystemExit):
        _parse("x", "--transparent-mode", "adobe")


def test_size_invalid_format_rejected_at_parse(capsys):
    with pytest.raises(SystemExit):
        _parse("x", "--size", "tiny")


def test_size_custom_wxh_accepted_when_valid():
    args = _parse("x", "--size", "1280x720")
    assert args.size == "1280x720"


def test_jpeg_compression_range_enforced(capsys):
    with pytest.raises(SystemExit):
        _parse("x", "--quality-jpeg", "150")


def test_high_quality_does_not_claim_fixed_cap(tmp_path, fixture_dir, monkeypatch, capsys):
    """A requested quality does not prove a fixed cap across models and plans."""
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
    assert "caps to medium" not in err.lower()
    assert "true high requires" not in err.lower()


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


@pytest.mark.parametrize("quality", ["xhigh", "max"])
def test_new_image_quality_choices(quality):
    assert _parse("x", "--quality", quality).quality == quality


@pytest.mark.parametrize("reported", ["gpt-image-2-codex", None, "gpt-image-2.5-flare"])
def test_requested_model_is_separate_from_observed(tmp_path, fixture_dir, monkeypatch, capsys, reported):
    import base64
    import json

    home = tmp_path / "auth"
    home.mkdir()
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / "state"))
    captured = {}

    def fake_post(*, body, headers, **kwargs):
        captured.update(body)
        response = {"tools": [{"type": "image_generation", "model": reported}]}
        item = {"type": "image_generation_call", "quality": "low",
                "result": base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()}
        return (f'event: response.created\ndata: {json.dumps({"type": "response.created", "response": response})}\n\n'
                f'event: response.output_item.done\ndata: {json.dumps({"type": "response.output_item.done", "item": item})}\n\n')

    monkeypatch.setattr(generate, "post_responses", fake_post)
    target = tmp_path / "out.png"
    assert generate.main(["x", "--image-model", "gpt-image-2.5-flare", "--quality", "max",
                          "--out", str(target)]) == 0
    assert captured["tools"][0]["model"] == "gpt-image-2.5-flare"
    assert captured["tools"][0]["quality"] == "max"
    record = json.loads(target.with_suffix(".png.json").read_text())
    assert record["requested_image_model"] == "gpt-image-2.5-flare"
    assert record["image_model"] == reported
    assert record["quality"] == "max"
    assert record["resolved_quality"] == "low"
    assert ("Requested model use is not verified" in capsys.readouterr().err) == (
        reported != "gpt-image-2.5-flare")
