### Prompt Assembly vs Gemini 2.5 Flash Image Preview — Evaluation and Recommendations

#### TL;DR
- **Keep a shared core prompt assembly**, but add a small **provider-aware wrapper** (prefix/suffix + tone) so prompts align with Gemini’s narrative-first guidance while remaining effective for OpenAI.
- **Switch core description to a single, fluent paragraph** (not label-style fragments). Preserve negative directives. Include text-rendering and branding directives only when applicable.
- **Avoid duplicate aspect ratio instructions for Gemini**: rely on the Gemini-side aspect ratio injection already handled downstream.

### Current design (what we have now)
- Scenario-based prefixes are chosen, then a structured concept is joined via labeled fragments, then an aspect ratio suffix is added.
- Example of suffix currently added:
```139:144:churns/stages/prompt_assembly.py
supported_aspect_ratio_for_prompt = map_to_supported_aspect_ratio_for_prompt(platform_aspect_ratio)

suffix = f" IMPORTANT: Ensure the image strictly adheres to a {supported_aspect_ratio_for_prompt} aspect ratio."

final_prompt_str = f"{prefix}{core_description}{suffix}"
```
- Prefix selection is scenario-driven (reference, logo, instruction):
```121:129:churns/stages/prompt_assembly.py
prefix = _get_prompt_prefix(
    is_style_adaptation=is_style_adaptation_run,
    has_reference=has_reference,
    has_logo=has_logo,
    has_instruction=has_instruction,
    instruction_text=instruction_text
)
```
- Gemini’s aspect ratio directive is also appended later in the generation stage, creating duplication:
```893:905:churns/stages/image_generation.py
def _add_aspect_ratio_to_prompt(prompt: str, aspect_ratio: str) -> str:
    """Add aspect ratio directive to prompt for Gemini (since it doesn't have size parameter)."""
    aspect_directive_map = {
        "1:1": "The image should be in a 1:1 aspect ratio (square).",
        "9:16": "The image should be in a 9:16 aspect ratio (vertical).",
        "16:9": "The image should be in a 16:9 aspect ratio (horizontal).",
        "2:3": "The image should be in a 2:3 aspect ratio (vertical).",
        "3:4": "The image should be in a 3:4 aspect ratio (vertical).",
        "1.91:1": "The image should be in a 1.91:1 aspect ratio (horizontal)."
    }
```

### What the Gemini guide optimizes for
- **Narrative scene description** over keyword or label fragments.
- **Templates per intent**: photorealism (camera/lighting/mood), stylized/sticker, accurate text rendering, product mockups, minimalist negative space, storyboard.
- **Editing prompts**: precise change requests with explicit preservation (style, geometry, identity) and natural blending.
- **Aspect ratio stated in natural language** inside the prompt.

### Gaps and risks in the current assembly
- The core is a series of labeled fragments (e.g., “Composition and Framing: …; Background: …”), which reads less naturally for Gemini.
- The suffix adds a capitalized imperative (“IMPORTANT: Ensure…”); Gemini prefers natural sentences.
- Aspect ratio is injected in two places (assembly suffix and Gemini stage), causing redundancy for Gemini.
- Style adaptation prefix is commented out; we lose a strong editing-specific directive.
- When `render_text` is enabled, we don’t explicitly instruct “render exactly the following text,” which is recommended for Gemini.

### Recommendation: Provider-aware assembly with a shared narrative core
Keep one shared content core across providers, but add a thin provider-aware layer for prefix/suffix and tone.

1) Make the assembly provider-aware
- Add a `provider` argument to `assemble_final_prompt(...)`, or source it inside from `constants.IMAGE_GENERATION_PROVIDER`.
- Route to provider-specific prefix/suffix builders while sharing the same core narrative description.

2) Replace label-style fragments with a narrative paragraph
- Convert:
  - “Composition and Framing: … Background: … Lighting & Mood: … Visual Style: …”
- Into a single paragraph:
  - “The composition features [composition_and_framing]. The background shows [background_environment], with [foreground_elements] in front when present. Lighting is [lighting_and_mood], creating [mood if present]. The color palette uses [color_palette] and the visual style is [visual_style]. [Textures and details] …”

3) Scenario-specific prefixes (shared intent, tailored tone)
- Full generation (no reference/logo):
  - OpenAI: “Create an image based on the following detailed visual concept.”
  - Gemini: “Create an image that closely follows this detailed scene description.”
- Default edit (reference, no instruction):
  - OpenAI: “Edit the provided image. Preserve the main subject exactly… Modify only the surrounding context…”
  - Gemini: “Using the provided image, keep the subject’s identity and geometry unchanged. Update the surrounding scene to match the description below.”
- Instructed edit (reference + instruction):
  - OpenAI: “Based on the provided reference image, modify it according to the user instruction ‘…’ to achieve the following visual concept.”
  - Gemini: “Using the provided image, apply the following change: ‘…’. Keep identity, camera geometry, and lighting continuity intact. Follow the scene description below.”
- Complex edit (reference + logo):
  - OpenAI: “Using the provided primary reference image and secondary logo image, create a composition that integrates both elements…”
  - Gemini: “Combine the provided image with the logo so it looks naturally present (correct perspective, lighting, and material interaction). Follow the scene description below.”
