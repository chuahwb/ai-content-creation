### Aspect Ratio Resolver Implementation Plan

#### Scope
- Implement a centralized, provider-aware aspect ratio resolution utility used by both `prompt_assembly.py` and `image_generation.py`.
- Remove duplicate aspect ratio prompt injection from `image_generation.py` and keep it only in `prompt_assembly.py`.
- Ensure mappings align with capabilities of `gpt-image-1` and `gemini-2.5-flash-image-preview` with a deterministic nearest-match policy.
- Deliver unit, stage, and integration tests (TDD) and minimal logging for observability.

#### Non-goals
- No changes to the front-end platform selector list or UX at this time.
- No change to platform definitions in `SOCIAL_MEDIA_PLATFORMS` aside from reading the existing aspect ratio string.

### Deliverables
- New module: `churns/core/aspect_ratio_utils.py` with `AspectResolution` and `resolveAspectRatio`.
- Refactors to `churns/stages/prompt_assembly.py` and `churns/stages/image_generation.py` to use the resolver and remove duplicate prompt edits.
- Tests:
  - Unit tests for resolver
  - Stage tests asserting prompt assembly text and API payload sizes
  - Integration tests covering OpenAI and Gemini flows
- Documentation references updated (already added analysis doc under `docs/analysis/`).

### Architecture and APIs
- File: `churns/core/aspect_ratio_utils.py`
  - Data structures:
    ```python
    from dataclasses import dataclass
    from typing import Optional

    @dataclass
    class AspectResolution:
        promptAspect: str                 # e.g., "2:3", "3:2", "9:16", etc.
        openaiSize: Optional[str] = None  # e.g., "1024x1536"; None when not applicable
        sourcePlatformAspect: str = ""
        provider: str = ""
        modelId: Optional[str] = None
        fallbackReason: Optional[str] = None
    ```
  - Public function:
    ```python
    def resolveAspectRatio(platformAspect: str, provider: str, modelId: Optional[str] = None) -> AspectResolution:
        """
        - Parses input aspect string (e.g., "1:1", "9:16", "1.91:1").
        - Looks up provider/model capabilities.
        - Picks best supported prompt aspect and payload size (if OpenAI).
        - Returns `AspectResolution` with optional `fallbackReason` when nearest-match chosen.
        """
    ```
  - Internal helpers:
    - `parseAspectStringToFloat(aspectStr: str) -> float` (supports decimals like `1.91:1`)
    - `nearestAspect(target: float, candidates: list[str]) -> tuple[str, float]` (returns best candidate and delta)
    - Capability tables:
      - OpenAI `gpt-image-1`:
        - Prompt aspects: `["1:1", "2:3", "3:2"]`
        - Payload sizes: `{ "1:1": "1024x1024", "2:3": "1024x1536", "3:2": "1536x1024" }`
      - Gemini `gemini-2.5-flash-image-preview`:
        - Prompt aspects: `["1:1", "9:16", "16:9", "3:4", "4:3"]`
        - No payload size (use prompt only)
    - Policy: If platform aspect not available, pick nearest by absolute delta of width/height ratio. Ties break by preference order: `1:1`, `9:16`, `16:9`, `3:4`, `4:3`, `2:3`, `3:2`.

### Detailed Implementation Steps
1) Create Aspect Ratio Resolver (TDD)
   - Add file `churns/core/aspect_ratio_utils.py` with the `AspectResolution` dataclass skeleton and empty `resolveAspectRatio`.
   - Add unit test file `churns/tests/test_aspect_ratio_utils.py` with failing tests covering mapping matrix:
     - OpenAI:
       - `1:1` → prompt `1:1`, size `1024x1024`
       - `9:16` → prompt `2:3`, size `1024x1536`
       - `2:3` → prompt `2:3`, size `1024x1536`
       - `3:4` → prompt `2:3`, size `1024x1536`
       - `1.91:1` → prompt `3:2`, size `1536x1024`
     - Gemini:
       - `1:1` → prompt `1:1`, size None
       - `9:16` → prompt `9:16`, size None
       - `2:3` → prompt `3:4`, size None
       - `3:4` → prompt `3:4`, size None
       - `1.91:1` → prompt `16:9`, size None
     - Edge cases:
       - Unknown string → default to `1:1` with `fallbackReason`
       - Malformed input (e.g., `abc`) → default to `1:1` with `fallbackReason` (do not raise hard error in pipeline)
   - Implement resolver until tests pass.

