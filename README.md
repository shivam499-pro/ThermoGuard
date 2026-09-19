# ThermoGuard

Satellite-driven thermal anomaly investigation priority and industrial fire risk assessment using geospatial evidence, deterministic multi-dimension scoring, and AWS cloud architecture.

---

## Current Status

| Component | Status | Details |
|---|---|---|
| **Deterministic Risk Engine** | **IMPLEMENTED** | Locked 5-dimension additive model (30/25/20/10/15), fixed thresholds, zero weight redistribution. |
| **Pilot Event Dataset** | **IMPLEMENTED** | 100 curated real-world thermal events with full score decompositions and explanation traces. |
| **Backend REST API** | **IMPLEMENTED** | FastAPI endpoints (`/health`, `/api/events`, `/api/events/{event_id}`) serving in-memory repository. |
| **Explainability & Auditability** | **IMPLEMENTED** | Driver hierarchy ranking, raw evidence traces, data limitation notices, and pilot recommendations. |
| **Bedrock Analyst Contract** | **IMPLEMENTED** | Typed Pydantic v2 input (`BedrockAnalystInput`) and narrative output (`BedrockAnalystOutput`) models. |
| **Score Immutability Architecture** | **IMPLEMENTED** | Assembly service guarantees deterministic scores are strictly sourced from `EventDetail`, never from the LLM. |
| **Scientific Guardrails** | **IMPLEMENTED** | Mandatory scientific caveats validated by schema; ground-truth / evaluation labels strictly forbidden. |
| **Regression & Contract Tests** | **IMPLEMENTED** | 129 passing backend tests (including 48 Bedrock contract tests) with 0 regressions. |
| **AWS Bedrock Runtime Invocation** | **NOT IMPLEMENTED** | `boto3` Bedrock runtime client and prompt execution layer are not yet wired. |
| **AWS Cloud Infrastructure** | **NOT IMPLEMENTED** | Lambda, API Gateway, IAM roles, and CloudWatch have not yet been provisioned. |
| **Public HTTPS / Cloud Deployment**| **NOT IMPLEMENTED** | No live public API endpoint or production cloud deployment exists yet. |
| **End-to-End Cloud Pipeline** | **NOT IMPLEMENTED** | Cloud workflow connecting deployed frontend, API Gateway, Lambda, and Bedrock is pending. |

### Current Handoff Point

> **The project is now ready for the AWS infrastructure / Bedrock runtime integration phase.**
>
> **Yusuf should START HERE.**
>
> **Yusuf should NOT redesign the deterministic scoring methodology.** The core scoring algorithms, weights, thresholds, and guardrails have been audited and locked. The next phase is strictly to operationalize the existing backend and Bedrock contract on AWS.

---

## Project Purpose

### The Problem
Satellite thermal sensors (such as VIIRS and MODIS) detect tens of thousands of thermal anomalies across the globe daily. Raw hotspot detections provide coordinates, acquisition timestamps, and radiometric intensity (FRP), but they lack surrounding spatial, temporal, and contextual intelligence. Critical operational questions remain unanswered:
- Is this an expected operational process (e.g., flaring at an oil refinery, slag dumping at a steel mill) or an accidental industrial fire?
- Has this location exhibited persistent thermal activity over weeks, or is this an abrupt new occurrence?
- What land-cover types and mapped industrial infrastructure surround the centroid?
- What concrete physical evidence supports prioritizing this event for field or analyst inspection?

### The Solution
ThermoGuard integrates independent spatial, temporal, and radiometric evidence sources into an explainable, deterministic investigation-priority assessment. It separates mathematical evidence evaluation from AI narrative synthesis:
1. **Deterministic Risk Engine (Authoritative)**: Evaluates observable evidence across five locked dimensions to calculate a numerical `risk_score` (0–100) and assign an operational `risk_tier`.
2. **Evidence Confidence (Separate)**: Quantifies sensor data corroboration, observation freshness, and multi-satellite agreement on a distinct scale (0–100).
3. **Amazon Bedrock Analyst Layer (Advisory)**: Receives the deterministic findings as read-only context and produces structured plain-language synthesis, citations, and advisory triage recommendations without altering scores.

