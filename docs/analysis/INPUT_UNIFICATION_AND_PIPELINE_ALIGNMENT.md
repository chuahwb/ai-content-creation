## Unified Input Strategy and Pipeline Alignment

### Executive summary

- **Problem**: Three prompt-like inputs — `prompt`, `imageInstruction`, and `taskDescription` — cause ambiguity and error-prone usage. Users are unsure where to put what, and downstream stages infer intent inconsistently.
- **Goal**: Provide an intuitive, single-entry experience that captures intent cleanly while preserving the pipeline’s sophistication and guarantees for image quality.
- **Recommendation**: Replace the three inputs with a unified, context-aware “Creative Brief” plus a dedicated, structured “Text Overlay” composer (shown only when relevant). Normalize the unified brief on the backend to maintain compatibility with existing stages, then incrementally modernize stages to read normalized fields. Ship with a migration plan and tests.

---

### Current inputs and downstream usage mapping

- **General Prompt (`prompt`)**: User’s high-level goals (theme, style, subject). Consumed as `ctx.prompt`.
  - Strategy (`churns/stages/strategy.py`): Included as “User's General Prompt” in Stage 2 goal generation context.
  - Style Guide (`churns/stages/style_guide.py`): Passed as `user_prompt_original` to enrich style rationale.
  - Creative Expert (`churns/stages/creative_expert.py`): Passed as `user_prompt_original` to ground the visual concept.

- **Image Instruction (`image_reference.instruction`)**: Specific edit guidance for an uploaded image.
  - Image Eval (`churns/stages/image_eval.py`): Drives analysis scope. If provided, VLM is asked for a full analysis; otherwise a minimal one (only `main_subject`).
  - Style Guide: Incorporated as hard constraints when both instruction and analysis are present.
  - Creative Expert: Determines edit mode behaviors in system prompt; affects inclusion/omission of `main_subject` in output.
  - Prompt Assembly (`churns/stages/prompt_assembly.py`): Determines prefix (default vs instructed edit, complex edit); instruction is injected into the final prompt prefix.

- **Task Description (`task_description`)**: Only relevant in task-specific modes when “Render Text” is enabled; intended to capture the headline/offer text.
  - Strategy: Included as "Task-Specific Content/Description" in both niche ID and goal generation contexts.
  - Creative Expert: Used to drive `promotional_text_visuals`; crucial for Pinterest/XHS guidance and when `render_text` is true.
  - Style Guide and Prompt Assembly: Not directly used (in current code) beyond downstream effects through Creative Expert output.

Key observations:
- `imageInstruction` toggles not just edit behavior but also how much the VLM analyzes. It is a control lever, not merely text.
- `taskDescription` is functionally a “text overlay plan,” yet is a free-text blob, confusing users and brittle for downstream parsing.
- `prompt` is overburdened; users often place edit instructions or text overlays here, creating inconsistent behavior.

---

### UX pain points and design goals

Pain points:
- **Ambiguity**: Three textareas with overlapping semantics lead to misplaced input and inconsistent outputs.
- **Cognitive load**: Users must map their intent to the “right box” instead of describing what they want.
- **Context leakage**: Missing edit instruction changes how earlier stages behave; missing task description cripples text rendering.

Design goals:
- **Intuitive single-entry**: One primary field to describe what to create or edit.
- **Context-aware**: UI adapts when a reference image is attached or when “Render Text” is enabled.
- **Structured where it matters**: Text overlay inputs should be structured (headline, subheadline, CTA) to improve downstream reliability.
- **Backward compatible**: Normalize to existing fields; modernize stages incrementally.

---

### Pipeline coverage audit (beyond the five focus stages)

The following stages exist in `churns/stages/` and are impacted or confirmed as unaffected by input unification:

