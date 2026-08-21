---
status: accepted
date: 2026-08-21
---

# Request transparency in the prompt, with `background: "auto"`

The image model behind the Codex OAuth transport can return a genuine alpha channel, but it refuses to be *told* to via the `background` request parameter. So we send `background: "auto"` and ask for transparency in the prompt text instead; the backend reads the prompt, resolves `auto` to `transparent`, and returns RGBA.

**Do not "fix" this by sending `background: "transparent"`.** It will look like the obvious correction, because OpenAI's public documentation says to do exactly that. It returns HTTP 400 and no image.

## Why the parameter is refused

The backend pins its own image model variant and echoes it on the response at `response.tools[0].model`:

```json
{"type": "image_generation", "background": "auto", "model": "gpt-image-2-codex",
 "moderation": "auto", "n": 1, "output_compression": 100,
 "output_format": "png", "quality": "auto", "size": "auto"}
```

The 2026-08-20 OpenAI changelog entry granting transparent-background support names `gpt-image-2` and `gpt-image-2-2026-04-21`. **`gpt-image-2-codex` is not among them.** This is not a lagging deployment; it is a model variant that was not in the rollout.

## Evidence

Sending `background: "transparent"` returns, at request validation and therefore free of charge:

```json
{"error": {"message": "Transparent background is not supported for this model.",
           "type": "image_generation_user_error", "param": "tools",
           "code": "invalid_value"}}
```

Sending a nonsense value returns a *different* error one layer earlier, which is how we know the wire schema already accepts `transparent`:

```json
{"error": {"message": "Invalid value: 'bogus'. Supported values are: 'transparent', 'opaque', and 'auto'.",
           "type": "invalid_request_error", "param": "tools[0].background",
           "code": "invalid_value"}}
```

Two live runs on 2026-08-21 sent `auto` and received `"background": "transparent"` back on the `image_generation_call` item, with genuine alpha confirmed three ways: transparent corners, a see-through handle aperture on a mug (which a painted backdrop cannot produce), and a thin sub-1% semi-transparent edge band characteristic of a real matte rather than a drawn checkerboard.

## Considered options

- **Send `background: "transparent"`.** Rejected: HTTP 400 on this transport.
- **Select a transparency-capable image model.** Rejected: `tools[0].model` is schema-present but not user-selectable here. `gpt-image-1.5`, `gpt-image-1`, and `gpt-image-1-mini` all returned the identical transparency error, and the public docs state the Responses API image tool "uses its own GPT Image model selection".
- **Route transparency to the public Images API with an API key.** Rejected: a second transport with its own auth, request shape, error taxonomy, and *billing model*, built for one feature that already works on the transport we have. The skill's entire premise is that no API key is needed.
- **Keep the chroma-key workaround as the default.** Rejected: it requires an optional dependency, hijacks the user's prompt with creative constraints they did not ask for, and produces a synthesised matte rather than the model's own alpha.

## Consequences

- The prompt is load-bearing. The appended sentence is the mechanism, not decoration; removing it breaks transparency even though the code will still look correct.
- The suffix carries no creative constraints on purpose. Banning shadows or text would silently override the user's own art direction.
- Chroma-key survives behind `--transparent-mode chroma`. Native alpha is verified on opaque glazed ceramic and nothing else; hair, fur, smoke, glass, and translucent bodies are untested.
- Requested `size` and `quality` are advisory on this transport. Two runs asked for `1024x1024` / `low` and received `1536x1024` / `medium` and `1312x1199` / `medium`.

## Re-checking this decision

A rejected request costs nothing, so re-testing is free. Send `background: "transparent"` with any prompt. A 400 means the gate is still closed. Anything else means the parameter has been un-gated and this ADR should be revisited in favour of the explicit, more reliable mechanism.

The untried experiment, also free unless it succeeds: send `model: "gpt-image-2"` together with `background: "transparent"`. If the backend honours the override, a variant that *is* in the rollout would handle it. We never learned whether the model field is honoured, because the transparency check fires before model-value validation.
