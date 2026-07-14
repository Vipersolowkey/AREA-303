"""
A/B prompt experiment for #01 (sentiment) and #05 (fake review).

Runs two prompt variants over the SAME (large) eval sample and compares metrics.
v1 = the prompt currently shipped in the feature; v2 = a tuned variant targeting
the known weak spot (#01 neutral class, #05 genuine recall). Uses the shared LLM
client (concurrent + cached), so re-runs are cheap.

    python code/ab_prompts.py            # both features
    python code/ab_prompts.py sentiment  # or: fake
"""
import sys
import time
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, recall_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "common"))
from llm_client import chat_json, map_concurrent, usage_report, reset_usage, CHAT_MODEL  # noqa: E402

# ===========================================================================
# #01 SENTIMENT
# ===========================================================================
SENT_SCHEMA = {"type": "object", "properties": {
    "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]}},
    "required": ["sentiment"]}

SENT_SYS_V1 = (
    "You are a sentiment classifier for e-commerce product reviews (fashion & "
    "cosmetics). Classify the OVERALL sentiment of each review into exactly one "
    "label: positive (satisfied), neutral (mixed/factual), negative (dissatisfied). "
    "Judge only the review content. Always return JSON matching the schema."
)
SENT_FEW_V1 = [
    ("Beautiful top, soft fabric, true to size, fast shipping. Very happy!", "positive"),
    ("Color is nice but it fades quickly, okay for the price.", "neutral"),
    ("Poor quality, looks nothing like the photo, thin material. Disappointed.", "negative"),
    ("Arrived on time, packaging was fine.", "neutral"),
]

# v2 — sharpen the neutral boundary (the weak class): mixed pros+cons, lukewarm,
# "okay/average/fine", or purely factual => neutral; reserve pos/neg for clear cases.
SENT_SYS_V2 = (
    "You are a sentiment classifier for e-commerce product reviews (fashion & "
    "cosmetics). Return exactly one label: positive, neutral, or negative.\n"
    "Guidance:\n"
    "- positive: clearly satisfied, recommends, praise with no real reservation.\n"
    "- negative: clearly dissatisfied, regrets the purchase, real problems dominate.\n"
    "- neutral: LUKEWARM or MIXED — praise AND complaints together; 'okay / average / "
    "fine / decent for the price'; mild reservations; or purely factual (shipping/"
    "packaging) with no strong feeling about the product itself.\n"
    "If the review has both clear pros and clear cons, choose neutral. Judge only the "
    "review content. Always return JSON matching the schema."
)
SENT_FEW_V2 = [
    ("Beautiful top, soft fabric, true to size. Absolutely love it, will buy again!", "positive"),
    ("The dress is pretty but the fabric is thinner than expected — fine for the price I guess.", "neutral"),
    ("It's okay. Nothing special, does the job.", "neutral"),
    ("Fast shipping, well packaged. Haven't worn it yet.", "neutral"),
    ("Terrible quality, fell apart after one wash. Very disappointed.", "negative"),
]


def sent_fn(system, few):
    def build(text):
        ex = "\n".join(f'- Review: "{t}" -> {lab}' for t, lab in few)
        return (f"Examples:\n{ex}\n\nClassify the review below. Return JSON "
                f'{{"sentiment": <positive|neutral|negative>}}.\nReview: "{text}"')

    def fn(text):
        try:
            r = chat_json(build(str(text)), system=system, schema=SENT_SCHEMA)
            s = str(r.get("sentiment", "")).lower().strip()
            return s if s in {"positive", "neutral", "negative"} else "neutral"
        except Exception:  # noqa: BLE001
            return "neutral"
    return fn


def eval_sentiment():
    df = pd.read_parquet(ROOT / "review_sentiment" / "outputs" / "eval_sample.parquet")
    y = df["sentiment"].tolist()
    texts = [str(t) for t in df["text"].tolist()]
    labels = ["negative", "neutral", "positive"]
    print(f"\n#01 SENTIMENT — {len(df)} reviews, model {CHAT_MODEL}")
    rows = []
    for name, sysp, few in [("v1 (current)", SENT_SYS_V1, SENT_FEW_V1),
                            ("v2 (neutral-calibrated)", SENT_SYS_V2, SENT_FEW_V2)]:
        reset_usage(); t0 = time.time()
        preds = map_concurrent(texts, sent_fn(sysp, few))
        acc = accuracy_score(y, preds)
        mf1 = f1_score(y, preds, labels=labels, average="macro", zero_division=0)
        rec = dict(zip(labels, recall_score(y, preds, labels=labels, average=None, zero_division=0)))
        u = usage_report()
        rows.append((name, acc, mf1, rec["neutral"], u["estimated_usd"], time.time() - t0))
        print(f"  {name:26s} acc {acc:.3f} | macroF1 {mf1:.3f} | neutral-recall {rec['neutral']:.3f} "
              f"| ${u['estimated_usd']:.3f} | {time.time()-t0:.0f}s")
    return rows


# ===========================================================================
# #05 FAKE REVIEW
# ===========================================================================
FAKE_SCHEMA = {"type": "object", "properties": {
    "is_fake": {"type": "boolean"}}, "required": ["is_fake"]}

FAKE_SYS_V1 = (
    "You are a review-integrity system for an e-commerce platform (fashion & "
    "cosmetics). Decide whether a review is GENUINE (written by a real customer) "
    "or FAKE (computer-generated / fabricated). Fake reviews tend to be generic, "
    "overly positive, template-like, repetitive, or lack concrete product detail. "
    "Use the text and metadata (rating, category). Always return JSON."
)
FAKE_FEW_V1 = [
    ('rating=5, category=Clothing, review: "Fits perfectly, the linen is breathable and the '
     'stitching held up after three washes. Runs slightly large."', "genuine"),
    ('rating=5, category=Beauty, review: "Love this product! Great quality and works perfectly. '
     'Highly recommend to everyone!"', "fake"),
    ('rating=1, category=Shoes, review: "Sole separated within a week and the glue smell was strong. '
     'Returned it."', "genuine"),
    ('rating=5, category=Home, review: "This is amazing. I love it. Best purchase ever. Amazing quality."', "fake"),
]

# v2 — raise the bar for FAKE to recover genuine recall: positivity/brevity alone
# is NOT evidence; require template/generic/no-specifics; when unsure -> genuine.
FAKE_SYS_V2 = (
    "You are a review-integrity system for an e-commerce platform (fashion & "
    "cosmetics). Label a review FAKE only when there is CLEAR evidence of fabrication: "
    "generic template language, no product-specific detail at all, unnatural repetition, "
    "or implausible/hollow enthusiasm. A GENUINE review can be short, very positive, or "
    "enthusiastic — do NOT call it fake merely for being positive, brief, or 5-star. "
    "Real reviews usually mention at least one concrete specific (fit, texture, color, "
    "scent, delivery, a use case). When evidence is weak or you are unsure, choose GENUINE. "
    "Use the text and metadata. Always return JSON."
)
FAKE_FEW_V2 = [
    ('rating=5, category=Clothing, review: "Fits perfectly, linen is breathable, stitching held after '
     'three washes. Runs slightly large."', "genuine (concrete specifics)"),
    ('rating=5, category=Beauty, review: "Love it, smells great and lasts all day on my oily skin."',
     "genuine (short but specific — do NOT flag)"),
    ('rating=5, category=Beauty, review: "Great quality and works perfectly. Highly recommend to everyone!"',
     "fake (generic, zero specifics)"),
    ('rating=5, category=Home, review: "This is amazing. I love it. Best purchase ever. Amazing quality."',
     "fake (hollow repetition)"),
]


def fake_fn(system, few):
    def build(row):
        ex = "\n".join(f"- {t} -> {lab}" for t, lab in few)
        meta = f"rating={row.get('rating','?')}, category={row.get('category','?')}"
        return (f"Examples:\n{ex}\n\nAssess the review below. Return JSON "
                f'{{"is_fake": bool}}.\nMetadata: {meta}\nReview: "{row["text"]}"')

    def fn(row):
        try:
            r = chat_json(build(row), system=system, schema=FAKE_SCHEMA)
            return int(bool(r.get("is_fake", False)))
        except Exception:  # noqa: BLE001
            return 0
    return fn


def eval_fake():
    df = pd.read_parquet(ROOT / "fake_review" / "outputs" / "eval_sample.parquet")
    y = df["is_fake"].astype(int).tolist()
    rowlist = [r for _, r in df.iterrows()]
    print(f"\n#05 FAKE REVIEW — {len(df)} reviews, model {CHAT_MODEL}")
    rows = []
    for name, sysp, few in [("v1 (current)", FAKE_SYS_V1, FAKE_FEW_V1),
                            ("v2 (genuine-recall)", FAKE_SYS_V2, FAKE_FEW_V2)]:
        reset_usage(); t0 = time.time()
        preds = map_concurrent(rowlist, fake_fn(sysp, few))
        acc = accuracy_score(y, preds)
        mf1 = f1_score(y, preds, average="macro", zero_division=0)
        gen_rec = recall_score(y, preds, pos_label=0, zero_division=0)
        fake_rec = recall_score(y, preds, pos_label=1, zero_division=0)
        u = usage_report()
        rows.append((name, acc, mf1, gen_rec, fake_rec, u["estimated_usd"], time.time() - t0))
        print(f"  {name:24s} acc {acc:.3f} | macroF1 {mf1:.3f} | genuine-recall {gen_rec:.3f} "
              f"| fake-recall {fake_rec:.3f} | ${u['estimated_usd']:.3f} | {time.time()-t0:.0f}s")
    return rows


if __name__ == "__main__":
    which = sys.argv[1:] or ["sentiment", "fake"]
    if "sentiment" in which:
        eval_sentiment()
    if "fake" in which:
        eval_fake()
    print("\nDone.")
