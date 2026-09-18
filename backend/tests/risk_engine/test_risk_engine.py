"""
Unit tests for the ThermoGuard deterministic risk scoring engine (Commit 2).

Covers:
  1.  Normal valid inputs — known expected score.
  2.  Minimum boundary values — all normalizers return 0.0.
  3.  Maximum boundary values — all normalizers return 1.0.
  4.  Determinism — identical input produces identical output.
  5.  Weighted dimension calculation — per-dimension weighted contributions.
  6.  Missing thermal evidence — dimension A scores 0, weight not redistributed.
  7.  Missing persistence evidence — dimension B scores 0, weight not redistributed.
  8.  Missing industrial evidence — dimension C scores 0, weight not redistributed.
  9.  Missing spatial evidence — dimension D scores 0, weight not redistributed.
  10. Missing spectral evidence — dimension E scores 0, weight not redistributed.
  11. Zero-value dimensions — all zero inputs produce score 0.
  12. All dimensions contributing — full evidence set.
  13. Monotonicity: higher FRP → higher thermal score.
  14. Monotonicity: more days → higher persistence score.
  15. Monotonicity: closer distance → higher industrial score.
  16. Monotonicity: higher SWIR anomaly → higher spectral score.
  17. Final score bounds — always in [0.0, 100.0].
  18. WorldCover does not alter risk score.
  19. OSM category/tier does not alter risk score.
  20. No OSM match → industrial score 0, explicit missing_evidence tag.
  21. Missing multiple dimensions — remaining weighted contributions are exact.
  22. Extreme maximum inputs → score = 100.0, tier = CRITICAL.
  23. Risk tier thresholds — boundary values.
  24. Single-detection event — low but non-zero persistence.
  25. Validate event utility — present, missing, unknown field classification.

Each test is independent and uses no randomness.
"""

from __future__ import annotations

import pytest

from risk_engine.scoring import score_event, get_risk_tier
from risk_engine.normalization import (
    normalize_frp_mean,
    normalize_frp_max,
    normalize_brightness,
    normalize_persistence_days,
    normalize_detection_count,
    normalize_osm_proximity,
    normalize_spatial_extent,
    normalize_swir_anomaly,
    normalize_ndvi,
    normalize_bsi,
    normalize_swir_ratio,
)
from risk_engine.validation import validate_event


# ── Shared fixture ─────────────────────────────────────────────────────────────

@pytest.fixture
def base_event() -> dict:
    """
    Representative full-evidence event used as the baseline fixture.

    This matches the canonical example from the methodology specification
    (Section 12 / base event).  The exact expected score is tested in
    test_01_normal_valid_inputs.
    """
    return {
        "event_id": "EVT_TEST_BASE",
        "frp_mean": 18.0,
        "frp_max": 45.0,
        "brightness_mean": 340.0,
        "distinct_detection_days": 210,
        "detection_count": 5000,
        "spatial_extent_km2": 12.0,
        "distinct_satellites": 3,
        "has_osm_industrial_match": 1,
        "osm_matched_fraction": 0.85,
        "osm_containment_fraction": 0.70,
        "osm_proximity_fraction": 0.90,
        "min_distance_m": 0.0,
        "osm_tier": 2,
        "osm_primary_category": "mine_quarry",
        "worldcover_class": 60,
        "worldcover_class_name": "Bare / sparse vegetation",
        "swir2_anomaly_ratio": 2.8,
        "ndvi": 0.12,
        "bsi": 0.15,
        "swir2_swir1_ratio": 1.3,
        "has_spectral_features": 1,
        "has_satellite_scene": 1,
        "scl_clear_fraction": 0.88,
        "temporal_delta_days": 25.0,
    }


# ── Test 1: Normal valid inputs ───────────────────────────────────────────────

class TestNormalValidInputs:
    def test_01_score_matches_methodology_example(self, base_event: dict) -> None:
        res = score_event(base_event)
        assert res["risk_score"] == 54.4
        assert res["risk_tier"] == "HIGH"
        assert res["event_id"] == "EVT_TEST_BASE"
        assert "methodology_version" in res

    def test_01_all_dimension_scores_in_range(self, base_event: dict) -> None:
        res = score_event(base_event)
        for key in (
            "thermal_dimension_score",
            "persistence_dimension_score",
            "industrial_dimension_score",
            "spatial_dimension_score",
            "spectral_dimension_score",
        ):
            assert 0.0 <= res[key] <= 1.0, f"{key} out of [0, 1]: {res[key]}"


# ── Test 2: Minimum boundary values ───────────────────────────────────────────

