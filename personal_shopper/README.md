# #03 — Personal Shopper (RAG, no training)

Answer natural-language shopping queries with top-K product picks —
retrieval-augmented generation, no chat UI (a callable `recommend()`).

- **Approach:** embed the catalog → cosine-retrieve top-K for a query → LLM writes
  a short recommendation grounded **only** in the retrieved products.
- **Data:** ASOS clothing catalog (English, GBP), 30k products. A Tiki catalog is
  auto-detected if present.
- **Backend:** OpenAI `text-embedding-3-small` + `gpt-4o-mini` (default), or Ollama
  `bge-m3` + `qwen2.5:7b` — set in `../.env`.

## Run
```bash
python personal_shopper/src/01_build_index.py --max-rows 6000
python personal_shopper/src/03_evaluate.py --n-recall 300
python personal_shopper/src/02_query.py          # demo queries
```

## Results (ASOS)
Known-item recall@k (query = product-name keywords):
| k | recall |
|---|---|
| @1 | 0.873 |
| @3 | 0.960 |
| @5 | 0.977 |
| @10 | 0.990 |

Generations are grounded and relevant — e.g. *"warm winter coat for women"* returns
actual puffer/wrap coats. Full samples in
[`outputs/sample_queries.md`](outputs/sample_queries.md); metric in
[`outputs/retrieval_report.txt`](outputs/retrieval_report.txt), `figures/recall_at_k.png`.

## Serve
`02_query.recommend(query, k=5) -> {'query', 'products', 'answer'}`
