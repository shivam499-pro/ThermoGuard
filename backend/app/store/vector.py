"""
Vector / RAG store.

Hackathon-zero path: store 5-dimension deterministic score vectors in DynamoDB
and rank with cosine similarity in Lambda (no OpenSearch bill).

Optional later path: the same embedding shape loads into Aurora PostgreSQL
pgvector (`infra/sql/pgvector.sql`) without changing API contracts.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from app.schemas.events import EventDetail


def embedding_from_detail(detail: EventDetail) -> List[float]:
    """Five locked dimension scores as a unit-length RAG vector."""
    raw = [
        detail.dimensions.thermal.normalized_score,
        detail.dimensions.persistence.normalized_score,
        detail.dimensions.industrial.normalized_score,
        detail.dimensions.spatial.normalized_score,
        detail.dimensions.spectral.normalized_score,
    ]
    return _l2_normalize(raw)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _l2_normalize(values: Iterable[float]) -> List[float]:
    vector = [float(v) for v in values]
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return vector
    return [v / norm for v in vector]


def rank_similar(
    query: Sequence[float],
    corpus: List[Dict[str, Any]],
    top_k: int = 5,
) -> List[Tuple[str, float]]:
    scored: List[Tuple[str, float]] = []
    for row in corpus:
        embedding = row.get("embedding") or []
        event_id = str(row.get("event_id", ""))
        scored.append((event_id, cosine_similarity(query, embedding)))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]