class TestMinimumBoundaries:
    def test_02_frp_mean_zero(self) -> None:
        val, miss = normalize_frp_mean(0.0)
        assert val == 0.0 and miss is False

    def test_02_frp_max_zero(self) -> None:
        val, miss = normalize_frp_max(0.0)
        assert val == 0.0 and miss is False

    def test_02_brightness_at_floor(self) -> None:
        val, miss = normalize_brightness(300.0)
        assert val == 0.0 and miss is False

    def test_02_brightness_below_floor(self) -> None:
        val, miss = normalize_brightness(250.0)
        assert val == 0.0 and miss is False

    def test_02_persistence_days_zero(self) -> None:
        val, miss = normalize_persistence_days(0)
        assert val == 0.0 and miss is False

    def test_02_detection_count_zero(self) -> None:
        val, miss = normalize_detection_count(0)
        assert val == 0.0 and miss is False

    def test_02_spatial_extent_zero(self) -> None:
        val, miss = normalize_spatial_extent(0.0)
        assert val == 0.0 and miss is False

    def test_02_swir_anomaly_below_threshold(self) -> None:
        val, miss = normalize_swir_anomaly(0.5)
        assert val == 0.0 and miss is False

    def test_02_osm_proximity_beyond_threshold(self) -> None:
        val, miss = normalize_osm_proximity(5000.0)
        assert val == 0.0 and miss is False


# ── Test 3: Maximum boundary values ───────────────────────────────────────────

class TestMaximumBoundaries:
    def test_03_frp_mean_at_ceiling(self) -> None:
        val, miss = normalize_frp_mean(100.0)
        assert val == 1.0 and miss is False

    def test_03_frp_mean_above_ceiling(self) -> None:
        val, miss = normalize_frp_mean(9999.0)
        assert val == 1.0 and miss is False

    def test_03_frp_max_above_ceiling(self) -> None:
        val, miss = normalize_frp_max(600.0)
        assert val == 1.0 and miss is False

    def test_03_brightness_at_ceiling(self) -> None:
        val, miss = normalize_brightness(370.0)
        assert val == 1.0 and miss is False

    def test_03_brightness_above_ceiling(self) -> None:
        val, miss = normalize_brightness(500.0)
        assert val == 1.0 and miss is False

    def test_03_persistence_days_at_anchor(self) -> None:
        val, miss = normalize_persistence_days(365)
        assert val == 1.0 and miss is False

    def test_03_persistence_days_above_anchor(self) -> None:
        val, miss = normalize_persistence_days(400)
        assert val == 1.0 and miss is False

    def test_03_detection_count_above_anchor(self) -> None:
        val, miss = normalize_detection_count(60_000)
        assert val == 1.0 and miss is False

    def test_03_spatial_extent_above_anchor(self) -> None:
        val, miss = normalize_spatial_extent(600.0)
        assert val == 1.0 and miss is False

    def test_03_swir_anomaly_clipped(self) -> None:
        val, miss = normalize_swir_anomaly(7.0)  # excess = 6 → clips to 5
        assert val == 1.0 and miss is False

    def test_03_osm_proximity_inside_polygon(self) -> None:
        val, miss = normalize_osm_proximity(0.0)
        assert val == 1.0 and miss is False

    def test_03_osm_proximity_negative_distance(self) -> None:
        val, miss = normalize_osm_proximity(-100.0)
        assert val == 1.0 and miss is False


# ── Test 4: Determinism ───────────────────────────────────────────────────────

class TestDeterminism:
    def test_04_identical_input_produces_identical_output(
        self, base_event: dict
    ) -> None:
        res1 = score_event(base_event)
        res2 = score_event(base_event)
        assert res1["risk_score"] == res2["risk_score"]
        assert res1["risk_score_raw"] == res2["risk_score_raw"]
        assert res1["risk_tier"] == res2["risk_tier"]
        assert res1["dimensions"] == res2["dimensions"]
        assert res1["missing_evidence"] == res2["missing_evidence"]

    def test_04_determinism_repeated_ten_times(self, base_event: dict) -> None:
        results = [score_event(base_event)["risk_score"] for _ in range(10)]
        assert len(set(results)) == 1, "Non-deterministic: scores differ across calls"


# ── Test 5: Weighted dimension calculation ────────────────────────────────────

