# codex-image

A skill that generates and edits images through the user's ChatGPT subscription, over the Codex CLI's OAuth credentials or the route Codex is configured to use, without an API key.

## Language

### Transports

Distinct surfaces reach OpenAI image models. Conflating them is the most common source of confusion in this project, because they have different capabilities and the public documentation describes the public APIs, not the subscription endpoints.

**Codex Images endpoints**:
`<base>/images/generations` and `<base>/images/edits` on the route Codex uses (chatgpt.com/backend-api/codex, a relay, or a proxy), reached with the Codex CLI's OAuth token or the proxy's key. Everything in `scripts/` targets them since 0.3.0. They share the public Images API's shape but choose size, quality and model from the prompt. See [ADR-0002](./docs/adr/0002-use-the-images-api.md).
_Avoid_: "the API", "the backend" (both are ambiguous)

**Codex Responses**:
`<base>/responses` with a chat model forced to call the hosted `image_generation` tool. The transport before 0.3.0; removed.
_Avoid_: describing it as current

**Built-in image_gen**:
Codex CLI's own image tool, reachable only from inside a Codex session. It calls the Codex Images endpoints; this skill sends the same requests from outside Codex.
_Avoid_: "the Codex tool"

**Public Images API**:
OpenAI's public image REST surface at api.openai.com. Requires an API key, which this skill deliberately does not use.
_Avoid_: "the official API"

### Transparency

**Transparency**:
The user's intent: an image whose background is absent rather than painted, so it composites onto anything.
_Avoid_: "cutout" as a synonym for the intent; a cutout is one result of it

**Alpha**:
The per-pixel opacity channel that carries transparency in the saved file. What the user actually receives.
_Avoid_: "the alpha layer"

**Native transparency**:
Alpha produced by the image model itself, requested with `background: "transparent"` plus one prompt sentence. The default path. See [ADR-0001](./docs/adr/0001-request-transparency-in-the-prompt.md) and [ADR-0002](./docs/adr/0002-use-the-images-api.md).
_Avoid_: "true transparency", "real transparency"

**Chroma key**:
The fallback path: generate the subject on a flat solid colour plate, then remove that colour locally to synthesise alpha. Retained for subject classes native transparency is unproven on.
_Avoid_: "green screen", "background removal"

**Background**:
The request parameter controlling output transparency mode, one of `opaque`, `auto`, `transparent`. It is **not** the visual setting of the image.
_Avoid_: using it to mean the scene

**Scene**:
The visual setting described in the prompt: a table, a studio, a landscape. Distinct from the `background` parameter.
_Avoid_: "backdrop" when the `background` parameter is what is meant

### Generation

**Orchestrator**:
The chat model the removed Codex Responses transport named in `model` to call the image tool. The Images endpoints have none; `--orchestrator` is a no-op.
_Avoid_: using it for the image model

**Image model**:
The model that actually renders pixels. The Images endpoints do not report it, and the ChatGPT backend ignores a requested one. The skill sends `--image-model` (or, on a proxy, the newest listed `gpt-image-*`) only so a proxy can route the request.
_Avoid_: asserting a specific image model in prose — read it from the response

**Reference**:
An input image supplied for style, composition, or mood, producing a new image.
_Avoid_: "source image"

**Edit target**:
An input image the user wants modified in place, producing a changed version of it.
_Avoid_: "input" unqualified, which spans both roles

**Sidecar**:
The per-image JSON record written next to a generated file, holding the prompt and the parameters the backend resolved.
_Avoid_: "metadata file"
