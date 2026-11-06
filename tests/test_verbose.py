from __future__ import annotations

import re


def test_verbose_output_contains_no_token_substrings(tmp_path, fixture_dir, monkeypatch, capsys,
                                                     fake_images_response):
    """Smoke: --verbose dump must redact any access_token / refresh_token / Bearer."""
    import generate

    home = tmp_path / "fake-codex-home"
    home.mkdir()
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    resp = fake_images_response()
    resp["data"][0]["revised_prompt"] = "X with Bearer eyJabc.def.ghi"
    monkeypatch.setattr(generate, "post_images", lambda **kw: resp)

    result = generate.main(["x", "--verbose", "--out-dir", str(tmp_path / "out")])
    assert result == 0
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "generation_id    = g1" in combined
    assert "resolved_size    = 1536x1024" in combined
    assert "Bearer eyJ" not in combined
    forbidden = re.compile(r"(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")
    assert not forbidden.search(combined), f"JWT-like substring leaked: {forbidden.search(combined).group()}"
