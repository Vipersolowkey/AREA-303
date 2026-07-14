"""
#03 Personal Shopper — Step 2: retrieve + generate (RAG).

recommend(query, k) embeds the Vietnamese query, retrieves the top-K products by
cosine similarity, and asks the LLM to write a short Vietnamese recommendation
grounded ONLY in the retrieved products. No chat UI — a callable function.

Input: <feature>/models/catalog_index.npz, <feature>/outputs/catalog.parquet
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "common"))
from llm_client import embed, chat, CHAT_MODEL  # noqa: E402

OUT_DIR = ROOT / "outputs"
MODEL_DIR = ROOT / "models"
_CACHE: dict = {}


def _load():
    if not _CACHE:
        idx = np.load(MODEL_DIR / "catalog_index.npz", allow_pickle=True)
        cat = pd.read_parquet(OUT_DIR / "catalog.parquet")
        cat["id"] = cat["id"].astype(str)
        _CACHE.update(vectors=idx["vectors"], ids=idx["ids"].astype(str),
                      currency=str(idx["currency"]), catalog=cat.set_index("id"))
    return _CACHE


def retrieve(query: str, k: int = 5) -> pd.DataFrame:
    c = _load()
    q = embed(query); q = q / (np.linalg.norm(q) + 1e-9)
    sims = c["vectors"] @ q
    top = np.argsort(-sims)[:k]
    rows = []
    for i in top:
        cid = c["ids"][i]
        if cid not in c["catalog"].index:
            continue
        r = c["catalog"].loc[cid]
        if isinstance(r, pd.DataFrame):
            r = r.iloc[0]
        rows.append({"id": cid, "name": r["name"], "category": r["category"],
                     "brand": r["brand"], "price": float(r["price"]),
                     "currency": r.get("currency", c["currency"]),
                     "domain": r.get("domain", ""),
                     "rating": float(r.get("rating", 0)), "sim": float(sims[i])})
    return pd.DataFrame(rows)


def recommend(query: str, k: int = 5, generate: bool = True) -> dict:
    """Return {'query', 'products', 'answer'} for a natural-language shopper query."""
    c = _load()
    products = retrieve(query, k=k)
    if products.empty:
        return {"query": query, "products": [], "answer": "Không tìm thấy sản phẩm phù hợp."}
    if not generate:
        return {"query": query, "products": products.to_dict("records"), "answer": None}

    lines = "\n".join(
        f"{i+1}. {r['name'][:70]} | {r['category']} | {r['price']:.2f} {r['currency']}"
        + (f" | {r['rating']:.1f}star" if r["rating"] else "")
        for i, r in products.iterrows())
    system = ("You are a shopping assistant for a fashion & cosmetics marketplace. "
              "Recommend ONLY from the provided product list — never invent products. "
              "Be concise and friendly: highlight the 2-3 best options with a short reason and price.")
    prompt = (f'Customer asks: "{query}"\n\nRetrieved products:\n{lines}\n\n'
              "Give the customer a recommendation.")
    answer = chat(prompt, system=system)
    return {"query": query, "products": products.to_dict("records"), "answer": answer}


if __name__ == "__main__":
    for q in ["warm winter coat for women", "long-lasting red lipstick"]:
        out = recommend(q, k=5)
        print(f"\nQ: {q}\n{'-'*60}")
        for p in out["products"]:
            print(f"  - {p['name'][:60]} ({p['price']:.0f}) sim={p['sim']:.3f}")
        print("LLM:", out["answer"][:300])
