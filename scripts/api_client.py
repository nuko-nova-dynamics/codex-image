"""Build and read Images API requests the way Codex's built-in image tool does.

Since openai/codex #31596 (2026-07-09) Codex generates images with its
`image_gen.imagegen` function tool, which calls `<base>/images/generations`
and `<base>/images/edits` directly (codex-rs/codex-api/src/endpoint/images.rs).
There is no chat model in the loop, so nothing like `reasoning` reaches the
image model. The older transport (a Responses call that forced the hosted
`image_generation` tool) is removed: ChatGPT began rejecting it in 2026-11 with
"Complexity '<effort>' is not supported for this image model".

Live checks on 2026-11-06 against chatgpt.com/backend-api/codex (Pro plan):
the backend chooses size, quality and image model from the prompt. It accepts
`size`, `quality`, `n`, `output_format`, `output_compression`, `moderation`,
`model` and unknown fields without error but does not apply them, and always
returns one PNG. `background: "transparent"` is honored and returns RGBA.
`images` is required on edits. See references/api-recipe.md.
"""
from __future__ import annotations

import re

GENERATIONS_PATH = "images/generations"
EDITS_PATH = "images/edits"


class ParseError(Exception):
    """The response held no image or was not the expected JSON shape."""


def build_body(
    *,
    prompt: str,
    background: str = "auto",
    size: str | None = None,
    quality: str | None = None,
    moderation: str | None = None,
    model: str | None = None,
    input_images: list[str] | None = None,
) -> dict:
    """Request body for images/generations, or images/edits when input_images is set.

    Fields mirror Codex's ImageGenerationRequest / ImageEditRequest. `size`,
    `quality` and `moderation` are sent only when the caller set them; the
    ChatGPT backend currently ignores them, but a proxy or a future backend
    may not. `model` is sent only when known: a proxy needs it to route the
    request to its Images API path, while ChatGPT ignores it.
    """
    body: dict = {"prompt": prompt, "background": background}
    if model:
        body["model"] = model
    if size:
        body["size"] = size
    if quality:
        body["quality"] = quality
    if moderation and moderation != "auto":
        body["moderation"] = moderation
    if input_images:
        body["images"] = [{"image_url": url} for url in input_images]
    return body


def endpoint_path(body: dict) -> str:
    return EDITS_PATH if body.get("images") else GENERATIONS_PATH


def build_headers(
    *, access_token: str, account_id: str, codex_cli_version: str,
) -> dict[str, str]:
    """Headers for the ChatGPT route, as the Codex CLI sends them.

    `codex_cli_version` MUST be the user's installed Codex CLI version. The
    backend gates features by this header and answers older versions with
    HTTP 400 'requires a newer version of Codex'.
    """
    return {
        "Authorization": f"Bearer {access_token}",
        "ChatGPT-Account-ID": account_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
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


_IMAGE_MODEL = re.compile(r"gpt-image-(\d+(?:\.\d+)*)(-[a-z0-9-]+)?")


def newest_image_model(models: list[dict]) -> str | None:
    """The highest-versioned `gpt-image-*` model a route lists.

    At equal versions the plain name (`gpt-image-2.6`) wins over a variant
    (`gpt-image-2.6-flare`), and an unprefixed ID over a proxy-prefixed one
    (`team/gpt-image-2.6`). A prefixed ID is matched on its last path part and
    returned whole, because the proxy routes on the prefix. Returns None when
    the list has no image model, which is normal for the ChatGPT catalog: it
    lists chat models only.
    """
    best: tuple[tuple[int, ...], int, int, str] | None = None
    for m in models:
        slug = m.get("slug") or ""
        if match := _IMAGE_MODEL.fullmatch(slug.rsplit("/", 1)[-1]):
            version = tuple(int(part) for part in match.group(1).split("."))
            key = (version, 0 if match.group(2) else 1, 0 if "/" in slug else 1, slug)
            if best is None or key[:3] > best[:3]:
                best = key
    return best[3] if best else None


def extract_image(resp: dict) -> tuple[str, dict]:
    """Return (b64, metadata) from an Images API JSON response."""
    if not isinstance(resp, dict):
        raise ParseError("response was not a JSON object")
    data = resp.get("data")
    if not isinstance(data, list) or not data:
        raise ParseError("no image in response (empty data)")
    first = data[0] if isinstance(data[0], dict) else {}
    b64 = first.get("b64_json")
    if not b64:
        raise ParseError("no image in response (data[0] has no b64_json)")
    meta = {
        "generation_id": first.get("generation_id"),
        "revised_prompt": first.get("revised_prompt"),
        "resolved_size": resp.get("size"),
        "resolved_quality": resp.get("quality"),
        "resolved_background": resp.get("background"),
        "output_format": resp.get("output_format"),
        "usage": resp.get("usage"),
        "image_count": len(data),
    }
    return b64, meta
