"""
ThermoGuard -- Bedrock Analyst Contract Tests.

Tests:
  1.  Valid BedrockAnalystInput is built from a real EventDetail.
  2.  Valid BedrockAnalystOutput passes Pydantic validation.
  3.  Missing required output field raises ValidationError.
  4.  Invalid output type raises ValidationError.
  5.  Deterministic risk_score remains unchanged through assembly.
  6.  Deterministic risk_tier remains unchanged through assembly.
  7.  Deterministic evidence_confidence remains unchanged through assembly.
  8.  Ground-truth / evaluation fields are NOT included in BedrockAnalystInput.
  9.  Missing evidence is preserved (no fabrication, data limitations recorded).
  10. Scientific caveat / guardrail behavior (mandatory caveats present,
      score fields forbidden in LLM output, extra fields rejected).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.services.event_service import get_event_repository
from app.schemas.events import EventDetail
from app.schemas.bedrock import (
    BedrockAnalystInput,
    BedrockAnalystOutput,
    BedrockAnalystResponse,
    BedrockTriageRecommendation,
    BedrockTriageStatus,
    FORBIDDEN_GROUND_TRUTH_FIELDS,
    IMMUTABLE_DETERMINISTIC_FIELDS,
    MANDATORY_SCIENTIFIC_GUARDRAILS,
)
from app.services.bedrock_service import (
    assemble_analyst_response,
    assert_no_ground_truth_in_input,
    build_bedrock_input,
)


# -- Test Fixtures -------------------------------------------------------------

@pytest.fixture(scope="module")
def repo():
    return get_event_repository()


@pytest.fixture(scope="module")
def sample_event(repo) -> EventDetail:
    """Retrieve the first real event from the curated repository."""
    summaries = repo.list_events()
    assert len(summaries) > 0, "Curated events repository must not be empty"
    first_id = summaries[0].event_id
    detail = repo.get_event(first_id)
    assert detail is not None, f"EventDetail for {first_id} must exist"
    return detail


@pytest.fixture(scope="module")
def sample_events_all(repo) -> list[EventDetail]:
    """Retrieve all real curated EventDetail records."""
    summaries = repo.list_events()
    details = [repo.get_event(s.event_id) for s in summaries]
    return [d for d in details if d is not None]


@pytest.fixture
def valid_llm_output_data() -> dict:
    """A realistic valid BedrockAnalystOutput narrative dictionary."""
    return {
        "ai_analyst_synthesis": (
            "The cluster exhibits moderate thermal activity with persistent detections "
            "over multiple satellite passes, co-located near identified industrial zones."
        ),
        "evidence_citations": [
            "Thermal frp_mean is 14.2 MW across 5 detections.",
            "Persistence duration_days is 3.5 with 2 distinct detection days.",
            "Nearest OSM industrial feature mapped at 120m distance.",
        ],
        "evidence_gaps_and_caveats": [
            "Sentinel-2 spectral data was acquired 4.2 days after initial detection.",
            "Reflectance anomaly indicates surface contrast, not confirmed active flame.",
        ],
        "triage_recommendation": {
            "status": "Investigate",
            "rationale": "Persistent industrial thermal signal warranting secondary analyst confirmation.",
            "action_checklist": [
                "Review next available optical pass for plume confirmation.",
                "Cross-reference local industrial registry for facility operation hours.",
            ],
        },
    }


# -- 1. Valid Bedrock Input Creation ------------------------------------------

class TestValidBedrockInputCreation:
    def test_build_bedrock_input_from_real_event(self, sample_event: EventDetail):
        """BedrockAnalystInput builds successfully from a real EventDetail."""
        inp = build_bedrock_input(sample_event)

        assert isinstance(inp, BedrockAnalystInput)
        assert inp.event_id == sample_event.event_id
        assert inp.methodology_version == sample_event.methodology_version
        assert inp.risk_summary.risk_score == sample_event.risk_score
        assert inp.risk_summary.risk_tier == sample_event.risk_tier
        assert inp.risk_summary.evidence_confidence == sample_event.evidence_confidence
        assert inp.risk_summary.confidence_tier == sample_event.confidence_tier

    def test_build_bedrock_input_all_curated_events(self, sample_events_all: list[EventDetail]):
        """All 100 curated events successfully build valid BedrockAnalystInput."""
        for event in sample_events_all:
            inp = build_bedrock_input(event)
            assert inp.event_id == event.event_id
            assert inp.risk_summary.risk_score == event.risk_score
            assert inp.driver_hierarchy.primary_driver == event.ranking.primary_driver


# -- 2. Valid Bedrock Output Validation ---------------------------------------

class TestValidBedrockOutputValidation:
    def test_valid_output_passes_pydantic(self, valid_llm_output_data: dict):
        """A valid narrative output dictionary validates cleanly."""
        out = BedrockAnalystOutput(**valid_llm_output_data)
        assert len(out.ai_analyst_synthesis) >= 50
        assert len(out.evidence_citations) >= 1
        assert out.triage_recommendation.status == "Investigate"
        assert len(out.triage_recommendation.action_checklist) >= 1

    @pytest.mark.parametrize("status", ["Monitor", "Investigate", "Escalate", "Deprioritise"])
    def test_all_allowed_triage_statuses_accepted(self, valid_llm_output_data: dict, status: str):
        """Each allowed triage status ('Monitor', 'Investigate', 'Escalate', 'Deprioritise') is accepted."""
        data = dict(valid_llm_output_data)
        data["triage_recommendation"] = dict(data["triage_recommendation"], status=status)
        out = BedrockAnalystOutput(**data)
        assert out.triage_recommendation.status == status


# -- 3. Missing Required Output Field -----------------------------------------

class TestMissingRequiredOutputField:
    def test_missing_ai_analyst_synthesis_raises_error(self, valid_llm_output_data: dict):
        """Missing ai_analyst_synthesis must raise ValidationError."""
        data = dict(valid_llm_output_data)
        del data["ai_analyst_synthesis"]
        with pytest.raises(ValidationError) as exc_info:
            BedrockAnalystOutput(**data)
        assert "ai_analyst_synthesis" in str(exc_info.value)

    def test_missing_evidence_citations_raises_error(self, valid_llm_output_data: dict):
        """Missing evidence_citations must raise ValidationError."""
        data = dict(valid_llm_output_data)
        del data["evidence_citations"]
        with pytest.raises(ValidationError) as exc_info:
            BedrockAnalystOutput(**data)
        assert "evidence_citations" in str(exc_info.value)

    def test_empty_evidence_citations_raises_error(self, valid_llm_output_data: dict):
        """Empty evidence_citations list must raise ValidationError (min_length=1)."""
        data = dict(valid_llm_output_data)
        data["evidence_citations"] = []
        with pytest.raises(ValidationError) as exc_info:
            BedrockAnalystOutput(**data)
        assert "evidence_citations" in str(exc_info.value)

    def test_missing_triage_recommendation_raises_error(self, valid_llm_output_data: dict):
        """Missing triage_recommendation must raise ValidationError."""
        data = dict(valid_llm_output_data)
        del data["triage_recommendation"]
        with pytest.raises(ValidationError) as exc_info:
            BedrockAnalystOutput(**data)
        assert "triage_recommendation" in str(exc_info.value)


# -- 4. Invalid Output Type ---------------------------------------------------

class TestInvalidOutputType:
    def test_synthesis_as_integer_raises_error(self, valid_llm_output_data: dict):
        """ai_analyst_synthesis passed as integer must fail."""
        data = dict(valid_llm_output_data)
        data["ai_analyst_synthesis"] = 12345
        with pytest.raises(ValidationError):
            BedrockAnalystOutput(**data)

    def test_citations_as_string_raises_error(self, valid_llm_output_data: dict):
        """evidence_citations passed as string instead of list must fail."""
        data = dict(valid_llm_output_data)
        data["evidence_citations"] = "Single citation string"
        with pytest.raises(ValidationError):
            BedrockAnalystOutput(**data)

    def test_synthesis_too_short_raises_error(self, valid_llm_output_data: dict):
        """ai_analyst_synthesis under 50 characters fails min_length constraint."""
        data = dict(valid_llm_output_data)
        data["ai_analyst_synthesis"] = "Too short."
        with pytest.raises(ValidationError) as exc_info:
            BedrockAnalystOutput(**data)
        assert "ai_analyst_synthesis" in str(exc_info.value)

    @pytest.mark.parametrize(
        "invalid_status",
        ["", "ArbitraryStatus", "URGENT", "LOW", "CRITICAL", "123", "monitor", "investigate"],
    )
    def test_invalid_or_empty_triage_status_rejected(self, valid_llm_output_data: dict, invalid_status: str):
        """Invalid arbitrary or empty status strings must raise ValidationError."""
        data = dict(valid_llm_output_data)
        data["triage_recommendation"] = dict(data["triage_recommendation"], status=invalid_status)
        with pytest.raises(ValidationError) as exc_info:
            BedrockAnalystOutput(**data)
        assert "status" in str(exc_info.value)


# -- 5. Deterministic Risk Score Remains Unchanged ----------------------------

class TestDeterministicRiskScoreImmutability:
    def test_risk_score_is_exact_match(
        self, sample_event: EventDetail, valid_llm_output_data: dict
    ):
        """Backend assemble_analyst_response preserves exact deterministic risk_score."""
        llm_out = BedrockAnalystOutput(**valid_llm_output_data)
        resp = assemble_analyst_response(sample_event, llm_out)

        assert resp.risk_score == sample_event.risk_score
        assert isinstance(resp.risk_score, float)

    def test_llm_cannot_override_risk_score(
        self, sample_event: EventDetail, valid_llm_output_data: dict
    ):
        """Even if someone tried to forge risk_score in the output dict, schema forbids it."""
        forged_data = dict(valid_llm_output_data)
        forged_data["risk_score"] = 99.9  # Attempted override

        with pytest.raises(ValidationError) as exc_info:
            BedrockAnalystOutput(**forged_data)
        assert "Extra inputs are not permitted" in str(exc_info.value)

    @pytest.mark.parametrize(
        "score_field",
        ["risk_score", "risk_tier", "evidence_confidence", "confidence_tier"],
    )
    def test_bedrock_cannot_inject_deterministic_fields(
        self, valid_llm_output_data: dict, score_field: str
    ):
        """Bedrock cannot inject any deterministic score or tier fields; extra='forbid' rejects them."""
        forged_data = dict(valid_llm_output_data)
        forged_data[score_field] = 99.9 if "score" in score_field or "confidence" in score_field else "CRITICAL"
        with pytest.raises(ValidationError) as exc_info:
            BedrockAnalystOutput(**forged_data)
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_assemble_analyst_response_sources_deterministic_fields_from_event_detail(
        self, sample_event: EventDetail, valid_llm_output_data: dict
    ):
        """assemble_analyst_response binds immutable scores strictly from EventDetail."""
        llm_out = BedrockAnalystOutput(**valid_llm_output_data)
        resp = assemble_analyst_response(sample_event, llm_out)

        assert resp.risk_score == sample_event.risk_score
        assert resp.risk_tier == sample_event.risk_tier
        assert resp.evidence_confidence == sample_event.evidence_confidence
        assert resp.confidence_tier == sample_event.confidence_tier
        assert resp.ai_analyst_synthesis == llm_out.ai_analyst_synthesis
        assert resp.triage_recommendation.status == llm_out.triage_recommendation.status


# -- 6. Deterministic Risk Tier Remains Unchanged -----------------------------

class TestDeterministicRiskTierImmutability:
    def test_risk_tier_is_exact_match(
        self, sample_event: EventDetail, valid_llm_output_data: dict
    ):
        """Backend assemble_analyst_response preserves exact deterministic risk_tier."""
        llm_out = BedrockAnalystOutput(**valid_llm_output_data)
        resp = assemble_analyst_response(sample_event, llm_out)

        assert resp.risk_tier == sample_event.risk_tier

    def test_llm_cannot_override_risk_tier(
        self, valid_llm_output_data: dict
    ):
        """LLM cannot supply a risk_tier field; extra='forbid' rejects it."""
        forged_data = dict(valid_llm_output_data)
        forged_data["risk_tier"] = "CRITICAL"

        with pytest.raises(ValidationError):
            BedrockAnalystOutput(**forged_data)


# -- 7. Deterministic Evidence Confidence Remains Unchanged -------------------

class TestDeterministicEvidenceConfidenceImmutability:
    def test_evidence_confidence_is_exact_match(
        self, sample_event: EventDetail, valid_llm_output_data: dict
    ):
        """Backend assemble_analyst_response preserves evidence_confidence & confidence_tier."""
        llm_out = BedrockAnalystOutput(**valid_llm_output_data)
        resp = assemble_analyst_response(sample_event, llm_out)

        assert resp.evidence_confidence == sample_event.evidence_confidence
        assert resp.confidence_tier == sample_event.confidence_tier

    def test_llm_cannot_override_confidence_fields(
        self, valid_llm_output_data: dict
    ):
        """LLM cannot supply confidence fields; extra='forbid' rejects them."""
        for field in ("evidence_confidence", "confidence_tier"):
            forged_data = dict(valid_llm_output_data)
            forged_data[field] = 95.0 if "score" in field or "confidence" in field else "HIGH"
            with pytest.raises(ValidationError):
                BedrockAnalystOutput(**forged_data)


# -- 8. Ground-Truth / Evaluation Fields Excluded -----------------------------

class TestGroundTruthFieldsExcluded:
    def test_no_ground_truth_fields_in_built_input(self, sample_events_all: list[EventDetail]):
        """Verify assert_no_ground_truth_in_input passes for all curated events."""
        for event in sample_events_all:
            inp = build_bedrock_input(event)
            assert_no_ground_truth_in_input(inp)

    def test_serialized_input_contains_zero_forbidden_keys(self, sample_event: EventDetail):
        """Exhaustively check that no forbidden ground truth field appears in serialized input."""
        inp = build_bedrock_input(sample_event)
        dumped = inp.model_dump()

        def find_keys(obj):
            found = set()
            if isinstance(obj, dict):
                for k, v in obj.items():
                    found.add(k)
                    found.update(find_keys(v))
            elif isinstance(obj, list):
                for item in obj:
                    found.update(find_keys(item))
            return found

        all_keys = find_keys(dumped)
        for forbidden in FORBIDDEN_GROUND_TRUTH_FIELDS:
            assert forbidden not in all_keys, f"Forbidden key '{forbidden}' found in Bedrock input!"

    def test_forbid_extra_prevents_injecting_ground_truth(self, sample_event: EventDetail):
        """Attempting to construct BedrockAnalystInput with is_confirmed_fire fails."""
        inp = build_bedrock_input(sample_event)
        data = inp.model_dump()
        data["is_confirmed_fire"] = True

        with pytest.raises(ValidationError) as exc_info:
            BedrockAnalystInput(**data)
        assert "Extra inputs are not permitted" in str(exc_info.value)


# -- 9. Missing Evidence Is Preserved -----------------------------------------

class TestMissingEvidencePreservation:
    def test_missing_osm_evidence_preserved_as_none(self, sample_events_all: list[EventDetail]):
        """Events without OSM match preserve osm_primary_category as None (no fabrication)."""
        none_osm_events = [
            e for e in sample_events_all if e.context.osm_primary_category is None
        ]
        assert len(none_osm_events) > 0, "Curated dataset should contain events without OSM matches"

        for event in none_osm_events:
            inp = build_bedrock_input(event)
            assert inp.observed_evidence.industrial.osm_primary_category is None
            assert inp.observed_evidence.industrial.osm_tier is None

    def test_missing_spectral_evidence_preserved_as_none(self, sample_events_all: list[EventDetail]):
        """Events without Sentinel-2 match preserve spectral fields as None."""
        none_spectral_events = [
            e for e in sample_events_all if e.spectral.swir2_anomaly_ratio is None
        ]
        if none_spectral_events:
            for event in none_spectral_events:
                inp = build_bedrock_input(event)
                assert inp.observed_evidence.spectral.swir2_anomaly_ratio is None

    def test_data_limitations_populated_when_evidence_missing(
        self, sample_events_all: list[EventDetail]
    ):
        """Events with missing/stale evidence have data_limitations populated."""
        events_with_limitations = []
        for event in sample_events_all:
            inp = build_bedrock_input(event)
            if inp.data_limitations:
                events_with_limitations.append(inp)

        assert len(events_with_limitations) > 0, "Some events should report data limitations"
        for inp in events_with_limitations:
            for lim in inp.data_limitations:
                assert isinstance(lim, str)
                assert len(lim) > 0


# -- 10. Scientific Caveat / Guardrail Behavior -------------------------------

class TestScientificCaveatsAndGuardrails:
    def test_mandatory_guardrails_present_in_input(self, sample_event: EventDetail):
        """All mandatory scientific guardrails are present in BedrockAnalystInput."""
        inp = build_bedrock_input(sample_event)
        for guardrail in MANDATORY_SCIENTIFIC_GUARDRAILS:
            assert guardrail in inp.scientific_guardrails

    def test_immutable_deterministic_fields_constant(self):
        """Assert the list of immutable deterministic fields covers all 4 core scores."""
        expected = {"risk_score", "risk_tier", "evidence_confidence", "confidence_tier"}
        assert set(IMMUTABLE_DETERMINISTIC_FIELDS) == expected

    def test_response_contains_all_immutable_and_narrative_fields(
        self, sample_event: EventDetail, valid_llm_output_data: dict
    ):
        """BedrockAnalystResponse correctly bundles immutable scores with LLM narrative."""
        llm_out = BedrockAnalystOutput(**valid_llm_output_data)
        resp = assemble_analyst_response(sample_event, llm_out)

        # Check immutable deterministic fields
        assert resp.event_id == sample_event.event_id
        assert resp.methodology_version == sample_event.methodology_version
        assert resp.risk_score == sample_event.risk_score
        assert resp.risk_tier == sample_event.risk_tier
        assert resp.evidence_confidence == sample_event.evidence_confidence
        assert resp.confidence_tier == sample_event.confidence_tier

        # Check narrative fields
        assert resp.ai_analyst_synthesis == llm_out.ai_analyst_synthesis
        assert resp.evidence_citations == llm_out.evidence_citations
        assert resp.evidence_gaps_and_caveats == llm_out.evidence_gaps_and_caveats
        assert resp.triage_recommendation.status == llm_out.triage_recommendation.status
