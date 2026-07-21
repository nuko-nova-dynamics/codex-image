"""Token redaction for verbose output and error logs (spec §5)."""
from __future__ import annotations

import re
from typing import Any

_BEARER_RE = re.compile(r"Bearer\s+([^\s\"',]+)", re.IGNORECASE)
_QUOTED_TOKEN_RE = re.compile(
    r"(?P<prefix>(?P<key_quote>['\"]?)(?P<key>access_token|id_token|refresh_token)"
    r"(?P=key_quote)\s*[:=]\s*)(?P<value_quote>['\"])(?P<value>.*?)"
    r"(?P=value_quote)",
    re.IGNORECASE,
)
_UNQUOTED_TOKEN_RE = re.compile(
    r"(?P<prefix>(?P<key_quote>['\"]?)(?P<key>access_token|id_token|refresh_token)"
    r"(?P=key_quote)\s*[:=]\s*)(?P<value>[^\s'\",;&}\]]+)",
    re.IGNORECASE,
)
_JWT_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])"
    r"(?P<jwt>eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)"
    r"(?![A-Za-z0-9_-]|\.[A-Za-z0-9_-])"
)
_SENSITIVE_KEYS = {"access_token", "id_token", "refresh_token"}


def redact_text(s: str) -> str:
    """Replace bearer tokens, token fields, and bare JWTs in arbitrary text."""
    s = _BEARER_RE.sub(lambda m: f"Bearer <redacted, len={len(m.group(1))}>", s)
    s = _QUOTED_TOKEN_RE.sub(
        lambda m: (
            f"{m.group('prefix')}{m.group('value_quote')}"
            f"<redacted, len={len(m.group('value'))}>{m.group('value_quote')}"
        ),
        s,
    )
    s = _UNQUOTED_TOKEN_RE.sub(
        lambda m: f"{m.group('prefix')}<redacted, len={len(m.group('value'))}>",
        s,
    )
    s = _JWT_RE.sub(
        lambda m: f"<redacted JWT, len={len(m.group('jwt'))}>",
        s,
    )
    return s


def redact_dict(obj: Any) -> Any:
    """Deep-redact a dict-like structure; returns a new copy."""
    if isinstance(obj, dict):
        out: dict = {}
        for k, v in obj.items():
            key = k.lower() if isinstance(k, str) else None
            if key in _SENSITIVE_KEYS and isinstance(v, str):
                out[k] = f"<redacted, len={len(v)}>"
            elif key == "authorization" and isinstance(v, str):
                # Expect "Bearer xxx" — keep prefix, redact value
                redacted = redact_text(v)
                if redacted != v:
                    out[k] = redacted
                else:
                    out[k] = f"<redacted, len={len(v)}>"
            else:
                out[k] = redact_dict(v)
        return out
    if isinstance(obj, list):
        return [redact_dict(x) for x in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj
