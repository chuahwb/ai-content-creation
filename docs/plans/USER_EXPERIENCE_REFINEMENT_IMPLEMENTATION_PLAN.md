### Unified Creative Canvas Implementation Plan

This plan operationalizes the User Experience Refinement and Mode Unification proposal into concrete, incremental changes across the frontend (Next.js/MUI), backend (FastAPI), and pipeline (executor/context/normalization). It preserves all current functionality while re-framing the homepage into a single, progressive workflow with optional “Lenses” and an inspirational template gallery.

---

### 1) Goals and Non-Goals

- **Goals**
  - **Remove explicit mode selection** in the UI and replace it with a unified, progressive Creative Canvas that starts simple and discloses advanced controls on demand.
  - **Retain all legacy capabilities**: target platform, creativity, variants, saving/loading presets, brand kit, text overlays, marketing inputs, image upload, template saving, and live WebSocket updates.
  - **Introduce `unifiedBrief` end-to-end**: collect on the frontend, transmit via API, normalize into pipeline context before stage execution.
  - **Make the interface compact, professional, and engaging** using existing MUI + framer-motion patterns.

- **Non-Goals**
  - No change to the backend database schema unless strictly necessary.
  - No change to existing pipeline stages contract; we adapt inputs via normalization rather than refactoring stages.

---

### 2) Current State Inventory (as-implemented)

- **Frontend homepage** (`front_end/src/app/page.tsx`)
  - Hosts three tabs: New Run (`PipelineForm`), Results (`RunResults`), History (`RunHistory`). Navigation to Results triggers WebSocket connection. Navigation happens immediately on submit, avoiding socket init disruption.

- **User input form** (`front_end/src/components/PipelineForm.tsx`)
  - React Hook Form with Zod schema. Tracks `mode`, `platform_name`, `creativity_level`, `num_variants`, optional `prompt`, `task_type`, `task_description`, `marketing_*`, language, `render_text`, `apply_branding`, `brand_kit`, image upload and preview.
  - Provides brand kit preset management, color palette editing, logo upload & analysis display, template saving, style recipe modal.
  - New components already exist and are wired: `CreativeBriefInput`, `EditModeSelector`, `TextOverlayComposer`, plus state `unifiedBrief` (intentType, generalBrief, editInstruction, textOverlay). The form submission sends `unifiedBrief` to the backend.

- **Frontend API** (`front_end/src/lib/api.ts`)
  - Submits `multipart/form-data` to POST `/api/v1/runs`. Appends form fields and optional image; sanitizes brand kit; appends `unified_brief` JSON part when present.
  - WebSocket client handles run progress updates under `/api/v1/ws/{run_id}`.

- **Backend API** (`churns/api/routers.py` → `create_pipeline_run`)
  - Accepts Form fields (including `unified_brief` JSON). Validates mode/platform/task_type/language. Attaches parsed brand kit and parsed `unifiedBrief`. Creates DB record. Starts background pipeline task via `task_processor.start_pipeline_run(run_id, request, image_data, executor)`.

- **Background execution** (`churns/api/background_tasks.py`)
  - Builds pipeline context and, if `request.unifiedBrief` is set, calls `normalize_unified_brief_into_context(request.unifiedBrief, context)`. This is the bridge to unify prompt/imageInstruction/taskDescription.

- **Schemas/Types**
  - Pydantic schemas include `UnifiedBrief` on the request model; TS types include `UnifiedBrief` and `PipelineFormData.unifiedBrief`.

Implication: The plumbing is wired end-to-end; focus shifts to UI unification, validation hardening, and visual polish.

---

### 3) Target UX and Information Architecture

- **Creative Canvas (single entry point)**
  - Primary inputs centered:
    - A large `CreativeBriefInput` with helpful placeholder.
    - An optional image drop zone with preview and remove actions.
  - Inline edit control for uploaded image: `EditModeSelector` appears only if an image is present; toggles between default and instructed edit; writes into `unifiedBrief` accordingly.

- **Inspirational Templates (replacing Task-Specific Mode)**
  - Visual gallery of 8 templates using curated image thumbnails representing task types (not programmatic previews).
  - Clicking a template sets `task_type` (for backend compatibility) and subtly highlights selected tile. User may still type a brief or upload an image.

- **Lenses (progressive disclosure of advanced options)**
  - **Brand Lens**: toggles `apply_branding` and reveals brand kit tools (colors/voice/logo, presets, palette editor).
  - **Text Lens**: toggles `render_text` and reveals `TextOverlayComposer` (writes into `unifiedBrief.textOverlay.raw`, language remains global).
  - **Marketing Lens**: reveals `marketing_*` fields in a compact grid.

