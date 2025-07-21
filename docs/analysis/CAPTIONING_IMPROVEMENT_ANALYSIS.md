"# Captioning Feature: Analysis and Improvement Plan

## 1. Executive Summary

The current captioning feature is built on a solid two-stage architecture (Analyst-Writer). However, it suffers from a critical information bottleneck that dampens the impact of user-selected settings, particularly the "Caption Tone." The Analyst stage interprets the user's tone selection but fails to pass this specific instruction to the Writer, resulting in captions that feel generic regardless of the chosen voice. Additionally, the Brand Voice defined in the main form's Brand Kit is currently ignored by the captioning module.

This document proposes a series of high-impact improvements, starting with foundational fixes to solve these core issues, followed by enhancements to create a more powerful and user-centric experience.

**Key Recommendations:**

1.  **Fix Information Loss:** Modify the `CaptionBrief` data structure to include an explicit `tone_of_voice` field, ensuring the user's exact choice is passed directly to the Writer LLM.
2.  **Integrate Brand Voice:** Connect the `brand_voice_description` from the Brand Kit to the Analyst prompt to ensure brand consistency.
3.  **Increase Transparency:** In "auto" mode, display the strategic choices (tone, CTA, etc.) the Analyst made, giving users insight into the AI's decisions.
4.  **Evolve User Controls:** Introduce "Caption Recipes" or "Flavor Profiles" that bundle settings for common social media goals, simplifying the user experience while offering more powerful control.

## 2. Analysis of Current Implementation

### 2.1. Architecture and Data Flow

The captioning process is a two-stage pipeline:

1.  **Analyst Stage:** A strategist LLM receives a large context bundle, including marketing strategy, visual context, and user-defined `CaptionSettings` (like tone). Its goal is to produce a strategic `CaptionBrief` (a JSON object).
2.  **Writer Stage:** A creative copywriter LLM receives *only* the `CaptionBrief` and writes the final caption based on its contents.

The data flow for the tone/voice setting is as follows:
`User Selection (e.g., "Witty & Playful")` -> `CaptionSettings.tone` -> `Analyst Prompt` -> **Analyst LLM** -> `CaptionBrief.target_emotion` -> `Writer Prompt` -> **Writer LLM** -> `Final Caption`

### 2.2. Root Cause of Identified Issues

#### Finding 1: Lossy Tone Transmission (Primary Issue)

The user's primary feedback is that changing the caption tone has minimal effect. The root cause is in the data flow:

-   The user's selected `tone` (e.g., "Witty & Playful") is passed to the Analyst.
-   The Analyst is instructed to generate a `CaptionBrief`, which contains a field called `target_emotion`.
-   The `tone` is not a field in the `CaptionBrief`. The nuance of "Witty" is lost when it's distilled into a generic emotion like "Happy" or "Engaging."
-   The Writer LLM never sees the original "Witty & Playful" instruction; it only sees `target_emotion: "Engaging"`.

This information bottleneck is the single biggest reason for the lack of distinctiveness in generated captions.

#### Finding 2: Brand Voice Is Ignored

The `PipelineForm` allows a user to define a `brand_voice_description` as part of a Brand Kit. However, this information is never passed to or used by the `caption.py` stage. This is a missed opportunity for generating on-brand copy and a disconnect in the user experience.

#### Finding 3: Auto-Mode is a "Black Box"

When the user doesn't specify any settings (auto-mode), the Analyst correctly infers the best settings. However, the user is never told what choices the AI made. They don't know if the Analyst chose a "Friendly" tone or a "Professional" one, making it difficult to adjust or regenerate with purpose.

## 3. Proposed High-Impact Improvements

These improvements are tiered, starting with the most critical fixes.

### Tier 1: Foundational Fixes (Highest Impact)

These two changes will directly address the user's reported issues and dramatically improve caption quality and consistency.

#### 1.1. Enhance `CaptionBrief` & Fix Data Flow

**Action:** Modify the system to pass the tone instruction directly to the Writer.

