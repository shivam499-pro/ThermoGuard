"""
ThermoGuard -- Bedrock Analyst Assembly Service.

Provides a pure-Python service layer that:
  1. Builds a BedrockAnalystInput from an EventDetail record (no invention).
  2. Assembles a BedrockAnalystResponse by merging immutable deterministic
     scores from EventDetail with the validated BedrockAnalystOutput narrative.
  3. Enforces immutability: deterministic fields are NEVER sourced from the
     LLM output.

IMPORTANT: This module does NOT call the Amazon Bedrock API.
The actual boto3/bedrock-runtime call is intentionally absent.
This module only defines the contract, assembly, and guardrail logic.
"""

from __future__ import annotations

import logging
from typing import List

from app.schemas.events import EventDetail
from app.schemas.bedrock import (
    BedrockAnalystInput,
    BedrockAnalystOutput,
    BedrockAnalystResponse,
    BedrockContextInput,
    BedrockDriverHierarchyInput,
    BedrockIndustrialEvidenceInput,
    BedrockObservedEvidenceInput,
    BedrockPersistenceEvidenceInput,
    BedrockRiskSummaryInput,
    BedrockSpatialEvidenceInput,
    BedrockSpectralEvidenceInput,
    BedrockThermalEvidenceInput,
    IMMUTABLE_DETERMINISTIC_FIELDS,
    FORBIDDEN_GROUND_TRUTH_FIELDS,
    MANDATORY_SCIENTIFIC_GUARDRAILS,
)

logger = logging.getLogger(__name__)


def build_bedrock_input(detail: EventDetail) -> BedrockAnalystInput:
    """
    Build a BedrockAnalystInput from an EventDetail record.

    Every field sourced here maps to an existing deterministic backend value.
    No field is invented, approximated, or fabricated.

    Ground-truth / evaluation labels are deliberately excluded because:
    - They do not exist in the curated pilot dataset.
    - Including them would violate the no-GT guardrail.

    Args:
        detail: Validated EventDetail from the in-memory EventRepository.

    Returns:
        BedrockAnalystInput ready to serialize as LLM context.
    """
    # -- Risk summary (immutable context, not for LLM to change) --------------
    risk_summary = BedrockRiskSummaryInput(
        risk_score=detail.risk_score,
        risk_tier=detail.risk_tier,
        evidence_confidence=detail.evidence_confidence,
        confidence_tier=detail.confidence_tier,
    )

    # -- Driver hierarchy (from deterministic contribution ranking) -----------
    driver_hierarchy = BedrockDriverHierarchyInput(
        primary_driver=detail.ranking.primary_driver,
        secondary_driver=detail.ranking.secondary_driver,
        weakest_dimension=detail.ranking.weakest_dimension,
    )

    # -- Thermal evidence (VIIRS/MODIS radiometry) ----------------------------
    thermal_evidence = BedrockThermalEvidenceInput(
        frp_mean=detail.thermal.frp_mean,
        frp_max=detail.thermal.frp_max,
        brightness_mean=detail.thermal.brightness_mean,
        normalized_score=detail.dimensions.thermal.normalized_score,
        weighted_contribution=detail.dimensions.thermal.weighted_contribution,
    )

    # -- Persistence evidence (temporal recurrence) ---------------------------
    persistence_evidence = BedrockPersistenceEvidenceInput(
        duration_days=detail.temporal.duration_days,
        distinct_detection_days=detail.temporal.distinct_detection_days,
        detection_count=detail.temporal.detection_count,
        first_detection=detail.temporal.first_detection,
        last_detection=detail.temporal.last_detection,
        normalized_score=detail.dimensions.persistence.normalized_score,
        weighted_contribution=detail.dimensions.persistence.weighted_contribution,
    )

    # -- Industrial evidence (OSM co-location) --------------------------------
    industrial_evidence = BedrockIndustrialEvidenceInput(
        osm_primary_category=detail.context.osm_primary_category,
        osm_sub_category=detail.context.osm_sub_category,
        osm_tier=detail.context.osm_tier,
        distance_to_industrial_m=detail.context.distance_to_industrial_m,
        normalized_score=detail.dimensions.industrial.normalized_score,
        weighted_contribution=detail.dimensions.industrial.weighted_contribution,
    )

    # -- Spatial evidence (geographic extent) ---------------------------------
    spatial_evidence = BedrockSpatialEvidenceInput(
        spatial_extent_km2=detail.dimensions.spatial.raw.get("spatial_extent_km2"),
        normalized_score=detail.dimensions.spatial.normalized_score,
        weighted_contribution=detail.dimensions.spatial.weighted_contribution,
    )

    # -- Spectral evidence (Sentinel-2 surface reflectance) -------------------
    spectral_evidence = BedrockSpectralEvidenceInput(
        swir2_anomaly_ratio=detail.spectral.swir2_anomaly_ratio,
        ndvi=detail.spectral.ndvi,
        bsi=detail.spectral.bsi,
        temporal_delta_days=detail.spectral.temporal_delta_days,
        normalized_score=detail.dimensions.spectral.normalized_score,
        weighted_contribution=detail.dimensions.spectral.weighted_contribution,
    )

    observed_evidence = BedrockObservedEvidenceInput(
        thermal=thermal_evidence,
        persistence=persistence_evidence,
        industrial=industrial_evidence,
        spatial=spatial_evidence,
        spectral=spectral_evidence,
    )

    # -- Context (0% risk weight) ---------------------------------------------
    context = BedrockContextInput(
        worldcover_class=detail.context.worldcover_class,
        worldcover_class_name=detail.context.worldcover_class_name,
        distinct_satellites=detail.context.distinct_satellites,
    )

    # -- Data limitations (missing/stale evidence narratives) -----------------
    data_limitations: List[str] = []
    task28 = detail.explanation.task28_explanation or {}
    ms = task28.get("missing_and_stale_evidence", {})
    narratives = ms.get("narratives", [])
    if isinstance(narratives, list):
        data_limitations = [str(n) for n in narratives if n]
    sentinel2_expl = ms.get("sentinel2_explanation")
    if sentinel2_expl and sentinel2_expl not in data_limitations:
        data_limitations.append(str(sentinel2_expl))

    # -- Baseline recommendation (deterministic investigation priority) -------
    ip = task28.get("investigation_priority", {})
    baseline_recommendation = (
        ip.get("recommendation")
        or detail.explanation.recommendation
        or ""
    )

    # -- Scientific guardrails (from pilot caveats + mandatory rules) ---------
    guardrails: List[str] = list(MANDATORY_SCIENTIFIC_GUARDRAILS)
    pilot_caveats = task28.get("scientific_caveats", [])
    if isinstance(pilot_caveats, list):
        for caveat in pilot_caveats:
            if caveat and caveat not in guardrails:
                guardrails.append(str(caveat))

    return BedrockAnalystInput(
        event_id=detail.event_id,
        methodology_version=detail.methodology_version,
        risk_summary=risk_summary,
        driver_hierarchy=driver_hierarchy,
        observed_evidence=observed_evidence,
        context=context,
        data_limitations=data_limitations,
        baseline_recommendation=baseline_recommendation,
        scientific_guardrails=guardrails,
    )


