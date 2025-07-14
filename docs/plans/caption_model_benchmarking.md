# Caption Model Benchmarking Plan

## 1  Objective
Provide a repeatable framework to **benchmark caption quality** across any number of LLM providers/models while keeping the existing code-base changes minimal.

## 2  High-Level Strategy
1. **Parameterise model selection** – treat `CAPTION_MODEL_PROVIDER` and `CAPTION_MODEL_ID` as *inputs* rather than constants during testing.
2. **Fixed evaluation corpus** – run each model against the **same deterministic inputs** (marketing strategy, visual concept, image analysis) to ensure comparability.
3. **Automated quality metrics** – score generated captions with objective metrics (e.g. *BERTScore*, *ROUGE-L*, readability) + rule-based sanity checks.
4. **Cost / latency tracking** – record tokens, latency, and cost alongside quality to understand trade-offs.
5. **Single pytest entry-point** – one command executes the full matrix of models and outputs a CSV / Markdown report.

## 3  Implementation Steps

### 3.1 Test Configuration
```yaml
# tests/caption_model_matrix.yml
- provider: OpenRouter
  model_id: openai/gpt-4o-mini
- provider: OpenAI
  model_id: gpt-4o
- provider: Groq
  model_id: llama3-70b-8192
- provider: Anthropic
  model_id: claude-3-sonnet-20240229
```
*Add/remove rows to expand the benchmark set.*

### 3.2 Env / Monkeypatch Helper
```python
# tests/conftest.py
import os, yaml, contextlib, importlib
import pytest

@pytest.fixture(scope="session")
def model_matrix():
    with open("tests/caption_model_matrix.yml") as f:
        return yaml.safe_load(f)

@contextlib.contextmanager
def patch_caption_constants(provider, model_id):
    from churns.core import constants as C
    # Hot-reload ensures every stage picks up the override
    original_provider, original_id = C.CAPTION_MODEL_PROVIDER, C.CAPTION_MODEL_ID
    C.CAPTION_MODEL_PROVIDER, C.CAPTION_MODEL_ID = provider, model_id
    importlib.reload(C)
    try:
        yield
    finally:
        C.CAPTION_MODEL_PROVIDER, C.CAPTION_MODEL_ID = original_provider, original_id
        importlib.reload(C)
```

### 3.3 Benchmark Test (parametrised)
```python
# tests/test_caption_models.py
import time, pytest, json, csv
from churns.stages import caption as caption_stage
from churns.pipeline.context import PipelineContext
from .conftest import patch_caption_constants

TEST_INPUT = json.load(open("tests/fixtures/caption_input.json"))  # fixed data

@pytest.mark.parametrize("entry", [pytest.param(e, id=e["model_id"]) for e in model_matrix()])
def test_caption_quality(entry, model_matrix, benchmark):
    with patch_caption_constants(entry["provider"], entry["model_id"]):
        ctx = PipelineContext(**TEST_INPUT)
        start = time.perf_counter()
        benchmark(asyncio.run, caption_stage.run(ctx))
        latency = time.perf_counter() - start

    caption = ctx.generated_captions[0]["text"]
    score = bert_score(caption, TEST_INPUT["reference_caption"])  # custom helper
    record_result(entry, score, latency, ctx.llm_usage)
    assert score > 0.85, f"Caption quality below threshold for {entry['model_id']}"
```

### 3.4 Metrics & Reporting
* **Quality**: BERTScore (`bert-score` package) against human-written reference, ROUGE-L as secondary.
* **Readability**: Flesch-Kincaid grade (`textstat`).
* **Compliance**: Regex checks – CTA present, `#` hashtags count, emoji usage aligns with settings.
* **Cost**: Derive USD cost via `MODEL_PRICING` already in `constants.py`.
*Results are appended to `benchmark_results.csv` which is summarised into a Markdown table at the end of the run.*

### 3.5 Running the Benchmark
```bash
pytest -q tests/test_caption_models.py --benchmark-only
```
The suite will iterate over every model in `caption_model_matrix.yml`, generate captions, compute metrics, and write a report `benchmark_results.md`.

## 4  Alternative Approaches
1. **OpenAI Evals** – plug the stage into the [OpenAI Evals](https://github.com/openai/evals) framework for more advanced metrics and crowd-sourced human evaluation.
2. **LangSmith Traces** – stream each model run to LangSmith for UI-driven qualitative comparison.
3. **Manual Review UI** – store captions in a database and surface a simple web page where reviewers blind-rank outputs (better subjective quality signal).

## 5  Future Enhancements
- **Caching layer** with `diskcache` to avoid re-calling identical prompts.
- **Prompt perturbations**: diversify inputs (different niches, tones) and aggregate scores for robustness.
- **Statistical testing**: use paired t-tests or bootstrap CI to declare significant differences.

---
**Outcome:** a reproducible, data-driven benchmark that measures each LLM's caption quality, speed, and cost, enabling informed model selection without modifying production code. 