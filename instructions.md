# Churns – Prototype Web-App Plan

> This document describes how to turn the existing **`combined_pipeline.py`** Colab notebook into a lightweight, modular web application suitable for local testing and rapid feature experiments.  
> Non-essential concerns such as user authentication, multi-tenant RBAC, or cloud-scale observability are deferred until a later phase.

---
## 1 Objectives
1. Preserve all current logic, prompts and pricing tables – **byte-for-byte**.  
2. Replace ipywidgets with a modern web form while keeping the staged-output experience.  
3. Split the monolith into independent *pipeline stages* so new features can be added by simply dropping a Python module into a folder.  
4. Provide a one-command local run via **Docker Compose**.

---
## 2 Minimal Architecture
```
  Next.js (React) form  ◄──────────────►  FastAPI server
         │  JSON POST /runs                    │
         ▼  WebSocket /runs/{id}/stream        ▼
      Browser shows live steps        In-process pipeline executor
                                                 │
                                                 ▼
                                   OpenAI / VLM HTTP APIs
```
* **Front-end** — small Next.js app with Material-UI; just one page to collect inputs and another to stream results.  
* **FastAPI** — receives the run request, stores input image locally, then launches the pipeline **in a background thread** (no Celery for now).  
* **Storage** — local `./data/` directory holds uploaded images, generated images, and JSON run manifests.  
* **Metadata** — a lightweight SQLite file (`runs.db`) tracks each run and stage; powered by SQLModel.

> NOTE: Switching to Celery/Rabbit, S3, or Postgres later will only require swapping the helper modules—nothing in stage logic will change.

---
## 3 Repo Layout
```
churns/
├── api/           # FastAPI routers & schemas
├── models/        # ➜ ALL Pydantic models (copied verbatim)
├── stages/        # One file per pipeline stage
├── pipeline/
│   ├── context.py # Holds the big nested dict
│   └── executor.py# Runs the ordered stage list
├── data/          # Images & JSON outputs (git-ignored)
├── configs/
│   ├── prompts/   # Raw YAML prompt texts (unchanged)
│   └── stage_order.yml
├── tests/
└── docker-compose.yml
front_end/         # Next.js project (optional separate repo)
```

---
## 4 Initial Pipeline Stages
| Order | Module                | Purpose |
|-------|-----------------------|---------|
| 1     | `image_eval.py`       | Vision-LLM subject analysis |
| 2     | `strategy.py`         | Generate marketing goals |
| 3     | `style_guide.py`      | Suggest visual style set |
| 4     | `creative_expert.py`  | Produce detailed concept JSON |
| 5     | `prompt_assembly.py`  | Build final prompt string |
| 6     | `image_generation.py` | Call DALL-E or image-edit API |

Each stage exposes:
```python
def run(ctx: PipelineContext) -> None:
    """Mutates ctx.data and appends log entries."""
```
The order is defined by **`configs/stage_order.yml`**, so inserting a new stage later is one line of YAML.

---
## 5 Front-end Form Fields (1:1 with ipywidgets)
* Platform (dropdown)  
* Task type (dropdown)  
* Prompt (textarea)  
* Image upload + preview  
* Image instruction (textarea)  
* Toggles: render_text, apply_branding  
* Creativity level (slider 1-3)  
* Optional marketing goals (audience, niche, objective, voice)  

Validation mirrors the original `validate_inputs()` rules in Python.

---
## 6 Local Development
1. `docker compose up`  
   * service **api** – FastAPI + Uvicorn  
   * service **front** – Next.js dev server (port 3000)  
2. Open `http://localhost:3000`, fill in the form, submit, and watch live stage updates.

---
## 7 Testing
* **pytest** unit tests per stage with OpenAI mocked.  
* A parity test loads canned inputs, runs both the *legacy* notebook code and the *new* pipeline, and asserts the final JSONs are identical.  
* A hash test ensures prompt YAML files equal the originals.

---
## 8 Migration Steps
1. **Scaffold repo** with above layout; add lint/format hooks.  
2. **Copy models & helper utils** unchanged.  
3. For each logical section inside `run_full_pipeline()` copy code into its own stage file (minimal edits: replace `print` with `ctx.log()`).  
4. Implement `executor.run()` that loops through the YAML list and calls each stage.  
5. Build FastAPI endpoints and WebSocket streamer.  
6. Create the simple Next.js form and viewer.  
7. Run parity tests and adjust until outputs match.  

---
## 9 Done-Definition (Prototype)
* One-command Docker run works on Mac/Windows/Linux.  
* User can complete a run end-to-end and view images & JSON.  
* Adding a new stage file + YAML entry executes automatically.  
* Original prompt strings remain unmodified (parity test green).  

---
Happy hacking!  ✨ 