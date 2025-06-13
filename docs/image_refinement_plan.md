# Image Refinement Add-On – Prototype Implementation Plan

---
## 1 Objectives
1. Deliver three refinement capabilities without altering existing generation flow:  
   • Subject repair • Text repair • Prompt/Mask refinement (combined regional & general).
2. **Support essential chain refinements**: refine any generated image, chain refinements (A→A1→A2).
3. Keep the staged-output experience and Live WebSocket streaming intact.
4. Re-use current storage (`./data/`), run manifests, and pipeline executor.
5. Ship a single-command Docker experience **unchanged**.
6. **Essential tracking**: parent-child relationships, basic progress feedback.

---
## 2 High-Level Architecture Extension
```
 Browser                FastAPI                           Pipeline
┌──────────┐   POST /runs/{id}/refine ───►  ┌──────────┐   
│ Results  │──────── WebSocket /ws/{job} ──►│ Executor │──►  refinement stage(s)
└──────────┘◄──────── updated PNG / JSON ◄──└──────────┘
```
• A *refinement job* is a child of an existing **run** and gets its own UUID.  
• The executor supports `mode="refinement"` to load refinement-specific stage configuration.
• **Critical**: `PipelineExecutor` needs modification to support multiple stage configurations.

### 2.1 Essential Chain Support
```
Original Run → Images A, B, C
├── Refine A → A1 → A2 (chain)
├── Refine A → A3 (multiple refinements of same image)
├── Refine B → B1 (independent)  
└── Refine C → C1 (independent)
```
• **Parent Tracking**: Each refinement knows its parent image
• **Multi-Image Support**: Refine any of the N generated images
• **Multiple Refinements**: Same image can be refined multiple times independently
• **Simple Chaining**: Linear refinement chains

---
## 3 User Journey & UI/UX
1. **Run Complete Screen** – add **"Refine"** button next to each output image.
2. Clicking opens **Refinement Modal** with *3 tabs*:
   - **Subject Repair** – shows current image, asks for reference image upload + instructions.
   - **Text Repair** – shows current image, text area for repair instructions.
   - **Prompt / Mask** – shows current image with optional **Draw Mask** toggle. Text area for refinement prompt.
3. **Submit** triggers `/refine` API; modal shows *progress* with real-time feedback.
4. When done, new image appears below original with *version badge* (v2, v3…). Users can refine any version.

*Accessibility Notes*: All controls keyboard-navigable; color-blind safe badges.

For **Subject Repair** the pipeline consumes: target image + reference image + `pipeline_metadata.json` concepts → outputs a subject-corrected image.

For **Text Repair** it consumes: target image + `pipeline_metadata.json` concepts → regenerates accurate text overlays.

For **Prompt / Mask** it consumes: target image + optional mask coordinates + user prompt + `pipeline_metadata.json` concepts.

---
## 4 API Design
```
POST /api/v1/runs/{run_id}/refine
Form Data (following existing patterns):
- refine_type: str = Form(...)  # subject|text|prompt
- parent_image_id: str = Form(...)        # Which image to refine
- parent_image_type: str = Form("original") # "original" | "refinement"
- generation_index: Optional[int] = Form(None) # Which of N images (0-based)
- prompt: Optional[str] = Form(None)
- instructions: Optional[str] = Form(None)
- mask_data: Optional[str] = Form(None)  # JSON string of coordinates
- creativity_level: int = Form(2)
- reference_image: Optional[UploadFile] = File(None)

Responses
201 Created → { "job_id": "uuid" }

WebSocket  /api/v1/ws/{job_id}
```

### 4.1 Essential Additional Endpoints
```
GET /api/v1/runs/{run_id}/refinements
→ Returns list of refinements for the run (simple list, not tree)

POST /api/v1/refinements/{job_id}/cancel
→ Cancel active refinement job
```

*Backward-compatibility*: No changes to existing `/runs` endpoints.

