"""
AREA 303 — unified demo of all five features (#01–#05), English platform.

Runs each feature's serve helper on a couple of example inputs so you can see the
whole platform working from one command. Requires an LLM backend (OpenAI via
.env, or a local Ollama) and the built indexes for #02/#03
(`python <feature>/src/01_build_index.py`).

    python demo.py
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load(feature: str, script: str):
    p = ROOT / feature / "src" / script
    spec = importlib.util.spec_from_file_location(f"{feature}_{script}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hr(title):
    print("\n" + "=" * 70 + f"\n  {title}\n" + "=" * 70)


def demo_sentiment():
    hr("#01 Review Sentiment")
    mod = _load("review_sentiment", "03_evaluate.py")
    for t in ["Absolutely love this dress, fabric is soft and fits perfectly!",
              "Package arrived dented and the color is off. Not worth it."]:
        r = mod.predict_sentiment(t)
        print(f"  \"{t[:55]}...\" -> {r['sentiment']}  ({r.get('reason','')[:50]})")


def demo_fake():
    hr("#05 Fake Review Detection")
    mod = _load("fake_review", "03_evaluate.py")
    for t, meta in [("Fits true to size, the cotton is breathable and held up after washing.", {"rating": 5, "category": "Clothing"}),
                    ("Amazing! Love it! Best product ever! Highly recommend to everyone!", {"rating": 5, "category": "Beauty"})]:
        r = mod.predict_fake(t, meta)
        verdict = "FAKE" if r["pred_is_fake"] else "genuine"
        print(f"  \"{t[:50]}...\" -> {verdict}  (conf {r['pred_conf']:.2f})")


def demo_pricing():
    hr("#02 Dynamic Pricing")
    try:
        mod = _load("dynamic_pricing", "02_recommend.py")
        mod._load()
        for feats in [{"name": "Faux leather biker jacket in black", "category": "Jackets", "brand": "OEM"}]:
            r = mod.recommend_price(feats, k=8)
            print(f"  {feats['name']} -> recommend {r.get('recommended_price')} "
                  f"{r.get('currency','')}  (range {r.get('low')}-{r.get('high')})")
            print(f"    rationale: {str(r.get('rationale',''))[:90]}")
    except FileNotFoundError:
        print("  (build the index first: python dynamic_pricing/src/01_build_index.py)")


def demo_shopper():
    hr("#03 Personal Shopper")
    try:
        mod = _load("personal_shopper", "02_query.py")
        for q in ["warm waterproof jacket for hiking", "long-lasting matte red lipstick"]:
            out = mod.recommend(q, k=3)
            print(f"\n  Q: {q}")
            for p in out["products"]:
                print(f"    - [{p.get('domain','')}] {p['name'][:52]} ({p['price']:.2f} {p.get('currency','')})")
            print(f"    LLM: {out['answer'][:120]}...")
    except FileNotFoundError:
        print("  (build the index first: python personal_shopper/src/01_build_index.py)")


def demo_churn():
    hr("#04 Customer Churn")
    mod = _load("customer_churn", "02_score.py")
    users = [
        {"recency_days": 210, "frequency_orders": 2, "monetary_avg": 18, "tenure_months": 20,
         "sessions_last_month": 1, "cart_abandon_rate": 0.7, "trend": "declining"},
        {"recency_days": 8, "frequency_orders": 14, "monetary_avg": 60, "tenure_months": 30,
         "sessions_last_month": 12, "cart_abandon_rate": 0.15, "trend": "growing"},
    ]
    for u in users:
        r = mod.predict_churn(u)
        print(f"  recency={u['recency_days']}d freq={u['frequency_orders']} trend={u['trend']} "
              f"-> churn {r['proba']:.2f} (rule {r['rule_risk']:.2f})")
        print(f"    action: {str(r.get('retention_action',''))[:80]}")


if __name__ == "__main__":
    print("AREA 303 — 5-feature demo (English platform, LLM-first, no training)")
    demo_sentiment()
    demo_fake()
    demo_pricing()
    demo_shopper()
    demo_churn()
    print("\nDone.")
