### User Experience Refinement Implementation Evaluation

This report validates the Unified Creative Canvas implementation against the plan and highlights areas for improvement.

---

### Summary Verdict

- **Functional**: Core flows work end-to-end (brief/image input → API submit with unifiedBrief → backend parse/validation → executor normalization → results). Back-compat maintained.
- **UX**: Creative Canvas is visually clean, compact, and intuitive with progressive lenses. Template gallery looks good but should switch from emoji to curated thumbnails for clarity and brand fit.
- **Code Health**: Most plan items are implemented; a few inconsistencies remain (type strictness for mode, legacy UI edge cases, duplicated constants).

---

### What We Validated

- **Frontend → Backend contract**
  - `front_end/src/lib/api.ts`: Appends `unified_brief` JSON (lines ~155-158). Skips `mode` when undefined.
  - `churns/api/routers.py`: Accepts `unified_brief` (Form), validates JSON, and constructs `PipelineRunRequest` with `unifiedBrief`. Derives `mode` server-side when missing.
  - `churns/api/schemas.py`: `UnifiedBrief` no longer includes `styleHints`; `TextOverlay` only has `raw`; unknown fields are ignored.

- **Client mapping & validation**
  - `PipelineForm.tsx`:
    - Zod schema excludes `mode`; `unifiedBrief` optional; `textOverlay.language` removed.
    - Submission maps `unifiedBrief.generalBrief` → legacy `prompt`, and sets `image_instruction` when in instructed edit.
    - Creative Canvas is gated by `NEXT_PUBLIC_UNIFIED_CANVAS` and provides lenses and a template gallery.

- **Pipeline normalization**
  - `background_tasks`: Keeps `normalize_unified_brief_into_context` usage; removed fields are ignored per schema config.

- **Data persistence**
  - `churns/api/database.py`: `unified_brief` JSON column exists.

---

### UX Evaluation

- **Creative Canvas**: Clear hierarchy (brief → optional image → templates → platform/settings → lenses). Motion/spacing are tasteful; controls feel compact and professional.
- **Templates**: Emoji cards are playful but reduce clarity. Curated image thumbnails per task type would better convey visual outcomes and improve scannability.
- **Lenses**: Brand/Text/Marketing are discoverable and collapse nicely. Brand kit tools remain powerful without cluttering the default view.
- **Form Feedback**: Footer alert for missing brief/image is helpful; consider inline helper text near brief input for quicker correction.

---

### Accessibility & Performance

- Accessibility
  - Canvas headers, labels, and helper texts are present. Add ARIA attributes for collapsibles and ensure focus management when opening lenses and dialogs.
  - Provide alt text for template thumbnails (currently emoji only).

- Performance
  - Consider dynamic imports for creativeCanvas subtree and modals to reduce initial bundle.
  - Optimize curated thumbnails (webp, responsive sizes) when introduced.

---

### Backward Compatibility

- Legacy fields are mirrored on submit; backend accepts both legacy and unified.
- Mode is derived on the server when omitted. Legacy UI is still present behind the flag.

---

### Gaps / Inconsistencies Found

1) **Type contract for `mode` (frontend types)**
   - `PipelineFormData.mode` is still required (union) in `front_end/src/types/api.ts`, yet submission sets `mode: undefined` in `PipelineForm.tsx`. This may cause TypeScript errors and confusion.
   - Recommendation: Make `mode?: 'easy_mode' | 'custom_mode' | 'task_specific_mode'` optional, or remove from the type and use a separate legacy type only where needed.

2) **Legacy UI task type visibility logic**
   - In legacy layout, `requiresTaskType` is derived from whether `task_type` is already set, which causes the Task Type selector to only appear after a selection.
   - Recommendation: If legacy path remains, restore the original logic (show selector when in task-specific context or always show it with optional selection) to avoid UX oddities.

3) **Template Gallery visuals**
   - Current gallery uses emoji circles. Plan calls for curated image thumbnails.
   - Recommendation: Replace with static images under `front_end/src/assets/task_types/` and use Next Image for optimization; include descriptive alt text.

