"""
Amazon SQS ingestion buffer.

Ingress-Lambda enqueues analyst jobs; Worker-Lambda drains the queue.
Local/dev uses an in-memory broker so tests never require AWS credentials.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class InMemoryBroker:
    """Process-local queue used when SQS_QUEUE_URL is unset."""

    def __init__(self) -> None:
        self._messages: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def send(self, body: Dict[str, Any]) -> str:
        message_id = str(uuid.uuid4())
        with self._lock:
            self._messages.append({"MessageId": message_id, "Body": json.dumps(body)})
        return message_id

    def drain(self) -> List[Dict[str, Any]]:
        with self._lock:
            batch = list(self._messages)
            self._messages.clear()
        return batch


_memory = InMemoryBroker()


def get_memory_broker() -> InMemoryBroker:
    return _memory


def enqueue_scoring_job(event_id: str, job_id: str) -> str:
    payload = {"event_id": event_id, "job_id": job_id}
    queue_url = os.environ.get("SQS_QUEUE_URL", "")
    if not queue_url:
        logger.info("SQS_QUEUE_URL unset; using in-memory broker for %s", job_id)
        return _memory.send(payload)

    import boto3

    client = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
    response = client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    return str(response.get("MessageId") or job_id)


def parse_sqs_records(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    records = event.get("Records") or []
    parsed: List[Dict[str, Any]] = []
    for record in records:
        body = record.get("body") or record.get("Body") or "{}"
        if isinstance(body, str):
            parsed.append(json.loads(body))
        else:
            parsed.append(body)
    return parsed


def process_queue_batch(
    payloads: List[Dict[str, Any]],
    handler: Callable[[str, str], None],
) -> None:
    for payload in payloads:
        event_id = payload["event_id"]
        job_id = payload["job_id"]
        handler(event_id, job_id)
