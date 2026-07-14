"""
#04 Customer Churn — Step 3: evaluate risk scores.

Compares LLM churn_risk (and the rule baseline) against the true churn label:
AUC, F1 at a 0.5 threshold, confusion matrix, and a risk-vs-actual reliability plot.

Input : <feature>/outputs/scored.parquet
Output: <feature>/outputs/churn_report.txt
        <feature>/figures/roc_curve.png, risk_calibration.png
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score, f1_score, confusion_matrix, roc_curve

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
OUT_DIR = ROOT / "outputs"
FIG_DIR = ROOT / "figures"; FIG_DIR.mkdir(parents=True, exist_ok=True)


def _model() -> str:
    sys.path.insert(0, str(REPO / "common"))
    from llm_client import CHAT_MODEL, BACKEND
    return f"{BACKEND}:{CHAT_MODEL}"


def _metrics(y, score, name):
    mask = ~pd.isna(score)
    y, score = np.asarray(y[mask], int), np.asarray(score[mask], float)
    if len(np.unique(y)) < 2:
        return f"{name}: not enough label variety", None, None
    auc = roc_auc_score(y, score)
    f1 = f1_score(y, (score >= 0.5).astype(int), zero_division=0)
    return f"{name}: AUC={auc:.3f}  F1@0.5={f1:.3f}  (n={len(y)})", auc, (y, score)


def main():
    df = pd.read_parquet(OUT_DIR / "scored.parquet")
    source = df["source"].iloc[0]
    y = df["label"].astype(int)

    rule_line, _, rule_pack = _metrics(y, df["rule_risk"], "Rule baseline (all users)")
    llm_mask = ~pd.isna(df.get("llm_risk"))
    llm_line, _, llm_pack = _metrics(y[llm_mask], df.loc[llm_mask, "llm_risk"],
                                     f"LLM {_model()} (scored subset)")

    header = (
        f"#04 Customer Churn — LLM risk scoring, zero-training\n"
        f"Data source: {source}  |  users: {len(df)}  |  churn rate: {y.mean():.3f}\n"
        f"LLM-scored users: {int(llm_mask.sum())}\n"
        + "=" * 60 + "\n" + rule_line + "\n" + llm_line + "\n"
    )
    if source == "synthetic":
        header += ("\nNOTE: synthetic cohort (rees46 not downloaded). Numbers demonstrate the\n"
                   "pipeline; re-run after `code/download_clean_ideas.py churn` for real data.\n")
    print(header)
    (OUT_DIR / "churn_report.txt").write_text(header, encoding="utf-8")
    print("Saved ->", (OUT_DIR / "churn_report.txt").relative_to(ROOT))

    # ROC curves
    fig, ax = plt.subplots(figsize=(5, 4.5))
    for pack, lab, col in [(rule_pack, "rule", "#64748b"), (llm_pack, "LLM", "#dc2626")]:
        if pack:
            yy, ss = pack
            fpr, tpr, _ = roc_curve(yy, ss)
            ax.plot(fpr, tpr, label=f"{lab} (AUC {roc_auc_score(yy, ss):.3f})", color=col)
    ax.plot([0, 1], [0, 1], "k--", lw=0.8)
    ax.set_xlabel("FPR"); ax.set_ylabel("TPR"); ax.set_title("Churn ROC"); ax.legend()
    fig.tight_layout(); fig.savefig(FIG_DIR / "roc_curve.png", dpi=150); plt.close(fig)
    print("Saved ->", (FIG_DIR / "roc_curve.png").relative_to(ROOT))

    # calibration: mean actual churn per LLM-risk decile
    if llm_pack:
        yy, ss = llm_pack
        d = pd.DataFrame({"y": yy, "risk": ss})
        d["bin"] = pd.qcut(d["risk"], q=min(10, d["risk"].nunique()), duplicates="drop")
        cal = d.groupby("bin", observed=True).agg(pred=("risk", "mean"), actual=("y", "mean"))
        fig, ax = plt.subplots(figsize=(5, 4.5))
        ax.plot(cal["pred"], cal["actual"], "o-", color="#dc2626")
        ax.plot([0, 1], [0, 1], "k--", lw=0.8)
        ax.set_xlabel("Mean predicted risk"); ax.set_ylabel("Actual churn rate")
        ax.set_title("LLM risk calibration"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        fig.tight_layout(); fig.savefig(FIG_DIR / "risk_calibration.png", dpi=150); plt.close(fig)
        print("Saved ->", (FIG_DIR / "risk_calibration.png").relative_to(ROOT))


if __name__ == "__main__":
    main()