4) **Duplicated platform lists**
   - Platforms are declared in both `PipelineForm.tsx` and `CreativeCanvas.tsx`.
   - Recommendation: DRY by centralizing platform options (e.g., `front_end/src/lib/constants.ts`) or fetch from `/config/platforms` and cache.

5) **Dynamic import opportunities**
   - `creativeCanvas` components and heavy dialogs are statically imported.
   - Recommendation: Next dynamic imports for `CreativeCanvas`, `PresetManagementModal`, `BrandKitPresetModal`, `StyleRecipeModal`, and color modal where feasible.

6) **Docs/env flag consistency**
   - Plan mentions `NEXT_PUBLIC_UNIFIED_CANVAS=1` in one place; sample.env uses `true`.
   - Recommendation: Standardize on `true|false` and update docs accordingly.

7) **Derived mode storage**
   - Server stores `derived_mode` into `run.mode` for analytics; ensure downstream lists/filters understand it’s synthetic.
   - Recommendation: Add a short comment in code/docs to avoid confusion when reading run history.

---

### Additional Validation & UI Checks (per user request)

1) **Is image upload visible in the enhanced Creative Canvas?**

- Finding: In the Creative Canvas path, the drag-and-drop image upload UI is not rendered. The upload block remains in the legacy branch of `PipelineForm.tsx`, while `CreativeCanvas.tsx` only renders `EditModeSelector` if an image is already present.
- Root cause (code-level):
```1221:1797:front_end/src/components/PipelineForm.tsx
{/* Image Upload */}
<Box sx={{ mb: 4 }}>
  ... // upload UI (dropzone)
</Box>
```
```121:175:front_end/src/components/creativeCanvas/CreativeCanvas.tsx
// No dropzone rendered; only EditModeSelector when uploadedFile exists
```
- Recommendation (non-breaking):
  - Extract the existing dropzone into a reusable component `ImageDropzone.tsx` and render it inside `CreativeCanvas` just above the Template Gallery.
  - Wire it to the same handlers currently in `PipelineForm.tsx` (`getRootProps`, `getInputProps`, `onDrop`, `removeImage`) via props.
  - Keep legacy branch unchanged for rollback.

2) **Form validation: brief OR image**

- Frontend: `validateFormData` checks either legacy `prompt` or `unifiedBrief.generalBrief` OR `image_file` (or uploadedFile) before enabling submit; this satisfies the requirement.
- Backend: `/api/v1/runs` validates that either `prompt` or `unified_brief.generalBrief` or `image_file` is present; otherwise returns 400.
- Suggested polish:
  - Add `z.string().min(1, 'Creative brief is required or upload an image')` to `unifiedBrief.generalBrief` when `unifiedBrief` exists to surface inline feedback sooner.
  - Trim whitespace before validation to avoid accidental spaces passing the check.

3) **Visual improvement opportunities**

- Upgrade Template Gallery visuals
  - Replace emoji circles with curated thumbnails per task type; use consistent rounded corners, subtle border, and hover zoom.
  - Use Next Image for responsive, optimized loading; include descriptive alt text.

- Introduce a concise canvas header microcopy
  - Add a single-sentence subheading under the title that guides new users (e.g., “Describe your idea, optionally add a reference image, then refine with lenses”).

- Harmonize card styling and spacing
  - Standardize on a single elevation level and use `alpha(primary, 0.08)` for selected borders; ensure 8/16/24 spacing rhythm across sections.

- Make actions more “sticky” and reassuring
  - Keep the footer CTA row visible on long pages (sticky bottom bar within the card), and show a short recap (platform, variants, brief length) next to the button.

- Motion polish
  - Add slight scale-in for lens content and a fade-in for template selection states; keep durations ≤ 200ms to feel snappy.

- Accessibility
  - Add ARIA-expanded/controls for lens sections; ensure keyboard focus moves to opened content. Confirm 44px tap targets on mobile.

---

### Recommended Actionables (Systematic Plan)