---
## 5 Pipeline Additions
### 5.1 Executor Modifications Required
**Critical**: `PipelineExecutor` must be updated to support refinement mode:

```python
# executor.py changes needed:
def __init__(self, mode: str = "generation", ...):
    self.mode = mode
    self.stages = self._load_stage_config(mode)

def _load_stage_config(self, mode: str) -> List[str]:
    # Load from YAML based on mode
    return config.get(mode, config.get('stages', []))
```

### 5.2 Context Extensions
Extend `PipelineContext` with refinement properties:
```python
# Required properties:
ctx.parent_run_id: str
ctx.parent_image_id: str           # Which image being refined
ctx.parent_image_type: str         # "original" | "refinement"
ctx.generation_index: Optional[int] # Which of N images
ctx.base_image_path: str  
ctx.refinement_type: str
ctx.mask_coordinates: Optional[List]
ctx.reference_image_path: Optional[str]
```

### 5.3 Stage Structure
| Order | File                    | Purpose |
|-------|-------------------------|---------|
| 1     | `load_base_image.py`    | Load parent image + metadata into ctx |
| 2     | `subject_repair.py`     | (conditional) Only if type==subject |
| 2     | `text_repair.py`        | (conditional) Only if type==text |
| 2     | `prompt_refine.py`      | (conditional) Only if type==prompt |
| 3     | `save_outputs.py`       | Persist PNG + update refinement list |

### 5.4 Configuration Updates
`configs/stage_order.yml` structure:
```yaml
generation:  # Existing stages
  - image_eval
  - strategy
  - style_guide
  - creative_expert
  - prompt_assembly
  - image_generation
  - image_assessment

refinement:  # Refinement pipeline
  - load_base_image
  - conditional_stage  # executor resolves to subject_repair, text_repair, or prompt_refine
  - save_outputs
```

---
## 6 Data & Persistence

### 6.1 File Organization
**Structure supporting chain refinements**:
```
./data/runs/{run_id}/
├── originals/
│   ├── image_0.png          # First generated image
│   ├── image_1.png          # Second generated image
│   └── image_2.png          # Third generated image
├── refinements/
│   ├── {job_id}_from_0.png  # Refinement of image_0
│   ├── {job_id}_from_1.png  # Refinement of image_1
│   └── {job_id}_from_{parent_job_id}.png  # Chain refinement
├── pipeline_metadata.json   # Original generation data
└── refinements.json         # Simple refinement list (not tree)
```

### 6.2 Database Schema
**Schema supporting parent-child relationships**:
```python
class RefinementJob(SQLModel, table=True):
    id: str = Field(primary_key=True)
    parent_run_id: str = Field(foreign_key="pipelinerun.id")
    
    # Parent tracking
    parent_image_id: Optional[str] = None  # Points to another refinement or original
    parent_image_type: str = "original"    # "original" | "refinement"
    parent_image_path: Optional[str] = None  # Direct path to parent image
    generation_index: Optional[int] = None  # Which of N original images (0-based)
    
    # Core refinement data
    refinement_type: str  # subject|text|prompt
    status: RunStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    cost_usd: Optional[float] = None
    
    # Results
    image_path: Optional[str] = None
    error_message: Optional[str] = None
    
    # Input summary for UI
    refinement_summary: Optional[str] = None  # Brief description for display
```

### 6.3 Refinement Index
**File**: `refinements.json` tracks refinement list:
```json
{
  "refinements": [
    {
      "job_id": "job_1",
      "parent_image_id": "original_0",
      "parent_image_path": "originals/image_0.png",
      "image_path": "refinements/job_1_from_0.png",
      "type": "prompt",
      "summary": "Add sunset lighting",
      "cost": 0.15,
      "created_at": "2024-01-01T12:00:00Z"
    },
    {
      "job_id": "job_2",
      "parent_image_id": "job_1",
      "parent_image_path": "refinements/job_1_from_0.png",
      "image_path": "refinements/job_2_from_job_1.png",
      "type": "subject",
      "summary": "Replace main subject",
      "cost": 0.12,
      "created_at": "2024-01-01T12:05:00Z"
    }
  ],
  "total_cost": 0.27,
  "total_refinements": 2
}
```

