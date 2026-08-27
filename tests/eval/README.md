# Retrieval eval suite

Canonical knowledge documents live only in `knowledge_base/`. This folder
holds the eval **dataset**, catalog checks, and opt-in scoring.

`golden_retrieval.json` is not a scoring run. It is the labeled catalog:
each case is a question and the `knowledge_base/` page it should find,
plus the search settings used when scoring.

Do not put the catalog inside `knowledge_base/` (that directory is the
corpus, not queries).

```text
knowledge_base/                 # canonical docs only
tests/eval/                     # this suite
  README.md
  golden_retrieval.json         # eval catalog (questions → expected docs)
  catalog.py                    # typed catalog load
  workflow_dsl.py               # exported retrieval-node settings
  test_golden_catalog.py        # catalog validity (make test)
  evaluate.py                   # live Dify retrieval (make eval)
```

## Recorded retrieval params

These values are stored once in `golden_retrieval.json` metadata:

- `knowledge_base`: `employee-helpdesk`
- `candidate_k`: 10
- `rerank_top_k`: 3
- `score_threshold`: 0.7
- `embedding_model`: `ibm/granite-embedding:30m`
- LLM-as-reranker: TBD / Phase 7; no Cohere/Jina slot

## What `make test` runs

It validates the catalog and exported retrieval settings without calling
Dify.

## What `make eval` runs

It queries the indexed `employee-helpdesk` knowledge base through Dify
and requires each golden document to rank first. The opt-in check needs
the running stack and `DIFY_DATASETS_API_KEY`; it uses local Ollama and
Weaviate, not Yandex. `DIFY_API_BASE_URL` defaults to
`http://localhost:13080/v1`.
