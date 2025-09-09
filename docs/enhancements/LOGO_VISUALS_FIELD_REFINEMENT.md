## Cutover: Rename “branding_visuals” → “logo_visuals” (complete migration)

### Problem
- `branding_visuals` stores only logo integration instructions (placement, size, color treatment). Other brand inputs (color palette, brand voice) are already incorporated in other fields (e.g., `color_palette`, `visual_style`).
- The field name is misleading and causes confusion across stages and the UI.

### Goals
- Clarify intent by renaming the field to `logo_visuals` with the same semantics.
- Output `logo_visuals` only when a logo is provided by the user.
- Keep routing to multi‑input image generation when both a reference image and a logo are present; otherwise call the correct single‑input or text‑only path.
- Perform a full cutover (no backward‑compat aliasing). Update all code and tests to the new key.

---

## Backend changes (complete cutover)

### 1) Pydantic model: rename the field (no alias)
- File: `churns/models/__init__.py`
  - In `VisualConceptDetails`, rename `branding_visuals: Optional[str]` → `logo_visuals: Optional[str]` and update its description to explicitly mention “logo integration only.”
  - Remove any aliasing. The old key is no longer accepted.

### 2) Creative Expert stage: update prompts and gating
- File: `churns/stages/creative_expert.py`
  - Replace all occurrences of `branding_visuals` with `logo_visuals` in system prompts, user prompts, JSON structure examples, and final instructions.
  - Gate `logo_visuals` strictly: only include when `ctx.apply_branding` is true AND a logo is present (`ctx.brand_kit.saved_logo_path_in_run_dir` or `logo_file_base64`). Otherwise, instruct to omit it (set to null) and enforce post‑processing to null it if present erroneously.
  - Remove any fallback mapping logic for `branding_visuals` (not used going forward).

### 3) Style Adaptation stages
- Files: `churns/stages/style_adaptation.py`, `churns/stages/style_adaptation_2.py`
  - Replace `branding_visuals` with `logo_visuals` in instructions, example JSON, and any normalization logic (e.g., converting nested objects to strings). Remove legacy handling branches.

### 4) Subject Repair and Utilities
- Files: `churns/stages/subject_repair.py`, `churns/stages/refinement_utils.py`
  - Replace `branding_visuals` with `logo_visuals` in reads, string assembly, and defaults.

### 5) Prompt Assembly stage (refinement required)
- File: `churns/stages/prompt_assembly.py`
  - Replace the inclusion clause in `_assemble_core_description`:
    - Old: include when `apply_branding` and `vc.get('branding_visuals')`.
    - New: include when `apply_branding` AND a logo is present AND `vc.get('logo_visuals')`.
  - Use the same `has_logo` determination already computed in `assemble_final_prompt` (brand kit contains `saved_logo_path_in_run_dir`). Pass `has_logo` as a parameter to `_assemble_core_description` (preferred), or re‑compute inside the function from `user_inputs`.
  - Change the label text appended into the prompt from “Branding Visuals” to “Logo Integration”. Example:
    - `parts.append(f"Logo Integration: {vc.get('logo_visuals')}")`

### 6) Image Generation stage (routing)
- File: `churns/stages/image_generation.py`
  - No logic changes. Current routing already handles (reference+logo), (reference), (logo‑only), and (none) correctly.

---

## Frontend changes (minimal UX refinement)

### 1) Branding lens: gate “Logo Integration” affordance by logo presence
- Under the Branding section (in `PipelineForm` / Creative Canvas):
  - Compute `hasLogo = !!brand_kit?.logo_file_base64`.
  - Show a disabled hint when no logo: "Logo Integration — upload a logo to enable."
  - When a logo is present: "Logo Integration enabled — system will generate logoVisuals (logo placement instructions)."
- No new request fields are required; the backend can derive the state solely from brand kit contents.

Notes:
- Keep `apply_branding` semantics unchanged. Colors and voice continue to flow into `color_palette`, `visual_style`, etc., regardless of logo presence.
- We are only gating the dedicated logo plan field and its downstream use.

---

## Tests (TDD)

Add focused tests to keep scope minimal:

- Creative Expert
  - apply_branding=True, colors/voice but no logo → `logo_visuals` omitted/null.
  - apply_branding=True, logo present → `logo_visuals` contains logo placement guidance.

- Prompt Assembly
  - `logo_visuals` included in final prompt only when apply_branding=True and logo present.
  - Label “Logo Integration:” is used in the assembled prompt.

- Image Generation routing
  - Reference image + logo → multi‑modal path.
  - Reference image only → single‑input edit path.
  - Neither (and no logo) → text‑to‑image path.

- Tests to update (rename keys):
  - `churns/tests/test_style_adaptation_stage_v2.py`
  - `churns/tests/test_brand_presets_e2e.py`

---

## Rollout plan
1) Bulk rename across backend code and tests (`branding_visuals` → `logo_visuals`).
2) Update prompts and JSON structures in Creative Expert and Style Adaptation to emit `logo_visuals` only.
3) Refine `prompt_assembly.py` to gate and label `logo_visuals` as described.
4) Add/adjust tests; run full suite. Verify assembled prompts and image routing logs for scenarios with/without logo.