---
## 7 Frontend Architecture

### 7.1 Results Page Enhancement
**Single page approach with refinement support**:
- **Enhanced RunResults Component**: Existing `RunResults.tsx` with refinement cards
- **Refinement Modal**: Overlay for creating refinements
- **Progress Tracking**: Real-time progress in modal

**Enhanced RunResults Features:**
- **Refined Image Cards**: Show refined images below originals with version badges
- **Refine Buttons**: "Refine" button on each image (original or refined)
- **Progress Indicators**: Progress bar during refinement
- **Cost Display**: Running total of refinement costs

### 7.2 Component Structure
```
/components
  # Enhanced Results Page (existing RunResults.tsx)
  RunResults.tsx            # EXISTING: Enhanced with refinement support
  ├── GeneratedImageCard.tsx # EXISTING: Enhanced with refine button
  ├── RefinedImageCard.tsx  # NEW: displays refined images with version badges
  ├── RefinementProgress.tsx # NEW: progress indicator for active refinements
  └── RefinementModal.tsx   # NEW: modal for creating refinements
      ├── SubjectRepairTab.tsx
      ├── TextRepairTab.tsx  
      ├── PromptMaskTab.tsx
      └── RefinementMaskCanvas.tsx # NEW: rectangular mask drawing
```

### 7.3 Schema Extensions
```typescript
interface PipelineResults {
  // ... existing fields
  refinements?: RefinementResult[]
}

interface RefinementResult {
  job_id: string
  type: 'subject' | 'text' | 'prompt'
  status: string
  parent_image_id: string
  parent_image_type: 'original' | 'refinement'
  generation_index?: number
  image_path?: string
  cost_usd?: number
  summary?: string
  created_at: string
}
```

### 7.4 State Management
- **Refinements**: Extend existing `useRun(id)` to include refinements list
- **Progress**: `useRefinementProgress(jobId)` for real-time updates
- **Re-use**: Existing `LogStream` component for WebSocket events

---
## 8 Testing Strategy
1. **Unit** – Mock editing SDK; test basic refinement logic.
2. **Integration** – Test refinement workflows: A→A1→A2, multiple refinements of same image.
3. **Front-end** – Cypress tests for refinement modal and progress.
4. **Regression** – Original pipeline tests untouched.

---
## 9 Implementation Plan

### 9.1 Phase 1: Foundation (Days 1-2) ✅ COMPLETED
**Focus**: Core refinement support
- ✅ `RefinementJob` schema with parent tracking
- ✅ File organization (originals/ + refinements/)
- ✅ refinements.json index
- ✅ API endpoint
- ✅ Stage configuration updates
- ✅ Pipeline executor refinement mode support
- ✅ Context extensions for refinement properties

**COMPLETED FILES:**
- `churns/api/database.py` - Added RefinementJob model and RefinementType enum
- `churns/api/schemas.py` - Added refinement request/response models
- `churns/api/routers.py` - Added refinement endpoints
- `churns/configs/stage_order.yml` - Added refinement pipeline configuration
- `churns/pipeline/executor.py` - Added refinement mode support with conditional stage resolution
- `churns/pipeline/context.py` - Extended context with refinement properties
- `churns/stages/load_base_image.py` - Load parent images and metadata
- `churns/stages/subject_repair.py` - Subject repair stage (placeholder with detailed implementation guidance)
- `churns/stages/text_repair.py` - Text repair stage (placeholder with detailed implementation guidance)
- `churns/stages/prompt_refine.py` - Prompt refinement stage (placeholder with detailed implementation guidance)
- `churns/stages/save_outputs.py` - Finalize outputs and update tracking

