# #01 — Review Sentiment (LLM, no training)

Classify English product-review sentiment (positive / neutral / negative) so
sellers see how customers feel. Instead of training a classifier, an LLM
classifies few-shot; we **evaluate** against rating-derived labels.

- **Approach:** few-shot prompt → structured JSON. The "model" is the LLM + prompt
  in [`models/prompt_config.json`](models/prompt_config.json). No trained weights.
- **Data:** `dataset/by_idea/idea_01_review_sentiment/fake_reviews_clean.parquet`
  (English product reviews, 40,526 rows). Ground-truth sentiment from rating:
  1–2 → negative, 3 → neutral, 4–5 → positive. Balanced sample.
- **Backend:** OpenAI `gpt-4o-mini` (default via `../.env`) or Ollama `qwen2.5:7b`.

## Run
```bash
python review_sentiment/src/01_prepare.py --per-class 400
python review_sentiment/src/02_classify.py        # concurrent + cached
python review_sentiment/src/03_evaluate.py
```

## Results (gpt-4o-mini, 1200 reviews)
| metric | value |
|---|---|
| Accuracy | 0.591 |
| Macro-F1 | 0.596 |

Per-class F1 = negative 0.617 / neutral 0.557 / positive 0.614. `neutral` is the
hard class (rating=3 ground truth is noisy vs. the text); the **neutral-calibrated**
prompt (chosen via `code/ab_prompts.py`) lifted neutral recall **0.61 → 0.71** at
this scale with no loss to overall macro-F1. See
[`outputs/classification_report.txt`](outputs/classification_report.txt) and `figures/`.

## Serve
`03_evaluate.predict_sentiment(text) -> {'sentiment', 'reason'}`
