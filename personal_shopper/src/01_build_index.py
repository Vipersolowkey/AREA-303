"""
#03 Personal Shopper — Step 1: build the retrieval index (RAG).

LLM-based, no training. Embed the product catalog (bge-m3 locally, or
text-embedding-3-small via OpenAI) so natural-language shopper queries can be
answered by retrieval + an LLM (no chat UI — a callable recommend()).

Primary catalog: Tiki.vn (VND). Falls back to ASOS (GBP) if tiki isn't present,
so this runs today on ASOS and switches to tiki once the Kaggle download lands.

Output: <feature>/models/catalog_index.npz   (embeddings + ids)
        <feature>/outputs/catalog.parquet     (retrievable fields)
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
BY_IDEA = REPO / "dataset" / "by_idea" / "idea_03_personal_shopper"
BY_IDEA_02 = REPO / "dataset" / "by_idea" / "idea_02_dynamic_pricing"


def _clip(s, n=200):
    s = "" if s is None else str(s)
    return s[:n].replace("\n", " ").strip()


def _norm(df, id_c, name_c, cat_c, brand_c, rating_c, currency, domain) -> pd.DataFrame:
    n = len(df)
    out = pd.DataFrame({
        "id": (df[id_c].astype(str) if id_c else pd.Series(range(n)).astype(str)) + f"::{domain}",
        "name": df[name_c].astype(str),
        "category": df[cat_c].astype(str) if cat_c else "",
        "brand": df[brand_c].astype(str) if brand_c else "",
        "price": pd.to_numeric(df["price"], errors="coerce"),
        "rating": pd.to_numeric(df[rating_c], errors="coerce").fillna(0) if rating_c else 0.0,
        "description": df.get("description", pd.Series([""] * n)).astype(str).map(_clip),
        "currency": currency,
        "domain": domain,
    })
    return out.dropna(subset=["price"]).reset_index(drop=True)


def load_catalog() -> tuple[pd.DataFrame, str]:
    """Combine every available catalog (clothing + cosmetics) into one index.

    Retrieval is currency-agnostic — each row keeps its own currency/domain for display.
    """
    tiki = BY_IDEA / "tiki_catalog_clean.parquet"
    asos = BY_IDEA_02 / "asos_catalog_clean.parquet"        # clothing (GBP)
    makeup = BY_IDEA / "makeup_catalog_clean.parquet"        # cosmetics (USD)
    parts = []
    if asos.exists():
        parts.append(_norm(pd.read_parquet(asos), "sku", "name", "category", "color", None, "GBP", "clothing"))
    if makeup.exists():
        parts.append(_norm(pd.read_parquet(makeup), "id", "name", "category", "brand", "rating", "USD", "cosmetics"))
    if tiki.exists():
        parts.append(_norm(pd.read_parquet(tiki), "id", "name", "category", "brand", "rating_average", "VND", "clothing"))
    if not parts:
        raise FileNotFoundError("No catalog. Get asos/makeup via code/download_clean_ideas.py.")
    df = pd.concat(parts, ignore_index=True)
    currency = "mixed" if df["currency"].nunique() > 1 else df["currency"].iloc[0]
    return df, currency


def doc_text(r) -> str:
    return f"{r['name']}. Category: {r['category']}. Brand: {r['brand']}. {r['description']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-rows", type=int, default=6000)
    args = ap.parse_args()
    if not ping():
        raise SystemExit("Embedding backend not reachable.")

    df, currency = load_catalog()
    df = df.drop_duplicates("id").reset_index(drop=True)
    if len(df) > args.max_rows:
        # keep ALL cosmetics (small), sample clothing to fill the budget
        cos = df[df["domain"] == "cosmetics"]
        oth = df[df["domain"] != "cosmetics"]
        n_oth = max(0, args.max_rows - len(cos))
        df = pd.concat([cos, oth.sample(min(n_oth, len(oth)), random_state=42)]).reset_index(drop=True)
    print(f"Catalog: {len(df)} products | currency={currency} | embedding with {EMBED_MODEL}")
    print("  by domain:", df["domain"].value_counts().to_dict())

    vecs = embed([doc_text(r) for _, r in df.iterrows()], batch_size=64)
    vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
    np.savez(MODEL_DIR / "catalog_index.npz", vectors=vecs, ids=df["id"].to_numpy(), currency=currency)
    df.to_parquet(OUT_DIR / "catalog.parquet", index=False)
    print(f"Saved index ({vecs.shape}) -> {(MODEL_DIR / 'catalog_index.npz').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