> [!IMPORTANT]
> **Scientific Clarification on Risk Scores:**
> The ThermoGuard `risk_score` represents an **INVESTIGATION PRIORITY / TRIAGE SIGNAL** based on observable physical and spatial evidence. It is **NOT** a validated empirical probability of active combustion or wildfire occurrence.

---

## Current Architecture

```
[ LOCAL SOURCE REPO — IMPLEMENTED ]
NASA FIRMS + Sentinel-2 + OSM + ESA WorldCover
                     │
                     ▼
       Deterministic Risk Engine (risk_engine/)
       ├── Thermal Intensity (30%)
       ├── Persistence (25%)
       ├── Industrial Association (20%)
       ├── Spatial Scale (10%)
       └── Spectral / Surface Evidence (15%)
                     │
                     ▼
          authoritative scores (0–100)
          ├── risk_score + risk_tier
          └── evidence_confidence + confidence_tier
                     │
                     ▼
          EventDetail Record (app/services/event_service.py)
                     │
                     ▼
       Bedrock Contract Foundation (app/schemas/bedrock.py)
       ├── build_bedrock_input() -> BedrockAnalystInput
       ├── Mandatory Scientific Guardrails Validated
       └── Forbidden Ground-Truth Exclusion Verified
                     │
                     ▼
========================================================================
[ AWS CLOUD INFRASTRUCTURE — PLANNED / NEXT PHASE (YUSUF) ]
========================================================================
                     │
                     ▼
       AWS Bedrock Runtime Integration Layer
       ├── boto3 Bedrock runtime client
       ├── Prompt formatting with BedrockAnalystInput payload
       └── LLM response parsing into BedrockAnalystOutput
                     │
                     ▼
       Response Assembly & Immutability Lock
       └── assemble_analyst_response(detail, llm_output) -> BedrockAnalystResponse
           (Locks deterministic scores from EventDetail; LLM cannot override)
                     │
                     ▼
       Serverless AWS Hosting [TARGET / PLANNED ARCHITECTURE]
       ├── AWS Lambda (FastAPI / Mangum handler)
       ├── Amazon API Gateway (HTTP/REST API routing, CORS)
       ├── Amazon CloudWatch (Structured audit logging, operational alarms)
       └── AWS IAM (Least-privilege role for bedrock:InvokeModel)
                     │
                     ▼
       GIS Dashboard Frontend (Static hosting / AWS Amplify)
```

---

## Deterministic Risk Engine — Authoritative

The deterministic risk engine (`backend/risk_engine/`) is the sole authoritative calculation engine. It computes an additive risk score from 0.0 to 100.0.

### Locked Dimension Weights

| Dimension | Key | Weight | Observable Evidence |
|---|---|:---:|---|
| **Thermal Intensity** | Dimension A | **30%** | Mean Fire Radiative Power (MW), Peak FRP, brightness temperature. |
| **Persistence** | Dimension B | **25%** | Duration in days, distinct detection days, total detection pixel count. |
| **Industrial Association** | Dimension C | **20%** | Distance to nearest matched OpenStreetMap industrial facility (metres). |
| **Spatial Scale** | Dimension D | **10%** | Bounding box spatial extent / cluster area (km²). |
| **Spectral / Surface Evidence**| Dimension E | **15%** | Sentinel-2 SWIR-2 anomaly ratio, NDVI vegetation index, Bare Soil Index. |
| **Total** | | **100%** | Fixed additive model. |

### Operational Risk Tier Thresholds

- **LOW**: score < 25
- **MODERATE**: 25 <= score < 50
- **HIGH**: 50 <= score < 75
- **CRITICAL**: score >= 75

