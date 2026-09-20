"""
Optional Amazon Bedrock runtime invocation.

Default for the $0 hackathon window: assemble a contract-valid narrative from
the deterministic explanation already stored on EventDetail (no model spend).
Set BEDROCK_ENABLED=true to call bedrock-runtime with the locked prompt.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from app.schemas.bedrock import BedrockAnalystInput, BedrockAnalystOutput
from app.schemas.events import EventDetail

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are the ThermoGuard AI analyst. You receive deterministic evidence as "
    "read-only context. You must not recalculate risk_score, risk_tier, "
    "evidence_confidence, or confidence_tier. Return JSON matching "
    "BedrockAnalystOutput only."
)


def bedrock_enabled() -> bool:
    return os.environ.get("BEDROCK_ENABLED", "false").lower() in {"1", "true", "yes"}


def model_id() -> str:
    return os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")


def local_analyst_output(detail: EventDetail, bedrock_input: BedrockAnalystInput) -> BedrockAnalystOutput:
    """$0 path: narrative sourced only from existing deterministic explanation."""
    synthesis = (
        detail.explanation.analyst_synthesis
        or detail.explanation.recommendation
        or "Deterministic evidence assembled for investigation priority review."
    )
    if len(synthesis) < 50:
        synthesis = (
            f"{synthesis} Event {detail.event_id} has risk_score {detail.risk_score} "
            f"({detail.risk_tier}) with evidence_confidence {detail.evidence_confidence}. "
            "This is investigation priority only, not fire confirmation."
        )
    citations = [
        f"Primary driver {detail.ranking.primary_driver} from locked contribution ranking.",
        f"Thermal FRP mean {detail.thermal.frp_mean} MW; max {detail.thermal.frp_max} MW.",
        f"Persistence duration {detail.temporal.duration_days} days across "
        f"{detail.temporal.distinct_detection_days} detection days.",
    ]
    caveats = list(bedrock_input.data_limitations) or [
        "Missing evidence contributes zero points and must not be read as safety."
    ]
    recommendation = detail.explanation.recommendation or bedrock_input.baseline_recommendation
    return BedrockAnalystOutput(
        ai_analyst_synthesis=synthesis,
        evidence_citations=citations,
        evidence_gaps_and_caveats=caveats,
        triage_recommendation={
            "status": "Investigate",
            "rationale": (
                recommendation
                if recommendation and len(recommendation) >= 20
                else "Advisory triage from deterministic baseline recommendation and evidence gaps."
            ),
            "action_checklist": [
                "Review five-dimension decomposition on the event detail record.",
                "Confirm Sentinel-2 recency before treating spectral contrast as current.",
                "Treat OSM proximity as co-location evidence only.",
            ],
        },
    )


def invoke_bedrock_analyst(bedrock_input: BedrockAnalystInput) -> BedrockAnalystOutput:
    if not bedrock_enabled():
        raise RuntimeError("BEDROCK_ENABLED is false")

    import boto3

    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
    body: Dict[str, Any] = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "text": (
                            f"{SYSTEM_PROMPT}\n\n"
                            f"Guardrails:\n"
                            + "\n".join(f"- {g}" for g in bedrock_input.scientific_guardrails)
                            + "\n\nEvidence JSON:\n"
                            + bedrock_input.model_dump_json()
                        )
                    }
                ],
            }
        ],
        "inferenceConfig": {
            "maxTokens": int(os.environ.get("BEDROCK_MAX_TOKENS", "1024")),
            "temperature": float(os.environ.get("BEDROCK_TEMPERATURE", "0.1")),
        },
    }
    response = client.invoke_model(
        modelId=model_id(),
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    raw = json.loads(response["body"].read())
    text = _extract_text(raw)
    return BedrockAnalystOutput.model_validate_json(text)


def _extract_text(raw: Dict[str, Any]) -> str:
    if "output" in raw and isinstance(raw["output"], dict):
        message = raw["output"].get("message") or {}
        content = message.get("content") or []
        if content and isinstance(content[0], dict) and "text" in content[0]:
            return content[0]["text"]
    if "content" in raw and isinstance(raw["content"], list):
        return raw["content"][0].get("text", "{}")
    if "completion" in raw:
        return str(raw["completion"])
    return json.dumps(raw)
