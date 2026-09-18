"""
ThermoGuard — Risk Engine Dimensions.

Computes the five core scoring dimensions of the deterministic risk model.

Locked dimension weights (must not be changed without methodology review):
  A: Thermal Intensity            30%
  B: Persistence                  25%
  C: Industrial / Contextual Association  20%
  D: Spatial Scale                10%
  E: Spectral / Surface Evidence  15%

Each compute_dimension_* function:
  - Accepts a Dict[str, Any] event record.
  - Returns a fully-documented dimension dict with:
      dimension_name, dimension_code, weight, score (0–1),
      weighted_contribution, raw_inputs, normalized_components,
      internal_weights, missing_fields, is_completely_missing.
  - Never redistributes weights for missing evidence.
  - Never calls an LLM, external service, or random source.

WorldCover class and OSM category/tier are carried as metadata only
and carry 0% risk weight.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .normalization import (
    is_missing,
    normalize_bsi,
    normalize_detection_count,
    normalize_fraction,
    normalize_frp_max,
    normalize_frp_mean,
    normalize_brightness,
    normalize_ndvi,
    normalize_osm_proximity,
    normalize_persistence_days,
    normalize_spatial_extent,
    normalize_swir_anomaly,
    normalize_swir_ratio,
)

# ── Locked dimension weights ──────────────────────────────────────────────────
WEIGHT_A_THERMAL: float = 0.30
WEIGHT_B_PERSISTENCE: float = 0.25
WEIGHT_C_INDUSTRIAL: float = 0.20
WEIGHT_D_SPATIAL: float = 0.10
WEIGHT_E_SPECTRAL: float = 0.15

# Sanity assertion — weights must sum to 1.0
_TOTAL_WEIGHT = (
    WEIGHT_A_THERMAL
    + WEIGHT_B_PERSISTENCE
    + WEIGHT_C_INDUSTRIAL
    + WEIGHT_D_SPATIAL
    + WEIGHT_E_SPECTRAL
)
assert abs(_TOTAL_WEIGHT - 1.0) < 1e-9, f"Dimension weights do not sum to 1.0: {_TOTAL_WEIGHT}"


# ── Dimension A — Thermal Intensity (30%) ────────────────────────────────────

def compute_dimension_a_thermal(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dimension A — Thermal Intensity (weight: 30%).

    Sub-features and their internal weights:
      frp_mean         50%  — mean Fire Radiative Power (MW)
      frp_max          35%  — peak Fire Radiative Power (MW)
      brightness_mean  15%  — brightness temperature (K)
    """
    frp_mean_raw = event.get("frp_mean")
    frp_max_raw = event.get("frp_max")
    brightness_raw = event.get("brightness_mean")

    frp_mean_norm, miss_mean = normalize_frp_mean(frp_mean_raw)
    frp_max_norm, miss_max = normalize_frp_max(frp_max_raw)
    brightness_norm, miss_b = normalize_brightness(brightness_raw)

    missing_fields: List[str] = []
    if miss_mean:
        missing_fields.append("frp_mean")
    if miss_max:
        missing_fields.append("frp_max")
    if miss_b:
        missing_fields.append("brightness_mean")

    score_a = 0.50 * frp_mean_norm + 0.35 * frp_max_norm + 0.15 * brightness_norm

    return {
        "dimension_name": "Thermal Intensity",
        "dimension_code": "A",
        "weight": WEIGHT_A_THERMAL,
        "score": float(score_a),
        "weighted_contribution": float(WEIGHT_A_THERMAL * score_a),
        "raw_inputs": {
            "frp_mean": frp_mean_raw,
            "frp_max": frp_max_raw,
            "brightness_mean": brightness_raw,
        },
        "normalized_components": {
            "frp_mean_norm": frp_mean_norm,
            "frp_max_norm": frp_max_norm,
            "brightness_norm": brightness_norm,
        },
        "internal_weights": {
            "frp_mean": 0.50,
            "frp_max": 0.35,
            "brightness_mean": 0.15,
        },
        "missing_fields": missing_fields,
        "is_completely_missing": len(missing_fields) == 3,
    }