- `load_base_image.py`: No change. Reads the uploaded reference image; unaffected by input semantics.
- `image_eval.py`: Covered. Instruction presence influences analysis depth; becomes more reliable via normalization.
- `strategy.py`: Covered. Consumes unified brief and optional overlay context as task hints.
- `style_guide.py`: Covered. Reads normalized instruction and brand kit context.
- `creative_expert.py`: Covered. Heavily benefits from unified brief and overlay parsing; drives `promotional_text_visuals`.
- `prompt_refine.py`: Minimal/no change. If enabled, can optionally receive parsed overlay strings to preserve literal text segments during refinement.
- `prompt_assembly.py`: Covered. Prefix selection based on normalized instruction remains stable.
- `image_generation.py`: No direct change. Receives assembled prompts; quality/clarity improves upstream.
- `image_assessment.py`: No change to API; benefits from clearer prompts.
- `style_adaptation.py`: Read-only alignment. If `intentType == styleAdaptation`, the normalized flags allow consistent behavior.
- `subject_repair.py` / `text_repair.py`: No change. May benefit from cleaner inputs; optional later tuning.
- `save_outputs.py`: No change.
- `caption.py`: Optional enhancement. Can include parsed overlay strings to avoid duplicating or contradicting on-image text.

No crucial generation stage is left unaddressed; changes are concentrated where inputs inform semantics.

---

### Recommended approach: Creative Brief + Context-aware sections

1) **Creative Brief (single main textarea)**
- Prompt label: “Describe what you want to create or edit.”
- Inline helper with examples (generation and edit):
  - Generation: “Festive latte promo in cozy, warm tones, cartoon style.”
  - Edit: “Keep the subject; make the background more minimal; use holiday palette.”
- Chips to hint structure (click to insert): `style`, `subject`, `mood`, `palette`, `seasonal`, `platform`.

2) **Edit Mode (only shown when a reference image is attached)**
- Radio: `Default Edit (preserve main subject)`, `Instructed Edit`.
- If `Instructed Edit`, show a concise `Edit Instruction` input (single-line or small textarea). If empty and user typed edit intent in the brief, auto-suggest extraction.

3) **Text Overlay Composer (Simplified, visible when “Render Text” is on or task type requires it)**
- **UI Simplicity:** A single freeform textarea is sufficient, avoiding complex UI elements like structured fields or live previews. The focus shifts from a complex composer to clear user guidance.
- **User Education:** The UI should provide clear instructions via placeholder text and tooltips. The core guidance is:
  - `Use "double quotes" for the exact text you want to appear on the image.`
  - `Text outside of quotes serves as a content and creative brief for the text's style, tone, placement, and subject (e.g., "a bold, festive font at the top for our new carbonara special").`
- **Backend Delegation:** The entire raw string is sent to the backend. This delegates the nuanced task of intent parsing to the downstream LLM-powered stages (like Creative Expert), which can interpret the mix of literal text, content hints, and stylistic guidance more effectively than a rigid parser.

4) **Brand Kit Hints (non-blocking panel)**
- If a Brand Kit is present, show palette swatches, brand voice summary, and detected logo style. No extra typing fields needed.

---

### Unified request schema (frontend and API)

Proposed new payload addition (kept alongside legacy fields during migration). Freeform-first on the frontend; backend supports both freeform and structured for compatibility:

```ts
// front_end/src/types/api.ts
export type UnifiedBrief = {
  intentType: "fullGeneration" | "defaultEdit" | "instructedEdit" | "styleAdaptation" | "logoOnly";
  generalBrief: string; // The single Creative Brief textarea
  editInstruction?: string; // Only for instructed edit
  textOverlay?: {
    raw?: string; // Freeform-only input on FE; quoted strings denote literal on-image text
    language?: "en" | "zh" | "auto";
  };
  styleHints?: string[]; // from chips (optional)
};
```

API (Pydantic) mirror:

```python
# churns/api/schemas.py
class TextOverlay(BaseModel):
    raw: Optional[str] = None
    language: Optional[str] = None  # "en" | "zh" | "auto"
    # Structured fields remain supported for compatibility and tests
    headline: Optional[str] = None
    subheadline: Optional[str] = None
    cta: Optional[str] = None

class UnifiedBrief(BaseModel):
    intentType: Literal[
        "fullGeneration", "defaultEdit", "instructedEdit", "styleAdaptation", "logoOnly"
    ]
    generalBrief: str
    editInstruction: Optional[str] = None
    textOverlay: Optional[TextOverlay] = None
    styleHints: Optional[List[str]] = None
```

Normalization on the backend (compatibility layer):
- If `UnifiedBrief` present:
  - Map `generalBrief` → `ctx.prompt`.
  - If `intentType` is `instructedEdit` and `editInstruction` exists → `ctx.image_reference["instruction"] = editInstruction`.
  - If `textOverlay` and `textOverlay.raw` exist, map it directly to the legacy-compatible context field: `ctx.task_description = textOverlay.raw`.
