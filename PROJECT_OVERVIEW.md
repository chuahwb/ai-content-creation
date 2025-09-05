# Churns: An AI-Powered Creative Content Engine

## 1. Executive Summary & Vision

**Churns** is not just an application; it's an **AI-powered creative engine** designed to function as a highly scalable, on-demand digital marketing team. It transforms simple user inputs—a text prompt, a product image, a marketing goal—into polished, ready-to-deploy social media assets, complete with high-quality visuals, platform-optimized captions, and strategic branding.

Our core innovation is a **modular, multi-stage AI pipeline** that deconstructs the complex creative process into a series of logical, machine-executable steps. By breaking down tasks like "visual analysis," "strategy," "art direction," and "copywriting" into discrete AI-driven stages, Churns achieves a level of control, consistency, and quality that is impossible with single-prompt approaches.

This document provides a comprehensive technical and functional overview of the Churns engine, detailing the sophisticated mechanisms that drive its creative output. It is intended for both **technical stakeholders** seeking to understand its architecture and **investors** looking to grasp its significant market potential.

## 2. The Core Generation Pipeline: A Deep Dive

The heart of Churns is a six-stage pipeline that mimics the workflow of a creative agency. Each stage is an independent Python module that performs a specific task, feeding its structured output to the next stage in the chain.

---

### **Stage 1: Image Evaluation (The Visual Analyst)**

This stage acts as the pipeline's "eyes," performing a deep analysis of the user's optional reference image.

*   **Mechanism**: It uses a Vision-Language Model (VLM), such as GPT-4 Vision, to analyze the image content. The prompt sent to the VLM is **dynamically constructed**: if the user provides specific instructions (e.g., "use the burger as the main subject"), the prompt asks for a detailed analysis of all visual elements. If not, it requests a minimal analysis, identifying only the `main_subject`.
*   **Sophistication**: The stage is highly resilient. It features a robust, multi-pass JSON parser to handle malformed LLM responses and a fallback simulation that generates a plausible analysis if the VLM call fails. This ensures the pipeline never crashes due to API or parsing errors at this critical first step.
*   **Output**: A structured `ImageAnalysisResult` object containing the main subject, secondary elements, setting, and style.

---

### **Stage 2: Strategy Generation (The Marketing Strategist)**

This stage develops the core marketing angle for the creative asset. It uses a sophisticated two-phase LLM process to ensure strategic depth.

*   **Mechanism**:
    1.  **Niche Identification**: First, an LLM call identifies several relevant F&B market niches based on the visual analysis and user inputs.
    2.  **Goal Combination**: Second, the identified niches and any user-provided goals are fed into another LLM. The prompt for this second call is incredibly detailed, instructing the model to generate diverse combinations of `target_audience`, `target_objective`, and `target_voice`. It has specific logic for handling cases where the user provides complete, partial, or no goals.
*   **Sophistication**: This two-step process prevents the model from generating generic ideas. By first grounding the task in a specific niche, the subsequent creative output is far more targeted and relevant.
*   **Output**: A list of `MarketingGoalSetFinal` objects, each representing a unique, complete marketing strategy.

---

### **Stage 3: Style Guidance (The Art Director)**

This stage translates the abstract marketing strategies into concrete, actionable visual directives.

*   **Mechanism**: For each marketing strategy, this stage calls an LLM with a system prompt that changes dramatically based on the user's selected `creativity_level`. It explicitly commands the model to generate a `StyleGuidance` object containing keywords, a detailed description, and an explanation of the style's `marketing_impact`.
*   **Sophistication**: The dynamic prompt is the key. Level 1 enforces photorealism, Level 2 encourages stylized visuals, and Level 3 pushes for abstract concepts. The prompt also explicitly instructs the model to avoid clichés and draw inspiration from diverse aesthetic sources (e.g., historical art movements, cultural motifs), ensuring a wide range of creative outputs.
*   **Output**: A list of `StyleGuidance` objects, one for each marketing strategy.

---

### **Stage 4: Creative Expert (The Master Synthesizer)**

This is the most complex and critical stage, where all prior context is fused into a final, detailed blueprint for the image.

*   **Mechanism**: This stage synthesizes the marketing strategy, style guide, user inputs, and platform requirements into a single, highly-structured `ImageGenerationPrompt` object. The system prompt is a masterpiece of dynamic engineering, changing based on over seven context variables (creativity, task type, language, presence of a reference image, etc.).
*   **Sophistication**:
    *   **Platform Optimization**: It contains expert-level instructions for optimizing visuals for Instagram, Pinterest, and even Xiaohongshu, tailoring the concept to what works best on each platform.
    *   **Creative Constraints**: For high creativity, it provides specific, actionable constraints (e.g., "use a monochromatic color scheme," "frame as a graphic novel panel") to force novel outputs.
    *   **Intelligent Image Handling**: It has nuanced logic for handling reference images. If the user provides an instruction, it creatively modifies the original; if not, it preserves the main subject and redesigns only the surrounding context.
*   **Output**: A list of `ImageGenerationPrompt` objects, ready for final assembly.

---

### **Stage 5: Prompt Assembly (The Translator)**

This stage flattens the rich, structured `ImageGenerationPrompt` into a final string that the image model can understand.

