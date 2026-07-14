"""
#02 Dynamic Pricing — Step 3: evaluate price recommendations.

Holds out real products and predicts their price from *other* products only
(self excluded), then compares to the actual price:
  - comps-median baseline (no LLM) over a larger set
  - LLM-reasoned price over a smaller subset (slower/costlier)

Metrics: MAE, MAPE. Figures: predicted-vs-actual, MAPE by category.

Input : <feature>/models/comps_index.npz, <feature>/outputs/catalog.parquet
Output: <feature>/outputs/pricing_report.txt
        <feature>/figures/pred_vs_actual.png, mape_by_category.png
"""
from pathlib import Path
import sys
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
import importlib.util
_spec = importlib.util.spec_from_file_location("rec02", ROOT / "src" / "02_recommend.py")
rec = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(rec)

OUT_DIR = ROOT / "outputs"
FIG_DIR = ROOT / "figures"; FIG_DIR.mkdir(parents=True, exist_ok=True)


def _mape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    m = a > 0
    return float(np.mean(np.abs((a[m] - p[m]) / a[m])) * 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-baseline", type=int, default=800, help="products for comps-median eval")
    ap.add_argument("--n-llm", type=int, default=60, help="products for LLM eval (slower)")
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    c = rec._load()
    vectors = c["vectors"]                       # (N, d), L2-normalised
    ids = c["ids"]                               # (N,) aligned to vectors
    currency = c["currency"]
    catalog = pd.read_parquet(OUT_DIR / "catalog.parquet")
    catalog["id"] = catalog["id"].astype(str)
    catalog = catalog.drop_duplicates("id").set_index("id")
    prices = catalog["price"].reindex(ids).to_numpy(float)
    cats = catalog["category"].reindex(ids).to_numpy()

    N = len(ids)
    n = min(args.n_baseline, N)
    rng = np.random.default_rng(7)
    test_pos = rng.choice(N, size=n, replace=False)
    print(f"Evaluating pricing on {n} products | currency={currency} | k={args.k}")

    # baseline comps-median — reuse precomputed vectors, NO re-embedding
    base_pred, base_actual, base_cat = [], [], []
    for pos in test_pos:
        sims = vectors @ vectors[pos]
        sims[pos] = -np.inf                      # exclude self
        top = np.argpartition(-sims, args.k)[:args.k]
        med = float(np.nanmedian(prices[top]))
        if np.isnan(med):
            continue
        base_pred.append(med); base_actual.append(prices[pos]); base_cat.append(cats[pos])
    base_pred, base_actual = np.array(base_pred), np.array(base_actual)
    base_mae = float(np.mean(np.abs(base_pred - base_actual)))
    base_mape = _mape(base_actual, base_pred)

    # LLM subset — full retrieval + reasoning (re-embeds the query; keep small)
    llm_positions = test_pos[:args.n_llm]
    llm_pred, llm_actual = [], []
    for i, pos in enumerate(llm_positions, 1):
        row = catalog.loc[ids[pos]]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        feats = {"id": ids[pos], "name": row["name"], "category": row["category"],
                 "brand": row.get("brand", ""), "current_price": float(row["price"])}
        out = rec.recommend_price(feats, k=args.k, use_llm=True)
        if "recommended_price" in out:
            llm_pred.append(out["recommended_price"]); llm_actual.append(float(row["price"]))
        if i % 20 == 0 or i == len(llm_positions):
            print(f"  LLM {i}/{len(llm_positions)}")
    llm_pred, llm_actual = np.array(llm_pred), np.array(llm_actual)
    llm_mae = float(np.mean(np.abs(llm_pred - llm_actual))) if len(llm_pred) else float("nan")
    llm_mape = _mape(llm_actual, llm_pred) if len(llm_pred) else float("nan")

    report = (
        f"#02 Dynamic Pricing — retrieval + LLM, zero-training\n"
        f"Currency: {currency} | comps k={args.k}\n"
        + "=" * 64 + "\n"
        f"Comps-median baseline (n={len(base_pred)}):  MAE={base_mae:,.1f}  MAPE={base_mape:.1f}%\n"
        f"LLM-reasoned ({rec.CHAT_MODEL}, n={len(llm_pred)}):  MAE={llm_mae:,.1f}  MAPE={llm_mape:.1f}%\n"
    )
    print("\n" + report)
    (OUT_DIR / "pricing_report.txt").write_text(report, encoding="utf-8")
    print("Saved ->", (OUT_DIR / "pricing_report.txt").relative_to(ROOT))

    # pred vs actual (baseline)
    fig, ax = plt.subplots(figsize=(5, 5))
    lim = np.percentile(base_actual, 99)
    ax.scatter(base_actual, base_pred, s=6, alpha=0.3, color="#0f766e")
    ax.plot([0, lim], [0, lim], "r--", lw=1)
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    ax.set_xlabel(f"Actual price ({currency})"); ax.set_ylabel("Predicted (comps-median)")
    ax.set_title(f"Predicted vs actual — MAPE {base_mape:.1f}%")
    fig.tight_layout(); fig.savefig(FIG_DIR / "pred_vs_actual.png", dpi=150); plt.close(fig)
    print("Saved ->", (FIG_DIR / "pred_vs_actual.png").relative_to(ROOT))

    # MAPE by category (top by count)
    dfb = pd.DataFrame({"cat": base_cat, "actual": base_actual, "pred": base_pred})
    top = dfb["cat"].value_counts().head(10).index
    rows = [(cat, _mape(g["actual"], g["pred"]), len(g))
            for cat, g in dfb[dfb["cat"].isin(top)].groupby("cat")]
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh([f"{r[0][:22]} (n={r[2]})" for r in rows], [r[1] for r in rows], color="#0f766e")
    ax.set_xlabel("MAPE %"); ax.set_title("Pricing error by category (comps-median)")
    fig.tight_layout(); fig.savefig(FIG_DIR / "mape_by_category.png", dpi=150); plt.close(fig)
    print("Saved ->", (FIG_DIR / "mape_by_category.png").relative_to(ROOT))


if __name__ == "__main__":
    main()
