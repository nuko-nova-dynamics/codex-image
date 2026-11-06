from __future__ import annotations

import json

import generate
import pytest

from tests.conftest import images_response


def _parse(*args):
    return generate.parse_args(list(args))


def _chatgpt_home(tmp_path, fixture_dir, monkeypatch):
    home = tmp_path / "codex-home"
    home.mkdir(exist_ok=True)
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(generate, "_detect_codex_cli_version", lambda: "0.200.0")
    return home


def _provider_home(tmp_path, monkeypatch):
    home = tmp_path / "codex-home"
    home.mkdir(exist_ok=True)
    (home / "config.toml").write_text(
        'model_provider = "proxy"\nmodel = "gpt-6-astra"\n'
        '[model_providers.proxy]\nbase_url = "http://127.0.0.1:8317/v1"\n'
        'experimental_bearer_token = "k-test"\nwire_api = "responses"\n')
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / "state"))
    return home


def _capture_post(monkeypatch, response=None):
    captured = {}

    def fake_post(*, body, headers, endpoint, **kw):
        captured.update(body=body, endpoint=endpoint, auth=headers.get("Authorization"))
        return response if response is not None else images_response()

    monkeypatch.setattr(generate, "post_images", fake_post)
    return captured


def test_moderation_default_auto_and_choices():
    assert _parse("x").moderation == "auto"
    assert _parse("x", "--moderation", "low").moderation == "low"
    with pytest.raises(SystemExit):
        _parse("x", "--moderation", "off")


def test_background_default_opaque_and_choices():
    assert _parse("x").background == "opaque"
    assert _parse("x", "--background", "auto").background == "auto"
    # 0.3.0: the Images API honors it, so it is the same request as --transparent.
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
    monkeypatch.setattr(generate, "post_images", post)

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


def test_size_and_quality_default_to_omitted():
    args = _parse("x")
    assert args.size is None
    assert args.quality is None


@pytest.mark.parametrize("quality", ["low", "medium", "high", "auto", "xhigh", "max"])
def test_quality_choices_accepted(quality):
    assert _parse("x", "--quality", quality).quality == quality


def test_chatgpt_body_omits_model_size_and_quality(tmp_path, fixture_dir, monkeypatch):
    _chatgpt_home(tmp_path, fixture_dir, monkeypatch)

    def no_list(**kw):
        raise AssertionError("the ChatGPT route must not fetch a model list")

    monkeypatch.setattr(generate, "fetch_models", no_list)
    captured = _capture_post(monkeypatch)
    assert generate.main(["x", "--moderation", "low", "--background", "auto",
                          "--out-dir", str(tmp_path / "out")]) == 0
    assert captured["body"] == {"prompt": "x", "background": "auto", "moderation": "low"}
    assert captured["endpoint"].endswith("/images/generations")


def test_deprecated_orchestrator_and_effort_warn_but_succeed(tmp_path, fixture_dir, monkeypatch, capsys):
    _chatgpt_home(tmp_path, fixture_dir, monkeypatch)
    captured = _capture_post(monkeypatch)
    rc = generate.main(["x", "--orchestrator", "gpt-6.1-sol", "--effort", "low",
                        "--out-dir", str(tmp_path / "out")])
    err = capsys.readouterr().err
    assert rc == 0
    assert "--orchestrator is deprecated and ignored" in err
    assert "--effort is deprecated and ignored" in err
    assert {"model", "reasoning"}.isdisjoint(captured["body"])


@pytest.mark.parametrize("quality", ["xhigh", "max"])
def test_xhigh_and_max_are_sent_as_high(tmp_path, fixture_dir, monkeypatch, capsys, quality):
    _chatgpt_home(tmp_path, fixture_dir, monkeypatch)
    captured = _capture_post(monkeypatch, images_response(quality="high"))
    target = tmp_path / "out.png"
    assert generate.main(["x", "--quality", quality, "--out", str(target)]) == 0
    assert captured["body"]["quality"] == "high"
    assert f"--quality {quality} is not an Images API value; sending high" in capsys.readouterr().err
    assert json.loads(target.with_suffix(".png.json").read_text())["quality"] == "high"


def test_backend_overrides_of_size_and_quality_are_reported(tmp_path, fixture_dir, monkeypatch, capsys):
    _chatgpt_home(tmp_path, fixture_dir, monkeypatch)
    captured = _capture_post(monkeypatch, images_response(size="1536x1024", quality="low"))
    target = tmp_path / "out.png"
    assert generate.main(["x", "--size", "1024x1024", "--quality", "high", "--out", str(target)]) == 0
    out, err = capsys.readouterr()
    assert captured["body"]["size"] == "1024x1024"
    assert "Requested size 1024x1024; the backend returned 1536x1024" in err
    assert "Requested quality high; the backend returned low" in err
    assert out.rstrip().endswith("size=1536x1024)")
    record = json.loads(target.with_suffix(".png.json").read_text())
    assert (record["size"], record["resolved_size"]) == ("1024x1024", "1536x1024")
    assert (record["quality"], record["resolved_quality"]) == ("high", "low")
    assert record["response_id"] == "g1"


def test_explicit_image_model_is_sent_and_recorded_as_requested(tmp_path, fixture_dir, monkeypatch):
    _chatgpt_home(tmp_path, fixture_dir, monkeypatch)
    captured = _capture_post(monkeypatch)
    target = tmp_path / "out.png"
    assert generate.main(["x", "--image-model", "gpt-image-2.5-flare", "--out", str(target)]) == 0
    assert captured["body"]["model"] == "gpt-image-2.5-flare"
    record = json.loads(target.with_suffix(".png.json").read_text())
    assert record["requested_image_model"] == "gpt-image-2.5-flare"
    # The Images API does not report the model it used.
    assert record["image_model"] is None


