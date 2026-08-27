"""Catalog validity: paths, coverage, unique queries, recorded params."""

from __future__ import annotations

from pathlib import Path

from . import catalog, evaluate


def test_workflow_retrieval_matches_catalog() -> None:
    """The exported Dify node matches the catalog's recorded settings."""
    evaluate.validate_workflow_config(catalog.load_catalog()["metadata"])


def test_expected_docs_exist_under_knowledge_base() -> None:
    """Each case points at a real Markdown file inside the corpus directory."""
    knowledge_root = catalog.KNOWLEDGE_DIR.resolve()
    for case in catalog.load_catalog()["cases"]:
        expected_doc = case["expected_doc"]
        assert expected_doc.endswith(".md")
        relative = Path(expected_doc)
        assert not relative.is_absolute()
        assert relative.parts[0] == "knowledge_base"
        assert ".." not in relative.parts
        path = (catalog.REPO_ROOT / relative).resolve()
        assert path.is_relative_to(knowledge_root)
        assert path.is_file()


def test_every_corpus_doc_has_a_golden_case() -> None:
    """Every topic page is the expected_doc of at least one case."""
    corpus = {
        path.relative_to(catalog.REPO_ROOT).as_posix()
        for path in catalog.list_topic_doc_paths()
    }
    expected = {
        case["expected_doc"] for case in catalog.load_catalog()["cases"]
    }
    assert corpus <= expected


def test_queries_are_unique_and_non_empty() -> None:
    """Questions are non-empty and not reused."""
    queries = [case["query"] for case in catalog.load_catalog()["cases"]]
    assert all(query.strip() for query in queries)
    assert len(queries) == len(set(queries))
