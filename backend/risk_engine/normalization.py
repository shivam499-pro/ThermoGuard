"""
ThermoGuard — Risk Engine Normalization.

Defines provisional pilot normalization anchors and per-feature normalization
functions for the 5-dimension deterministic risk model.

All anchors are provisional expert estimates requiring empirical calibration
once human-reviewed ground truth becomes available.

Normalization contract:
  - Each function returns (normalized_value: float, is_missing: bool).
  - normalized_value is always in [0.0, 1.0].
  - When the input is missing/NaN, returns (0.0, True).
  - When the input is present (even if zero), returns (clipped_value, False).
  - No imputation. Missing evidence scores zero for that feature.
"""

from __future__ import annotations

from typing import Optional, Union, Tuple

import numpy as np


# ── Version ───────────────────────────────────────────────────────────────────

METHODOLOGY_VERSION = "ThermoGuard-2026-09-18"

# ── Normalization anchors ─────────────────────────────────────────────────────
# Thermal Intensity (Dimension A)
FRP_MEAN_CEILING: float = 100.0       # MW — clip ceiling for frp_mean
FRP_MAX_CEILING: float = 500.0        # MW — clip ceiling for frp_max
BRIGHTNESS_FLOOR: float = 300.0       # K  — lower anchor (background fires)
BRIGHTNESS_RANGE: float = 70.0        # K  — range to ceiling (370 K)

# Persistence (Dimension B)
PERSISTENCE_DAYS_ANCHOR: float = 365.0     # days — log1p anchor
DETECTION_COUNT_ANCHOR: float = 50_000.0   # detections — log1p anchor

# Industrial Association (Dimension C)
OSM_DISTANCE_THRESHOLD: float = 5_000.0   # metres — proximity score threshold

# Spatial Scale (Dimension D)
SPATIAL_EXTENT_ANCHOR: float = 500.0      # km² — log1p anchor

# Spectral / Surface Evidence (Dimension E)
SWIR_ANOMALY_THRESHOLD: float = 1.0       # baseline contrast (no signal below)
SWIR_ANOMALY_RANGE: float = 5.0           # upper contrast clip (excess above 1.0)
SWIR_RATIO_CEILING: float = 2.0           # B12/B11 ratio ceiling


# ── Missing-value helper ──────────────────────────────────────────────────────

def is_missing(val: Optional[Union[float, int]]) -> bool:
    """Return True when a numeric value is None or NaN."""
    if val is None:
        return True
    try:
        return bool(np.isnan(float(val)))
    except (TypeError, ValueError):
        return True


# ── Thermal Intensity normalizers ─────────────────────────────────────────────

def normalize_frp_mean(val: Optional[float]) -> Tuple[float, bool]:
    """
    Fire Radiative Power (mean): clip(frp_mean, 0, 100) / 100.

    Returns (normalized, is_missing).
    """
    if is_missing(val):
        return 0.0, True
    clipped = float(np.clip(float(val), 0.0, FRP_MEAN_CEILING))
    return clipped / FRP_MEAN_CEILING, False


def normalize_frp_max(val: Optional[float]) -> Tuple[float, bool]:
    """
    Fire Radiative Power (peak): clip(frp_max, 0, 500) / 500.

    Returns (normalized, is_missing).
    """
    if is_missing(val):
        return 0.0, True
    clipped = float(np.clip(float(val), 0.0, FRP_MAX_CEILING))
    return clipped / FRP_MAX_CEILING, False


def normalize_brightness(val: Optional[float]) -> Tuple[float, bool]:
    """
    Brightness temperature: clip((brightness_mean - 300), 0, 70) / 70.

    Returns (normalized, is_missing).
    """
    if is_missing(val):
        return 0.0, True
    offset = float(val) - BRIGHTNESS_FLOOR
    clipped = float(np.clip(offset, 0.0, BRIGHTNESS_RANGE))
    return clipped / BRIGHTNESS_RANGE, False


# ── Persistence normalizers ───────────────────────────────────────────────────

def normalize_persistence_days(val: Optional[Union[float, int]]) -> Tuple[float, bool]:
    """
    Distinct detection days: log1p(days) / log1p(365).

    Returns (normalized, is_missing).
    """
    if is_missing(val):
        return 0.0, True
    v = max(0.0, float(val))
    norm = float(np.log1p(v) / np.log1p(PERSISTENCE_DAYS_ANCHOR))
    return float(np.clip(norm, 0.0, 1.0)), False


