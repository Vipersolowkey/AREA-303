# #02 — Dynamic Pricing (retrieval + LLM, no training)

Recommend a selling price for a product. Instead of a trained regressor, we
**retrieve** comparable products by embedding similarity and reason about their
prices — a comps-median statistical anchor plus an LLM adjustment.

- **Approach:** embed catalog (bge-m3 / text-embedding-3-small) → retrieve top-K
  comps → `recommended_price` = comps median (baseline) refined by the LLM given
  the product's attributes.
- **Data:** ASOS clothing catalog (English, GBP), 30k products. Currency is
  auto-detected; the code also loads a Tiki catalog if one is present (never mixes currencies).
- **Backend:** OpenAI (default) or Ollama — set in `../.env`.

## Run
```bash
python dynamic_pricing/src/01_build_index.py --max-rows 6000   # embed comps
python dynamic_pricing/src/03_evaluate.py --n-baseline 1500 --n-llm 40
```

## Results (ASOS catalog, GBP, k=10)
| method | MAE | MAPE |
|---|---|---|
| comps-median baseline (n=1500) | 11.7 | 25.8% |
| LLM-reasoned gpt-4o-mini (n=40) | 4.9 | 12.5% |

The LLM roughly halves the error of the pure statistical anchor. See
[`outputs/pricing_report.txt`](outputs/pricing_report.txt),
`figures/pred_vs_actual.png`, `figures/mape_by_category.png`.

## Serve
`02_recommend.recommend_price(sku_features, k=10) -> {recommended_price, low, high, confidence, rationale, comps}`

## Notes
Any catalog with `name / category / brand / price` works. A Tiki catalog (with a
`quantity_sold` demand signal) is auto-detected if downloaded via
`python code/download_clean_ideas.py tiki`.
