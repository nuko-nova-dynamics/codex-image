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
    "background": "<opaque|auto>"
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
| `background: "transparent"` | HTTP 400, `"Transparent background is not supported for this model."` — see **Transparency** below. This does **not** mean transparency is unavailable |

## Transparency

Native alpha works on this transport. It is requested through the **prompt**, not the parameter.

Send `background: "auto"` and append a transparency request to the prompt text. The backend resolves `auto` to `transparent` and returns RGBA. Confirm it worked by reading `background` back off the `image_generation_call` item: it comes back as `"transparent"` even though `"auto"` was sent.

Never send `background: "transparent"`. Full reasoning, evidence, and the free re-test recipe are in [ADR-0001](../docs/adr/0001-request-transparency-in-the-prompt.md).

### Why it is refused

The backend pins its own image model and echoes it at `response.tools[0].model`:

```json
{"type": "image_generation", "background": "auto", "model": "gpt-image-2-codex",
 "moderation": "auto", "n": 1, "output_compression": 100,
 "output_format": "png", "quality": "auto", "size": "auto"}
```

OpenAI's 2026-08-20 changelog granted transparent-background support to `gpt-image-2` and `gpt-image-2-2026-04-21`. `gpt-image-2-codex` is not on that list. The public Responses API accepts the parameter; this transport does not, because it routes to a variant that was not in the rollout.

The wire schema already accepts the value — a nonsense background returns `"Supported values are: 'transparent', 'opaque', and 'auto'."` from an earlier validation layer — so only the model-capability gate is closed.

### Re-testing is free

Rejections happen at request validation, before any generation, so they cost no quota. Send `background: "transparent"`; a 400 means the gate is still closed. Verified closed on 2026-08-21 with codex-cli 0.149.0.

### Resolved parameters are advisory

`size` and `quality` are requests, not instructions. Two runs asking for `1024x1024` / `low` returned `1536x1024` / `medium` and `1312x1199` / `medium`. Read `resolved_size` and `resolved_quality` off the response rather than assuming.

## SSE result extraction — priority order

The image (`base64 PNG`) can arrive via three paths. Consume the FULL stream, then:

1. **Preferred:** `response.output_item.done` event with `item.type == "image_generation_call"` carrying a `result` → use it. **Do not require `item.status == "completed"`.** This backend emits the finished image while still reporting `status: "generating"`.
2. **Equivalent fallback:** post-stream sweep `response.completed.response.output[*]` for any `image_generation_call` item. **This array is frequently empty** on completed streams, so it cannot be relied on.
3. **Last-resort fallback:** the latest `response.image_generation_call.partial_image` payload, **only** if neither path above produced bytes.

Never short-circuit on the first match — partial frames arrive first by design.

Gating step 1 on `status == "completed"` was a real bug (fixed 2026-08-21): with an empty `response.completed.output`, every successful generation silently demoted to the partial frame. Both observed cases happened to be byte-identical, but a stale partial would have saved the wrong image. `tests/fixtures/sse_generating_status.txt` reproduces the shape.

`response.failed`, HTTP non-2xx, or stream close with no candidate → surface as error.
