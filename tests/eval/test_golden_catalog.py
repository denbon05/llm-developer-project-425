"""Check that golden_retrieval.json is a valid catalog.

This file does not test retrieval and does not run an embedding model.
The JSON is the eval dataset: employee-like questions paired with the
knowledge_base/ page each question should find. Later scoring will load
the same catalog. These tests only fail if that file is unusable
(wrong search settings, missing paths, blank or duplicate questions).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

# Catalog and corpus live beside this test / at the repo root.
_EVAL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_DIR.parents[1]
_CATALOG_PATH = _EVAL_DIR / "golden_retrieval.json"
_KNOWLEDGE_DIR = _REPO_ROOT / "knowledge_base"
_README_NAME = "README.md"

# Recorded search settings. The JSON metadata must match these so later
# measurement cannot silently change k, threshold, or the embedding model.
_CANDIDATE_K = 10
_RERANK_TOP_K = 3
_SCORE_THRESHOLD = 0.7
_EMBEDDING_MODEL = "granite-embedding:30m"


class CatalogMetadata(TypedDict):
    """Search settings stored next to the cases in the catalog JSON."""

    candidate_k: int
    rerank_top_k: int
    score_threshold: float
    embedding_model: str


class GoldenCase(TypedDict):
    """One labeled pair: a question and the page it should retrieve."""

    id: str
    query: str
    expected_doc: str


class GoldenCatalog(TypedDict):
    """Root shape of golden_retrieval.json after a typed load."""

    metadata: CatalogMetadata
    cases: list[GoldenCase]


def _as_metadata(raw: object) -> CatalogMetadata:
    """Require the four recorded search fields with the expected types."""
    assert isinstance(raw, dict)
    candidate_k = raw["candidate_k"]
    rerank_top_k = raw["rerank_top_k"]
    score_threshold = raw["score_threshold"]
    embedding_model = raw["embedding_model"]
    assert isinstance(candidate_k, int)
    assert isinstance(rerank_top_k, int)
    assert isinstance(score_threshold, float)
    assert isinstance(embedding_model, str)
    return {
        "candidate_k": candidate_k,
        "rerank_top_k": rerank_top_k,
        "score_threshold": score_threshold,
        "embedding_model": embedding_model,
    }


def _as_case(raw: object) -> GoldenCase:
    """Require id, query, and expected_doc to be strings."""
    assert isinstance(raw, dict)
    case_id = raw["id"]
    query = raw["query"]
    expected_doc = raw["expected_doc"]
    assert isinstance(case_id, str)
    assert isinstance(query, str)
    assert isinstance(expected_doc, str)
    return {
        "id": case_id,
        "query": query,
        "expected_doc": expected_doc,
    }


def _load_catalog() -> GoldenCatalog:
    """Read golden_retrieval.json from this directory."""
    payload: object = json.loads(
        _CATALOG_PATH.read_text(encoding="utf-8"),
    )
    assert isinstance(payload, dict)
    cases_raw = payload["cases"]
    assert isinstance(cases_raw, list)
    return {
        "metadata": _as_metadata(payload["metadata"]),
        "cases": [_as_case(item) for item in cases_raw],
    }


def test_recorded_retrieval_params() -> None:
    """JSON metadata still records the agreed search settings.

    candidate_k is how many nearest chunks to keep, rerank_top_k how many
    survive rerank, score_threshold the cutoff, embedding_model the local
    bi-encoder tag. This is a drift guard, not a model run.
    """
    metadata = _load_catalog()["metadata"]
    assert metadata["candidate_k"] == _CANDIDATE_K
    assert metadata["rerank_top_k"] == _RERANK_TOP_K
    assert metadata["score_threshold"] == _SCORE_THRESHOLD
    assert metadata["embedding_model"] == _EMBEDDING_MODEL


def test_expected_docs_exist_under_knowledge_base() -> None:
    """Each case points at a real Markdown file under knowledge_base/.

    A typo or a move of a page would otherwise only show up when we try
    to score retrieval. Reject absolute paths and `..` so the catalog
    cannot escape the corpus directory.
    """
    knowledge_root = _KNOWLEDGE_DIR.resolve()
    for case in _load_catalog()["cases"]:
        expected_doc = case["expected_doc"]
        assert expected_doc.endswith(".md")
        relative = Path(expected_doc)
        assert not relative.is_absolute()
        assert relative.parts[0] == "knowledge_base"
        assert ".." not in relative.parts
        path = (_REPO_ROOT / relative).resolve()
        assert path.is_relative_to(knowledge_root)
        assert path.is_file()


def test_every_corpus_doc_has_a_golden_case() -> None:
    """Every topic page is the expected_doc of at least one case.

    README.md is not a topic page. This is a coverage policy for the
    current corpus (do not leave an unevaluated article), not a general
    retrieval rule. Drop or narrow it if a page should exist without a
    golden question.
    """
    corpus = {
        path.relative_to(_REPO_ROOT).as_posix()
        for path in _KNOWLEDGE_DIR.glob("*.md")
        if path.name != _README_NAME
    }
    expected = {case["expected_doc"] for case in _load_catalog()["cases"]}
    assert corpus <= expected


def test_queries_are_unique_and_non_empty() -> None:
    """Questions are usable labels: not blank, and not reused.

    The same question with two expected docs would make the catalog
    undefined. Empty strings are not employee questions.
    """
    queries = [case["query"] for case in _load_catalog()["cases"]]
    assert all(query.strip() for query in queries)
    assert len(queries) == len(set(queries))
