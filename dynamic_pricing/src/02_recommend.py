"""
#02 Dynamic Pricing — Step 2: recommend a price via retrieval + LLM reasoning.

No trained regressor. For a target product we:
  1. embed its text and retrieve the K most similar products (comps),
  2. summarise the comps' price distribution (a strong statistical anchor),
  3. ask the LLM to reason a final recommended price + range given the product's
     attributes and the comps.

Exposes recommend_price(sku_features) for reuse (API/backend later).

Input : <feature>/models/comps_index.npz, <feature>/outputs/catalog.parquet
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "common"))
from llm_client import embed, chat_json, CHAT_MODEL  # noqa: E402

OUT_DIR = ROOT / "outputs"
MODEL_DIR = ROOT / "models"

_CACHE: dict = {}

SCHEMA = {
    "type": "object",
    "properties": {
        "recommended_price": {"type": "number"},
        "low": {"type": "number"},
        "high": {"type": "number"},
        "confidence": {"type": "number"},
        "rationale": {"type": "string"},
    },
    "required": ["recommended_price", "low", "high"],
}


def _load():
    if not _CACHE:
        idx = np.load(MODEL_DIR / "comps_index.npz", allow_pickle=True)
        cat = pd.read_parquet(OUT_DIR / "catalog.parquet")
        cat = cat.set_index(cat["id"].astype(str))
        _CACHE.update(vectors=idx["vectors"], ids=idx["ids"].astype(str),
                      currency=str(idx["currency"]), catalog=cat)
    return _CACHE


def comp_text(f: dict) -> str:
    return f"{f.get('name','')} | category: {f.get('category','')} | brand: {f.get('brand','')}"


def retrieve_comps(features: dict, k: int = 10, exclude_id: str | None = None) -> pd.DataFrame:
    c = _load()
    q = embed(comp_text(features))
    q = q / (np.linalg.norm(q) + 1e-9)
    sims = c["vectors"] @ q
    order = np.argsort(-sims)
    comps, seen = [], 0
    for i in order:
        cid = c["ids"][i]
        if exclude_id is not None and cid == str(exclude_id):
            continue
        if cid not in c["catalog"].index:
            continue
        row = c["catalog"].loc[cid]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        comps.append({"id": cid, "name": row["name"], "category": row["category"],
                      "price": float(row["price"]), "sim": float(sims[i])})
        seen += 1
        if seen >= k:
            break
    return pd.DataFrame(comps)


def recommend_price(sku_features: dict, k: int = 10, use_llm: bool = True) -> dict:
    """Recommend a price for a product. sku_features: name, category, brand[, current_price]."""
    c = _load()
    comps = retrieve_comps(sku_features, k=k, exclude_id=sku_features.get("id"))
    if comps.empty:
        return {"error": "no comparable products found"}
    prices = comps["price"]
    anchor = {"median": float(prices.median()), "p25": float(prices.quantile(.25)),
              "p75": float(prices.quantile(.75)), "n": int(len(prices))}

    baseline = {"recommended_price": anchor["median"], "low": anchor["p25"],
                "high": anchor["p75"], "confidence": min(1.0, anchor["n"] / k),
                "rationale": f"Median of {anchor['n']} comparable products.",
                "method": "comps_median", "currency": c["currency"]}
    if not use_llm:
        return {**baseline, "comps": comps.to_dict("records")}

    comp_lines = "\n".join(f"- {r['name'][:60]} ({r['category']}): {r['price']:.2f}"
                           for _, r in comps.iterrows())
    prompt = (
        f"Product to price ({c['currency']}):\n"
        f"  Name: {sku_features.get('name','')}\n  Category: {sku_features.get('category','')}\n"
        f"  Brand: {sku_features.get('brand','')}\n"
        f"  Current price: {sku_features.get('current_price','(none)')}\n\n"
        f"Comparable products and their prices:\n{comp_lines}\n\n"
        f"Comps stats: median {anchor['median']:.2f}, range {anchor['p25']:.2f}–{anchor['p75']:.2f}.\n"
        f"Recommend a competitive selling price for a small/medium seller (balance competitiveness "
        f'and margin). Return JSON {{"recommended_price", "low", "high", "confidence" 0..1, "rationale"}}.'
    )
    system = "You are an e-commerce pricing expert for small and medium fashion & cosmetics sellers. Always return JSON."
    try:
        r = chat_json(prompt, system=system, schema=SCHEMA)
        r.update(method=f"llm_comps:{CHAT_MODEL}", currency=c["currency"],
                 comps_anchor=anchor, comps=comps.to_dict("records"))
        return r
    except Exception as e:  # noqa: BLE001
        return {**baseline, "llm_error": str(e), "comps": comps.to_dict("records")}


if __name__ == "__main__":
    _load()
    demo = {"name": "Men's oversized cotton t-shirt", "category": "T-shirts", "brand": "OEM"}
    print("Demo recommend_price:")
    out = recommend_price(demo, k=8)
    for key in ("recommended_price", "low", "high", "confidence", "method", "currency", "rationale"):
        if key in out:
            print(f"  {key}: {out[key]}")
