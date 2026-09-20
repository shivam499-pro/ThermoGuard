# ThermoGuard

Satellite-driven thermal anomaly **investigation priority** for industrial fire risk, using geospatial evidence, a locked deterministic 5-dimension score, and a serverless AWS architecture.

**Investigation priority only — not a fire confirmation.**

---

## Live demo (AWS)

| Surface | URL |
|---|---|
| **GIS dashboard (Amplify)** | https://main.d1z0ic5gt8xfky.amplifyapp.com |
| **Privacy** | https://main.d1z0ic5gt8xfky.amplifyapp.com/privacy.html |
| **Terms of use** | https://main.d1z0ic5gt8xfky.amplifyapp.com/terms.html |
| **API health (open this, not the API root)** | https://svrtmrkr4b.execute-api.ap-south-1.amazonaws.com/health |
| **Events JSON** | https://svrtmrkr4b.execute-api.ap-south-1.amazonaws.com/api/events |
| **OpenAPI docs** | https://svrtmrkr4b.execute-api.ap-south-1.amazonaws.com/docs |
| **Region** | `ap-south-1` (Mumbai) |

The API Gateway *origin* is `https://svrtmrkr4b.execute-api.ap-south-1.amazonaws.com`. Opening that path with no route (`/`) returns **404** — FastAPI has no homepage there. Use `/health` or `/api/events`.

---

## Current status

| Component | Status | Details |
|---|---|---|
| **Deterministic risk engine** | **Live** | Locked 5-dimension additive model (30/25/20/10/15). Scores are never overwritten by an LLM. |
| **Pilot dataset** | **Live** | 100 curated thermal events in DynamoDB (`thermoguard-events`). |
| **Public HTTPS API** | **Live** | FastAPI + Mangum on Lambda behind API Gateway. |
| **GIS dashboard** | **Live** | Static frontend on AWS Amplify, pointed at API Gateway. |
| **Serverless pipeline** | **Live** | Ingress-Lambda → SQS → Worker-Lambda; CloudWatch Logs; Terraform IaC. |
| **Bedrock contract** | **Implemented** | Typed `BedrockAnalystInput` / `BedrockAnalystOutput`; immutability + 11 scientific guardrails. |
| **Bedrock runtime** | **Wired, off by default** | `invoke_bedrock_analyst()` exists. Production uses `BEDROCK_ENABLED=false` (local assembly, $0 model spend). Set `true` to call Bedrock. |
| **Global Tables / Aurora pgvector** | **Designed, not enabled** | DynamoDB GSIs + vector cosine search are live. Replicas and Postgres pgvector stay off for cost. |

---

## Problem

VIIRS/MODIS detect huge volumes of thermal anomalies (coordinates, time, FRP) without enough context to triage:

- Expected industrial heat vs something that needs investigation?
- Persistent cluster vs a one-off spike?
- Nearby mapped industry and land cover?
- What **observable evidence** justifies analyst time?

## Solution

1. **Deterministic risk engine (authoritative)** — five locked dimensions → `risk_score` (0–100) and `risk_tier`.
2. **Evidence confidence (separate)** — data quality / corroboration (0–100), **not** fire probability.
3. **Advisory analyst layer** — narrative and triage **must not** change scores.

> The `risk_score` is an **investigation-priority / triage signal**. It is **not** a validated probability of active combustion.

---

## AWS architecture (5 services)

```
Analyst browser
      │
      ▼
AWS Amplify (CDN)  ── frontend/index.html + config.js
      │
      ▼
Amazon API Gateway (HTTP API)
      │
      ▼
AWS Lambda  thermoguard-ingress   (FastAPI / Mangum)
      │  enqueue
      ▼
Amazon SQS  thermoguard-scoring
      │
      ▼
AWS Lambda  thermoguard-worker    (out-of-band scoring / analyst assembly)
      │
      ▼
Amazon DynamoDB
  ├── thermoguard-events     (PK + GSIs)
  ├── thermoguard-jobs
  ├── thermoguard-semantic-cache
  └── thermoguard-vectors
      │
CloudWatch Logs  ← Lambda stdout (JSON)
Terraform        ← infra/terraform
```

