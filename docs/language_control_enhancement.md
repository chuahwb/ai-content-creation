# Language Control Enhancement Plan

## Objective
Introduce an explicit `language` setting (default **English**) that flows from the UI to every backend stage so users can reliably choose the language for:
1. Text rendered **inside the generated image** (`promotional_text_visuals`, `branding_visuals`, `suggested_alt_text`).
2. **Captions** produced in the `caption` stage.

This removes ambiguity where platform presets (e.g., Xiaohongshu) implicitly forced Chinese output despite English user inputs.

---

## 1. Front-End Changes
1. **UI Component**
   • Update `front_end/src/components/PipelineForm.tsx` – add a grouped `<RadioGroup>` (mobile-friendly) labelled **"Output Language"** with three options:
      1. **English** *(default)*
      2. **中文 / Chinese*
      3. **Other** (shows a text input for ISO-639-1 code when chosen)

    The radio group should sit directly below the *Task Type* selector so it is visible in **Easy**, **Custom**, and **Task-Specific** modes. Use Flex/Grid so it wraps gracefully on small screens.

2. **Type & API typings**
   • Extend `front_end/src/types/api.ts` → add `language?: string` to `PipelineRequest` interface.
   • Ensure form submit serialises `language`.

3. **Form Validation**
   • Default to `'en'` (English locale code) when not specified.

---

## 2. API & Persistence Layer
1. **FastAPI Schemas** (`churns/api/schemas.py`)
   • Add `language: Optional[str] = Field('en', description='ISO-639-1 code of desired output language')` to the inbound request model.

2. **Routers / Endpoints** (`churns/api/routers.py`)
   • Accept the field, pass it into `PipelineContext` instantiation.

3. **Database / Metadata Storage**
   • If you persist `pipeline_metadata.json` or SQL rows, add a `language` column / key.
   • Set default `'en'` for historical rows.

---

## 3. Core Pipeline Adjustments
1. **PipelineContext** (`churns/pipeline/context.py`)
   • Add `language: str = 'en'` attribute.
   • When building the context in the executor, populate from API payload.

2. **Executor** (`churns/pipeline/executor.py`)
   • Ensure each stage receives the context containing `language`.

---

## 4. Stage-Specific Updates
### 4.1 Creative Expert (`churns/stages/creative_expert.py`)
• **System Prompt Injection**: Insert a sentence after persona block:
  `"All textual fields (including any promotional text) MUST be written in {ctx.language.upper()} unless otherwise specified."`
• **User Prompt**: In `_get_creative_expert_user_prompt` add explicit note e.g.:
  `"Write all text (including alt-text) in {{language_name}}."`
• **Post-processing Guard**: If `ctx.language != 'en'`, skip hard-coded English fallbacks.
• **Explicit Field Instruction**
  1. The following Pydantic fields **must** be in `ctx.language`: `promotional_text_visuals`, `branding_visuals`, `suggested_alt_text`.
  2. **Every other `visual_concept` field** (`composition_and_framing`, `background_environment`, `foreground_elements`, etc.) **remains in English** to ensure optimal downstream LLM parsing.

  Accordingly:
  ```python
  lang_note = (
      f"Write the following JSON fields in {ctx.language.upper()}: "
      "promotional_text_visuals, branding_visuals, suggested_alt_text. "
      "Keep every other VisualConceptDetails field in ENGLISH."
  )
  ```
  • Append `lang_note` right after the Text & Branding guidance in both **system** and **user** prompts.
  • **Reference Prompt Snippets (good practice)**
    Insert **after** the Text & Branding guidance block:
    ```python
    # --- Language Control (insert right here) ---
    lang_note = (
        f"\n**Language Control (IMPORTANT):** "
        f"Write the following JSON fields **only** in {ctx.language.upper()}: "
        "`promotional_text_visuals`, `branding_visuals`, `suggested_alt_text`. "
        "Keep all other fields (e.g., composition_and_framing, background_environment) in ENGLISH to optimise LLM comprehension.\n"
    )
    prompt_parts_ce.append(lang_note)
    ```
    • **User Prompt Addition** – append just before the final instruction paragraph:
    ```python
    user_prompt_parts.append(
        f"\n**Language Reminder:** When filling `promotional_text_visuals`, `branding_visuals`, and `suggested_alt_text`, use {ctx.language.upper()}. All other descriptions stay in English.\n"
    )
    ```