- **Global controls**
  - Platform and language remain visible and compact.
  - Generation settings (creativity and variants) remain visible in a single row.
  - Presets surface as “Load Preset/Save Template,” same behavior and modals.

- **Actions**
  - Primary CTA: Generate.
  - Secondary: Save as Template; Reset.
  - On submit: navigate first, then WebSocket connects in results. Session storage flag used for resetting upon return remains.

---

### 4) Data Model and Back-Compat Strategy

- **Remove mode from the client; deprecate the API input**
  - Do not render or submit `mode` from the frontend.
  - Backend treats `mode` as optional and either:
    - Computes a value server-side for analytics-only (e.g., template picked → task_specific, marketing fields present → custom, else easy), or
    - Ignores it entirely in favor of actual inputs (preferred long term).
  - Update backend validation to be content-driven (require brief or image), not mode-driven. Require `task_type` only when a template tile is selected.

- **Single source of truth for content**
  - `unifiedBrief.generalBrief` replaces free-form prompt field in the UI. We still populate legacy `prompt` when submitting to ensure existing servers/tests pass.
  - When an image is uploaded and the user selects `instructedEdit`, copy `unifiedBrief.editInstruction` into legacy `image_instruction` as well.

- **Language control**
  - Keep a single global `language` for text on images and captions. Remove `textOverlay.language` from unifiedBrief. Continue to send the legacy top-level `language` field to the backend.

---

### 5) API and Backend Changes

- **Unified brief acceptance (already implemented)**
  - Backend accepts `unified_brief` JSON in multipart form, parses into `UnifiedBrief`, and passes to the executor. Ensure robust 400 handling for malformed JSON and optionally gate via a feature flag.

- **Frontend request (already implemented)**
  - Client appends `unified_brief` JSON when present. Maintain mirroring to legacy fields for back-compat: map `generalBrief` → `prompt`, and `editInstruction` → `image_instruction` when applicable (UI prepares this mapping). Do not submit `mode`.

- **Deprecate `mode` in the API**
  - Make `mode` optional in the request handling; stop using it for validation. Optionally compute and store a derived value for analytics only.

- **Prune redundant unifiedBrief fields**
  - Remove `textOverlay.language` and `styleHints` from the unifiedBrief schema and TS types. Normalizer ignores these fields if sent by older clients. Top-level `language` remains authoritative.

---

### 6) Frontend Implementation Plan (modular)

- **A. Introduce feature flag**
  - `NEXT_PUBLIC_UNIFIED_CANVAS=1` (default on in dev) to show the new IA. Provide fallback to existing layout if disabled. This enables safe rollout and quick rollback.

- **B. Component structure**
  - New directory: `front_end/src/components/creativeCanvas/`
    - `CreativeCanvas.tsx` (wrapper that composes existing and new components)
    - `TemplateGallery.tsx` (visual grid; uses curated image thumbnails per task type)
    - `LensBrand.tsx` (wraps current Brand Kit block)
    - `LensText.tsx` (wraps `TextOverlayComposer`)
    - `LensMarketing.tsx` (wraps the marketing grid)
    - `CanvasHeader.tsx` (title + optional microcopy)
  - Refactor `PipelineForm.tsx` minimally to:
    - Remove the Mode select in UI and omit `mode` from submission.
    - Move current left/right layout under the new `CreativeCanvas` structure gated by the flag.
    - Bind `CreativeBriefInput`, `EditModeSelector`, and `TextOverlayComposer` to `unifiedBrief` state (already present) and keep legacy fields synchronized for now.

- **C. Template gallery behavior**
  - Selecting a tile sets `task_type` and visually marks the selection. Use curated static images (local assets) with alt text for accessibility.
  - Remove styleHints usage; no longer part of unifiedBrief.

- **D. Lenses behavior**
  - Brand Lens toggles `apply_branding`; reveal current brand kit UI in a card (unchanged functionality).
  - Text Lens toggles `render_text`; show `TextOverlayComposer` (already wired to `unifiedBrief`).
  - Marketing Lens reveals `marketing_*` fields.
  - All lenses are collapsed by default to keep the canvas compact.

- **E. Save/Load Presets**
  - Preserve current preset modals and flows. Ensure saving templates persists the same `input_snapshot` format; we keep legacy shape for compatibility and migration simplicity.

- **F. Submit flow**
  - On submit, set `prompt` = `unifiedBrief.generalBrief` (if any). If image uploaded and `instructedEdit`, set `image_instruction` = `unifiedBrief.editInstruction`.
  - Send `unified_brief` JSON in the same request for the executor normalization path.
  - Do not submit `mode`. Navigate to Results first (unchanged), relying on session storage to reset the form upon return.

---

### 7) Pipeline and Normalization

