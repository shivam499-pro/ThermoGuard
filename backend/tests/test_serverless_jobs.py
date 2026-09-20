"""Tests for serverless job queue, semantic cache, and vector RAG helpers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.store.cache import MemoryLruCache, semantic_cache_key
from app.store.vector import cosine_similarity, rank_similar


def test_semantic_cache_key_is_stable() -> None:
    a = semantic_cache_key("EVT_1", "PhaseIX", "amazon.nova-lite-v1:0")
    b = semantic_cache_key("EVT_1", "PhaseIX", "amazon.nova-lite-v1:0")
    assert a == b
    assert a != semantic_cache_key("EVT_2", "PhaseIX", "amazon.nova-lite-v1:0")


def test_memory_lru_ttl_and_eviction() -> None:
    cache = MemoryLruCache(max_items=2, ttl_seconds=3600)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_cosine_similarity_and_rank() -> None:
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    ranked = rank_similar([1.0, 0.0], [
        {"event_id": "near", "embedding": [0.9, 0.1]},
        {"event_id": "far", "embedding": [0.0, 1.0]},
    ], top_k=1)
    assert ranked[0][0] == "near"


def test_enqueue_analyst_job_completes_locally() -> None:
    client = TestClient(create_app())
    accepted = client.post("/api/events/EVT_00963466/analyst-jobs")
    assert accepted.status_code == 202
    job_id = accepted.json()["job_id"]
    status = client.get(f"/api/jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "completed"
    assert body["result"]["event_id"] == "EVT_00963466"
    assert body["result"]["risk_score"] == 49.0
    assert body["result"]["risk_tier"] == "MODERATE"


def test_similar_events_endpoint() -> None:
    client = TestClient(create_app())
    res = client.get("/api/events/EVT_00963466/similar?top_k=3")
    assert res.status_code == 200
    body = res.json()
    assert body["event_id"] == "EVT_00963466"
    assert len(body["neighbors"]) == 3
    assert "similarity" in body["neighbors"][0]
