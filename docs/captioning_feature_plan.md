# Captioning Feature – Implementation Plan

> Goal: Seamlessly extend the prototype **Churns** pipeline so that each generated image is delivered with an on-brand, platform-optimised social-media caption and a simple regeneration flow that versions every caption.

---
## 1 High-Level Workflow
1. **New Pipeline Stage** – `caption.py`
   1. *Analyst step* – produces a JSON **Caption Brief**.
   2. *Writer step* – produces the final caption string.
2. **Executor**
   * `caption` stage is **not** part of the default `stage_order`.  
     The executor exposes a helper `run_single_stage(run_id, image_id, "caption", payload)` that the API invokes when the user requests a caption.
3. **Storage**
   * Captions are persisted as `data/{run_id}/{image_id}/captions/{v}.json` (brief) + `{v}.txt` (final).
   * `v` is an auto-incrementing integer (0 = first pass).
4. **API**
   * `POST /runs/{run_id}/images/{image_id}/caption` – triggers caption stage (optional user overrides).
   * `POST /runs/{run_id}/images/{image_id}/caption/{v}/regenerate` – re-run Writer only (default) or both steps when overrides provided.
   * `GET  /runs/{run_id}/images/{image_id}/captions` – list versions with metadata.
5. **Front-End**
   * **Results page** – each image card displays a **Generate Caption** button. Clicking opens a dialog where the user can tweak tone, CTA, emojis, and hashtag strategy, then triggers the caption API.  
     * Once a caption exists, it is rendered beneath the image with a *Regenerate* dropdown for subsequent versions.

---
## 2 Back-End Details
### 2.1 Stage Code (`stages/caption.py`)
```python
from .utils import call_llm, save_file, load_json

class CaptionStage:
    name = "caption"

    def run(self, ctx):
        img = ctx.current_image  # provided by previous stage
        userSettings = ctx.payload.get("captionSettings", {})

        if ctx.request.get("regenerateWriterOnly") and img.captionBrief:
            brief = img.captionBrief  # cache hit
        else:
            brief = self._run_analyst(img, userSettings)
            img.captionBrief = brief

        caption = self._run_writer(brief)
        img.add_caption(caption)

    # _run_analyst() and _run_writer() hide LLM calls.
```
*Key points*
• The cached `captionBrief` gives cheap creativity loops (regenerateWriterOnly).
• Mocks in unit tests replace `call_llm`.

### 2.2 SQLModel Tables
```python
class Caption(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    imageId: UUID
    version: int
    briefPath: str
    captionPath: str
    settings: JSON
    createdAt: datetime = Field(default_factory=datetime.utcnow)
```
*Discreet table keeps history & quick lookup.*

### 2.3 API Routes
* Placed in `api/captions.py`; mounted under `/captions` router.
* Use background task to enqueue stage when caption generation is called after the initial run.
* Validation layer mirrors existing pattern, returns 202 with polling URL.

---
## 3 Front-End (Next.js)
### 3.1 Generate Caption Flow
*Extend existing `ImageCard` component*
```tsx
<Button size="small" onClick={openCaptionDialog}>Generate Caption</Button>
{caption && (
  <Typography variant="body2">{caption.text}</Typography>
  <Button size="small" onClick={openRegenerateDialog}>Regenerate</Button>
)}
```

*CaptionDialog* contains the settings form (tone, CTA, emoji toggle, hashtag strategy) and submits to `POST /caption` for that image.  
Behaviour:
• **Auto-mode first** – the dialog shows a single primary action: **Generate (Auto)**.  
• An **"Advanced Options" accordion** (collapsed by default) reveals tone, CTA, emoji toggle, and hashtag strategy overrides.  
• If the user doesn't expand the accordion, the API is called with an empty `captionSettings` object triggering the pipeline's Auto logic.  
• Real-time status is streamed over WebSocket; on `caption_added` the UI replaces the button with the caption text and regeneration controls.

### 3.2 No Additional Pages Required
All interactions still occur within the existing form and results pages—keeping the prototype simple while deferring caption decisions until the user sees the image.

---
## 4 Caption Regeneration Logic
| Scenario | API Call | Stage(s) Executed | Cache | Version Increment |
|----------|----------|-------------------|-------|-------------------|
| *Default* (new creativity) | `/caption/{v}/regenerate` with empty body | Writer only | Brief reused | +1 |
| *Settings changed* | `/caption/{v}/regenerate` with body | Analyst + Writer | Brief refreshed | +1 |

---
## 5 Testing Strategy (TDD)
1. **Unit**
   * Validate JSON schema of Caption Brief.
   * Ensure caption matches platform structure regex.
2. **Integration**
   * End-to-end test: fixed metadata ➜ caption ➜ assert deterministic output via seeded stub.
3. **API**
   * FastAPI test client: happy path, invalid params, regenerate flow.
4. **Front-End**
   * React Testing Library: form state ➜ POST payload; regenerate dialog state machine.

