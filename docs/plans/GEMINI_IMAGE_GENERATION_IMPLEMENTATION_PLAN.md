### Gemini Image Generation Integration Plan

#### Goals
- **Add Gemini as an alternative image generation backend** while preserving existing behavior with OpenAI `gpt-image-1` as default.
- **Allow backend runtime/config switching** between OpenAI and Gemini without changing calling code from other stages.
- **Reuse existing infrastructure**: client injection, constants-based configuration, output saving and token tracking.
- **Maintain reliability**: identical output persistence format and logging; no breaking changes to `stages/image_generation.py` public behavior.

#### Non-Goals
- Replace OpenAI. OpenAI remains default and fully supported.
- Frontend changes; selection is driven by backend config and (optionally) request-level overrides.

---

### Current Implementation Snapshot

- **Stage**: `churns/stages/image_generation.py`
  - Uses globals injected by the executor: `image_gen_client` (OpenAI client) and `IMAGE_GENERATION_MODEL_ID` (default `gpt-image-1`).
  - Supports three paths: text-to-image, single-image edit, and multi-image (reference + logo) edit.
  - Calls OpenAI Images API via `client.images.generate` and `client.images.edit` and then `_process_image_response` which expects an OpenAI-style response (`response.data[0].b64_json` or `url`).
  - Token estimation via `get_token_cost_manager()`; uses model id for cost/tokens, plus PIL to estimate image input tokens.
  - Parallelization via `asyncio.gather`, output files saved to the run directory with consistent naming.

- **Client Injection**: `churns/pipeline/executor.py`
  - Injects `image_gen_client` into stages.
  - Injects model ids/providers for many stages; image generation currently injects only `IMAGE_GENERATION_MODEL_ID` (no provider var).

- **Client Configuration**: `churns/core/client_config.py`
  - Configures many clients. For image generation, currently constructs an OpenAI client only and stores it as `image_gen_client`.
  - Gemini API key is supported for LLMs via an OpenAI-compatible endpoint, but no Gemini image client is configured.

- **Token/Cost Manager**: `churns/core/token_cost_manager.py`
  - Supports OpenAI/OpenRouter/Google providers and image token estimation, but hardcodes provider resolution for `IMAGE_GENERATION_MODEL_ID` to OpenAI.

---

### Design Overview (Provider-Agnostic Adapter + Config Switch)

- **Provider switch**: Introduce `IMAGE_GENERATION_MODEL_PROVIDER` with default `"OpenAI"`. Add env override support to align with the rest of the system.
- **Clients**: Configure a Gemini image client alongside the existing OpenAI image client. Inject both (or a provider-agnostic wrapper) into the stage.
- **Adapters**: Add thin adapters that translate provider-specific requests/responses to our existing internal contract so `image_generation.py` can preserve its flow and `_process_image_response` semantics.
  - OpenAI adapter: pass-through of current logic (no change).
  - Gemini adapter: uses Google GenAI client, normalizes its response into an OpenAI-like object for `_process_image_response`.
- **Token/cost**: Allow token manager to correctly attribute provider/model for Gemini output and keep current estimation for text and input image tokens. Add pricing entries for Gemini image model(s) if available; otherwise fall back gracefully with notes.

This approach maximizes reuse: the stage’s routing, batching, error handling, naming, saving, and metadata remain intact. Only provider selection and request/response plumbing are added.

### Reusing Existing Tools and Framework (explicit checklist)
- Pipeline injection: reuse `PipelineExecutor` client/model injection pattern.
- Constants-driven config: reuse `core/constants.py` with env overrides in `ClientConfig`.
- Token/cost tracking: reuse `TokenCostManager` for text/input-image tokens and extend for Gemini image output.
- Output handling: reuse `_process_image_response` by normalizing Gemini responses to the OpenAI-like shape.
- Concurrency and logging: reuse `asyncio.gather`, existing `ctx.log` calls, file naming, and run-directory persistence.

---

### API Details and Normalization

- **OpenAI (existing)**
  - Text-to-image: `client.images.generate(model, prompt, size, n, quality)`
  - Image edit: `client.images.edit(model, image=[...], prompt, size, quality, input_fidelity)`
  - Response: OpenAI-like with `response.data[0].b64_json` or `url` → already handled by `_process_image_response`.

- **Gemini (new)**
  - Library: `google-genai` (a.k.a. `google.genai`).
  - Text-to-image: `client.models.generate_content(model, contents=[prompt])`.
  - Image edit (single and multi-image): `client.models.generate_content(model, contents=[prompt, inlineDataImg1, inlineDataImg2, ...])` where `inlineData` contains base64 image and mime.
  - Response form: iterate `response.candidates[0].content.parts`, pick first `inline_data` image part; decode `inline_data.data` (base64) to bytes.
  - Normalization: wrap bytes into an OpenAI-style response shape for reuse of `_process_image_response`:
    ```python
    class _OpenAIStyleImageData:
        def __init__(self, b64):
            self.b64_json = b64
            self.url = None

    class _OpenAIStyleResponse:
        def __init__(self, b64):
            self.data = [_OpenAIStyleImageData(b64)]
    ```
    This lets `_process_image_response` continue to save images and name files identically.

