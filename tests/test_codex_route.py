from __future__ import annotations

import codex_route
import pytest


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_user_config_overrides_system(tmp_path, monkeypatch):
    system = _write(tmp_path / "etc/config.toml", 'openai_base_url = "http://system"\nmodel = "sys-model"\n')
    _write(tmp_path / "home/config.toml", 'openai_base_url = "http://user"\n')
    monkeypatch.setattr(codex_route, "SYSTEM_CONFIG", system)
    config = codex_route.effective_config(tmp_path / "home")
    assert config["openai_base_url"] == "http://user"
    assert config["model"] == "sys-model"


def test_default_route_is_chatgpt():
    route = codex_route.resolve_route({})
    assert (route.kind, route.base_url) == ("chatgpt", codex_route.CHATGPT_BASE_URL)
    assert route.responses_url == codex_route.CHATGPT_BASE_URL + "/responses"


def test_openai_base_url_keeps_chatgpt_sign_in_at_the_relay():
    route = codex_route.resolve_route({"openai_base_url": "http://127.0.0.1:8318/backend-api/codex/"})
    assert route.kind == "chatgpt"
    assert route.models_url == "http://127.0.0.1:8318/backend-api/codex/models"


def test_custom_provider_route_uses_its_url_and_key():
    route = codex_route.resolve_route({
        "model_provider": "proxy",
        "model_providers": {"proxy": {"base_url": "http://127.0.0.1:8317/v1",
                                      "experimental_bearer_token": "k-1",
                                      "http_headers": {"X-Test": "1"}}},
    })
    assert (route.kind, route.responses_url) == ("provider", "http://127.0.0.1:8317/v1/responses")
    headers = codex_route.provider_headers(route)
    assert headers["Authorization"] == "Bearer k-1"
    assert headers["X-Test"] == "1"


def test_provider_env_key_must_be_set(monkeypatch):
    monkeypatch.delenv("PROXY_KEY", raising=False)
    config = {"model_provider": "proxy",
              "model_providers": {"proxy": {"base_url": "http://p/v1", "env_key": "PROXY_KEY"}}}
    with pytest.raises(codex_route.RouteError, match="PROXY_KEY"):
        codex_route.resolve_route(config)
    monkeypatch.setenv("PROXY_KEY", "k-2")
    assert codex_route.resolve_route(config).bearer_token == "k-2"


def test_provider_without_responses_api_is_rejected():
    with pytest.raises(codex_route.RouteError, match="Responses"):
        codex_route.resolve_route({"model_provider": "chat",
                                   "model_providers": {"chat": {"base_url": "http://c", "wire_api": "chat"}}})
