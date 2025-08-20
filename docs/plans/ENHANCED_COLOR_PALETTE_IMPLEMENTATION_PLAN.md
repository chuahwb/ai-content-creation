### Complete Implementation Plan for the EnhancedColorPaletteEditor Component

This comprehensive implementation plan details the step-by-step development of the EnhancedColorPaletteEditor React component, based on the proposed tiered brand color system. It incorporates the core philosophy of guided curation with progressive disclosure, limiting palettes to 5-7 colors for restraint and cohesion, as inspired by Material Design standards. The plan is informed by current best practices in 2025 for color palette editors in React apps, including emphasis on semantic roles (primary, secondary, accent), accessibility-first design, and theming for consistency. It also accounts for Material-UI (MUI) updates, such as native color support in v6+ for better performance and customization. WCAG guidelines remain anchored in WCAG 2.2 (effective in 2025), with 4.5:1 contrast ratios for AA compliance and new criteria for non-text elements, ensuring the component avoids relying on color alone for meaning.

The plan is organized by priority levels (High, Medium, Low) as previously outlined, with each item including:
- **Rationale:** Why this is important, tied to the proposal, user considerations (e.g., reordering vs. ratios, embedded utilities), and research insights.
- **Detailed Steps:** Specific code changes, dependencies, and implementation notes.
- **Dependencies and Tools:** Required libraries, MUI components, or external tools (e.g., for testing).
- **Testing Criteria:** How to validate, including edge cases.
- **Effort Estimate:** Low (<1 day), Medium (1-2 days), High (3+ days).
- **Potential Risks and Mitigations:** Issues like performance or conflicts.

Total estimated timeline: 3-5 weeks for a single developer, assuming iterative PRs and user testing after each priority level. Use Agile sprints: Week 1-2 (High), Week 3 (Medium), Week 4-5 (Low + Polish). Prerequisites: React 18+, MUI v6+, TypeScript for types (e.g., BrandColor interface).

#### High Priority: Polish and Stabilize Implemented Features
Focus on refining existing code for reliability, usability, and alignment with 2025 best practices like accessible theming and native color handling in MUI.

1. **Refine Semantic Roles and Limits (Tier 1 Core)**
   - **Rationale:** Semantic roles (e.g., primary for dominance) prevent chaotic palettes and empower AI outputs. Enforcing 5-7 color cap aligns with design restraint; soft warnings promote deliberate choices without paralysis.
   - **Detailed Steps:**
     - Update COLOR_ROLES object to include tooltip descriptions (e.g., { ..., tooltip: 'Primary: Dominant color for backgrounds (inferred 60% usage)' }).
     - In getAvailableRoles, add logic to suggest underused roles (e.g., prioritize 'accent' if missing).
     - In handleAddColor, if colors.length >= 5, show a MUI Alert: "Palettes over 5 colors may dilute focus—consider simplifying?" with "Proceed" button.
     - Render role subtitles with MUI Typography and Tooltip for guidance.
   - **Dependencies and Tools:** MUI Tooltip, Alert.
   - **Testing Criteria:** Add colors to hit limits; verify warnings/tooltips; edge case: maxed roles disable add buttons.
   - **Effort Estimate:** Low.
   - **Potential Risks and Mitigations:** Over-warning could annoy users—test with A/B on threshold (5 vs. 7).

2. **Enhance ColorPickerDialog and Input Methods (Tier 1 Inputs)**
   - **Rationale:** Precision inputs (hex/RGB/HSL) cater to experts; auto-labels reduce jargon. Validation prevents duplicates, ensuring clean palettes.
   - **Detailed Steps:**
     - Add tabs (MUI Tabs) in DialogContent for input modes: Hex (existing), RGB (separate fields syncing with picker), HSL (similar, using hslToHex helper).
     - Implement auto-suggest label: Use a hue map (e.g., if hue 180-240, suggest "Ocean Blue") via simple if-else in handleColorChange.
     - On save, check role-specific duplicates (e.g., no two primaries with same hex); toast.error if invalid.
     - Embed basic contrast preview in dialog: Show swatch against a neutral for quick WCAG check.
   - **Dependencies and Tools:** MUI Tabs, TextField; extend existing getContrastColor.
   - **Testing Criteria:** Switch tabs; verify sync; add duplicate → error; edge case: invalid HSL input.
   - **Effort Estimate:** Medium.
   - **Potential Risks and Mitigations:** Sync lag—use useMemo for conversions.

3. **Optimize Auto-Generated Neutrals (Tier 1 Neutrals)**
   - **Rationale:** Defaults cover 90% cases; embedding checks (per user point 2) makes it user-centric, aligning with WCAG 2.2's non-text contrast.
   - **Detailed Steps:**
     - In generateNeutrals, add fallback: if no primary, use #F9F9F9/#1A1A1A; ensure min 3:1 contrast with primaries.
     - Make toggle per neutral: Add Switch in neutral swatch for "Auto" vs. "Manual".
     - Inline icons: In swatch render, use MUI Icon (CheckCircleIcon for pass, WarningIcon for fail) based on getContrastRatio with other colors.
   - **Dependencies and Tools:** MUI Switch, Icons.
   - **Testing Criteria:** Change primary → neutrals update; toggle manual → preserve custom; low contrast → warning icon.
   - **Effort Estimate:** Low.
   - **Potential Risks and Mitigations:** Over-generation—debounce useEffect.

