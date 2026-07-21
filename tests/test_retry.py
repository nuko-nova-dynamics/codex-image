from __future__ import annotations

import urllib.error

import pytest
import retry as retry_mod
from retry import call_with_retries


def test_succeeds_on_first_try():
    calls = {"n": 0}
    def f():
        calls["n"] += 1
        return "ok"
    assert call_with_retries(f) == "ok"
    assert calls["n"] == 1


def test_retries_on_5xx():
    calls = {"n": 0}
    def f():
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError("u", 503, "x", {}, None)
        return "ok"
    assert call_with_retries(f, max_attempts=4, base_delay=0.001) == "ok"
    assert calls["n"] == 3


@pytest.mark.parametrize(("header", "expected_delay"), [("7", 7), ("45", 30)])
def test_retry_after_integer_seconds_is_honored_and_capped(
    header, expected_delay, monkeypatch
):
    calls = {"n": 0}
    sleeps = []

    def f():
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(
                "u", 503, "x", {"Retry-After": header}, None
            )
        return "ok"

    monkeypatch.setattr(retry_mod.time, "sleep", sleeps.append)
    assert call_with_retries(f) == "ok"
    assert sleeps == [expected_delay]


def test_does_not_retry_on_429():
    calls = {"n": 0}
    def f():
        calls["n"] += 1
        raise urllib.error.HTTPError("u", 429, "x", {}, None)
    with pytest.raises(urllib.error.HTTPError):
        call_with_retries(f, max_attempts=4, base_delay=0.001)
    assert calls["n"] == 1


def test_does_not_retry_on_401():
    calls = {"n": 0}
    def f():
        calls["n"] += 1
        raise urllib.error.HTTPError("u", 401, "x", {}, None)
    with pytest.raises(urllib.error.HTTPError):
        call_with_retries(f, max_attempts=4, base_delay=0.001)
    assert calls["n"] == 1


def test_does_not_retry_on_timeout():
    """Spec §10: SSE idle timeouts must NOT auto-retry (user retries manually)."""
    calls = {"n": 0}
    def f():
        calls["n"] += 1
        raise TimeoutError("idle stream")
    with pytest.raises(TimeoutError):
        call_with_retries(f, max_attempts=4, base_delay=0.001)
    assert calls["n"] == 1


def test_gives_up_after_max_attempts():
    calls = {"n": 0}
    def f():
        calls["n"] += 1
        raise urllib.error.HTTPError("u", 502, "x", {}, None)
    with pytest.raises(urllib.error.HTTPError):
        call_with_retries(f, max_attempts=3, base_delay=0.001)
    assert calls["n"] == 3


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (urllib.error.URLError("request failed with eyJabc.def.ghi"), "network error"),
        (TimeoutError("request timed out with eyJabc.def.ghi"), "timed out"),
    ],
)
def test_post_with_error_handling_catches_network_errors(
    error, expected, monkeypatch, capsys
):
    import generate

    def boom(**kwargs):
        raise error

    monkeypatch.setattr(generate, "post_responses", boom)
    monkeypatch.setattr(generate.retry_mod, "call_with_retries", lambda fn: fn())

    sse, exit_code = generate._post_with_error_handling(body={}, headers={})
    err = capsys.readouterr().err
    assert sse is None
    assert exit_code == 1
    assert err.startswith("✗")
    assert expected in err.lower()
    assert "eyJabc.def.ghi" not in err
    assert "<redacted JWT" in err
