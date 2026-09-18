"""
ThermoGuard — Risk Engine Input Validation.

Validates and describes the expected fields for a thermal event dict
before it enters the scoring pipeline.

Responsibilities:
  - Enumerate all recognised input fields with types and descriptions.
  - Detect unrecognised/unknown keys (warn, do not raise).
  - Report which required fields are missing vs. present.
  - Return a structured validation report (never raises on missing evidence —
    missing evidence is valid; the engine scores it as zero contribution).

This module does NOT perform risk scoring. It is a pre-flight helper.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .normalization import is_missing


# ── Known field registry ──────────────────────────────────────────────────────
# Maps field_name → (type_label, description, is_required)
# is_required = True means the field is used in a scoring dimension.
# is_required = False means it is context-only / metadata.

FIELD_REGISTRY: Dict[str, Tuple[str, str, bool]] = {
    # ── Dimension A — Thermal Intensity ───────────────────────────────────────
    "frp_mean": ("float", "Mean Fire Radiative Power (MW)", True),
    "frp_max": ("float", "Peak Fire Radiative Power (MW)", True),
    "brightness_mean": ("float", "Mean brightness temperature (K)", True),
    # ── Dimension B — Persistence ─────────────────────────────────────────────
    "distinct_detection_days": ("int", "Distinct calendar days with detections", True),
    "detection_count": ("int", "Total number of satellite detections", True),
    # ── Dimension C — Industrial Association ──────────────────────────────────
    "osm_matched_fraction": ("float [0,1]", "Fraction of detections with OSM industrial match", True),
    "osm_containment_fraction": ("float [0,1]", "Fraction spatially contained in OSM polygon", True),
    "osm_proximity_fraction": ("float [0,1]", "Fraction within OSM proximity buffer", True),
    "min_distance_m": ("float ≥ 0", "Minimum distance to nearest industrial OSM feature (m)", True),
    "has_osm_industrial_match": ("bool/int", "Whether an OSM industrial match exists", True),
    # ── Dimension D — Spatial Scale ───────────────────────────────────────────
    "spatial_extent_km2": ("float ≥ 0", "Physical footprint area (km²)", True),
    # ── Dimension E — Spectral / Surface Evidence ─────────────────────────────
    "swir2_anomaly_ratio": ("float", "SWIR2 surface reflectance anomaly ratio", True),
    "ndvi": ("float [-1,1]", "Normalized Difference Vegetation Index", True),
    "bsi": ("float [-0.5,0.5]", "Bare Soil Index", True),
    "swir2_swir1_ratio": ("float ≥ 0", "SWIR2 / SWIR1 band ratio", True),
    "has_spectral_features": ("bool/int", "Whether Sentinel-2 spectral features were extracted", True),
    "has_satellite_scene": ("bool/int", "Whether a satellite scene exists for this event", True),
    "scl_clear_fraction": ("float [0,1]", "Fraction of scene with clear-sky SCL classification", True),
    "temporal_delta_days": ("float ≥ 0", "Days between satellite scene and thermal event date", True),
    # ── Context only (0% risk weight) ─────────────────────────────────────────
    "event_id": ("str", "Unique event identifier", False),
    "worldcover_class": ("int", "ESA WorldCover class code (context only)", False),
    "worldcover_class_name": ("str", "ESA WorldCover class label (context only)", False),
    "osm_tier": ("int", "OSM industrial tier classification (context only)", False),
    "osm_primary_category": ("str", "OSM primary industry category (context only)", False),
    "osm_sub_category": ("str", "OSM sub-category (context only)", False),
    "distinct_satellites": ("int", "Number of distinct satellite platforms (Evidence Confidence input)", False),
    "satellite_scene_id": ("str", "Satellite scene identifier (metadata)", False),
    "b02_blue_mean": ("float", "Sentinel-2 B02 Blue band mean (spectral inference helper)", False),
}

REQUIRED_SCORING_FIELDS: List[str] = [
    name for name, (_, _, required) in FIELD_REGISTRY.items() if required
]


# ── Validation function ───────────────────────────────────────────────────────

def validate_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a thermal event dictionary before scoring.

    Returns a structured report with:
      - present_fields   : list of scoring fields present and non-null
      - missing_fields   : list of scoring fields absent or null
      - unknown_fields   : list of keys not in the registry (logged as warnings)
      - is_scoreable     : bool — True if at least one dimension has any data
      - dimension_coverage : dict — per-dimension field presence summary

    Does NOT raise on missing evidence — the scoring pipeline handles
    missing evidence gracefully by contributing zero to that feature.
    """
    present_fields: List[str] = []
    missing_fields: List[str] = []
    unknown_fields: List[str] = []

    for key in event:
        if key not in FIELD_REGISTRY:
            unknown_fields.append(key)

    for field in REQUIRED_SCORING_FIELDS:
        val = event.get(field)
        if val is None or is_missing(val):
            missing_fields.append(field)
        else:
            present_fields.append(field)

    # Per-dimension presence summary
    dim_fields: Dict[str, List[str]] = {
        "thermal": ["frp_mean", "frp_max", "brightness_mean"],
        "persistence": ["distinct_detection_days", "detection_count"],
        "industrial": [
            "osm_matched_fraction", "osm_containment_fraction",
            "osm_proximity_fraction", "min_distance_m",
        ],
        "spatial": ["spatial_extent_km2"],
        "spectral": [
            "swir2_anomaly_ratio", "ndvi", "bsi", "swir2_swir1_ratio",
            "has_spectral_features", "has_satellite_scene",
            "scl_clear_fraction", "temporal_delta_days",
        ],
    }

    dimension_coverage: Dict[str, Dict[str, Any]] = {}
    for dim_name, fields in dim_fields.items():
        present = [f for f in fields if f in present_fields]
        missing = [f for f in fields if f in missing_fields]
        dimension_coverage[dim_name] = {
            "present": present,
            "missing": missing,
            "coverage_fraction": len(present) / len(fields) if fields else 0.0,
        }

    is_scoreable = any(
        coverage["coverage_fraction"] > 0.0
        for coverage in dimension_coverage.values()
    )

    return {
        "present_fields": present_fields,
        "missing_fields": missing_fields,
        "unknown_fields": unknown_fields,
        "is_scoreable": is_scoreable,
        "dimension_coverage": dimension_coverage,
    }