### 4.2 Caption Stage (`churns/stages/caption.py`)
• Replace the current hard-coded English instruction block:
  `"This content should be generated primarily in English …"`
  with template referencing `ctx.language`.
• Pass `ctx.language` through `_get_analyst_system_prompt` & `_get_writer_system_prompt` (parameterise or f-string).
• **Language Scope Rules for `CaptionBrief`**
  | CaptionBrief field          | Language Behaviour                         |
  |-----------------------------|--------------------------------------------|
  | core_message                | Follows `ctx.language`                     |
  | primary_call_to_action      | Follows `ctx.language`                     |
  | hashtags                    | Follows `ctx.language` *(if alphabet changes)* |
  | emoji_suggestions           | Language-agnostic
  | key_themes_to_include       | **English** (kept for writer clarity)      |
  | seo_keywords                | Follows `ctx.language`                     |
  | target_emotion              | English                                    |
  | platform_optimizations.*    | English                                    |
  | task_type_notes             | English                                    |

  • Modify Analyst system prompt to: "Generate the language-controlled fields (see table) in {ctx.language.upper()}…".
  • Update **Analyst user prompt**: Replace the hard-coded English advisory (`**Important:** This content should be generated primarily in English…`) with the same dynamic language note reflecting `ctx.language`.
  • Update **Writer system prompt**: Change the `**Language Adherence:**` sentence to use `{ctx.language.upper()}` so it mirrors the selected language rather than defaulting to English.
  • Writer system prompt already inherits language via the brief.
  • **Analyst System Prompt** – edit the bullet:
    ```text
    - **Language Consistency:** Generate the *language-controlled* fields listed below in {ctx.language.upper()}. Preserve authentic terms (e.g., "Japandi") but do not switch languages elsewhere.
    ```
  • **Analyst User Prompt** – replace English-only advisory with:
    ```python
    prompt_parts.append(
        f"**Important (Language Control):** The fields `core_message`, `primary_call_to_action`, `hashtags`, and `seo_keywords` should be written in {ctx.language.upper()}. Other guidance fields remain in English."
    )
    ```
  • **Writer System Prompt** – change Language Adherence line to:
    ```text
    - **Language Adherence:** Write the final caption in {ctx.language.upper()}, keeping cultural/brand terms as-is. Only use a different language if explicitly present in those terms.
    ```

> Best-practice tip: Always precede critical instructions with an **all-caps heading** (e.g., `**Language Control (IMPORTANT):**`) to maximise adherence by the model, and place them *near the end* of the prompt so they are within the model's most recent context window.

### 4.3 Other Stages
If any stage references fixed language (e.g., alt-text generation, style guide), wrap it behind `ctx.language`.

---

## 5. Validation & Tests (TDD)
1. **Unit Tests** (`churns/tests/`)
   • Add tests for context propagation: ensure `language` injected equals the value posted.
   • Mock LLM calls – assert prompts contain the chosen language.

2. **Integration Test**
   • Post a pipeline request with `language='zh'` and platform `Instagram` – assert caption and promotional_text are Chinese.
   • Post with `language='en'` + `Xiaohongshu` – assert English output.

---

## 6. Backward Compatibility
• Default remains `'en'`; existing front-end versions won't break.
• For legacy records missing the field, executor should fall back to `'en'`.

---

## 7. Roll-out Checklist
- [ ] Update front-end form & deploy.
- [ ] Update API schema & version docs.
- [ ] Apply database migration (add column with default `'en'`).
- [ ] Update pipeline code & prompts.
- [ ] Write/extend unit + integration tests.
- [ ] Bump minor version; communicate change in README & release notes.

---

## 8. Future Extensions
• Allow **multi-lingual** outputs (e.g., bilingual captions).
• Add **auto-detect** mode where language inferred from user content.
• Expose i18n files for UI labels to support a translated web UI. 