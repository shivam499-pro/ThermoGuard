"""
ThermoGuard — Pilot Events API Router.

Exposes read-only access to the curated 100-event pilot cohort:
  - GET /events: Lightweight summary collection for GIS map rendering and tables.
  - GET /events/{event_id}: Comprehensive detail record with full score decomposition,
    analyst interpretations, and operational recommendations.

Invariants:
  - Deterministic read-only access to validated pilot cohort.
  - No recomputation of risk scores or confidence values.
  - Returns HTTP 404 for unknown event IDs (never 500).
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.events import EventDetail, EventListResponse
from app.services.event_service import EventRepository, get_event_repository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Events"])


@router.get(
    "/events",
    response_model=EventListResponse,
    summary="List pilot thermal events",
    description=(
        "Returns lightweight summaries of all 100 curated pilot thermal events, "
        "including GIS coordinates, bounding boxes, risk scores, tiers, and "
        "operational recommendations. Suitable for map rendering and table views."
    ),
)
async def list_events(
    repo: EventRepository = Depends(get_event_repository),
) -> EventListResponse:
    """Retrieve all curated pilot events as lightweight summaries."""
    events = repo.list_events()
    return EventListResponse(count=len(events), events=events)


@router.get(
    "/events/{event_id}",
    response_model=EventDetail,
    summary="Get pilot thermal event detail",
    description=(
        "Returns the complete investigation record for a single event by ID, "
        "including full mathematical 5-dimension decompositions, raw evidence "
        "traces, plain-language analyst interpretations, and operational recommendations."
    ),
    responses={
        404: {
            "description": "Event not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Thermal event 'EVT_99999999' not found"}
                }
            },
        }
    },
)
async def get_event(
    event_id: str,
    repo: EventRepository = Depends(get_event_repository),
) -> EventDetail:
    """Retrieve full detail for a single thermal event."""
    event = repo.get_event(event_id)
    if event is None:
        logger.info("Requested event not found: %s", event_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thermal event '{event_id}' not found",
        )
    return event