### Inviolable Engine Rules
1. **Missing Evidence Contributes Zero**: If an observation is missing (e.g., no cloud-free Sentinel-2 pass, no OSM match), that dimension contributes `0.0` points.
2. **Zero Weight Redistribution**: The weights of missing dimensions are **never** redistributed to available dimensions. The denominator remains 100%.
3. **Contextual Variables Carry 0% Direct Risk Weight**: ESA WorldCover land cover class and OSM facility category codes provide contextual metadata only. They do not multiply or add risk points.
4. **Evidence Confidence is Independent**: Evidence confidence (0–100) measures sensor corroboration and data freshness. A low risk score with low confidence indicates sparse or degraded data, **not** verified safety.
5. **Score Immutability**: LLMs, Bedrock models, and external services must **never** recalculate, adjust, or override risk scores or risk tiers.

---

## Evidence Sources & Scientific Clarifications

The pilot cohort is built upon real-world observations from multiple independent sensors:

- **NASA FIRMS (MODIS / VIIRS)**: Satellite radiometry measuring active thermal emissions (MW and Kelvin).
- **Temporal Persistence**: Recurrence history over the detection cluster duration.
- **OpenStreetMap (OSM)**: Proximity to mapped infrastructure features (refineries, power plants, manufacturing).
- **Sentinel-2 Multispectral**: High-resolution optical/SWIR surface reflectance indices (SWIR-2 B12/B11 contrast, NDVI, BSI).
- **ESA WorldCover**: 10-metre global land cover classification context.

> [!WARNING]
> **Mandatory Scientific Distinctions:**
> - **Sentinel-2 SWIR Reflectance**: Sentinel-2 Short-Wave Infrared (B11/B12) bands measure surface reflectance contrast against baseline imagery. They are **NOT** direct thermal radiometer measurements and must **never** be described as combustion temperatures.
> - **OSM Proximity**: Proximity to an OSM feature is co-location evidence, **NOT** proof of industrial causation.
> - **Missing OSM Features**: OpenStreetMap is a crowdsourced database with incomplete coverage. Missing OSM features indicate an absence of mapped data in OSM, **NOT** confirmed absence of industrial infrastructure.

---

## Explainability & Auditability

ThermoGuard provides end-to-end mathematical transparency for every evaluated event:
- **Driver Hierarchy**: Ranks dimensions by contribution points to identify the `primary_driver`, `secondary_driver`, and `weakest_dimension`.
- **Mathematical Decomposition**: Every dimension exposes its raw measurement, normalized score (0.0–1.0), fixed weight, and point contribution to the final score.
- **Limitation Tracking**: Explicitly records data gaps (e.g., stale optical imagery, acquisition delays) in `data_limitations`.
- **Baseline Operational Recommendations**: Sourced deterministically from pilot analysis (e.g., *"Needs additional satellite verification"*, *"Confident low-risk event"*).

---

## Current API Endpoints

The backend is implemented in FastAPI (`backend/app/main.py`). The following endpoints are implemented, tested, and active:

| Method | Path | Description | Response Model |
|---|---|---|---|
| `GET` | `/health` | System liveness probe and service verification. | `HealthResponse` |
| `GET` | `/api/events` | List all 100 curated pilot events as lightweight summaries for GIS map rendering. | `EventListResponse` |
| `GET` | `/api/events/{event_id}` | Retrieve comprehensive investigation detail for a single event by ID (O(1) lookup). | `EventDetail` |
| `GET` | `/docs` | Interactive OpenAPI / Swagger UI documentation. | HTML |
| `GET` | `/redoc` | Alternative ReDoc API documentation. | HTML |

*(Note: Bedrock runtime invocation endpoints are planned for the upcoming AWS phase and are not yet mounted).*

---

## Bedrock Contract Foundation

Defined in `backend/app/schemas/bedrock.py` and assembled in `backend/app/services/bedrock_service.py`:

```
Deterministic EventDetail
          │
          ▼
build_bedrock_input() ──────► BedrockAnalystInput (Validated context sent to LLM)
                                   │
                                   ▼
                             [Amazon Bedrock]
                                   │
                                   ▼
BedrockAnalystOutput ────────► Pydantic Validation (Narrative & Triage only)
                                   │
                                   ▼
assemble_analyst_response() ─► BedrockAnalystResponse (API response)
  ├── risk_score (FROM EventDetail)
  ├── risk_tier (FROM EventDetail)
  ├── evidence_confidence (FROM EventDetail)
  ├── confidence_tier (FROM EventDetail)
  └── narrative + triage (FROM BedrockAnalystOutput)
```

