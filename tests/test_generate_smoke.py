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
    assert "--edge-contract" not in seen["cmd"]
    assert "--edge-feather" not in seen["cmd"]


def test_generate_transparent_edge_flags_pass_through(tmp_path, fixture_dir, fake_sse_with_image, monkeypatch):
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
        "--edge-contract", "1", "--edge-feather", "0.25",
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    assert result == 0
    cmd = seen["cmd"]
    assert cmd[cmd.index("--edge-contract") + 1] == "1"
    assert cmd[cmd.index("--edge-feather") + 1] == "0.25"


def test_generate_transparent_defaults_to_native_not_chroma(
    tmp_path, fixture_dir, fake_sse_with_image, monkeypatch
):
    """Behaviour change in 0.2.0: bare --transparent asks the model for alpha
    instead of running the chroma-key post-process."""
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
    assert not seen["called"], "bare --transparent must not run the chroma post-process"


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


# --- native transparency (v0.2.0) -------------------------------------------

def _png_b64(mode: str) -> str:
    """Real 8x8 PNG in the requested mode, base64-encoded."""
    from io import BytesIO

    from PIL import Image
    img = Image.new(mode, (8, 8), (255, 0, 0, 0) if mode == "RGBA" else (255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _sse(result_b64: str, *, background: str = "transparent",
         model: str | None = "gpt-image-2-codex") -> str:
    tools = (
        f'"tools":[{{"type":"image_generation","background":"auto","model":"{model}"}}]'
        if model else '"tools":[]'
    )
    return (
        "event: response.created\n"
        f'data: {{"type":"response.created","response":{{"id":"resp_9",{tools}}}}}\n\n'
        "event: response.output_item.done\n"
        'data: {"type":"response.output_item.done","item":{"id":"ig_9",'
        '"type":"image_generation_call","status":"generating",'
        f'"result":"{result_b64}","quality":"medium","size":"1536x1024",'
        f'"output_format":"png","background":"{background}","action":"generate",'
        '"revised_prompt":"X"}}\n\n'
        "event: response.completed\n"
        f'data: {{"type":"response.completed","response":{{"id":"resp_9","output":[],{tools}}}}}\n\n'
    )


def _env(tmp_path, fixture_dir, monkeypatch):
    fake_home = tmp_path / "fake-codex-home"
    fake_home.mkdir()
    (fake_home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(fake_home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))


def _no_chroma_subprocess(monkeypatch):
    """Stub codex --version; blow up if anything tries to run the chroma helper."""
    import subprocess
    calls = []

    def fake_run(cmd, **kw):
        if cmd == ["codex", "--version"]:
            class V:
                stdout = "codex-cli 0.149.0\n"
            return V()
        calls.append(cmd)
        raise AssertionError(f"unexpected subprocess on the native path: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_transparent_sends_background_auto_and_appends_suffix(
    tmp_path, fixture_dir, monkeypatch
):
    """Native transparency is requested via background=auto plus a prompt
    sentence. background=transparent 400s on this transport."""
    import generate
    import transparency
    _env(tmp_path, fixture_dir, monkeypatch)
    _no_chroma_subprocess(monkeypatch)

    captured = {}

    def fake_post(*, body, headers, endpoint=None, timeout=None):
        captured["body"] = body
        return _sse(_png_b64("RGBA"))

    monkeypatch.setattr(generate, "post_responses", fake_post)

    assert generate.main([
        "a red mug", "--transparent",
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ]) == 0

    tool = captured["body"]["tools"][0]
    assert tool["background"] == "auto"
    text = captured["body"]["input"][0]["content"][-1]["text"]
    assert text.startswith("a red mug")
    assert text.endswith(transparency.NATIVE_TRANSPARENCY_SUFFIX)


def test_transparent_suffix_states_no_creative_constraints(monkeypatch):
    """The suffix must not smuggle in art direction — the user owns shadow,
    framing and text."""
    import transparency
    suffix = transparency.NATIVE_TRANSPARENCY_SUFFIX.lower()
    for banned in ("no cast shadow", "no shadow", "no plinth", "no rectangle",
                   "no text", "no label", "chroma", "#00ff00"):
        assert banned not in suffix


def test_transparent_native_writes_returned_bytes_unmodified(
    tmp_path, fixture_dir, monkeypatch
):
    import generate
    _env(tmp_path, fixture_dir, monkeypatch)
    _no_chroma_subprocess(monkeypatch)

    payload = _png_b64("RGBA")
    monkeypatch.setattr(generate, "post_responses", lambda **kw: _sse(payload))

    out_dir = tmp_path / "out"
    assert generate.main([
        "a red mug", "--transparent",
        "--out-dir", str(out_dir), "--quality", "low",
    ]) == 0

    pngs = list(out_dir.glob("*.png"))
    assert len(pngs) == 1
    assert pngs[0].read_bytes() == base64.b64decode(payload)


def test_sidecar_records_image_model_and_resolved_background(
    tmp_path, fixture_dir, monkeypatch
):
    import generate
    _env(tmp_path, fixture_dir, monkeypatch)
    _no_chroma_subprocess(monkeypatch)
    monkeypatch.setattr(generate, "post_responses", lambda **kw: _sse(_png_b64("RGBA")))

    out_dir = tmp_path / "out"
    assert generate.main([
        "a red mug", "--transparent",
        "--out-dir", str(out_dir), "--quality", "low",
    ]) == 0

    sidecar = next(out_dir.glob("*.png.json"))
    data = json.loads(sidecar.read_text())
    assert data["image_model"] == "gpt-image-2-codex"
    assert data["resolved_background"] == "transparent"


def test_transparent_warns_when_result_has_no_alpha(
    tmp_path, fixture_dir, monkeypatch, capsys
):
    """A flat RGB result still saves — the user already paid for it — but the
    agent needs a signal to retry."""
    import generate
    _env(tmp_path, fixture_dir, monkeypatch)
    _no_chroma_subprocess(monkeypatch)
    monkeypatch.setattr(
        generate, "post_responses",
        lambda **kw: _sse(_png_b64("RGB"), background="opaque"),
    )

    out_dir = tmp_path / "out"
    assert generate.main([
        "a red mug", "--transparent",
        "--out-dir", str(out_dir), "--quality", "low",
    ]) == 0
    assert list(out_dir.glob("*.png")), "image must still be saved"
    err = capsys.readouterr().err.lower()
    assert "transparent" in err and "alpha" in err


def test_background_transparent_is_passed_through_unrewritten(
    tmp_path, fixture_dir, monkeypatch, capsys
):
    """Never silently substitute a value the user explicitly typed."""
    import generate
    _env(tmp_path, fixture_dir, monkeypatch)
    _no_chroma_subprocess(monkeypatch)

    captured = {}

    def fake_post(*, body, headers, endpoint=None, timeout=None):
        captured["body"] = body
        return _sse(_png_b64("RGBA"))

    monkeypatch.setattr(generate, "post_responses", fake_post)

    assert generate.main([
        "a red mug", "--background", "transparent",
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ]) == 0
    assert captured["body"]["tools"][0]["background"] == "transparent"
    assert "--transparent" in capsys.readouterr().err


def test_transparent_mode_chroma_runs_post_process(
    tmp_path, fixture_dir, monkeypatch
):
    """The chroma path survives as an explicit, named fallback."""
    import generate
    import transparency
    _env(tmp_path, fixture_dir, monkeypatch)
    monkeypatch.setattr(transparency, "pillow_available", lambda: True)
    monkeypatch.setattr(generate, "post_responses", lambda **kw: _sse(_png_b64("RGBA")))

    import subprocess
    seen = {}

    def fake_run(cmd, **kw):
        if cmd == ["codex", "--version"]:
            class V:
                stdout = "codex-cli 0.149.0\n"
            return V()
        seen["cmd"] = cmd
        from pathlib import Path
        Path(cmd[cmd.index("--out") + 1]).write_bytes(b"\x89PNG\r\n\x1a\nALPHA")

        class R:
            returncode = 0
            stderr = ""
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert generate.main([
        "a leaf", "--transparent", "--transparent-mode", "chroma",
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ]) == 0
    assert "remove_chroma_key.py" in str(seen["cmd"][1])