# ── Dimension B — Persistence (25%) ──────────────────────────────────────────

def compute_dimension_b_persistence(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dimension B — Persistence (weight: 25%).

    Sub-features and their internal weights:
      distinct_detection_days  70%  — distinct calendar days with detections
      detection_count          30%  — total number of detections
    """
    days_raw = event.get("distinct_detection_days")
    count_raw = event.get("detection_count")

    days_norm, miss_days = normalize_persistence_days(days_raw)
    count_norm, miss_count = normalize_detection_count(count_raw)

    missing_fields: List[str] = []
    if miss_days:
        missing_fields.append("distinct_detection_days")
    if miss_count:
        missing_fields.append("detection_count")

    score_b = 0.70 * days_norm + 0.30 * count_norm

    return {
        "dimension_name": "Persistence",
        "dimension_code": "B",
        "weight": WEIGHT_B_PERSISTENCE,
        "score": float(score_b),
        "weighted_contribution": float(WEIGHT_B_PERSISTENCE * score_b),
        "raw_inputs": {
            "distinct_detection_days": days_raw,
            "detection_count": count_raw,
        },
        "normalized_components": {
            "persistence_norm": days_norm,
            "detection_count_norm": count_norm,
        },
        "internal_weights": {
            "distinct_detection_days": 0.70,
            "detection_count": 0.30,
        },
        "missing_fields": missing_fields,
        "is_completely_missing": len(missing_fields) == 2,
    }


# ── Dimension C — Industrial / Contextual Association (20%) ──────────────────

def compute_dimension_c_industrial(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dimension C — Industrial / Contextual Association (weight: 20%).

    Uses only objective, quantitative spatial metrics — NOT OSM category or tier.
    OSM category/tier are passed through as context-only metadata (0% weight).

    Sub-features and their internal weights:
      osm_matched_fraction      35%  — fraction of detections with OSM industrial match
      osm_containment_fraction  30%  — fraction spatially contained within OSM polygon
      osm_proximity_fraction    20%  — fraction within proximity buffer
      osm_proximity_score       15%  — inverse-distance proximity score from min_distance_m
    """
    matched_raw = event.get("osm_matched_fraction")
    containment_raw = event.get("osm_containment_fraction")
    proximity_raw = event.get("osm_proximity_fraction")
    min_dist_raw = event.get("min_distance_m")

    has_match_raw = event.get("has_osm_industrial_match")
    has_match = (
        bool(has_match_raw)
        if has_match_raw is not None and not is_missing(has_match_raw)
        else False
    )

    prox_score, miss_dist = normalize_osm_proximity(min_dist_raw)
    matched_norm, miss_matched = normalize_fraction(matched_raw)
    containment_norm, miss_containment = normalize_fraction(containment_raw)
    proximity_norm, miss_proximity = normalize_fraction(proximity_raw)

    missing_fields: List[str] = []
    if miss_matched:
        missing_fields.append("osm_matched_fraction")
    if miss_containment:
        missing_fields.append("osm_containment_fraction")
    if miss_proximity:
        missing_fields.append("osm_proximity_fraction")
    if miss_dist:
        missing_fields.append("min_distance_m")

    is_no_match = (len(missing_fields) == 4) or (
        not has_match and matched_norm == 0.0 and prox_score == 0.0
    )

    score_c = (
        0.35 * matched_norm
        + 0.30 * containment_norm
        + 0.20 * proximity_norm
        + 0.15 * prox_score
    )

    return {
        "dimension_name": "Industrial / Contextual Association",
        "dimension_code": "C",
        "weight": WEIGHT_C_INDUSTRIAL,
        "score": float(score_c),
        "weighted_contribution": float(WEIGHT_C_INDUSTRIAL * score_c),
        "raw_inputs": {
            "osm_matched_fraction": matched_raw,
            "osm_containment_fraction": containment_raw,
            "osm_proximity_fraction": proximity_raw,
            "min_distance_m": min_dist_raw,
            "has_osm_industrial_match": has_match_raw,
            # Context-only metadata — zero risk weight
            "osm_tier": event.get("osm_tier"),
            "osm_primary_category": event.get("osm_primary_category"),
            "osm_sub_category": event.get("osm_sub_category"),
        },
        "normalized_components": {
            "osm_matched_fraction": matched_norm,
            "osm_containment_fraction": containment_norm,
            "osm_proximity_fraction": proximity_norm,
            "osm_proximity_score": prox_score,
        },
        "internal_weights": {
            "osm_matched_fraction": 0.35,
            "osm_containment_fraction": 0.30,
            "osm_proximity_fraction": 0.20,
            "osm_proximity_score": 0.15,
        },
        "missing_fields": missing_fields,
        "has_mapped_association": not is_no_match and score_c > 0.0,
        "is_completely_missing": len(missing_fields) == 4,
    }


# ── Dimension D — Spatial Scale (10%) ────────────────────────────────────────

def compute_dimension_d_spatial(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dimension D — Spatial Scale (weight: 10%).

    Sub-features and their internal weights:
      spatial_extent_km2  100%  — physical event footprint area

    Note: distinct_satellites is NOT a risk input — it belongs to
    Evidence Confidence (Commit 3).
    """
    extent_raw = event.get("spatial_extent_km2")
    spatial_norm, miss_extent = normalize_spatial_extent(extent_raw)

    missing_fields: List[str] = []
    if miss_extent:
        missing_fields.append("spatial_extent_km2")

    score_d = spatial_norm

    return {
        "dimension_name": "Spatial Scale",
        "dimension_code": "D",
        "weight": WEIGHT_D_SPATIAL,
        "score": float(score_d),
        "weighted_contribution": float(WEIGHT_D_SPATIAL * score_d),
        "raw_inputs": {
            "spatial_extent_km2": extent_raw,
        },
        "normalized_components": {
            "spatial_norm": spatial_norm,
        },
        "internal_weights": {
            "spatial_norm": 1.00,
        },
        "missing_fields": missing_fields,
        "is_completely_missing": bool(miss_extent),
    }


# ── Dimension E — Spectral / Surface Evidence (15%) ──────────────────────────

def compute_dimension_e_spectral(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dimension E — Spectral / Surface Evidence (weight: 15%).

    Sentinel-2 optical/SWIR surface reflectance contrast and ground disturbance.

    Sub-features and their internal weights:
      swir_anomaly_norm   45%  — SWIR2 anomaly ratio contrast
      ndvi_disturb_norm   25%  — NDVI surface disturbance
      swir_ratio_norm     20%  — SWIR2/SWIR1 ratio
      bsi_norm            10%  — Bare Soil Index

    The raw sub-feature score is multiplied by spectral_reliability:
      spectral_reliability = temporal_reliability × cloud_reliability

    Temporal reliability:
      - Missing temporal_delta_days → 0.50 (neutral/unknown)
      - ≤ 0 days              → 1.00
      - ≥ 90 days             → 0.00
      - Otherwise             → 1.0 - (delta / 90)

    Cloud reliability (requires has_spectral_features == 1):
      - scl_clear_fraction ≥ 0.9  → 1.00
      - scl_clear_fraction ≥ 0.5  → scl_clear_fraction
      - scl_clear_fraction < 0.5  → 0.00

    If has_spectral_features == 0 or has_satellite_scene == 0,
    score_E is forced to 0.0.
    """
    has_spectral_raw = event.get("has_spectral_features")
    has_scene_raw = event.get("has_satellite_scene")

    # Infer has_spectral if not explicitly provided
    if has_spectral_raw is None:
        has_spectral = (
            1
            if not is_missing(event.get("swir2_anomaly_ratio"))
            or not is_missing(event.get("b02_blue_mean"))
            else 0
        )
    else:
        has_spectral = int(has_spectral_raw) if not is_missing(has_spectral_raw) else 0

    if has_scene_raw is None:
        has_scene = (
            1
            if event.get("satellite_scene_id") is not None or has_spectral == 1
            else 0
        )
    else:
        has_scene = int(has_scene_raw) if not is_missing(has_scene_raw) else 0

    swir_anomaly_raw = event.get("swir2_anomaly_ratio")
    ndvi_raw = event.get("ndvi")
    bsi_raw = event.get("bsi")
    swir_ratio_raw = event.get("swir2_swir1_ratio")
    temporal_delta_raw = event.get("temporal_delta_days")
    scl_clear_raw = event.get("scl_clear_fraction")

    swir_anomaly_norm, miss_swir_a = normalize_swir_anomaly(swir_anomaly_raw)
    ndvi_disturb_norm, miss_ndvi = normalize_ndvi(ndvi_raw)
    bsi_norm, miss_bsi = normalize_bsi(bsi_raw)
    swir_ratio_norm, miss_swir_r = normalize_swir_ratio(swir_ratio_raw)

    missing_fields: List[str] = []
    if miss_swir_a:
        missing_fields.append("swir2_anomaly_ratio")
    if miss_ndvi:
        missing_fields.append("ndvi")
    if miss_bsi:
        missing_fields.append("bsi")
    if miss_swir_r:
        missing_fields.append("swir2_swir1_ratio")

    # Temporal reliability
    if is_missing(temporal_delta_raw):
        temporal_reliability = 0.5
    else:
        delta = float(temporal_delta_raw)
        if delta <= 0.0:
            temporal_reliability = 1.0
        elif delta >= 90.0:
            temporal_reliability = 0.0
        else:
            temporal_reliability = 1.0 - (delta / 90.0)

    # Cloud reliability
    if has_spectral == 0 or is_missing(scl_clear_raw):
        cloud_reliability = 0.0
    else:
        clear_frac = float(scl_clear_raw)
        if clear_frac >= 0.9:
            cloud_reliability = 1.0
        elif clear_frac >= 0.5:
            cloud_reliability = clear_frac
        else:
            cloud_reliability = 0.0

    spectral_reliability = float(temporal_reliability * cloud_reliability)

    e_raw = (
        0.45 * swir_anomaly_norm
        + 0.25 * ndvi_disturb_norm
        + 0.20 * swir_ratio_norm
        + 0.10 * bsi_norm
    )

    if has_spectral == 0 or has_scene == 0:
        score_e = 0.0
        spectral_reliability = 0.0
        all_missing = True
    else:
        score_e = e_raw * spectral_reliability
        all_missing = len(missing_fields) == 4

    return {
        "dimension_name": "Spectral / Surface Evidence",
        "dimension_code": "E",
        "weight": WEIGHT_E_SPECTRAL,
        "score": float(score_e),
        "raw_score_before_reliability": float(e_raw),
        "spectral_reliability": float(spectral_reliability),
        "temporal_reliability": float(temporal_reliability),
        "cloud_reliability": float(cloud_reliability),
        "weighted_contribution": float(WEIGHT_E_SPECTRAL * score_e),
        "raw_inputs": {
            "swir2_anomaly_ratio": swir_anomaly_raw,
            "ndvi": ndvi_raw,
            "bsi": bsi_raw,
            "swir2_swir1_ratio": swir_ratio_raw,
            "temporal_delta_days": temporal_delta_raw,
            "scl_clear_fraction": scl_clear_raw,
            "has_spectral_features": has_spectral,
            "has_satellite_scene": has_scene,
        },
        "normalized_components": {
            "swir_anomaly_norm": swir_anomaly_norm,
            "ndvi_disturb_norm": ndvi_disturb_norm,
            "bsi_norm": bsi_norm,
            "swir_ratio_norm": swir_ratio_norm,
        },
        "internal_weights": {
            "swir_anomaly_norm": 0.45,
            "ndvi_disturb_norm": 0.25,
            "swir_ratio_norm": 0.20,
            "bsi_norm": 0.10,
        },
        "missing_fields": missing_fields,
        "is_completely_missing": all_missing,
    }