### 9.2 Phase 2: Core Backend (Days 3-4)
**Focus**: Working refinement pipeline
- Modify executor for refinement mode
- `load_base_image.py` supporting parent images
- `subject_repair.py`, `text_repair.py`, `prompt_refine.py` stages
- WebSocket progress tracking

### 9.3 Phase 3: Frontend (Days 5-6)
**Focus**: Refinement interface
- Enhance existing `RunResults.tsx` component with refinement cards
- Build `RefinementModal.tsx` with 3 tabs
- Add `RefinementProgress.tsx` component
- Implement `RefinementMaskCanvas.tsx` (rectangular)

### 9.4 Phase 4: Testing & Polish (Day 7)
**Focus**: Completion
- Workflow testing
- UI polish and bug fixes
- Docker validation

---
## 10 Realistic Effort Estimation

### 10.1 Prototype System
• **Backend**: 3 days (essential schema + refinement pipeline + basic API) ✅ **1 day completed**
• **Frontend**: 3 days (enhanced results page + modal + progress)
• **Testing**: 1 day (essential workflows)
• **Total Prototype**: 7 days

### 10.2 Critical Path Items
1. ✅ **Database schema** (blocks API) - COMPLETED
2. ✅ **Executor refinement mode** (blocks pipeline) - COMPLETED
3. ✅ **File organization** (blocks storage) - COMPLETED
4. **Enhanced `RunResults.tsx`** (blocks UI)

---
## 11 Prototype Implementation Roadmap

### 11.1 ✅ Phase 1: Foundation (Days 1-2) - COMPLETED
1. ✅ **Create `RefinementJob`** model with required fields
2. ✅ **Implement file organization**
3. ✅ **Create refinement API endpoint**
4. ✅ **Update `stage_order.yml`**

### 11.2 Phase 2: Backend (Days 3-4)
1. ✅ **Modify `PipelineExecutor`** for refinement mode - COMPLETED
2. ✅ **Build `load_base_image.py`** stage - COMPLETED
3. ✅ **Create refinement stages**: `subject_repair.py`, `text_repair.py`, `prompt_refine.py` - COMPLETED (with implementation guidance)
4. **Add WebSocket progress** tracking

### 11.3 Phase 3: Frontend (Days 5-6)
1. **Enhance `RunResults.tsx`** with refinement support
2. **Build `RefinementModal.tsx`** with 3 tabs
3. **Create `RefinementProgress.tsx`** component
4. **Implement `RefinementMaskCanvas.tsx`**

### 11.4 Phase 4: Polish (Day 7)
1. **Testing** (chain refinements work)
2. **UI bug fixes** and polish
3. **Docker validation**

---
## 12 Implementation Progress Log

### ✅ **Phase 1 Complete** - Backend Foundation (Day 1)
**SUMMARY**: Successfully implemented core refinement infrastructure with parent-child relationship tracking, API endpoints, and pipeline stage framework.

**Key Achievements:**
- **Database Schema**: Added `RefinementJob` model with comprehensive parent tracking
- **API Layer**: Complete refinement endpoints with form data and file upload support  
- **Pipeline Architecture**: Executor now supports refinement mode with conditional stage resolution
- **Stage Framework**: Created 4 refinement stages with detailed implementation guidance
- **File Organization**: Structured storage supporting chain refinements

**Technical Highlights:**
- Conditional stage resolution (`conditional_stage` → actual refinement type)
- Parent-child relationship tracking (original → refinement → refinement chain)
- Comprehensive context extensions for refinement properties
- Form-based API matching existing patterns (Form + File uploads)
- Detailed implementation guidance for actual image editing logic

**Ready for**: Phase 2 (Background task processing and WebSocket integration)

> ✅ This foundation delivers a complete refinement pipeline infrastructure suitable for prototype development and testing.