"""
ThermoGuard — Deterministic Risk Scoring Engine.

Locked 5-Dimension Additive Model:
  A: Thermal Intensity          30%
  B: Persistence                25%
  C: Industrial Association     20%
  D: Spatial Scale              10%
  E: Spectral / Surface Evidence 15%
  Total:                       100%

Evidence Confidence is a strictly separate quantity computed in Commit 3.
This package exports only the risk-scoring surface.

Scientific principles:
- Deterministic: same input → same output.
- No weight redistribution for missing evidence.
- Missing evidence is represented explicitly as 0-contribution (not imputed).
- Risk score represents investigation priority, NOT a probability of fire.
- No LLM, no Bedrock, no ML classifier.
"""

from __future__ import annotations

from .normalization import METHODOLOGY_VERSION
from .scoring import score_event, get_risk_tier
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

__all__ = [
    "METHODOLOGY_VERSION",
    "score_event",
    "get_risk_tier",
    "WEIGHT_A_THERMAL",
    "WEIGHT_B_PERSISTENCE",
    "WEIGHT_C_INDUSTRIAL",
    "WEIGHT_D_SPATIAL",
    "WEIGHT_E_SPECTRAL",
    "compute_dimension_a_thermal",
    "compute_dimension_b_persistence",
    "compute_dimension_c_industrial",
    "compute_dimension_d_spatial",
    "compute_dimension_e_spectral",
]
