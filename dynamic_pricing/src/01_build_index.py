"""
#02 Dynamic Pricing — Step 1: build a comparable-product index.

LLM-based (no training). Instead of a trained price regressor, we recommend
prices by *retrieval*: embed each product (bge-m3), so at inference time we can
pull the K most similar products and reason about their prices.

Primary catalog: Tiki.vn (VND). Falls back to ASOS (GBP) if tiki isn't present
yet — so this runs today on the freely-available ASOS data and switches to tiki
automatically once the Kaggle download lands.

Output: <feature>/models/comps_index.npz   (embeddings + ids)
        <feature>/outputs/catalog.parquet   (normalised catalog + category price stats)
"""
from pathlib import Path
import sys
import argparse
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "common"))
from llm_client import embed, ping, EMBED_MODEL  # noqa: E402

OUT_DIR = ROOT / "outputs"; OUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR = ROOT / "models"; MODEL_DIR.mkdir(parents=True, exist_ok=True)
BY_IDEA = REPO / "dataset" / "by_idea" / "idea_02_dynamic_pricing"


def load_catalog(which: str = "auto") -> tuple[pd.DataFrame, str]:
    """Return (normalised catalog, currency) for one catalog (never mix currencies).

    which: 'asos' (clothing/GBP), 'makeup' (cosmetics/USD), 'tiki' (clothing/VND),
           or 'auto' (tiki > asos > makeup by availability).
    """
    tiki = BY_IDEA / "tiki_catalog_clean.parquet"
    asos = BY_IDEA / "asos_catalog_clean.parquet"
    makeup = BY_IDEA / "makeup_catalog_clean.parquet"

    if which == "auto":
        which = "tiki" if tiki.exists() else ("asos" if asos.exists() else "makeup")

    if which == "tiki" and tiki.exists():
        df = pd.read_parquet(tiki)
        out = pd.DataFrame({
            "id": df["id"].astype(str), "name": df["name"].astype(str),
            "category": df["category"].astype(str),
            "brand": df.get("brand", pd.Series(["OEM"] * len(df))).astype(str),
            "price": pd.to_numeric(df["price"], errors="coerce"),
            "demand": pd.to_numeric(df.get("quantity_sold", 0), errors="coerce").fillna(0),
            "rating": pd.to_numeric(df.get("rating_average", 0), errors="coerce").fillna(0),
        })
        return out.dropna(subset=["price"]).query("price > 0").reset_index(drop=True), "VND"
    if which == "asos" and asos.exists():
        df = pd.read_parquet(asos)
        out = pd.DataFrame({
            "id": df.get("sku", pd.Series(range(len(df)))).astype(str),
            "name": df["name"].astype(str), "category": df["category"].astype(str),
            "brand": df.get("color", pd.Series([""] * len(df))).astype(str),
            "price": pd.to_numeric(df["price"], errors="coerce"), "demand": 0.0, "rating": 0.0,
        })
        return out.dropna(subset=["price"]).query("price > 0").reset_index(drop=True), "GBP"
    if which == "makeup" and makeup.exists():
        df = pd.read_parquet(makeup)
        out = pd.DataFrame({
            "id": df["id"].astype(str), "name": df["name"].astype(str),
            "category": df["category"].astype(str), "brand": df["brand"].astype(str),
            "price": pd.to_numeric(df["price"], errors="coerce"),
            "demand": pd.to_numeric(df.get("review_count", 0), errors="coerce").fillna(0),
            "rating": pd.to_numeric(df.get("rating", 0), errors="coerce").fillna(0),
        })
        return out.dropna(subset=["price"]).query("price > 0").reset_index(drop=True), "USD"
    raise FileNotFoundError(
        f"Catalog '{which}' not found. Fetch via `python code/download_clean_ideas.py {which}`.")


def comp_text(row) -> str:
    return f"{row['name']} | category: {row['category']} | brand: {row['brand']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-rows", type=int, default=6000, help="cap catalog size for embedding speed")
    ap.add_argument("--catalog", default="auto", choices=["auto", "asos", "makeup", "tiki"],
                    help="which catalog to price (never mixes currencies)")
    args = ap.parse_args()
    if not ping():
        raise SystemExit("Embedding backend not reachable (Ollama/OpenAI).")

    df, currency = load_catalog(args.catalog)
    df = df.drop_duplicates("id").reset_index(drop=True)   # ids must be unique for index alignment
    if len(df) > args.max_rows:
        df = df.sample(args.max_rows, random_state=42).reset_index(drop=True)
    print(f"Catalog: {len(df)} products | currency={currency} | embedding with {EMBED_MODEL}")

    vecs = embed([comp_text(r) for _, r in df.iterrows()], batch_size=64)
    vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)  # normalise for cosine

    np.savez(MODEL_DIR / "comps_index.npz", vectors=vecs, ids=df["id"].to_numpy(), currency=currency)
    df.to_parquet(OUT_DIR / "catalog.parquet", index=False)

    # category price stats — a strong no-LLM reference
    stats = df.groupby("category")["price"].agg(["count", "median", "mean", "std"]).round(2)
    stats.to_csv(OUT_DIR / "category_price_stats.csv")
    print(f"Saved index ({vecs.shape}) -> {(MODEL_DIR / 'comps_index.npz').relative_to(ROOT)}")
    print(f"Saved catalog -> {(OUT_DIR / 'catalog.parquet').relative_to(ROOT)}  | currency={currency}")


if __name__ == "__main__":
    main()
