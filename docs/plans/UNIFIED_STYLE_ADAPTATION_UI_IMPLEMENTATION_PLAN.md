# Unified Implementation Plan: Style Adaptation UI & API Enhancements

This document provides a comprehensive, step-by-step implementation plan for enhancing the Style Recipe feature. It unifies the backend and frontend changes proposed in the `STYLE_ADAPTATION_RESULTS_UI_ANALYSIS.md` and `STYLE_ADAPTATION_API_AND_HISTORY_ENHANCEMENTS.md` documents into a single, actionable roadmap.

The goal is to create a clear, context-rich user experience for Style Recipe adaptations, from the results page to the run history.

---

## Gap Closure & Refinements  ⬅️ **(NEW)**

Before diving into the phased work, close the following gaps to avoid regressions and build-time errors.

1. **`base_image_url` Source of Truth**  
   • Confirm `PipelineRun` already stores a reference to the *new subject image* for a Style Adaptation. If not, add a nullable `base_image_url` column with an Alembic migration and expose it on the ORM model.  
   • Include `base_image_url` in **all** run-response schemas (`GET /run/{id}`, `/runs`).
2. **Database Performance**  
   • Create an index on `pipeline_runs.preset_id` to keep the `LEFT JOIN` in `/runs` fast.  
   • Verify the enum value used in SQL (`STYLE_RECIPE`) matches `PresetType.STYLE_RECIPE.value`.
3. **Image URL Strategy**  — ensure the `/images/{path}` helper returns a fully qualified or signed URL identical to other image assets in prod/stage.
4. **Type Safety**  
   • Keep `overrides` loosely typed (`Record<string, any>`) so future override keys don’t break the TS build.  
   • Confirm the path alias `@/types/api` resolves in `tsconfig.json`.
5. **Frontend Layout Polish**  
   • On screens `<md`, render `AdaptationContext` full-width (`xs={12}`) to avoid cramped cards.  
   • Provide Skeleton placeholders while images load.  
   • Add explicit empty-state copy if no subject image or prompt override is present.
6. **Testing & Rollback**  
   • Unit + integration tests for new API fields.  
   • Cypress/Playwright flow: create recipe → adapt → view history → open results.
7. **Deployment Safety**  
   • Version bump the API (`v1.1`) if external clients consume `PipelineRunResponse`.

---

## Phase 1: Backend API Enhancements (The Foundation)

**Objective**: Modify the backend to provide the necessary contextual data about style adaptation runs to the frontend. These changes are foundational and must be completed before frontend work can begin.

### Step 1.1: Update Data Schemas

**File**: `churns/api/schemas.py`

**Action**: Define a schema for parent preset information and add it as an optional field to the main pipeline run response schema. This makes the new data structure official.

```python
# In churns/api/schemas.py

from pydantic import BaseModel
from typing import Optional, List # Ensure imports are present

# ... other schemas ...

class ParentPresetInfo(BaseModel):
    id: str
    name: str
    image_url: Optional[str] = None

class PipelineRunResponse(BaseModel):
    # ... existing fields ...
    run_id: str
    status: str
    preset_id: Optional[str] = None
    preset_type: Optional[str] = None
    
    # NEW FIELD
    parent_preset: Optional[ParentPresetInfo] = None

    class Config:
        orm_mode = True
```

### Step 1.2: Enhance Single Run Endpoint (`GET /pipeline/run/{run_id}`)

**File**: `churns/api/routers.py`

**Action**: Modify the `get_run` function to conditionally fetch and embed the `parent_preset` details for `STYLE_RECIPE` runs. This provides the results page with everything it needs.

```python
# In churns/api/routers.py

# Ensure these imports are present at the top of the file
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from . import schemas, database
from ..models.presets import PresetType

# ...

async def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(database.PipelineRun).filter(database.PipelineRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Use the updated schema for the response
    response_data = schemas.PipelineRunResponse.from_orm(run).dict()
    
    # --- NEW LOGIC ---
    if run.preset_id and run.preset_type == PresetType.STYLE_RECIPE.value:
        parent_preset = db.query(database.BrandPreset).filter(database.BrandPreset.id == run.preset_id).first()
        if parent_preset:
            parent_image_url = None
            if parent_preset.source_run_id:
                # Find the first image from the run that created the recipe
                source_output = db.query(database.PipelineOutput.image_path) \
                                  .filter(database.PipelineOutput.run_id == parent_preset.source_run_id) \
                                  .order_by(database.PipelineOutput.created_at) \
                                  .first()
                if source_output:
                    parent_image_url = f"/images/{source_output.image_path}"

            response_data['parent_preset'] = schemas.ParentPresetInfo(
                id=parent_preset.id,
                name=parent_preset.name,
                image_url=parent_image_url
            )
    # --- END NEW LOGIC ---
            
    return response_data
```

