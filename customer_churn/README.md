# #04 — Customer Churn (LLM risk scoring, no training)

Estimate which customers are likely to churn so the team can retain them. Instead
of a trained classifier, we distil each user's behaviour into interpretable
RFM-style signals and have the **LLM** score churn risk + name the drivers +
propose a retention action.

- **Signals:** recency, frequency, tenure, sessions, cart-abandon rate, trend.
- **Data:** **real REES46 event logs** (free, HuggingFace) → churn label = inactivity
  in the last-30-day holdout window; 48k users, ~38% churn. Fetch with
  `python code/download_clean_ideas.py churn_events`. (A synthetic cohort is used
  only if no real data is present; the Kaggle 276-col table is also supported.)
- **Backend:** OpenAI (default) or Ollama — set in `../.env`.

## Run
```bash
python code/download_clean_ideas.py churn_events     # real data (free, ~245MB events)
python customer_churn/src/01_prepare.py --n 1500
python customer_churn/src/02_score.py --n-llm 200
python customer_churn/src/03_evaluate.py
```

## Results (real REES46 events, churn rate 0.389)
| scorer | AUC | F1@0.5 |
|---|---|---|
| rule baseline (all 1500) | 0.572 | 0.131 |
| LLM gpt-4o-mini (200) | 0.775 | 0.718 |

The LLM generalizes to real behaviour and clearly beats the transparent rule (which
was tuned on synthetic assumptions). See
[`outputs/churn_report.txt`](outputs/churn_report.txt), `figures/roc_curve.png`,
`figures/risk_calibration.png`.

## Serve
`02_score.predict_churn(feature_row) -> {'proba', 'drivers', 'retention_action', 'rule_risk'}`
