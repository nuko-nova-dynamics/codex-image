from __future__ import annotations

import generate
import pytest


def _parse(*args):
    return generate.parse_args(list(args))


def test_orchestrator_is_unpinned(monkeypatch):
    assert _parse("x").orchestrator is None
    assert _parse("x", "--orchestrator", "any-future-model").orchestrator == "any-future-model"
    monkeypatch.setenv("CODEX_IMAGE_ORCHESTRATOR", "from-env")
    assert _parse("x").orchestrator == "from-env"


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

    generate.main(["x", "--orchestrator", "explicit-model", "--effort", "low",
                   "--moderation", "low", "--background", "auto",
                   "--out-dir", str(tmp_path / "out"), "--quality", "low"])
    body = captured["body"]
    assert body["model"] == "explicit-model"
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


def _run_capturing_model(tmp_path, fixture_dir, monkeypatch, *extra):
    import base64
    home = tmp_path / "codex-home"
    home.mkdir(exist_ok=True)
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / "state"))
    fake_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
    captured = {}

    def fake_post(*, body, headers, **kw):
        captured["model"] = body["model"]
        return ('event: response.output_item.done\ndata: {"type":"response.output_item.done",'
                f'"item":{{"type":"image_generation_call","result":"{fake_b64}"}}}}\n\n')

    monkeypatch.setattr(generate, "post_responses", fake_post)
    monkeypatch.setattr(generate, "_detect_codex_cli_version", lambda: "0.200.0-alpha.3")
    rc = generate.main(["x", "--out-dir", str(tmp_path / "out"), *extra])
    return rc, captured.get("model"), home


def test_default_orchestrator_comes_from_codex_catalog(tmp_path, fixture_dir, monkeypatch):
    rc, model, _ = _run_capturing_model(tmp_path, fixture_dir, monkeypatch)
    assert rc == 0
    assert model == "gpt-catalog-default"


def test_cache_is_used_when_catalog_request_fails(tmp_path, fixture_dir, monkeypatch):
    import json
    import urllib.error

    def offline(**kw):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(generate, "fetch_models", offline)
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "models_cache.json").write_text(json.dumps({"client_version": "0.200.0", "models": [
        {"slug": "cached-default", "priority": 1, "visibility": "list"}]}))
    rc, model, _ = _run_capturing_model(tmp_path, fixture_dir, monkeypatch)
    assert rc == 0
    assert model == "cached-default"


def test_cache_from_another_codex_version_is_ignored(tmp_path, fixture_dir, monkeypatch, capsys):
    import http.client
    import json

    def truncated(**kw):
        raise http.client.IncompleteRead(b"")

    monkeypatch.setattr(generate, "fetch_models", truncated)
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "models_cache.json").write_text(json.dumps({"client_version": "0.150.0", "models": [
        {"slug": "retired-model", "priority": 1, "visibility": "list"}]}))
    rc, model, _ = _run_capturing_model(tmp_path, fixture_dir, monkeypatch)
    assert rc == 1
    assert model is None
    assert "--orchestrator" in capsys.readouterr().err


def test_catalog_request_uses_whole_codex_version():
    assert generate._whole_version("0.144.0-alpha.4") == "0.144.0"
    assert generate._whole_version("0.163.0") == "0.163.0"


def test_no_catalog_and_no_cache_fails_before_posting(tmp_path, fixture_dir, monkeypatch, capsys):
    import urllib.error

    def offline(**kw):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(generate, "fetch_models", offline)
    rc, model, _ = _run_capturing_model(tmp_path, fixture_dir, monkeypatch)
    assert rc == 1
    assert model is None
    assert "--orchestrator" in capsys.readouterr().err


def test_expired_token_on_catalog_says_to_log_in(tmp_path, fixture_dir, monkeypatch, capsys):
    import io
    import urllib.error

    def expired(**kw):
        raise urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b"token_expired"))

    monkeypatch.setattr(generate, "fetch_models", expired)
    rc, model, _ = _run_capturing_model(tmp_path, fixture_dir, monkeypatch)
    err = capsys.readouterr().err
    assert rc == 1
    assert model is None
    assert "HTTP 401" in err
    assert "codex login" in err


def test_network_failure_reason_is_reported(tmp_path, fixture_dir, monkeypatch, capsys):
    import urllib.error

    def no_dns(**kw):
        raise urllib.error.URLError("[Errno 8] nodename nor servname provided")

    monkeypatch.setattr(generate, "fetch_models", no_dns)
    rc, _, _ = _run_capturing_model(tmp_path, fixture_dir, monkeypatch)
    err = capsys.readouterr().err
    assert rc == 1
    assert "URLError: [Errno 8] nodename nor servname provided" in err


def test_provider_route_needs_no_chatgpt_sign_in(tmp_path, monkeypatch):
    import base64
    import json

    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text(
        'model_provider = "proxy"\nmodel = "gpt-6-astra"\n'
        '[model_providers.proxy]\nbase_url = "http://127.0.0.1:8317/v1"\n'
        'experimental_bearer_token = "k-test"\nwire_api = "responses"\n')
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(generate, "fetch_models", lambda **kw: [
        {"slug": s} for s in ("gpt-6-astra", "gpt-6.1-sol", "gpt-6-sol", "gpt-sol-latest")])
    fake_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
    captured = {}

    def fake_post(*, body, headers, endpoint, **kw):
        captured.update(model=body["model"], endpoint=endpoint, auth=headers.get("Authorization"))
        return ('event: response.output_item.done\ndata: {"type":"response.output_item.done",'
                f'"item":{{"type":"image_generation_call","result":"{fake_b64}"}}}}\n\n')

    monkeypatch.setattr(generate, "post_responses", fake_post)
    target = tmp_path / "out.png"
    assert generate.main(["x", "--out", str(target)]) == 0
    assert captured == {"model": "gpt-6.1-sol",
                        "endpoint": "http://127.0.0.1:8317/v1/responses",
                        "auth": "Bearer k-test"}
    assert json.loads(target.with_suffix(".png.json").read_text())["account_id"] == "provider:proxy"
