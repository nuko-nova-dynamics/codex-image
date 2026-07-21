"""Build Codex Responses API requests for gpt-image-2 image generation."""
from __future__ import annotations

DEFAULT_ENDPOINT = "https://chatgpt.com/backend-api/codex/responses"

_VALID_EFFORTS = {"low", "medium", "high", "xhigh"}
_REJECTED_BACKEND = {"n", "previous_response_id", "max_tool_calls", "max_output_tokens"}


def build_body(
    *,
    prompt: str,
    size: str,
    quality: str,
    output_format: str,
    background: str = "opaque",
    moderation: str | None = None,
    quality_jpeg: int = 90,
    input_images: list[str] | None = None,
    orchestrator_model: str = "gpt-5.5",
    reasoning_effort: str = "xhigh",
    instructions: str | None = None,
) -> dict:
    """Construct the Codex Responses request body per spec section 4.

    Args:
        output_format: "png" | "jpeg" | "webp". WebP requests PNG on the wire
            (we convert locally) since the backend ignores webp.
        input_images: list of data URLs / URLs / file_ids. Up to 16 (gpt-image-2
            model limit, per the official image-edit API types). Triggers edit mode.
        reasoning_effort: 'minimal'/'none' are rejected for image_gen; we silently
            promote to 'low'.
    """
    if input_images and len(input_images) > 16:
        raise ValueError(f"too many input references: got {len(input_images)}, max is 16")

    if reasoning_effort not in _VALID_EFFORTS:
        reasoning_effort = "low"

    # Wire format. Omit local-only formats (webp); request png and convert locally.
    wire_format = output_format if output_format in ("png", "jpeg") else "png"

    tool: dict = {
        "type": "image_generation",
        "size": size,
        "quality": quality,
        "output_format": wire_format,
        "background": background,
    }
    if wire_format == "jpeg":
        tool["output_compression"] = quality_jpeg
    if moderation:
        tool["moderation"] = moderation
    if input_images:
        tool["action"] = "edit"

    # User content: image refs first, text last (spec section 8 edit body order).
    user_content: list[dict] = []
    for ref in input_images or []:
        user_content.append({"type": "input_image", "image_url": ref})
    user_content.append({"type": "input_text", "text": prompt})

    body = {
        "model": orchestrator_model,
        "instructions": instructions or (
            "Pass-through image generator. Call image_generation exactly once "
            "with the user's prompt verbatim. No commentary."
        ),
        "input": [{"type": "message", "role": "user", "content": user_content}],
        "tools": [tool],
        "tool_choice": {
            "type": "allowed_tools",
            "mode": "required",
            "tools": [{"type": "image_generation"}],
        },
        "reasoning": {"effort": reasoning_effort},
        "parallel_tool_calls": False,
        "store": False,
        "stream": True,
    }
    return body


def build_headers(
    *, access_token: str, account_id: str, codex_cli_version: str,
) -> dict[str, str]:
    """Headers per spec section 4. OpenAI-Beta is intentionally absent (WebSocket-only).

    `codex_cli_version` MUST be the user's installed Codex CLI version (or
    a current one), not our skill version. The Codex backend gates feature
    access (e.g. gpt-5.5) by this header — older versions get HTTP 400
    'requires a newer version of Codex'. The caller is responsible for
    detecting the right value at runtime (see generate.py main()).
    """
    return {
        "Authorization": f"Bearer {access_token}",
        "ChatGPT-Account-ID": account_id,
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "originator": "codex_cli_rs",
        "User-Agent": f"codex_cli_rs/{codex_cli_version}",
        "version": codex_cli_version,
    }
