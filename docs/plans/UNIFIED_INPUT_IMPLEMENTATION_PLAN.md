## Unified Input Implementation Plan

### 1. Objective

This document outlines the implementation plan for replacing the three legacy user inputs (`prompt`, `imageInstruction`, `taskDescription`) with a unified "Creative Brief" and context-aware components. This will reduce user ambiguity, improve intent capture, and streamline the pipeline, as detailed in the [Unified Input Strategy and Pipeline Alignment analysis](../analysis/INPUT_UNIFICATION_AND_PIPELINE_ALIGNMENT.md).

### 2. Core Components & Phased Rollout

The implementation will be executed in three phases to ensure a safe and reversible rollout:

*   **Phase 1: Foundational Backend & Frontend (Dual Mode)**: Implement the new schemas, frontend components, and backend normalization layer. The API will accept both new and legacy fields, with the new `UnifiedBrief` being normalized to populate legacy context fields for backward compatibility.
*   **Phase 2: Comprehensive Testing**: Develop and execute unit, integration, and end-to-end tests to validate the new input flow and ensure no regressions in pipeline behavior.
*   **Phase 3: Deprecation & Cleanup**: After a monitoring period, phase out the legacy fields from the frontend and then the backend.

---

### Phase 1: Foundational Backend & Frontend (Dual Mode)

#### **1.1. Backend Tasks**

**Task 1.1.1: Define Pydantic Models**
*   **File**: `churns/api/schemas.py`
*   **Action**: Add the `TextOverlay` and `UnifiedBrief` Pydantic models. The `TextOverlay` model will be simplified to only include the fields currently in use.

```python
# In churns/api/schemas.py

class TextOverlay(BaseModel):
    raw: Optional[str] = None
    language: Optional[str] = None  # "en" | "zh" | "auto"

class UnifiedBrief(BaseModel):
    intentType: Literal[
        "fullGeneration", "defaultEdit", "instructedEdit", "styleAdaptation", "logoOnly"
    ]
    generalBrief: str
    editInstruction: Optional[str] = None
    textOverlay: Optional[TextOverlay] = None
    styleHints: Optional[List[str]] = None

# Add UnifiedBrief to the main RunPipelineRequest model
class RunPipelineRequest(BaseModel):
    # ... existing fields
    unifiedBrief: Optional[UnifiedBrief] = None
```

**Task 1.1.2: Implement Input Normalizer**
*   **File**: `churns/core/input_normalizer.py` (new file)
*   **Action**: Create a function to map the `UnifiedBrief` object to the legacy `PipelineContext` fields (`prompt`, `image_reference.instruction`, `task_description`). This ensures the rest of the pipeline can function without immediate changes.

```python
# In churns/core/input_normalizer.py
from churns.pipeline.context import PipelineContext
from churns.api.schemas import UnifiedBrief

def normalize_unified_brief_into_context(brief: UnifiedBrief, ctx: PipelineContext):
    """Populates the pipeline context from the new unified brief."""
    ctx.prompt = brief.generalBrief

    if brief.intentType == "instructedEdit" and brief.editInstruction:
        if ctx.image_reference is None:
            ctx.image_reference = {}
        ctx.image_reference["instruction"] = brief.editInstruction

    if brief.textOverlay and brief.textOverlay.raw:
        ctx.task_description = brief.textOverlay.raw
```

**Task 1.1.3: Integrate Normalizer into API Router**
*   **File**: `churns/api/routers.py` (or wherever the pipeline is invoked)
*   **Action**: In the `/run_pipeline` endpoint, check if `unifiedBrief` exists. If so, call the normalizer *before* executing the pipeline.

```python
# In churns/api/routers.py
from churns.core.input_normalizer import normalize_unified_brief_into_context

@router.post("/run_pipeline/", response_model=RunResponse)
async def run_pipeline_endpoint(request: RunPipelineRequest, ...):
    # ... setup ...
    ctx = PipelineContext(...)

    if request.unifiedBrief:
        normalize_unified_brief_into_context(request.unifiedBrief, ctx)

    # ... continue to pipeline executor ...
```

**Task 1.1.4: Update Creative Expert Prompt**
*   **File**: `churns/stages/creative_expert.py`
*   **Action**: This task is **complete**. The system prompt has been updated to correctly parse the `task_description` field for literal text (in quotes) and content/creative briefs (outside quotes).

#### **1.2. Frontend Tasks**

**Task 1.2.1: Define TypeScript Types**
*   **File**: `front_end/src/types/api.ts`
*   **Action**: Add the `UnifiedBrief` and `TextOverlay` types to mirror the simplified Pydantic models.

```typescript
// In front_end/src/types/api.ts
export type TextOverlay = {
  raw?: string;
  language?: "en" | "zh" | "auto";
};

export type UnifiedBrief = {
  intentType: "fullGeneration" | "defaultEdit" | "instructedEdit" | "styleAdaptation" | "logoOnly";
  generalBrief: string;
  editInstruction?: string;
  textOverlay?: TextOverlay;
  styleHints?: string[];
};

export interface RunPipelineRequest {
  // ... existing fields
  unifiedBrief?: UnifiedBrief;
};
```