class TestWeightedDimensionCalculation:
    def test_05_weighted_contributions_sum_to_risk_score_raw(
        self, base_event: dict
    ) -> None:
        res = score_event(base_event)
        dims = res["dimensions"]
        expected_raw = (
            dims["thermal"]["weighted_contribution"]
            + dims["persistence"]["weighted_contribution"]
            + dims["industrial"]["weighted_contribution"]
            + dims["spatial"]["weighted_contribution"]
            + dims["spectral"]["weighted_contribution"]
        )
        assert abs(res["risk_score_raw"] - expected_raw) < 1e-9

    def test_05_weighted_contribution_equals_weight_times_score(
        self, base_event: dict
    ) -> None:
        res = score_event(base_event)
        for key, weight in (
            ("thermal", 0.30),
            ("persistence", 0.25),
            ("industrial", 0.20),
            ("spatial", 0.10),
            ("spectral", 0.15),
        ):
            dim = res["dimensions"][key]
            expected = weight * dim["score"]
            assert abs(dim["weighted_contribution"] - expected) < 1e-9, (
                f"{key}: weighted_contribution {dim['weighted_contribution']} "
                f"!= weight * score {expected}"
            )


# ── Tests 6–10: Missing single dimensions (no weight redistribution) ──────────

class TestMissingDimensions:
    def test_06_missing_thermal_contributes_zero_weight_not_redistributed(
        self, base_event: dict
    ) -> None:
        ev = {**base_event, "frp_mean": None, "frp_max": None, "brightness_mean": None}
        res = score_event(ev)
        assert res["thermal_dimension_score"] == 0.0
        assert res["dimensions"]["thermal"]["weighted_contribution"] == 0.0
        assert "dimension_A_thermal_missing" in res["missing_evidence"]
        # Persistence weight must still be 0.25, not boosted
        assert abs(res["dimensions"]["persistence"]["weight"] - 0.25) < 1e-9

    def test_07_missing_persistence_contributes_zero_weight_not_redistributed(
        self, base_event: dict
    ) -> None:
        ev = {**base_event, "distinct_detection_days": None, "detection_count": None}
        res = score_event(ev)
        assert res["persistence_dimension_score"] == 0.0
        assert res["dimensions"]["persistence"]["weighted_contribution"] == 0.0
        assert "dimension_B_persistence_missing" in res["missing_evidence"]

    def test_08_missing_industrial_contributes_zero(
        self, base_event: dict
    ) -> None:
        ev = {
            **base_event,
            "osm_matched_fraction": None,
            "osm_containment_fraction": None,
            "osm_proximity_fraction": None,
            "min_distance_m": None,
            "has_osm_industrial_match": 0,
        }
        res = score_event(ev)
        assert res["industrial_dimension_score"] == 0.0
        assert res["dimensions"]["industrial"]["weighted_contribution"] == 0.0

    def test_09_missing_spatial_contributes_zero(
        self, base_event: dict
    ) -> None:
        ev = {**base_event, "spatial_extent_km2": None}
        res = score_event(ev)
        assert res["spatial_dimension_score"] == 0.0
        assert res["dimensions"]["spatial"]["weighted_contribution"] == 0.0
        assert "dimension_D_spatial_missing" in res["missing_evidence"]

    def test_10_missing_spectral_contributes_zero(
        self, base_event: dict
    ) -> None:
        ev = {**base_event, "has_spectral_features": 0, "has_satellite_scene": 0}
        res = score_event(ev)
        assert res["spectral_dimension_score"] == 0.0
        assert res["dimensions"]["spectral"]["weighted_contribution"] == 0.0
        assert "dimension_E_spectral_missing" in res["missing_evidence"]


# ── Test 11: Zero-value dimensions ────────────────────────────────────────────

class TestZeroValueDimensions:
    def test_11_all_zero_inputs_produce_zero_score(self) -> None:
        ev = {
            "event_id": "EVT_ZERO",
            "frp_mean": 0.0,
            "frp_max": 0.0,
            "brightness_mean": 300.0,   # at floor → 0
            "distinct_detection_days": 0,
            "detection_count": 0,
            "spatial_extent_km2": 0.0,
            "osm_matched_fraction": 0.0,
            "osm_containment_fraction": 0.0,
            "osm_proximity_fraction": 0.0,
            "min_distance_m": 5000.0,   # at threshold → 0
            "has_osm_industrial_match": 0,
            "has_spectral_features": 0,
            "has_satellite_scene": 0,
        }
        res = score_event(ev)
        assert res["risk_score"] == 0.0
        assert res["risk_tier"] == "LOW"


# ── Test 12: All dimensions contributing ─────────────────────────────────────

