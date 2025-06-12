Phase-based Improvement Roadmap
================================

⚡ Purpose: Incrementally raise first-run image quality, reduce latency/cost, and surface richer controls—without breaking existing modular design.

Phase 1 — Quality Boost (Highest ROI, 1-2 days)
------------------------------------------------
1. Auto-Refinement Loop
   • New stage `image_rerank.py` ➜ generate 3 low-res images → GPT-Vision scores & selects best. If score < 7/10 set `needs_refinement`.
   • New stage `prompt_refiner.py` (conditional) ➜ turn critic feedback into "delta prompt", regenerate once in high-quality.
   • Outputs: `best_image`, `alt_images`, `critic_report` for UI.
2. Async/Parallel Execution
   • Convert serial loops in `creative_expert`, `image_generation`, and new rerank stages to `asyncio.gather()`.
   • Expect ≈ N× latency reduction for multi-strategy runs.

Phase 2 — Reliability & Cost (3-5 days)
---------------------------------------
1. Native Function Calling
   • Replace manual JSON extraction / Instructor fallbacks with OpenAI function-calling where supported → Zero parsing errors.
2. Local CLIP/BLIP Scoring (optional toggle)
   • Offer CPU-only OpenCLIP scorer as cheaper alternative to GPT-Vision for rerank.
3. Response Caching
   • SHA-256 hash prompts → SQLite table of LLM outputs; skip identical calls across runs/tests.

Phase 3 — UX / Developer Experience (1 week)
--------------------------------------------
1. Front-end Controls
   • Expose quality (`low|medium|high`), `n` (variants), and "auto-refine" toggle.
2. WebSocket Progress Events
   • Stream rerank scores, refinement steps, and final selection to the browser.
3. Unit-Test Expansion
   • `test_image_rerank.py`, `test_prompt_refiner.py`, `test_pipeline_integration.py` covering new flows.
4. Docs & Metrics
   • Update README, generate OpenAPI docs, and add simple `/metrics` endpoint for stage timings/cost.

Phase 4 — Stretch Goals (Backlog)
---------------------------------
• Advanced multi-modal caption generator stage.
• S3 / CDN image storage swap-in.
• Fine-grained cost dashboard with per-user budgeting.
• Plug-in system for 3rd-party stages.

Checklist
---------
☐ Design specs accepted  ☐ Stages implemented  ☐ Tests green  ☐ Frontend wired  ☐ Docs updated 

Prompt Optimisation Guide
=========================
Global, cross-stage tweaks
-------------------------
• Externalise raw prompt text to `configs/prompts/*.j2` templates → slimmer code, easier copy tweaks, hash-based regression tests.
• Prefer function-calling / JSON schema over manual extraction → near-zero parsing failures.
• Add two or three few-shot demonstrations per schema (stored in `prompt_examples.yml`).
• Insert an "assistant acknowledgment" stub ("Understood, will comply with schema…") before generation to boost compliance.

Stage-by-stage check-list
-------------------------
Image Eval
  – Supply one good vs bad example; trim duplicate exposition from the system prompt.
Strategy
  – Few-shot examples; explicit instruction not to invent pool items.
Style Guide
  – Split system vs user prompt; bullet template for `style_keywords`; dynamic `max_tokens` (900 + 300×N).
Creative Expert
  – Move big task-type map to Jinja include; compact markdown tables; rely on function calling; add short negative-prompt list.
Prompt Assembly
  – Store assembly strings as Jinja templates for localisation/testing.
Image Generation
  – Auto-prepend negative prompts; expose seed/style preset hooks.

Expected outcome
----------------
≈ 30-45 % fewer tokens per run, < 2 % JSON errors, and non-dev stakeholders can iterate on copy without Python changes. 