- **A. Frontend – Functionality**
  - Add `ImageDropzone.tsx`; render in `CreativeCanvas` above Template Gallery; reuse existing dropzone handlers from `PipelineForm.tsx`.
  - Make `PipelineFormData.mode` optional in `front_end/src/types/api.ts`; remove `mode` from defaults; only append if defined in `api.ts`.
  - Centralize platform options (e.g., `front_end/src/lib/constants.ts`), import in both `PipelineForm.tsx` and `CreativeCanvas.tsx`.
  - Replace Template Gallery emoji cards with curated images under `front_end/src/assets/task_types/`; use Next Image; add alt text.

- **B. Frontend – UX/Visual Polish**
  - Add subheading microcopy under Canvas header to guide new users.
  - Harmonize cards: consistent elevation, border color via `alpha(primary, 0.08)`, 8/16/24 spacing.
  - Make footer CTA row sticky; include a compact run recap (platform, variants, brief length).
  - Add subtle motion (≤ 200ms) to lens content and template selection state.

- **C. Frontend – Accessibility & Perf**
  - Add ARIA attributes (expanded/controls) to lens sections; manage focus when opening/closing.
  - Ensure controls meet 44px tap target guidelines.
  - Dynamic import `CreativeCanvas` subtree and heavy modals (Preset/BrandKit/StyleRecipe/ColorPalette) to reduce initial bundle.

- **D. Backend – Validation & Docs**
  - Confirm content-driven validation: brief OR image; keep `mode` optional-only and derive for analytics.
  - Add code comment in run listing/detail noting `mode` may be derived.
  - Standardize env flags on `true|false`; update docs.

- **E. Tests**
  - Frontend: add tests for ImageDropzone in Canvas, Template Gallery image selection, sticky CTA presence, ARIA roles.
  - Backend: tests for no-mode submissions, brief-or-image rule, and malformed unified_brief JSON.
  - Normalizer: confirm ignoring removed fields; mapping still correct.

- **F. Rollout**
  - Keep `NEXT_PUBLIC_UNIFIED_CANVAS` on by default in dev; verify legacy path remains intact.
  - Stage changes behind flags; canary with selected users; monitor run starts and error rates.

- **G. Acceptance Criteria**
  - Canvas shows an image dropzone; users can start with image-only, brief-only, or both.
  - Template Gallery shows curated images with alt text; selection is clear and snappy.
  - Sticky CTA present; recap shows correct info; accessibility checks pass.
  - All tests pass (frontend/backend/normalizer); no regression in WebSocket results flow.

- **H. Suggested Sequence (Non-breaking)**
  1. Types & schemas (make mode optional; add ARIA stubs; constants).
  2. Add ImageDropzone to Canvas; wire handlers; verify submit.
  3. Replace Template Gallery visuals with curated images.
  4. Visual polish (microcopy, spacing, borders, sticky CTA recap).
  5. Accessibility (ARIA, focus management, tap targets).
  6. Performance (dynamic imports for heavy components).
  7. Tests (frontend, backend, normalizer) and docs/flags standardization.
  8. Canary rollout and monitor.

---

### Quick Visual Checklist (Canvas)

- Primary brief area prominent and inviting: YES
- Image upload affordance clear and friendly: PARTIAL (missing in Canvas; present in legacy)
- Templates visually scannable: PARTIAL (emoji-based; replace with images)
- Lenses discoverable and compact: YES
- Actions prominent and aligned: YES

---

### Conclusion

The implementation closely matches the plan, preserves all core capabilities, and delivers a more user-centric, compact creation experience. Adding the image dropzone to the Creative Canvas, tightening validation UX, and upgrading template visuals will further improve clarity and professionalism without breaking existing behavior.

---

### Gap Analysis – Brand Lens and Template Save/Load

1) Brand Lens – parity with legacy behavior