### Risks and mitigations
- Risk: An LLM might still emit the old key. Mitigation: updated prompts and JSON schema examples use only `logo_visuals`; test coverage will catch violations.
- Risk: Users expect brand palette/voice to appear under “branding visuals.” Mitigation: UI copy clarifies those are integrated elsewhere; “Logo Integration” is logo‑specific.

---

## Acceptance criteria
- All code and tests use `logo_visuals` exclusively (no references to `branding_visuals`).
- `logo_visuals` is present only when a logo exists in the brand kit and branding is enabled.
- Prompt assembly includes “Logo Integration” only under the same gating.
- Image generation routing remains correct for all input combinations.

---

## Alternative (if rollback ever needed)
- Re‑introduce an alias in the Pydantic model or a parser shim mapping `branding_visuals` → `logo_visuals`. Not recommended for the cutover but available if external dependencies require it.

---

## Exact strings (copy/paste where applicable)

### Creative Expert: Language Control (system prompt)
Use this exact bullet:

```
- For `promotional_text_visuals` and `logo_visuals` fields: The description of how the text/logo should look (e.g., 'A bold, sans-serif font placed at the top', 'A subtle watermark in the corner') MUST remain in ENGLISH. Only the actual text content to be displayed in the image (e.g., the headline or brand name) should be written in {language_display}.
```

### Creative Expert: Text & Branding fields (system prompt)
Enabled:

```
- `logo_visuals`: {task_guidance['branding_style']}. If no guidelines are provided, derive the branding style from the marketing strategy and task. The description MUST detail placement, scale, and integration of the brand logo based on the provided Brand Kit context.
```

Disabled:

```
- `logo_visuals`: This field MUST be omitted (set to null) as branding application is disabled.
```

### Creative Expert: JSON structure (manual mode)

```
{
  "visual_concept": {
    "main_subject": "string | null",
    "composition_and_framing": "string",
    "background_environment": "string",
    "foreground_elements": "string | null",
    "lighting_and_mood": "string",
    "color_palette": "string",
    "visual_style": "string",
    "promotional_text_visuals": "string | null",
    "logo_visuals": "string | null",
    "texture_and_details": "string | null",
    "negative_elements": "string | null",
    "creative_reasoning": "string | null",
    "suggested_alt_text": "string"
  },
  "source_strategy_index": "integer | null"
}
```

### Creative Expert: Brand Kit integration (user prompt)

```
The following brand kit MUST be integrated into your visual concept. You must describe logo placement in the `logo_visuals` field.
```

Specific guidance example:

```
Your `logo_visuals` description should be specific and prioritize a watermark-style placement, such as:
- 'Subtly place the logo in the bottom-right corner, scaled to 5% of the image width. It should be rendered as a semi-transparent watermark to avoid distracting from the main subject.'
- 'Position the brand logo as a discreet watermark in the top-left corner, using a color that complements the background.'
Avoid instructions that replace or alter the main subject with the logo unless explicitly requested by the user.
```

No guidelines but branding enabled:

```
- Branding Guidelines: Not provided, but branding application is enabled. Derive branding style from strategy/task and describe visualization in the `logo_visuals` field of the JSON output, following task-specific branding guidance from the system prompt.
```

### Creative Expert: Adherence note (instructor mode)

```
Adhere strictly to the requested Pydantic JSON output format (`ImageGenerationPrompt` containing `VisualConceptDetails`). Note that `main_subject`, `promotional_text_visuals`, and `logo_visuals` are optional and should be omitted (set to null) if the specific scenario instructs it. The `suggested_alt_text` field is mandatory. Ensure all other required descriptions are detailed enough to guide image generation effectively.
```

### Creative Expert: Final instruction (summary list)

Enabled:

```
- `logo_visuals`: Describe the branding logo elements and their integration.
```

Disabled:

```
- `logo_visuals`: This field MUST be omitted (set to null) as branding application is disabled.
```

### Creative Expert: Language Reminder (user prompt)

```
- `promotional_text_visuals` & `logo_visuals`: Describe the visual style (font, color, placement) in ENGLISH. Write the actual text content (e.g., a headline or brand name) in {language_display}.
```

### Style Adaptation: Branding instruction (system prompt)

Enabled:

```
- **Adapt Branding**: `apply_branding` is enabled. You MUST generate a `logo_visuals` field. Your description MUST be a specific instruction for logo placement, prioritizing a watermark-style integration (e.g., 'Subtly place the logo in the bottom-right corner'). Avoid instructions that replace the main subject. If a `brand_kit_override` is provided, adapt to it; otherwise, adapt the original recipe's branding.
```

Disabled:

```
- **Omit Branding**: `apply_branding` is disabled. You MUST OMIT the `logo_visuals` field from your JSON output.
```

Override note:

```
- **New Logo Details:** A new logo is provided. Describe its placement and integration in the `logo_visuals` field. Logo style is: `'{brand_kit_override['logo_analysis'].get('logo_style', 'N/A')}'`.
```

### Prompt Assembly: exact label

```
Logo Integration: {vc.get('logo_visuals')}
```

### Frontend UX copy

```
Logo Integration — upload a logo to enable.
```

```
Logo Integration enabled — system will generate logoVisuals (logo placement instructions).
```