### Contract Guarantees
- **Immutable Fields**: `risk_score`, `risk_tier`, `evidence_confidence`, and `confidence_tier` are never accepted from the LLM. `BedrockAnalystOutput` forbids them (`extra="forbid"`), and `assemble_analyst_response` copies them strictly from `EventDetail`.
- **Advisory Triage Dispositions**: `BedrockTriageRecommendation.status` is strictly typed as:
  ```python
  BedrockTriageStatus = Literal["Monitor", "Investigate", "Escalate", "Deprioritise"]
  ```
  > [!IMPORTANT]
  > There is **NO** deterministic mapping from `risk_tier` to triage status (e.g., `LOW` does NOT automatically map to `Monitor`). Triage status is an advisory AI recommendation and does not replace deterministic risk tiers.
- **Mandatory Guardrail Validation**: `BedrockAnalystInput.scientific_guardrails` is schema-required and validated by a `@field_validator` asserting that all 11 mandatory guardrail statements are present.
- **Ground-Truth Prohibition**: Ground-truth / evaluation labels (`is_confirmed_fire`, `validated_class`, `ground_truth`, `label`, `true_positive`, `false_positive`, `evaluation_label`, `gt_class`) are strictly forbidden and recursively checked via `assert_no_ground_truth_in_input()`.

---

## Scientific Safety & Guardrails

The following 11 mandatory guardrails are codified in `MANDATORY_SCIENTIFIC_GUARDRAILS` and enforced across the contracts:

1. Risk score reflects observed physical/contextual evidence strength; NOT ground-truth validated.
2. Evidence Confidence is observational quality/corroboration; NOT class probability.
3. Sentinel-2 SWIR bands (B11/B12) measure surface reflectance contrast; NOT temperature or active combustion.
4. OSM proximity indicates mapped infrastructure co-location; NOT proof of industrial causation.
5. Missing OSM data does NOT confirm absence of industry.
6. LOW risk + LOW confidence does NOT imply safety or confirmed absence of hazard.
7. Missing evidence lowers the observed score on a fixed scale; must NOT be interpreted as lower real-world danger.
8. You must NOT recalculate risk_score, risk_tier, evidence_confidence, or confidence_tier.
9. You must NOT claim validated fire classification, confirmed active combustion, or emergency-response authority.
10. You must NOT invent sensor observations or fabricate missing evidence values.
11. You must NOT use ground-truth or evaluation labels as inference inputs.

---

## Test Status

The test suite is fully passing and verified via pytest:

```bash
# Run entire backend test suite
python -m pytest backend/tests/ -q
```

**Verified Test Results:**
- **Total Backend Tests**: **129 passed**, 1 warning in ~3.0s
- **Bedrock Contract Tests (`test_bedrock_contract.py`)**: **48 passed**
- **Core API & Repository Tests (`test_events.py`, `test_main.py`)**: **81 passed**

*(Note: The 48 Bedrock tests are pure-Python contract and immutability tests. They do not invoke live AWS Bedrock APIs).*

---

## Scientific & Product Limitations

- **Investigation Priority Only**: The risk score is an operational triage signal, not an empirical probability of fire.
- **No Machine Learning Classifier**: The system currently uses locked deterministic heuristics; there is no statistical ML classifier or neural network in the risk scoring engine.
- **No Ground-Truth Fire Labels**: The pilot dataset does not contain empirical ground-truth fire verification labels.
- **No Industrial Process Classifier**: The system does not yet empirically distinguish controlled industrial heat processes from accidental industrial fires.
- **Contract Stage Only**: The Bedrock implementation is currently a contract and assembly foundation; live AWS Bedrock inference and cloud deployments are pending.

---

## AWS Infrastructure Handoff — Yusuf

> ### START HERE
> Yusuf, this section outlines your roadmap to connect the tested backend and Bedrock contract to AWS infrastructure. Follow the phases in dependency order.