- Finding: In the Creative Canvas brand lens, brand voice is read-only and logo cannot be uploaded. Legacy actions (Load Kit, Save Kit) were replaced with “Manage Presets / Edit Colors / Style Recipes”.
- Evidence:
```146:241:front_end/src/components/creativeCanvas/LensBrand.tsx
{/* Brand Voice (read-only box) */}
<Controller name="brand_kit.brand_voice_description" ...>
  <Box ...>
    <Typography ...>
      {field.value || 'No brand voice defined'}
    </Typography>
  </Box>
</Controller>
```
```191:205:front_end/src/components/creativeCanvas/LensBrand.tsx
{/* Logo (display only) */}
<CompactLogoDisplay ... />
```
```210:241:front_end/src/components/creativeCanvas/LensBrand.tsx
{/* Action buttons (non-legacy) */}
<Button ...>Manage Presets</Button>
<Button ...>Edit Colors</Button>
<Button ...>Style Recipes</Button>
```
- Legacy reference (desired parity):
```1363:1381:front_end/src/components/PipelineForm.tsx
<Button ... onClick={handleLoadBrandKitPreset}>Load Kit</Button>
<Button ... onClick={handleSaveBrandKitPreset} disabled={!hasBrandKitData()}>Save Kit</Button>
```

- Actionable fixes:
  - Replace read-only Brand Voice display with an editable TextField (small size, 250 char limit, live counter) bound to `brand_kit.brand_voice_description` (as in legacy).
  - Add `LogoUploader` in the lens; when a logo is present, show `CompactLogoDisplay` with remove action; otherwise show `LogoUploader`. Bind to `brand_kit.logo_file_base64` and `brand_kit.logo_analysis` (legacy behavior).
  - Revert brand lens actions to the legacy pair: “Load Kit” (opens BrandKitPresetModal) and “Save Kit” (calls handleSaveBrandKitPreset), and keep “Edit Colors” for palette editing. Remove “Manage Presets” and “Style Recipes” from the Brand Lens (style recipes are unrelated to brand kit configuration).
  - Preserve auto-enable `apply_branding` when brand kit data present and auto-clear on disable (already works).

- Acceptance criteria:
  - Brand Voice can be edited inline and respects 250-char guidance with counter.
  - Logo can be uploaded/removed; preview shows; data persists as before.
  - Buttons appear as “Load Kit”, “Save Kit”, and “Edit Colors” only; they work identically to legacy.

2) Save/Load Template – missing fields (brief, text overlay, edit instruction)

- Finding: Save Template excludes creative brief and text overlay captured via unifiedBrief; Load Template doesn’t hydrate text overlay back to the Canvas.
- Evidence (save):
```644:676:front_end/src/components/PipelineForm.tsx
const inputSnapshot = {
  mode: currentValues.mode,
  prompt: currentValues.prompt || '',           // unifiedBrief not mapped here
  ...
  task_description: currentValues.task_description || null, // text overlay not mapped here
  image_instruction: currentValues.image_instruction || null,
  ...
};
```
- Evidence (load):
```418:446:front_end/src/components/PipelineForm.tsx
reset({
  prompt: inputData.prompt || '',              // not hydrating unifiedBrief.generalBrief
  ...
  task_description: inputData.task_description || '', // not hydrating unifiedBrief.textOverlay.raw
  image_instruction: inputData.image_instruction || '',
  ...
});
```

- Actionable fixes (non-breaking mapping):
  - On Save Template (INPUT_TEMPLATE):
    - Map `unifiedBrief.generalBrief` → `input_snapshot.prompt` when present (fallback to legacy `prompt`).
    - Map `unifiedBrief.textOverlay.raw` → `input_snapshot.task_description` when present (this preserves legacy semantics that previously used task description for overlay text).
    - If `unifiedBrief.intentType === 'instructedEdit'`, map `unifiedBrief.editInstruction` → `input_snapshot.image_instruction`.
  - On Load Template (applyPresetToForm):
    - After `reset({...})`, hydrate Canvas state:
      - If `inputData.prompt`, set `unifiedBrief.generalBrief` accordingly in form state.
      - If `inputData.task_description`, set `unifiedBrief.textOverlay.raw` and consider toggling `render_text=true`.
      - If `inputData.image_instruction`, and an image is present or later uploaded, prefill `unifiedBrief.editInstruction` and set `intentType='instructedEdit'`.
  - Ensure Save Template preserves brand kit (with color migration) and language, render_text, apply_branding, and marketing fields as before.

