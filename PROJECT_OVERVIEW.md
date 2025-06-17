# Churns – Project Overview

## Purpose
Churns is an AI-driven content-generation pipeline that helps food-and-beverage (F&B) brands quickly create social-media imagery (and accompanying copy) that is:

* On-brand and strategy-aligned
* Optimised for each target platform (Instagram, Pinterest, Facebook, Xiaohongshu, etc.)
* SEO-friendly and accessibility-compliant (mandatory alt-text)
* Ready for text-to-image diffusion models or human design teams

---

## Latest End-to-End Workflow (v2.1)
1. **Input Gathering** – User supplies campaign brief, style hints and optional reference images.
2. **Strategy & Style Generation**
   * *Marketing Strategist* stage proposes multiple audience-objective strategies.
   * *Style Guider* stage outputs matched style-guidance sets.
3. **Creative Expert** – Converts each strategy+style pair into a fully-structured `ImageGenerationPrompt` object containing detailed `VisualConceptDetails`.
   * Supports three creativity levels (Photorealistic ↔️ Abstract) with guardrails.
   * Generates mandatory, hashtag-free `suggested_alt_text` (100-125 chars).
   * Injects platform-specific rules (e.g. motion cues for IG Reels, bold text overlays for Pinterest Pins, authentic UGC aesthetic for Xiaohongshu).
4. **Image Generation** – Down-stream service consumes the prompt JSON to call a diffusion model (SDXL, DALLE-3, etc.).
5. **Frontend Review** – React + MUI UI lists variant options; the detail dialog shows marketing strategy, final prompt, alt-text (copy-button) and creative reasoning.
6. **Analytics & Iteration** – Token usage recorded per strategy; results stored in `PipelineContext` for A/B tests and cost tracking.

---

## Core Logic Highlights
* **Modular Pipeline** – Each stage in `churns/stages/` operates on a shared `PipelineContext` and can be unit-tested independently.
* **Pydantic Schemas** – Strong typing (`ImageGenerationPrompt`, `VisualConceptDetails`, `StyleGuidance`) guarantees structured outputs.
* **Instructor vs Manual JSON Parsing** – Detects whether to use OpenAI *instructor* tool-mode or robust regex extraction fallback.
* **Async Parallelism** – Strategies processed concurrently for speed.
* **Comprehensive Tests** – >19 unit tests cover edge-cases, error handling and SEO rules (alt-text no hashtags, length checks, etc.).

---

## Key Features Added in Latest Release
| Area | Feature |
| --- | --- |
| Accessibility & SEO | Mandatory alt-text, 100–125 chars, no hashtags/emojis |
| Platform Optimisation | Refined guidance for IG Reels, Pinterest Pins, Xiaohongshu Notes |
| Frontend UX | Alt-text shown in detail dialog with copy-to-clipboard button |
| Developer Tooling | Token usage tracking and improved mock LLM clients |

---

## Tech Stack (High Level)
* **Python 3.10+** backend
* **FastAPI** (API layer under `api/`)
* **Pydantic v2** for data models
* **OpenAI / Qwen** LLM clients (injected at runtime)
* **React + Material-UI** frontend (`front_end/`)
* **PyTest** for automated testing

---

## Roadmap (Excerpt)
* Automatic hashtag suggestions & trend integration
* Carousel (multi-image) post support
* Integrated analytics dashboard for generated asset performance
* Built-in A/B testing harness

---
**Status:** All enhancements deployed (December 2024). No breaking changes; production-ready for generating platform-optimised, SEO-compliant F&B social-media visuals. 