```
                  ┌─────────────────────────────────────────────────┐
                  │ Phase A: AWS & Bedrock Prerequisites            │
                  │ - Verify AWS credentials, region & Bedrock model│
                  │ - Define environment configuration              │
                  └──────────────────────┬──────────────────────────┘
                                         │
                                         ▼
                  ┌─────────────────────────────────────────────────┐
                  │ Phase B: Runtime Integration Layer              │
                  │ - Add boto3 to backend                          │
                  │ - Implement Bedrock runtime client              │
                  │ - Wire BedrockAnalystInput -> LLM -> Output     │
                  └──────────────────────┬──────────────────────────┘
                                         │
                                         ▼
                  ┌─────────────────────────────────────────────────┐
                  │ Phase C: Target Serverless API Deployment       │
                  │ (TARGET / PLANNED ARCHITECTURE)                 │
                  │ - Package FastAPI with Mangum adapter           │
                  │ - Deploy AWS Lambda function                    │
                  │ - Configure Amazon API Gateway HTTP API         │
                  └──────────────────────┬──────────────────────────┘
                                         │
                                         ▼
                  ┌─────────────────────────────────────────────────┐
                  │ Phase D: Security & Observability               │
                  │ - Attach least-privilege IAM policy             │
                  │ - Configure CloudWatch structured logging       │
                  │ - Handle timeouts & fallback responses          │
                  └──────────────────────┬──────────────────────────┘
                                         │
                                         ▼
                  ┌─────────────────────────────────────────────────┐
                  │ Phase E: Frontend & Public Verification         │
                  │ - Deploy GIS frontend                           │
                  │ - Connect frontend to public API Gateway URL    │
                  │ - Verify end-to-end triage synthesis live       │
                  └─────────────────────────────────────────────────┘
```

### Phase A — AWS & Bedrock Prerequisites
1. **AWS Region & Model Verification**: Confirm the target AWS region and an available Bedrock model that satisfies the project requirements. Verify model availability and access in the actual AWS account before implementation.
2. **Environment Configuration**: Define configuration variables:
   - `AWS_REGION`: target AWS region.
   - `BEDROCK_MODEL_ID`: target Bedrock model identifier.
   - `BEDROCK_MAX_TOKENS`: output token budget (e.g., 1024).
   - `BEDROCK_TEMPERATURE`: low temperature for factual consistency (e.g., 0.1).

### Phase B — Bedrock Runtime Integration
1. **Dependency Update**: Add `boto3>=1.34.0` and `botocore` to `backend/requirements.txt`.
2. **Invoke Layer**: Implement an invocation function (e.g. `invoke_bedrock_analyst(payload: BedrockAnalystInput) -> BedrockAnalystOutput`) using `boto3.client("bedrock-runtime")`.
3. **Prompt Framing**: Feed the serialized `BedrockAnalystInput.model_dump_json()` into the system prompt along with `MANDATORY_SCIENTIFIC_GUARDRAILS`.
4. **Structured Output Validation**: Parse and validate the raw LLM JSON response using `BedrockAnalystOutput.model_validate_json(raw_response)`.
5. **Response Assembly**: Merge the validated narrative with the original `EventDetail` using `assemble_analyst_response(detail, llm_output)`.
6. **Error Handling**: Gracefully handle `ClientError`, rate-limiting (`ThrottlingException`), and invalid JSON outputs without crashing the API.

### Phase C — Target Serverless Backend Deployment (TARGET / PLANNED ARCHITECTURE)
*Note: FastAPI + Mangum + AWS Lambda + Amazon API Gateway represents the target / planned architecture for deployment, not an already-deployed architecture.*
1. **Lambda Adapter**: Add `mangum>=0.17.0` to expose FastAPI via AWS Lambda:
   ```python
   # In app/main.py or lambda_handler.py:
   from mangum import Mangum
   handler = Mangum(app, lifespan="off")
   ```
2. **Packaging**: Containerize via Docker or package as a zip archive with pre-compiled Python dependencies.
3. **Amazon API Gateway**: Deploy an HTTP API or REST API pointing to the Lambda function. Configure CORS to accept requests from the frontend origin.

