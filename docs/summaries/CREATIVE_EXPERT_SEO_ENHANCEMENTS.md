# Recommendations for SEO Enhancement of `creative_expert.py`

## Introduction

This document outlines recommended enhancements for the `churns/stages/creative_expert.py` script. The goal is to more deeply integrate key social media imagery SEO techniques from the provided guide into the visual concept generation process.

The existing script provides a strong, platform-aware foundation. The following suggestions aim to build upon it by making the generated concepts even more potent for organic discovery and engagement, without altering the core logic of the pipeline.

---

## 1. Universal Enhancements

### 1.1. Generate SEO-Friendly Alt Text

**SEO Rationale:** The guide identifies alt text as a "direct and powerful SEO tool" for both accessibility and algorithmic understanding. Since the script generates a complete description of the visual, it is perfectly positioned to also create a concise, keyword-rich alt text suggestion.

**Proposed Implementation:**

1.  **Modify Pydantic Model:** In `churns/models.py`, add a new optional field to the `VisualConceptDetails` class:
    ```python
    # In churns/models.py, within VisualConceptDetails class
    suggested_alt_text: Optional[str] = None
    ```

2.  **Update System Prompt:** In `creative_expert.py`, amend the `_get_creative_expert_system_prompt` function to include instructions for filling this new field. This could be added to the `reasoning_ce` section.
    ```python
    # In _get_creative_expert_system_prompt, before the adherence_ce section
    
    alt_text_ce = """
**Alt Text Generation:** Based on the final visual concept, you MUST generate a concise, descriptive alt text (100-125 characters) in the `suggested_alt_text` field. This text is crucial for SEO and accessibility. It should clearly describe the image's subject, setting, and any important actions or text, naturally incorporating primary keywords from the marketing strategy.
"""
    # ... then add alt_text_ce to the prompt_parts_ce list
    prompt_parts_ce = [
        base_persona_ce, input_refinement_ce, core_task_ce, task_type_awareness_ce,
        creativity_instruction_ce, image_ref_handling_ce, text_branding_field_instruction_ce,
        reasoning_ce, alt_text_ce, adherence_ce
    ]
    ```
3.  **Update Final Instruction:** In `_get_creative_expert_user_prompt`, add a bullet point to the `final_instruction` string to remind the model to generate the alt text.
    ```python
    # In _get_creative_expert_user_prompt, within final_instruction
    # ...
    # - Provide a brief `creative_reasoning` ...
    - **Generate a concise and descriptive `suggested_alt_text` for SEO and accessibility.**

    Ensure the overall visual concept...
    # ...
    ```

---

## 2. Platform-Specific Enhancements

The following changes should be made to the `platform_guidance_map` dictionary within the `_get_creative_expert_user_prompt` function in `creative_expert.py`.

### 2.1. Enhance Instagram Reels/Video Concepts

**SEO Rationale:** The guide notes that Instagram's algorithm prioritizes Reels. The script can be enhanced to generate concepts that feel more dynamic and video-native, even if they are for a single image prompt.

**Proposed Implementation:**

-   **Modify `platform_guidance_map["Instagram Story/Reel"]`:**
    -   **Current:** `"Optimize for Instagram Story/Reel: Focus on dynamic, attention-grabbing visuals for {aspect_ratio_for_prompt} vertical format. Consider bold text, trendy effects, or concepts suitable for short video loops or interactive elements."`
    -   **Proposed:** `"Optimize for Instagram Story/Reel: Focus on dynamic, attention-grabbing visuals for {aspect_ratio_for_prompt} vertical format. **Describe the visual as if it were a single, high-impact frame from a video Reel.** Incorporate a sense of motion or action in the `composition_and_framing` description (e.g., 'dynamic motion blur,' 'subject captured mid-action,' 'cinematic freeze-frame effect')."`

### 2.2. Add Specific Text Overlay Guidance for Pinterest

**SEO Rationale:** The guide highlights that for Pinterest, a "text overlay...is a critical ranking factor" and it must be "large, legible (avoid script fonts), and contain your primary keyword."

**Proposed Implementation:**

-   **Modify `platform_guidance_map["Pinterest Pin"]`:**
    -   **Current:** `"Optimize for Pinterest: Create visually striking, informative vertical images in {aspect_ratio_for_prompt} format. Focus on aesthetics, clear subject matter, and potential for text overlays that add value."`
    -   **Proposed:** `"Optimize for Pinterest: Create visually striking, informative vertical images in {aspect_ratio_for_prompt} format. **If text is enabled, the concept MUST include a prominent text overlay.** As per Pinterest best practices, the description in `promotional_text_visuals` should specify text that is **large, highly legible (e.g., bold sans-serif fonts), and contains primary keywords from the marketing strategy.**"`

### 2.3. Strengthen Xiaohongshu (XHS) Guidance

**SEO Rationale:** The guide provides several key insights for XHS: the cover image text is a critical hook, an authentic UGC style is preferred over polished ads, and featuring real people increases engagement.

**Proposed Implementation:**

-   **Modify `platform_guidance_map["Xiaohongshu (Red Note)"]`:**
    -   **Current:** `"Optimize for Xiaohongshu: Focus on authentic, aesthetically pleasing, informative, and often lifestyle-oriented visuals in {aspect_ratio_for_prompt} vertical format. Use high-quality imagery, potentially with integrated text overlays in a blog-post style."`
    -   **Proposed (Combined Enhancement):** `"Optimize for Xiaohongshu: Focus on an **authentic, User-Generated Content (UGC) aesthetic** in {aspect_ratio_for_prompt} format. The concept should resemble a high-quality photo from a peer, not a polished ad. When describing the `visual_style`, favor terms like 'natural lighting' or 'candid shot.' **The concept should feature real people** interacting with the product or in the scene. If text is enabled, the `promotional_text_visuals` description must detail a **catchy, keyword-rich title overlay to act as a strong hook.**"`

---

## 3. Future Consideration: Carousel Post Generation

**Rationale:** The guide notes carousel posts are highly effective on XHS for detailed storytelling.

**Recommendation:** As a future, more advanced enhancement, the `_generate_visual_concept_for_strategy` function could be adapted to optionally generate a sequence of 2-3 related concepts for a carousel post. This would likely involve changing the function's return signature and adding logic to create a cohesive narrative or step-by-step guide across multiple `ImageGenerationPrompt` objects. This would provide significant value for platforms where multi-image posts are common. 