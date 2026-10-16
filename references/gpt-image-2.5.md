# GPT Image 2.5 compatibility

Checked 2026-09-08. This skill uses Codex Responses with subscription OAuth, not an API key.

## Model requests

[Sunburst](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst) targets precise editing; [Flare](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare) targets faster everyday generation.
Both document `low`, `medium`, `high`, `xhigh`, `max`, and `auto` quality.
The [launch announcement](https://openai.com/index/introducing-chatgpt-images-2-5/) announces rollout to Codex and ChatGPT; it does not establish which model an individual subscription request receives.

```bash
# Experimental request; check the warning and sidecar after completion
bash "<skill-dir>/scripts/generate.sh" "a blue circle on white" \
  --image-model gpt-image-2.5-flare --quality low --verbose
```

Omit `--image-model` to preserve endpoint selection.
Use Sunburst's ID for editing requests; use Flare's ID when speed matters.
An explicit request can still resolve to another model.
Do not repeatedly generate to try to force a model rollout.

## Live Codex Responses checks

Two isolated probes used the existing `gpt-5.5` orchestrator with low reasoning effort and an opaque background.
They saved valid PNGs without changing the last-image pointer.

| Requested model | Requested quality | Reported model | Reported quality |
| --- | --- | --- | --- |
| `gpt-image-2.5-flare` | `low` | `gpt-image-2-codex` | `low` |
| `gpt-image-2.5-sunburst` | `xhigh` | `gpt-image-2-codex` | `low` |

Both reported `1254x1254` despite a `1024x1024` request.
These checks establish that model requests were not confirmed as honored on this account and route.
They do not identify the weights behind the returned model name or prove behavior across all accounts.
`max` is exposed as a request but was not live-tested.

A repeat check confirmed installed Codex CLI `0.153.4` matched npm's latest stable release.
Both variants were requested again at `low` quality; `response.created`, `response.in_progress`, and `response.completed` all reported `gpt-image-2-codex`.
The completed image items reported `low` quality and `1254x1254`.
The retry retained response events with image payloads omitted for inspection.
No newer stable CLI was available to test.

Sidecar `requested_image_model` and `quality` preserve the request; `image_model` and `resolved_quality` preserve response values, or null when absent.
The script warns on a different or missing model ID, including a dated ID that differs from the requested alias.

## Public API boundary

The [generation guide](https://developers.openai.com/api/docs/guides/image-generation) supports explicit `tools[].model` on the public Responses API; its top-level model remains a mainline orchestrator.
The [vision guide](https://developers.openai.com/api/docs/guides/images-vision?api-mode=responses) distinguishes image analysis from generation and editing.
Neither documents the private Codex Responses contract.

The public generation guide supports transparent PNG/WebP and dimensions divisible by 16, an edge limit of 3840, an aspect ratio no wider than 3:1 or taller than 1:3, and 655,360–8,294,400 pixels.
These public limits do not establish that Codex Responses will honor the requested dimensions.
The skill retains its existing size validation and 16-reference cap.

Keep the prompt-based `--transparent` mechanism from [ADR-0001](../docs/adr/0001-request-transparency-in-the-prompt.md); these probes did not retest transparency.
Do not switch to API-key billing to obtain a requested model without user authorization.

## Further diagnosis: orchestrator and standalone endpoint

Additional live checks on 2026-09-08 used the same blue-circle prompt and preserved outputs under separate names.

| Route | Requested image model | Observation |
| --- | --- | --- |
| Codex Responses with `gpt-6-astra` | Flare | Response confirmed Astra as orchestrator; image model remained `gpt-image-2-codex` |
| Codex Responses with `gpt-6-astra` | Sunburst | Image model remained `gpt-image-2-codex` |
| Built-in `imagegen` | No model argument available | Generated PNG; C2PA software agent `gpt-image`, version `2.0` |
| Codex standalone `images/generations` | Flare and Sunburst, separate requests | Both succeeded; JSON omitted model identity; both PNGs carried C2PA `gpt-image` version `2.0` |

The standalone route is `https://chatgpt.com/backend-api/codex/images/generations`, using subscription OAuth.
It is distinct from the public API-key Images API and the skill's Responses route.
The diagnostic requests followed OpenAI's [Images client](https://github.com/openai/codex/blob/main/codex-rs/codex-api/src/endpoint/images.rs) and [ChatGPT provider configuration](https://github.com/openai/codex/blob/main/codex-rs/model-provider-info/src/lib.rs).
It is not added as a supported skill transport because these checks did not verify 2.5 selection.

OpenAI's current [built-in tool source](https://github.com/openai/codex/blob/main/codex-rs/ext/image-generation/src/tool.rs) sets `IMAGE_MODEL` to `gpt-image-2` and exposes no model selector.
This is inspected upstream source, not an inspection of the installed app binary.
The [built-in documentation](https://learn.chatgpt.com/docs/image-generation) also still names `gpt-image-2`, despite the rollout announcement.
Changing the prompt cannot change that request field through the exposed tool interface.

### Inspect embedded provenance correctly

Pillow's empty `info` and EXIF dictionaries do not establish that a PNG lacks provenance.
The earlier skill-generated PNGs also contained C2PA data in a `caBX` chunk, as confirmed with ExifTool.
For diagnostic inspection when ExifTool is available:

```bash
exiftool -s -ActionsSoftwareAgentName -ActionsSoftwareAgentVersion image.png
```

The checked old and new images all reported `gpt-image` and `2.0`.
These are embedded software-agent fields, not a response model ID or independent verification of the deployed weights.
ExifTool reads the assertions; this check did not validate their cryptographic signatures.
Use response identity, provenance, and routing documentation together; none of these checks confirmed 2.5.

The offline suite passed all 157 tests, including tool-model placement, request/response identity separation, mismatch warnings, and final-response metadata precedence.
Python and shell lint also passed.

## Official announcement asset comparison

Downloaded 12 example assets linked from OpenAI's Images 2.5 announcement, using the original CDN asset URLs without resizing or format-conversion query parameters.
The announcement's [80s-headshot.png](https://images.ctfassets.net/kftzwdyauwt9/1oUEzmNEwhlktfQMqWLwTO/cde41dc57991caa0d6b22b35b2d8c70c/80s-headshot.png) contains `ActionsSoftwareAgentName: gpt-image`, `ActionsSoftwareAgentVersion: 2.0`, and `Claim_Generator_InfoName: OpenAI Media Service API`.
These exactly match the kitten supplied by the user and the tested Codex outputs.
The other 11 downloaded examples exposed no software-agent/model-version field through ExifTool.
Absent metadata is not evidence of a particular model version.

This comparison undermines using the `2.0` provenance tag to rule out Images 2.5: OpenAI itself publishes an example carrying that tag in the 2.5 announcement.
It does not prove which model generated each announcement asset or our test images.
Likewise, the legacy `gpt-image-2-codex` response identifier establishes the reported alias, not the weights behind that alias.
The correct result is that explicit 2.5 identity remains unverified, not that these images are conclusively from an older model.
