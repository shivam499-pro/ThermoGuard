"""Seed DynamoDB events + vector tables from the bundled pilot JSON."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.event_service import EventRepository  # noqa: E402
from app.store.vector import embedding_from_detail  # noqa: E402


def seed() -> None:
    os.environ.setdefault("STORAGE_BACKEND", "file")
    repo = EventRepository()
    from app.store.dynamodb import DynamoEventStore, DynamoVectorStore

    events = DynamoEventStore()
    vectors = DynamoVectorStore()
    for summary in repo.list_events():
        detail = repo.get_event(summary.event_id)
        assert detail is not None
        events.put_event(
            {
                "event_id": summary.event_id,
                "risk_tier": summary.risk_tier,
                "methodology_version": summary.methodology_version,
                "summary": summary.model_dump(),
                "detail": detail.model_dump(),
            }
        )
        vectors.put_vector(
            summary.event_id,
            embedding_from_detail(detail),
            {
                "risk_tier": summary.risk_tier,
                "methodology_version": summary.methodology_version,
            },
        )
    print(f"Seeded {repo.get_event_count()} events into DynamoDB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"))
    args = parser.parse_args()
    os.environ["AWS_REGION"] = args.region
    seed()
