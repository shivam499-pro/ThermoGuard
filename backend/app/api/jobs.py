"""
Async analyst jobs and RAG neighbor lookup.

POST /api/events/{event_id}/analyst-jobs  -> Ingress enqueue (202)
GET  /api/jobs/{job_id}                   -> job status / assembled result
GET  /api/events/{event_id}/similar        -> cosine neighbors from vector store
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.jobs import AnalystJobAccepted, AnalystJobRecord, SimilarEventsResponse
from app.services.event_service import get_event_repository
from app.services.job_service import get_job, new_job_id, put_job, update_job
from app.services.queue_service import enqueue_scoring_job, get_memory_broker
from app.store.vector import embedding_from_detail, rank_similar

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Jobs"])


@router.post(
    "/events/{event_id}/analyst-jobs",
    response_model=AnalystJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_analyst_job(event_id: str) -> AnalystJobAccepted:
    repo = get_event_repository()
    if repo.get_event(event_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thermal event '{event_id}' not found",
        )
    job_id = new_job_id()
    put_job({"job_id": job_id, "event_id": event_id, "status": "queued", "cache_hit": False})
    enqueue_scoring_job(event_id, job_id)

    # Local/dev: drain the in-memory broker immediately so pytest and uvicorn
    # still complete jobs without Worker-Lambda.
    from app.services.bedrock_service import score_event_out_of_band
    import os

    if not os.environ.get("SQS_QUEUE_URL"):
        for message in get_memory_broker().drain():
            import json

            body = json.loads(message["Body"])
            _run_worker(body["event_id"], body["job_id"], score_event_out_of_band)

    return AnalystJobAccepted(job_id=job_id, event_id=event_id)


@router.get("/jobs/{job_id}", response_model=AnalystJobRecord)
async def get_analyst_job(job_id: str) -> AnalystJobRecord:
    record = get_job(job_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )
    return AnalystJobRecord.model_validate(record)


@router.get("/events/{event_id}/similar", response_model=SimilarEventsResponse)
async def similar_events(event_id: str, top_k: int = 5) -> SimilarEventsResponse:
    repo = get_event_repository()
    detail = repo.get_event(event_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thermal event '{event_id}' not found",
        )
    query = embedding_from_detail(detail)
    corpus = []
    for summary in repo.list_events():
        other = repo.get_event(summary.event_id)
        if other is None or other.event_id == event_id:
            continue
        corpus.append(
            {
                "event_id": other.event_id,
                "embedding": embedding_from_detail(other),
                "risk_tier": other.risk_tier,
            }
        )
    neighbors = [
        {"event_id": nid, "similarity": round(score, 4)}
        for nid, score in rank_similar(query, corpus, top_k=top_k)
    ]
    return SimilarEventsResponse(event_id=event_id, neighbors=neighbors)


def _run_worker(event_id: str, job_id: str, scorer) -> None:
    update_job(job_id, status="running")
    try:
        scored = scorer(event_id)
        update_job(
            job_id,
            status="completed",
            result=scored["result"],
            cache_hit=scored["cache_hit"],
        )
    except Exception as exc:
        logger.exception("Worker failed for job %s", job_id)
        update_job(job_id, status="failed", error=str(exc))
