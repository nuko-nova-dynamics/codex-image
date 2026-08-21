from __future__ import annotations

from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402
from postprocess import convert_png_to_webp, save_image  # noqa: E402


def _make_png(path: Path, size=(8, 8), mode="RGB") -> None:
    Image.new(mode, size, "red").save(path, format="PNG")


def test_convert_png_to_webp_creates_webp(tmp_path):
    src = tmp_path / "in.png"
    dst = tmp_path / "out.webp"
    _make_png(src)
    convert_png_to_webp(src, dst, quality=80)
    img = Image.open(dst)
    assert img.format == "WEBP"


def test_convert_png_to_webp_preserves_alpha(tmp_path):
    src = tmp_path / "rgba.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 128)).save(src, "PNG")
    dst = tmp_path / "rgba.webp"
    convert_png_to_webp(src, dst, quality=80)
    img = Image.open(dst)
    assert img.mode in ("RGBA", "LA")


def test_save_image_png_passthrough(tmp_path):
    raw = b"\x89PNG\r\n\x1a\nFAKE"
    target = tmp_path / "x.png"
    save_image(raw_bytes=raw, target_path=target, format="png")
    assert target.read_bytes() == raw


def test_save_image_jpeg_passthrough(tmp_path):
    raw = b"\xff\xd8\xff\xe0FAKE"
    target = tmp_path / "x.jpg"
    save_image(raw_bytes=raw, target_path=target, format="jpeg")
    assert target.read_bytes() == raw


def test_save_image_webp_converts_via_pillow(tmp_path):
    src = tmp_path / "stage.png"
    _make_png(src)
    target = tmp_path / "x.webp"
    save_image(raw_bytes=src.read_bytes(), target_path=target, format="webp", webp_quality=70)
    assert Image.open(target).format == "WEBP"


def test_transparent_plus_jpeg_rejected_BEFORE_paid_call(tmp_path, fixture_dir, monkeypatch, capsys):
    """Codex review: rejection must happen before post_responses to save credits."""
    import generate

    fake_home = tmp_path / "fake-codex-home"
    fake_home.mkdir()
    (fake_home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(fake_home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    called = {"post": False}
    def boom(**kw):
        called["post"] = True
        raise AssertionError("post_responses must NOT be called when --transparent + --format jpeg")
    monkeypatch.setattr(generate, "post_responses", boom)

    rc = generate.main([
        "x", "--transparent", "--format", "jpeg",
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    assert rc != 0
    assert called["post"] is False
    err = capsys.readouterr().err
    assert "jpeg" in err.lower() and "alpha" in err.lower()


def test_transparent_plus_webp_runs_chroma_before_conversion(tmp_path, fixture_dir, monkeypatch):
    """Chroma mode + --format webp must stage PNG → chroma → convert to WebP."""
    import subprocess

    import generate
    import transparency

    fake_home = tmp_path / "fake-codex-home"
    fake_home.mkdir()
    (fake_home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(fake_home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    monkeypatch.setattr(transparency, "pillow_available", lambda: True)

    import base64
    fake_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
    monkeypatch.setattr(generate, "post_responses", lambda **kw:
        f'event: response.output_item.done\ndata: {{"type":"response.output_item.done","item":{{"id":"i","type":"image_generation_call","status":"completed","result":"{fake_b64}"}}}}\n\n'
    )

    seen = {"chroma_input_ext": None, "chroma_output_ext": None}

    def fake_run(cmd, **kw):
        # Be tolerant of the pre-flight `codex --version` call from _detect_codex_cli_version
        if "--input" not in cmd or "--out" not in cmd:
            class RVersion:
                returncode = 0
                stdout = "codex-cli 0.128.0\n"
                stderr = ""
            return RVersion()
        in_path = cmd[cmd.index("--input") + 1]
        out_path = cmd[cmd.index("--out") + 1]
        seen["chroma_input_ext"] = Path(in_path).suffix
        seen["chroma_output_ext"] = Path(out_path).suffix
        Image.new("RGBA", (4, 4), (255, 0, 0, 128)).save(out_path, "PNG")

        class RChroma:
            returncode = 0
            stderr = ""
        return RChroma()
    monkeypatch.setattr(subprocess, "run", fake_run)

    out_dir = tmp_path / "out"
    rc = generate.main([
        "a leaf", "--transparent", "--transparent-mode", "chroma", "--format", "webp",
        "--out-dir", str(out_dir), "--quality", "low",
    ])
    assert rc == 0
    assert seen["chroma_input_ext"] == ".png"
    assert seen["chroma_output_ext"] == ".png"
    webps = list(out_dir.glob("*.webp"))
    assert len(webps) == 1
    assert not list(out_dir.glob("*.stage.png"))


def test_plain_webp_does_not_apply_chroma_key(tmp_path, fixture_dir, monkeypatch, capsys):
    """`--format webp` alone (no --transparent) must NOT mutate the prompt
    or print the chroma-key warning. Regression for v0.1.0 smoke run."""
    import generate
    import transparency

    fake_home = tmp_path / "fake-codex-home"
    fake_home.mkdir()
    (fake_home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(fake_home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))
    monkeypatch.setattr(transparency, "pillow_available", lambda: True)

    # Real PNG bytes so Pillow can convert to WebP.
    import base64
    import io
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(buf, "PNG")
    real_png_b64 = base64.b64encode(buf.getvalue()).decode()

    sent = {}

    def capture_body(**kwargs):
        sent["body"] = kwargs.get("body", {})
        return ('event: response.output_item.done\n'
                'data: {"type":"response.output_item.done","item":'
                f'{{"id":"i","type":"image_generation_call","status":"completed","result":"{real_png_b64}"}}}}\n\n')

    monkeypatch.setattr(generate, "post_responses", capture_body)

    rc = generate.main([
        "a tiny blue square", "--format", "webp",
        "--out-dir", str(tmp_path / "out"), "--quality", "low",
    ])
    assert rc == 0

    err = capsys.readouterr().err
    assert "chroma-key workaround" not in err, (
        "plain --format webp must not print the transparency workaround warning"
    )

    # The user prompt must reach the API verbatim (no chroma-key suffix).
    body = sent["body"]
    user_msgs = [m for m in body.get("input", []) if m.get("role") == "user"]
    assert user_msgs, f"no user message in body: {body}"
    text_parts = []
    for m in user_msgs:
        for c in m.get("content", []):
            if c.get("type") in ("input_text", "text"):
                text_parts.append(c.get("text", ""))
    full_prompt = " ".join(text_parts)
    assert full_prompt.strip().startswith("a tiny blue square"), full_prompt
    # Chroma template phrasing must be absent.
    assert "chroma-key" not in full_prompt.lower(), (
        f"chroma-key suffix leaked into plain webp prompt: {full_prompt!r}"
    )
