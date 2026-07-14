"""
#05 Fake Review — Step 2: detect fake/computer-generated reviews with an LLM.

Classifies each English review as genuine or fake (computer-generated), from the
review text plus metadata (rating, category). Returns structured JSON. No training.

Input : <feature>/outputs/eval_sample.parquet
Output: <feature>/outputs/predictions.parquet
        <feature>/models/prompt_config.json
"""
from pathlib import Path
import sys
import json
import argparse
import time
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "common"))
from llm_client import chat_json, ping, CHAT_MODEL, map_concurrent, usage_report, reset_usage  # noqa: E402

OUT_DIR = ROOT / "outputs"
MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM = (
    "You are a review-integrity system for an e-commerce platform (fashion & "
    "cosmetics). Decide whether a review is GENUINE (written by a real customer) "
    "or FAKE (computer-generated / fabricated). Fake reviews tend to be generic, "
    "overly positive, template-like, repetitive, or lack concrete product detail. "
    "Use the text and metadata (rating, category). Always return JSON."
)

FEWSHOT = [
    ('rating=5, category=Clothing, review: "Fits perfectly, the linen is breathable and the '
     'stitching held up after three washes. Runs slightly large."', "genuine (specific, concrete detail)"),
    ('rating=5, category=Beauty, review: "Love this product! Great quality and works perfectly. '
     'Highly recommend to everyone!"', "fake (generic, template-like, no specifics)"),
    ('rating=1, category=Shoes, review: "Sole separated within a week and the glue smell was strong. '
     'Returned it."', "genuine (concrete complaint)"),
    ('rating=5, category=Home, review: "This is amazing. I love it. Best purchase ever. Amazing quality."',
     "fake (repetitive, vague)"),
]

SCHEMA = {
    "type": "object",
    "properties": {
        "is_fake": {"type": "boolean"},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["is_fake"],
}


def build_prompt(row) -> str:
    ex = "\n".join(f"- {t} -> {lab}" for t, lab in FEWSHOT)
    meta = f"rating={row.get('rating','?')}, category={row.get('category','?')}"
    return (
        f"Examples:\n{ex}\n\n"
        f'Assess the review below. Return JSON {{"is_fake": bool, "confidence": 0..1, "reason": <short>}}.\n'
        f"Metadata: {meta}\n"
        f'Review: "{row["text"]}"'
    )


def classify_one(row) -> dict:
    try:
        r = chat_json(build_prompt(row), system=SYSTEM, schema=SCHEMA)
        is_fake = bool(r.get("is_fake", False))
        conf = float(r.get("confidence", 0.5) or 0.5)
        return {"pred_is_fake": int(is_fake), "pred_conf": max(0.0, min(1.0, conf)),
                "reason": r.get("reason", "")}
    except Exception as e:  # noqa: BLE001
        return {"pred_is_fake": 0, "pred_conf": 0.0, "reason": f"ERROR: {e}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if not ping():
        raise SystemExit("LLM backend not reachable. Start Ollama or set OPENAI_API_KEY in .env.")

    sample = pd.read_parquet(OUT_DIR / "eval_sample.parquet")
    if args.limit:
        sample = sample.head(args.limit)
    print(f"Classifying {len(sample)} reviews with {CHAT_MODEL} (concurrent) ...")

    reset_usage()
    t0 = time.time()
    row_list = [row for _, row in sample.iterrows()]
    rows = map_concurrent(
        row_list, classify_one,
        on_progress=lambda d, n: print(f"  {d}/{n}") if (d % 50 == 0 or d == n) else None)
    dt = time.time() - t0

    preds = pd.DataFrame(rows, index=sample.index)
    pd.concat([sample, preds], axis=1).to_parquet(OUT_DIR / "predictions.parquet", index=False)
    print(f"Done in {dt:.1f}s ({dt/max(1,len(sample)):.2f}s/review) | usage: {usage_report()}")
    print(f"Saved -> {(OUT_DIR / 'predictions.parquet').relative_to(ROOT)}")

    with open(MODEL_DIR / "prompt_config.json", "w", encoding="utf-8") as f:
        json.dump({"approach": "llm-fewshot-zero-training", "model": CHAT_MODEL,
                   "task": "english-fake-review-detection",
                   "system_prompt": SYSTEM, "fewshot": FEWSHOT, "schema": SCHEMA},
                  f, ensure_ascii=False, indent=2)
    print(f"Saved -> {(MODEL_DIR / 'prompt_config.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