---
## 6 Alternative Designs (Trade-offs)
1. **Single LLM Call** – Simpler, cheaper; lower caption quality.
2. **External Caption Micro-Service** – Decouples heavy compute, but over-kill for prototype.
Current plan chooses in-process dual-stage for best balance.

---
## 7 Implementation Steps
1. Add SQLModel `Caption` table & alembic migration.
2. Create `stages/caption.py` with Analyst/Writer helpers.
3. Implement executor `run_single_stage` helper for on-demand caption runs.
4. Implement `api/captions.py` CRUD & regenerate endpoints; mount router.
5. Persist caption files under `data/`.
6. Extend executor + WebSocket to emit `caption_added` event.
7. Front-End: ImageCard **Generate Caption** button, CaptionDialog, RegenerateDialog.
8. Write tests; update CI.

---
## 8 Done-Definition
* User can generate an image, then choose to generate a caption with custom settings.
* Regenerating caption produces new version without touching previous ones.
* All new code is lint-clean, covered by tests, and adheres to modular layout.

---
## 9 Implementation Progress

### ✅ Milestone 1: Core Models & Stage Implementation (Completed)
- **Date:** December 2024
- **Changes:**
  - Added `CaptionBrief`, `CaptionSettings`, and `CaptionResult` Pydantic models to `churns/models/__init__.py`
  - Created `churns/stages/caption.py` with two-stage approach (Analyst + Writer LLMs)
  - Implemented centralized JSON parsing integration following existing patterns
  - Added proper error handling and token usage tracking
  - Followed existing stage patterns from `image_eval.py` and `creative_expert.py`

### 🔄 Next Steps:
1. Test caption stage in isolation
2. Create API endpoints for caption generation
3. Implement single-stage executor helper
4. Add WebSocket events for real-time updates
5. Frontend integration

### ✅ Milestone 2: API Endpoints Implementation (Completed)
- **Date:** December 2024
- **Changes:**
  - Added caption-related schemas to `churns/api/schemas.py` (`CaptionSettings`, `CaptionRequest`, `CaptionRegenerateRequest`, `CaptionResponse`)
  - Created caption endpoints in `churns/api/routers.py`:
    - `POST /{run_id}/images/{image_id}/caption` - Generate caption for specific image
    - `POST /{run_id}/images/{image_id}/caption/{version}/regenerate` - Regenerate caption with new settings
    - `GET /{run_id}/images/{image_id}/captions` - List all caption versions
  - Added background task processing for caption generation in `churns/api/background_tasks.py`
  - Implemented WebSocket events for real-time caption updates
  - Fixed timezone deprecation warnings for datetime usage

### 🔄 Next Steps:
1. Test API endpoints
2. Create simple test for caption generation flow
3. Frontend integration (Generate Caption button + dialog)
4. File storage for caption persistence
5. Full end-to-end testing

### ✅ Milestone 3: API Testing & Validation (Completed)
- **Date:** December 2024
- **Changes:**
  - Created comprehensive integration tests for caption API endpoints in `churns/tests/test_caption_api.py`
  - Tests cover all scenarios: success, auto mode, error cases, regeneration (writer-only and full), validation
  - Fixed FastAPI dependency injection for proper test mocking
  - All 8 API tests passing successfully
  - Validated caption endpoints are properly registered and accessible
  - Confirmed two-stage caption generation workflow integration

### ✅ Milestone 4: File Structure & Token Usage Integration (Completed)
- **Date:** December 2024
- **Changes:**
  - **Fixed caption output directory structure** to follow existing pattern: `data/runs/{run_id}/captions/{image_id}/`
  - **Enhanced file persistence** with three files per caption version:
    - `v{version}.txt` - Final caption text
    - `v{version}_brief.json` - Strategic brief from Analyst LLM
    - `v{version}_result.json` - Complete result with metadata and token usage
  - **Confirmed token usage tracking** - Caption LLM calls tracked in `ctx.llm_usage` with keys:
    - `caption_analyst` - Token usage for strategic brief generation
    - `caption_writer` - Token usage for final caption writing
  - **Token usage persistence** - All LLM usage data saved to `pipeline_metadata.json` under `processing_context.llm_call_usage`
  - **Fixed metadata file path** - Caption generation now correctly loads from `pipeline_metadata.json` (not `metadata.json`)
  - **Concurrent execution confirmed** - Multiple caption generations can run simultaneously with unique task IDs

### 🔄 Next Steps:
1. ✅ Test API endpoints
2. ✅ Create simple test for caption generation flow  
3. ✅ Fix file structure and token usage integration
4. Frontend integration (Generate Caption button + dialog)
5. End-to-end testing with real LLM calls 

