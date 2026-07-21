"""Tests for auth file discovery and JWT decoding."""
from __future__ import annotations

import json

import pytest
from auth import (
    AuthError,
    AuthFile,
    decode_account_id_from_jwt,
    discover_auth_file,
    load_auth,
)


def test_discover_prefers_codex_home(tmp_path, monkeypatch):
    codex_home = tmp_path / "custom_codex"
    codex_home.mkdir()
    target = codex_home / "auth.json"
    target.write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("HOME", str(tmp_path))
    assert discover_auth_file() == target


def test_discover_falls_through_to_home_dotcodex(tmp_path, monkeypatch):
    target = tmp_path / ".codex" / "auth.json"
    target.parent.mkdir()
    target.write_text("{}")
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CHATGPT_LOCAL_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert discover_auth_file() == target


def test_discover_returns_none_when_nothing_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CHATGPT_LOCAL_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert discover_auth_file() is None


def test_load_auth_chatgpt_mode(fixture_dir):
    auth = load_auth(fixture_dir / "auth_chatgpt.json")
    assert isinstance(auth, AuthFile)
    assert auth.auth_mode == "chatgpt"
    assert auth.access_token.startswith("eyJ")
    assert auth.account_id == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_auth_file_repr_excludes_tokens(tmp_path):
    token_values = ("access-secret", "id-secret", "refresh-secret")
    auth = AuthFile(
        auth_mode="chatgpt",
        access_token=token_values[0],
        id_token=token_values[1],
        refresh_token=token_values[2],
        account_id="account-123",
        last_refresh=None,
        path=tmp_path / "auth.json",
    )
    representation = repr(auth)
    assert all(token not in representation for token in token_values)
    assert "account-123" in representation


def test_load_auth_apikey_raises(fixture_dir):
    with pytest.raises(AuthError, match="apikey"):
        load_auth(fixture_dir / "auth_apikey.json")


def test_load_auth_missing_file(tmp_path):
    with pytest.raises(AuthError, match="not signed in"):
        load_auth(tmp_path / "missing.json")


def test_decode_account_id_from_namespaced_claim(make_jwt):
    jwt = make_jwt({
        "https://api.openai.com/auth": {"chatgpt_account_id": "ns-account-123"},
    })
    assert decode_account_id_from_jwt(jwt) == "ns-account-123"


def test_decode_account_id_top_level_fallback(make_jwt):
    jwt = make_jwt({"chatgpt_account_id": "top-level-456"})
    assert decode_account_id_from_jwt(jwt) == "top-level-456"


def test_decode_account_id_returns_none_when_absent(make_jwt):
    jwt = make_jwt({"sub": "user-xxx"})
    assert decode_account_id_from_jwt(jwt) is None


def test_load_auth_uses_jwt_fallback_when_account_id_missing(tmp_path, make_jwt):
    id_token = make_jwt({
        "https://api.openai.com/auth": {"chatgpt_account_id": "from-jwt-789"},
    })
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps({
        "auth_mode": "chatgpt",
        "tokens": {
            "access_token": "eyJ.fake.fake",
            "id_token": id_token,
            "refresh_token": "rt",
            # No account_id at top level — should fall back to JWT
        },
    }))
    auth = load_auth(auth_path)
    assert auth.account_id == "from-jwt-789"
