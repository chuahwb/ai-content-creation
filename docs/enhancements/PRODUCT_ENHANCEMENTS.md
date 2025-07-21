# Proposed Enhancements for **Churns**

---

## Priority Matrix

| Rank | Enhancement | Category |
|------|-------------|----------|
| 1    | Brand Presets & Style Memory | **Must-Have** |
| 2    | Interactive Visual Editor & In-painting | **Must-Have** |
| 3    | Multi-Image Story / Carousel Generation | **Must-Have** |
| 4    | Cost-Optimized Model Auto-Selection | **Must-Have** |
| 5    | Smart A/B Variant Selector | **Must-Have** |
| 6    | One-Click Social Publish & Scheduler | Good-to-Have |
| 7    | Automated Video Reel Synthesis | Good-to-Have |
| 8    | Integrated Analytics Dashboard | Good-to-Have |

*“Must-Have” items deliver immediate user value, reduce friction/cost, or unlock critical content formats. “Good-to-Have” items are valuable but can follow once the core UX is polished and robust.*

---

## 1. Smart A/B Variant Selector

### High-Level Value
* **Problem** – Users manually review multiple image variants, which is subjective and time-consuming.
* **Benefit** – Automatically surfaces the highest-performing variant, accelerating decision-making and improving perceived output quality.

### User Persona Impact
* **Solo founders / small teams** – Saves time; narrows focus to the best option.
* **Agencies** – Provides data-backed justification to clients.

### ROI vs Effort
* **ROI** – High; every run with ≥2 variants benefits.
* **Effort** – Medium; limited ML scope and re-uses stored run data.

### Potential Risks & Mitigations
* **Cold-start** – Use heuristic scorer (CLIP similarity to brand style) until historical data accrues.
* **Model drift** – Retrain weekly on new engagement feedback.

### Low-Level Implementation
1. **New Stage:** `variant_ranker.py` (insert after `image_generation`).
2. **Feature Extraction:**
   * Vision embeddings (e.g. CLIP) + prompt text tokens.
   * Optional meta-data (creativity level, niche).
3. **Model:** LightGBM or shallow NN trained on historical run-engagement pairs.
4. **Output:** JSON list of variant scores → `ctx.variant_scores` (also persisted).
5. **UI:** Display “Recommended” badge & auto-sort.
6. **Tests:** PyTest with synthetic embeddings ⇒ assert deterministic ranking.

---

## 2. One-Click Social Publish & Scheduler

### High-Level Value
* **Problem** – Manual download & posting breaks workflow and causes drop-off.
* **Benefit** – Seamless “Generate → Schedule/Publish” pipeline; boosts retention and positions Churns as an end-to-end solution.

### User Persona Impact
* **SMB owners** – Reduces tech overhead; one tool instead of three.
* **Content managers** – Enables calendar-driven campaigns directly from Churns.

### ROI vs Effort
* **ROI** – High engagement uplift but depends on API maintenance.
* **Effort** – High; OAuth, rate-limit handling, queue infra.

### Potential Risks & Mitigations
* **API deprecations** – Abstract each connector behind an adapter interface.
* **Posting failures** – Use retry + fallback email notification.

### Low-Level Implementation
1. **OAuth Connectors:** Instagram, Facebook, Pinterest (expandable).
2. **Backend Router:** `api/publish.py` – endpoints: `/auth`, `/post`, `/schedule`.
3. **Queue:** Redis + Celery (reuse existing Redis) – worker posts at scheduled time.
4. **Frontend:** `PublishDialog` with calendar picker + status toast.
5. **Tests:** Mock API responses (VCR) + e2e Cypress test for schedule flow.

---

## 3. Brand Presets & Style Memory

### High-Level Value
* **Problem** – Repeat users re-enter brand data every run.
* **Benefit** – One-click brand consistency; drastically reduces friction.

### User Persona Impact
* **E-commerce brands** – Guarantees consistent voice & colors.
* **Agencies** – Saves setup time for multiple clients.

### ROI vs Effort
* **ROI** – Immediate UX uplift; encourages repeat usage.
* **Effort** – Low-medium; mostly CRUD & context merge.

