# Image Refinement Add-On – Prototype Implementation Plan

---
## 1 Objectives
1. Deliver four refinement capabilities without altering existing generation flow:  
   • Subject repair • Text repair • Regional refinement • General refinement.
2. Keep the staged-output experience and Live WebSocket streaming intact.
3. Re-use current storage (`./data/`), run manifests, and pipeline executor.
4. Ship a single-command Docker experience **unchanged**.

---
## 2 High-Level Architecture Extension
```
 Browser                FastAPI                           Pipeline
┌──────────┐   POST /runs/{id}/refine ───►  ┌──────────┐   
│ Results  │──────── WebSocket /ws/{job} ──►│ Executor │──►  new *refinement* stage(s)
└──────────┘◄──────── updated PNG / JSON ◄──└──────────┘
```
• A *refinement job* is a child of an existing **run** and gets its own UUID.  
• The executor loads the parent run's final image + context, appends a refinement stage list, and streams logs exactly like generation.

---
## 3 User Journey & UI/UX
1. **Run Complete Screen** – add **"Refine Image"** button next to each output.
2. Clicking opens **Refinement Drawer** (Material-UI `SwipeableDrawer`) with *4 tabs*:
   - **Subject Repair** – shows original & generated images side by side, asks for subject image upload (optional) + description textarea.
   - **Text Repair** – overlays OCR-detected text boxes; user edits text in a form list.
   - **Regional** – Canvas (react-konva) to draw rect masks + per-mask prompt.
   - **General** – Single textarea for free-form prompt.
3. **Submit** triggers `/refine` API; drawer switches to *live log* tab identical to the run page.
4. When done, new image cards stack under originals with a *version badge* (v2, v3…).  Users can chain refinements.

*Accessibility Notes*: All controls keyboard-navigable; color-blind safe badges.

---
## 4 API Design
```
POST /api/v1/runs/{run_id}/refine
{
  "type": "subject|text|region|general",
  "payload": { ... },          // type-specific fields
  "creativity": 1-3            // optional override
}

Responses
201 Created → { "job_id": "uuid" }

WebSocket  /api/v1/ws/{job_id}
```
### Payload Schemas
• **subject** `{ "referenceFileId": "uuid", "instructions": str }`  
• **text**    `{ "corrections": [ {"bbox": [x,y,w,h], "text": str } ], "instructions": str }`  
• **region**  `{ "masks": [ {"bbox": [x,y,w,h], "prompt": str } ] }`  
• **general** `{ "prompt": str }`

*Backward-compatibility*: No changes to existing `/runs` endpoints.

---
## 5 Pipeline Additions
Directory: `stages/refine/`
| Order | File                    | Purpose |
|-------|-------------------------|---------|
| 1     | `load_base_image.py`    | Load parent run image into ctx |
| 2     | `subject_repair.py`     | (optional) Only if type==subject |
| 2     | `text_repair.py`        | (optional) Only if type==text |
| 2     | `region_repair.py`      | (optional) Only if type==region |
| 2     | `general_repair.py`     | (optional) Only if type==general |
| 3     | `save_outputs.py`       | Persist PNG + updated manifest |

Implementation notes:
• Each stage implements existing `run(ctx)` signature.  
• Use OpenAI Image Edit or Stability SDK with `ctx.mask` when region masks present.  
• Helper in `pipeline/utils/editing.py` wraps calls for all modes.

`configs/stage_order.yml` gains a second list:
```yaml
refinement:
  - load_base_image
  - conditional_stage  # executor resolves to one file above
  - save_outputs
```
Executor update: if `ctx.mode == "refine"` load this list.

---
## 6 Data & Persistence
• Store refined images under `./data/{run_id}/refinements/{job_id}/image.png`.  
• Append a `refinements` array to the parent `run.json`:
```json
{
  "job_id": "uuid",
  "type": "text",
  "payload": { ... },
  "image_path": ".../image.png",
  "created_at": "ISO" }
```
No DB schema change needed (SQLModel `Run` already has `JSON` field for extra).

---
## 7 Routing Changes (Next.js)
```
/pages
  runs/[id]/index.tsx        // existing details + refine drawer
  runs/[id]/results.tsx      // unchanged
```
Components:
• `RefineDrawer.tsx` (tabs, form logic)  
• `MaskCanvas.tsx` (react-konva wrapper)  
• Re-use existing `LogStream` component for WebSocket events.

State management remains in SWR hooks; add `useRefinement(jobId)`.

---
## 8 Testing Strategy
1. **Unit** – Mock editing SDK; assert each stage mutates `ctx.data` as expected.
2. **Integration** – Create fake run → call `/refine` → ensure output file exists and manifest updated.
3. **Front-end** – Cypress test records user drawing a mask and sees new image card.
4. **Regression (parity)** – Original pipeline tests untouched.

---
## 9 Alternative Lightweight Approach
Merge all logic into a single stage `image_refine.py` with a switch on `ctx.refine_type`.  Simpler short-term but harder to extend.

---
## 10 Estimated Effort
• Backend (API + stages): 1.5 days  
• Front-end UI/UX: 2 days  
• Tests & polish: 1 day

---
## 11 Next Steps
1. Scaffold `api/v1/refine.py` router + schemas.
2. Implement executor support for `mode="refine"`.
3. Build front-end drawer (static)
4. Wire WebSocket & streaming.
5. Write unit tests (TDD) for `subject_repair.py`.
6. QA end-to-end in Docker.

> ✅ With this plan we add powerful iterative refinement while leaving the core generation flow and repo layout untouched. 