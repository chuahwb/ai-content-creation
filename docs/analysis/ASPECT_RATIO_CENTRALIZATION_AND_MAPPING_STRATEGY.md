### Aspect Ratio Centralization and Mapping Strategy

#### Problem statement
- **New model support**: The app now supports two image models with different aspect ratio capabilities:
  - **OpenAI gpt-image-1**: supports sizes `1024x1024`, `1024x1536` (vertical), `1536x1024` (horizontal) via a size payload.
  - **Google gemini-2.5-flash-image-preview**: supports aspect ratios `1:1`, `9:16`, `16:9`, `3:4`, `4:3` controlled by prompt only.
- **Current duplication**: Aspect ratio adherence is injected both in `prompt_assembly.py` (text instruction) and again in `image_generation.py` (Gemini path adds a second prompt directive). These can disagree.
- **Current mapping is legacy**: The prompt-level mapping in `prompt_assembly.py` was tailored for OpenAI only (`1:1`, vertical → `2:3`, horizontal → `3:2`) and does not fit Gemini's richer AR set.

#### Goals
- **Single source of truth** for AR mapping usable by both prompt assembly and API payloads.
- **Provider/model-aware mapping** that chooses the nearest supported AR when the platform AR is not directly supported.
- **Remove duplicate prompt injection**; keep prompt AR instruction centralized in `prompt_assembly.py` only.
- **Scalable** to add new providers/models with their own AR capabilities.

### Proposed design: AspectRatioResolver utility (centralized mapping)
Create a small utility module (e.g., `churns/core/aspect_ratio_utils.py`) that encapsulates:

- **Model capability registry** (extensible):
  - For text/prompt: supported aspect ratio strings per provider/model.
  - For payload: supported size options (if any) per provider/model.
- **Normalization and best-fit selection**:
  - Input: platform AR (string), `provider`, and optional `modelId`.
  - Output: a struct containing the AR to put in the prompt, and the payload fields (e.g., OpenAI `size`) to send.

Recommended API:
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class AspectResolution:
    promptAspect: str                 # e.g., "2:3", "3:2", "9:16", etc.
    openaiSize: Optional[str] = None  # e.g., "1024x1536"; None for providers not using a payload size
    sourcePlatformAspect: str = ""   # original platform AR, for logging/debugging
    provider: str = ""
    modelId: Optional[str] = None
    fallbackReason: Optional[str] = None  # why/when a nearest match was chosen

def resolveAspectRatio(platformAspect: str, provider: str, modelId: Optional[str] = None) -> AspectResolution:
    ...