### Potential Risks & Mitigations
* **Preset sprawl** – Add owner + last-used timestamps for cleanup.

### Low-Level Implementation
1. **DB Table:** `BrandPreset(id, user_id, name, colors, voice, logo_path, default_settings)`.
2. **CRUD API:** `/brand-presets` (GET/POST/PUT/DELETE).
3. **Form Integration:** Dropdown to load preset → auto-populate fields.
4. **Executor Hook:** Merge preset into `PipelineContext` before Stage 1.
5. **Tests:** SQLModel CRUD + React autofill unit tests.

---

## 4. Cost-Optimized Model Auto-Selection

### High-Level Value
* **Problem** – Users lack visibility into cost/quality trade-offs.
* **Benefit** – Transparent budgeting; prevents bill shock and aligns output quality with spend tolerance.

### User Persona Impact
* **Bootstrapped startups** – Control burn rate.
* **Enterprises** – Toggle “premium” for flagship campaigns.

### ROI vs Effort
* **ROI** – Medium-high; cost control is key for scaling.
* **Effort** – Medium; primarily config mapping + UI toggle.

### Potential Risks & Mitigations
* **Model unavailability** – Fallback to next best tier automatically.

### Low-Level Implementation
1. **Config Enum:** `ModelTier = {budget, balanced, premium}`.
2. **Mapping YAML:** `model_tiers.yml` → stage → model ID per tier.
3. **Executor Logic:** Resolve model per stage at runtime.
4. **UI Toggle:** Radio switch in settings; show estimated cost.
5. **Tests:** Assert model IDs & snapshot cost calc.

---

## 5. Integrated Analytics Dashboard

### High-Level Value
* **Problem** – No consolidated view of usage, cost, or engagement.
* **Benefit** – Empowers power users & admins with data-driven insights; supports upsell.

### User Persona Impact
* **Admins** – Monitor usage & cost; spot power users.
* **Marketers** – Identify top-performing niches & strategies.

### ROI vs Effort
* **ROI** – Medium; useful for retention and upsell but not blocking core flow.
* **Effort** – Medium-high; front-end charting & aggregation queries.

### Potential Risks & Mitigations
* **Data volume** – Use materialized views & pagination.

### Low-Level Implementation
1. **Endpoint:** `/analytics/summary` – returns runs/day, success rate, avg cost, top niches, token spend.
2. **SQLModel Views:** Pre-aggregated for performance.
3. **Frontend Page:** `AnalyticsPage.tsx` with Recharts / Victory graphs.
4. **Auth:** Admin-only initially → user scoped later.
5. **Tests:** API contract + visual regression (Chromatic).

---

> All enhancements preserve Churns’ plug-and-play architecture: each new capability is either a discrete pipeline stage or an isolated service, ensuring minimal coupling and maximal extensibility. 

---

## 6. Multi-Image Story / Carousel Generation

### High-Level Value
* **Problem** – Modern social media relies on multi-image carousels to tell stories or showcase products from different angles. Churns currently only creates single, independent images.
* **Benefit** – Unlocks a critical and highly-demanded content format, elevating the tool from a "single asset generator" to a "micro-campaign generator."

### User Persona Impact
* **E-commerce brands** – Can generate a carousel showing a product in-context, its details, and a lifestyle shot, all in one run.
* **Content creators** – Can create visual narratives or step-by-step guides.

### ROI vs Effort
* **ROI** – Very High; directly meets a dominant need for platforms like Instagram & LinkedIn.
* **Effort** – Medium; requires modifying the `CreativeExpert` stage and the frontend results view.

### Potential Risks & Mitigations
* **Visual Inconsistency** – To ensure variants feel like a set, the prompt for image N+1 must include the visual description of image N for context.
* **Cost** – A carousel run will be 3-5x the cost of a single image; this must be made clear in the UI.