- Logo-only:
  - OpenAI: “Integrate the provided logo into the following detailed visual concept.”
  - Gemini: “Use the provided logo as an element in the scene, placed naturally with correct perspective and lighting, following the description below.”
- Style adaptation (re-enable):
  - OpenAI: “Adapt the provided reference image to match the stylistic elements of the description…”
  - Gemini: “Adapt the provided image: keep the composition intact while applying the described style (lighting, color, mood, texture) consistently.”

4) Text rendering and branding directives (conditional)
- If `render_text` is True: add a Gemini-friendly directive like “Render the following text exactly as typed: ‘…’ (clean kerning and consistent baseline).” Keep it for OpenAI too.
- If `apply_branding` is True: add
  - “Use the brand color palette where appropriate and integrate the logo with natural perspective. Do not distort the logo; maintain clear space and legibility.”

5) Aspect ratio handling
- OpenAI: keep the existing suffix (it is harmless and the actual enforcement is via size parameter).
- Gemini: remove the explicit assembly suffix and rely solely on `_add_aspect_ratio_to_prompt(...)` added in the generation stage to avoid duplication.

### Proposed implementation sketch (minimal invasive)
- Add `provider` awareness and restructure the narrative description. Use existing fields; do not add new ones.

```python
# In prompt_assembly.py

def assemble_final_prompt(structured_prompt_data: Dict[str, Any], user_inputs: Dict[str, Any], platform_aspect_ratio: str, provider: Optional[str] = None) -> str:
    provider = (provider or IMAGE_GENERATION_PROVIDER or "OpenAI").lower()

    # Build scenario-aware prefix with provider tone
    prefix = _get_provider_aware_prefix(provider, has_reference, has_logo, has_instruction, instruction_text, is_style_adaptation_run)

    # Build narrative description (single paragraph)
    core_description = _assemble_narrative_description(vc, user_inputs, include_main_subject)

    # Provider-aware suffix
    suffix = _build_suffix_for_provider(provider, platform_aspect_ratio)

    return f"{prefix}{core_description}{suffix}"
```

Key helpers:
- `_assemble_narrative_description(...)`: converts the current labeled fragments into fluent sentences; keep negatives (“Avoid …”) as a final clause.
- `_get_provider_aware_prefix(...)`: switches tone/wording per provider for each scenario (above).
- `_build_suffix_for_provider(...)`:
  - OpenAI: keep current aspect ratio sentence.
  - Gemini: return empty string to avoid duplication with `_add_aspect_ratio_to_prompt`.

### Sample outputs (same input, different provider)
- Scenario: Instructed edit with text rendering and branding enabled.

OpenAI
```
Based on the provided reference image, modify it according to the user instruction "Add the logo on the t‑shirt chest" to achieve the following detailed visual concept: Keep the subject’s identity and pose unchanged. The composition features a casual mid-shot. The background shows a neutral studio wall; the foreground includes a folded denim jacket on a table. Lighting is soft and front‑biased, creating a relaxed mood. The color palette uses charcoal, off‑white, and brand blue, and the visual style is clean commercial photography with subtle texture on fabric. Render the following text exactly as typed if present. Use the brand color palette where appropriate and integrate the logo with natural perspective; do not distort the logo, and maintain clear space and legibility. IMPORTANT: Ensure the image strictly adheres to a 1:1 aspect ratio.
```

Gemini
```
Using the provided image, apply the following change: "Add the logo on the t‑shirt chest". Keep identity, camera geometry, and lighting continuity intact. The composition features a casual mid‑shot. The background shows a neutral studio wall; the foreground includes a folded denim jacket on a table. Lighting is soft and front‑biased, creating a relaxed mood. The color palette uses charcoal, off‑white, and brand blue, and the visual style is clean commercial photography with subtle fabric texture. Render the following text exactly as typed if present. Use the brand palette; integrate the logo with correct perspective; do not distort it and keep clear space.
```
(Gemini’s aspect ratio is appended downstream by `_add_aspect_ratio_to_prompt`.)

### Should prompts be separated by provider?
- **Yes, minimally**: keep a shared narrative core but add a small provider-aware layer for prefix/suffix/tone. This avoids duplicate logic while aligning with each model’s strengths.

### Test coverage to add (unit-level)
- Prompt assembly returns expected phrasing for:
  - Full generation, default edit, instructed edit, complex edit, logo-only, style adaptation.
  - Both providers: OpenAI keeps the AR suffix; Gemini omits it.
  - When `render_text=True`, prompt contains an “render exactly the following text” directive.
  - When `apply_branding=True`, prompt contains logo integration and color palette guidance.
- Assert no duplicated AR directive when provider is Gemini.

### Rollout plan
- Step 1: Implement provider-aware prefix/suffix with narrative core; keep existing mapping helpers.
- Step 2: Add/adjust unit tests in `churns/tests/test_prompt_assembly_stage.py` (and related) per the coverage above.
- Step 3: Verify end-to-end with Gemini provider enabled and ensure no prompt duplication.


