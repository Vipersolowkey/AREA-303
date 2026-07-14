"""
#03 Personal Shopper — Step 3: evaluate retrieval + sample generations.

  - recall@k: for N random products, build a query from their name keywords and
    check whether the product is retrieved in the top-k (uses index vectors, no
    re-embedding — fast).
  - smoke queries: run a few realistic Vietnamese queries end-to-end (retrieval
    + LLM answer) and save them for eyeballing.

Output: <feature>/outputs/retrieval_report.txt
        <feature>/outputs/sample_queries.md
        <feature>/figures/recall_at_k.png
"""
from pathlib import Path
import sys
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
import importlib.util
_spec = importlib.util.spec_from_file_location("q03", ROOT / "src" / "02_query.py")
q = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(q)

OUT_DIR = ROOT / "outputs"
FIG_DIR = ROOT / "figures"; FIG_DIR.mkdir(parents=True, exist_ok=True)

SMOKE_QUERIES = [
    "warm winter coat for women",        # clothing
    "elegant party dress",               # clothing
    "long-lasting matte red lipstick",   # cosmetics
    "gentle hydrating face moisturizer", # cosmetics
    "waterproof mascara for volume",     # cosmetics
]


def _name_query(name: str) -> str:
    """Build a realistic partial query from a product name (first ~6 tokens)."""
    toks = str(name).split()
    return " ".join(toks[:6])


def recall_at_k(n=200, ks=(1, 3, 5, 10), seed=13) -> dict:
    """Known-item retrieval: query built from a product's name should retrieve THAT product.

    Language- and taxonomy-agnostic (doesn't depend on the category field, which is
    degenerate in the ASOS demo catalog). Queries are embedded in one batch (fast).
    """
    c = q._load()
    from llm_client import embed
    vectors, ids = c["vectors"], c["ids"]
    catalog = c["catalog"]
    rng = np.random.default_rng(seed)
    pos = rng.choice(len(ids), size=min(n, len(ids)), replace=False)

    queries = [_name_query(catalog.loc[ids[p]]["name"]) for p in pos]
    qv = embed(queries, batch_size=64)
    qv = qv / (np.linalg.norm(qv, axis=1, keepdims=True) + 1e-9)
    sims = qv @ vectors.T                         # (n, N)

    hits = {k: 0 for k in ks}
    kmax = max(ks)
    for r, p in enumerate(pos):
        top = np.argpartition(-sims[r], kmax)[:kmax]
        top = top[np.argsort(-sims[r][top])]
        top_ids = list(ids[top])
        for k in ks:
            if ids[p] in top_ids[:k]:
                hits[k] += 1
    total = len(pos)
    return {k: hits[k] / total for k in ks}, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-recall", type=int, default=300)
    args = ap.parse_args()

    c = q._load()
    rec, total = recall_at_k(args.n_recall)
    report = (
        f"#03 Personal Shopper — retrieval (RAG), zero-training\n"
        f"Embed backend index | currency={c['currency']} | recall probes={total}\n"
        + "=" * 60 + "\n"
        + "Known-item recall@k (query = product name keywords):\n"
        + "\n".join(f"  @{k}: {v:.3f}" for k, v in rec.items()) + "\n"
    )
    print(report)
    (OUT_DIR / "retrieval_report.txt").write_text(report, encoding="utf-8")

    fig, ax = plt.subplots(figsize=(5, 3.6))
    ax.plot(list(rec.keys()), list(rec.values()), "o-", color="#6d28d9")
    ax.set_xlabel("k"); ax.set_ylabel("relevant@k"); ax.set_ylim(0, 1)
    ax.set_title("Retrieval relevance@k")
    fig.tight_layout(); fig.savefig(FIG_DIR / "recall_at_k.png", dpi=150); plt.close(fig)
    print("Saved ->", (FIG_DIR / "recall_at_k.png").relative_to(ROOT))

    # smoke queries end-to-end
    md = ["# #03 Personal Shopper — sample queries\n",
          f"Model: {q.CHAT_MODEL} | currency: {c['currency']}\n"]
    for query in SMOKE_QUERIES:
        out = q.recommend(query, k=5)
        md.append(f"\n## {query}\n")
        md.append("**Retrieved:**\n")
        for p in out["products"]:
            md.append(f"- [{p.get('domain','')}] {p['name'][:66]} — {p['price']:.2f} "
                      f"{p.get('currency','')} (sim {p['sim']:.3f})")
        md.append(f"\n**Gợi ý (LLM):** {out['answer']}\n")
    (OUT_DIR / "sample_queries.md").write_text("\n".join(md), encoding="utf-8")
    print("Saved ->", (OUT_DIR / "sample_queries.md").relative_to(ROOT))


if __name__ == "__main__":
    main()
