"""Read retrieval settings from the exported Dify workflow."""

from __future__ import annotations

from typing import TypedDict

import yaml

from . import catalog

WORKFLOW_DSL_PATH = catalog.REPO_ROOT / "dify" / "apps" / "email_helpdesk.yml"


class WorkflowConfigError(ValueError):
    """The exported workflow has an unusable retrieval configuration."""


class WorkflowRetrievalConfig(TypedDict):
    """Phase 6 settings exported by the Knowledge Retrieval node."""

    dataset_ids: list[str]
    candidate_k: int
    score_threshold: float
    embedding_model: str
    is_reranking_enabled: bool


def load_workflow_retrieval_config() -> WorkflowRetrievalConfig:
    """Return settings from the workflow's sole Knowledge Retrieval node."""
    payload: object = yaml.safe_load(
        WORKFLOW_DSL_PATH.read_text(encoding="utf-8")
    )
    if not isinstance(payload, dict):
        raise WorkflowConfigError("workflow DSL root is not a mapping")
    workflow = payload.get("workflow")
    if not isinstance(workflow, dict):
        raise WorkflowConfigError("workflow DSL has no workflow mapping")
    graph = workflow.get("graph")
    if not isinstance(graph, dict):
        raise WorkflowConfigError("workflow DSL has no graph mapping")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise WorkflowConfigError("workflow DSL graph has no node list")

    retrieval_nodes = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data")
        if isinstance(data, dict) and data.get("type") == "knowledge-retrieval":
            retrieval_nodes.append(data)
    if len(retrieval_nodes) != 1:
        raise WorkflowConfigError(
            "workflow DSL must contain exactly one Knowledge Retrieval node"
        )

    data = retrieval_nodes[0]
    dataset_ids = data.get("dataset_ids")
    settings = data.get("multiple_retrieval_config")
    if not isinstance(dataset_ids, list) or not all(
        isinstance(dataset_id, str) and dataset_id for dataset_id in dataset_ids
    ):
        raise WorkflowConfigError("retrieval dataset_ids must be strings")
    if not isinstance(settings, dict):
        raise WorkflowConfigError("retrieval settings are missing")

    candidate_k = settings.get("top_k")
    score_threshold = settings.get("score_threshold")
    is_reranking_enabled = settings.get("reranking_enable")
    weights = settings.get("weights")
    if isinstance(candidate_k, bool) or not isinstance(candidate_k, int):
        raise WorkflowConfigError("retrieval top_k must be an integer")
    if isinstance(score_threshold, bool) or not isinstance(
        score_threshold, (int, float)
    ):
        raise WorkflowConfigError("retrieval score_threshold must be numeric")
    if not isinstance(is_reranking_enabled, bool):
        raise WorkflowConfigError("retrieval reranking_enable must be boolean")
    if not isinstance(weights, dict):
        raise WorkflowConfigError("retrieval weights are missing")

    keyword_settings = weights.get("keyword_setting")
    vector_settings = weights.get("vector_setting")
    if not isinstance(keyword_settings, dict) or not isinstance(
        vector_settings, dict
    ):
        raise WorkflowConfigError("retrieval vector weights are missing")
    if (
        keyword_settings.get("keyword_weight") != 0
        or vector_settings.get("vector_weight") != 1
    ):
        raise WorkflowConfigError("retrieval must use vector search only")
    embedding_model = vector_settings.get("embedding_model_name")
    if not isinstance(embedding_model, str) or not embedding_model:
        raise WorkflowConfigError("retrieval embedding model is missing")

    return {
        "dataset_ids": dataset_ids,
        "candidate_k": candidate_k,
        "score_threshold": float(score_threshold),
        "embedding_model": embedding_model,
        "is_reranking_enabled": is_reranking_enabled,
    }
