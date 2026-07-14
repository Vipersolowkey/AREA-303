"""
#05 Fake Review — Step 3: evaluate + serve helper (English).

Binary fake-review detection metrics (macro-F1, precision/recall) against the
ground-truth is_fake label, plus a PR curve using the LLM confidence as score.

Input : <feature>/outputs/predictions.parquet
Output: <feature>/outputs/classification_report.txt
        <feature>/figures/confusion_matrix.png, pr_curve.png
"""
from pathlib import Path
import sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import (classification_report, confusion_matrix, f1_score,
                             accuracy_score, precision_recall_curve, average_precision_score)

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
OUT_DIR = ROOT / "outputs"
FIG_DIR = ROOT / "figures"; FIG_DIR.mkdir(parents=True, exist_ok=True)


def _model() -> str:
    sys.path.insert(0, str(REPO / "common"))
    from llm_client import CHAT_MODEL, BACKEND
    return f"{BACKEND}:{CHAT_MODEL}"


def main():
    df = pd.read_parquet(OUT_DIR / "predictions.parquet")
    y_true = df["is_fake"].astype(int)
    y_pred = df["pred_is_fake"].astype(int)
    score = df["pred_conf"].where(df["pred_is_fake"] == 1, 1 - df["pred_conf"])  # P(fake)

    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    acc = accuracy_score(y_true, y_pred)
    report = classification_report(y_true, y_pred, target_names=["genuine", "fake"],
                                   digits=3, zero_division=0)
    n_err = int(df["reason"].astype(str).str.startswith("ERROR").sum())

    header = (
        f"#05 Fake Review (English) — LLM {_model()}, zero-training\n"
        f"Eval sample: {len(df)} reviews | LLM errors: {n_err}\n"
        f"Binary fake detection — Accuracy: {acc:.3f}  Macro-F1: {macro_f1:.3f}\n"
        + "=" * 64 + "\n"
    )
    print(header + report)
    with open(OUT_DIR / "classification_report.txt", "w", encoding="utf-8") as f:
        f.write(header + report + "\n")
    print("Saved ->", (OUT_DIR / "classification_report.txt").relative_to(ROOT))

    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(4.8, 4.2))
    im = ax.imshow(cm, cmap="Oranges")
    ax.set_xticks([0, 1], ["genuine", "fake"]); ax.set_yticks([0, 1], ["genuine", "fake"])
    ax.set_xlabel("Predicted"); ax.set_ylabel("True"); ax.set_title(f"Fake-review confusion — F1 {macro_f1:.3f}")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.colorbar(im, fraction=0.046, pad=0.04)
    fig.tight_layout(); fig.savefig(FIG_DIR / "confusion_matrix.png", dpi=150); plt.close(fig)
    print("Saved ->", (FIG_DIR / "confusion_matrix.png").relative_to(ROOT))

    if y_true.nunique() == 2:
        prec, rec, _ = precision_recall_curve(y_true, score)
        ap = average_precision_score(y_true, score)
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.plot(rec, prec, color="#ea580c")
        ax.set_xlabel("Recall"); ax.set_ylabel("Precision"); ax.set_title(f"Fake-review PR curve — AP {ap:.3f}")
        fig.tight_layout(); fig.savefig(FIG_DIR / "pr_curve.png", dpi=150); plt.close(fig)
        print("Saved ->", (FIG_DIR / "pr_curve.png").relative_to(ROOT))


def predict_fake(text: str, meta: dict | None = None) -> dict:
    """Flag one review as fake/genuine. meta may include rating, category."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("clf05", Path(__file__).resolve().parent / "02_classify.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    meta = meta or {}
    row = {"text": text, "rating": meta.get("rating", 5), "category": meta.get("category", "")}
    return mod.classify_one(row)


if __name__ == "__main__":
    main()
