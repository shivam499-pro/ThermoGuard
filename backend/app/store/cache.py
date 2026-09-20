"""
Semantic cache for repetitive Bedrock analyst lookups.

Two layers, both free on the hackathon path:
  1. Process-local LRU (Lambda execution environment reuse).
  2. Optional DynamoDB table with TTL (shared across warm/cold starts).

Cache keys are hashes of event_id + methodology_version + model_id so identical
evidence never re-invokes the model.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

logger = logging.getLogger(__name__)


def semantic_cache_key(event_id: str, methodology_version: str, model_id: str) -> str:
    raw = f"{event_id}|{methodology_version}|{model_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class MemoryLruCache:
    """Tiny in-process LRU used as Lambda operational-layer cache."""

    def __init__(self, max_items: int = 256, ttl_seconds: int = 3600) -> None:
        self._max_items = max_items
        self._ttl = ttl_seconds
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at < now:
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return value

    def put(self, key: str, value: Any) -> None:
        now = time.time()
        with self._lock:
            self._data[key] = (now + self._ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self._max_items:
                self._data.popitem(last=False)


_memory = MemoryLruCache()


def get_memory_cache() -> MemoryLruCache:
    return _memory