class TestAllDimensionsContributing:
    def test_12_all_dimensions_have_nonzero_contribution(
        self, base_event: dict
    ) -> None:
        res = score_event(base_event)
        dims = res["dimensions"]
        for key in ("thermal", "persistence", "industrial", "spatial", "spectral"):
            assert dims[key]["weighted_contribution"] > 0.0, (
                f"Dimension {key} has zero contribution on full base_event"
            )


# ── Tests 13–16: Monotonicity ─────────────────────────────────────────────────

class TestMonotonicity:
    def test_13_higher_frp_mean_increases_thermal_score(
        self, base_event: dict
    ) -> None:
        low = score_event({**base_event, "frp_mean": 5.0})
        high = score_event({**base_event, "frp_mean": 80.0})
        assert low["thermal_dimension_score"] < high["thermal_dimension_score"]

    def test_14_more_detection_days_increases_persistence(
        self, base_event: dict
    ) -> None:
        low = score_event({**base_event, "distinct_detection_days": 10})
        high = score_event({**base_event, "distinct_detection_days": 300})
        assert low["persistence_dimension_score"] < high["persistence_dimension_score"]

    def test_15_closer_distance_increases_industrial_score(
        self, base_event: dict
    ) -> None:
        near = score_event({**base_event, "min_distance_m": 100.0})
        far = score_event({**base_event, "min_distance_m": 4000.0})
        assert near["industrial_dimension_score"] >= far["industrial_dimension_score"]

    def test_16_higher_swir_anomaly_increases_spectral_score(
        self, base_event: dict
    ) -> None:
        low = score_event({**base_event, "swir2_anomaly_ratio": 1.5})
        high = score_event({**base_event, "swir2_anomaly_ratio": 4.0})
        assert low["spectral_dimension_score"] < high["spectral_dimension_score"]


# ── Test 17: Final score bounds ───────────────────────────────────────────────

class TestFinalScoreBounds:
    def test_17_score_never_below_zero(self, base_event: dict) -> None:
        res = score_event(base_event)
        assert res["risk_score"] >= 0.0

    def test_17_score_never_above_100(self, base_event: dict) -> None:
        ev = {
            "event_id": "EVT_MAX",
            "frp_mean": 500.0,
            "frp_max": 2000.0,
            "brightness_mean": 500.0,
            "distinct_detection_days": 500,
            "detection_count": 100_000,
            "spatial_extent_km2": 1000.0,
            "has_osm_industrial_match": 1,
            "osm_matched_fraction": 1.0,
            "osm_containment_fraction": 1.0,
            "osm_proximity_fraction": 1.0,
            "min_distance_m": 0.0,
            "swir2_anomaly_ratio": 10.0,
            "ndvi": -0.5,
            "bsi": 0.8,
            "swir2_swir1_ratio": 3.0,
            "has_spectral_features": 1,
            "has_satellite_scene": 1,
            "scl_clear_fraction": 1.0,
            "temporal_delta_days": 0.0,
        }
        res = score_event(ev)
        assert res["risk_score"] == 100.0
        assert res["risk_tier"] == "CRITICAL"


# ── Tests 18–19: Context fields do not alter risk score ──────────────────────

class TestContextFieldsDoNotAlterRiskScore:
    def test_18_worldcover_class_does_not_change_risk_score(
        self, base_event: dict
    ) -> None:
        bare = score_event({**base_event, "worldcover_class": 60, "worldcover_class_name": "Bare"})
        tree = score_event({**base_event, "worldcover_class": 10, "worldcover_class_name": "Tree cover"})
        built = score_event({**base_event, "worldcover_class": 50, "worldcover_class_name": "Built-up"})
        assert bare["risk_score"] == tree["risk_score"] == built["risk_score"]

    def test_19_osm_category_and_tier_do_not_change_risk_score(
        self, base_event: dict
    ) -> None:
        mine = score_event({**base_event, "osm_primary_category": "mine_quarry", "osm_tier": 1})
        sub = score_event({**base_event, "osm_primary_category": "substation", "osm_tier": 2})
        none = score_event({**base_event, "osm_primary_category": None, "osm_tier": None})
        assert mine["risk_score"] == sub["risk_score"] == none["risk_score"]


# ── Test 20: No OSM match → explicit missing_evidence tag ────────────────────

class TestNoOSMMatch:
    def test_20_no_osm_match_produces_zero_industrial_score(
        self, base_event: dict
    ) -> None:
        ev = {
            **base_event,
            "has_osm_industrial_match": 0,
            "min_distance_m": None,
            "osm_matched_fraction": 0.0,
            "osm_containment_fraction": 0.0,
            "osm_proximity_fraction": 0.0,
        }
        res = score_event(ev)
        assert res["industrial_dimension_score"] == 0.0
        assert "osm_context:no_mapped_association" in res["missing_evidence"]