### Phase D — Security & Observability
1. **Least-Privilege IAM Permissions**: Yusuf must implement least-privilege IAM permissions appropriate to the selected Bedrock model and actual deployment architecture, with resource scope restricted as tightly as supported (e.g., allowing only `bedrock:InvokeModel` scoped strictly to the chosen model ARN rather than wildcard resources).
2. **CloudWatch Logging**: Enable CloudWatch structured JSON logging. Ensure credentials, sensitive API keys, and raw authentication headers are **never** logged.
3. **Timeout Budgets**: Configure Lambda timeout (recommend 30s) and API Gateway integration timeout to allow sufficient headroom for LLM inference.

### Phase E — Public Deployment & GIS Connection
1. **Deploy Frontend**: Deploy the GIS frontend dashboard.
2. **API Endpoint Wiring**: Configure the frontend's `NEXT_PUBLIC_API_URL` to point to the live API Gateway HTTPS endpoint.
3. **CORS Verification**: Ensure preflight `OPTIONS` requests succeed and response headers include `Access-Control-Allow-Origin`.
4. **Live Verification**: Confirm that selecting an event on the dashboard displays deterministic scores and triggers the Bedrock analyst synthesis successfully.

---

## Do Not Redesign These

Yusuf must treat the following components as locked:

- [x] **Risk Dimension Weights**: Do not change the 30/25/20/10/15 breakdown.
- [x] **Risk Tier Thresholds**: Do not modify exact cutoffs (LOW: score < 25, MODERATE: 25 <= score < 50, HIGH: 50 <= score < 75, CRITICAL: score >= 75).
- [x] **Missing Data Handling**: Missing evidence must continue to contribute 0.0 points with zero weight redistribution.
- [x] **Confidence Semantics**: Do not convert confidence into an empirical fire probability or use it to multiply risk score.
- [x] **Score Immutability**: The LLM must never supply or override `risk_score`, `risk_tier`, `evidence_confidence`, or `confidence_tier`.
- [x] **Ground-Truth Prohibition**: Do not add ground-truth / evaluation labels to the Bedrock context.
- [x] **Advisory Triage Status**: Do not create a hardcoded mapping from `risk_tier` to triage status.
- [x] **Scientific Guardrails**: Do not remove any of the 11 mandatory guardrails from the schema or prompt.

---

## Files Yusuf Should Read First

| File | Purpose |
|---|---|
| [`backend/app/schemas/bedrock.py`](backend/app/schemas/bedrock.py) | Defines `BedrockAnalystInput`, `BedrockAnalystOutput`, `BedrockTriageStatus`, and mandatory guardrails. |
| [`backend/app/services/bedrock_service.py`](backend/app/services/bedrock_service.py) | Contains `build_bedrock_input()`, `assemble_analyst_response()`, and immutability logic. |
| [`backend/tests/test_bedrock_contract.py`](backend/tests/test_bedrock_contract.py) | 48 regression tests detailing expected validation, immutability, and guardrail behavior. |
| [`backend/app/api/events.py`](backend/app/api/events.py) | Existing FastAPI routes (`/api/events`, `/api/events/{event_id}`) where Bedrock synthesis will be connected. |
| [`backend/app/schemas/events.py`](backend/app/schemas/events.py) | Core domain schemas (`EventSummary`, `EventDetail`, `RiskSummary`, dimension models). |
| [`backend/app/services/event_service.py`](backend/app/services/event_service.py) | Data access layer loading the 100 curated pilot events into memory. |
| [`backend/risk_engine/scoring.py`](backend/risk_engine/scoring.py) | Authoritative scoring pipeline computing the deterministic scores and risk tiers. |
| [`backend/risk_engine/dimensions.py`](backend/risk_engine/dimensions.py) | Five-dimension formulas, normalization thresholds, and locked mathematical weights. |
| [`backend/app/main.py`](backend/app/main.py) | FastAPI application factory, CORS settings, and `/health` probe (entrypoint for Mangum/Lambda). |
| [`backend/requirements.txt`](backend/requirements.txt) | Current backend dependencies (target for adding `boto3` and `mangum`). |

---

## Verification Checklist for Yusuf

