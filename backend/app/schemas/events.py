"""
ThermoGuard — Event Pydantic Schemas.

Defines the presentation/response data models for:
  - GET /events (EventListResponse, EventSummary)
  - GET /events/{event_id} (EventDetail)

Invariants:
  - Coordinates normalized to `lat` and `lon` without precision loss.
  - Bounding box represented as `{lat_min, lon_min, lat_max, lon_max}`.
  - Genuine null values preserved as Python None (JSON null).
  - No synthetic placeholder strings ("Unknown", "N/A", "nan").
  - Read-only models for verified pilot cohort presentation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ── GIS & Spatial ─────────────────────────────────────────────────────────────

class BoundingBox(BaseModel):
    """Geographic bounding box for a spatial cluster."""
    lat_min: Optional[float] = None
    lon_min: Optional[float] = None
    lat_max: Optional[float] = None
    lon_max: Optional[float] = None

    model_config = ConfigDict(extra="ignore")


# ── GET /events Summary ───────────────────────────────────────────────────────

class EventSummary(BaseModel):
    """
    Lightweight summary for map pin rendering, tabular views, and filtering.

    Omits heavy Task 28 explanation traces to ensure sub-millisecond payloads.
    """
    event_id: str
    lat: float
    lon: float
    bbox: BoundingBox
    risk_score: float
    risk_tier: str
    evidence_confidence: float
    confidence_tier: str
    primary_driver: str
    investigation_recommendation: str
    worldcover_class_name: str
    osm_primary_category: Optional[str] = None
    duration_days: float
    distinct_detection_days: int
    detection_count: int
    frp_mean: float
    frp_max: float
    spatial_extent_km2: float
    missing_evidence: Optional[str] = None
    methodology_version: str

    model_config = ConfigDict(extra="ignore")


class EventListResponse(BaseModel):
    """Container for the collection returned by GET /events."""
    count: int
    events: List[EventSummary]

    model_config = ConfigDict(extra="ignore")


# ── GET /events/{event_id} Sub-models ─────────────────────────────────────────

class RiskSummary(BaseModel):
    """High-level risk and evidence confidence metrics."""
    risk_score: float
    risk_tier: str
    evidence_confidence: float
    confidence_tier: str
    methodology_version: str

    model_config = ConfigDict(extra="ignore")


class DimensionDetail(BaseModel):
    """Mathematical decomposition for a single scoring dimension."""
    name: str
    weight: float
    normalized_score: float
    weighted_contribution: float
    raw: Dict[str, Any]

    model_config = ConfigDict(extra="ignore")


class DimensionsDetail(BaseModel):
    """Five locked scoring dimensions."""
    thermal: DimensionDetail
    persistence: DimensionDetail
    industrial: DimensionDetail
    spatial: DimensionDetail
    spectral: DimensionDetail

    model_config = ConfigDict(extra="ignore")


class RankingDetail(BaseModel):
    """Driver hierarchy based on weighted contribution points."""
    primary_driver: str
    secondary_driver: Optional[str] = None
    weakest_dimension: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ExplanationDetail(BaseModel):
    """Deterministic scientific interpretations and operational recommendations."""
    analyst_synthesis: Optional[str] = None
    recommendation: Optional[str] = None
    limitations: Optional[str] = None
    task28_explanation: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")


class ContextDetail(BaseModel):
    """Environmental, industrial, and sensor context (0% risk weight)."""
    worldcover_class: Optional[int] = None
    worldcover_class_name: Optional[str] = None
    osm_primary_category: Optional[str] = None
    osm_sub_category: Optional[str] = None
    osm_tier: Optional[int] = None
    distance_to_industrial_m: Optional[float] = None
    distinct_satellites: Optional[int] = None

    model_config = ConfigDict(extra="ignore")


class TemporalDetail(BaseModel):
    """Persistence duration and recurrence counts."""
    first_detection: str
    last_detection: str
    duration_days: float
    distinct_detection_days: int
    detection_count: int

    model_config = ConfigDict(extra="ignore")


class ThermalDetail(BaseModel):
    """Sensor-derived thermal energy measurements."""
    frp_mean: float
    frp_max: float
    brightness_mean: float

    model_config = ConfigDict(extra="ignore")


class SpectralDetail(BaseModel):
    """Sentinel-2 multispectral surface features."""
    swir2_anomaly_ratio: Optional[float] = None
    ndvi: Optional[float] = None
    bsi: Optional[float] = None
    temporal_delta_days: Optional[float] = None

    model_config = ConfigDict(extra="ignore")


# ── GET /events/{event_id} Detail ─────────────────────────────────────────────

class EventDetail(BaseModel):
    """
    Comprehensive investigation record for the detail/explanation drawer.

    Includes full mathematical score breakdown, scientific interpretation,
    spatial bounding box, and environmental context.
    """
    event_id: str
    lat: float
    lon: float
    bbox: BoundingBox
    risk_score: float
    risk_tier: str
    evidence_confidence: float
    confidence_tier: str
    methodology_version: str
    risk_summary: RiskSummary
    dimensions: DimensionsDetail
    ranking: RankingDetail
    explanation: ExplanationDetail
    context: ContextDetail
    temporal: TemporalDetail
    thermal: ThermalDetail
    spectral: SpectralDetail

    model_config = ConfigDict(extra="ignore")