2) Integrate into Prompt Assembly
   - File: `churns/stages/prompt_assembly.py`
   - Import resolver and constants:
     - `from ..core.aspect_ratio_utils import resolveAspectRatio`
     - `from ..core.constants import IMAGE_GENERATION_PROVIDER, get_image_generation_model_id`
   - Replace current `map_to_supported_aspect_ratio_for_prompt` usage:
     - Build `provider = IMAGE_GENERATION_PROVIDER or "OpenAI"`
     - `model_id = get_image_generation_model_id()`
     - `res = resolveAspectRatio(platform_aspect_ratio, provider, model_id)`
     - Use `res.promptAspect` in the prompt instruction string.
   - Keep a minimal wrapper for backward compatibility (optional):
     - `map_to_supported_aspect_ratio_for_prompt()` becomes a thin proxy to the resolver and is marked for deprecation.
   - Ensure no provider-conditional branching remains in prompt assembly besides resolver usage.

3) Integrate into Image Generation
   - File: `churns/stages/image_generation.py`
   - Import resolver and constants:
     - `from ..core.aspect_ratio_utils import resolveAspectRatio`
     - `from ..core.constants import IMAGE_GENERATION_PROVIDER, get_image_generation_model_id`
   - Remove duplicate prompt mutation:
     - Delete `_add_aspect_ratio_to_prompt` function.
     - Remove its invocation in `_gemini_generate_with_*` functions. Use the prompt as-assembled.
   - Replace payload size mapping:
     - In `_generate_with_no_input_image`, `_generate_with_single_input_edit`, `_generate_with_multiple_inputs`:
       - Resolve: `res = resolveAspectRatio(platform_aspect_ratio, provider, model_id)`
       - For OpenAI only, set `image_api_size = res.openaiSize` and send as the `size` parameter.
       - For Gemini, do not send `size` or append aspect text here.
   - Logging:
     - If `res.fallbackReason` present, log a single line warning via `ctx.log`.

4) Clean-up and Backward Compatibility
   - Keep the old functions as wrappers (optional) for one release cycle to ease code comprehension, with clear deprecation comments.
   - Update docstrings to reference the resolver as the single source of truth.

### Testing Strategy (TDD)
- Unit tests (new): `churns/tests/test_aspect_ratio_utils.py`
  - Cover mapping matrix for both providers and edge/default cases.
- Stage tests (update or add):
  - Prompt assembly tests: verify single AR clause is present and matches resolver output for given `IMAGE_GENERATION_PROVIDER` and platform AR.
  - Image generation tests:
    - OpenAI: assert `size` param equals expected; verify prompt is not mutated.
    - Gemini: assert no `size` param is added; prompt remains as assembled.
- Integration tests (update existing):
  - End-to-end pipeline for each provider confirming images are produced and the chosen AR/size is logged or reflected in metadata. Do not rely on pixel inspection for Gemini.

### Migration and Rollout
1. Land resolver and unit tests first (failing → passing).
2. Refactor `prompt_assembly.py` to use resolver (fix tests).
3. Refactor `image_generation.py` to use resolver and remove duplicate prompt injection (fix tests).
4. Run full suite and QA a few manual runs per provider/platform.
5. Optional: in next release, remove deprecated wrappers and references.

### Observability
- Log `fallbackReason` in both stages the first time a mapping occurs per run (throttled at stage-level) to avoid noisy logs.
- Include the `sourcePlatformAspect`, `provider`, `modelId`, and chosen `promptAspect`/`openaiSize` in debug logs for diagnosing issues.

### Risks and Mitigations
- Slight prompt change for Gemini where `2:3` maps to `3:4`. Mitigation: document in logs/tests and validate visually during QA.
- If OpenAI expands aspect sizes, table must be updated. Mitigation: centralized capability tables ease maintenance.
- If future providers need pixel-exact sizes but differ in API semantics, extend `AspectResolution` with provider-specific fields.

### Acceptance Criteria
- A single resolver determines both prompt aspect text and OpenAI size payload.
- No aspect ratio text is appended in `image_generation.py`.
- All tests pass: resolver unit tests, prompt assembly stage tests, image generation stage tests, and relevant integration tests.
- Logs show clear mapping and fallback messages when applicable.


