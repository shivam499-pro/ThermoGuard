"""
Tests for the ThermoGuard backend foundation.

Covers:
  - /health endpoint returns HTTP 200
  - /health response body matches HealthResponse schema
  - Unknown routes return 404
  - ValueError handler returns 422 with correct structure
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Return a test client for a freshly created app instance."""
    return TestClient(create_app())


# ── /health ───────────────────────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_body(self, client: TestClient) -> None:
        data = client.get("/health").json()
        assert data["status"] == "ok"
        assert data["service"] == "ThermoGuard"
        assert "version" in data

    def test_health_version_is_string(self, client: TestClient) -> None:
        data = client.get("/health").json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0


# ── 404 for unknown routes ────────────────────────────────────────────────────


class TestNotFound:
    def test_unknown_route_returns_404(self, client: TestClient) -> None:
        response = client.get("/does-not-exist")
        assert response.status_code == 404


# ── Global exception handler: ValueError → 422 ───────────────────────────────


class TestExceptionHandlers:
    def test_value_error_handler_returns_422(self, client: TestClient) -> None:
        """
        Register a transient test route that raises ValueError,
        verify the global handler returns 422 with the right shape.
        """
        app = create_app()

        @app.get("/test-value-error")
        async def _raise() -> None:
            raise ValueError("synthetic test error")

        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get("/test-value-error")
            assert resp.status_code == 422
            body = resp.json()
            assert body["type"] == "validation_error"
            assert "synthetic test error" in body["detail"]