---

### Configuration and Injection Changes

- **constants.py**
  - Add `IMAGE_GENERATION_MODEL_PROVIDER = "OpenAI"` (default).
  - Add default Gemini image model id, e.g. `GEMINI_IMAGE_GENERATION_MODEL_ID = "gemini-2.5-flash-image-preview"`.
  - Extend `MODEL_PRICING` with a Gemini image entry using the following rates: input (text/image) $0.30 per 1M tokens; output image $30.00 per 1M tokens; typical 1024x1024 output ~1290 tokens (~$0.039 per image). See Token/Cost Manager Updates for details.

- **client_config.py**
  - Install dependency: `google-genai` in the API image.
  - Configure a Gemini image client when `GEMINI_API_KEY` is present:
    - `from google import genai as google_genai`
    - `gemini_image_client = google_genai.Client()`
  - Store both in the clients map:
    - `image_gen_client_openai` (existing `OpenAI` client)
    - `image_gen_client_gemini` (new)
  - Keep `image_gen_client` for backward compatibility pointing to OpenAI client.

- **pipeline/executor.py**
  - Inject `IMAGE_GENERATION_MODEL_PROVIDER` into stages (mirrors other stages’ pattern).
  - Inject `image_gen_client_gemini` alongside `image_gen_client`.

---

### Stage Changes (minimal and backward-compatible)

- **Globals in `image_generation.py`**
  - Add `IMAGE_GENERATION_MODEL_PROVIDER = None` (injected).
  - Add `image_gen_client_gemini = None`.

- **Routing**
  - In `generate_image(...)`, choose provider path based on `IMAGE_GENERATION_MODEL_PROVIDER`:
    - OpenAI → current `_generate_with_*` paths (unchanged).
    - Gemini → new `_gemini_generate_with_no_input_image`, `_gemini_generate_with_single_input_edit`, `_gemini_generate_with_multiple_inputs`.
  - The Gemini functions:
    - Build `contents` array with `prompt` and optional inline image(s) read and base64-encoded.
    - Call `await asyncio.to_thread(gemini_client.models.generate_content, model=..., contents=...)` to avoid blocking.
    - Extract first `inline_data` part, base64 string → construct `_OpenAIStyleResponse` → pass to existing `_process_image_response`.

- **Aspect Ratio Handling**
  - OpenAI: keep using `size` parameter from `map_aspect_ratio_to_size_for_api` (existing).
  - Gemini: model doesn’t accept a `size` param in the same way; append an explicit aspect ratio directive to the prompt (e.g., “The image should be in a 1:1 aspect ratio.”). Optionally add a post-resize step if strict sizing is required later; for now keep prompt-only guidance to avoid quality loss.

- **Error Handling**
  - Keep `_handle_image_api_error(...)` for OpenAI exceptions.
  - For Gemini, catch Google client errors and map messages into the same error tuple so callers receive identical shapes.

- **Token Calculation**
  - Continue using `_calculate_comprehensive_tokens(...)` for text + input image token estimates.
  - Pass the chosen model id for the provider (OpenAI or Gemini) into the calculation for accurate attribution.
  - Update token manager provider resolution so Gemini image model ids map to `google` instead of always `openai`.

---

### Token/Cost Manager Updates

- Adjust `_get_provider_for_model` in `token_cost_manager.py` to not hardcode image generation as OpenAI; use:
  - If model id matches `GEMINI_IMAGE_GENERATION_MODEL_ID`, return `google`.
  - If model id matches `gpt-image-1`, return `openai`.
- Add `MODEL_PRICING` for the Gemini image model with official rates and per-image token guidance (below) so costs are computed via the existing manager without bespoke logic.

#### Gemini Image Pricing (to add into `constants.py` MODEL_PRICING)

- **Input tokens (text and image)**: $0.30 per 1,000,000 tokens (USD)
- **Output image tokens**: $30.00 per 1,000,000 tokens (USD)
- **Typical output image**: up to 1024x1024 consumes ~1290 tokens → ≈ $0.039 per image

Recommended entry:
```json
"gemini-2.5-flash-image-preview": {
  "provider": "Google",
  "currency": "USD",
  "input_text_cost_per_mtok": 0.30,
  "input_image_cost_per_mtok": 0.30,
  "output_image_cost_per_mtok": 30.00,
  "token_counts_by_quality": {
    "default": {
      "1024x1024": 1290
    }
  },
  "notes": "Output images up to 1024x1024 consume ~1290 tokens (~$0.039 per image at $30/1M)."
}
```

