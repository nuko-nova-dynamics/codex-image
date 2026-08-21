# codex-image

A skill that generates and edits images through the user's ChatGPT subscription, over the Codex CLI's OAuth credentials, without an API key.

## Language

### Transports

Three distinct surfaces reach OpenAI image models. Conflating them is the single most common source of confusion in this project, because they have different capabilities and the public documentation describes only the third.

**Codex Responses**:
The endpoint this skill talks to, reached with the Codex CLI's OAuth token. Everything in `scripts/` targets it.
_Avoid_: "the API", "the backend" (both are ambiguous across the three)

**Built-in image_gen**:
Codex CLI's own image tool, reachable only from inside a Codex session. Not reachable from this skill.
_Avoid_: "the Codex tool"

**Images API**:
OpenAI's public REST surface. Requires an API key, which this skill deliberately does not use.
_Avoid_: "the official API"

### Transparency

**Transparency**:
The user's intent: an image whose background is absent rather than painted, so it composites onto anything.
_Avoid_: "cutout" as a synonym for the intent; a cutout is one result of it

**Alpha**:
The per-pixel opacity channel that carries transparency in the saved file. What the user actually receives.
_Avoid_: "the alpha layer"

**Native transparency**:
Alpha produced by the image model itself, requested via the prompt with `background: "auto"`. The default path. See [ADR-0001](./docs/adr/0001-request-transparency-in-the-prompt.md).
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
The mainline model named in the request `model` field. It calls the image tool; it does not draw.
_Avoid_: "the model" unqualified

**Image model**:
The model that actually renders pixels. The backend selects it and echoes its identity on the response; this skill cannot choose it.
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