### ✅ Milestone 5: Data Validation & Main Subject Extraction (Completed)
- **Date:** December 2024
- **Changes:**
  - **Removed misleading defaults** from strategy and visual concept data extraction
  - **Added safe data extraction functions**:
    - `_safe_extract_strategy_data()` - Returns None for missing fields instead of defaults
    - `_safe_extract_visual_data()` - Returns None for missing fields instead of defaults
    - `_validate_required_data()` - Validates critical fields are present before caption generation
  - **Enhanced main subject extraction** with fallback logic:
    - Primary: Extract from `visual_concept.main_subject`
    - Fallback: Extract from `image_analysis_result.main_subject` when visual concept has null/missing subject
    - Error handling: Raises clear error when no valid main subject found
  - **Improved prompt construction** to only include available data:
    - Optional fields only added to prompt if they exist
    - Auto-mode logic adapts based on available context data
    - Clear indication when falling back to defaults vs. using actual data
  - **Added comprehensive tests** (5 new tests):
    - Main subject extraction from image analysis
    - Handling missing data scenarios
    - Safe extraction without defaults
    - Validation of required fields
    - Graceful handling of incomplete pipeline data
  - **Enhanced error handling** - Caption generation fails gracefully with clear error messages when required data is missing

### 🔄 Next Steps:
1. ✅ Test API endpoints
2. ✅ Create simple test for caption generation flow  
3. ✅ Fix file structure and token usage integration
4. ✅ Improve data validation and main subject extraction
5. Frontend integration (Generate Caption button + dialog)
6. End-to-end testing with real LLM calls 

### ✅ Milestone 6: Centralized Model Configuration (Completed)
- **Date:** December 2024  
- **Changes:**
  - **Added caption model configuration to `constants.py`**:
    - `CAPTION_MODEL_PROVIDER = "OpenRouter"` 
    - `CAPTION_MODEL_ID = "openai/gpt-4o-mini"` (cost-effective model)
    - Added pricing information for `openai/gpt-4o-mini` in `MODEL_PRICING`
  - **Extended `client_config.py`** to support caption clients:
    - Added caption model imports from constants
    - Added caption client configuration in `_configure_clients()`
    - Caption clients follow same pattern as other stages
  - **Updated caption stage** to use centralized configuration:
    - Removed hardcoded model values from `background_tasks.py`
    - Caption stage now gets model ID and provider from constants
    - Follows same client injection pattern as other stages
  - **Added caption cost calculation** to main pipeline cost tracking:
    - Caption usage keys (`caption_analyst`, `caption_writer`) added to stage mappings
    - Caption costs now included in final cost summary calculations
  - **Environment variable support** - Caption model can be overridden via:
    - `CAPTION_MODEL_PROVIDER` environment variable
    - `CAPTION_MODEL_ID` environment variable

### 🔄 Next Steps:
1. ✅ Test API endpoints
2. ✅ Create simple test for caption generation flow  
3. ✅ Fix file structure and token usage integration
4. ✅ Improve data validation and main subject extraction
5. ✅ Centralize model configuration and cost tracking
6. Frontend integration (Generate Caption button + dialog)
7. End-to-end testing with real LLM calls

### ✅ Milestone 7: Frontend Integration (Completed)
- **Date:** December 2024  
- **Changes:**
  - **Created CaptionDialog component** (`front_end/src/components/CaptionDialog.tsx`):
    - Auto-mode first approach with advanced options in collapsible accordion
    - Settings for tone, CTA, emoji inclusion, hashtag strategy
    - Beautiful Material-UI design matching existing app aesthetic
    - Loading states and disabled states during generation
  - **Created CaptionDisplay component** (`front_end/src/components/CaptionDisplay.tsx`):
    - Displays generated captions with copy-to-clipboard functionality
    - Regeneration dropdown with writer-only and full regeneration options
    - Version tracking and settings display
    - Timestamp and metadata information
  - **Integrated caption functionality into RunResults**:
    - Added "Caption" button to image action buttons
    - Caption display below assessment indicators
    - State management for multiple image captions
    - Loading states per image during generation
  - **Added caption API methods** to `front_end/src/lib/api.ts`:
    - `generateCaption()` - Initial caption generation
    - `regenerateCaption()` - Caption regeneration with settings
    - `getCaptions()` - List all caption versions for an image
  - **Extended TypeScript interfaces**:
    - `CaptionSettings`, `CaptionResult`, `CaptionResponse` types
    - Updated `WebSocketMessage` to include `caption_added` events
  - **WebSocket integration**:
    - Real-time caption generation updates
    - Automatic caption loading when generation completes
    - Live progress feedback in logs
  - **Frontend builds successfully** with no TypeScript or linting errors

### 🔄 Next Steps:
1. ✅ Test API endpoints
2. ✅ Create simple test for caption generation flow  
3. ✅ Fix file structure and token usage integration
4. ✅ Improve data validation and main subject extraction
5. ✅ Centralize model configuration and cost tracking
6. ✅ Frontend integration (Generate Caption button + dialog)
7. End-to-end testing with real LLM calls
8. Performance optimization and caching
9. User documentation and help tooltips