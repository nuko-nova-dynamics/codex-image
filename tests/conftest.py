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