- **Normalization remains centralized**
  - Continue using `normalize_unified_brief_into_context(unifiedBrief, context)` to populate legacy fields used by stages (prompt assembly, edits, text rendering, etc.).
  - Ensure the normalizer maps:
    - `generalBrief` → `context.prompt`
    - `editInstruction` → `context.image_instruction`
    - `textOverlay.raw` → text rendering subsystem (already picked up via `render_text` flag and composer value in brief; maintain current path)
  - Remove handling for `textOverlay.language` and `styleHints` in normalization; tolerate their presence from older clients.

---

### 8) Testing Strategy (TDD-first)

- **Frontend (Jest + React Testing Library)**
  - `CreativeCanvas` renders primary inputs and is compact by default.
  - Template selection sets `task_type` and highlights active tile.
  - Lenses toggle visibility; fields bind to form state; brand kit auto-enables applyBranding when kit data present (existing behavior preserved).
  - Submit assembles FormData with `unified_brief`, legacy `prompt`, `image_instruction` mirrors (no `mode`); call path verified with `msw`.
  - Regression: Save Template tooltip gating and behavior unchanged; preset load still applies brand kit migration.

- **Backend (pytest)**
  - New tests for `/api/v1/runs` accepting `unified_brief` (multipart with a JSON part). Validate 400 on bad JSON.
  - Ensure the `PipelineRunRequest` created for the executor includes `unifiedBrief` when provided.
  - End-to-end test: submit with only `unifiedBrief.generalBrief` (no `prompt`, no `mode`) and verify pipeline starts successfully.
  - Validation tests: server rejects when neither brief nor image is present, independent of mode.

- **Executor/Normalizer**
  - Unit tests for `normalize_unified_brief_into_context` mapping cases:
    - Full generation only with brief
    - Image default edit
    - Image instructed edit (with instruction)
    - Text overlay provided with `render_text=true`

- **Results/WebSocket**
  - Regression test: navigate-first submission still yields live stage updates; no disconnections.

---

### 9) Performance, Accessibility, and Visual Polish

- **Performance**
  - Lazy-load the Template Gallery preview assets and any non-critical lens UIs.
  - Keep drag-and-drop bounded by existing 10MB limit; maintain preview revoke lifecycle.

- **Accessibility**
  - Proper labels and helper texts for Lenses toggles and controls.
  - Keyboard focus order: brief → upload → platform → generation settings → lenses → actions.

- **Visual polish**
  - Keep current MUI card/typography system and framer-motion transitions. Use consistent spacing (8/16/24 px rhythm). Retain the professional tone and compact layout by default.

---

### 10) Incremental Rollout and Flags

- Add `NEXT_PUBLIC_UNIFIED_CANVAS` (frontend). Default: enabled in dev.
- Add `ENABLE_UNIFIED_BRIEF` (backend) to gate parsing/validation and pass-through to executor. When disabled, ignore the incoming field for immediate rollback.
- Provide a toggle in `.env` and `sample.env` with documentation.

---

### 11) Step-by-step Technical Implementation

- **Step 1: Types and Schemas (non-breaking, compile-time first)**
  - Frontend `front_end/src/types/api.ts`
    - Update `export interface TextOverlay` to remove `language`.
    - Update `export interface UnifiedBrief` to remove `styleHints`.
    - Ensure all references compile; update any consumers to rely only on `raw`.
  - Frontend `PipelineFormData` type remains unchanged except `unifiedBrief` shape now reflects removals.
  - Backend `churns/api/schemas.py`
    - Remove `styleHints` from `UnifiedBrief` and `language` from `TextOverlay`.
    - Add model config to ignore extra fields from older clients (Pydantic v1: `class Config: extra = 'ignore'`; v2: `model_config = ConfigDict(extra='ignore')`).

- **Step 2: Zod schema and form defaults**
  - `front_end/src/components/PipelineForm.tsx`
    - Zod: remove `unifiedBrief.textOverlay.language` and `styleHints` from `formSchema`.
    - Defaults: remove `textOverlay.language` and any `styleHints` default from `originalDefaultValues` and `setUnifiedBrief` reset path.
    - Remove `mode` from schema, default values, and all `watch('mode')` usages. Replace `requiresTaskType` and `showAdvancedFields` logic with:
      - `requiresTaskType` → true when a template tile is selected in `TemplateGallery`.
      - `showAdvancedFields` → derived from lens toggles (e.g., `apply_branding` or `render_text`) or simply show the lenses block collapsed by default.