def normalize_detection_count(val: Optional[Union[float, int]]) -> Tuple[float, bool]:
    """
    Total detection count: log1p(count) / log1p(50 000).

    Returns (normalized, is_missing).
    """
    if is_missing(val):
        return 0.0, True
    v = max(0.0, float(val))
    norm = float(np.log1p(v) / np.log1p(DETECTION_COUNT_ANCHOR))
    return float(np.clip(norm, 0.0, 1.0)), False


# ── Industrial Association normalizers ───────────────────────────────────────

def normalize_osm_proximity(min_distance_m: Optional[float]) -> Tuple[float, bool]:
    """
    Convert minimum distance to industrial feature into a proximity score:
      - NULL/missing → 0.0 (no evidence of proximity)
      - ≤ 0 m        → 1.0 (inside or coincident with industrial polygon)
      - ≥ 5 000 m    → 0.0 (beyond threshold, no industrial context)
      - otherwise    → 1.0 - (min_distance_m / 5 000)

    Returns (normalized, is_missing).
    """
    if is_missing(min_distance_m):
        return 0.0, True
    d = float(min_distance_m)
    if d <= 0.0:
        return 1.0, False
    if d >= OSM_DISTANCE_THRESHOLD:
        return 0.0, False
    score = 1.0 - (d / OSM_DISTANCE_THRESHOLD)
    return float(np.clip(score, 0.0, 1.0)), False


def normalize_fraction(val: Optional[float]) -> Tuple[float, bool]:
    """
    Generic fraction [0, 1] normalizer — clips to valid range.

    Returns (normalized, is_missing).
    """
    if is_missing(val):
        return 0.0, True
    return float(np.clip(float(val), 0.0, 1.0)), False


# ── Spatial Scale normalizer ─────────────────────────────────────────────────

def normalize_spatial_extent(val: Optional[float]) -> Tuple[float, bool]:
    """
    Spatial event footprint: log1p(km²) / log1p(500).

    Returns (normalized, is_missing).
    """
    if is_missing(val):
        return 0.0, True
    v = max(0.0, float(val))
    norm = float(np.log1p(v) / np.log1p(SPATIAL_EXTENT_ANCHOR))
    return float(np.clip(norm, 0.0, 1.0)), False


# ── Spectral / Surface Evidence normalizers ──────────────────────────────────

def normalize_swir_anomaly(val: Optional[float]) -> Tuple[float, bool]:
    """
    SWIR2 anomaly ratio (surface reflectance contrast vs. background):
      - < 1.0  → 0.0 (no anomaly above background)
      - ≥ 1.0  → clip(ratio - 1.0, 0, 5) / 5

    Returns (normalized, is_missing).
    """
    if is_missing(val):
        return 0.0, True
    ratio = float(val)
    if ratio < SWIR_ANOMALY_THRESHOLD:
        return 0.0, False
    excess = ratio - SWIR_ANOMALY_THRESHOLD
    norm = float(np.clip(excess, 0.0, SWIR_ANOMALY_RANGE) / SWIR_ANOMALY_RANGE)
    return norm, False


def normalize_ndvi(val: Optional[float]) -> Tuple[float, bool]:
    """
    NDVI surface disturbance: clip(1.0 - ndvi, 0, 1).

    Lower vegetation density → higher surface disturbance score.

    Returns (normalized, is_missing).
    """
    if is_missing(val):
        return 0.0, True
    disturb = 1.0 - float(val)
    return float(np.clip(disturb, 0.0, 1.0)), False


def normalize_bsi(val: Optional[float]) -> Tuple[float, bool]:
    """
    Bare Soil Index: clip(bsi + 0.5, 0, 1).

    BSI typically ranges from −0.5 to +0.5; shift by 0.5 to bring into [0, 1].

    Returns (normalized, is_missing).
    """
    if is_missing(val):
        return 0.0, True
    shifted = float(val) + 0.5
    return float(np.clip(shifted, 0.0, 1.0)), False


def normalize_swir_ratio(val: Optional[float]) -> Tuple[float, bool]:
    """
    SWIR2 / SWIR1 band ratio: clip(ratio, 0, 2) / 2.

    Returns (normalized, is_missing).
    """
    if is_missing(val):
        return 0.0, True
    clipped = float(np.clip(float(val), 0.0, SWIR_RATIO_CEILING))
    return clipped / SWIR_RATIO_CEILING, False
