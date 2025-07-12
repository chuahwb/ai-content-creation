# Caption Generation – Enhancement Plan

## 1. Objective
Elevate the quality and relevance of generated captions by:
1. Incorporating **task-type optimisation**, mirroring the existing logic used for imagery design.
2. Leveraging **additional context** already produced by the image-generation pipeline.
3. Maintaining backward compatibility with current modes (`task_specific_mode`, `easy_mode`, `custom_mode`).
4. Ensuring the update is fully covered by automated tests (TDD).

---

## 2. Task-Type Optimisation
### 2.1 Source of Truth
* Task types are defined in `churns/core/constants.py` (e.g. "1. Product Photography", …, "8. Behind the Scenes Imagery").
* A guidance map for imagery already exists in `stages/creative_expert.py → task_type_guidance_map`.

### 2.2 Proposed Mapping for Captions
Create a **`taskTypeCaptionGuidanceMap`** (Python dict) colocated in `caption.py` (or external YAML for easier maintenance). Each entry should provide:
* `captionObjective` – high-level purpose of the caption.
* `toneHints` – tonal keywords to steer the LLM.
* `hookTemplate` – optional string template for opening lines.
* `structuralHints` – platform-agnostic structural cues (e.g. list vs story vs tip carousel).

Example snippet:
```python
# caption.py
TASK_TYPE_CAPTION_GUIDANCE = {
    "1. Product Photography": {
        "captionObjective": "Showcase product features & craftsmanship to spark desire and perceived quality.",
        "toneHints": ["aspirational", "sensory", "detail-oriented"],
        "hookTemplate": "Up close with {product} —",  # keeps room for creative continuation
        "structuralHints": "Hook → Sensory description → Benefit → CTA"
    },
    "2. Promotional Graphics & Announcements": {
        "captionObjective": "Drive immediate awareness and action for time-sensitive offers or news.",
        "toneHints": ["urgent", "excited", "inclusive"],
        "hookTemplate": "Heads up! {promo_title} drops {date} —",
        "structuralHints": "Headline → Key offer → Scarcity line → CTA"
    },
    "3. Store Atmosphere & Decor": {
        "captionObjective": "Transport the audience into the ambience and evoke an in-store experience.",
        "toneHints": ["immersive", "inviting", "storytelling"],
        "hookTemplate": "Step into our space —",
        "structuralHints": "Hook → Atmosphere description → Feeling → CTA"
    },
    "4. Menu Spotlights": {
        "captionObjective": "Highlight a specific menu item with appetite appeal and encourage orders.",
        "toneHints": ["mouth-watering", "friendly", "tempting"],
        "hookTemplate": "Craving something {flavour}? Meet our {menu_item} —",
        "structuralHints": "Hook → Taste/ingredient details → Benefit → CTA"
    },
    "5. Cultural & Community Content": {
        "captionObjective": "Celebrate cultural roots or community stories to foster connection and authenticity.",
        "toneHints": ["warm", "respectful", "celebratory"],
        "hookTemplate": "From our community to yours —",
        "structuralHints": "Hook → Cultural story → Value → CTA"
    },
    "6. Recipes & Food Tips": {
        "captionObjective": "Educate followers with practical recipes or tips featuring the product.",
        "toneHints": ["educational", "encouraging", "practical"],
        "hookTemplate": "Save this recipe: {dish_name} —",
        "structuralHints": "Hook → Key step or tip → Benefit → CTA"
    },
    "7. Brand Story & Milestones": {
        "captionObjective": "Share brand journey or achievements to build emotional connection and trust.",
        "toneHints": ["inspirational", "authentic", "grateful"],
        "hookTemplate": "Our journey began with {origin} —",
        "structuralHints": "Hook → Narrative snippet → Milestone → CTA"
    },
    "8. Behind the Scenes Imagery": {
        "captionObjective": "Reveal the people and process behind the brand to humanise and build transparency.",
        "toneHints": ["candid", "relatable", "transparent"],
        "hookTemplate": "Behind the scenes at {brand} —",
        "structuralHints": "Hook → Process insight → Team mention → CTA"
    }
}
```

### 2.3 Integration Points
1. **PipelineContext** already carries `task_type` (see `pipeline_metadata.json → request_details`).
2. In `_get_analyst_user_prompt(...)`:
   * Retrieve `ctx.task_type` (fallback to `None`).
   * If present **and** `task_type` exists in guidance map, inject a **Task Type Guidance** section into the prompt.
3. Add a new field to `CaptionBrief` schema (optional) – `task_type_notes` – so the Writer LLM can also respect it.
4. **Keep Creativity Unlocked** – guidance acts as *suggestive rails*, not *hard chains*. We only pass *tone hints* and *objectives*; the model keeps latitude on wording & structure.

### 2.4 Mode Handling
* **task_specific_mode** – always include guidance.
* **easy_mode / custom_mode** – include only if `task_type` present, otherwise omit without penalty.

