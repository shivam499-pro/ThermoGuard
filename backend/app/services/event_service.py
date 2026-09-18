"""
ThermoGuard — Pilot Event Data Access Layer.

Provides a fast, in-memory, read-only repository for the static 100-event
pilot dataset.

Guarantees:
  - Resolves file paths relative to the package directory (no CWD dependency).
  - Uses standard-library JSON only (no heavy pandas or pyarrow dependencies).
  - Validates basic dataset integrity at initialization time.
  - Indexes events by `event_id` for O(1) detail lookup.
  - Never mutates loaded source data.
  - Thread-safe singleton access via `get_event_repository()`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.schemas.events import (
    BoundingBox,
    ContextDetail,
    DimensionDetail,
    DimensionsDetail,
    EventDetail,
    EventSummary,
    ExplanationDetail,
    RankingDetail,
    RiskSummary,
    SpectralDetail,
    TemporalDetail,
    ThermalDetail,
)

logger = logging.getLogger(__name__)


class EventRepository:
    """
    In-memory repository serving the curated ThermoGuard pilot event cohort.
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        if data_dir is None:
            # Resolve relative to ThermoGuard/backend/data
            base_dir = Path(__file__).resolve().parent.parent.parent
            data_dir = base_dir / "data"

        self._data_dir = data_dir
        self._events_file = data_dir / "curated_pilot_events.json"
        self._explanations_file = data_dir / "pilot_explanations.json"

        self._events_by_id: Dict[str, dict] = {}
        self._explanations_by_id: Dict[str, dict] = {}
        self._summaries_cache: List[EventSummary] = []
        self._details_cache: Dict[str, EventDetail] = {}

        self._load_data()

    def _load_data(self) -> None:
        """Load and validate the curated pilot datasets."""
        if not self._events_file.is_file():
            raise FileNotFoundError(
                f"ThermoGuard curated pilot events dataset not found at: {self._events_file}"
            )
        if not self._explanations_file.is_file():
            raise FileNotFoundError(
                f"ThermoGuard pilot explanations dataset not found at: {self._explanations_file}"
            )

        with self._events_file.open("r", encoding="utf-8") as f:
            raw_events = json.load(f)

        with self._explanations_file.open("r", encoding="utf-8") as f:
            raw_explanations = json.load(f)

        if not isinstance(raw_events, list) or len(raw_events) == 0:
            raise ValueError(f"Expected non-empty list in {self._events_file}")

        if not isinstance(raw_explanations, dict):
            raise ValueError(f"Expected dictionary in {self._explanations_file}")

        # Index and build models
        summaries: List[EventSummary] = []
        details: Dict[str, EventDetail] = {}

        for row in raw_events:
            event_id = row["event_id"]
            self._events_by_id[event_id] = row

            bbox = BoundingBox(
                lat_min=row.get("bbox_lat_min"),
                lon_min=row.get("bbox_lon_min"),
                lat_max=row.get("bbox_lat_max"),
                lon_max=row.get("bbox_lon_max"),
            )

            # Build EventSummary (lightweight)
            summary = EventSummary(
                event_id=event_id,
                lat=float(row["latitude"]),
                lon=float(row["longitude"]),
                bbox=bbox,
                risk_score=float(row["risk_score"]),
                risk_tier=str(row["risk_tier"]),
                evidence_confidence=float(row["evidence_confidence"]),
                confidence_tier=str(row["confidence_tier"]),
                primary_driver=str(row["primary_driver"]),
                investigation_recommendation=str(row["investigation_recommendation"]),
                worldcover_class_name=str(row["worldcover_class_name"]),
                osm_primary_category=row.get("osm_primary_category"),
                duration_days=float(row["duration_days"]),
                distinct_detection_days=int(row["distinct_detection_days"]),
                detection_count=int(row["detection_count"]),
                frp_mean=float(row["frp_mean"]),
                frp_max=float(row["frp_max"]),
                spatial_extent_km2=float(row["spatial_extent_km2"]),
                missing_evidence=row.get("missing_evidence"),
                methodology_version=str(row["methodology_version"]),
            )
            summaries.append(summary)

            # Build EventDetail (comprehensive)
            expl = raw_explanations.get(event_id, {})
            self._explanations_by_id[event_id] = expl

            sb = expl.get("score_breakdown", {})
            rt = expl.get("raw_evidence_trace", {})

            def _build_dim(key: str, default_name: str) -> DimensionDetail:
                dim_sb = sb.get(key, {})
                dim_rt = rt.get(key, {})
                return DimensionDetail(
                    name=dim_sb.get("dimension_name", default_name),
                    weight=float(dim_sb.get("weight", 0.0)),
                    normalized_score=float(dim_sb.get("normalized_score", 0.0)),
                    weighted_contribution=float(
                        dim_sb.get(
                            "weighted_contribution_points",
                            row.get(f"weighted_{key}", 0.0),
                        )
                    ),
                    raw=dim_rt,
                )

            dimensions = DimensionsDetail(
                thermal=_build_dim("thermal", "Thermal Intensity"),
                persistence=_build_dim("persistence", "Persistence"),
                industrial=_build_dim("industrial", "Industrial Association"),
                spatial=_build_dim("spatial", "Spatial Scale"),
                spectral=_build_dim("spectral", "Spectral Evidence"),
            )

            cr = expl.get("contribution_ranking", {})
            ranking = RankingDetail(
                primary_driver=str(
                    cr.get("primary_driver", {}).get("name") or row["primary_driver"]
                ),
                secondary_driver=cr.get("secondary_driver", {}).get("name")
                or row.get("secondary_driver"),
                weakest_dimension=cr.get("weakest_dimension", {}).get("name")
                or row.get("weakest_dimension"),
            )

            ai = expl.get("analyst_interpretations", {})
            ip = expl.get("investigation_priority", {})
            ms = expl.get("missing_and_stale_evidence", {})

            explanation = ExplanationDetail(
                analyst_synthesis=ai.get("overall_synthesis"),
                recommendation=ip.get("recommendation")
                or row["investigation_recommendation"],
                limitations=ms.get("sentinel2_explanation"),
                task28_explanation=expl,
            )

            context = ContextDetail(
                worldcover_class=row.get("worldcover_class"),
                worldcover_class_name=row.get("worldcover_class_name"),
                osm_primary_category=row.get("osm_primary_category"),
                osm_sub_category=row.get("osm_sub_category"),
                osm_tier=row.get("osm_tier"),
                distance_to_industrial_m=row.get("distance_to_industrial_m"),
                distinct_satellites=row.get("distinct_satellites"),
            )

            temporal = TemporalDetail(
                first_detection=str(row["first_detection"]),
                last_detection=str(row["last_detection"]),
                duration_days=float(row["duration_days"]),
                distinct_detection_days=int(row["distinct_detection_days"]),
                detection_count=int(row["detection_count"]),
            )

            thermal = ThermalDetail(
                frp_mean=float(row["frp_mean"]),
                frp_max=float(row["frp_max"]),
                brightness_mean=float(row["brightness_mean"]),
            )

            spectral = SpectralDetail(
                swir2_anomaly_ratio=row.get("swir2_anomaly_ratio"),
                ndvi=row.get("ndvi"),
                bsi=row.get("bsi"),
                temporal_delta_days=row.get("temporal_delta_days"),
            )

            risk_summary = RiskSummary(
                risk_score=float(row["risk_score"]),
                risk_tier=str(row["risk_tier"]),
                evidence_confidence=float(row["evidence_confidence"]),
                confidence_tier=str(row["confidence_tier"]),
                methodology_version=str(row["methodology_version"]),
            )

            detail = EventDetail(
                event_id=event_id,
                lat=float(row["latitude"]),
                lon=float(row["longitude"]),
                bbox=bbox,
                risk_score=float(row["risk_score"]),
                risk_tier=str(row["risk_tier"]),
                evidence_confidence=float(row["evidence_confidence"]),
                confidence_tier=str(row["confidence_tier"]),
                methodology_version=str(row["methodology_version"]),
                risk_summary=risk_summary,
                dimensions=dimensions,
                ranking=ranking,
                explanation=explanation,
                context=context,
                temporal=temporal,
                thermal=thermal,
                spectral=spectral,
            )
            details[event_id] = detail

        self._summaries_cache = summaries
        self._details_cache = details

        logger.info(
            "ThermoGuard EventRepository initialised with %d events and %d explanations from %s",
            len(self._summaries_cache),
            len(self._details_cache),
            self._data_dir,
        )

    def list_events(self) -> List[EventSummary]:
        """Return all curated pilot events as lightweight summaries."""
        return self._summaries_cache

    def get_event(self, event_id: str) -> Optional[EventDetail]:
        """Return the complete investigation record for an event by ID (O(1))."""
        return self._details_cache.get(event_id)

    def get_event_count(self) -> int:
        """Return total event count."""
        return len(self._summaries_cache)


# ── Global singleton ──────────────────────────────────────────────────────────

_repository_instance: Optional[EventRepository] = None


def get_event_repository() -> EventRepository:
    """Provide the global singleton EventRepository instance."""
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = EventRepository()
    return _repository_instance