def test_catalog_request_uses_whole_codex_version():
    assert generate._whole_version("0.144.0-alpha.4") == "0.144.0"
    assert generate._whole_version("0.163.0") == "0.163.0"


def test_provider_route_needs_no_chatgpt_sign_in_and_picks_newest_image_model(tmp_path, monkeypatch):
    _provider_home(tmp_path, monkeypatch)
    captured = _capture_post(monkeypatch)
    target = tmp_path / "out.png"
    assert generate.main(["x", "--out", str(target)]) == 0
    assert captured["body"]["model"] == "gpt-image-2.6"
    assert captured["endpoint"] == "http://127.0.0.1:8317/v1/images/generations"
    assert captured["auth"] == "Bearer k-test"
    assert json.loads(target.with_suffix(".png.json").read_text())["account_id"] == "provider:proxy"


def test_provider_route_explicit_image_model_skips_the_model_list(tmp_path, monkeypatch):
    _provider_home(tmp_path, monkeypatch)

    def no_list(**kw):
        raise AssertionError("an explicit --image-model must not fetch the model list")

    monkeypatch.setattr(generate, "fetch_models", no_list)
    captured = _capture_post(monkeypatch)
    assert generate.main(["x", "--image-model", "gpt-image-2", "--out-dir", str(tmp_path / "out")]) == 0
    assert captured["body"]["model"] == "gpt-image-2"


def test_provider_route_without_image_model_fails_before_posting(tmp_path, monkeypatch, capsys):
    _provider_home(tmp_path, monkeypatch)
    monkeypatch.setattr(generate, "fetch_models", lambda **kw: [{"slug": "gpt-6.1-sol"}])
    captured = _capture_post(monkeypatch)
    assert generate.main(["x", "--out-dir", str(tmp_path / "out")]) == 1
    err = capsys.readouterr().err
    assert captured == {}
    assert "Could not pick an image model for model_provider 'proxy'" in err
    assert "the model list has no gpt-image model" in err
    assert "--image-model" in err


def test_provider_model_list_401_points_at_the_provider_key(tmp_path, monkeypatch, capsys):
    import io
    import urllib.error

    _provider_home(tmp_path, monkeypatch)

    def expired(**kw):
        raise urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b"bad key"))

    monkeypatch.setattr(generate, "fetch_models", expired)
    assert generate.main(["x", "--out-dir", str(tmp_path / "out")]) == 1
    err = capsys.readouterr().err
    assert "HTTP 401" in err
    assert "Check the key for model_provider 'proxy'" in err


def test_provider_network_failure_reason_is_reported(tmp_path, monkeypatch, capsys):
    import urllib.error

    _provider_home(tmp_path, monkeypatch)

    def no_dns(**kw):
        raise urllib.error.URLError("[Errno 8] nodename nor servname provided")

    monkeypatch.setattr(generate, "fetch_models", no_dns)
    assert generate.main(["x", "--out-dir", str(tmp_path / "out")]) == 1
    assert "URLError: [Errno 8] nodename nor servname provided" in capsys.readouterr().err


@pytest.mark.parametrize("fmt", ["jpeg", "webp"])
def test_jpeg_and_webp_need_pillow_before_the_paid_call(tmp_path, fixture_dir, monkeypatch, capsys, fmt):
    import transparency

    _chatgpt_home(tmp_path, fixture_dir, monkeypatch)
    monkeypatch.setattr(transparency, "pillow_available", lambda: False)
    captured = _capture_post(monkeypatch)
    assert generate.main(["x", "--format", fmt, "--out-dir", str(tmp_path / "out")]) == 2
    assert captured == {}
    assert f"Pillow is required for --format {fmt}" in capsys.readouterr().err


def test_unreadable_codex_config_is_a_clean_error(tmp_path, monkeypatch, capsys):
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text('model_provider = "p\n')
    monkeypatch.setenv("CODEX_HOME", str(home))
    assert generate.main(["x", "--out-dir", str(tmp_path / "out")]) == 2
    assert capsys.readouterr().err.startswith("✗ Cannot read Codex's config")


def test_model_list_failure_does_not_print_provider_query_values(tmp_path, monkeypatch, capsys):
    import urllib.error

    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text(
        'model_provider = "p"\n[model_providers.p]\nbase_url = "http://p/v1"\n'
        'experimental_bearer_token = "k"\n[model_providers.p.query_params]\nkey = "secret-q"\n')
    monkeypatch.setenv("CODEX_HOME", str(home))

    def offline(**kw):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(generate, "fetch_models", offline)
    assert generate.main(["x", "--out-dir", str(tmp_path / "out")]) == 1
    assert "secret-q" not in capsys.readouterr().err


def test_api_calls_refuse_redirects(monkeypatch):
    import http.server
    import threading
    import urllib.error

    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append((self.path, self.headers.get("Authorization")))
            if self.path.startswith("/v1/models"):
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/elsewhere")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"data": []}')

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/v1/models",
                                     headers={"Authorization": "Bearer k"})
        with pytest.raises(urllib.error.HTTPError) as err:
            generate._OPENER.open(req, timeout=5)
        assert err.value.code == 302
        assert [path for path, _ in hits] == ["/v1/models"]
    finally:
        server.shutdown()
