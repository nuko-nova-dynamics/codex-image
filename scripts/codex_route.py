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

    @property
    def responses_url(self) -> str:
        return f"{self.base_url}/responses"

    @property
    def models_url(self) -> str:
        return f"{self.base_url}/models"


def _load(path: Path) -> dict:
    if tomllib is None:
        return {}
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except (OSError, ValueError):
        return {}


def effective_config(codex_home: Path | None = None) -> dict:
    """Merge the system and user config layers, user winning."""
    home = codex_home or Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    system, user = _load(SYSTEM_CONFIG), _load(home / "config.toml")
    merged = {**system, **user}
    providers = {**(system.get("model_providers") or {}), **(user.get("model_providers") or {})}
    if providers:
        merged["model_providers"] = providers
    return merged


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
    token = provider.get("experimental_bearer_token")
    if not token and (env_key := provider.get("env_key")):
        token = os.environ.get(env_key)
        if not token:
            raise RouteError(f"Codex model_provider '{name}' reads its key from ${env_key}, "
                             "which is not set.")
    return Route(kind="provider", name=name, base_url=provider["base_url"].rstrip("/"),
                 bearer_token=token, headers=dict(provider.get("http_headers") or {}))


def provider_headers(route: Route) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream", **route.headers}
    if route.bearer_token:
        headers["Authorization"] = f"Bearer {route.bearer_token}"
    return headers