```

### Canonical capabilities and mappings
We will store canonical capabilities and a deterministic nearest-match policy. All inputs/outputs use the string form `W:H`.

- **Platform ARs currently used in the app** (via `SOCIAL_MEDIA_PLATFORMS`):
  - `1:1`, `9:16`, `1.91:1`, `2:3`, `3:4`.

- **Model capabilities**:
  - OpenAI `gpt-image-1`:
    - Prompt-level canonical AR we will use: `1:1`, `2:3` (vertical), `3:2` (horizontal).
    - Payload sizes: `1024x1024`, `1024x1536` (vertical), `1536x1024` (horizontal).
  - Gemini `gemini-2.5-flash-image-preview`:
    - Prompt-level AR supported by model: `1:1`, `9:16`, `16:9`, `3:4`, `4:3`.
    - Payload: no explicit size; aspect is controlled by prompt only.

#### Nearest-match policy
When a platform AR is not directly supported by a model, pick the closest supported ratio by minimizing absolute difference in aspect value (`width/height`). Ties prefer more popular social destiny ARs: first `1:1`, then `9:16`, `16:9`, `3:4`, `4:3`, then `2:3`, `3:2` if applicable.

#### Concrete mapping behavior (effective outcomes)
- For OpenAI `gpt-image-1`:
  - `1:1` → prompt `1:1`; payload `1024x1024`.
  - `9:16` → prompt `2:3`; payload `1024x1536` (vertical).
  - `2:3` → prompt `2:3`; payload `1024x1536` (vertical).
  - `3:4` → prompt `2:3`; payload `1024x1536` (vertical).  (3:4 ≈ 0.75 → nearest among the two vertical families)
  - `1.91:1` → prompt `3:2`; payload `1536x1024` (horizontal).  (`1.91:1` ≈ `16:9` ≈ 1.78 → nearest horizontal)

- For Gemini `gemini-2.5-flash-image-preview`:
  - `1:1` → prompt `1:1`; no payload.
  - `9:16` → prompt `9:16`; no payload.
  - `2:3` → prompt `3:4`; no payload.  (nearest is `3:4` ≈ 0.75 vs `9:16` ≈ 0.56)
  - `3:4` → prompt `3:4`; no payload.
  - `1.91:1` → prompt `16:9`; no payload.  (nearest cinematic widescreen)

These rules are encoded once in the resolver and consumed by both stages.

### Integration points and refactor steps
1. **Add** `churns/core/aspect_ratio_utils.py` with:
   - `resolveAspectRatio(platformAspect, provider, modelId=None) -> AspectResolution` implementing the policy above.
   - Internal helpers: parse `W:H` strings, compute float ratio, nearest-match search, provider capability tables.
2. **Update** `prompt_assembly.py`:
   - Replace `map_to_supported_aspect_ratio_for_prompt` with a call to `resolveAspectRatio(...).promptAspect`.
   - Keep the single prompt-level adherence instruction, e.g.:
     - "IMPORTANT: Ensure the image strictly adheres to a {promptAspect} aspect ratio."
   - Remove any provider-specific logic from prompt assembly other than calling the resolver.
3. **Update** `image_generation.py`:
   - Replace `map_aspect_ratio_to_size_for_api` with `resolveAspectRatio(...).openaiSize` for OpenAI.
   - **Delete** `_add_aspect_ratio_to_prompt` and any call sites. Do not mutate prompts here.
   - For Gemini, do not add payload size; just use the prompt as-is.
4. **Plumbing**:
   - Pass `provider` (and optionally `modelId`) into both stages (they already read `IMAGE_GENERATION_PROVIDER`/model via constants or injected globals). The resolver can read from constants if needed, but make the function explicit-args driven for testability.

### Why this design
- **Single responsibility**: Prompt assembly assembles prompts; image generation only calls APIs. The resolver is the only place knowing about AR nuances.
- **Extensibility**: Adding a new model involves adding a capability entry and, if needed, a small nearest-match tweak; no stage code changes.
- **Consistency**: Both prompt text and payload size come from the same decision.
- **Observability**: The `AspectResolution` can carry a `fallbackReason` to log when nearest-match mappings occur (useful for support).

### Test plan (TDD)
Create tests before refactor; assert current behavior for OpenAI, then add Gemini cases.

- **Unit tests** (`tests/`):
  - `test_aspect_ratio_resolver_openai()`: assert mapping matrix above for OpenAI.
  - `test_aspect_ratio_resolver_gemini()`: assert mapping matrix above for Gemini.
  - Edge cases: unknown AR defaults to `1:1` with a `fallbackReason`; malformed strings raise a clear error or default with log.

- **Stage tests** (extend existing stage tests):
  - `test_prompt_assembly_aspect_clause_openai`: verify prompt contains `2:3` or `3:2` as expected given platform.
  - `test_prompt_assembly_aspect_clause_gemini`: verify prompt contains Gemini-supported AR (e.g., `3:4` for platform `2:3`).
  - `test_image_generation_payload_openai`: verify OpenAI call uses the correct `size` and does not add/alter prompt.
  - `test_image_generation_payload_gemini`: verify no payload size is sent and no duplicate AR text is appended in the generation stage.

- **Integration tests**:
  - Run a small end-to-end pipeline for both providers to ensure successful image generation/editing and that the output resolution matches expectations (OpenAI likely exact size; Gemini aspect simulated by prompt—validate by metadata only, not strict pixel check).

### Rollout plan
1. Add resolver + unit tests (failing initially).
2. Wire up `prompt_assembly.py` to resolver; update tests to pass.
3. Wire up `image_generation.py` to resolver; remove duplicate prompt injection; update tests to pass.
4. Run full test suite; watch logs for `fallbackReason` occurrences; adjust mappings if needed.

### Notes and edge cases
- The Facebook `1.91:1` platform ratio is mapped to `16:9` for Gemini and `3:2`/`1536x1024` for OpenAI to match each model's capabilities while keeping a sensible horizontal framing.
- For vertical content where platform is `2:3`, Gemini uses `3:4` as the closest supported ratio (0.75 vs 0.666…), prioritizing closeness over the narrower `9:16` (0.5625).
- The resolver is deterministic; document the mapping table in code comments and in tests to avoid confusion.

### Example usage
```python
from churns.core.aspect_ratio_utils import resolveAspectRatio

# Prompt Assembly
res = resolveAspectRatio(platformAspect="2:3", provider="Gemini", modelId="gemini-2.5-flash-image-preview")
prompt += f" IMPORTANT: Ensure the image strictly adheres to a {res.promptAspect} aspect ratio."

# Image Generation (OpenAI)
res = resolveAspectRatio(platformAspect=platform_aspect_ratio, provider="OpenAI", modelId="gpt-image-1")
openai_size = res.openaiSize  # e.g., "1024x1536"
```

### Summary of edits to perform (when implementing)
- Add `core/aspect_ratio_utils.py` with resolver and capabilities tables.
- Replace AR mapping calls in `prompt_assembly.py` and `image_generation.py` with the resolver.
- Remove `_add_aspect_ratio_to_prompt` and any prompt mutations in `image_generation.py`.
- Add unit/stage/integration tests enumerated above.

This approach removes duplication, centralizes logic, adapts to each provider/model, and is easy to extend.


