### Project Goal

The goal is to unify the three existing refinement features (Subject Repair, Text Repair, and Prompt Refinement) into a single, more intuitive user experience. This involves removing the redundant Text Repair feature, transforming Subject Repair into a one-click "Repair" action, and making Prompt Refinement the primary, feature-rich editing tool in a new, unified modal.

---

### Implementation Plan

The implementation will be structured into two main phases: backend modifications followed by frontend development.

#### **Phase 1: Backend Modifications**

The focus of this phase is to adapt the API and pipeline logic to support the new, consolidated frontend experience while making minimal, targeted changes.

**1.1: Update the API Router**
The main refinement endpoint needs to be adjusted to handle the new request structure.

*   **File to Modify:** `churns/api/routers.py`
*   **Actions:**
    1.  Locate the main refinement endpoint (likely handling POST requests).
    2.  **Remove the logic branch** that handles `refinement_type: 'text'`. This will decommission the text repair feature from the API layer.
    3.  **Update the `'prompt'` refinement logic** to accept an optional `reference_image` file upload. The API will save this image and pass its path to the pipeline context (`ctx.reference_image_path`). This allows `prompt_refine.py` to use it without modification.
    4.  **Verify the `'subject'` repair logic**. Ensure it can be triggered with only the base image identifier, relying on the `get_reference_image_path` utility to find the original reference image from the parent run. No changes should be needed if it already functions this way.

**1.2: Prune Pipeline Execution Logic**
We need to ensure the `text_repair` stage is no longer callable by the pipeline executor.

*   **File to Modify:** `churns/api/background_tasks.py` and/or `churns/pipeline/executor.py`
*   **Actions:**
    1.  Search for where refinement stages are dispatched based on `refinement_type`.
    2.  Remove the case that would instantiate or call the `text_repair` stage.

**1.3: Ensure Subject Repair is Input-Free**
A minimal check is needed to guarantee the one-click repair functions as expected.

*   **File to Review:** `churns/stages/subject_repair.py`
*   **Actions:**
    1.  Confirm that the script correctly sets a default for `ctx.instructions` if none is provided (e.g., `"Replace main subject using reference image"`). The code already does this.
    2.  Confirm that `get_reference_image_path` is called to fetch the original reference image. The code already does this.
    3.  No code changes are anticipated here, as the existing implementation appears to support this use case. The "repair" will only be possible if a reference image was used in the original generation, which is a reasonable constraint.

#### **Phase 2: Frontend Redesign and Implementation**

This phase will focus on creating the new, unified UI, removing old components, and wiring everything to the updated backend.

**2.1: Design the New Unified Refinement Modal**
The existing modal will be rebuilt to be cleaner and more powerful.

*   **File to Modify:** `front_end/src/components/RefinementModal.tsx`
*   **Actions:**
    1.  **Remove the tabbed layout**. The modal's entire view will be dedicated to prompt-based refinement.
    2.  The UI will prominently feature the **prompt input textarea** and the **mask-drawing canvas**.
    3.  Introduce a new **file upload component** for the optional reference image. This will be designed to be unobtrusive, perhaps with a clear "Upload Optional Reference" label and a drag-and-drop area.
    4.  Ensure the overall modal design is clean, professional, and provides a good user experience.
    5.  **Visual & Interaction Guidelines:**
        * Maintain the existing brand color gradient header (`linear-gradient(135deg, #667eea 0%, #764ba2 100%)`) for a cohesive look.
        * Use ample white space and consistent 12-px radius card corners to match other modals.
        * Provide subtle hover states for all clickable elements (buttons, upload zone, drawing toggle) for better affordance.
        * Animate state changes (e.g., fade-in the mask overlay, loading spinner inside the primary button) to signal responsiveness.
        * Keep the mask-drawing cursor as a crosshair and dim the underlying image to 70 % opacity while drawing for clarity.
        * Include contextual helper tooltips (e.g., "Draw region" icon, "Upload reference image") to guide first-time users.
        * Validate input in real-time (disable primary button until prompt textarea has content).
        * Ensure the modal is fully keyboard accessible: focus trap, TAB order, and ARIA labels.
        * Support dark-mode theming by relying on the existing MUI palette instead of hard-coded colors.