- If legacy fields present (no `UnifiedBrief`) → maintain current behavior.

---

### Frontend changes (modular, context-aware)

- **Replace three inputs** in `front_end/src/components/PipelineForm.tsx` with:
  - `CreativeBriefInput` (main textarea).
  - `EditModeSelector` shown only when an image is uploaded.
  - `TextOverlayComposer` shown only when `renderText` is on or task requires text.

- **Types and request assembly** in `front_end/src/types/api.ts` and `front_end/src/lib/api.ts`:
  - Add `UnifiedBrief` type.
  - Update submit function to include `unifiedBrief` while still sending legacy fields for a transitional period.
  - The Text Overlay Composer will be a simple freeform textarea with clear placeholder guidance.

- **Guidance and validation**:
  - If an image is present and the user selects Default Edit with no edit text, set `intentType = defaultEdit` (no `editInstruction`).
  - If the user writes explicit edit instructions in the brief, suggest extracting to `editInstruction` via a one-click hint.

---

### Backend normalization and stage alignment

Introduce a small normalizer (e.g., `churns/core/input_normalizer.py`) to convert `UnifiedBrief` into the existing context shape.

1) **Image Eval (`churns/stages/image_eval.py`)**
- Today: decides `user_has_provided_instruction` by checking `image_reference.instruction`.
- Change: After normalization, this field is reliably set from `UnifiedBrief.editInstruction` when `intentType == instructedEdit`.
- Result: No behavioral change; decision logic becomes more dependable.

2) **Strategy (`churns/stages/strategy.py`)**
- Today: uses `ctx.prompt` + `task_description` in both niche ID and goal generation.
- Change: Set `ctx.prompt` from `generalBrief`. Derive `task_description` from parsed overlay (concatenate `headline`, `subheadline`, `cta`) only when at least one quoted string is present; otherwise leave `None`. Provide the full `text_overlay.raw` as supplemental context when generating goals.
- Result: Better alignment; promotional tasks receive explicit, structured text intent.

3) **Style Guide (`churns/stages/style_guide.py`)**
- Today: uses `user_prompt_original`, `image_instruction`, brand kit context.
- Change: No direct modification needed. Ensure `image_instruction` is set via normalization. Optionally pass `text_overlay.raw` to inform copy tone without constraining literal text selection.

4) **Creative Expert (`churns/stages/creative_expert.py`)**
- Today: Uses `user_prompt_original`, `task_description`, `image_instruction`, brand kit, and toggles to drive `promotional_text_visuals` and edit behavior.
- Change:
  - The stage's system and user prompts will be enhanced to guide the LLM in parsing the raw `task_description` (from `textOverlay.raw`).
  - The prompt will instruct the model to treat text inside double quotes as literal content. Text outside quotes will be treated as a **content and creative brief**, guiding style, tone, placement, and **informing the generation of the text itself if not provided literally.**
  - This delegates parsing to the LLM, leveraging its ability to understand nuanced, mixed instructions without needing a rigid, intermediate parsing step.

5) **Prompt Assembly (`churns/stages/prompt_assembly.py`)**
- Today: Reads `has_instruction` and injects the instruction into the prefix.
- Change: None if normalization sets `image_reference.instruction` correctly. Assembly remains stable.

6) **Prompt Refine (`churns/stages/prompt_refine.py`)**
- Ensure literal overlay strings (parsed from quotes) are preserved across refinement. If refinement is active, pass them as protected tokens to avoid paraphrasing.

---

### Backend Parsing Strategy for Text Overlay

- **Delegate to LLM:** Instead of a separate, rigid backend parser, the responsibility of interpreting the text overlay input is delegated to the LLM in the `Creative Expert` stage.
- **Prompt-Driven Parsing:** The `Creative Expert` system prompt will be updated to include clear instructions on how to handle the freeform text:
  - It will be instructed to identify text enclosed in double quotes (`"..."`) as literal strings to be rendered on the image.
  - All other text will be treated as a **content and creative brief**, guiding aspects like font style, color, placement, and overall tone, and **serving as the source material to generate the text if it is not provided literally.**
