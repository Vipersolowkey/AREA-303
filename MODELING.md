# AREA 303 — Modeling (features #01–#05)

Modeling layer on top of the data foundation. Focus: **small/medium sellers of
clothing & cosmetics** on an **English** marketplace. Built **LLM-first, no model
training** — features call the OpenAI API (default) or a local Ollama model for
inference; labelled data is used for **evaluation**, not fitting.

Each feature is a self-contained top-level folder (mirrors `customer_segmentation`
/ #13): `src/01_*.py 02_*.py 03_*.py` + `models/ figures/ outputs/` + `README.md`.

**Demo:** `python demo.py` runs all five serve helpers on example inputs (clothing +
cosmetics). **Dashboard:** `python code/build_dashboard.py` → `dashboard.html`
(self-contained results summary with embedded figures). **Prompt A/B:**
`python code/ab_prompts.py` compares prompt variants at scale (cheap thanks to the
cache) — used to pick #01's neutral-calibrated prompt.

Numbers are at scale (#01: 1200 reviews, #05: 1000) — larger, firmer estimates than
early small-sample runs.

## Features (all English, gpt-4o-mini)

| # | Folder | Approach | Data | Headline result |
|---|---|---|---|---|
| 01 | [`review_sentiment/`](review_sentiment/) | few-shot LLM sentiment | fake_reviews (EN) ✅ | acc 0.591 / macro-F1 0.596 (1200) |
| 05 | [`fake_review/`](fake_review/) | few-shot LLM fake detection | fake_reviews (EN) ✅ | acc 0.767 / macro-F1 0.766 (1000) |
| 02 | [`dynamic_pricing/`](dynamic_pricing/) | embed comps + LLM price reasoning | asos (EN) ✅ | MAPE 12.5% LLM vs 25.8% baseline |
| 03 | [`personal_shopper/`](personal_shopper/) | RAG (embed retrieve + LLM) | asos + cosmetics (EN) ✅ | known-item recall@5 0.987 |
| 04 | [`customer_churn/`](customer_churn/) | LLM risk scoring | REES46 events (EN) ✅ | AUC 0.775 / F1 0.718 |

## LLM backend

All features import `common/llm_client.py` — one API, two backends, switched
by `.env` (copy from `.env.example`):

- **OpenAI** (primary): `gpt-4o-mini` + `text-embedding-3-small`, ~1–2 s/call.
  Set `OPENAI_API_KEY` in `.env`. Full runs of all five features cost well under ~$1.
- **Ollama** (optional local fallback): `qwen2.5:7b` + `bge-m3`. CPU-only here
  ≈ 15–20 s/call — usable for small batches. Set `LLM_BACKEND=ollama`.

The client (`common/llm_client.py`) also provides:
- **On-disk cache** (`.cache/llm/`, `LLM_CACHE=1`): identical calls are served from
  disk — re-runs are instant and free, and results are reproducible.
- **Concurrency** (`map_concurrent`, `LLM_WORKERS=8`): batch evals run threaded —
  e.g. #05's 250 reviews drop from ~5.5 min to ~50 s (~7×).
- **429/Retry-After backoff** and **token+cost tracking** (`usage_report()`), printed
  after each classify run.

## Setup

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt -r requirements-ml.txt
cp .env.example .env      # then set OPENAI_API_KEY (LLM_BACKEND=openai is the default)
# optional local fallback: install Ollama, `ollama pull qwen2.5:7b && ollama pull bge-m3`, set LLM_BACKEND=ollama
```

## Data status

`code/download_clean_ideas.py` reproduces each idea's `*_clean.parquet`:

- **Free (HuggingFace, done):** `fake_reviews` (English → #01, #05), `asos`
  (clothing → #02, #03), `makeup` (cosmetics → #02, #03), `churn_events`
  (REES46 event logs → #04 real churn labels).
- **Kaggle (need `~/.kaggle/kaggle.json`), optional:** `tiki` / `sephora` / `shopee`
  / `utkarshx27` / `churn` (276-col table) if you later want those catalogs.

```bash
python code/download_clean_ideas.py                 # all free sources
python code/download_clean_ideas.py churn_events    # real churn data (free, ~245MB)
```

All five features now run on free English data. Kaggle sources are optional extras.

## Not in this layer
UI / API server; model training / fine-tuning; ideas #06–#17; live crawling.
