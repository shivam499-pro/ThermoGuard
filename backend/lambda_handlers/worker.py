"""Worker-Lambda: SQS scoring queue -> Bedrock assembly out of band."""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.observability import configure_logging
from app.services.bedrock_service import score_event_out_of_band
from app.services.job_service import update_job
from app.services.queue_service import parse_sqs_records

configure_logging()
logger = logging.getLogger(__name__)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    payloads = parse_sqs_records(event)
    failures = []
    for payload in payloads:
        job_id = payload.get("job_id")
        event_id = payload.get("event_id")
        try:
            update_job(job_id, status="running")
            scored = score_event_out_of_band(event_id)
            update_job(
                job_id,
                status="completed",
                result=scored["result"],
                cache_hit=scored["cache_hit"],
            )
        except Exception:
            logger.exception("Worker-Lambda failed job=%s event=%s", job_id, event_id)
            if job_id:
                update_job(job_id, status="failed", error="worker_exception")
            failures.append({"itemIdentifier": payload.get("messageId") or job_id})
    return {"batchItemFailures": failures}
