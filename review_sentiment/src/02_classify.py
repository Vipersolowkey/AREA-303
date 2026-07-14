"""
#01 Review Sentiment — Step 2: classify with an LLM (few-shot, English).

Reads the balanced eval sample and asks the LLM to classify each English review
as positive / neutral / negative, returning structured JSON. No training.

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

# Prompt v2 (neutral-calibrated) — chosen via code/ab_prompts.py: lifts neutral
# recall 0.61 -> 0.71 at 1200 reviews with no loss to overall macro-F1.
SYSTEM = (
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

FEWSHOT = [
    ("Beautiful top, soft fabric, true to size. Absolutely love it, will buy again!", "positive"),
    ("The dress is pretty but the fabric is thinner than expected — fine for the price I guess.", "neutral"),
    ("It's okay. Nothing special, does the job.", "neutral"),
    ("Fast shipping, well packaged. Haven't worn it yet.", "neutral"),
    ("Terrible quality, fell apart after one wash. Very disappointed.", "negative"),
]

SCHEMA = {
    "type": "object",
    "properties": {
        "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
        "reason": {"type": "string"},
    },
    "required": ["sentiment"],
}


def build_prompt(text: str) -> str:
    ex = "\n".join(f'- Review: "{t}" -> {lab}' for t, lab in FEWSHOT)
    return (
        f"Examples:\n{ex}\n\n"
        f'Classify the review below. Return JSON {{"sentiment": <positive|neutral|negative>, "reason": <short>}}.\n'
        f'Review: "{text}"'
    )


def classify_one(text: str) -> dict:
    try:
        r = chat_json(build_prompt(text), system=SYSTEM, schema=SCHEMA)
        s = str(r.get("sentiment", "")).lower().strip()
        if s not in {"positive", "neutral", "negative"}:
            s = "neutral"
        return {"pred": s, "reason": r.get("reason", "")}
    except Exception as e:  # noqa: BLE001
        return {"pred": "neutral", "reason": f"ERROR: {e}"}


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
    texts = [str(t) for t in sample["text"].tolist()]
    results = map_concurrent(
        texts, classify_one,
        on_progress=lambda d, n: print(f"  {d}/{n}") if (d % 50 == 0 or d == n) else None)
    dt = time.time() - t0

    sample = sample.copy()
    sample["pred_sentiment"] = [r["pred"] for r in results]
    sample["pred_reason"] = [r["reason"] for r in results]
    sample.to_parquet(OUT_DIR / "predictions.parquet", index=False)
    print(f"Done in {dt:.1f}s ({dt/max(1,len(sample)):.2f}s/review) | usage: {usage_report()}")
    print(f"Saved -> {(OUT_DIR / 'predictions.parquet').relative_to(ROOT)}")

    with open(MODEL_DIR / "prompt_config.json", "w", encoding="utf-8") as f:
        json.dump({"approach": "llm-fewshot-zero-training", "model": CHAT_MODEL,
                   "task": "english-review-sentiment",
                   "labels": ["positive", "neutral", "negative"],
                   "system_prompt": SYSTEM, "fewshot": FEWSHOT, "schema": SCHEMA},
                  f, ensure_ascii=False, indent=2)
    print(f"Saved -> {(MODEL_DIR / 'prompt_config.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
