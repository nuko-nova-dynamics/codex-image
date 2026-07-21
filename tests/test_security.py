"""Security guarantees mandated by spec §5."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


def test_no_script_enables_shell_tracing():
    """Spec §5: never `set -x` (would echo bearer tokens to logs)."""
    offenders = []
    for sh in SCRIPTS_DIR.glob("*.sh"):
        text = sh.read_text()
        if re.search(r'^\s*set\s+-\w*x\w*', text, re.MULTILINE):
            offenders.append(sh.name)
        if re.search(r'^\s*set\s+-o\s+xtrace', text, re.MULTILINE):
            offenders.append(sh.name)
    assert not offenders, (
        f"shell tracing enables found in {offenders}; "
        "shell tracing leaks bearer tokens via process-arg / curl logs"
    )


def test_auth_warns_on_loose_permissions(fixture_dir, tmp_path, capsys):
    """0644 auth.json should produce a warning to stderr (but still load)."""
    import auth as auth_mod

    target = tmp_path / "auth.json"
    target.write_text((fixture_dir / "auth_chatgpt.json").read_text())
    target.chmod(0o644)

    auth = auth_mod.load_auth(target)
    err = capsys.readouterr().err
    assert auth.account_id
    assert "permissions" in err.lower() or "0600" in err


def test_auth_silent_on_strict_permissions(fixture_dir, tmp_path, capsys):
    """0600 auth.json is the recommended posture — no warning."""
    import auth as auth_mod

    target = tmp_path / "auth.json"
    target.write_text((fixture_dir / "auth_chatgpt.json").read_text())
    target.chmod(0o600)

    auth_mod.load_auth(target)
    assert "permissions" not in capsys.readouterr().err.lower()


def test_http_error_body_redacted_before_print(tmp_path, fixture_dir, monkeypatch, capsys):
    """If the backend returns 4xx with a body containing tokens, generate.py must redact them.

    Skipped until Task 2.7 creates scripts/generate.py.
    """
    pytest.importorskip("generate")
    import urllib.error

    import generate

    fake_home = tmp_path / "fake-codex-home"
    fake_home.mkdir()
    (fake_home / "auth.json").write_text((fixture_dir / "auth_chatgpt.json").read_text())
    monkeypatch.setenv("CODEX_HOME", str(fake_home))
    monkeypatch.setenv("CODEX_IMAGE_HOME", str(tmp_path / ".codex-image"))

    leaky_body = (
        '{"detail":"failure","echo":{"Authorization":"Bearer eyJabcd.efgh.ijkl",'
        '"access_token":"eyJsneaky.token.value"}}'
    )

    def boom(**kw):
        e = urllib.error.HTTPError("u", 400, "Bad Request", {}, None)
        e.body_text = leaky_body  # type: ignore[attr-defined]
        raise e
    monkeypatch.setattr(generate, "post_responses", boom)

    rc = generate.main(["x", "--out-dir", str(tmp_path / "out"), "--quality", "low"])
    err = capsys.readouterr().err
    assert rc != 0
    assert "eyJabcd" not in err
    assert "eyJsneaky" not in err
    assert "<redacted" in err
