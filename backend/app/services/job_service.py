"""Analyst job persistence: DynamoDB in AWS, in-memory for local/tests."""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_jobs: Dict[str, Dict[str, Any]] = {}


def _use_dynamodb() -> bool:
    return os.environ.get("STORAGE_BACKEND", "file").lower() == "dynamodb"


def new_job_id() -> str:
    return str(uuid.uuid4())


def _serialize(record: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(record)
    result = item.get("result")
    if result is not None and not isinstance(result, str):
        item["result"] = json.dumps(result)
    return item


def _deserialize(record: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(record)
    result = item.get("result")
    if isinstance(result, str):
        try:
            item["result"] = json.loads(result)
        except json.JSONDecodeError:
            pass
    return item


def put_job(record: Dict[str, Any]) -> None:
    if _use_dynamodb():
        from app.store.dynamodb import DynamoJobStore

        DynamoJobStore().put_job(_serialize(record))
        return
    with _lock:
        _jobs[record["job_id"]] = dict(record)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    if _use_dynamodb():
        from app.store.dynamodb import DynamoJobStore

        item = DynamoJobStore().get_job(job_id)
        return _deserialize(item) if item else None
    with _lock:
        record = _jobs.get(job_id)
        return dict(record) if record else None


def update_job(job_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    current = get_job(job_id)
    if current is None:
        return None
    current.update(fields)
    put_job(current)
    return current