**Task 1.2.2: Create New Form Components**
*   **Directory**: `front_end/src/components/`
*   **Action**: Create three new, modular components:
    *   `CreativeBriefInput.tsx`: A robust textarea component for the main `generalBrief`.
    *   `EditModeSelector.tsx`: A component with radio buttons (`Default Edit`, `Instructed Edit`) and a small textarea for `editInstruction`. This component is only visible when a reference image is present.
    *   `TextOverlayComposer.tsx`: A simple textarea for the `textOverlay.raw` input, with clear placeholder text explaining the "quotes for literals" convention. This is only visible when text rendering is enabled.

**Task 1.2.3: Refactor `PipelineForm.tsx`**
*   **File**: `front_end/src/components/PipelineForm.tsx`
*   **Action**:
    1.  Import and render the three new components.
    2.  Implement the conditional rendering logic based on `isImageUploaded` and `isTextRenderEnabled` state.
    3.  Remove or hide the three legacy textareas for `prompt`, `imageInstruction`, and `taskDescription`.
    4.  Update the form's state management (`useState` or a state management library) to build the `UnifiedBrief` object.

**Task 1.2.4: Update API Submission Logic**
*   **File**: `front_end/src/lib/api.ts`
*   **Action**: In the function responsible for submitting the pipeline request:
    1.  Accept the new `UnifiedBrief` object from the form.
    2.  Construct the request payload to include **both** the new `unifiedBrief` object and the legacy fields, populated from the `UnifiedBrief` object. This ensures backward compatibility during the transition.

```typescript
// Example snippet in front_end/src/lib/api.ts
function submitPipeline(formData) {
  const { unifiedBrief, ...otherFields } = formData;

  const requestBody = {
    ...otherFields,
    unifiedBrief, // Send the new object
    // Also send legacy fields for dual-mode compatibility
    prompt: unifiedBrief.generalBrief,
    task_description: unifiedBrief.textOverlay?.raw || '',
    image_reference: {
      instruction: unifiedBrief.editInstruction || '',
      // ... other image ref fields
    },
  };

  // POST requestBody to API
}
```

---

### Phase 2: Comprehensive Testing

**Task 2.1: Backend Tests**
*   **2.1.1 Unit Test for Normalizer**:
    *   **File**: `churns/tests/core/test_input_normalizer.py` (new file)
    *   **Action**: Create tests to verify that `normalize_unified_brief_into_context` correctly maps all fields for all `intentType` variations.
*   **2.1.2 Expand Stage Unit Tests**:
    *   **Files**: `test_strategy_stage.py`, `test_creative_expert_stage.py`, `test_prompt_assembly_stage.py`
    *   **Action**: Add test cases that construct a `PipelineContext` using a normalized `UnifiedBrief` and assert that the stage's behavior and outputs are correct.
*   **2.1.3 Integration Tests**:
    *   **File**: `test_full_pipeline_integration.py`
    *   **Action**: Add new integration tests covering end-to-end runs for:
        *   Instructed edit with a text overlay.
        *   Default edit (no instruction).
        *   Full generation with a complex text overlay brief.

**Task 2.2: Frontend Tests**
*   **2.2.1 Component Tests**:
    *   **Directory**: `front_end/src/components/__tests__/`
    *   **Action**: Write unit/integration tests for the new components (`CreativeBriefInput`, `EditModeSelector`, `TextOverlayComposer`) to ensure they render correctly and handle user input.
*   **2.2.2 Form Logic Tests**:
    *   **File**: `front_end/src/components/__tests__/PipelineForm.unified.test.tsx` (new file)
    *   **Action**: Write tests for `PipelineForm.tsx` to:
        *   Verify the correct components are rendered based on form state.
        *   Confirm the `UnifiedBrief` object is assembled correctly on submission.
        *   Mock the API call and verify that both new and legacy fields are being sent.

---

### Phase 3: Deprecation & Cleanup

**Task 3.1: Monitor Legacy Usage**
*   **Location**: Backend API (`churns/api/routers.py`)
*   **Action**: Add logging to track how many incoming requests use *only* the legacy fields without the `unifiedBrief` object. This will inform the timeline for deprecation.

**Task 3.2: Remove Legacy Frontend Code**
*   **Files**: `front_end/src/lib/api.ts`, `front_end/src/components/PipelineForm.tsx`
*   **Action**: Once monitoring shows negligible use of the legacy-only path, remove the code that sends the legacy fields in the API request. The frontend will now send *only* the `unifiedBrief` object.

**Task 3.3: Remove Legacy Backend Code**
*   **Files**: `churns/core/input_normalizer.py`, `churns/api/routers.py`, stage files.
*   **Action**: After the frontend change has been deployed and stabilized:
    1.  Modify the pipeline entry point to directly use `unifiedBrief` fields to populate the context, removing the need for the normalizer.
    2.  Refactor stages to directly read from a more structured context if desired, or continue using the populated legacy fields.
    3.  Delete `input_normalizer.py`.
    4.  Remove the legacy fields from the `RunPipelineRequest` Pydantic model.