### Step 1.3: Enhance All Runs Endpoint (`GET /pipeline/runs`)

**File**: `churns/api/routers.py`

**Action**: Modify the `get_runs` function to use a `LEFT OUTER JOIN`. This efficiently fetches the parent preset name for all adaptation runs in the history list without degrading performance.

```python
# In churns/api/routers.py

# Ensure 'and_' is imported from sqlalchemy
from sqlalchemy import and_

# ...

async def get_runs(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    results = db.query(
        database.PipelineRun,
        database.BrandPreset.name.label("parent_preset_name"),
        database.BrandPreset.id.label("parent_preset_id")
    ).outerjoin(
        database.BrandPreset,
        and_(
            database.PipelineRun.preset_id == database.BrandPreset.id,
            database.PipelineRun.preset_type == PresetType.STYLE_RECIPE.value
        )
    ).order_by(database.PipelineRun.created_at.desc()).offset(skip).limit(limit).all()

    response_runs = []
    for run, parent_preset_name, parent_preset_id in results:
        run_data = schemas.PipelineRunResponse.from_orm(run).dict()
        if parent_preset_name:
            run_data['parent_preset'] = schemas.ParentPresetInfo(
                id=parent_preset_id,
                name=parent_preset_name,
                image_url=None  # Deferred to the detail view for performance
            )
        response_runs.append(run_data)
        
    return response_runs
```

### Step 1.4: Add `base_image_url` & DB Indexes  ⬅️ **(NEW)**

1. **Alembic Migration**  
   * Create `base_image_url` (nullable `TEXT`) on `pipeline_runs`.  
   * Add an index on `preset_id` to optimise the `LEFT JOIN` used in `/runs`.
2. **ORM & Schema**  
   * Update the `PipelineRun` SQLAlchemy model and ensure `PipelineRunResponse` serialises the field.
3. **Population Logic**  
   * When a Style Adaptation run is triggered, store the uploaded subject image path in `base_image_url` so the results page can display it without an extra query.

---

## Phase 2: Frontend UI Enhancements (The Core Experience)

**Objective**: Implement the new UI components and conditional logic on the results and history pages. This phase depends on the successful completion of Phase 1.

### Step 2.1: Update Frontend Types

**File**: `front_end/src/types/api.ts`

**Action**: Mirror the backend schema changes in the frontend TypeScript types to ensure type safety.

```typescript
// In front_end/src/types/api.ts

export interface ParentPresetInfo {
  id: string;
  name: string;
  image_url?: string;
}

export interface PipelineRun {
  // ... existing fields
  run_id: string;
  status: string;
  preset_type?: string;
  base_image_url?: string;
  overrides?: Record<string, any>; // loosened typing for forward-compat
  parent_preset?: ParentPresetInfo;
}
```

### Step 2.2: Create the `AdaptationContext` Component

**File**: `front_end/src/components/AdaptationContext.tsx` (New File)

**Action**: Create a new component to display the context of a style adaptation run. This component will replace the standard "Form Inputs" display.

