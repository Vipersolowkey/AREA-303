"""
#04 Customer Churn — Step 2: score churn risk with a local LLM.

Turns each user's compact signals into a Vietnamese behaviour summary and asks
the LLM for churn_risk (0..1) + top drivers + a retention action. No training.

Also computes a transparent rule-based risk (fast, no LLM) as a sanity baseline.

Exposes predict_churn(feature_row) for reuse.

Input : <feature>/outputs/users.parquet
Output: <feature>/outputs/scored.parquet
        <feature>/models/prompt_config.json
"""
from pathlib import Path
import sys
import json
import argparse
import time
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "common"))
from llm_client import chat_json, ping, CHAT_MODEL, map_concurrent, usage_report, reset_usage  # noqa: E402

OUT_DIR = ROOT / "outputs"
MODEL_DIR = ROOT / "models"; MODEL_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM = (
    "You are a customer-retention expert for a fashion & cosmetics e-commerce platform. "
    "From the customer's behaviour, estimate the CHURN RISK over the next 30-90 days. "
    "churn_risk is a probability 0..1. Name 2-3 key drivers and one concrete retention action. "
    "Always return JSON."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "churn_risk": {"type": "number"},
        "drivers": {"type": "array", "items": {"type": "string"}},
        "retention_action": {"type": "string"},
    },
    "required": ["churn_risk"],
}


def summarize(row) -> str:
    def g(k, default="?"):
        v = row.get(k)
        return default if v is None or (isinstance(v, float) and np.isnan(v)) else v
    parts = [
        f"Last purchase: {g('recency_days')} days ago",
        f"Orders placed: {g('frequency_orders')}",
        f"Average spend per order: {g('monetary_avg')}",
        f"Tenure: {g('tenure_months')} months",
        f"Sessions last month: {g('sessions_last_month')}",
        f"Cart-abandon rate: {g('cart_abandon_rate')}",
        f"Activity trend: {g('trend')}",
    ]
    return "; ".join(str(p) for p in parts)


def rule_risk(row) -> float:
    """Transparent baseline in [0,1] (no LLM)."""
    r = float(row.get("recency_days") or 0)
    f = float(row.get("frequency_orders") or 0)
    s = float(row.get("sessions_last_month") or 0)
    c = float(row.get("cart_abandon_rate") or 0)
    trend = row.get("trend", "stable")
    z = 0.012 * r - 0.15 * f - 0.08 * s + 2.2 * c
    z += 1.1 if trend == "declining" else (-0.9 if trend == "growing" else 0)
    z -= 1.6
    return float(1 / (1 + np.exp(-z)))


def score_one(row) -> dict:
    try:
        r = chat_json(f"Customer behaviour: {summarize(row)}", system=SYSTEM, schema=SCHEMA)
        risk = float(r.get("churn_risk", 0.5) or 0.5)
        return {"llm_risk": max(0.0, min(1.0, risk)),
                "drivers": "; ".join(r.get("drivers", []) or []),
                "retention_action": r.get("retention_action", "")}
    except Exception as e:  # noqa: BLE001
        return {"llm_risk": np.nan, "drivers": f"ERROR: {e}", "retention_action": ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-llm", type=int, default=200, help="users scored by the LLM (slower)")
    args = ap.parse_args()
    if not ping():
        raise SystemExit("LLM backend not reachable.")

    df = pd.read_parquet(OUT_DIR / "users.parquet")
    df["rule_risk"] = df.apply(rule_risk, axis=1)          # baseline over ALL users

    sub = df.head(args.n_llm).copy()
    print(f"LLM-scoring {len(sub)} users with {CHAT_MODEL} (concurrent) ...")
    reset_usage()
    t0 = time.time()
    row_list = [row for _, row in sub.iterrows()]
    rows = map_concurrent(
        row_list, score_one,
        on_progress=lambda d, n: print(f"  {d}/{n}") if (d % 50 == 0 or d == n) else None)
    print(f"Done in {time.time()-t0:.1f}s | usage: {usage_report()}")
    llm = pd.DataFrame(rows, index=sub.index)
    for col in llm.columns:
        df.loc[sub.index, col] = llm[col]

    out = OUT_DIR / "scored.parquet"
    df.to_parquet(out, index=False)
    print(f"Saved -> {out.relative_to(ROOT)}")
    with open(MODEL_DIR / "prompt_config.json", "w", encoding="utf-8") as f:
        json.dump({"approach": "ollama-llm-scoring-zero-training", "model": CHAT_MODEL,
                   "task": "customer-churn-risk", "system_prompt": SYSTEM, "schema": SCHEMA},
                  f, ensure_ascii=False, indent=2)


def predict_churn(feature_row: dict) -> dict:
    """Score one user. Returns {'proba', 'drivers', 'retention_action', 'rule_risk'}."""
    res = score_one(feature_row)
    return {"proba": res["llm_risk"], "drivers": res["drivers"],
            "retention_action": res["retention_action"], "rule_risk": rule_risk(feature_row)}


if __name__ == "__main__":
    main()