- Acceptance criteria:
  - Saving a template captures the brief (into prompt), overlay (into task_description), and edit instruction (into image_instruction) when applicable.
  - Loading a template restores brief into Canvas, overlay into TextOverlayComposer (and toggles render_text), and edit instruction into EditModeSelector.
  - Legacy templates still load successfully without Canvas hydration (no runtime errors).

---

### Implementation Notes (to guide the fixes)

- Brand Lens
  - Replace read-only Typography block with a TextField bound to `brand_kit.brand_voice_description` (mirror legacy snippet around lines 1405–1435 in `PipelineForm.tsx`).
  - Swap CompactLogoDisplay for conditional LogoUploader/CompactLogoDisplay as per legacy behavior (lines ~1463–1479 in `PipelineForm.tsx`).
  - Replace action buttons block with legacy “Load Kit” and “Save Kit” callbacks (lines 1363–1381 in `PipelineForm.tsx`), plus keep color editor trigger.

- Template Save/Load
  - Save: In `handleSaveTemplate`, build `inputSnapshot.prompt` from `unifiedBrief.generalBrief || prompt`, `inputSnapshot.task_description` from `unifiedBrief.textOverlay?.raw || task_description`, and `inputSnapshot.image_instruction` from `unifiedBrief.editInstruction || image_instruction`.
  - Load: In `applyPresetToForm`, after `reset`, call `setValue('unifiedBrief', hydratedBrief)` with fields built from `input_snapshot` and toggle `render_text` if overlay present.
  - Keep color migration and brand kit preservation as currently implemented.

---

### Test Additions

- Brand Lens
  - Edit brand voice and save; ensure value persists in form state and submission payload when apply_branding is true.
  - Upload and remove logo; ensure base64 stored/cleared and CompactLogoDisplay updates accordingly.
  - Buttons: “Load Kit” opens preset modal; “Save Kit” disabled until brand kit present.

- Template Save/Load
  - Save: When unifiedBrief provided (brief/overlay/editInstruction), verify template `input_snapshot` contains prompt/task_description/image_instruction.
  - Load: Select saved template; verify Canvas fields (brief/overlay/editInstruction) hydrate and `render_text` toggles if overlay exists.

---

### UI/UX Enhancement Recommendations (Focused on 1–6)

1) Headers – make them professional and non-redundant

- Finding: Parent header is “Create New Pipeline Run” while CanvasHeader shows “Creative Canvas” (conflicts and feels prototype-ish).
- Action:
  - Remove the “Creative Canvas” title/icon; keep a concise subheading (microcopy) under the parent header.
  - Update parent header to “Create Visual” (or “Create New Visual”) for a professional tone during prototyping. Retain app header “Churns • Beta”.
- Where:
```903:917:front_end/src/components/PipelineForm.tsx
<Typography variant="h4">Create New Pipeline Run</Typography>
```
```12:22:front_end/src/components/creativeCanvas/CanvasHeader.tsx
<Typography variant="h4">Creative Canvas</Typography>
```
- Implementation notes:
  - Change parent header text to “Create Visual”.
  - In CanvasHeader, drop the h4 title and icon; keep a single body text line guiding users (microcopy), e.g., “Describe your idea or add a reference image; refine with lenses when needed.”
- Acceptance:
  - Single clear page header; Canvas section has helpful microcopy only.

2) Brief/Image optionality – present better than “(Optional)”

- Finding: “Reference Image (Optional)” is textual; Creative Brief lacks “Optional”, yet the rule is “either one required”.
- Action:
  - Add a centered divider-chip between Brief and Image: Chip label “Provide one: Brief or Image”.
  - Add subtle “Optional” chips near both section titles (MUI Chip, size small) instead of text in title.
  - Keep existing footer alert as reinforcement only when invalid.
- Where:
  - Between CreativeBriefInput and ImageDropzone (Canvas path) and in legacy form block.
- Acceptance:
  - Users see a clear visual cue “Provide one: Brief or Image”; both sections marked Optional; validation and footer alert align.

3) Optional vs. mandatory – consistent indicators

- Action:
  - Mark required fields via MUI required prop or an asterisk consistently (e.g., Platform required).
  - Add a lightweight legend (caption) at the top: “Fields marked * are required”.
  - Default non-essential controls to collapsed/hidden state.
