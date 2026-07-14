"""
#01 Review Sentiment — Step 3: evaluate + serve helper.

Compares the LLM predictions against rating-derived ground truth. Writes a
classification report + figures. Exposes predict_sentiment() for reuse.

Input : <feature>/outputs/predictions.parquet
Output: <feature>/outputs/classification_report.txt
        <feature>/figures/confusion_matrix.png
        <feature>/figures/class_distribution.png
"""
from pathlib import Path
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
OUT_DIR = ROOT / "outputs"
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

LABELS = ["negative", "neutral", "positive"]


def main():
    df = pd.read_parquet(OUT_DIR / "predictions.parquet")
    y_true = df["sentiment"]
    y_pred = df["pred_sentiment"]

    macro_f1 = f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)
    acc = accuracy_score(y_true, y_pred)
    report = classification_report(y_true, y_pred, labels=LABELS, digits=3, zero_division=0)

    n_err = int((df["pred_reason"].astype(str).str.startswith("ERROR")).sum())

    header = (
        f"#01 Review Sentiment (English) — LLM {_model()}, zero-training\n"
        f"Eval sample: {len(df)} reviews\n"
        f"LLM call errors (fell back to neutral): {n_err}\n"
        f"Accuracy: {acc:.3f}   Macro-F1: {macro_f1:.3f}\n"
        + "=" * 64 + "\n"
    )
    print(header + report)
    with open(OUT_DIR / "classification_report.txt", "w", encoding="utf-8") as f:
        f.write(header + report)
    print("Saved ->", (OUT_DIR / "classification_report.txt").relative_to(ROOT))

    # confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=LABELS)
    fig, ax = plt.subplots(figsize=(5.5, 4.8))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(3), LABELS); ax.set_yticks(range(3), LABELS)
    ax.set_xlabel("Predicted (LLM)"); ax.set_ylabel("True (rating-derived)")
    ax.set_title(f"Sentiment confusion — macro-F1 {macro_f1:.3f}")
    for i in range(3):
        for j in range(3):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.colorbar(im, fraction=0.046, pad=0.04)
    fig.tight_layout(); fig.savefig(FIG_DIR / "confusion_matrix.png", dpi=150); plt.close(fig)
    print("Saved ->", (FIG_DIR / "confusion_matrix.png").relative_to(ROOT))

    # class distribution (true vs pred)
    fig, ax = plt.subplots(figsize=(6, 4))
    x = np.arange(3); w = 0.38
    ax.bar(x - w/2, [(y_true == l).sum() for l in LABELS], w, label="True", color="#2563eb")
    ax.bar(x + w/2, [(y_pred == l).sum() for l in LABELS], w, label="LLM pred", color="#f59e0b")
    ax.set_xticks(x, LABELS); ax.set_ylabel("count"); ax.legend()
    ax.set_title("Class distribution: true vs predicted")
    fig.tight_layout(); fig.savefig(FIG_DIR / "class_distribution.png", dpi=150); plt.close(fig)
    print("Saved ->", (FIG_DIR / "class_distribution.png").relative_to(ROOT))


def _model() -> str:
    sys.path.insert(0, str(REPO / "common"))
    from llm_client import CHAT_MODEL, BACKEND
    return f"{BACKEND}:{CHAT_MODEL}"


# ----------------------------------------------------------------------------
# Serving helper — reusable single-review classification
# ----------------------------------------------------------------------------
def predict_sentiment(text: str) -> dict:
    """Classify one Vietnamese review. Returns {'sentiment', 'reason'}."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location("classify_mod", Path(__file__).resolve().parent / "02_classify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    res = mod.classify_one(text)
    return {"sentiment": res["pred"], "reason": res.get("reason", "")}


if __name__ == "__main__":
    main()
