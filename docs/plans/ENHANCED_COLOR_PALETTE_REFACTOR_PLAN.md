# Enhanced Color Palette Refactoring and Enhancement Plan

## 1. Overview

This document outlines the implementation plan for refactoring the `EnhancedColorPaletteEditor.tsx` component and refining its backend integration. The goal is to improve frontend code maintainability and enhance the clarity of prompts sent to the LLM pipeline for more accurate results, based on the findings in the `ENHANCED_COLOR_PALETTE_ANALYSIS.md` document.

## 2. Frontend Refactoring (`EnhancedColorPaletteEditor.tsx`)

### 2.1. Objective

To improve the maintainability, readability, and reusability of the `EnhancedColorPaletteEditor.tsx` component by breaking down its monolithic structure into smaller, more focused sub-components and separating utility functions.

### 2.2. Task Breakdown

#### Task 2.2.1: Extract Generic Utility Functions

1.  **Identify Generic Utilities:** The `apiCallWithRetry` function within `EnhancedColorPaletteEditor.tsx` is a generic helper that can be used elsewhere in the application.
2.  **Move the Utility:**
    *   Cut the `apiCallWithRetry` function from `EnhancedColorPaletteEditor.tsx`.
    *   Paste it into the shared API library at `front_end/src/lib/api.ts`.
    *   Export the function from `api.ts`.
3.  **Update Imports:**
    *   Modify `EnhancedColorPaletteEditor.tsx` to import `apiCallWithRetry` from its new location in `front_end/src/lib/api.ts`.

#### Task 2.2.2: Isolate SVG Mockup Previews into Design-Centric Components

1.  **Create a New Directory for Previews:**
    *   Create a new directory: `front_end/src/components/design_previews/`.
2.  **Create `ProductFocusedPreview` Component:**
    *   Create a new file: `front_end/src/components/design_previews/ProductFocusedPreview.tsx`.
    *   This component will contain an SVG mockup of a product-centric ad (e.g., a drink or a dish). It will demonstrate how primary/secondary colors work for backgrounds and how accent colors highlight CTAs.
    *   The component should accept the `colors` array as a prop to dynamically render the preview.
3.  **Create `PromotionalAnnouncementPreview` Component:**
    *   Create a new file: `front_end/src/components/design_previews/PromotionalAnnouncementPreview.tsx`.
    *   This component will contain an SVG mockup for a text-heavy promotional graphic (e.g., "Special Offer"). It will showcase text legibility using neutral colors against the brand palette.
    *   The component should also accept the `colors` array as a prop.
4.  **Create `LifestyleAtmospherePreview` Component:**
    *   Create a new file: `front_end/src/components/design_previews/LifestyleAtmospherePreview.tsx`.
    *   This component will contain an SVG mockup of a mood-focused lifestyle scene (e.g., a cafe interior). It will demonstrate how the color palette contributes to the overall brand voice.
    *   The component will accept `colors` as a prop.
5.  **Integrate New Preview Components:**
    *   In `EnhancedColorPaletteEditor.tsx`, import the three new preview components.
    *   Replace the existing hardcoded SVG blocks with calls to these new, more relevant components, passing the `colors` state to them.


## 3. Backend Prompt Refinement

### 3.1. Objective

To strengthen the instructional prompts sent to the LLM pipeline, ensuring that the generated content more strictly adheres to the user-defined brand colors and their semantic roles.

### 3.2. Task Breakdown

#### Task 3.2.1: Refine `style_guide.py` User Prompt

1.  **Locate Prompt Logic:** Open `churns/stages/style_guide.py` and navigate to the `_get_style_guider_user_prompt` function.
2.  **Strengthen the Instruction:** Find the section where the prompt is constructed for a provided `brand_kit`.
3.  **Modify Wording:**
    *   **Current Wording:**
      ```
      Your style suggestions should be inspired by these colors and their semantic roles. Keep guidance concise, emphasize hierarchy, and ensure accessibility.
      ```
    *   **Proposed New Wording:**
      ```
      Your style suggestions must strictly adhere to this brand color palette. The provided semantic roles and usage plans are not optional guidelines; they are constraints that must be followed to ensure brand consistency.
      ```
4.  **Update Prompt Construction:** Replace the old line in the `prompt_parts` list with the new, more directive wording.

#### Task 3.2.2: Refine `creative_expert.py` User Prompt

1.  **Locate Prompt Logic:** Open `churns/stages/creative_expert.py` and navigate to the `_get_creative_expert_user_prompt` function.
2.  **Strengthen Color Plan Instruction:** In the section that details the "Color Application Plan," add a sentence to reinforce the strictness of the color constraints.
3.  **Modify Wording:**
    *   **Current Guidance:** The current prompt asks the model to create a color plan.
    *   **Proposed Addition:** Add the following sentence to the guidance for the `color_palette` field:
      ```
      The color scheme you define MUST be built from the provided Brand Colors. Non-brand colors should only be used sparingly as supporting functional shades (e.g., pure white for a background) if absolutely necessary. Adherence to the brand palette is a primary requirement.
      ```
This change will make it clearer to the LLM that the brand colors are a strict constraint, not merely a suggestion.