- Where:
```137:154:front_end/src/components/creativeCanvas/CreativeCanvas.tsx
<FormControl fullWidth required>Target Platform</FormControl>
```
- Acceptance:
  - Clear, consistent required markers; optional sections visually secondary.

4) Tooltips – consistent, intentional usage

- Action:
  - Define tooltip defaults: placement="top", arrow, enterDelay=300, leaveDelay=0, maxWidth ~280px.
  - Use tooltips only on: icons without labels, switches (Brand/Text) with short explanations, sliders (creativity/variants) with concise help, language dropdown info, and “Save as Template” eligibility.
  - Centralize strings in a tooltip map (e.g., `front_end/src/lib/ui-tooltips.ts`).
- Acceptance:
  - All tooltips consistent in style and tone; no tooltip duplicating visible labels.

5) Lenses – unify switch vs. collapse behavior

- Finding: Each lens has both a Switch (enable) and a separate expand/collapse button; feels redundant.
- Action (consistent model across lenses):
  - Keep the Switch as the single source of truth (enable/disable).
  - Auto-expand content when Switch turns on; auto-collapse when off.
  - Make the entire header (title row) clickable to toggle the Switch for faster interaction; remove the separate chevron button.
  - Keep a subtle “Configured”/“Has Content” chip for quick scanning.
- Where:
```103:133:front_end/src/components/creativeCanvas/LensBrand.tsx
// Switch + separate expand button
```
```108:118:front_end/src/components/creativeCanvas/LensText.tsx
// Switch + separate expand button
```
- Implementation notes:
  - Drive expansion exclusively from the Switch state and remove the chevron Button.
  - Maintain accessibility via ARIA-expanded on the header container reflecting switch state.
- Acceptance:
  - One-click enable reveals settings; disabling hides content. No redundant controls.

6) Reset and Template application – state, collapse, and hydration

- Finding: Reset should collapse empty sections; applying templates should uncollapse affected sections and hydrate fields correctly.
- Action:
  - Reset: ensure `apply_branding=false`, `render_text=false`, clear `brand_kit`, reset `unifiedBrief`, remove image; drive expansion from switches so content collapses automatically.
  - Apply template: After `reset({ ... })`, set toggles true when snapshot contains content (brand kit → apply_branding, overlay → render_text, editInstruction + image → set instructedEdit); then set unifiedBrief to hydrate brief/overlay/instructions.
  - Order: set toggles before hydrating to trigger auto-expand, or keep the current effect but ensure order consistency.
- Where:
```575:615:front_end/src/components/PipelineForm.tsx
resetFormToDefaults() // ensure toggles false and brief cleared
```
```418:446:front_end/src/components/PipelineForm.tsx
applyPresetToForm() // hydrate legacy + setValue for toggles and unifiedBrief
```
- Acceptance:
  - Reset collapses all lenses and clears data; templates uncollapse relevant lenses and restore values without extra clicks.

---

### Implementation Checklist (UI/UX)

- Headers:
  - [ ] Rename parent header to “Create Visual”; remove Canvas h4; keep microcopy only.
- Brief/Image requirement:
  - [ ] Add Divider with Chip “Provide one: Brief or Image”.
  - [ ] Add small “Optional” chips to Brief and Image titles.
- Required markers:
  - [ ] Ensure Platform has required indicator; add form legend.
- Tooltips:
  - [ ] Create `ui-tooltips.ts`; apply consistent Tooltip props and messages.
- Lenses:
  - [ ] Remove chevrons; header toggles switch; auto expand/collapse based on switch.
- Reset/Template:
  - [ ] Reset collapses empty sections and clears state.
  - [ ] Template sets toggles first, then hydrates unifiedBrief and expands relevant sections.

- Tests:
  - [ ] Headers render as expected.
  - [ ] Brief-or-Image chip present; submit blocked until one provided.
  - [ ] Tooltips render with standard props and content.
  - [ ] Lenses expand/collapse based on switch only.
  - [ ] Reset collapses; template un-collapses and hydrates.