Estimator rule in token manager (reusing existing framework):
- If provider is Google and model is the configured Gemini image model:
  - Use 1290 tokens for 1024x1024 outputs (from pricing note).
  - If other dimensions are detected/desired, scale tokens linearly by pixel area relative to 1024x1024 using the existing image token estimation hooks.
  - Continue using existing text and input-image token estimation paths and aggregate totals via `TokenCostManager`.

---

### Runtime Switching and Backward Compatibility

- **Default**: `IMAGE_GENERATION_MODEL_PROVIDER = "OpenAI"` and `IMAGE_GENERATION_MODEL_ID = "gpt-image-1"` → zero behavior change.
- **Env overrides**: Allow setting `IMAGE_GENERATION_MODEL_PROVIDER=Gemini` and `IMAGE_GENERATION_MODEL_ID=<gemini-image-model>` (e.g., `gemini-2.5-flash-image-preview`).
- **Optional per-request override**: If desired, extend `PipelineContext` to accept `imageGenerationModelId`/`imageGenerationModelProvider` from API request and let the executor inject these dynamically for that run.

---

### File-Level Changes Summary

- `churns/core/constants.py`
  - Add `IMAGE_GENERATION_MODEL_PROVIDER` and `GEMINI_IMAGE_GENERATION_MODEL_ID`.
  - Extend `MODEL_PRICING` with a Gemini image entry (annotated).

- `churns/core/client_config.py`
  - Add optional `gemini_image_client` using `google-genai`.
  - Expose both `image_gen_client_openai` and `image_gen_client_gemini` in `clients`.
  - Keep `image_gen_client` for backward compatibility (OpenAI client).

- `churns/pipeline/executor.py`
  - Inject `IMAGE_GENERATION_MODEL_PROVIDER`.
  - Inject `image_gen_client_gemini` (optional, may be None when key missing).

- `churns/stages/image_generation.py`
  - Add provider-aware routing with Gemini functions.
  - Normalize Gemini responses to the OpenAI-like shape for `_process_image_response`.
  - Keep all existing file naming, logging, and error surfaces unchanged.

- `churns/core/token_cost_manager.py`
  - Update provider detection for image generation models.
  - Optionally add Gemini pricing.

---

### Test Plan (TDD)

- **Unit tests**
  - Adapters: Given mocked Gemini responses (with `inline_data`) return OpenAI-like normalized objects; verify `_process_image_response` saves PNGs with expected filenames.
  - Aspect ratio: Ensure OpenAI uses `size` mapping; Gemini path appends prompt directive.
  - Error handling: Simulate provider-specific errors and assert standardized error tuples.

- **Integration tests**
  - Stage-level tests with the provider switched via injected constants and mocked clients; ensure identical `ctx.generated_image_results` structure for OpenAI vs Gemini.

- **Smoke/E2E (optional gated)**
  - Behind an env flag and network-allowed CI job to validate one text-to-image and one edit flow for Gemini.

---

### Operational Considerations

- **Dependencies**: Add `google-genai` to the API image. Handle missing key/client gracefully (Gemini disabled when `GEMINI_API_KEY` absent).
- **Concurrency**: Stage continues to use `asyncio.gather`. Gemini calls are wrapped in `to_thread` to avoid blocking.
- **Security**: Use `GEMINI_API_KEY` from env; do not log secrets.
- **Observability**: Preserve current logs; optionally add provider/model to the log prefix.
- **Watermark**: Gemini images include SynthID per guide; document this in user-facing docs if needed.

---

### Risks and Mitigations
- **API differences**: Gemini lacks an explicit `size` parameter. Mitigate with prompt directives and (if necessary) optional post-resize.
- **Multi-image editing availability**: Guide supports multiple images; still implement fallback to single-image edit mirroring current OpenAI fallback logic.
- **Pricing/usage variance**: If official image token billing is not exposed, annotate estimates and keep costs best-effort.

---

### Rollout Plan
- Add constants and client configuration; wire injection in the executor.
- Introduce adapters and provider-aware routing in `image_generation.py` with tests first (mocks).
- Add token/cost manager mapping for Gemini model id; add pricing entry with annotations.
- Land behind config defaults (OpenAI), then enable Gemini in a test environment via env overrides.
- Monitor logs, output parity, and token/cost summaries; then roll to staging/prod.

---

### Alternatives Considered
- **OpenAI-compatible endpoint for Gemini**: Risky for images; official `google-genai` offers first-class image support and better fidelity, so we prefer native SDK + normalization.
- **Single wrapper client**: Could hide provider differences entirely. Chosen approach keeps a thin adapter but still leverages existing stage structure to minimize churn and risk.

---

### Summary
This plan adds Gemini as a first-class, switchable image generation backend using a small adapter layer and config-driven provider selection. It preserves the stage’s current interface, batching, saving, and error/metadata semantics while enabling future scalability (more providers) with minimal, isolated changes.

