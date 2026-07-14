"""
#04 Customer Churn — Step 1: build a compact behavioural summary per user.

LLM-based, no training: instead of a trained classifier we distil each user's
behaviour into a few interpretable RFM-style signals, which the LLM then scores.

Data:
  - If rees46_churn_clean.parquet is present (Kaggle), map its 276 engineered
    features down to the compact signals below and use target_event as the label.
  - Otherwise generate a SYNTHETIC cohort with realistic churn signal, so the
    pipeline runs end-to-end today. (Clearly flagged as synthetic.)

Compact signals: recency_days, frequency_orders, monetary_avg, tenure_months,
sessions_last_month, cart_abandon_rate, trend (declining/stable/growing).

Output: <feature>/outputs/users.parquet  (signals + label + `source`)
"""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
RANDOM_STATE = 42
OUT_DIR = ROOT / "outputs"; OUT_DIR.mkdir(parents=True, exist_ok=True)
CHURN_DIR = REPO / "dataset" / "by_idea" / "idea_04_customer_churn"
REES46 = CHURN_DIR / "rees46_churn_clean.parquet"              # Kaggle 276-col table (optional)
REES46_EVENTS = CHURN_DIR / "rees46_events_churn.parquet"      # real, free (derived from HF events)


def _first_col(df, *needles):
    for c in df.columns:
        lc = c.lower()
        if all(n in lc for n in needles):
            return c
    return None


def from_rees46(n: int) -> pd.DataFrame:
    df = pd.read_parquet(REES46)
    if len(df) > n:
        df = df.sample(n, random_state=RANDOM_STATE)
    rec = _first_col(df, "recency")
    freq = _first_col(df, "purchase_count", "sum") or _first_col(df, "purchase", "sum") or _first_col(df, "purchase")
    mon = _first_col(df, "revenue", "mean") or _first_col(df, "revenue")
    sess = _first_col(df, "session") or _first_col(df, "view_count", "sum")
    cart = _first_col(df, "cart")
    out = pd.DataFrame({
        "recency_days": pd.to_numeric(df[rec], errors="coerce") if rec else np.nan,
        "frequency_orders": pd.to_numeric(df[freq], errors="coerce") if freq else np.nan,
        "monetary_avg": pd.to_numeric(df[mon], errors="coerce") if mon else np.nan,
        "sessions_last_month": pd.to_numeric(df[sess], errors="coerce") if sess else np.nan,
        "cart_abandon_rate": pd.to_numeric(df[cart], errors="coerce") if cart else np.nan,
        "tenure_months": np.nan,
        "trend": "stable",
        "label": pd.to_numeric(df["target_event"], errors="coerce").astype("Int64"),
    })
    out["source"] = "rees46"
    return out.reset_index(drop=True)


def synthetic(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_STATE)
    recency = rng.gamma(2.0, 30, n).clip(0, 400)          # days since last order
    frequency = rng.poisson(6, n).clip(0, 60)
    monetary = rng.gamma(2.0, 25, n).clip(1, 500)
    tenure = rng.integers(1, 48, n)
    sessions = rng.poisson(8, n).clip(0, 60)
    cart_ab = rng.beta(2, 3, n)
    trend = rng.choice(["declining", "stable", "growing"], n, p=[0.35, 0.4, 0.25])

    # churn propensity: high recency, low frequency/sessions, declining trend, high abandon
    z = (0.012 * recency - 0.15 * frequency - 0.08 * sessions + 2.2 * cart_ab
         + np.where(trend == "declining", 1.1, 0) - np.where(trend == "growing", 0.9, 0)
         - 1.6 + rng.normal(0, 0.6, n))
    p = 1 / (1 + np.exp(-z))
    label = (rng.random(n) < p).astype(int)

    return pd.DataFrame({
        "recency_days": recency.round(0), "frequency_orders": frequency,
        "monetary_avg": monetary.round(1), "tenure_months": tenure,
        "sessions_last_month": sessions, "cart_abandon_rate": cart_ab.round(3),
        "trend": trend, "label": label, "source": "synthetic",
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1500)
    args = ap.parse_args()

    if REES46.exists():
        print(f"Using real REES46 churn table (Kaggle): {REES46.relative_to(REPO)}")
        df = from_rees46(args.n)
    elif REES46_EVENTS.exists():
        print(f"Using real REES46 churn derived from events: {REES46_EVENTS.relative_to(REPO)}")
        df = pd.read_parquet(REES46_EVENTS)
        if len(df) > args.n:
            df = df.sample(args.n, random_state=RANDOM_STATE).reset_index(drop=True)
    else:
        print("No real churn data -> generating SYNTHETIC cohort (flagged). "
              "Get real data via `python code/download_clean_ideas.py churn_events` (free).")
        df = synthetic(args.n)

    df = df.dropna(subset=["label"]).reset_index(drop=True)
    print(f"Users: {len(df)} | churn rate: {df.label.mean():.3f} | source: {df.source.iloc[0]}")
    out = OUT_DIR / "users.parquet"
    df.to_parquet(out, index=False)
    print(f"Saved -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
