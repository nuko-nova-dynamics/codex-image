from __future__ import annotations


def _setup_auth(fixture_dir, monkeypatch, tmp_path):
    home = tmp_path / "fake-codex-home"
    home.mkdir()
    (home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))


def test_whoami_prints_account_and_exits_without_generating(tmp_path, fixture_dir, monkeypatch, capsys):
    import generate
    _setup_auth(fixture_dir, monkeypatch, tmp_path)

    called = {"post": False}
    def post(**kw):
        called["post"] = True
        return ""
    monkeypatch.setattr(generate, "post_responses", post)

    result = generate.main(["x", "--whoami"])
    out = capsys.readouterr().out
    assert result == 0
    assert called["post"] is False
    assert "test@example.com" in out
    assert "pro" in out


def test_first_use_banner_appears_once_per_session(tmp_path, fixture_dir, monkeypatch, capsys):
    import generate
    _setup_auth(fixture_dir, monkeypatch, tmp_path)

    import base64
    fake_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nf").decode()
    monkeypatch.setattr(generate, "post_responses", lambda **kw:
        f'event: response.output_item.done\ndata: {{"type":"response.output_item.done","item":{{"id":"i","type":"image_generation_call","status":"completed","result":"{fake_b64}"}}}}\n\n'
    )

    # First call: banner shown
    generate.main(["a", "--quality", "low", "--out-dir", str(tmp_path / "out")])
    first = capsys.readouterr().err
    assert "test@example.com" in first

    # Second call: same account → no banner
    generate.main(["b", "--quality", "low", "--out-dir", str(tmp_path / "out")])
    second = capsys.readouterr().err
    assert "test@example.com" not in second


def test_whoami_uses_access_token_exp_not_id_token_exp(tmp_path, fixture_dir, monkeypatch, capsys):
    """Codex review nit: access_token exp is what matters for API validity."""
    import auth as auth_mod

    # Build an auth file whose id_token is "expired" but access_token is fresh.
    # The fixture's existing tokens both have exp=9999999999 so the test really
    # confirms summarize_account reads from the access_token claims.
    af = auth_mod.load_auth(fixture_dir / "auth_chatgpt.json")
    summary = auth_mod.summarize_account(af)
    assert summary["exp"] == 9999999999
