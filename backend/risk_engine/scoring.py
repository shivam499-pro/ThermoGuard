"""
ThermoGuard — Deterministic Risk Scoring Pipeline.

Computes a deterministic risk score (0–100) and risk tier for a single
thermal event dictionary.

Non-negotiable invariants of the methodology:
  1. Fixed weights: A=30%, B=25%, C=20%, D=10%, E=15%. Total = 100%.
  2. No weight redistribution for missing evidence.
  3. WorldCover class is context only — 0% risk weight.
  4. OSM tier / category is context only — 0% risk weight.
  5. Evidence Confidence is strictly separate from Risk Score (Commit 3).
  6. No randomness. Same input → same output.
  7. Risk score represents investigation priority, NOT fire probability.

Risk Tier thresholds (0–100 scale):
  CRITICAL  ≥ 75.0
  HIGH      ≥ 50.0
  MODERATE  ≥ 25.0
  LOW       < 25.0
"""

from __future__ import annotations

from typing import Any, Dict, List

from .normalization import METHODOLOGY_VERSION
from .dimensions import (
    WEIGHT_A_THERMAL,
    WEIGHT_B_PERSISTENCE,
    WEIGHT_C_INDUSTRIAL,
    WEIGHT_D_SPATIAL,
    WEIGHT_E_SPECTRAL,
    compute_dimension_a_thermal,
    compute_dimension_b_persistence,
    compute_dimension_c_industrial,
    compute_dimension_d_spatial,
    compute_dimension_e_spectral,
)


# ── Risk Tier ─────────────────────────────────────────────────────────────────

def get_risk_tier(risk_score: float) -> str:
    """
    Map a numerical risk score (0–100) to a named risk tier.

    Thresholds are fixed by the methodology and must not be adjusted
    without a formal methodology review.
    """
    if risk_score >= 75.0:
        return "CRITICAL"
    elif risk_score >= 50.0:
        return "HIGH"
    elif risk_score >= 25.0:
        return "MODERATE"
    else:
        return "LOW"


# ── Single-event scorer ───────────────────────────────────────────────────────

def score_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score a single thermal event dictionary deterministically.

    Parameters
    ----------
    event : dict
        Flat dictionary of evidence fields for one thermal event.
        All fields are optional; missing fields score zero for that feature
        without redistributing weight to present dimensions.

    Returns
    -------
    dict containing:
      - event_id             : str
      - methodology_version  : str
      - risk_score           : float  — rounded to 1 d.p., scale 0–100
      - risk_score_raw       : float  — unrounded weighted sum (0–1 internal)
      - risk_tier            : str    — LOW / MODERATE / HIGH / CRITICAL
      - thermal_dimension_score      : float (0–1)
      - persistence_dimension_score  : float (0–1)
      - industrial_dimension_score   : float (0–1)
      - spatial_dimension_score      : float (0–1)
      - spectral_dimension_score     : float (0–1)
      - dimensions           : dict   — full per-dimension detail
      - missing_evidence     : list   — explicitly named missing signals
      - contextual_data      : dict   — 0%-weight metadata
    """
    event_id = str(event.get("event_id", "UNKNOWN"))

    # ── Step 1: Compute all five dimensions ───────────────────────────────────
    dim_a = compute_dimension_a_thermal(event)
    dim_b = compute_dimension_b_persistence(event)
    dim_c = compute_dimension_c_industrial(event)
    dim_d = compute_dimension_d_spatial(event)
    dim_e = compute_dimension_e_spectral(event)

    # ── Step 2: Linear weighted aggregation ───────────────────────────────────
    # Weights are fixed. Missing dimensions contribute 0 — never redistributed.
    risk_raw = (
        dim_a["weighted_contribution"]
        + dim_b["weighted_contribution"]
        + dim_c["weighted_contribution"]
        + dim_d["weighted_contribution"]
        + dim_e["weighted_contribution"]
    )
    risk_score = round(risk_raw * 100.0, 1)
    risk_tier = get_risk_tier(risk_score)

    # ── Step 3: Audit missing evidence ────────────────────────────────────────
    missing_evidence: List[str] = []

    if dim_a["is_completely_missing"]:
        missing_evidence.append("dimension_A_thermal_missing")
    elif dim_a["missing_fields"]:
        missing_evidence.append(f"partial_thermal:{','.join(dim_a['missing_fields'])}")

    if dim_b["is_completely_missing"]:
        missing_evidence.append("dimension_B_persistence_missing")
    elif dim_b["missing_fields"]:
        missing_evidence.append(f"partial_persistence:{','.join(dim_b['missing_fields'])}")

    if dim_c["is_completely_missing"]:
        missing_evidence.append("dimension_C_industrial_missing")
    elif not dim_c["has_mapped_association"]:
        missing_evidence.append("osm_context:no_mapped_association")

    if dim_d["is_completely_missing"]:
        missing_evidence.append("dimension_D_spatial_missing")

    if dim_e["is_completely_missing"]:
        missing_evidence.append("dimension_E_spectral_missing")
        has_scene = dim_e["raw_inputs"].get("has_satellite_scene", 0)
        has_spectral = dim_e["raw_inputs"].get("has_spectral_features", 0)
        if has_scene == 0:
            missing_evidence.append("spectral_coverage:no_scene")
        elif has_spectral == 0:
            missing_evidence.append("spectral_coverage:extraction_failed")
    else:
        if dim_e["cloud_reliability"] < 0.5:
            missing_evidence.append("spectral_quality:degraded_cloud")
        if dim_e["temporal_reliability"] < 0.5:
            missing_evidence.append("temporal_relevance:stale")
        if dim_e["missing_fields"]:
            missing_evidence.append(f"partial_spectral:{','.join(dim_e['missing_fields'])}")

    # ── Step 4: Contextual data (0% risk weight) ──────────────────────────────
    contextual_data: Dict[str, Any] = {
        "worldcover_class": event.get("worldcover_class"),
        "worldcover_class_name": event.get("worldcover_class_name"),
        "osm_primary_category": event.get("osm_primary_category"),
        "osm_sub_category": event.get("osm_sub_category"),
        "osm_tier": event.get("osm_tier"),
        "distinct_satellites": event.get("distinct_satellites"),
    }

    return {
        "event_id": event_id,
        "methodology_version": METHODOLOGY_VERSION,
        "risk_score": risk_score,
        "risk_score_raw": float(risk_raw),
        "risk_tier": risk_tier,
        "thermal_dimension_score": float(dim_a["score"]),
        "persistence_dimension_score": float(dim_b["score"]),
        "industrial_dimension_score": float(dim_c["score"]),
        "spatial_dimension_score": float(dim_d["score"]),
        "spectral_dimension_score": float(dim_e["score"]),
        "dimensions": {
            "thermal": dim_a,
            "persistence": dim_b,
            "industrial": dim_c,
            "spatial": dim_d,
            "spectral": dim_e,
        },
        "missing_evidence": missing_evidence,
        "contextual_data": contextual_data,
    }
