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


def test_provider_fields_merge_across_layers(tmp_path, monkeypatch):
    system = _write(tmp_path / "etc/config.toml",
                    'model_provider = "p"\n[model_providers.p]\nbase_url = "http://sys/v1"\n'
                    'experimental_bearer_token = "k"\n')
    _write(tmp_path / "home/config.toml", '[model_providers.p.http_headers]\nX-Team = "a"\n')
    monkeypatch.setattr(codex_route, "SYSTEM_CONFIG", system)
    route = codex_route.resolve_route(codex_route.effective_config(tmp_path / "home"))
    assert (route.base_url, route.bearer_token, route.headers) == ("http://sys/v1", "k", {"X-Team": "a"})


def test_env_headers_and_query_params_follow_the_provider(monkeypatch):
    monkeypatch.setenv("TENANT", "t-9")
    route = codex_route.resolve_route({"model_provider": "p", "model_providers": {"p": {
        "base_url": "http://p/v1", "experimental_bearer_token": "k",
        "env_http_headers": {"X-Tenant": "TENANT", "X-Unset": "NOT_SET_ANYWHERE"},
        "query_params": {"api-version": "2026-10-01"}}}})
    assert route.headers == {"X-Tenant": "t-9"}
    assert route.models_url == "http://p/v1/models?api-version=2026-10-01"
    assert route.url("models", {"client_version": "1.2.3"}).endswith("api-version=2026-10-01&client_version=1.2.3")


def test_requires_openai_auth_provider_stops_clearly():
    with pytest.raises(codex_route.RouteError, match="requires_openai_auth"):
        codex_route.resolve_route({"model_provider": "p", "model_providers": {"p": {
            "base_url": "http://p/v1", "requires_openai_auth": True}}})


def test_unreadable_config_stops_instead_of_falling_back(tmp_path, monkeypatch):
    _write(tmp_path / "home/config.toml", 'model_provider = "p\n')  # unterminated string
    with pytest.raises(codex_route.RouteError, match="Cannot read"):
        codex_route.effective_config(tmp_path / "home")


def test_missing_config_files_mean_the_default_route(tmp_path):
    assert codex_route.resolve_route(codex_route.effective_config(tmp_path / "none")).kind == "chatgpt"
