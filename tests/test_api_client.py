from __future__ import annotations

import pytest
from api_client import (
    build_body,
    build_headers,
)


def test_build_body_minimal_generate():
    body = build_body(prompt="a cat", size="1024x1024", quality="high", output_format="png")
    assert body["model"] == "gpt-5.5"
    assert body["stream"] is True
    assert body["store"] is False
    assert body["parallel_tool_calls"] is False
    assert body["reasoning"] == {"effort": "xhigh"}
    assert body["tool_choice"] == {
        "type": "allowed_tools",
        "mode": "required",
        "tools": [{"type": "image_generation"}],
    }
    tool = body["tools"][0]
    assert tool["type"] == "image_generation"
    assert tool["size"] == "1024x1024"
    assert tool["quality"] == "high"
    assert tool["output_format"] == "png"
    assert tool["background"] == "opaque"
    assert "action" not in tool  # not in edit mode
    msg = body["input"][0]
    assert msg["role"] == "user"
    assert msg["content"][0] == {"type": "input_text", "text": "a cat"}


def test_build_body_jpeg_includes_compression():
    body = build_body(
        prompt="x", size="1024x1024", quality="high",
        output_format="jpeg", quality_jpeg=75,
    )
    tool = body["tools"][0]
    assert tool["output_format"] == "jpeg"
    assert tool["output_compression"] == 75


def test_build_body_webp_requests_png_for_local_conversion():
    body = build_body(prompt="x", size="1024x1024", quality="high", output_format="webp")
    tool = body["tools"][0]
    # Backend webp is broken; we request png and convert locally.
    assert tool["output_format"] == "png"
    assert "output_compression" not in tool


def test_build_body_edit_mode_with_input_image():
    body = build_body(
        prompt="make it blue",
        size="1024x1024", quality="medium", output_format="png",
        input_images=["data:image/png;base64,QUFBQQ=="],
    )
    tool = body["tools"][0]
    assert tool["action"] == "edit"
    content = body["input"][0]["content"]
    # Spec: input_image first, references after, text last
    assert content[0]["type"] == "input_image"
    assert content[-1]["type"] == "input_text"


def test_build_body_rejects_more_than_16_input_images():
    refs = [f"data:image/png;base64,A{i}" for i in range(17)]
    with pytest.raises(ValueError, match="max is 16"):
        build_body(
            prompt="x", size="1024x1024", quality="high",
            output_format="png", input_images=refs,
        )


def test_build_body_lowers_quality_minimal_to_low():
    body = build_body(
        prompt="x", size="1024x1024", quality="high",
        output_format="png", reasoning_effort="minimal",
    )
    # 'minimal' is rejected by backend for image_gen; transform to 'low'.
    assert body["reasoning"] == {"effort": "low"}


def test_build_body_omits_rejected_keys():
    body = build_body(prompt="x", size="1024x1024", quality="high", output_format="png")
    rejected = {"n", "previous_response_id", "max_tool_calls", "max_output_tokens"}
    assert rejected.isdisjoint(body.keys())
    assert rejected.isdisjoint(body["tools"][0].keys())


def test_build_headers_set_required_fields():
    """The `version` header must carry the Codex CLI version (which the backend
    gates feature/model access by), NOT our skill version. Tracer-bullet run
    proved 'gpt-5.5' is rejected with HTTP 400 'requires a newer version of
    Codex' when version is too low. See generate.py main() for runtime detection
    via `codex --version`."""
    headers = build_headers(access_token="tok-xyz", account_id="acc-123",
                            codex_cli_version="0.128.0")
    assert headers["Authorization"] == "Bearer tok-xyz"
    assert headers["ChatGPT-Account-ID"] == "acc-123"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "text/event-stream"
    assert headers["originator"] == "codex_cli_rs"
    assert headers["User-Agent"] == "codex_cli_rs/0.128.0"
    assert headers["version"] == "0.128.0"
    # OpenAI-Beta is intentionally not set (WebSocket-only).
    assert "OpenAI-Beta" not in headers
