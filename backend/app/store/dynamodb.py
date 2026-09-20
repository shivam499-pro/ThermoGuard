"""
Amazon DynamoDB persistence for events, jobs, cache, and vectors.

Pay-per-request tables stay at $0 while traffic is inside the AWS free tier /
hackathon validation window. Local development keeps the JSON file repository.
"""

from __future__ import annotations

import json
import logging
import os
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


def to_dynamo(value: Any) -> Any:
    """boto3 DynamoDB resource rejects Python float; coerce to Decimal."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_dynamo(v) for v in value]
    return value


def _json_safe(value: Any) -> Any:
    """Convert DynamoDB Decimal values back to int/float for Pydantic."""
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


class DynamoClientFactory:
    """Lazy boto3 resource factory so unit tests never import AWS by default."""

    def __init__(self, region: Optional[str] = None) -> None:
        self._region = region or os.environ.get("AWS_REGION", "ap-south-1")
        self._resource = None

    def resource(self):
        if self._resource is None:
            import boto3

            self._resource = boto3.resource("dynamodb", region_name=self._region)
        return self._resource


_factory = DynamoClientFactory()


def events_table_name() -> str:
    return os.environ.get("EVENTS_TABLE", "thermoguard-events")


def jobs_table_name() -> str:
    return os.environ.get("JOBS_TABLE", "thermoguard-jobs")


def cache_table_name() -> str:
    return os.environ.get("CACHE_TABLE", "thermoguard-semantic-cache")


def vectors_table_name() -> str:
    return os.environ.get("VECTORS_TABLE", "thermoguard-vectors")


class DynamoEventStore:
    """Read/write split: PK writes, GSI reads by risk_tier / methodology."""

    def __init__(self, table_name: Optional[str] = None) -> None:
        self._table = _factory.resource().Table(table_name or events_table_name())

    def put_event(self, item: Dict[str, Any]) -> None:
        self._table.put_item(Item=to_dynamo(item))

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        response = self._table.get_item(Key={"event_id": event_id})
        item = response.get("Item")
        return _json_safe(item) if item else None

    def list_events(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        scan_kwargs: Dict[str, Any] = {}
        while True:
            response = self._table.scan(**scan_kwargs)
            items.extend(_json_safe(response.get("Items", [])))
            start = response.get("LastEvaluatedKey")
            if not start:
                break
            scan_kwargs["ExclusiveStartKey"] = start
        return items

    def list_by_risk_tier(self, risk_tier: str) -> List[Dict[str, Any]]:
        """Read path via GSI `risk_tier-index` (read/write splitting)."""
        from boto3.dynamodb.conditions import Key

        items: List[Dict[str, Any]] = []
        kwargs: Dict[str, Any] = {
            "IndexName": "risk_tier-index",
            "KeyConditionExpression": Key("risk_tier").eq(risk_tier),
        }
        while True:
            response = self._table.query(**kwargs)
            items.extend(_json_safe(response.get("Items", [])))
            start = response.get("LastEvaluatedKey")
            if not start:
                break
            kwargs["ExclusiveStartKey"] = start
        return items


class DynamoJobStore:
    def __init__(self, table_name: Optional[str] = None) -> None:
        self._table = _factory.resource().Table(table_name or jobs_table_name())

    def put_job(self, item: Dict[str, Any]) -> None:
        self._table.put_item(Item=to_dynamo(item))

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        response = self._table.get_item(Key={"job_id": job_id})
        item = response.get("Item")
        return _json_safe(item) if item else None

    def list_by_event(self, event_id: str) -> List[Dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        response = self._table.query(
            IndexName="event_id-index",
            KeyConditionExpression=Key("event_id").eq(event_id),
        )
        return _json_safe(response.get("Items", []))


class DynamoCacheStore:
    def __init__(self, table_name: Optional[str] = None) -> None:
        self._table = _factory.resource().Table(table_name or cache_table_name())

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        response = self._table.get_item(Key={"cache_key": cache_key})
        item = response.get("Item")
        if not item:
            return None
        return json.loads(item["payload"]) if isinstance(item.get("payload"), str) else _json_safe(item.get("payload"))

    def put(self, cache_key: str, payload: Dict[str, Any], ttl_epoch: int) -> None:
        self._table.put_item(
            Item={
                "cache_key": cache_key,
                "payload": json.dumps(payload),
                "expires_at": ttl_epoch,
            }
        )


class DynamoVectorStore:
    """Cost-effective vector rows: 5-dimension score embeddings in DynamoDB."""

    def __init__(self, table_name: Optional[str] = None) -> None:
        self._table = _factory.resource().Table(table_name or vectors_table_name())

    def put_vector(self, event_id: str, embedding: Iterable[float], metadata: Dict[str, Any]) -> None:
        self._table.put_item(
            Item=to_dynamo(
                {
                    "event_id": event_id,
                    "embedding": list(embedding),
                    **metadata,
                }
            )
        )

    def scan_vectors(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        kwargs: Dict[str, Any] = {}
        while True:
            response = self._table.scan(**kwargs)
            items.extend(_json_safe(response.get("Items", [])))
            start = response.get("LastEvaluatedKey")
            if not start:
                break
            kwargs["ExclusiveStartKey"] = start
        return items