```typescript
// Create new file front_end/src/components/AdaptationContext.tsx

import React from 'react';
import { Paper, Typography, Grid, Box } from '@mui/material';
import { PipelineRun } from '@/types/api';
import ImageWithAuth from './ImageWithAuth';

interface AdaptationContextProps {
  run: PipelineRun;
}

const AdaptationContext: React.FC<AdaptationContextProps> = ({ run }) => {
  if (!run.parent_preset) {
    return null;
  }

  return (
    <Paper elevation={3} sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        Adaptation Context
      </Typography>
      <Grid container spacing={2}>
        {/* Source Style */}
        <Grid item xs={12} md={6}>
          <Typography variant="subtitle1" gutterBottom>
            Source Style: <strong>{run.parent_preset.name}</strong>
          </Typography>
          {run.parent_preset.image_url && (
            <ImageWithAuth
              src={run.parent_preset.image_url}
              alt={`Source style: ${run.parent_preset.name}`}
              sx={{ width: '100%', borderRadius: 1 }}
            />
          )}
        </Grid>

        {/* New Inputs */}
        <Grid item xs={12} md={6}>
          <Typography variant="subtitle1" gutterBottom>
            New Inputs
          </Typography>
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>New Subject:</Typography>
            {run.base_image_url ? (
              <ImageWithAuth
                src={run.base_image_url}
                alt="New subject image"
                sx={{ width: '100%', borderRadius: 1, mt: 1 }}
              />
            ) : (
              <Typography variant="body2" color="text.secondary">Not provided</Typography>
            )}
          </Box>
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>Prompt Override:</Typography>
            <Typography variant="body2" color="text.secondary">
              {run.overrides?.prompt || 'None'}
            </Typography>
          </Box>
        </Grid>
      </Grid>
    </Paper>
  );
};

export default AdaptationContext;
```

### Step 2.3: Update the `RunResults` Component

**File**: `front_end/src/components/RunResults.tsx`

**Action**: Implement the conditional rendering logic to show the new `AdaptationContext` component and a notification banner for style adaptation runs.

```typescript
// In front_end/src/components/RunResults.tsx

// --- IMPORTS ---
import { Alert } from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'; // Or another suitable icon
import AdaptationContext from './AdaptationContext';
// import RunInputs from './RunInputs'; // Assuming you have a component for regular inputs

// --- INSIDE THE COMPONENT RENDER ---

// After fetching the `run` object
return (
  <Container sx={{ py: 2 }}>
    {run.preset_type === 'STYLE_RECIPE' && run.parent_preset && (
      <Alert severity="info" icon={<AutoAwesomeIcon />} sx={{ mb: 2 }}>
        Results adapted from Style Recipe: <strong>{run.parent_preset.name}</strong>
      </Alert>
    )}

    {/* ... The rest of the results page grid ... */}
    
    {/* Example of where to replace the input display */}
    <Grid item xs={12} md={4}>
      {run.preset_type === 'STYLE_RECIPE' ? (
        <AdaptationContext run={run} />
      ) : (
        <RunInputs run={run} />
      )}
    </Grid>

    {/* ... */}
  </Container>
);
```

### Step 2.4: Update the `RunHistory` Component

**File**: `front_end/src/components/RunHistory.tsx`

**Action**: Enhance the run history list to visually distinguish style adaptation runs and show the parent recipe's name.

```typescript
// In front_end/src/components/RunHistory.tsx

// --- IMPORTS ---
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';

// --- INSIDE THE RENDER LOGIC FOR EACH RUN ITEM ---
// When mapping over the `runs` array fetched from the API

<ListItem key={run.run_id} /* ... */>
  <ListItemText
    primary={
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Typography>Run: {run.run_id}</Typography>
        {run.parent_preset && (
          <Tooltip title={`Adapted from: ${run.parent_preset.name}`}>
            <AutoAwesomeIcon color="primary" sx={{ ml: 1, fontSize: '1rem' }} />
          </Tooltip>
        )}
      </Box>
    }
    secondary={
      <>
        <Typography component="span" variant="body2" color="text.primary">
          {run.status} - {new Date(run.created_at).toLocaleString()}
        </Typography>
        {run.parent_preset && (
           <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
             Style: {run.parent_preset.name}
           </Typography>
        )}
      </>
    }
  />
</ListItem>
```

---

## Phase 3: Verification

**Objective**: Ensure all changes work together as expected.

1.  **Backend**: Restart the API server and test the `/pipeline/runs` and `/pipeline/run/{run_id}` endpoints using Swagger/OpenAPI docs to confirm the new `parent_preset` field appears correctly for `STYLE_RECIPE` runs.
2.  **Frontend**:
    *   Run a new Style Adaptation. Verify the results page shows the new banner and the `AdaptationContext` component with the correct source style and new subject images/text.
    *   Navigate to the Run History page. Verify that the adaptation run has the icon and "Adapted from..." text.
    *   Check a regular (non-adaptation) run to ensure its results page and history item appear as they did before, confirming no regressions were introduced.

This unified plan provides a clear path to delivering a significantly improved and more intuitive Style Recipe feature. 