"""Evaluate golden queries through Dify's indexed knowledge retrieval API."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple, cast

import httpx
from pydantic import AnyHttpUrl, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import catalog, workflow_dsl

_APP_ENV_PATH = catalog.REPO_ROOT / ".env"
_REQUEST_TIMEOUT_SECONDS = 180.0
_DATASET_PAGE_LIMIT = 100
_ERROR_BODY_PREVIEW_CHARS = 300
_FIRST_DATASET_PAGE = 1
_EXPECTED_DATASET_COUNT = 1


class EvalError(RuntimeError):
    """Dify or the committed retrieval configuration is unusable."""


class EvalSettings(BaseSettings):
    """Opt-in Dify Knowledge API settings from the root environment."""

    model_config = SettingsConfigDict(
        env_file=_APP_ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dify_api_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:13080/v1")
    dify_datasets_api_key: SecretStr


class RankedCase(NamedTuple):
    """One golden query ranked by Dify against indexed chunks."""

    case_id: str
    expected_doc: str
    expected_score: float | None
    top_doc: str | None


def load_eval_settings() -> EvalSettings:
    """Load validated settings without manually parsing dotenv syntax."""
    try:
        return EvalSettings.model_validate({})
    except ValidationError as exc:
        raise EvalError(
            f"invalid eval settings; check DIFY_API_BASE_URL and "
            f"DIFY_DATASETS_API_KEY in {_APP_ENV_PATH}"
        ) from exc


def build_api_headers(settings: EvalSettings) -> dict[str, str]:
    """Build Dify authorization without exposing the knowledge API key."""
    api_key = settings.dify_datasets_api_key.get_secret_value().strip()
    if api_key.lower().startswith("bearer "):
        api_key = api_key[7:].strip()
    return {"Authorization": f"Bearer {api_key}"}


def parse_response(
    response: httpx.Response, operation: str
) -> dict[str, object]:
    """Validate one Dify API response as a JSON object."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip()[:_ERROR_BODY_PREVIEW_CHARS]
        raise EvalError(
            f"Dify {operation} HTTP {exc.response.status_code}: {detail}"
        ) from exc
    try:
        body: object = response.json()
    except ValueError as exc:
        raise EvalError(f"Dify {operation} response is not JSON") from exc
    if not isinstance(body, dict):
        raise EvalError(f"Dify {operation} response is not an object")
    return cast(dict[str, object], body)


def resolve_knowledge_base_id(
    client: httpx.Client,
    api_url: str,
    headers: dict[str, str],
    expected_name: str,
) -> str:
    """Find exactly one accessible Dify knowledge base by exact name."""
    matches: list[str] = []
    # Dify's dataset API uses one-based pagination.
    page = _FIRST_DATASET_PAGE
    while True:
        try:
            response = client.get(
                f"{api_url}/datasets",
                headers=headers,
                params={"page": page, "limit": _DATASET_PAGE_LIMIT},
            )
        except httpx.RequestError as exc:
            raise EvalError(
                f"Cannot reach Dify at {api_url}. Is the stack up?"
            ) from exc
        body = parse_response(response, "list knowledge bases")
        datasets = body.get("data")
        if not isinstance(datasets, list):
            raise EvalError("Dify knowledge-base list has no data array")
        for item in datasets:
            if not isinstance(item, dict) or item.get("name") != expected_name:
                continue
            dataset_id = item.get("id")
            if not isinstance(dataset_id, str) or not dataset_id:
                raise EvalError("Dify knowledge base has no id")
            matches.append(dataset_id)
        has_more = body.get("has_more")
        if not isinstance(has_more, bool):
            raise EvalError("Dify knowledge-base list has no has_more flag")
        if not has_more:
            break
        page += 1
    if len(matches) != _EXPECTED_DATASET_COUNT:
        raise EvalError(
            f"expected exactly one accessible knowledge base named "
            f"{expected_name!r}, found {len(matches)}"
        )
    # The cardinality check makes the first item the only valid match.
    return matches[0]