- **Step 3: UI changes (Creative Canvas)**
  - Remove Mode select dropdown from `PipelineForm.tsx`.
  - Introduce `creativeCanvas` structure (flagged by `NEXT_PUBLIC_UNIFIED_CANVAS`).
  - Implement `TemplateGallery.tsx` using curated static images under `front_end/src/assets/task_types/<slug>.jpg|png`. Provide `alt` text and selection state. Export selected `task_type` back to parent via controlled prop.
  - Keep Brand/Text/Marketing lenses as collapsible sections; no logic change to brand kit internals.

- **Step 4: Submission mapping (back-compat)**
  - On submit, set legacy `prompt` = `unifiedBrief.generalBrief` if present.
  - If image is uploaded and edit mode is instructed, set legacy `image_instruction` = `unifiedBrief.editInstruction`.
  - Append `unified_brief` JSON to FormData; do not append `mode`.

- **Step 5: Backend validation and mode deprecation**
  - `churns/api/routers.py:create_pipeline_run`
    - Change `mode: Optional[str] = Form(None)` and stop validation based on mode.
    - Enforce content-driven checks: require brief (legacy prompt or unified) or `image_file`.
    - Require `task_type` only if a template was selected (frontend sets it; server treats as optional otherwise).
    - Compute `derived_mode` for analytics only (easy/custom/task_specific) without affecting validation; store into `run.mode` to avoid DB changes.

- **Step 6: Normalizer hardening**
  - `normalize_unified_brief_into_context` should ignore unknown fields; do not expect `textOverlay.language` or `styleHints`.
  - Maintain existing mapping to context fields.

- **Step 7: Tests (additions/updates)**
  - Frontend
    - `CreativeCanvas` render tests; `TemplateGallery` selection state and `task_type` propagation.
    - FormData composition tests with `msw`: verify `unified_brief` present; `mode` absent; legacy mirrors populated as expected.
  - Backend
    - Multipart `unified_brief` parsing success and malformed JSON 400.
    - Content-driven validation (no prompt+no image → 400).
    - No-mode submission accepted; `run.mode` populated by derived logic.
  - Normalizer
    - Unit tests to verify mappings; ensure ignoring of removed fields.

- **Step 8: Rollout & flags**
  - Gate UI under `NEXT_PUBLIC_UNIFIED_CANVAS`. Default on for dev.
  - Keep `ENABLE_UNIFIED_BRIEF` backend flag if desired; when off, ignore incoming `unified_brief` and rely on legacy fields.

- **Step 9: Assets and performance**
  - Place curated task type thumbnails under `front_end/src/assets/task_types/` with optimized sizes (webp where possible), import statically for Next.js image optimization.
  - Lazy-load TemplateGallery and lenses heavy subtrees.

- **Step 10: Accessibility & polish**
  - Ensure focus management for collapsible lenses; add ARIA attributes.
  - Provide clear helper texts for each lens toggle.

---

### 12) Risk/Compatibility Assessment and Mitigations

- **Risk**: Legacy tests/consumers rely on `prompt`/`image_instruction` fields.
  - **Mitigation**: Mirror from `unifiedBrief` on submit (frontend) and normalize on backend; keep both paths working.

- **Risk**: Template save/load flows break.
  - **Mitigation**: Preserve `input_snapshot` format and existing migration logic for brand colors and kit data. No changes to preset endpoints.

- **Risk**: Regression on WebSocket progress due to UI reorder.
  - **Mitigation**: Keep navigate-first pattern and sessionStorage guard (unchanged).

- **Risk**: Some clients still submit `mode`, or validators rely on it.
  - **Mitigation**: Treat `mode` as optional/ignored in validation; if present, accept but do not depend on it.

---

### 13) Alternatives Considered

- **A) Hard replacement of `PipelineForm`**
  - Pros: cleaner code, no dual-mode logic.
  - Cons: larger one-shot change, harder rollback.
  - Decision: not preferred initially; we’ll gate via a flag and refactor iteratively.

- **B) Keep explicit Mode selector and only reorganize advanced fields**
  - Pros: minimal backend changes.
  - Cons: does not meet UX objective of unified, progressive experience.
  - Decision: not preferred; flag allows rapid iteration if needed.

---

### 14) Acceptance Criteria

- Users can create runs from the Creative Canvas without selecting a mode upfront.
- Templates are browsable visually and set `task_type` with one click.
- Brand/Text/Marketing Lenses are opt-in disclosures and preserve existing behavior.
- Submissions include `unified_brief` (no `mode`) and still satisfy backend validations.
- All current tests pass; new tests for unified brief and UI are added and passing.

---

### 15) Milestones (suggested)

- M1: Backend accepts `unified_brief` and executor normalization verified (tests).
- M2: Frontend API sends `unified_brief`; submit mirrors legacy fields (tests).
- M3: Creative Canvas flagged on; Template Gallery and Lenses integrated (tests).
- M4: Visual polish, a11y audit, documentation, and rollout toggle in `sample.env`.


