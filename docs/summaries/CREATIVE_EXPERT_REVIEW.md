# Creative Expert Stage – System Design Review

## 1. Clarifying Questions
1. **Deployment context** – Will the pipeline run as a long-lived service or invoked ad-hoc (e.g., CLI, serverless)?  Thread-safety and warm-start decisions depend on this.
2. **LLM provider mix** – Do you expect to swap providers/models per request or is the provider mostly static?  This impacts how clients should be cached/initialised.
3. **Prompt size constraints** – What is the maximum effective context length you observe for your target models?  Current prompts can exceed 8–10 K tokens.
4. **Reference-image usage patterns** – Roughly what % of calls include an image reference vs not?  This informs branching optimisation.
5. **Required latency per strategy** – Is sub-second per strategy a hard requirement or is several seconds acceptable?  Guides degree of batching/parallelism.
6. **Failure tolerance** – When one strategy generation fails, should the pipeline abort, retry, or continue with partial results?
7. **Down-stream consumer** – Does any component after this stage need the raw LLM answer or only the parsed `ImageGenerationPrompt` object?

---

## 2. Critique of Current Implementation
### 2.1 Architecture & Maintainability
• **Global mutable state** – `instructor_client_creative_expert`, `CREATIVE_EXPERT_MODEL_ID`, etc. make the module non-reentrant and complicate testing.
• **Monolithic prompt builders** – `_get_creative_expert_system_prompt` and `_get_creative_expert_user_prompt` embed >300 lines of string literals and branching logic, which is hard to unit-test and reason about.
• **Mixed responsibilities** – Functions build prompts, perform I/O with LLM, parse, validate, post-process, and log, violating SRP.
• **Hard-coded maps** – `task_type_guidance_map` and `platform_guidance_map` are inline; difficult to update externally or localise.

### 2.2 Redundancies & Inefficiencies
• **Repeated static blocks** – Large constant strings are rebuilt for every strategy; minor runtime but major token cost.
• **Token bloat** – System prompt repeats explanations already present in user prompt (e.g., style guidance elaboration), increasing cost and risk of context overflow.
• **Manual JSON extraction fallback** duplicates validation effort and still depends on brittle regex; could be avoided with more robust tool calling or explicit function-calling.
• **Temperature logic duplicated** – Temperature is set twice (default + creativity switch).
• **Inefficient error handling** – Traces are concatenated into strings and passed through LLM context logs, inflating memory.

### 2.3 Testing & Observability
• No dedicated unit tests for prompt builders or parsing helpers.
• Usage logging depends on provider-specific object attributes, risking attribute errors when providers change.

---

## 3. Recommendations for Improvement
### 3.1 Architectural Refactor
1. **Dependency Injection container** – Pass LLM clients and configuration through the `PipelineContext` or constructor, eliminating globals.
2. **Split concerns**
   • `PromptBuilder` – pure functions or classes returning structured dicts `{system, user}`.
   • `LLMClient` wrapper – handles retries, streaming, provider abstraction.
   • `Parser` – converts raw LLM output → pydantic model.
   • `CreativeExpertService` – orchestrates the above and exposes `generate(strategy, style)`.
3. **Externalise static data** – Move `task_type_guidance_map`, `platform_guidance_map`, and creativity templates to YAML/JSON + Jinja2 templates for easier editing & localisation.

### 3.2 Prompt Engineering Optimisation
• **Token de-duplication** – Place immutable, rarely-changing instruction blocks in the system prompt once; keep user prompt minimal (only dynamic fields).
• **Use function calling / JSON schema** when available: send the expected schema so the model returns structured JSON without regex extraction.
• **Template engine** – Adopt Jinja2 or faststring templates to compose prompts declaratively and unit-test fragments.

### 3.3 Performance & Cost
• **Memoise system prompt** per `(creativity_level, task_type, platform, flags)` to avoid rebuilding identical strings.
• **Batch strategies** if model supports parallel function calls to reduce round-trips.
• **Adaptive max_tokens** – Calculate expected answer length from enabled fields instead of static 5000.