**2.2: Implement the One-Click "Repair" Button**
Subject repair will be transformed into a one-click action within the unified refinement modal.

*   **File to Modify:** `front_end/src/components/RefinementModal.tsx`
*   **Actions:**
    1.  In the `DialogActions` area of the modal, add a new **"Repair" button**.
    2.  Position this button on the **far left** to distinguish it from the primary form actions ("Cancel" and "Start Refinement").
    3.  Style it as a less prominent button (e.g., tertiary or icon-based) to indicate it's a secondary, quick action.
    4.  Clicking this button will trigger an immediate API call to the subject repair endpoint, requiring no input from the form fields in the modal.

**2.3: Update API Client and Form Logic**
The frontend's communication with the backend needs to be updated.

*   **Files to Modify:** `front_end/src/lib/api.ts`, and components handling form submission like `front_end/src/components/PipelineForm.tsx`.
*   **Actions:**
    1.  Modify the function responsible for prompt refinement to send its payload as `multipart/form-data` to accommodate the optional image file.
    2.  Create a new, simple API function for the one-click subject repair, which will only send the necessary image identifiers.
    3.  Remove any client-side code, functions, or state management related to the old text repair feature. 

---
### **Phase 3: Refinement Details & Insights**

The goal of this phase is to provide users with valuable, on-demand insights into each refinement without cluttering the main UI.

**3.1: Introduce "Details" Button**
A new button will be added to each refined image card.

*   **File to Modify:** `front_end/src/components/RunResults.tsx`
*   **Actions:**
    1.  Add a "Details" button next to the existing "View", "Download", and "Refine" buttons on each refinement card.
    2.  This button will trigger a new dialog to display refinement metadata.

**3.2: Create a Dedicated Details Dialog**
A new modal component will be created to display the refinement information.

*   **New File:** `front_end/src/components/RefinementDetailsDialog.tsx` (or similar)
*   **Actions:**
    1.  Design a clean, read-only dialog to present information clearly.
    2.  The dialog will be populated with data fetched from a new API endpoint.

**3.3: Curate User-Friendly Metadata**
The information displayed will be tailored to be insightful for the user, not just for developers.

*   **For "Quick Repair" (Subject Enhancement):**
    *   **Refinement Type:** Automatic Subject Enhancement
    *   **Outcome:** A simple, clear description of the automated action (e.g., "The main subject was automatically enhanced using the original reference image.").
    *   **Reference Image Used:** The filename of the original reference image.
    *   **Cost & Duration:** The exact cost and time taken.

*   **For "Custom Enhancement" (Prompt Refinement):**
    *   **Refinement Type:** Custom Prompt Enhancement
    *   **Your Prompt:** The exact prompt the user provided.
    *   **AI's Refined Prompt:** The interpreted prompt the AI used.
    *   **Editing Mode:** Global or Regional (if a mask was used).
    *   **Uploaded Reference:** Filename of the new reference image, if provided.
    *   **Cost & Duration:** The exact cost and time taken.

**3.4: Create a New API Endpoint for Details**
A new endpoint will fetch detailed metadata for a single refinement job.

*   **File to Modify:** `churns/api/routers.py`
*   **Actions:**
    1.  Create a new GET endpoint, something like `/api/v1/refinements/{job_id}/details`.
    2.  This endpoint will query the `RefinementJob` table and also read the `metadata.json` file associated with the job ID to retrieve all necessary details (like the refined prompt).
    3.  This ensures the main results page remains fast, as detailed metadata is loaded on demand.

**3.5: Implement Frontend Logic**
The frontend will be updated to call the new endpoint and display the data.

*   **File to Modify:** `front_end/src/components/RunResults.tsx`
*   **Actions:**
    1.  Add state management to handle the opening/closing of the new details dialog.
    2.  Implement the `onClick` handler for the "Details" button to fetch data from the new API endpoint and pass it to the dialog component. 