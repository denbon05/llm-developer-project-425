"""Load the golden retrieval catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent.parent
CATALOG_PATH = EVAL_DIR / "golden_retrieval.json"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge_base"


class CatalogMetadata(TypedDict):
    """Search settings stored next to the cases in the catalog JSON."""

    knowledge_base: str
    candidate_k: int
    score_threshold: float
    embedding_model: str


class GoldenCase(TypedDict):
    """One labeled pair: a question and the page it should retrieve."""

    id: str
    query: str
    expected_doc: str


class GoldenCatalog(TypedDict):
    """Root shape of the eval catalog after a typed load."""

    metadata: CatalogMetadata
    cases: list[GoldenCase]


def _parse_metadata(raw: object) -> CatalogMetadata:
    """Require the recorded knowledge and search fields."""
    assert isinstance(raw, dict)
    knowledge_base = raw["knowledge_base"]
    candidate_k = raw["candidate_k"]
    score_threshold = raw["score_threshold"]
    embedding_model = raw["embedding_model"]
    assert isinstance(knowledge_base, str)
    assert isinstance(candidate_k, int)
    assert isinstance(score_threshold, float)
    assert isinstance(embedding_model, str)
    return {
        "knowledge_base": knowledge_base,
        "candidate_k": candidate_k,
        "score_threshold": score_threshold,
        "embedding_model": embedding_model,
    }


def _parse_case(raw: object) -> GoldenCase:
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


def load_catalog() -> GoldenCatalog:
    """Parse CATALOG_PATH into a typed catalog."""
    payload: object = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    cases_raw = payload["cases"]
    assert isinstance(cases_raw, list)
    return {
        "metadata": _parse_metadata(payload["metadata"]),
        "cases": [_parse_case(item) for item in cases_raw],
    }


def list_topic_doc_paths() -> list[Path]:
    """Topic Markdown pages in the corpus, excluding the corpus README."""
    return sorted(
        path for path in KNOWLEDGE_DIR.glob("*.md") if path.name != "README.md"
    )
