"""Build Codex Responses API requests for GPT Image generation."""
from __future__ import annotations

DEFAULT_ENDPOINT = "https://chatgpt.com/backend-api/codex/responses"
MODELS_ENDPOINT = "https://chatgpt.com/backend-api/codex/models"

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
    orchestrator_model: str,
    image_model: str | None = None,
    reasoning_effort: str = "xhigh",
    instructions: str | None = None,
) -> dict:
    """Construct the Codex Responses request body per spec section 4.

    Args:
        output_format: "png" | "jpeg" | "webp". WebP requests PNG on the wire
            (we convert locally) since the backend ignores webp.
        input_images: list of data URLs / URLs / file_ids. Up to 16
            references (the skill cap). Triggers edit mode.
        image_model: Optional image-tool model request. Codex Responses may
            override it; only response metadata identifies the resolved model.
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
    if image_model is not None:
        tool["model"] = image_model
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
    access by this header — older versions get HTTP 400
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


def model_ids(catalog: dict) -> list[dict]:
    """Normalize a model list: Codex's catalog (`models[].slug`) or an
    OpenAI-style list from a proxy (`data[].id`)."""
    entries = catalog.get("models") or catalog.get("data") or []
    return [{**m, "slug": m.get("slug") or m.get("id")} for m in entries
            if isinstance(m, dict) and (m.get("slug") or m.get("id"))]


def newest_sol_model(models: list[dict]) -> str | None:
    """The highest-versioned Sol-tier model (`gpt-<version>-sol`) the account lists.

    Sol is the tier the image tool needs; Astra is the top tier and Luna the
    small one. Aliases such as `gpt-sol-latest` carry no version and are
    skipped, as are models Codex hides from its picker.
    """
    import re
    best: tuple[tuple[int, ...], str] | None = None
    for m in models:
        if m.get("visibility") == "hide":
            continue
        if match := re.fullmatch(r"gpt-(\d+(?:\.\d+)*)-sol", m.get("slug") or ""):
            version = tuple(int(part) for part in match.group(1).split("."))
            if best is None or version > best[0]:
                best = (version, m["slug"])
    return best[1] if best else None


def codex_default_model(models: list[dict]) -> str | None:
    """Pick the model Codex itself treats as the default for this account.

    Mirrors Codex's own rule (`mark_default_by_picker_visibility` in
    openai/codex): sort the account's catalog by `priority`, take the first
    model shown in the picker, else the first model at all.
    """
    ranked = sorted((m for m in models if m.get("slug")),
                    key=lambda m: m.get("priority", float("inf")))
    for model in ranked:
        if model.get("visibility") == "list":
            return model["slug"]
    return ranked[0]["slug"] if ranked else None
