# API recipe — canonical Codex Responses request

## Endpoint

`POST https://chatgpt.com/backend-api/codex/responses`

## Headers (required)

| Header | Value |
| --- | --- |
| `Authorization` | `Bearer <tokens.access_token>` |
| `ChatGPT-Account-ID` | `<tokens.account_id>` (PascalCase exact) |
| `Content-Type` | `application/json` |
| `Accept` | `text/event-stream` |
| `originator` | `codex_cli_rs` |
| `User-Agent` | `codex_cli_rs/<codex_cli_version>` |
| `version` | `<codex_cli_version>` |

`OpenAI-Beta` is NEVER sent — that header is WebSocket-only.

The `version` and `User-Agent` carry the user's installed Codex CLI version (detected at runtime via `codex --version`), not the skill's own version. The Codex backend gates feature/model access by this — older versions get HTTP 400 "requires a newer version of Codex".

## Body shape (single generation)

The request `model` is the *orchestrator* (`gpt-5.5` by default, `--orchestrator` to change), which invokes the `image_generation` tool — the actual image model, `gpt-image-2`. That's why docs elsewhere say "gpt-image-2" while the wire body never mentions it.

```json
{
  "model": "gpt-5.5",
  "instructions": "Pass-through image generator. ...",
  "input": [{
    "type": "message",
    "role": "user",
    "content": [{"type": "input_text", "text": "<USER_PROMPT>"}]
  }],
  "tools": [{
    "type": "image_generation",
    "size": "<size>",
    "quality": "<quality>",
    "output_format": "<png|jpeg>",
    "background": "opaque"
  }],
  "tool_choice": {
    "type": "allowed_tools",
    "mode": "required",
    "tools": [{"type": "image_generation"}]
  },
  "reasoning": {"effort": "xhigh"},
  "parallel_tool_calls": false,
  "store": false,
  "stream": true
}
```

## Body shape (edit mode)

`input[0].content` includes one or more `input_image` parts BEFORE the text:

```json
{"type": "input_image", "image_url": "data:image/png;base64,..."}
```

The tool gets `"action": "edit"`. Up to 16 references (the documented gpt-image-2 edit limit, confirmed against this backend with a live 6-reference run on 2026-07-21); the combined cap covers `--input` + `--from-last`.

## Rejected fields — never send

| Field | Backend response |
| --- | --- |
| `n` | "Unknown parameter" |
| `previous_response_id` | "Unsupported parameter" |
| `item_reference` | 404 unless `store: true` (and `store: true` itself is untested) |
| `max_tool_calls`, `max_output_tokens` | "Unsupported parameter" |
| `reasoning.effort: "minimal"` / `"none"` | rejected for the `image_gen` tool |
| `output_format: "webp"` | silently ignored — backend returns PNG bytes mislabeled. The user-facing `--format webp` flag therefore requests PNG on the wire and converts locally via Pillow (`postprocess.py`) |
| `background: "transparent"` | rejected on `gpt-image-2` (chroma-key replaces) |

## SSE result extraction — priority order

The image (`base64 PNG`) can arrive via three paths. Consume the FULL stream, then:

1. **Preferred:** `response.output_item.done` event with `item.type == "image_generation_call"` and `item.status == "completed"` → use `item.result`.
2. **Equivalent fallback:** post-stream sweep `response.completed.response.output[*]` for any `image_generation_call` item.
3. **Last-resort fallback:** the latest `response.image_generation_call.partial_image` payload, **only** if neither completed-state path produced bytes.

Never short-circuit on the first match — partial frames arrive first by design.

`response.failed`, HTTP non-2xx, or stream close with no candidate → surface as error.
