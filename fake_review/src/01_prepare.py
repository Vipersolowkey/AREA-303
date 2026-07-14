"""
#05 Fake Review — Step 1: prepare evaluation sample (English platform).

LLM-based (no training): a local/remote LLM flags computer-generated / fake
reviews; we evaluate against ground-truth labels.

Data: fake_reviews_clean (Salminen et al., English).
  is_fake  0 = genuine (original), 1 = fake (computer-generated)

We build a balanced binary sample and keep rating + category as metadata signals.

Input : dataset/by_idea/idea_05_fake_review/fake_reviews_clean.parquet
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
    REPO / "dataset" / "by_idea" / "idea_05_fake_review" / "fake_reviews_clean.parquet",
]
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_data() -> Path:
    for p in DATA_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "fake_reviews_clean.parquet not found. Run: python code/download_clean_ideas.py fake_reviews")


def build_sample(df: pd.DataFrame, per_class: int) -> pd.DataFrame:
    df = df.dropna(subset=["text"]).copy()
    df = df[df["text"].str.strip().str.len() >= 3]
    parts = []
    for lbl in [0, 1]:
        pool = df[df["is_fake"] == lbl]
        parts.append(pool.sample(min(per_class, len(pool)), random_state=RANDOM_STATE))
    return pd.concat(parts).sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=125, help="reviews per class (genuine / fake)")
    args = ap.parse_args()

    path = resolve_data()
    print(f"Loading {path.relative_to(REPO)}")
    df = pd.read_parquet(path)
    print(f"  full: {df.shape} | fake rate: {df.is_fake.mean():.3f}")

    sample = build_sample(df, args.per_class)
    print(f"\nBalanced sample: {len(sample)} rows")
    print("  is_fake (0=genuine,1=fake):", sample.is_fake.value_counts().to_dict())

    out = OUT_DIR / "eval_sample.parquet"
    sample.to_parquet(out, index=False)
    print(f"\nSaved -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
