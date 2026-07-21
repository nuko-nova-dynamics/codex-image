"""Auth file discovery and JWT decoding for codex-image skill.

Read-only — never writes back to auth.json. Tokens never logged.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path


class AuthError(Exception):
    """Raised when auth cannot be resolved."""


@dataclass
class AuthFile:
    auth_mode: str
    access_token: str = field(repr=False)
    id_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    account_id: str
    last_refresh: str | None
    path: Path


def discover_auth_file() -> Path | None:
    """Return the first readable auth.json from the discovery chain.

    Order: $CODEX_HOME → $CHATGPT_LOCAL_HOME → ~/.codex → ~/.chatgpt-local.
    """
    home = Path(os.environ.get("HOME", str(Path.home())))
    candidates = []
    if env := os.environ.get("CODEX_HOME"):
        candidates.append(Path(env) / "auth.json")
    if env := os.environ.get("CHATGPT_LOCAL_HOME"):
        candidates.append(Path(env) / "auth.json")
    candidates.append(home / ".codex" / "auth.json")
    candidates.append(home / ".chatgpt-local" / "auth.json")
    for c in candidates:
        if c.is_file() and os.access(c, os.R_OK):
            return c
    return None


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def decode_account_id_from_jwt(jwt: str) -> str | None:
    """Extract chatgpt_account_id from a JWT id_token.

    Tries the namespaced claim first, then top-level fallback.
    Returns None on any decode failure (no exception — caller decides).
    """
    try:
        parts = jwt.split(".")
        if len(parts) < 2:
            return None
        claims = json.loads(_b64url_decode(parts[1]))
    except Exception:
        return None
    ns = claims.get("https://api.openai.com/auth")
    if isinstance(ns, dict) and (acc := ns.get("chatgpt_account_id")):
        return acc
    if acc := claims.get("chatgpt_account_id"):
        return acc
    return None


def load_auth(path: Path) -> AuthFile:
    """Load and validate an auth.json. Raises AuthError on any problem.

    Token values are never echoed back via the exception message.
    """
    if not path.exists():
        raise AuthError(f"Codex CLI not signed in (no auth at {path}). Run: codex login")

    # Spec §5: warn on lax permissions (don't fail; user is in control of their dotfiles).
    try:
        mode_bits = path.stat().st_mode & 0o777
        if mode_bits & 0o077:  # any group or other access bit set
            import sys as _sys
            print(
                f"⚠ {path} permissions are {oct(mode_bits)}; recommend 0600. "
                f"Run: chmod 600 {path}",
                file=_sys.stderr,
            )
    except OSError:
        pass  # stat failure is non-fatal — best-effort security hygiene

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise AuthError(f"auth file at {path} is not valid JSON ({e}); re-run codex login") from e

    mode = data.get("auth_mode")
    if mode == "apikey":
        raise AuthError(
            "Skill uses ChatGPT subscription auth, not apikey. "
            "Re-run: codex login (with the OAuth flow, not API key)."
        )
    if mode != "chatgpt":
        raise AuthError(f"unsupported auth_mode {mode!r}; re-run: codex login")

    tokens = data.get("tokens") or {}
    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token") or ""
    refresh_token = tokens.get("refresh_token") or ""
    account_id = tokens.get("account_id")

    if not access_token:
        raise AuthError("auth file is missing tokens.access_token; re-run: codex login")
    if not account_id:
        # Fall back to JWT claim
        account_id = decode_account_id_from_jwt(id_token)
        if not account_id:
            raise AuthError(
                "auth file appears corrupt (no chatgpt_account_id in id_token claim or top-level field); "
                "re-run: codex login"
            )

    return AuthFile(
        auth_mode=mode,
        access_token=access_token,
        id_token=id_token,
        refresh_token=refresh_token,
        account_id=account_id,
        last_refresh=data.get("last_refresh"),
        path=path,
    )


def decode_id_token_claims(jwt: str) -> dict:
    """Best-effort extraction of email / plan / fedramp from id_token. Returns {} on failure."""
    try:
        parts = jwt.split(".")
        if len(parts) < 2:
            return {}
        return json.loads(_b64url_decode(parts[1]))
    except Exception:
        return {}


def summarize_account(auth: AuthFile) -> dict:
    """Human-readable summary for --whoami / banner.

    Note: `exp` is read from the access_token (the credential the API actually
    validates), not the id_token — the two can rotate independently and the
    id_token's exp may be stale while the access_token is still fresh.
    """
    id_claims = decode_id_token_claims(auth.id_token)
    access_claims = decode_id_token_claims(auth.access_token)
    ns = id_claims.get("https://api.openai.com/auth") or {}
    return {
        "email": id_claims.get("email"),
        "plan": ns.get("chatgpt_plan_type") or "unknown",
        "organization_id": ns.get("organization_id"),
        "fedramp": bool(ns.get("chatgpt_account_is_fedramp")),
        "account_id": auth.account_id,
        "auth_file": str(auth.path),
        "exp": access_claims.get("exp"),  # access_token exp drives API validity
    }
