"""
CloudWatch-oriented structured logging.

Lambda and local uvicorn both write to stdout. AWS pipes that stream into
CloudWatch Logs automatically; this formatter keeps records JSON so Insights
queries stay cheap during the hackathon window.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class CloudWatchJsonFormatter(logging.Formatter):
    """Single-line JSON formatter for CloudWatch Logs ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": os.environ.get("APP_NAME", "ThermoGuard"),
        }
        request_id = getattr(record, "aws_request_id", None) or os.environ.get(
            "AWS_LAMBDA_REQUEST_ID"
        )
        if request_id:
            payload["aws_request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Replace root handlers with stdout JSON logging (idempotent)."""
    root = logging.getLogger()
    numeric = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(numeric)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CloudWatchJsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