*   **Mechanism**: A simple but context-aware function, `assemble_final_prompt`, concatenates the fields of the visual concept into a coherent paragraph.
*   **Sophistication**: It operates in three distinct modes: **Full Generation** (for new images), **Instructed Edit** (for images with user instructions), and **Default Edit** (for images without instructions, where it preserves the subject and only modifies the context). This ensures the final instruction is perfectly tailored to the creative task.
*   **Output**: A list of final, ready-to-use prompt strings.

---

### **Stage 6: Image Generation (The Final Executor)**

The final stage executes the assembled prompts to produce the visual assets.

*   **Mechanism**: It calls the OpenAI Images API, intelligently selecting the `generate` or `edit` endpoint based on the presence of a reference image.
*   **Sophistication**: It runs all image generations in parallel using `asyncio.gather`, dramatically speeding up the process. It also features robust I/O handling for saving the generated images and comprehensive error handling for API or network failures.
*   **Output**: A list of paths to the final, generated image files.

---

### **Stage 7: Image Assessment (Optional Quality Control)**

Although not enabled in the default run, Churns ships with a seventh, optional stage that acts as an in-house QA engineer.

* **Mechanism**: The `image_assessment` module feeds each generated image—and its prompt metadata—into a specialised LLM rubric that scores **aesthetics, brand fit, and relevance**. The result is a structured JSON report.
* **Usage**: When enabled (via YAML or API flag) the executor surfaces the scores in real-time, allowing downstream logic to auto-select the *best* variant or flag low-quality outputs for refinement.
* **Outcome**: A measurable feedback loop that prevents sub-par assets from reaching the user and dramatically reduces manual review time.

---

## 3. Advanced Features & Capabilities

Beyond the core generation flow, Churns includes several advanced features that enhance its power and usability.

### **Feature: Two-Phase Caption Generation**

Similar to the main pipeline, captioning is a two-step process that mimics an expert marketing team:

1.  **The Analyst LLM**: A "strategist" LLM first creates a structured `CaptionBrief`. It analyzes all available context to define the core message, SEO keywords, target emotion, and, crucially, a **platform-specific structure** (e.g., "Hook + Value + CTA" for Instagram).
2.  **The Writer LLM**: A "creative copywriter" LLM then receives this brief with a non-negotiable instruction: execute the brief flawlessly. This ensures the final caption is not only well-written but also perfectly aligned with the strategic goals for that platform.

### **Feature: "One-Click" Refinement Flows**

Churns includes "refinement" pipelines that allow users to fix or alter generated images with a single click. These are conditional stages that run instead of the main pipeline.

*   **Subject Repair**: If an image's subject is flawed, this stage automatically retrieves the *original* reference image and uses a specialized prompt to re-run the `images.edit` API, commanding it to replace the subject while preserving the background and style.
*   **Text Repair & Prompt Refinement**: Similar flows exist to fix garbled text or to allow users to slightly tweak the original prompt and regenerate the image, making iteration fast and intuitive.

### **Feature: Cost-and-Usage Transparency**

Every LLM call—across all stages—is intercepted by `token_cost_manager.py`.

* Tracks **prompt / completion / cached tokens**
* Calculates **input, output, and total USD cost** per call
* Persists a per-run cost ledger that feeds the UI and future billing integrations

### **Feature: Run History & Analytics**

All inputs, stage outputs, timing, and cost data are stored in a **SQLModel** database. The front-end “History” tab queries this data to provide:

* Full audit trail of past runs
* Search & filter by date, platform, cost, or success status
* Future-proof foundation for usage analytics dashboards

### **Feature: Platform & Language Localisation**

* **Aspect-Ratio Mapping**: The selected `platform_name` (e.g. *Instagram Story 9:16*) propagates through `prompt_assembly` and `image_generation`, guaranteeing correct canvas sizes.
* **Language Control**: A two-letter ISO-639-1 code forces captions and on-image text into the desired language while keeping technical style descriptors in English for LLM comprehension.

### **Feature: Robust Error-Handling & Fallbacks**

* Multi-pass JSON extraction (`RobustJSONParser`) salvages malformed LLM responses.
* Simulated outputs keep the pipeline running in API-key-free dev environments.
* Truncated responses trigger automatic retries with higher token limits.

### **Feature: Plug-and-Play Extensibility**

Developers can add capabilities in minutes:
1. Drop `my_new_stage.py` with an async `run(ctx)` into `churns/stages/`.
2. Reference it in `configs/stage_order.yml` *(or add a new execution mode entry).*  
3. Restart—no further wiring needed thanks to runtime discovery and dependency injection.

This architecture future-proofs Churns for rapid feature expansion—think *Hashtag Optimiser*, *Brand Sentiment Checker*, or *AR Filter Generator*—without touching core code.

## 4. The Investor & Developer Proposition

*   **For Investors**: Churns represents a scalable, automated solution to the massive and ever-growing demand for high-quality digital marketing content. By productizing the expertise of an entire creative team into a predictable, machine-driven workflow, it offers a powerful and defensible position in the generative AI market. The modular architecture and detailed cost tracking (`token_cost_manager.py`) provide a clear path to commercialization and profitability.

*   **For Developers**: The architecture is a model of modern software engineering. The modular `stages/` directory, the central `PipelineExecutor`, and the use of dependency injection make the system highly extensible. Adding a new stage (e.g., a "Hashtag Generator" or a "Brand Voice Analyzer") is as simple as adding a new Python file and updating a YAML config. This makes for a clean, maintainable, and enjoyable development experience. 