def assemble_analyst_response(
    detail: EventDetail,
    llm_output: BedrockAnalystOutput,
) -> BedrockAnalystResponse:
    """
    Assemble the final API response by merging deterministic fields with
    validated LLM narrative.

    IMMUTABILITY GUARANTEE:
    - risk_score, risk_tier, evidence_confidence, confidence_tier are ALWAYS
      sourced from the deterministic EventDetail record.
    - These fields are NEVER taken from llm_output, even if the LLM returned
      them.  BedrockAnalystOutput.model_config has extra="forbid" to prevent
      the LLM from injecting them, but this function provides an additional
      hard guarantee at the assembly layer.

    Args:
        detail:     Validated EventDetail from the in-memory EventRepository.
        llm_output: Validated BedrockAnalystOutput from the LLM.

    Returns:
        BedrockAnalystResponse with immutable deterministic scores.
    """
    logger.debug(
        "Assembling BedrockAnalystResponse for %s: risk_score=%s sourced from EventDetail",
        detail.event_id,
        detail.risk_score,
    )

    return BedrockAnalystResponse(
        # -- Immutable deterministic identity --------------------------------
        event_id=detail.event_id,
        methodology_version=detail.methodology_version,
        # -- Immutable deterministic scores (EventDetail is sole authority) --
        risk_score=detail.risk_score,
        risk_tier=detail.risk_tier,
        evidence_confidence=detail.evidence_confidence,
        confidence_tier=detail.confidence_tier,
        # -- AI analyst narrative (validated from LLM) -----------------------
        ai_analyst_synthesis=llm_output.ai_analyst_synthesis,
        evidence_citations=llm_output.evidence_citations,
        evidence_gaps_and_caveats=llm_output.evidence_gaps_and_caveats,
        triage_recommendation=llm_output.triage_recommendation,
    )


def assert_no_ground_truth_in_input(bedrock_input: BedrockAnalystInput) -> None:
    """
    Assert that no ground-truth / evaluation fields were accidentally included
    in the BedrockAnalystInput payload.

    This is a defensive check at the service boundary.  BedrockAnalystInput
    already uses extra="forbid", so ground-truth fields cannot be added via
    Pydantic construction.  This function provides an additional programmatic
    audit for use in tests and assertions.

    Args:
        bedrock_input: Constructed BedrockAnalystInput to audit.

    Raises:
        AssertionError: If any forbidden field is found in the serialized input.
    """
    serialized = bedrock_input.model_dump()
    serialized_keys = set(_collect_keys(serialized))
    forbidden_found = serialized_keys.intersection(set(FORBIDDEN_GROUND_TRUTH_FIELDS))
    assert not forbidden_found, (
        f"Ground-truth / evaluation fields found in BedrockAnalystInput: {forbidden_found}. "
        "These must never be sent to Bedrock."
    )


def _collect_keys(obj: object, keys: set = None) -> set:
    """Recursively collect all dictionary keys from a nested structure."""
    if keys is None:
        keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            _collect_keys(v, keys)
    elif isinstance(obj, list):
        for item in obj:
            _collect_keys(item, keys)
    return keys