### 2.5 Conflict-Avoidance & Harmony
* **Structural vs Platform Guidance** – `structuralHints` are **platform-agnostic**. The Analyst MUST defer to `platform_optimizations[platform].caption_structure` when there is any clash. We instruct the model:

  > "Treat **structuralHints** as inspiration. If the platform optimisation already prescribes a structure, **merge** or **defer** to it. Do **not** duplicate or contradict.”

* **Tone Reconciliation Priority** –
  1. `CaptionSettings.tone` (explicit user choice)
  2. `visual_concept.lighting_and_mood` + `strategy.target_voice`
  3. `TASK_TYPE_CAPTION_GUIDANCE.toneHints` (fallback flavour)

  The Analyst prompt will include this priority to avoid clashes.

* **Hook Template Flexibility** – Hook templates are labelled "example hook". The Analyst is free to adapt wording or discard if a stronger open line emerges from context.

  > "Use **hookTemplate** as a creative starting point only. Feel free to remix or craft a better hook that suits the overall context.”

---

## 3. Additional Context Signals
- **Critical signals** (always include):
  1. `style_guidance_sets[i].style_keywords` – gives the LLM concrete visual vocabulary to echo.
  2. `generated_image_prompts[i].visual_concept.creative_reasoning` – provides the narrative/story behind the visual.
  3. `processing_context.suggested_marketing_strategies[i].target_niche` – sharpens audience relevance.

- **Optional signals** (include when feature‐flagged or when high confidence):
  * `image_assessment.general_score` & `assessment_justification` – useful for future adaptive captions (e.g. compensating weak visuals) but **not critical** today; can be skipped to keep prompt lean.
  * `visual_concept.color_palette` – poetic flair only; safe to omit.

Implementation: add helper `_extract_additional_style_context(...)` and append to Analyst prompt under **Style Context**.

---

## 4. Implementation Steps
**Compatibility Guarantee** – All modifications are **additive & optional**, so existing flows keep working if the new flag is off.

1. **Data Extraction**
   * Extend `PipelineContext` **non-breaking** by adding `task_type: str | None = None` with a default `None`.
   * Utility funcs live **within caption.py** to avoid import cycles; they are pure helpers.
   * If `enableTaskTypeCaptionOptimisation` is **False**, helper returns `None` and existing prompt remains unchanged.
   * No other modules need to import the new map directly → encapsulation keeps surface area minimal.

2. **Prompt Construction**
   * Wrapper check:

     ```python
     if ctx.get("enableTaskTypeCaptionOptimisation") and task_type_guidance:
         # inject extra prompt blocks
     ```

   * Existing prompt structure is preserved; we only **append** sections.
   * `_get_writer_user_prompt` guards with `if getattr(brief, "task_type_notes", None):` to avoid AttributeErrors when old briefs are passed.

3. **CaptionBrief Schema**
   * Add optional `task_type_notes: str | None` field (Pydantic). Populate this with a concise, one-sentence summary: _"Optimise for {task_type}: {captionObjective}."_
4. **Writer Prompt**
   * Inside `_get_writer_user_prompt`, surface `brief.task_type_notes` just after **Core Message**:

     ```text
     **Task Note:** {task_type_notes}
     ```

     This keeps the writer aware without over-specifying.
5. **Config / Constants**
   * Store `TASK_TYPE_CAPTION_GUIDANCE` in `churns/core/constants.py` **or** a new module `churns/configs/task_type_caption.yml` for easy editing.
6. **Tests (TDD)**
   * New file `tests/test_caption_task_type.py` with parametrised cases:
     1. Valid task type → Analyst prompt contains "**Task Type Context:**".
     2. Unknown task type → guidance omitted.
     3. CaptionBrief populated with `task_type_notes`.
   * Mock LLM client to isolate prompt text.

---

## 5. Alternative Solutions
* **External YAML Config** – non-devs tweak wording without code deploy.
* **Dynamic LLM Retrieval** – ask a separate model to draft guidance on-the-fly (higher token cost, but ultra-flexible).

---

## 6. Roll-Out Plan
1. Wrap new logic behind flag `enableTaskTypeCaptionOptimisation` (env or ctx flag).
2. Launch to staging with A/B test (flag on vs off) measuring caption quality ratings.
3. Monitor token usage impact and iterate.

---

## 7. Estimated Effort
| Item | Complexity | Hours |
|------|------------|-------|
| Mapping & utils | Low | 2 |
| Prompt & schema updates | Medium | 4 |
| Tests & fixtures | Medium | 3 |
| Docs & config | Low | 1 |
| **Total** |  | **10** |

---

## 8. Next Steps
1. Vet this plan with stakeholders.
2. Approve guidance phrases & mapping table.
3. Create implementation PRs following the outlined steps.
4. Set up telemetry to evaluate caption performance post-launch.