def load_ranked_chunks(
    client: httpx.Client,
    api_url: str,
    headers: dict[str, str],
    dataset_id: str,
    query: str,
    metadata: catalog.CatalogMetadata,
) -> list[tuple[str, float]]:
    """Retrieve and validate ordered `(document name, score)` chunks."""
    retrieval_model = {
        "search_method": "semantic_search",
        "reranking_enable": False,
        "top_k": metadata["candidate_k"],
        "score_threshold_enabled": True,
        "score_threshold": metadata["score_threshold"],
    }
    try:
        response = client.post(
            f"{api_url}/datasets/{dataset_id}/retrieve",
            headers=headers,
            json={"query": query, "retrieval_model": retrieval_model},
        )
    except httpx.RequestError as exc:
        raise EvalError(
            f"Cannot retrieve from Dify at {api_url}. Is the stack up?"
        ) from exc
    body = parse_response(response, "retrieve")
    records = body.get("records")
    if not isinstance(records, list):
        raise EvalError("Dify retrieve response has no records array")

    ranked: list[tuple[str, float]] = []
    for record in records:
        if not isinstance(record, dict):
            raise EvalError("Dify retrieval record is not an object")
        segment = record.get("segment")
        score = record.get("score")
        if (
            not isinstance(segment, dict)
            or isinstance(score, bool)
            or not isinstance(score, (int, float))
        ):
            raise EvalError(
                "Dify retrieval record has invalid segment or score"
            )
        document = segment.get("document")
        if not isinstance(document, dict):
            raise EvalError("Dify retrieval segment has no document")
        document_name = document.get("name")
        if not isinstance(document_name, str) or not document_name:
            raise EvalError("Dify retrieval document has no name")
        ranked.append((document_name, float(score)))
    return ranked


def validate_workflow_config(metadata: catalog.CatalogMetadata) -> None:
    """Require the exported node to match the golden retrieval contract."""
    config = workflow_dsl.load_workflow_retrieval_config()
    mismatches: list[str] = []
    if len(config["dataset_ids"]) != _EXPECTED_DATASET_COUNT:
        mismatches.append(
            f"dataset count={len(config['dataset_ids'])}, "
            f"expected {_EXPECTED_DATASET_COUNT}"
        )
    for field in ("candidate_k", "score_threshold", "embedding_model"):
        if config[field] != metadata[field]:
            mismatches.append(
                f"{field}={config[field]!r}, expected {metadata[field]!r}"
            )
    if mismatches:
        raise EvalError("workflow retrieval mismatch: " + "; ".join(mismatches))


def rank_catalog_cases() -> list[RankedCase]:
    """Run every golden query through the indexed Dify knowledge base."""
    loaded = catalog.load_catalog()
    metadata = loaded["metadata"]
    validate_workflow_config(metadata)
    settings = load_eval_settings()
    api_url = str(settings.dify_api_base_url).rstrip("/")
    headers = build_api_headers(settings)
    with httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
        dataset_id = resolve_knowledge_base_id(
            client,
            api_url,
            headers,
            metadata["knowledge_base"],
        )
        rows: list[RankedCase] = []
        for case in loaded["cases"]:
            chunks = load_ranked_chunks(
                client,
                api_url,
                headers,
                dataset_id,
                case["query"],
                metadata,
            )
            expected_doc = Path(case["expected_doc"]).name
            expected_score = next(
                (score for name, score in chunks if name == expected_doc),
                None,
            )
            rows.append(
                RankedCase(
                    case_id=case["id"],
                    expected_doc=expected_doc,
                    expected_score=expected_score,
                    top_doc=None if not chunks else chunks[0][0],
                )
            )
    return rows


def format_score_table(rows: list[RankedCase]) -> str:
    """Format each expected document and its best Dify score."""
    header = f"{'id':<28}  {'expected':<22}  {'score':>5}"
    rule = "=" * len(header)
    lines = [rule, header]
    for row in rows:
        score = (
            "-" if row.expected_score is None else f"{row.expected_score:.3f}"
        )
        lines.append(f"{row.case_id:<28}  {row.expected_doc:<22}  {score:>5}")
    lines.append(rule)
    return "\n".join(lines)


def main() -> int:
    """Return nonzero so Make exposes live retrieval regressions."""
    try:
        rows = rank_catalog_cases()
    except (EvalError, workflow_dsl.WorkflowConfigError, AssertionError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(format_score_table(rows))
    failures = [
        f"{row.case_id}: top={row.top_doc!r}, expected={row.expected_doc!r}"
        for row in rows
        if row.top_doc != row.expected_doc
    ]
    if failures:
        print("; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
