# Implementation Plan: Refactor "Apply Branding" Toggle

This document outlines a focused implementation plan to refactor the "Apply Branding" toggle in the main pipeline form. The goal is to improve user experience by making branding a globally accessible feature, available in all modes (`Easy`, `Custom`, `Task-Specific`).

---

## 1. Executive Summary

The current UI prevents users from applying a Brand Kit in `Easy Mode`, forcing them into a more complex workflow than necessary. This plan will correct this by making the "Apply Branding" toggle and its associated `BrandKit` editor available in all modes, controlled only by the toggle's state.

Other components, such as the "Render Text" toggle and the "Advanced Settings" section (containing `task_description`), are already implemented correctly and will not be changed.

---

## 2. Current State Analysis

*   **`PipelineForm.tsx`**:
    *   The "Apply Branding" toggle and the `BrandKit` editor are currently only rendered when `showAdvancedFields` is `true` (i.e., in `custom_mode` or `task_specific_mode`).
    *   The `task_description` field is correctly located within an "Advanced Settings" section that is exclusive to advanced modes.
    *   The "Render Text" toggle is correctly implemented as a global control.
*   **User Experience Gap**:
    *   A user cannot apply a Brand Kit in `Easy Mode`.

---

## 3. Proposed Architecture & UI/UX Enhancements

| Feature / Component | Proposed Strategy | Rationale |
| :--- | :--- | :--- |
| **"Apply Branding" Toggle** | **Globally Visible.** The `Switch` control will be rendered and accessible in all three modes. | Applying a pre-configured brand is a foundational action, not an advanced one. Users should be able to apply their brand to any task, simple or complex. |
| **`BrandKit` Editor UI** | **Conditionally Rendered & Visually Grouped.** The editor will appear inside its own `Paper` component (creating a "card" effect) whenever the "Apply Branding" toggle is **ON**, regardless of the selected mode. A header with a `<PaletteIcon />` will be added for clarity. | This visually isolates the Brand Kit as a distinct, self-contained tool. The card layout provides a strong boundary, preventing confusion with other settings. |
| **Visual Separation** | **Spacing and `Paper` Components.** The `BrandKit` editor card and the `Advanced Settings` accordion will be separated by sufficient vertical margin. Each is contained in its own `Paper`-like component, creating clear visual grouping. | Strong grouping and separation prevent the user from mentally blending the two distinct sections, improving overall form clarity and usability. |

---

## 4. Detailed Implementation Plan - Frontend (`PipelineForm.tsx`)

The work will be focused on a few specific areas within `PipelineForm.tsx`.

### Step 1: Relocate the "Apply Branding" Toggle

The `FormControlLabel` containing the `apply_branding` `Switch` needs to be moved out of the `showAdvancedFields` conditional block.

*   **Action**: Find the block of code responsible for rendering the "Options" (containing the "Render Text" and "Apply Branding" toggles). Currently, this is inside the `showAdvancedFields` block. It needs to be moved outside of it, to be on the same level as the "Generation Settings" or "Prompt" fields.

**Current (Simplified):**
```tsx
// RIGHT SIDE
<Grid item xs={12} lg={5}>
  {showAdvancedFields ? (
    <Box>
      // ... a lot of advanced fields
      // Brand Kit editor is here
    </Box>
  ) : (
    // Placeholder
  )}
</Grid>

// LEFT SIDE (Incorrect location for global options)
// ...
<Box sx={{ mb: 4 }}>
  <Typography>Options</Typography>
  // Toggles are here, but should be global
</Box>
```

**Proposed (Simplified):**
```tsx
// LEFT SIDE
<Grid item xs={12} lg={7}>
  // ... Mode, Platform, Creativity, Prompt, Image Upload ...
  
  {/* --- Global Options --- */}
  <Box sx={{ mb: 4 }}>
    <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>
      Options
    </Typography>
    <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      <RenderTextToggle />
      <ApplyBrandingToggle />
    </Box>
  </Box>
</Grid>

// RIGHT SIDE
<Grid item xs={12} lg={5}>
  {/* --- Brand Kit (now also on right side) --- */}
  <AnimatePresence>
    {watch('apply_branding') && (
      <motion.div>
        <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <PaletteIcon /> Brand Kit
          </Typography>
          <BrandKitEditor />
        </Paper>
      </motion.div>
    )}
  </AnimatePresence>
  
  {/* --- Advanced Settings (remains as-is) --- */}
  {showAdvancedFields && (
    <AdvancedSettingsAccordion />
  )}
</Grid>
```

### Step 2: Relocate the `BrandKit` Editor

The conditional block that renders the `ColorPaletteEditor`, `LogoUploader`, etc., must be moved and wrapped in the styled `Paper` component.

*   **Action**: Find the `Grid item` where `applyBranding` is checked. This entire block should be moved from its current location inside the `showAdvancedFields` conditional. It should be placed on the right side of the form, and its visibility should *only* depend on `applyBranding`.

```tsx
// In the RIGHT SIDE grid item
<AnimatePresence>
  {applyBranding && (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
    >
      <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <PaletteIcon /> Brand Kit
        </Typography>
        {/* All Brand Kit components (Color, Voice, Logo) go here */}
      </Paper>
    </motion.div>
  )}
</AnimatePresence>
```

---

## 5. Backend & API Verification

No backend or API changes are required. The existing endpoints and database schemas already support this configuration correctly.

---

## 6. Validation & Testing Plan

| Test Case ID | Mode | Action | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **TC-1** | `Easy Mode` | View the form. | The "Apply Branding" and "Render Text" toggles are visible. The `BrandKit` editor is **not** visible. |
| **TC-2** | `Easy Mode` | Toggle "Apply Branding" **ON**. | The `BrandKit` editor component animates into view, contained within its own visually distinct `Paper` card with a header. |
| **TC-3** | `Easy Mode` | Toggle "Apply Branding" **OFF**. | The `BrandKit` editor card animates out of view. |
| **TC-4** | `Custom Mode` | Toggle "Apply Branding" **ON**. | The `BrandKit` editor card appears, same as in `Easy Mode`. It is visually separate from the "Advanced Settings" accordion below it. |
| **TC-5** | Form Submission | Submit from `Easy Mode` with branding **ON**. | Verify the API request payload contains `apply_branding: true` and the correct `brand_kit` data. |

---

## 7. Expected Outcome

*   **Increased Flexibility**: Users can now apply their brand in any mode.
*   **Improved UX**: The UI is more consistent and intuitive. The "Apply Branding" toggle behaves predictably across the entire application.
*   **Simplified Logic**: The rendering logic in `PipelineForm.tsx` related to branding will be simpler and easier to maintain. 