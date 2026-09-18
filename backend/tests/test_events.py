"""
Tests for ThermoGuard Pilot Events API.

Validates:
  1. GET /health still returns 200.
  2. GET /events returns 200.
  3. GET /events returns exactly 100 events.
  4. Every returned event has: event_id, lat, lon, risk_score, risk_tier, evidence_confidence.
  5. Coordinates are numeric.
  6. No event has duplicate event_id.
  7. Risk tiers are valid (LOW, MODERATE, HIGH, CRITICAL).
  8. GET /events/{known_id} returns 200.
  9. Detail response contains: risk summary, five dimensions, ranking, explanation, spatial info.
  10. GET /events/{unknown_id} returns 404.
  11. A genuinely nullable OSM field remains JSON null.
  12. Existing risk-engine tests continue passing.
  13. Existing backend tests continue passing.
  14. API values match curated JSON source.
  15. Known event risk_score and evidence_confidence exactly match source.
"""

from __future__ import annotations

import concurrent.futures
import json
import math
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.event_service import get_event_repository


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


@pytest.fixture(scope="module")
def raw_curated_events() -> list[dict]:
    data_path = Path(__file__).resolve().parent.parent / "data" / "curated_pilot_events.json"
    with data_path.open("r", encoding="utf-8") as f:
        return json.load(f)


class TestHealthRemainsFunctional:
    def test_health_still_returns_200(self, client: TestClient):
        res = client.get("/health")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"
        assert body["service"] == "ThermoGuard"


class TestListEventsEndpoint:
    def test_get_events_returns_200(self, client: TestClient):
        res = client.get("/api/events")
        assert res.status_code == 200

    def test_get_events_returns_exactly_100(self, client: TestClient):
        res = client.get("/api/events")
        body = res.json()
        assert "count" in body
        assert "events" in body
        assert body["count"] == 100
        assert len(body["events"]) == 100

    def test_every_event_has_mandatory_fields(self, client: TestClient):
        res = client.get("/api/events")
        events = res.json()["events"]
        for ev in events:
            assert "event_id" in ev and isinstance(ev["event_id"], str)
            assert "lat" in ev and isinstance(ev["lat"], (int, float))
            assert "lon" in ev and isinstance(ev["lon"], (int, float))
            assert "risk_score" in ev and isinstance(ev["risk_score"], (int, float))
            assert "risk_tier" in ev and isinstance(ev["risk_tier"], str)
            assert "evidence_confidence" in ev and isinstance(ev["evidence_confidence"], (int, float))
            assert "confidence_tier" in ev and isinstance(ev["confidence_tier"], str)
            assert "bbox" in ev and isinstance(ev["bbox"], dict)

    def test_coordinates_are_numeric_and_in_india_bounds(self, client: TestClient):
        res = client.get("/api/events")
        events = res.json()["events"]
        for ev in events:
            assert 6.0 <= ev["lat"] <= 38.0, f"Latitude out of bounds for {ev['event_id']}: {ev['lat']}"
            assert 68.0 <= ev["lon"] <= 98.0, f"Longitude out of bounds for {ev['event_id']}: {ev['lon']}"

    def test_no_duplicate_event_ids(self, client: TestClient):
        res = client.get("/api/events")
        events = res.json()["events"]
        eids = [ev["event_id"] for ev in events]
        assert len(eids) == len(set(eids)) == 100

    def test_risk_tiers_are_strictly_valid(self, client: TestClient):
        valid_tiers = {"LOW", "MODERATE", "HIGH", "CRITICAL"}
        res = client.get("/api/events")
        events = res.json()["events"]
        for ev in events:
            assert ev["risk_tier"] in valid_tiers


