"""Send requests where Codex sends them, per Codex's own config.toml layers.

Codex resolves config from the user file ($CODEX_HOME/config.toml) over the
system file (/etc/codex/config.toml) over built-in defaults. This module reads
those two layers and returns the route Codex would use:

- a custom `model_provider` (for example a proxy): its `base_url`, its bearer
  token, and no ChatGPT sign-in;
- otherwise the built-in OpenAI provider with ChatGPT sign-in, at
  `openai_base_url` when set (for example a local relay), else chatgpt.com.

Project and profile layers are not read; they rarely change routing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None

CHATGPT_BASE_URL = "https://chatgpt.com/backend-api/codex"
SYSTEM_CONFIG = Path("/etc/codex/config.toml")


class RouteError(Exception):
    """Codex's config names a route this script cannot use."""


@dataclass
class Route:
    kind: str  # "chatgpt" (ChatGPT sign-in) or "provider" (custom model provider)
    name: str
    base_url: str
    bearer_token: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, str] = field(default_factory=dict)

    def url(self, path: str, extra: dict[str, str] | None = None) -> str:
        params = {**self.query_params, **(extra or {})}
        return f"{self.base_url}/{path}" + (f"?{urlencode(params)}" if params else "")

    @property
    def responses_url(self) -> str:
        return self.url("responses")

    @property
    def models_url(self) -> str:
        return self.url("models")


def _load(path: Path) -> dict:
    """Read one config layer. A missing file is an empty layer; a file that
    exists but cannot be read stops the run, so a broken config never silently
    sends requests somewhere the user did not configure."""
    if not path.exists():
        return {}
    if tomllib is None:
        raise RouteError(f"Reading Codex's config ({path}) needs Python 3.11 or later.")
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except (OSError, ValueError) as e:
        raise RouteError(f"Cannot read Codex's config {path}: {e}") from e


def _merge(base: dict, override: dict) -> dict:
    """Recursive merge, override winning, as Codex layers its config."""
    out = dict(base)
    for key, value in override.items():
        out[key] = (_merge(out[key], value) if isinstance(value, dict)
                    and isinstance(out.get(key), dict) else value)
    return out


def effective_config(codex_home: Path | None = None) -> dict:
    """Merge the system and user config layers, user winning."""
    home = codex_home or Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    return _merge(_load(SYSTEM_CONFIG), _load(home / "config.toml"))


def resolve_route(config: dict) -> Route:
    name = config.get("model_provider") or "openai"
    if name == "openai":
        base = config.get("openai_base_url") or CHATGPT_BASE_URL
        return Route(kind="chatgpt", name=name, base_url=base.rstrip("/"))

    provider = (config.get("model_providers") or {}).get(name)
    if not provider or not provider.get("base_url"):
        raise RouteError(f"Codex model_provider '{name}' has no base_url in config.toml.")
    if provider.get("wire_api", "responses") != "responses":
        raise RouteError(f"Codex model_provider '{name}' does not use the Responses API.")
    if provider.get("requires_openai_auth"):
        raise RouteError(f"Codex model_provider '{name}' uses requires_openai_auth, which this "
                         "script does not support yet. Give the provider its own key "
                         "(experimental_bearer_token or env_key), or use the built-in OpenAI route.")
    token = provider.get("experimental_bearer_token")
    if not token and (env_key := provider.get("env_key")):
        token = os.environ.get(env_key)
        if not token:
            raise RouteError(f"Codex model_provider '{name}' reads its key from ${env_key}, "
                             "which is not set.")
    headers = dict(provider.get("http_headers") or {})
    for header, env_var in (provider.get("env_http_headers") or {}).items():
        if value := os.environ.get(env_var):
            headers[header] = value
    return Route(kind="provider", name=name, base_url=provider["base_url"].rstrip("/"),
                 bearer_token=token, headers=headers,
                 query_params={k: str(v) for k, v in (provider.get("query_params") or {}).items()})


def provider_headers(route: Route) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream", **route.headers}
    if route.bearer_token:
        headers["Authorization"] = f"Bearer {route.bearer_token}"
    return headers