### Pre-Implementation Checks
- [ ] Backend test suite passes locally (`python -m pytest backend/tests/ -q` → 129 passed).
- [ ] Bedrock contract test suite passes (`python -m pytest backend/tests/test_bedrock_contract.py -q` → 48 passed).
- [ ] Confirm the target AWS region and an available Bedrock model that satisfies the project requirements. Verify model availability and access in the actual AWS account before implementation.

### Bedrock Integration Checks
- [ ] `boto3` client initialized with appropriate region and retry config.
- [ ] `build_bedrock_input(detail)` serialized cleanly into prompt context.
- [ ] Bedrock response parsed and validated via `BedrockAnalystOutput.model_validate_json(...)`.
- [ ] All 11 mandatory scientific guardrails verified in prompt/input.
- [ ] `assemble_analyst_response()` used to bind deterministic scores from `EventDetail`.
- [ ] Error handling active for model throttling, timeouts, or invalid JSON.

### AWS Deployment Checks (Target / Planned Architecture)
- [ ] Lambda function deployed with Mangum adapter and tested via test event.
- [ ] API Gateway routes traffic to Lambda; `/health` returns HTTP 200.
- [ ] `/api/events` and `/api/events/{event_id}` return identical responses to local tests.
- [ ] New Bedrock analysis route returns validated `BedrockAnalystResponse`.
- [ ] IAM permissions restricted to least-privilege `bedrock:InvokeModel` scoped to the selected model ARN.
- [ ] CloudWatch logs operational with zero credential leakage.
- [ ] Frontend connected to API Gateway URL with CORS functioning properly.
- [ ] Public HTTPS URL verified and live demonstration ready.

---

## Handoff Success Criteria

The AWS deployment phase will be considered complete when:
1. **Live Cloud API**: FastAPI backend runs on AWS Lambda behind Amazon API Gateway with valid HTTPS.
2. **Bedrock Invocation Active**: Real Amazon Bedrock API calls return valid narrative syntheses matching `BedrockAnalystOutput`.
3. **Scores Remain Untouched**: Live API verification confirms `risk_score` and `risk_tier` match deterministic values exactly.
4. **Frontend Connected**: GIS dashboard renders all 100 events and displays the live AI analyst synthesis on demand.
5. **Observability**: CloudWatch metrics track request counts, latencies, and Bedrock token usage.
6. **Zero Regression**: All 129 backend tests continue to pass in CI/CD against the codebase.

---

## Technology Stack

### Currently Implemented in Repository
- **Language**: Python 3.11+
- **Web Framework**: FastAPI (v0.111+)
- **Validation**: Pydantic v2 (v2.7+) & Pydantic-Settings
- **Server**: Uvicorn
- **Testing**: Pytest (v8.2+) & HTTPX (TestClient)
- **Numerical Processing**: NumPy
- **Dataset**: Curated static JSON pilot cohort (100 events with full audit trace)

### Planned AWS Cloud Services (Next Phase — Target / Planned Architecture)
- **AI / LLM Runtime**: Amazon Bedrock (selected foundational model meeting project requirements)
- **Compute**: AWS Lambda (serverless Python runtime via Mangum) [TARGET / PLANNED ARCHITECTURE]
- **API Management**: Amazon API Gateway (HTTP API) [TARGET / PLANNED ARCHITECTURE]
- **Observability**: Amazon CloudWatch (Logs, Metrics, Alarms)
- **Security & Access**: AWS IAM (least-privilege execution roles)
- **Static Hosting / Frontend**: AWS Amplify / Amazon S3 + CloudFront

---

## Development Setup

```bash
# 1. Clone repository and navigate to backend
git clone https://github.com/shivam499-pro/ThermoGuard.git
cd ThermoGuard/backend

# 2. Set up virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows PowerShell
# source .venv/bin/activate  # macOS / Linux

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Run the complete test suite
python -m pytest tests/ -v

# 5. Start local development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- API Docs: <http://localhost:8000/docs>
- Health Check: <http://localhost:8000/health>
- Pilot Events: <http://localhost:8000/api/events>
