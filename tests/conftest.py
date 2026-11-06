"""Shared pytest fixtures."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _b64url(data: dict) -> str:
    raw = json.dumps(data).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _make_jwt(claims: dict) -> str:
    """Build a minimal unsigned JWT for tests. Header + payload + dot-fake-sig."""
    header = _b64url({"alg": "RS256", "typ": "JWT"})
    payload = _b64url(claims)
    return f"{header}.{payload}.fakesig"


@pytest.fixture
def make_jwt():
    """Factory: make_jwt({'exp': 1234, ...}) -> JWT string."""
    return _make_jwt


@pytest.fixture
def fixture_dir() -> Path:
    return FIXTURE_DIR


# What a proxy's /models lists: chat models plus the gpt-image models it can
# route to its Images API path. The ChatGPT route never fetches a model list.
PROVIDER_MODELS = [
    {"slug": "gpt-6.1-sol"},
    {"slug": "gpt-image-2"},
    {"slug": "gpt-image-2.6-flare"},
    {"slug": "gpt-image-2.6"},
]


@pytest.fixture(autouse=True)
def _offline_model_catalog(monkeypatch):
    """Tests never reach a live model list; individual tests override this."""
    import generate
    monkeypatch.setattr(generate, "fetch_models", lambda **kw: list(PROVIDER_MODELS))
    for var in ("CODEX_IMAGE_ORCHESTRATOR", "CODEX_IMAGE_MODEL", "CODEX_IMAGE_SIZE",
                "CODEX_IMAGE_QUALITY", "CODEX_IMAGE_FORMAT", "CODEX_IMAGE_OUT_DIR"):
        monkeypatch.delenv(var, raising=False)
    import codex_route
    monkeypatch.setattr(codex_route, "SYSTEM_CONFIG", FIXTURE_DIR / "no-such-system-config.toml")


def images_response(b64: str | None = None, **overrides) -> dict:
    """An Images API JSON response as the ChatGPT backend returns it."""
    if b64 is None:
        b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKEPNGBYTES").decode()
    resp = {
        "created": 1,
        "data": [{"b64_json": b64, "generation_id": "g1"}],
        "size": "1536x1024",
        "quality": "low",
        "background": "opaque",
        "output_format": "png",
        "usage": {"input_tokens": 17, "output_tokens": 343, "total_tokens": 360},
    }
    resp.update(overrides)
    return resp


@pytest.fixture
def fake_images_response():
    """Factory: fake_images_response(b64=None, **top_level_overrides) -> dict."""
    return images_response