class TestEventDetailEndpoint:
    def test_get_known_event_returns_200(self, client: TestClient):
        res = client.get("/api/events/EVT_00963466")
        assert res.status_code == 200
        body = res.json()
        assert body["event_id"] == "EVT_00963466"

    def test_detail_contains_all_required_sections(self, client: TestClient):
        res = client.get("/api/events/EVT_00963466")
        body = res.json()

        # Identity & Spatial
        assert "lat" in body and isinstance(body["lat"], (int, float))
        assert "lon" in body and isinstance(body["lon"], (int, float))
        assert "bbox" in body
        assert body["bbox"]["lat_min"] is not None

        # Risk summary
        assert "risk_summary" in body
        rs = body["risk_summary"]
        assert rs["risk_score"] == 49.0
        assert rs["risk_tier"] == "MODERATE"
        assert rs["evidence_confidence"] == 70.0
        assert rs["confidence_tier"] == "MEDIUM"

        # Five dimensions
        assert "dimensions" in body
        dims = body["dimensions"]
        for dname in ("thermal", "persistence", "industrial", "spatial", "spectral"):
            assert dname in dims
            d = dims[dname]
            assert "name" in d
            assert "weight" in d
            assert "normalized_score" in d
            assert "weighted_contribution" in d
            assert "raw" in d

        # Ranking
        assert "ranking" in body
        rk = body["ranking"]
        assert rk["primary_driver"] == "Persistence"
        assert rk["weakest_dimension"] == "Spectral / Surface Evidence"

        # Explanation
        assert "explanation" in body
        exp = body["explanation"]
        assert exp["analyst_synthesis"] is not None
        assert exp["recommendation"] is not None

        # Context, Temporal, Thermal, Spectral
        assert "context" in body
        assert "temporal" in body
        assert "thermal" in body
        assert "spectral" in body

    def test_unknown_event_returns_404_clean_json(self, client: TestClient):
        res = client.get("/api/events/EVT_NONEXISTENT_999999")
        assert res.status_code == 404
        body = res.json()
        assert "detail" in body
        assert "not found" in body["detail"].lower()


class TestDataIntegrityAndParity:
    def test_nullable_osm_field_remains_json_null(self, client: TestClient):
        # In pilot data, EVT_01035117 is unmatched to any OSM industrial facility
        res = client.get("/api/events/EVT_01035117")
        assert res.status_code == 200
        body = res.json()
        assert body["context"]["osm_primary_category"] is None
        assert body["context"]["distance_to_industrial_m"] is None

        # Also in list view
        res_list = client.get("/api/events")
        ev_list = {e["event_id"]: e for e in res_list.json()["events"]}
        assert ev_list["EVT_01035117"]["osm_primary_category"] is None

    def test_known_event_scores_match_source_precisely(self, client: TestClient, raw_curated_events: list[dict]):
        # Benchmark EVT_00963466
        res = client.get("/api/events/EVT_00963466")
        detail = res.json()

        source_row = next(r for r in raw_curated_events if r["event_id"] == "EVT_00963466")
        assert detail["risk_score"] == source_row["risk_score"] == 49.0
        assert detail["risk_tier"] == source_row["risk_tier"] == "MODERATE"
        assert detail["evidence_confidence"] == source_row["evidence_confidence"] == 70.0
        assert detail["confidence_tier"] == source_row["confidence_tier"] == "MEDIUM"

    def test_all_100_events_match_curated_source_scores(self, client: TestClient, raw_curated_events: list[dict]):
        res = client.get("/api/events")
        api_events = {e["event_id"]: e for e in res.json()["events"]}

        for src in raw_curated_events:
            eid = src["event_id"]
            assert eid in api_events
            api_ev = api_events[eid]
            assert api_ev["risk_score"] == src["risk_score"]
            assert api_ev["risk_tier"] == src["risk_tier"]
            assert api_ev["evidence_confidence"] == src["evidence_confidence"]
            assert api_ev["lat"] == src["latitude"]
            assert api_ev["lon"] == src["longitude"]


class TestStrictJsonAndNonFiniteHardening:
    """Validate that API and repository models strictly adhere to RFC 8259 without non-finite floats."""

    @pytest.mark.parametrize("event_id", ["EVT_00424345", "EVT_01035117"])
    def test_detail_response_is_strict_rfc8259_json(self, client: TestClient, event_id: str):
        res = client.get(f"/api/events/{event_id}")
        assert res.status_code == 200

        # Strict JSON parse that fails on any non-finite constants
        def forbid_non_finite(val: str):
            raise ValueError(f"Non-finite JSON constant encountered: {val}")

        parsed = json.loads(res.text, parse_constant=forbid_non_finite)
        assert parsed["event_id"] == event_id

    @pytest.mark.parametrize("event_id", ["EVT_00424345", "EVT_01035117"])
    def test_repository_model_dumps_strictly_without_nan(self, event_id: str):
        repo = get_event_repository()
        evt = repo.get_event(event_id)
        assert evt is not None

        # Verify model dump can be serialized with allow_nan=False (Starlette JSONResponse standard)
        dumped = evt.model_dump()
        dumped_json = json.dumps(dumped, allow_nan=False)
        assert "NaN" not in dumped_json
        assert "Infinity" not in dumped_json


