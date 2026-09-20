"""Ingress-Lambda: Amazon API Gateway HTTP API -> FastAPI (Mangum)."""

from __future__ import annotations

from app.main import handler as lambda_handler

handler = lambda_handler