4. **Improve Live Palette Preview and Status Bar (Tier 1 Preview)**
   - **Rationale:** Immediate feedback aids iteration; role labels enhance semantics.
   - **Detailed Steps:**
     - Enhance bar: Map segments with Typography overlays for role abbreviations (e.g., "Pri").
     - Add Tooltip on bar: "Preview AI application (e.g., primary dominant)".
     - Status: Use MUI LinearProgress colored by theme, showing colors.length / maxColors.
   - **Dependencies and Tools:** MUI LinearProgress, Tooltip.
   - **Testing Criteria:** Add color → preview updates; hover → tooltip; full palette → progress 100%.
   - **Effort Estimate:** Low.
   - **Potential Risks and Mitigations:** Clutter on small screens—make labels optional via media query.

5. **Stabilize API Integrations for Helpers (Tier 3 Basics)**
   - **Rationale:** Reliable helpers (extraction, harmonies) make it a "design partner".
   - **Detailed Steps:**
     - Wrap fetch in async with MUI Backdrop loader.
     - On error, retry button in toast.
     - Limit additions: If > maxColors, trim least relevant (e.g., lowest score from API).
   - **Dependencies and Tools:** MUI Backdrop, CircularProgress.
   - **Testing Criteria:** Mock API fail → retry; successful add → no duplicates.
   - **Effort Estimate:** Low.
   - **Potential Risks and Mitigations:** API downtime—add offline fallbacks (hardcoded harmonies).

#### Medium Priority: Complete Essential Missing or Partial Features
Build depth with embedded utilities for seamlessness (per point 2) and inferred mechanics.

1. **Implement Inferred Ratios with Fine-Tuning (Tier 2 Ratios)**
   - **Rationale:** Infers 60-30-10 for AI; sliders add control without contradicting reordering (ratios = distribution, reordering = hierarchy).
   - **Detailed Steps:**
     - Define defaults in COLOR_ROLES (e.g., primary: 0.6).
     - In handleSaveColor, set ratio to role default.
     - In sliders, onChange: Sum totals, if >1, scale proportionally; use useEffect for normalization.
     - Add "Reset" ButtonGroup: per color and global.
   - **Dependencies and Tools:** MUI Slider, ButtonGroup.
   - **Testing Criteria:** Add primary → ratio 0.6; adjust slider → others normalize; reset → defaults.
   - **Effort Estimate:** Medium.
   - **Potential Risks and Mitigations:** Math errors—unit test normalization.

2. **Embed Accessibility and Validation Checker More Deeply (Tier 3 Checker)**
   - **Rationale:** Inline tooltips (per point 2) for proactive fixes; includes harmony checks for clashing tones.
   - **Detailed Steps:**
     - Compute all pairs in useEffect; store in state.
     - On swatches, add Tooltip with pair details (e.g., "vs. Accent: 4.8:1 ✓").
     - Add harmony: Calculate HSL delta; if >120° apart and non-complementary, warn "Clashing? Suggest analogous".
     - Click warning → suggest fix (e.g., darken hex by 10%).
   - **Dependencies and Tools:** MUI Tooltip; extend getContrastRatio.
   - **Testing Criteria:** Add clashing color → tooltip warning; fix → updates live.
   - **Effort Estimate:** Medium.
   - **Potential Risks and Mitigations:** Performance on 7 colors—memoize pairs.

3. **Add Enhanced Preview Integration (Tier 2 Preview)**
   - **Rationale:** Mock thumbnails simulate AI outputs, per design workflows.
   - **Detailed Steps:**
     - In advanced Card, add SVG element: <svg> with rect (primary fill), text (neutral_dark), circle (accent).
     - Use ratios for sizing (e.g., primary rect width = ratio * 100%).
     - Update on color/ratio change via useEffect.
   - **Dependencies and Tools:** Inline SVG or react-svg.
   - **Testing Criteria:** Change ratio → thumbnail resizes; tooltip on hover.
   - **Effort Estimate:** Medium.
   - **Potential Risks and Mitigations:** SVG complexity—start simple, iterate.

4. **Improve Helper UIs for Logo and Harmonies (Tier 3 Helpers)**
   - **Rationale:** Preview modals educate users; auto-roles from theory (e.g., dominant=primary).
   - **Detailed Steps:**
     - Post-API, open Dialog with swatches, Checkboxes for select, "Tweak" button to edit.
     - Assign roles: Sort by dominance (API data), map to availableRoles.
   - **Dependencies and Tools:** MUI Dialog, Checkbox.
   - **Testing Criteria:** Extract → modal shows 3-5; select subset → add to palette.
   - **Effort Estimate:** Medium.
   - **Potential Risks and Mitigations:** No API data—mock for dev.