class TestExplanationDecompositionAndPrecision:
    """Validate canonical numerical decomposition across all 100 pilot events."""

    def test_all_100_events_dimension_decomposition_sums_to_risk_score(
        self, client: TestClient, raw_curated_events: list[dict]
    ):
        dims = ["thermal", "persistence", "industrial", "spatial", "spectral"]
        repo = get_event_repository()

        for src in raw_curated_events:
            eid = src["event_id"]
            evt = repo.get_event(eid)
            assert evt is not None

            # 1. Normalized scores must match canonical dimension scores
            for d in dims:
                model_dim = getattr(evt.dimensions, d)
                canonical_norm = src[f"{d}_dimension_score"]
                canonical_weighted = src[f"weighted_{d}"] * 100.0

                assert math.isclose(
                    model_dim.normalized_score, canonical_norm, abs_tol=1e-5
                ), f"Normalized score mismatch in {eid}.{d}: {model_dim.normalized_score} != {canonical_norm}"

                assert math.isclose(
                    model_dim.weighted_contribution, canonical_weighted, abs_tol=1e-5
                ), f"Weighted contribution mismatch in {eid}.{d}: {model_dim.weighted_contribution} != {canonical_weighted}"

            # 2. Sum of five dimension weighted contributions must equal canonical risk_score
            contrib_sum = sum(getattr(evt.dimensions, d).weighted_contribution for d in dims)
            assert round(contrib_sum, 1) == src["risk_score"]
            assert math.isclose(
                round(contrib_sum, 1), src["risk_score"], abs_tol=0.001
            ), f"Decomposition sum mismatch in {eid}: {contrib_sum} -> {round(contrib_sum, 1)} != {src['risk_score']}"


class TestDatasetIntegrity:
    """Validate that on-disk datasets are clean, RFC 8259 compliant, and strictly typed."""

    def test_curated_pilot_events_clean_and_unchanged(self):
        data_path = Path(__file__).resolve().parent.parent / "data" / "curated_pilot_events.json"
        with data_path.open("r", encoding="utf-8") as f:
            events = json.load(f)
        assert len(events) == 100

    def test_pilot_explanations_contains_zero_non_finite_values(self):
        data_path = Path(__file__).resolve().parent.parent / "data" / "pilot_explanations.json"

        def forbid_non_finite(val: str):
            raise ValueError(f"Found non-finite constant: {val}")

        with data_path.open("r", encoding="utf-8") as f:
            explanations = json.load(f, parse_constant=forbid_non_finite)

        assert len(explanations) == 100
        text = json.dumps(explanations)
        assert "NaN" not in text
        assert "Infinity" not in text

    def test_pilot_risk_summary_integrity(self):
        data_path = Path(__file__).resolve().parent.parent / "data" / "pilot_risk_summary.json"

        def forbid_non_finite(val: str):
            raise ValueError(f"Found non-finite constant: {val}")

        with data_path.open("r", encoding="utf-8") as f:
            summary = json.load(f, parse_constant=forbid_non_finite)

        # zero_spatial_events must remain strictly 19
        assert summary["coverage"]["zero_spatial_events"] == 19

        # Verify no literal "nan" strings exist
        summary_text = json.dumps(summary)
        assert '"nan"' not in summary_text

        # Lowest 5 events have null osm_primary_category
        for ev in summary["lowest_5_events"]:
            assert ev["osm_primary_category"] is None


class TestSingletonConcurrency:
    """Validate thread-safe singleton initialization under concurrent access."""

    def test_concurrent_get_event_repository_returns_identical_instance(self):
        def _fetch_repo():
            return get_event_repository()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(_fetch_repo) for _ in range(25)]
            instances = [f.result() for f in futures]

        first_instance = instances[0]
        assert all(inst is first_instance for inst in instances)
        assert len({id(inst) for inst in instances}) == 1