# ── Test 21: Missing multiple dimensions — remaining weights are exact ─────────

class TestMissingMultipleDimensions:
    def test_21_partial_evidence_weights_are_not_redistributed(
        self, base_event: dict
    ) -> None:
        ev = {
            **base_event,
            "frp_mean": None,
            "frp_max": None,
            "brightness_mean": None,
            "has_spectral_features": 0,
            "has_satellite_scene": 0,
        }
        res = score_event(ev)
        assert res["thermal_dimension_score"] == 0.0
        assert res["spectral_dimension_score"] == 0.0

        # Only B, C, D contribute; their locked weights must be preserved exactly
        expected_raw = (
            0.25 * res["persistence_dimension_score"]
            + 0.20 * res["industrial_dimension_score"]
            + 0.10 * res["spatial_dimension_score"]
        )
        assert abs(res["risk_score_raw"] - expected_raw) < 1e-9


# ── Test 22: Extreme maximum inputs ──────────────────────────────────────────

class TestExtremeMaximumInputs:
    def test_22_extreme_max_produces_100_critical(self) -> None:
        ev = {
            "event_id": "EVT_EXTREME_MAX",
            "frp_mean": 9999.0,
            "frp_max": 9999.0,
            "brightness_mean": 9999.0,
            "distinct_detection_days": 9999,
            "detection_count": 9_999_999,
            "spatial_extent_km2": 9999.0,
            "has_osm_industrial_match": 1,
            "osm_matched_fraction": 1.0,
            "osm_containment_fraction": 1.0,
            "osm_proximity_fraction": 1.0,
            "min_distance_m": 0.0,
            "swir2_anomaly_ratio": 99.0,
            "ndvi": -1.0,
            "bsi": 99.0,
            "swir2_swir1_ratio": 99.0,
            "has_spectral_features": 1,
            "has_satellite_scene": 1,
            "scl_clear_fraction": 1.0,
            "temporal_delta_days": 0.0,
        }
        res = score_event(ev)
        assert res["risk_score"] == 100.0
        assert res["risk_tier"] == "CRITICAL"


# ── Test 23: Risk tier thresholds ─────────────────────────────────────────────

class TestRiskTierThresholds:
    def test_23_low_tier(self) -> None:
        assert get_risk_tier(0.0) == "LOW"
        assert get_risk_tier(24.9) == "LOW"

    def test_23_moderate_tier(self) -> None:
        assert get_risk_tier(25.0) == "MODERATE"
        assert get_risk_tier(49.9) == "MODERATE"

    def test_23_high_tier(self) -> None:
        assert get_risk_tier(50.0) == "HIGH"
        assert get_risk_tier(74.9) == "HIGH"

    def test_23_critical_tier(self) -> None:
        assert get_risk_tier(75.0) == "CRITICAL"
        assert get_risk_tier(100.0) == "CRITICAL"


# ── Test 24: Single-detection event ──────────────────────────────────────────

class TestSingleDetectionEvent:
    def test_24_single_detection_produces_small_but_nonzero_persistence(
        self, base_event: dict
    ) -> None:
        ev = {**base_event, "distinct_detection_days": 1, "detection_count": 1}
        res = score_event(ev)
        assert 0.0 < res["persistence_dimension_score"] < 0.20


# ── Test 25: Validate event utility ──────────────────────────────────────────

class TestValidateEvent:
    def test_25_full_event_has_no_missing_scoring_fields(
        self, base_event: dict
    ) -> None:
        report = validate_event(base_event)
        assert report["is_scoreable"] is True
        assert len(report["missing_fields"]) == 0

    def test_25_empty_event_reports_all_fields_missing(self) -> None:
        report = validate_event({"event_id": "EMPTY"})
        assert report["is_scoreable"] is False
        assert len(report["missing_fields"]) > 0

    def test_25_unknown_fields_are_flagged(self) -> None:
        report = validate_event({"event_id": "X", "unknown_field_xyz": 99})
        assert "unknown_field_xyz" in report["unknown_fields"]

    def test_25_dimension_coverage_reported_per_dimension(
        self, base_event: dict
    ) -> None:
        report = validate_event(base_event)
        for dim in ("thermal", "persistence", "industrial", "spatial", "spectral"):
            assert dim in report["dimension_coverage"]
            coverage = report["dimension_coverage"][dim]["coverage_fraction"]
            assert 0.0 <= coverage <= 1.0