### Low-Level Implementation
1. **New Pipeline Mode:** Add a `carousel` mode to `stage_order.yml`.
2. **Executor Logic:** In `carousel` mode, the `CreativeExpert` stage is looped N times.
3. **Prompt Chaining:** The `user_prompt` for variant N+1 includes the final `visual_concept` from variant N, with an instruction like: "Now generate a complementary image that follows this one..."
4. **UI Update:** The `RunResults` component uses a carousel/slider library (e.g., `swiper.js`) to display the sequence of images.
5. **Tests:** A new integration test, `test_carousel_pipeline.py`, asserts that N images are generated and that their prompt data is chained correctly.

---

## 7. Automated Video Reel Synthesis

### High-Level Value
* **Problem** – Static images have lower engagement than short-form video. Users must take generated assets to another tool to create a video.
* **Benefit** – Caters directly to the market's dominant content format (Reels, TikToks, Shorts) and makes Churns a more complete, one-stop solution.

### User Persona Impact
* **All users** – Drastically reduces the effort to turn creative concepts into video content, a major "ease of life" improvement.

### ROI vs Effort
* **ROI** – High; taps into the largest growth area for social media content.
* **Effort** – Medium-High; depends on implementation choice (library vs. API).

### Potential Risks & Mitigations
* **Generic Animations** – Using a simple library like `moviepy` might produce bland results. Mitigation: offer several animation style templates (e.g., "fast cuts," "slow zoom").
* **API Cost/Latency** – Using a dedicated video generation API (e.g., RunwayML, Pika) will be more expensive and slower. Mitigation: Process as an async background task and notify the user via email upon completion.

### Low-Level Implementation
1. **New Stage:** `video_synthesis.py`, runs *after* `image_generation`.
2. **Implementation (Option A - Library):**
   * Use `moviepy` to sequence the generated images.
   * Apply simple animations (Ken Burns effect via cropping/zooming frames) and crossfades.
   * Add a royalty-free audio track from a pre-selected library.
3. **Implementation (Option B - API):**
   * Integrate with a video generation API.
   * Pass the generated images as keyframes and the prompt as a style guide.
4. **Frontend:** The `RunResults` page needs a video player component (`<video>`) to display the output MP4 file.
5. **Tests:** Unit test the `moviepy` script to ensure it generates a valid, non-empty video file given a set of input images.

---

## 8. Interactive Visual Editor & In-painting

### High-Level Value
* **Problem** – The current "one-click" refinement flows lack granular control. Users cannot fix a specific small area or add an element to a precise location.
* **Benefit** – Bridges the gap between a purely generative tool and a creative editing suite, giving users the final 10% of control they often need for a perfect result.

### User Persona Impact
* **Designers & Power Users** – Enables precise corrections (e.g., "remove the stray spoon," "change the color of the logo") that are currently impossible.

### ROI vs Effort
* **ROI** – High; significantly increases the "finish rate" of generated assets and user satisfaction.
* **Effort** – High; requires a complex frontend canvas component and a new backend API.

### Potential Risks & Mitigations
* **UI Complexity** – The editor must be kept simple and intuitive, not a full-blown Photoshop. Focus on just two tools: mask drawing and text/logo placement.
* **Cost** – Each edit is another API call. The UI must clearly display the cost of each refinement action.

### Low-Level Implementation
1. **Frontend Component:** A new `InteractiveEditor.tsx` built with a canvas library like `react-konva` or `fabric.js`.
   * Allows users to load a generated image.
   * A "brush" tool lets the user draw a mask, which is exported as a base64 PNG.
   * A text input provides the prompt for the masked area.
2. **New Backend API:** `/refine/interactive` endpoint.
   * Accepts the base image, the mask image (base64), and a text prompt.
3. **Pipeline Logic:** This API call bypasses the main pipeline and directly calls the `images.edit` function, supplying the `mask` parameter.
4. **UI Feedback:** The editor displays a loading spinner over the canvas while the API call is in progress and then replaces the image with the new version upon success.
5. **Tests:**
   * Frontend: Jest/RTL tests to ensure the canvas correctly exports a mask.
   * Backend: PyTest to ensure the API endpoint correctly calls the OpenAI client with the `mask` parameter. 