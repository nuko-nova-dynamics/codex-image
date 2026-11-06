# API recipe: the Images API on the Codex route

Since 0.3.0 the skill calls the same endpoints Codex's built-in image tool calls. openai/codex [#31596](https://github.com/openai/codex/pull/31596) (2026-07-09) made the `image_gen.imagegen` function tool the default. It posts to `<base>/images/generations` and `<base>/images/edits` (`codex-rs/codex-api/src/endpoint/images.rs`). No chat model is involved.

`<base>` is wherever Codex's config sends Codex:

| Route | Base | Generation URL |
| --- | --- | --- |
| ChatGPT sign-in | `https://chatgpt.com/backend-api/codex` | `…/backend-api/codex/images/generations` |
| `openai_base_url` relay | the relay URL, for example `http://127.0.0.1:8318/backend-api/codex` | `…/images/generations` |
| Custom `model_provider` (a proxy) | the provider's `base_url`, for example `http://host:8317/v1` | `…/v1/images/generations` |

## Headers (ChatGPT route)

```text
Authorization: Bearer <tokens.access_token from ~/.codex/auth.json>
ChatGPT-Account-ID: <tokens.account_id>
Content-Type: application/json
Accept: application/json
originator: codex_cli_rs
User-Agent: codex_cli_rs/<installed codex --version>
version: <installed codex --version>
```

A provider route sends `Authorization: Bearer <provider key>` plus the provider's configured headers.

## Generation body

```json
{
  "prompt": "<prompt>",
  "background": "opaque"
}
```

## Edit body

```json
{
  "prompt": "<prompt>",
  "background": "opaque",
  "images": [{"image_url": "data:image/png;base64,..."}]
}
```

Codex also sends `{"file_id": "..."}` references; the skill sends data URLs. `images` is required on `images/edits` (`400 missing_required_parameter` without it).

## Response

```json
{
  "created": 1793987994,
  "data": [{"b64_json": "<PNG>", "generation_id": "…"}],
  "background": "opaque",
  "quality": "low",
  "size": "1536x1024",
  "output_format": "png",
  "usage": {"input_tokens": 17, "output_tokens": 343, "total_tokens": 360}
}
```

The response header `x-codex-imagegen-request-id` carries a request ID. The response does not name the image model.

## What the ChatGPT backend honors

Probed on 2026-11-06 against `chatgpt.com/backend-api/codex` with a Pro plan, a simple prompt, and one call per row.

| Field sent | Result |
| --- | --- |
| `prompt` | Required. Also drives size and quality. |
| `background: "transparent"` | Honored: RGBA output, `background: "transparent"` in the response. See transparency below. |
| `size` (`1024x1024`, `1024x1536`, `2048x1152`, `auto`) | Ignored: every result was `1536x1024`. |
| `quality` (`low`, `medium`, `high`, `auto`, omitted) | Ignored: the backend picked `low` for the cube prompt, `medium` for transparent and dense-text prompts. |
| `model` (`gpt-image-2`, `-2.5`, `-2.6`, `-2.6-flare`, `-1.5`, an unknown name, omitted) | Ignored and never echoed. Not required. |
| `n: 2` | Ignored: one image. |
| `output_format: "jpeg"`/`"webp"`, `output_compression` | Ignored: PNG every time. The skill converts locally. |
| `moderation: "low"` | Accepted; effect not observable. |
| `stream: true`, `partial_images: 1` | Streams `keepalive` then one `image_generation.completed` event; no partial frames. |
| `output_format: "gif"` | `400 GIF output is not enabled for this request.` |
| An unknown field | Accepted silently. |
| `images` with 6, 16 or 17 references | All accepted. The skill keeps its cap of 16. |

The prompt sets the size: "Square 1:1 image: …" returned `1254x1254`, "Tall vertical 9:16 phone wallpaper: …" returned `941x1672`, and a dense infographic returned `1247x1261` at `medium`. Ask for an aspect ratio in the prompt.

The skill still sends `size`, `quality` and `moderation` when the user passes them, because a proxy or a later backend may apply them, and it warns when the response differs. It sends `model` only on a proxy route, where the proxy needs a `gpt-image-*` name to route the request to its Images API path. It picks the newest one the proxy lists under `/models`, or `--image-model`.

## Transparency

Send `background: "transparent"` and append one sentence to the prompt:

> Output the isolated subject on a genuinely transparent background with actual alpha.

Both halves matter. On 2026-11-06, "a ceramic coffee mug" with the parameter alone returned alpha between 12 and 252 everywhere: no fully transparent pixel. With the sentence, about half the pixels were fully transparent and the subject was opaque (alpha 250 or more), with or without the parameter. See `docs/adr/0002-use-the-images-api.md`.

## Removed transport

Before 0.3.0 the skill posted to `<base>/responses` with a chat model ("orchestrator") forced to call the hosted `image_generation` tool. In 2026-11 ChatGPT began passing the request's `reasoning.effort` to the image model as `complexity`, and every value failed with `Complexity '<effort>' is not supported for this image model`. CLIProxyAPI v8.0.58 then rejected those requests outright (router-for-me/CLIProxyAPI#7309). Codex itself had already moved off that path in July.
