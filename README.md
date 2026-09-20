# ThermoGuard

Satellite-driven thermal anomaly **investigation priority** for industrial fire risk, using geospatial evidence, a locked deterministic 5-dimension score, and a serverless AWS architecture.

**Investigation priority only — not fire confirmation.**

---

## Live demo (AWS)

| Surface | URL |
|---|---|
| **API health (open this, not the API root)** | https://svrtmrkr4b.execute-api.ap-south-1.amazonaws.com/health |
| **Events JSON** | https://svrtmrkr4b.execute-api.ap-south-1.amazonaws.com/api/events |
| **OpenAPI docs** | https://svrtmrkr4b.execute-api.ap-south-1.amazonaws.com/docs |
| **Region** | `ap-south-1` (Mumbai) |


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
| 10 Database |