### 3.4 Reliability
• **Typed contexts** – Replace raw dicts with pydantic BaseModels for `strategy`, `platform`, `image_reference` to catch errors early.
• **Centralised error handling & retry policy** – Exponential backoff for transient LLM errors before bubbling up.
• **Strict schema validation** – Keep using pydantic but remove regex extraction by leveraging tool/function calling.

### 3.5 Testing Strategy
• Unit tests: prompt builder ensures no placeholder tokens remain; length under limit.
• Property-based tests: random permutations of flags to ensure JSON validity.
• Integration tests: mock LLM, assert parsed output matches expectation.

### 3.6 Alternative Solutions
| Aspect | Current | Alternative |
|-------|---------|-------------|
| Prompt construction | Inline f-strings | Jinja2 templates with partials |
| Concurrency | `asyncio.gather` | Multiplex LLM API if provider supports batch messages |
| Parsing | Regex + pydantic | Provider function-calling mode or JSON mode |
| Config | Hard-coded dicts | External YAML + pydantic settings model |

---

## 4. Next Steps
1. Confirm answers to clarifying questions.
2. Introduce DI + template refactor behind feature flag to avoid breaking current pipeline.
3. Add unit tests for new prompt builder.
4. Benchmark token counts & latency before/after to quantify gains.

---

## 5. Prompt-Design Opportunities for Higher-Quality Visual Concepts
### 5.1 System Prompt
1. **Token economy** – Move lengthy explanations (e.g., *Input Refinement*, *Core Task* copy) into comments or external docs when using models that ignore comments, or reference them via a concise link-style placeholder: "{See: CoreTask}", reducing repetition across calls.
2. **Explicit schema / function-calling** – Provide the JSON schema via the `tools` (OpenAI) or *Qwen function call* feature so the model *must* return structured data—eliminates manual regex parsing.
3. **Few-shot exemplars** – Add 1–2 short, high-quality image-concept examples paired with the desired JSON output.  Examples anchor the model's style, tone, and level of detail better than verbose rules.
4. **Progressive constraints** – Present a high-level goal first, then incrementally add constraints (task-type, creativity, reference-image handling).  This staged approach tends to be better followed than a single large block.
5. **Dynamic creativity snippets** – Instead of three hard-coded creativity blocks, store modular templates keyed by `creativity_level` and inject only the selected one.
6. **Minimise duplication with user prompt** – Remove strategy field listings from the system prompt; they appear again in user prompt.  The system prompt should focus on *how* to think, the user prompt on *what* to use.

### 5.2 User Prompt
1. **Structured input block** – Supply dynamic data as a compact JSON blob instead of prose lists.  Models handle JSON context efficiently and it aligns with the requested output schema.
2. **Field-to-field mapping reminders** – Precede the JSON with a short mapping table ("Input key ➜ Output field") to help the model place data correctly.
3. **Inline few-shot** – After the JSON, include a minimal previous example of inputs ➜ outputs for the *same* task-type to prime task-specific style.
4. **Conditional sections** – Omit entire sections (e.g., *Branding*, *Text*) when disabled rather than adding lines that say they're disabled—saves tokens and reduces confusion.
5. **Reference-image delta description** – When an image reference exists with no instruction, pass only the *delta* to design ("Describe context around subject X…"), not the full default-edit explanation.
6. **Aspect-ratio normalisation** – Pass aspect ratio once as a numeric pair and reference it via placeholders elsewhere to avoid repetition.

### 5.3 Experimental Ideas
• **Chain-of-thought sandbox** – Use hidden `assistant` messages (`role=system`, name="internal_note") where allowed to let the model think privately before producing JSON, improving reasoning without polluting output.
• **Re-ranking** – Generate multiple candidate concepts (`n=3` completions) and let a lightweight classifier rank for brand-fit or novelty before returning best.
• **Auto-feedback loop** – After initial generation, run a secondary LLM call asking "Does this concept meet all instructions?"; if not, regenerate.

Implementing these prompt-engineering tweaks can reduce cost, improve adherence to schema, and yield more vivid, on-strategy visual concepts. 