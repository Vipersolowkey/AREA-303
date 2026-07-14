# #05 — Fake / Computer-Generated Review Detection (LLM, no training)

Flag fake / computer-generated reviews to keep the review system trustworthy. An
LLM classifies each English review (genuine vs fake) from the text plus metadata
(rating, category). No training.

- **Data:** `dataset/by_idea/idea_05_fake_review/fake_reviews_clean.parquet`
  (Salminen et al., English; `is_fake` 0 = genuine, 1 = computer-generated). Balanced sample.
- **Backend:** OpenAI `gpt-4o-mini` (default) or Ollama `qwen2.5:7b`.

## Run
```bash
python fake_review/src/01_prepare.py --per-class 500
python fake_review/src/02_classify.py        # concurrent + cached
python fake_review/src/03_evaluate.py
```

## Results (gpt-4o-mini, 1000 reviews)
| metric | value |
|---|---|
| Accuracy | 0.767 |
| Macro-F1 | 0.766 |

Balanced at scale: fake recall 0.844, genuine recall 0.690. (An earlier 0.64
genuine-recall reading was small-sample noise on 250 reviews.) A/B testing a
"genuine-first" prompt (`code/ab_prompts.py`) traded fake recall away for genuine
recall and lowered macro-F1, so the balanced prompt is kept. See
[`outputs/classification_report.txt`](outputs/classification_report.txt),
`figures/confusion_matrix.png`, `figures/pr_curve.png`.

## Serve
`03_evaluate.predict_fake(text, meta={'rating','category'}) -> {...}`