The **14 architecture pillars** are patterns on these five services (two Lambdas, GSIs, SQS buffer, cache table, vector items, Terraform, GitHub Actions workflow). They are not 14 separate AWS products.

| Pillar | Mapping |
|---|---|
| 1 API Gateway | HTTP API `$default` → Ingress-Lambda |
| 2 CDN | Amplify Hosting |
| 3 Serverless compute | Lambda zip (Python 3.12), not a standing uvicorn server |
| 4 Two nodes | `thermoguard-ingress` + `thermoguard-worker` |
| 5 Async pool | Worker drains SQS; `score_event_out_of_band()` |
| 6 IaC | `infra/terraform` |
| 7 Logging | CloudWatch via Lambda stdout |
| 8 GitOps | `.github/workflows/gitops.yml` |
| 9 Message buffer | SQS `thermoguard-scoring` |
| 10 Database | DynamoDB pay-per-request |
| 11 Read/write split | PK writes; GSIs `risk_tier-index`, `methodology-index` |
| 12 Replicas | `enable_global_tables=false` (optional later) |
| 13 Semantic cache | Lambda LRU + `thermoguard-semantic-cache` |
| 14 Vector / RAG | DynamoDB embeddings + cosine search; optional `infra/sql/pgvector.sql` |

---

## Deterministic risk engine (locked)

Weights must not change:

| Dimension | Weight | Evidence |
|---|:---:|---|
| Thermal intensity | 30% | FRP mean/max, brightness |
| Persistence | 25% | Duration, detection days, count |
| Industrial association | 20% | Distance to mapped OSM industry |
| Spatial scale | 10% | Cluster area (km²) |
| Spectral / surface | 15% | Sentinel-2 SWIR-2 ratio, NDVI, BSI |

Tiers: **LOW** &lt; 25 · **MODERATE** 25–50 · **HIGH** 50–75 · **CRITICAL** ≥ 75.

Rules: missing evidence contributes **0**; **no** weight redistribution; WorldCover/OSM category are **context only**; confidence is **not** fire probability; LLMs **cannot** override scores.

**Scientific distinctions:** Sentinel-2 SWIR is reflectance contrast, **not** temperature. OSM proximity is co-location, **not** causation. Missing OSM ≠ “no industry.”

---

## API

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` | Liveness |
| `GET` | `/api/events` | 100 event summaries (map + list) |
| `GET` | `/api/events/{event_id}` | Full investigation record |
| `POST` | `/api/events/{event_id}/analyst-jobs` | 202 — enqueue worker job |
| `GET` | `/api/jobs/{job_id}` | Job status / assembled narrative |
| `GET` | `/api/events/{event_id}/similar` | Vector neighbors (cosine) |
| `GET` | `/docs` | OpenAPI |

---

## Local development

```bash
git clone https://github.com/shivam499-pro/ThermoGuard.git
cd ThermoGuard/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests/ -q
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend: `frontend/config.js` → `http://localhost:8000` locally, API Gateway URL in AWS.

Package Lambda **without Docker**:

```bash
cd backend
python scripts/package_lambda.py
```

---

## Deploy notes

- Region: `ap-south-1`
- Keep `bedrock_enabled = false` and `enable_global_tables = false` unless you accept extra cost
- Seed: `python scripts/seed_dynamodb.py` with `STORAGE_BACKEND=dynamodb`
- Do not commit `.venv`, `backend/dist`, `terraform.tfstate`, or `*.tfvars`

---

## Tests

```bash
python -m pytest backend/tests/ -q
```

Core API, repository, Bedrock **contract** (no live Bedrock), plus serverless job/vector helpers.

---

## What we did not redesign

Risk weights, tier cutoffs, missing-data zeros, confidence semantics, score immutability, ground-truth prohibition, advisory-only triage, and the 11 scientific guardrails stay locked.
