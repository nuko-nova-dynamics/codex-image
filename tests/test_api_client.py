from __future__ import annotations

import pytest
from api_client import (
    EDITS_PATH,
    GENERATIONS_PATH,
    ParseError,
    build_body,
    build_headers,
    endpoint_path,
    extract_image,
    model_ids,
    newest_image_model,
)


def test_build_body_minimal_generate_omits_unset_fields():
    body = build_body(prompt="a cat")
    assert body == {"prompt": "a cat", "background": "auto"}


def test_build_body_sends_set_fields_and_skips_auto_moderation():
    body = build_body(prompt="x", background="opaque", size="1024x1024", quality="high",
                      moderation="low", model="gpt-image-2")
    assert body == {"prompt": "x", "background": "opaque", "model": "gpt-image-2",
                    "size": "1024x1024", "quality": "high", "moderation": "low"}
    assert "moderation" not in build_body(prompt="x", moderation="auto")


def test_build_body_edit_sends_images_list():
    refs = ["data:image/png;base64,QUFBQQ==", "data:image/png;base64,QkJCQg=="]
    body = build_body(prompt="make it blue", input_images=refs)
    assert body["images"] == [{"image_url": refs[0]}, {"image_url": refs[1]}]


def test_build_body_never_sends_responses_fields():
    body = build_body(prompt="x", size="auto", quality="high", model="gpt-image-2")
    assert {"tools", "tool_choice", "reasoning", "input", "stream", "instructions"}.isdisjoint(body)


def test_endpoint_path_picks_edits_only_with_images():
    assert endpoint_path(build_body(prompt="x")) == GENERATIONS_PATH == "images/generations"
    assert endpoint_path(build_body(prompt="x", input_images=["data:a"])) == EDITS_PATH == "images/edits"


def test_build_headers_set_required_fields():
    """The `version` header must carry the Codex CLI version (the backend gates
    features by it), NOT our skill version."""
    headers = build_headers(access_token="tok-xyz", account_id="acc-123",
                            codex_cli_version="0.128.0")
    assert headers["Authorization"] == "Bearer tok-xyz"
    assert headers["ChatGPT-Account-ID"] == "acc-123"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
    assert headers["originator"] == "codex_cli_rs"
    assert headers["User-Agent"] == "codex_cli_rs/0.128.0"
    assert headers["version"] == "0.128.0"
    assert "OpenAI-Beta" not in headers


def test_newest_image_model_accepts_proxy_prefixed_ids():
    assert newest_image_model([{"slug": "team/gpt-image-2"}, {"slug": "team/gpt-image-2.6-flare"},
                               {"slug": "team/gpt-6.1-sol"}]) == "team/gpt-image-2.6-flare"
    assert newest_image_model([{"slug": "team/gpt-image-2.6"}, {"slug": "gpt-image-2.6"}]) == "gpt-image-2.6"


def test_newest_image_model_orders_by_version_then_plain_over_variant():
    models = [{"slug": s} for s in (
        "gpt-image-1.5", "gpt-image-2.6-flare", "gpt-image-2.5", "gpt-image-2",
        "gpt-image-2.6", "gpt-image-2.6-sunburst", "gpt-6.1-sol")]
    assert newest_image_model(models) == "gpt-image-2.6"
    assert newest_image_model([{"slug": "gpt-image-2.6-flare"}, {"slug": "gpt-image-2.5"}]) == "gpt-image-2.6-flare"
    assert newest_image_model([{"slug": "gpt-image-10"}, {"slug": "gpt-image-9.9"}]) == "gpt-image-10"


def test_newest_image_model_none_for_chat_only_list():
    assert newest_image_model([{"slug": "gpt-6.1-sol"}, {"slug": "gpt-6-luna"}]) is None
    assert newest_image_model([]) is None


def test_model_ids_reads_codex_and_proxy_lists():
    assert [m["slug"] for m in model_ids({"models": [{"slug": "a"}]})] == ["a"]
    assert [m["slug"] for m in model_ids({"data": [{"id": "b"}, {"object": "model"}]})] == ["b"]


def test_extract_image_returns_b64_and_metadata():
    b64, meta = extract_image({
        "created": 1, "data": [{"b64_json": "QUJD", "generation_id": "g1", "revised_prompt": "rp"}],
        "size": "1536x1024", "quality": "low", "background": "opaque", "output_format": "png",
        "usage": {"total_tokens": 5},
    })
    assert b64 == "QUJD"
    assert meta["generation_id"] == "g1"
    assert meta["revised_prompt"] == "rp"
    assert meta["resolved_size"] == "1536x1024"
    assert meta["resolved_quality"] == "low"
    assert meta["resolved_background"] == "opaque"
    assert meta["usage"] == {"total_tokens": 5}
    assert meta["image_count"] == 1


@pytest.mark.parametrize("resp, match", [
    (["not", "a", "dict"], "not a JSON object"),
    ({"data": []}, "no image"),
    ({}, "no image"),
    ({"data": [{"generation_id": "g1"}]}, "no image"),
])
def test_extract_image_errors(resp, match):
    with pytest.raises(ParseError, match=match):
        extract_image(resp)