1.  **Modify `CaptionBrief` Model:** Add a new field, `tone_of_voice: str`.
2.  **Update Analyst Prompt (`_get_analyst_system_prompt`):**
    -   Instruct the Analyst to populate the new `tone_of_voice` field.
    -   If the user provides a tone, the Analyst MUST pass it through verbatim.
    -   In auto-mode, the Analyst should infer the best tone and populate the field with its choice (e.g., "Friendly & approachable").
3.  **Update Writer Prompt (`_get_writer_system_prompt`):**
    -   Make the `tone_of_voice` from the brief a **critical, non-negotiable instruction**.
    -   Example prompt change: *"**CRITICAL TONE OF VOICE:** You MUST adopt the following tone: **{brief.tone_of_voice}**. This is the most important instruction."*

#### 1.2. Integrate Brand Kit's Brand Voice

**Action:** Ensure the user-defined brand voice is used during caption generation.

1.  **Update Analyst Prompt (`_get_analyst_user_prompt`):**
    -   If `ctx.brand_kit` and `ctx.brand_kit.get('brand_voice_description')` exist, add it to the Analyst's context.
    -   Example prompt addition: `**Brand Voice Guidelines:** "{ctx.brand_kit.get('brand_voice_description')}"`
2.  **Update Analyst System Prompt:**
    -   Instruct the Analyst that if `Brand Voice Guidelines` are provided, they are a primary source of truth for inferring the tone in auto-mode.

### Tier 2: User Experience & Quality Enhancements

#### 2.1. Make Auto-Mode Transparent

**Action:** Show the user what settings the Analyst inferred.

-   **Modify `CaptionResult`:** Add a field to store the inferred settings (or reuse `settings_used` more effectively).
-   **Frontend Change:** In the `CaptionDisplay` component, when a caption was generated on auto, display the choices made by the AI (e.g., "Auto-Generated (Tone: Friendly, CTA: 'Learn More')"). This empowers the user to make more informed regeneration requests.

#### 2.2. More Expressive Tone Controls

**Action:** Move beyond a fixed list of tones to a more user-centric model.

-   **Leverage Brand Kits:** With the fix from 1.2, the Brand Kit's voice description becomes the primary method of control.
-   **Frontend Enhancement:** Allow users to easily create, save, and select from multiple Brand Kits (each with its own voice description) directly from the `PipelineForm`. This makes the "tone" selection a more robust "brand profile" selection.

### Tier 3: Advanced Features (Future Vision)

#### 3.1. Introduce "Caption Recipes"

**Action:** Bundle settings into goal-oriented presets.

-   Instead of asking the user to individually select tone, CTA, and hashtag strategy, offer "Recipes" like:
    -   **Viral Hook:** (Witty tone, question-based CTA, broad/trending hashtags)
    -   **Educational Snippet:** (Professional tone, "Learn More" CTA, niche hashtags)
    -   **SEO Powerhouse:** (Keyword-driven tone, no CTA, keyword-focused hashtags)

#### 3.2. Interactive/Conversational Regeneration

**Action:** Allow for more natural regeneration feedback.

-   Instead of just opening the settings dialog again, provide a simple text input where the user can type "make it funnier" or "be more direct."
-   This would trigger a simplified, single-stage LLM call that takes the previous caption and the new instruction to refine the text.

## 4. Addressing the "Default Settings" Question

