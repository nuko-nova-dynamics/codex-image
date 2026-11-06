---
status: accepted
date: 2026-11-06
supersedes: 0001 (transport and the `background` value; the prompt sentence is kept)
---

# Generate through the Images API on the Codex route, as Codex does

The skill now posts to `<base>/images/generations` and `<base>/images/edits` on whatever route Codex's config selects. It no longer posts to `<base>/responses` with a chat model forced to call the hosted `image_generation` tool.

## Context

- Codex stopped using the hosted tool on 2026-07-09 (openai/codex #31596, commit `a7c72aee8b`). Its `image_gen.imagegen` function tool calls the Images endpoints directly with `{prompt, model, background, quality: "auto", size: "auto"}`, and `images` on edits.
- Between 2026-11-03 and 2026-11-05, ChatGPT began forwarding the Responses request's `reasoning.effort` to the hosted image model as `complexity`. Every value failed: `Complexity '<effort>' is not supported for this image model`. Omitting `reasoning` still worked when sent directly to ChatGPT.
- CLIProxyAPI v8.0.58 (2026-11-06) rejects forced hosted `image_generation` on GPT-6 models with a request-scoped 400, so the old transport failed on every machine that routes Codex through that proxy. Reported as router-for-me/CLIProxyAPI#7309.
- The Images endpoints worked on all three routes on 2026-11-06: ChatGPT directly, the local relay, and the proxy.

## Decision

Use the Images endpoints for all generation and edits. Remove the Responses transport, the orchestrator choice, and the SSE parser. Keep `--orchestrator` and `--effort` as no-op flags that warn, so existing invocations still run.

## Consequences

- The ChatGPT backend chooses size, quality and image model from the prompt. `size`, `quality`, `model`, `n`, `output_format` and `output_compression` are accepted and not applied (see `references/api-recipe.md`). The skill still sends what the user asked for, warns when the response differs, and records the resolved values in the sidecar. An aspect ratio is best requested in the prompt.
- The response is always PNG. JPEG and WebP are converted locally and need Pillow.
- The response does not name the image model, so the sidecar's `image_model` is now always null.
- A proxy route needs a `gpt-image-*` model name to send the request to its Images path; the skill takes the newest one the proxy lists, or `--image-model`.

## Transparency (amends ADR-0001)

`background: "transparent"` is accepted on the Images endpoints, unlike on the hosted tool. It is not enough on its own: for "a ceramic coffee mug" the parameter alone returned alpha between 12 and 252 everywhere, with no fully transparent pixel. With ADR-0001's prompt sentence appended, about half the pixels were fully transparent and the subject opaque, with the parameter set to either `transparent` or `auto`. The skill sends `background: "transparent"` plus the sentence. Keep the sentence.
