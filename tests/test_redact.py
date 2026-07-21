from __future__ import annotations

from redact import redact_dict, redact_text


def test_redact_text_replaces_bearer_tokens():
    s = "Authorization: Bearer eyJhbGc.foobar.baz123"
    out = redact_text(s)
    assert "eyJhbGc" not in out
    assert "<redacted, len=" in out


def test_redact_text_handles_quoted_token_fields():
    s = '"access_token":"eyJ.aaa.bbb","other":"keep"'
    out = redact_text(s)
    assert "eyJ.aaa.bbb" not in out
    assert "keep" in out


def test_redact_text_handles_case_insensitive_single_quoted_token_fields():
    s = "{'ACCESS_TOKEN': 'secret-one', 'Refresh_Token': 'secret-two'}"
    out = redact_text(s)
    assert "secret-one" not in out
    assert "secret-two" not in out
    assert out.count("<redacted") == 2
    assert out == (
        "{'ACCESS_TOKEN': '<redacted, len=10>', "
        "'Refresh_Token': '<redacted, len=10>'}"
    )


def test_redact_text_handles_key_value_token_fields():
    s = "access_token=secret-one refresh_token='secret-two'"
    out = redact_text(s)
    assert "secret-one" not in out
    assert "secret-two" not in out
    assert out.count("<redacted") == 2
    assert out == (
        "access_token=<redacted, len=10> "
        "refresh_token='<redacted, len=10>'"
    )


def test_redact_text_handles_bare_jwt_but_preserves_non_jwt_base64():
    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature_123"
    ordinary_base64 = "VGhpcyBpcyBub3QgYSBKV1Q="
    out = redact_text(f"token={jwt} payload={ordinary_base64}")
    assert jwt not in out
    assert "<redacted JWT" in out
    assert ordinary_base64 in out


def test_redact_text_preserves_non_jwt_four_segment_value():
    value = "eyJheader.payload.signature.extra"
    assert redact_text(value) == value


def test_redact_dict_strips_token_fields():
    d = {
        "tokens": {
            "access_token": "secret-1",
            "id_token": "secret-2",
            "refresh_token": "secret-3",
        },
        "ok": "fine",
    }
    out = redact_dict(d)
    assert out["tokens"]["access_token"].startswith("<redacted")
    assert out["tokens"]["id_token"].startswith("<redacted")
    assert out["tokens"]["refresh_token"].startswith("<redacted")
    assert out["ok"] == "fine"


def test_redact_dict_strips_authorization_header():
    d = {"headers": {"Authorization": "Bearer xyz", "X-Other": "keep"}}
    out = redact_dict(d)
    assert out["headers"]["Authorization"] == "Bearer <redacted, len=3>"
    assert out["headers"]["X-Other"] == "keep"


def test_redact_dict_redacts_case_insensitive_keys_and_nested_strings():
    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature_123"
    data = {
        "Access_Token": "secret-one",
        "nested": [{"message": f"request failed with {jwt}"}],
    }
    out = redact_dict(data)
    assert "secret-one" not in out["Access_Token"]
    assert jwt not in out["nested"][0]["message"]
    assert "<redacted JWT" in out["nested"][0]["message"]
