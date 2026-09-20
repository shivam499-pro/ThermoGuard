"""Async analyst job contracts (Ingress-Lambda -> SQS -> Worker-Lambda)."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal["queued", "running", "completed", "failed"]


class AnalystJobAccepted(BaseModel):
    job_id: str
    event_id: str
    status: JobStatus = "queued"
    message: str = "Scoring job queued on the worker pool"

    model_config = ConfigDict(extra="ignore")


class AnalystJobRecord(BaseModel):
    job_id: str
    event_id: str
    status: JobStatus
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    cache_hit: bool = False

    model_config = ConfigDict(extra="ignore")


class SimilarEventsResponse(BaseModel):
    event_id: str
    neighbors: list[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")
