"""
ThermoGuard -- Amazon Bedrock Analyst Contract Schemas.

Defines the typed, Pydantic-validated contracts for:
  - BedrockAnalystInput  : deterministic evidence sent TO Bedrock as context
  - BedrockAnalystOutput : narrative returned FROM Bedrock (narrative only)
  - BedrockAnalystResponse : final merged response returned by the API

Design invariants
-----------------
1.  BedrockAnalystInput is constructed ENTIRELY from deterministic EventDetail
    fields.  No field is invented; every field maps to an existing backend source.

2.  BedrockAnalystOutput intentionally EXCLUDES risk_score, risk_tier,
    evidence_confidence, and confidence_tier.  Bedrock must not recalculate
    or overwrite these values.

3.  BedrockAnalystResponse is assembled by the backend service layer, which
    copies immutable deterministic scores from the EventDetail record AFTER
    Bedrock has returned.  The LLM output cannot influence those fields.

4.  Ground-truth / evaluation labels (is_confirmed_fire, label, ground_truth,
    validated_class, etc.) are explicitly excluded from BedrockAnalystInput.
    They do not exist in the curated pilot dataset and must not be fabricated.

Scientific guardrails documented here are enforced both at the prompt level
(in the service layer) and at the Pydantic validation level (field constraints).
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


# -- Input sub-models ----------------------------------------------------------

class BedrockRiskSummaryInput(BaseModel):
    """
    Immutable risk metrics passed to Bedrock AS CONTEXT -- not for Bedrock to
    recalculate.  These values come from the deterministic risk engine and
    are read-only by design.
    """

    risk_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description=(
            "Deterministic risk score [0-100] from the locked Phase IX methodology. "
            "Bedrock must NOT recalculate or alter this value."
        ),
    )
    risk_tier: str = Field(
        ...,
        pattern=r"^(LOW|MODERATE|HIGH|CRITICAL)$",
        description="Deterministic tier derived from risk_score thresholds.",
    )
    evidence_confidence: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description=(
            "Observational quality / corroboration score [0-100]. "
            "NOT a class probability. Bedrock must NOT alter this value."
        ),
    )
    confidence_tier: str = Field(
        ...,
        pattern=r"^(LOW|MEDIUM|HIGH)$",
        description="Deterministic tier derived from evidence_confidence thresholds.",
    )

    model_config = ConfigDict(extra="forbid")


class BedrockDriverHierarchyInput(BaseModel):
    """Which dimension drove the risk score most/least (deterministic ranking)."""

    primary_driver: str = Field(
        ...,
        description="Dimension with the highest weighted_contribution.",
    )
    secondary_driver: Optional[str] = Field(
        default=None,
        description="Dimension with the second-highest weighted_contribution.",
    )
    weakest_dimension: Optional[str] = Field(
        default=None,
        description="Dimension with the lowest weighted_contribution.",
    )

    model_config = ConfigDict(extra="forbid")


class BedrockThermalEvidenceInput(BaseModel):
    """VIIRS / MODIS thermal radiometry measurements."""

    frp_mean: Optional[float] = Field(
        default=None,
        description="Mean Fire Radiative Power [MW] across all detections.",
    )
    frp_max: Optional[float] = Field(
        default=None,
        description="Peak Fire Radiative Power [MW].",
    )
    brightness_mean: Optional[float] = Field(
        default=None,
        description="Mean brightness temperature [K].",
    )
    normalized_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Deterministic thermal dimension score [0-1].",
    )
    weighted_contribution: float = Field(
        ...,
        description="Points contributed to risk_score by this dimension.",
    )

    model_config = ConfigDict(extra="forbid")


class BedrockPersistenceEvidenceInput(BaseModel):
    """Temporal recurrence / duration measurements."""

    duration_days: Optional[float] = Field(
        default=None,
        description="Elapsed days between first and last detection.",
    )
    distinct_detection_days: Optional[int] = Field(
        default=None,
        description="Count of calendar days with at least one satellite detection.",
    )
    detection_count: Optional[int] = Field(
        default=None,
        description="Total VIIRS / MODIS detection pixel-events across the cluster.",
    )
    first_detection: Optional[str] = Field(
        default=None,
        description="ISO-8601 date of the earliest detection.",
    )
    last_detection: Optional[str] = Field(
        default=None,
        description="ISO-8601 date of the most recent detection.",
    )
    normalized_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Deterministic persistence dimension score [0-1].",
    )
    weighted_contribution: float = Field(
        ...,
        description="Points contributed to risk_score by this dimension.",
    )

    model_config = ConfigDict(extra="forbid")


class BedrockIndustrialEvidenceInput(BaseModel):
    """
    OSM industrial co-location evidence.

    IMPORTANT SCIENTIFIC CAVEAT:
    - OSM proximity is co-location evidence, NOT proof of industrial causation.
    - A null osm_primary_category means no OSM mapped feature was found within
      the threshold; it does NOT mean industry is absent.
    """

    osm_primary_category: Optional[str] = Field(
        default=None,
        description=(
            "Highest-tier OSM industrial category matched within threshold distance. "
            "Null = no mapped OSM feature found; does NOT confirm absence of industry."
        ),
    )
    osm_sub_category: Optional[str] = Field(
        default=None,
        description="OSM sub-category of the matched industrial feature.",
    )
    osm_tier: Optional[int] = Field(
        default=None,
        description="Industrial priority tier of the OSM match (1=highest).",
    )
    distance_to_industrial_m: Optional[float] = Field(
        default=None,
        description="Distance [metres] from event centroid to nearest matched OSM industrial feature.",
    )
    normalized_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Deterministic industrial dimension score [0-1].",
    )
    weighted_contribution: float = Field(
        ...,
        description="Points contributed to risk_score by this dimension.",
    )

    model_config = ConfigDict(extra="forbid")


class BedrockSpatialEvidenceInput(BaseModel):
    """Geographic spatial extent measurements."""

    spatial_extent_km2: Optional[float] = Field(
        default=None,
        description="Cluster bounding-box area [km2].",
    )
    normalized_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Deterministic spatial dimension score [0-1].",
    )
    weighted_contribution: float = Field(
        ...,
        description="Points contributed to risk_score by this dimension.",
    )

    model_config = ConfigDict(extra="forbid")


class BedrockSpectralEvidenceInput(BaseModel):
    """
    Sentinel-2 multispectral surface reflectance features.

    CRITICAL SCIENTIFIC CAVEAT:
    - SWIR bands (B11/B12) measure surface reflectance contrast, NOT surface
      temperature, NOT active combustion.  Bedrock must not claim otherwise.
    """

    swir2_anomaly_ratio: Optional[float] = Field(
        default=None,
        description=(
            "Sentinel-2 SWIR-2 anomaly ratio. Measures surface reflectance contrast. "
            "NOT a temperature reading. NOT confirmation of active combustion."
        ),
    )
    ndvi: Optional[float] = Field(
        default=None,
        description="Normalized Difference Vegetation Index [-1 to 1].",
    )
    bsi: Optional[float] = Field(
        default=None,
        description="Bare Soil Index.",
    )
    temporal_delta_days: Optional[float] = Field(
        default=None,
        description=(
            "Days elapsed between VIIRS detection and Sentinel-2 acquisition. "
            "Large values indicate stale spectral data."
        ),
    )
    normalized_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Deterministic spectral dimension score [0-1].",
    )
    weighted_contribution: float = Field(
        ...,
        description="Points contributed to risk_score by this dimension.",
    )

    model_config = ConfigDict(extra="forbid")


class BedrockObservedEvidenceInput(BaseModel):
    """Five locked scoring dimensions -- exactly the deterministic breakdown."""

    thermal: BedrockThermalEvidenceInput
    persistence: BedrockPersistenceEvidenceInput
    industrial: BedrockIndustrialEvidenceInput
    spatial: BedrockSpatialEvidenceInput
    spectral: BedrockSpectralEvidenceInput

    model_config = ConfigDict(extra="forbid")


class BedrockContextInput(BaseModel):
    """
    Environmental / land-cover context.

    Note: These carry 0% direct risk weight per locked Phase IX methodology.
    Bedrock must not treat them as deterministic risk drivers.
    """

    worldcover_class: Optional[int] = Field(
        default=None,
        description="ESA WorldCover numeric class code.",
    )
    worldcover_class_name: Optional[str] = Field(
        default=None,
        description="ESA WorldCover human-readable land-cover class.",
    )
    distinct_satellites: Optional[int] = Field(
        default=None,
        description="Number of distinct satellite platforms contributing detections.",
    )

    model_config = ConfigDict(extra="forbid")


# -- Top-level Bedrock Input Contract -----------------------------------------

class BedrockAnalystInput(BaseModel):
    """
    Complete, typed contract for the evidence payload sent to Amazon Bedrock.

    Construction rules
    ------------------
    - ALL fields map directly to existing EventDetail / pilot_explanations data.
    - No field is invented or approximated.
    - Ground-truth / evaluation labels (is_confirmed_fire, validated_class,
      label, ground_truth) are deliberately absent -- they do not exist in the
      pilot dataset and must not be fabricated.
    - Bedrock receives this as READ-ONLY context; it does not recompute scores.

    Guardrail enforcement
    ---------------------
    The scientific_guardrails field lists the rules Bedrock MUST follow.
    These are reiterated in the system prompt but stored here for auditability.
    """

    event_id: str = Field(
        ...,
        description="Unique ThermoGuard event identifier.",
    )
    methodology_version: str = Field(
        ...,
        description="Locked scoring methodology version string.",
    )
    risk_summary: BedrockRiskSummaryInput = Field(
        ...,
        description="Deterministic risk and confidence metrics (read-only context).",
    )
    driver_hierarchy: BedrockDriverHierarchyInput = Field(
        ...,
        description="Deterministic dimension contribution ranking.",
    )
    observed_evidence: BedrockObservedEvidenceInput = Field(
        ...,
        description="Five-dimension evidence breakdown from the deterministic engine.",
    )
    context: BedrockContextInput = Field(
        ...,
        description="Environmental context with 0% direct risk weight.",
    )
    data_limitations: List[str] = Field(
        default_factory=list,
        description=(
            "Missing or stale evidence narratives from missing_and_stale_evidence. "
            "Preserves observed evidence gaps for Bedrock's awareness."
        ),
    )
    baseline_recommendation: str = Field(
        ...,
        description=(
            "Deterministic investigation_priority.recommendation from the pilot "
            "explanations. Bedrock may elaborate but must not contradict this."
        ),
    )
    scientific_guardrails: List[str] = Field(
        default_factory=list,
        description=(
            "Mandatory scientific constraints Bedrock must follow. "
            "Populated from pilot_explanations.scientific_caveats."
        ),
    )

    model_config = ConfigDict(extra="forbid")


# -- Output sub-models --------------------------------------------------------

BedrockTriageStatus = Literal["Monitor", "Investigate", "Escalate", "Deprioritise"]


class BedrockTriageRecommendation(BaseModel):
    """
    Operational triage recommendation proposed by the AI analyst.

    Represents an advisory AI triage disposition. It does NOT replace or override
    the authoritative deterministic risk_tier or the baseline investigation priority.
    """

    status: BedrockTriageStatus = Field(
        ...,
        description=(
            "Operational AI triage disposition ('Monitor', 'Investigate', 'Escalate', "
            "'Deprioritise'). Advisory only; does NOT replace or override deterministic risk_tier."
        ),
    )
    rationale: str = Field(
        ...,
        min_length=20,
        description="Plain-language rationale for the triage status.",
    )
    action_checklist: List[str] = Field(
        ...,
        min_length=1,
        description="Ordered list of concrete next steps for the analyst.",
    )

    model_config = ConfigDict(extra="forbid")


# -- Top-level Bedrock Output Contract ----------------------------------------

class BedrockAnalystOutput(BaseModel):
    """
    Typed contract for the narrative payload returned FROM Amazon Bedrock.

    IMMUTABILITY RULE
    -----------------
    This model intentionally does NOT contain:
        - risk_score
        - risk_tier
        - evidence_confidence
        - confidence_tier

    These fields are sourced ONLY from the deterministic engine (EventDetail).
    If Bedrock returns any of these fields, the service layer must discard them
    and source the authoritative values from the EventDetail record.

    Validation guarantees
    ---------------------
    - ai_analyst_synthesis must be non-empty (min 50 chars).
    - evidence_citations must contain at least one entry.
    - triage_recommendation must be structurally valid.
    - extra fields are FORBIDDEN -- prevents LLM from sneaking in score fields.
    """

    ai_analyst_synthesis: str = Field(
        ...,
        min_length=50,
        description=(
            "Plain-language expert synthesis of the deterministic evidence. "
            "Must summarise the five-dimension evidence, drivers, and gaps. "
            "Must NOT claim validated fire classification or ground truth."
        ),
    )
    evidence_citations: List[str] = Field(
        ...,
        min_length=1,
        description=(
            "Specific evidence statements citing observed sensor measurements. "
            "Each entry must reference a real field from BedrockAnalystInput -- "
            "not invented or hallucinated values."
        ),
    )
    evidence_gaps_and_caveats: List[str] = Field(
        default_factory=list,
        description=(
            "List of evidence limitations, stale data notes, and scientific caveats. "
            "Must acknowledge missing evidence as a limitation, not as absence."
        ),
    )
    triage_recommendation: BedrockTriageRecommendation = Field(
        ...,
        description="Structured operational recommendation from the AI analyst.",
    )

    model_config = ConfigDict(extra="forbid")


# -- Final merged API response ------------------------------------------------

class BedrockAnalystResponse(BaseModel):
    """
    Final API response: deterministic fields + AI analyst narrative.

    Assembly invariant (enforced by the service layer, not by Bedrock):
    -------------------------------------------------------------------
    1.  Deterministic EventDetail is loaded from the in-memory repository.
    2.  risk_score, risk_tier, evidence_confidence, confidence_tier are copied
        verbatim from that record.
    3.  Bedrock is called with BedrockAnalystInput (context only).
    4.  BedrockAnalystOutput is received and validated.
    5.  This response is assembled by taking immutable fields from step 2 and
        the narrative from step 4 -- the LLM output never overwrites step 2.

    If Bedrock returns fields named risk_score / risk_tier / evidence_confidence /
    confidence_tier, the service layer MUST ignore or reject them.
    """

    # -- Immutable deterministic identity ------------------------------------
    event_id: str = Field(..., description="ThermoGuard event identifier.")
    methodology_version: str = Field(..., description="Locked scoring methodology version.")

    # -- Immutable deterministic scores (source-of-truth) --------------------
    risk_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description=(
            "IMMUTABLE: deterministic risk score. "
            "Always sourced from EventDetail; never from LLM output."
        ),
    )
    risk_tier: str = Field(
        ...,
        pattern=r"^(LOW|MODERATE|HIGH|CRITICAL)$",
        description="IMMUTABLE: deterministic risk tier. Always sourced from EventDetail.",
    )
    evidence_confidence: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description=(
            "IMMUTABLE: deterministic evidence confidence. "
            "Always sourced from EventDetail; never from LLM output."
        ),
    )
    confidence_tier: str = Field(
        ...,
        pattern=r"^(LOW|MEDIUM|HIGH)$",
        description=(
            "IMMUTABLE: deterministic confidence tier. "
            "Always sourced from EventDetail; never from LLM output."
        ),
    )

    # -- AI analyst narrative (from Bedrock) ---------------------------------
    ai_analyst_synthesis: str = Field(
        ..., description="Plain-language synthesis from the AI analyst."
    )
    evidence_citations: List[str] = Field(
        ..., description="Evidence statements cited by the AI analyst."
    )
    evidence_gaps_and_caveats: List[str] = Field(
        default_factory=list,
        description="Limitations and caveats from the AI analyst.",
    )
    triage_recommendation: BedrockTriageRecommendation = Field(
        ..., description="Structured triage recommendation from the AI analyst."
    )

    model_config = ConfigDict(extra="forbid")


# -- Guardrail constants -------------------------------------------------------

#: Fields that are authoritative deterministic outputs.
#: The service layer must assert these come from EventDetail, not from Bedrock.
IMMUTABLE_DETERMINISTIC_FIELDS: tuple = (
    "risk_score",
    "risk_tier",
    "evidence_confidence",
    "confidence_tier",
)

#: Fields that must NEVER appear in BedrockAnalystInput (ground-truth labels).
FORBIDDEN_GROUND_TRUTH_FIELDS: tuple = (
    "is_confirmed_fire",
    "validated_class",
    "ground_truth",
    "label",
    "true_positive",
    "false_positive",
    "evaluation_label",
    "gt_class",
)

#: Mandatory scientific caveats injected into every BedrockAnalystInput.
MANDATORY_SCIENTIFIC_GUARDRAILS: tuple = (
    "Risk score reflects observed physical/contextual evidence strength; NOT ground-truth validated.",
    "Evidence Confidence is observational quality/corroboration; NOT class probability.",
    "Sentinel-2 SWIR bands (B11/B12) measure surface reflectance contrast; NOT temperature or active combustion.",
    "OSM proximity indicates mapped infrastructure co-location; NOT proof of industrial causation.",
    "Missing OSM data does NOT confirm absence of industry.",
    "LOW risk + LOW confidence does NOT imply safety or confirmed absence of hazard.",
    "Missing evidence lowers the observed score on a fixed scale; must NOT be interpreted as lower real-world danger.",
    "You must NOT recalculate risk_score, risk_tier, evidence_confidence, or confidence_tier.",
    "You must NOT claim validated fire classification, confirmed active combustion, or emergency-response authority.",
    "You must NOT invent sensor observations or fabricate missing evidence values.",
    "You must NOT use ground-truth or evaluation labels as inference inputs.",
)
