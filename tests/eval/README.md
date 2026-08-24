# Retrieval eval suite

Canonical knowledge documents live only in `knowledge_base/`. This folder
holds the eval **dataset** and the cheap pytest checks on that dataset.
Pytest collects `tests/`, so those checks run with the rest of the suite.

`golden_retrieval.json` is not a scoring run. It is the labeled catalog:
each case is a question and the `knowledge_base/` page it should find,
plus the search settings we will use when we later measure retrieval.
Keep it here so catalog tests and a future scoring test load one file.

Do not put the catalog inside `knowledge_base/` (that directory is the
corpus, not queries).

```text
knowledge_base/                 # canonical docs only
tests/eval/                     # this suite
  README.md
  golden_retrieval.json         # eval catalog (questions → expected docs)
  test_golden_catalog.py        # catalog validity only (no embeddings)
```

## Recorded retrieval params

These values are stored in `golden_retrieval.json` metadata:

- `candidate_k`: 10
- `rerank_top_k`: 3
- `score_threshold`: 0.7
- `embedding_model`: `granite-embedding:30m`
- LLM-as-reranker: TBD / Phase 7; no Cohere/Jina slot

## What merge-gate tests do

`test_golden_catalog.py` checks that the catalog is usable (paths,
coverage, unique queries, recorded params). It does **not** call Ollama,
Dify, or Weaviate.

Bi-encoder measurement against these goldens is a later Phase 6 step.
Ingest into the `employee-helpdesk` dataset is also later.
