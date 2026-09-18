"""
ThermoGuard — shared Pydantic schemas for the backend API.

Only foundation-level schemas live here.
Domain-specific schemas (risk analysis, satellite events, etc.)
will be added in later commits within their own modules.
"""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response body for the /health endpoint."""

    status: str
    version: str
    service: str