- **Benefits:** This approach is simpler to implement and more flexible. It leverages the LLM's natural language understanding capabilities to interpret user intent more accurately than a rule-based parser, especially for creative and nuanced instructions.

---

### Tests (TDD) – unit, integration, E2E

1) **Backend unit tests**
- `tests/test_input_normalizer.py` (new):
  - Maps `UnifiedBrief` to `ctx.prompt`, `ctx.image_reference.instruction`, `ctx.task_description` correctly for all `intentType` cases.
  - Update existing stage tests to include normalized inputs:
  - `churns/tests/test_prompt_assembly_stage.py`: ensure instruction appears in prefix for instructed edits.
  - `churns/tests/test_strategy_stage.py`: verify `task_description` is populated correctly from `textOverlay.raw`.
  - `churns/tests/test_creative_expert_stage.py`: verify `promotional_text_visuals` is correctly influenced by raw text containing both quoted (literal) and unquoted (guidance) content.

2) **Backend integration tests**
- `churns/tests/test_full_pipeline_integration.py`: add subtests covering (a) full generation with headline, (b) default edit, (c) instructed edit with overlay.

3) **Frontend tests**
- `front_end/src/components/__tests__/PipelineForm.unifiedBrief.test.tsx`:
  - Renders correct subcomponents based on image presence and `renderText` toggle.
  - Extracts edit instructions from the brief when user opts in.
  - Quote insertion helper wraps selection and preserves existing quotes.
  - Builds `UnifiedBrief` correctly and posts via `api.ts`.
- `front_end/src/components/design_previews/__tests__/previews.test.tsx`: update or add cases if the previews depend on text overlay.

---

### Migration and rollout plan

- **Phase 1 (Dual-mode, default ON)**: Ship `UnifiedBrief` on the frontend, send both new and legacy fields. Backend normalizes new into legacy to drive current stages. All tests must pass for both modes.
- **Phase 2 (Telemetry & soft deprecation)**: Log when legacy-only fields are used; surface soft warnings in UI tooltips.
- **Phase 3 (Default to new only)**: Hide legacy fields. Keep backend fallback for a release window.
- **Phase 4 (Remove legacy path)**: Remove legacy fields and code branches after usage drops below threshold.

Backward compatibility guarantees: No change to assembled prompts or edit behaviors when fields are mapped equivalently.

---

### Alternative solutions considered

- **Option A: Two-field model**
  - Keep `prompt` and add `textOverlay` composer; hide `imageInstruction` as a separate field and rely on brief extraction with a toggle for default/instructed edits.
  - Pros: Fewer changes; acceptable clarity.
  - Cons: Edit instruction remains implicit; risks under-specifying edits.

- **Option B: Retain three fields with assistive parsing**
  - Keep all fields but add auto-extraction from `prompt` into the right boxes; show inline confirmations.
  - Pros: Minimal backend change; gentle for existing users.
  - Cons: Continues cognitive overhead; ambiguity persists.

- **Option C: Wizard flow**
  - Progressive steps: (1) Choose generation vs edit, (2) Describe, (3) Add text overlay, (4) Review.
  - Pros: Very clear; no ambiguity.
  - Cons: Higher friction for power users; slower for quick tasks.

**Recommendation**: Adopt the **Creative Brief + Context-aware sections** (this document), optionally adding a compact wizard as an onboarding overlay for new users.

---

### Implementation checklist (high-level)

- Frontend
  - Add `UnifiedBrief` type and builders.
  - Replace three inputs with `CreativeBriefInput`, `EditModeSelector`, `TextOverlayComposer` (conditional rendering).
  - Update `api.ts` to post `unifiedBrief` plus legacy during Phase 1.

- Backend
  - Add `UnifiedBrief`/`TextOverlay` Pydantic models.
  - Implement `input_normalizer` (map unified → legacy context fields).
  - Ensure stages read normalized fields with no behavior regressions.

- Tests
  - New unit tests for normalizer.
  - Expand stage tests to cover unified inputs.
  - Frontend tests for new components and request assembly.

- Rollout
  - Phase 1 dual-mode; Phase 2 telemetry; Phase 3 default-to-new; Phase 4 remove legacy.

This plan reduces user ambiguity, strengthens intent capture (especially for edits and overlay text), and aligns with current stage logic with minimal, safe backend changes.