> **User Question:** for default setting, should we allow the analyst layer in @caption.py to decide the settings (voice/tone, cta, emoji usage, hastag strategy instead?

**Answer:** **Yes, absolutely.** The current design, where the Analyst acts as a strategist in "auto mode," is a powerful and correct architecture. It leverages the LLM's reasoning capabilities to make context-aware decisions based on the provided marketing goals and visual information.

The problem is not *that* the Analyst is making these decisions, but that its decisions are not being communicated with high fidelity to the Writer. The improvements outlined in **Tier 1** directly fix this communication breakdown without changing the fundamental (and correct) architectural decision. By strengthening the `CaptionBrief`, we empower the Analyst to be a better strategist and the Writer to be a better creative. 

## 5. Clarifications on Key Concepts

### 5.1. How Auto-Mode Works with Marketing Goals

In "auto-mode," the Analyst LLM uses the `marketing_goals` from the Strategy stage as its primary input for making creative and strategic decisions.

-   **Tone/Voice:** The `marketing_voice` (e.g., "Playful, casual") is the primary driver for the caption's tone. It is often synthesized with visual context (like `lighting_and_mood`) for a more nuanced result.
-   **Call to Action (CTA):** The `target_objective` is the main factor determining the CTA. An objective to "Drive Sales" results in a direct CTA, while an objective to "Build Community" results in an engagement-focused CTA.
-   **Hashtags & SEO:** The `target_niche` and `target_audience` are used to generate relevant, effective hashtags and keywords.

### 5.2. `tone_of_voice` vs. `target_emotion`

The proposal to add `tone_of_voice` does not make `target_emotion` redundant. They serve distinct, complementary purposes:

-   **`tone_of_voice`**: This is an instruction for the **writer's personality**. It dictates *how* the caption should be written (e.g., "Witty," "Professional," "Empathetic"). It is the *input* for the writer's style.
-   **`target_emotion`**: This is the desired **emotional outcome for the reader**. It dictates how you want the audience to *feel* after reading (e.g., "Aspirational," "Trustworthy," "Excited"). It is the strategic *output* of the caption.

By specifying both, we provide a more complete brief. For example: "Write in a **witty tone** to make the reader feel **excited**." This is a far more powerful instruction than either directive alone. 

## 6. Implementation Plan

This plan details the steps required to implement the Tier 1 foundational fixes and the Tier 2 transparency enhancement.

### Part 1: Enhance `CaptionBrief` & Fix Tone Data Flow

This part ensures the user-selected or auto-inferred tone is passed directly and with high fidelity to the final Writer LLM.

#### Step 1.1: Modify `CaptionBrief` Model

The `CaptionBrief` model must be updated to include the new field.

-   **File:** `churns/models/__init__.py`
-   **Action:** Add the `tone_of_voice: str` field to the `CaptionBrief` Pydantic model, positioned after `target_emotion`.

```python
# In churns/models/__init__.py -> class CaptionBrief(BaseModel):
# ... existing fields ...
    target_emotion: str = Field(description="Primary emotion to evoke (e.g., 'Aspirational', 'Trustworthy')")
    tone_of_voice: str = Field(description="The specific tone of voice the writer must adopt (e.g., 'Witty & Playful', 'Professional & Polished'). This is a direct instruction.")
# ... existing fields ...
```

#### Step 1.2: Update Analyst System Prompt

-   **File:** `churns/stages/caption.py`
-   **Function:** `_get_analyst_system_prompt()`
-   **Action:** Modify the prompt to include and prioritize the new `tone_of_voice` field.

-   **Change 1: Update Auto Mode Logic.**
    -   **Remove:**
        ```
        - Auto-Tone Selection: Infer optimal tone by synthesizing target_voice from marketing strategy and lighting_and_mood from visual concept.
        ```
    -   **Add:**
        ```
        - **Auto-Tone Selection:** Infer the optimal `tone_of_voice`. Prioritize the `brand_voice_description` if available. Otherwise, synthesize `target_voice` from the marketing strategy and `lighting_and_mood` from the visual concept. The result should be a descriptive string like "Friendly and approachable" or "Witty and slightly sarcastic."
        ```
-   **Change 2: Update JSON Structure.**
    -   In the `CRITICAL JSON STRUCTURE REQUIREMENTS` JSON blob:
    -   **Add** the following field after `target_emotion`:
        ```json
          "tone_of_voice": "The specific tone the writer must adopt. If a user provided a tone, use it verbatim. In auto-mode, state your inferred tone (e.g., 'Witty & Playful').",
        ```

#### Step 1.3: Update Writer System Prompt

-   **File:** `churns/stages/caption.py`
-   **Function:** `_get_writer_system_prompt()`
-   **Action:** Add a critical, non-negotiable instruction to adopt the specified tone.

-   **Change 1: Add Critical Instructions.**
    -   In the `**Instructions:**` section, after the `Language Adherence` bullet point, **add** the following two bullet points:
        ```
        - **CRITICAL TONE OF VOICE:** You MUST adopt the following tone: **{{brief.tone_of_voice}}**. This is the most important instruction and is non-negotiable.
        - **CRITICAL STRUCTURE:** You MUST strictly adhere to the `caption_structure` and `style_notes` provided in the `platform_optimizations` section of the brief. This structure is key to the caption's success on that specific platform.
        ```
    -   **Remove** the original `CRITICAL:` instruction about structure from lower down in the prompt to avoid redundancy.

#### Step 1.4: Update Writer User Prompt

-   **File:** `churns/stages/caption.py`
-   **Function:** `_get_writer_user_prompt()`
-   **Action:** Add the `tone_of_voice` to the prompt parts so the LLM can see the value.

```python
# In _get_writer_user_prompt, modify the prompt_parts list:

prompt_parts = [
    "Write a social media caption based on this strategic brief:",
    "",
    f"**Core Message:** {brief.core_message}"
]
# ...
# After the Core Message, add:
prompt_parts.append(f"**Tone of Voice:** {brief.tone_of_voice}")
# ...
```

### Part 2: Integrate Brand Kit Voice

This part ensures the `brand_voice_description` is used as a primary input for the Analyst in auto-mode.

#### Step 2.1: Update Analyst User Prompt

-   **File:** `churns/stages/caption.py`
-   **Function:** `_get_analyst_user_prompt()`
-   **Action:** Prepend logic to the prompt construction to inject the `brand_voice_description` if it exists in the context.

```python
# In _get_analyst_user_prompt, before the prompt_parts list is initialized:

# Extract Brand Kit voice if available
brand_voice = None
if hasattr(ctx, 'brand_kit') and ctx.brand_kit:
    brand_voice = ctx.brand_kit.get('brand_voice_description')

prompt_parts = []
if brand_voice:
    prompt_parts.extend([
        "**Brand Voice Guidelines:**",
        f'"{brand_voice}"',
        ""
    ])
# ... the rest of the original prompt_parts list construction follows.
```

#### Step 2.2: Update Analyst User Prompt to Reflect Tone Hierarchy

-   **File:** `churns/stages/caption.py`
-   **Function:** `_get_analyst_user_prompt()`
-   **Action:** Modify the logic that handles `settings.tone` to correctly implement the full priority hierarchy in auto-mode. This change affects the `**User Settings:**` section of the prompt (lines ~404-413).

-   **Change 1: Update Tone Handling Logic.**
    -   **Find:** The `if settings.tone:` block and its corresponding `else` clause.
    -   **Replace** the entire block with the following more precise logic:
        ```python
        # Handle user settings vs auto mode for Caption Tone
        if settings.tone:
            prompt_parts.append(f"- Caption Tone: {settings.tone} (USER OVERRIDE)")
        else:
            # Auto mode hierarchy
            if strategy_data['target_voice']:
                prompt_parts.append(f"- Caption Tone: Auto mode - infer from the tactical 'Marketing Voice' provided for this specific run: '{strategy_data['target_voice']}'")
            elif brand_voice:
                prompt_parts.append(f"- Caption Tone: Auto mode - infer from the global 'Brand Voice' provided in the brand kit: '{brand_voice}'")
            else:
                prompt_parts.append("- Caption Tone: Auto mode - no specific voice provided, use a generally friendly and engaging tone.")
        ```

### Part 3: Increase Auto-Mode Transparency

This part implements the "Increase Transparency" enhancement, showing the user the settings the AI inferred in auto-mode.

#### Step 3.1: Backend - Populate `settings_used` in Auto-Mode

-   **File:** `churns/stages/caption.py`
-   **Function:** `run()`
-   **Action:** After the `brief` is generated by the Analyst, update the `settings` object with the inferred values before creating the final `CaptionResult`.

```python
# In the run() function, after the `brief` is successfully generated and before the Writer is called:

# If running in auto-mode, update the settings object with the Analyst's choices for transparency.
if not settings.tone and brief.tone_of_voice:
    settings.tone = brief.tone_of_voice
if not settings.call_to_action and brief.primary_call_to_action:
    settings.call_to_action = brief.primary_call_to_action
# This makes the auto-generated settings visible in the UI and pre-populates them for regeneration.
```

#### Step 3.2: Frontend - Enhance `CaptionDisplay`

-   **File:** `front_end/src/components/CaptionDisplay.tsx`
-   **Function:** `formatSettingsDisplay()`
-   **Action:** Modify the function to clearly label auto-generated settings.

-   **Change 1: Update formatting logic.**
    -   **Find:** The existing `formatSettingsDisplay` function.
    -   **Replace** its logic with the following to prepend "Auto:" to the settings string if the caption was generated without explicit user settings. We can detect this if the `initialSettings` prop was undefined during generation. A simple proxy for this is to check if the returned settings object has a tone.
        ```typescript
        const formatSettingsDisplay = (settings: CaptionSettings, wasAuto: boolean) => {
            const parts = [];
            if (settings.tone) parts.push(`Tone: ${settings.tone}`);
            if (settings.hashtag_strategy) parts.push(`Hashtags: ${settings.hashtag_strategy}`);
            if (settings.call_to_action) parts.push('Custom CTA');
            if (settings.include_emojis === false) parts.push('No Emojis');
            
            if (parts.length === 0) return 'Auto settings';

            const prefix = wasAuto ? 'Auto: ' : 'Custom: ';
            return prefix + parts.join(', ');
        };
        ```
    - This change may require passing a new prop `wasAuto` to the component, or inferring it from the state when the caption was generated. A simpler approach is to modify the logic to depend only on the `settings` object itself. Let's refine this: the backend change in 3.1 populates the settings regardless. The UI just needs to display them. The key is distinguishing a run where the user *chose* auto vs provided settings. The `brief_used` object can hold this clue. Let's simplify the frontend change.

-   **Refined Frontend Action:**
    -   No complex logic change is needed. The backend change from Step 3.1 will automatically populate `settings_used`. The existing `formatSettingsDisplay` function will then render these settings. The key benefit is that when a user clicks "Regenerate with new settings," the dialog will now correctly be pre-filled with the AI's previous choices, achieving the primary goal of transparency.

### Part 4: Validation and Testing

#### Step 4.1: Update Unit Tests

-   **File:** `churns/tests/test_caption_stage.py`
-   **Actions:**
    1.  Update the mock `CaptionBrief` object in tests to include a `tone_of_voice` field.
    2.  In `test_caption_settings_parsing`, assert that the `brief_used` in the final `CaptionResult` contains the expected `tone_of_voice`.
    3.  Create a new test, `test_brand_voice_integration_in_analyst_prompt`, to assert that when `ctx.brand_kit` contains a `brand_voice_description`, the prompt passed to the Analyst includes the "**Brand Voice Guidelines:**" section.
    4.  Create a new test, `test_auto_settings_population`, to verify that when `run` is called with empty `caption_settings`, the resulting `generated_captions[0]['settings_used']` is populated with values from the mock `brief`.

#### Step 4.2: Manual E2E Testing Plan

Perform the following manual tests through the UI:

1.  **User Override Test:** Select a "Witty" tone. Verify the caption is witty. Click regenerate and see "Witty" is pre-selected.
2.  **Brand Voice Test:** Set a "Sophisticated" brand voice. Clear other voices. Generate in auto-mode. Verify caption is sophisticated. Click regenerate and see "Sophisticated" is now pre-selected in the tone dropdown.
3.  **Transparency Test:** After the brand voice test, observe that the caption info area displays "Tone: Sophisticated...".
4.  **Fallback Test:** Clear all voices. Generate in auto-mode. Verify a "friendly and engaging" tone is used and displayed in the caption info area. 