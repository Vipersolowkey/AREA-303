"""
#01 Review Sentiment — Step 1: prepare evaluation sample (English platform).

LLM-based (no training): a local/remote LLM classifies review sentiment
zero/few-shot; we evaluate against the rating-derived ground truth.

Ground-truth sentiment from rating:  1-2 -> negative, 3 -> neutral, 4-5 -> positive

Primary data: English product reviews (fake_reviews_clean). We build a *balanced*
stratified sample (equal reviews per sentiment class) because ratings skew to 5★.

Input : dataset/by_idea/idea_01_review_sentiment/fake_reviews_clean.parquet
Output: <feature>/outputs/eval_sample.parquet
"""
from pathlib import Path
import argparse
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
RANDOM_STATE = 42

DATA_CANDIDATES = [
    ROOT / "data" / "fake_reviews_clean.parquet",
    REPO / "dataset" / "by_idea" / "idea_01_review_sentiment" / "fake_reviews_clean.parquet",
]
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_data() -> Path:
    for p in DATA_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "fake_reviews_clean.parquet not found. Run: python code/download_clean_ideas.py fake_reviews")


def rating_to_sentiment(r: float) -> str:
    return "negative" if r <= 2 else ("neutral" if r == 3 else "positive")


def build_sample(df: pd.DataFrame, per_class: int) -> pd.DataFrame:
    df = df.dropna(subset=["text", "rating"]).copy()
    df = df[df["text"].str.strip().str.len() >= 3]
    df["sentiment"] = df["rating"].apply(rating_to_sentiment)

    parts = []
    for cls in ["negative", "neutral", "positive"]:
        pool = df[df["sentiment"] == cls]
        parts.append(pool.sample(min(per_class, len(pool)), random_state=RANDOM_STATE))
    return pd.concat(parts).sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=150,
                    help="reviews per sentiment class (total = 3x this)")
    args = ap.parse_args()

    path = resolve_data()
    print(f"Loading {path.relative_to(REPO)}")
    df = pd.read_parquet(path)
    print(f"  full: {df.shape}")

    sample = build_sample(df, args.per_class)
    print(f"\nBalanced eval sample: {len(sample)} rows")
    print("  by sentiment:", sample.sentiment.value_counts().to_dict())

    out = OUT_DIR / "eval_sample.parquet"
    sample.to_parquet(out, index=False)
    print(f"\nSaved -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
