"""Integration test for generate.main, mocking only the HTTP call."""
from __future__ import annotations

import base64
import json
from unittest.mock import patch

import pytest


@pytest.fixture
def fake_sse_with_image():
    fake_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKEPNGBYTES").decode()
    return (
        "event: response.created\n"
        'data: {"type":"response.created","response":{"id":"resp_1"}}\n\n'
        "event: response.output_item.done\n"
        'data: {"type":"response.output_item.done","item":{"id":"ig_1","type":"image_generation_call",'
        f'"status":"completed","result":"{fake_b64}","quality":"medium","size":"1024x1024",'
        '"output_format":"png","background":"opaque","action":"generate","revised_prompt":"X"}}\n\n'
    )


def test_generate_writes_png_and_sidecar(tmp_path, fixture_dir, fake_sse_with_image, monkeypatch):
    import generate

    fake_home = tmp_path / "fake-codex-home"
    fake_home.mkdir()
    (fake_home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(fake_home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    out_dir = tmp_path / "out"

    with patch.object(generate, "post_responses", return_value=fake_sse_with_image):
        result = generate.main([
            "a small red circle",
            "--out-dir", str(out_dir),
            "--quality", "low",
        ])

    assert result == 0
    pngs = list(out_dir.glob("*.png"))
    assert len(pngs) == 1
    assert pngs[0].read_bytes().startswith(b"\x89PNG")
    sidecar = pngs[0].with_suffix(".png.json")
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["prompt"] == "a small red circle"


def test_generate_edit_mode_passes_input_image(tmp_path, fixture_dir, fake_sse_with_image, monkeypatch):
    import generate

    fake_home = tmp_path / "fake-codex-home"
    fake_home.mkdir()
    (fake_home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(fake_home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    src = tmp_path / "ref.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\nFAKE")

    captured = {}
    def fake_post(*, body, headers, endpoint=None, timeout=None):
        captured["body"] = body
        return fake_sse_with_image
    monkeypatch.setattr(generate, "post_responses", fake_post)

    result = generate.main([
        "make it bigger", "--input", str(src),
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    assert result == 0
    tool = captured["body"]["tools"][0]
    assert tool["action"] == "edit"
    user_content = captured["body"]["input"][0]["content"]
    assert user_content[0]["type"] == "input_image"
    assert user_content[0]["image_url"].startswith("data:image/png;base64,")


def test_generate_transparent_chroma_runs_post_process(tmp_path, fixture_dir, fake_sse_with_image, monkeypatch):
    import generate

    fake_home = tmp_path / "fake-codex-home"
    fake_home.mkdir()
    (fake_home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(fake_home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    monkeypatch.setattr(generate, "post_responses", lambda **kw: fake_sse_with_image)

    import subprocess

    import transparency
    monkeypatch.setattr(transparency, "pillow_available", lambda: True)
    seen = {}

    def fake_run(cmd, **kw):
        if cmd == ["codex", "--version"]:
            class VersionResult:
                stdout = "codex-cli 0.144.6\n"

            return VersionResult()
        seen["cmd"] = cmd
        from pathlib import Path
        Path(cmd[cmd.index("--out") + 1]).write_bytes(b"\x89PNG\r\n\x1a\nALPHAd")

        class R:
            returncode = 0
            stderr = ""

        return R()
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = generate.main([
        "a leaf", "--transparent", "--bg-tool", "chroma",
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    assert result == 0
    assert "remove_chroma_key.py" in str(seen["cmd"][1])


def test_generate_transparent_default_bg_tool_falls_through_to_chroma(
    tmp_path, fixture_dir, fake_sse_with_image, monkeypatch
):
    import generate

    fake_home = tmp_path / "fake-codex-home"
    fake_home.mkdir()
    (fake_home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(fake_home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    monkeypatch.setattr(generate, "post_responses", lambda **kw: fake_sse_with_image)

    import subprocess

    import transparency
    monkeypatch.setattr(transparency, "pillow_available", lambda: True)
    seen = {"called": False}

    def fake_run(cmd, **kw):
        if cmd == ["codex", "--version"]:
            class VersionResult:
                stdout = "codex-cli 0.144.6\n"

            return VersionResult()
        seen["called"] = True
        from pathlib import Path
        Path(cmd[cmd.index("--out") + 1]).write_bytes(b"\x89PNG\r\n\x1a\nALPHA")

        class R:
            returncode = 0
            stderr = ""

        return R()
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = generate.main([
        "a leaf", "--transparent",
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    assert result == 0
    assert seen["called"], "default --bg-tool=auto should fall through to chroma when running directly"


def test_generate_transparent_bg_tool_adobe_errors_in_shell(
    tmp_path, fixture_dir, fake_sse_with_image, monkeypatch, capsys
):
    import generate

    fake_home = tmp_path / "fake-codex-home"
    fake_home.mkdir()
    (fake_home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(fake_home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    import transparency
    monkeypatch.setattr(transparency, "pillow_available", lambda: True)
    monkeypatch.setattr(generate, "post_responses", lambda **kw: fake_sse_with_image)

    result = generate.main([
        "a mug", "--transparent", "--bg-tool", "adobe",
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    err = capsys.readouterr().err
    assert result == 2
    assert "adobe" in err.lower() and "skill.md" in err.lower()


def test_empty_sse_retry_handles_401_on_second_call(tmp_path, fixture_dir, monkeypatch, capsys):
    """A 401 on a plain-generation retry must surface cleanly, not raise."""
    import urllib.error

    import generate

    fake_home = tmp_path / "fake-codex-home"
    fake_home.mkdir()
    (fake_home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(fake_home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    calls = {"n": 0}
    empty_sse = "event: response.created\ndata: {}\n\n"
    def fake_post(*, body, headers, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return empty_sse  # triggers retry
        e = urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)
        e.body_text = "auth expired"  # type: ignore[attr-defined]
        raise e
    monkeypatch.setattr(generate, "post_responses", fake_post)

    rc = generate.main([
        "x", "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    err = capsys.readouterr().err
    assert rc == 1
    assert "401" in err or "auth" in err.lower()
    assert "codex login" in err.lower()
    assert calls["n"] == 2


def test_sidecar_stores_original_ref_not_data_url(tmp_path, fixture_dir, fake_sse_with_image, monkeypatch):
    """Spec §9 + Codex review: sidecar must not bloat with base64 data URLs."""
    import json

    import generate

    fake_home = tmp_path / "fake-codex-home"
    fake_home.mkdir()
    (fake_home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(fake_home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    src = tmp_path / "ref.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\nFAKE" * 1000)  # bigger than slug-length
    monkeypatch.setattr(generate, "post_responses", lambda **kw: fake_sse_with_image)

    result = generate.main([
        "edit", "--input", str(src),
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    assert result == 0
    sidecars = list((tmp_path / "out").glob("*.png.json"))
    assert sidecars, "no sidecar found"
    data = json.loads(sidecars[0].read_text())
    # The sidecar must record the local PATH, not the resolved data URL
    assert data["input_image"] == str(src) or data["input_image"].startswith(str(src))
    assert "data:image" not in data["input_image"]


def test_empty_sse_edit_does_not_retry_without_refs(
    tmp_path, fixture_dir, monkeypatch, capsys
):
    """An edit that yields no image must preserve semantics and stop."""
    import generate
    home = tmp_path / "fake-codex-home"
    home.mkdir()
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    src = tmp_path / "ref.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\nFAKE")

    empty_sse = "event: response.created\ndata: {}\n\n"

    calls = {"n": 0, "bodies": []}
    def fake_post(*, body, headers, **kw):
        calls["n"] += 1
        calls["bodies"].append(body)
        return empty_sse
    monkeypatch.setattr(generate, "post_responses", fake_post)

    result = generate.main([
        "make it cool", "--input", str(src),
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    assert result != 0
    assert calls["n"] == 1
    refs1 = [c for c in calls["bodies"][0]["input"][0]["content"] if c["type"] == "input_image"]
    assert len(refs1) == 1
    err = capsys.readouterr().err.lower()
    assert "edit produced no image" in err
    assert "re-run" in err


def test_empty_sse_reference_free_generation_retries_once(
    tmp_path, fixture_dir, monkeypatch
):
    """A reference-free generation gets one retry after an empty response."""
    import generate
    home = tmp_path / "fake-codex-home"
    home.mkdir()
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    img = base64.b64encode(b"\x89PNG\r\n\x1a\nNICE").decode()
    success_sse = (
        "event: response.output_item.done\n"
        f'data: {{"type":"response.output_item.done","item":{{"id":"i","type":"image_generation_call","status":"completed","result":"{img}"}}}}\n\n'
    )
    empty_sse = "event: response.created\ndata: {}\n\n"

    calls = {"n": 0, "bodies": []}

    def fake_post(*, body, headers, **kw):
        calls["n"] += 1
        calls["bodies"].append(body)
        return empty_sse if calls["n"] == 1 else success_sse

    monkeypatch.setattr(generate, "post_responses", fake_post)

    result = generate.main([
        "make it cool", "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    assert result == 0
    assert calls["n"] == 2
    for body in calls["bodies"]:
        refs = [
            item for item in body["input"][0]["content"]
            if item["type"] == "input_image"
        ]
        assert refs == []


def test_incomplete_partial_stream_is_not_saved(
    tmp_path, fixture_dir, monkeypatch, capsys
):
    import generate
    home = tmp_path / "fake-codex-home"
    home.mkdir()
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    incomplete_sse = (
        "event: response.image_generation_call.partial_image\n"
        'data: {"type":"response.image_generation_call.partial_image",'
        '"partial_image_b64":"VFJVTkNBVEVE","partial_image_index":0}\n\n'
    )
    monkeypatch.setattr(generate, "post_responses", lambda **kw: incomplete_sse)

    out_dir = tmp_path / "out"
    result = generate.main([
        "x", "--out-dir", str(out_dir), "--quality", "low",
    ])
    assert result != 0
    assert "incomplete stream" in capsys.readouterr().err.lower()
    assert not out_dir.exists()
