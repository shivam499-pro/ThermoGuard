# ThermoGuard

Satellite-driven thermal anomaly detection and industrial fire classification using geospatial evidence, deterministic risk assessment, and AWS cloud infrastructure.

---

## Problem

Satellite thermal sensors detect thousands of thermal anomalies every day across the globe. Distinguishing between an industrial fire, a persistent thermal source (steel plant, oil refinery, power station), agricultural burning, a wildfire, mining-related thermal activity, or an unclassifiable uncertain anomaly is a non-trivial problem.

Simple hotspot detections report coordinates and intensity — they do not reason about the surrounding context. Analysts and emergency responders need to know:

- Is this a legitimate industrial process or an unexpected fire?
- Has this location burned before, or is this a new event?
- What land cover and infrastructure surrounds this thermal source?
- What is the real risk level, and what evidence supports that conclusion?

Without spatial and contextual evidence, thermal data alone cannot answer these questions reliably.

---

## Solution

ThermoGuard addresses this by combining multiple independent evidence sources into a single, explainable thermal event assessment:

| Evidence Source | Role |
|---|---|
| **NASA FIRMS** | Real-time thermal anomaly detections (MODIS, VIIRS) |
| **OpenStreetMap** | Infrastructure context — industrial sites, roads, facilities |
| **ESA WorldCover** | Land-cover classification — forests, cropland, urban, bare ground |
| **Sentinel-2 / Landsat** | Satellite imagery for visual and spectral confirmation |
| **Geospatial analysis** | Spatial relationships between thermal source and surroundings |
| **Temporal analysis** | Historical recurrence patterns at a location |
| **Deterministic risk engine** | Rule-based methodology that assigns risk from observable evidence |
| **Explainable results** | Every risk level is traceable to specific evidence factors |
| **AWS cloud architecture** | Scalable, serverless backend for data processing and storage |
| **Amazon Bedrock** | Analyst assistant layer for natural-language explanation of results |

> **Note:** This repository is the official hackathon implementation. Features are being built incrementally. Not all components listed above are fully implemented yet.

---

## Core Workflow

```
Satellite & Geospatial Data
         |
         v
  Evidence Processing
  (NASA FIRMS, OSM, WorldCover, Sentinel-2/Landsat)
         |
         v
  Thermal Event Analysis
  (classification, spatial context, temporal patterns)
         |
         v
  Risk Assessment
  (deterministic, evidence-based scoring)
         |
         v
    AWS Backend
  (Lambda, API Gateway, DynamoDB, S3)
         |
         v
   GIS Dashboard
  (Next.js frontend with interactive mapping)
         |
         v
  Bedrock Analyst Assistant
  (natural-language explanation of events and evidence)
```

---

## AWS Architecture (Planned)

The following AWS services are planned for the ThermoGuard backend:

| Service | Planned Use |
|---|---|
| **Amazon S3** | Storage for satellite data, processed outputs, and assets |
| **AWS Lambda** | Serverless functions for evidence processing and risk computation |
| **Amazon API Gateway** | REST API layer between frontend and backend |
| **Amazon DynamoDB** | Storage for thermal event records and assessment results |
| **AWS Amplify** | Frontend hosting and deployment |
| **Amazon Bedrock** | LLM-powered analyst assistant for event explanation |
| **Amazon CloudWatch** | Logging, monitoring, and operational observability |
| **AWS IAM** | Access control and permission management |

> AWS resources have not yet been provisioned. This section reflects the intended architecture for the hackathon implementation.

---

## Technology Stack

### Frontend
- Next.js / React
- TypeScript
- GIS mapping library *(to be finalized during implementation)*

### Backend
- Python
- FastAPI / AWS Lambda architecture *(to be finalized during implementation)*

### Data Sources
- NASA FIRMS (Fire Information for Resource Management System)
- OpenStreetMap
- ESA WorldCover
- Sentinel-2 / Landsat

### Cloud
- AWS

### AI / Analyst Layer
- Amazon Bedrock

---

## Team

| Name | Role |
|---|---|
| **Shivam Jaiswal** | Team Lead |
| **Riya Sharma** | Team Member |
| **Priyan S** | Team Member |
| **Yusuf / Mohamed Yusuff** | Team Member |

---

## Project Status

This repository is the official hackathon implementation for ThermoGuard. Development is proceeding incrementally during the hackathon. Components will be added and integrated as implementation progresses.

---

## Scientific Principles

The following principles govern the ThermoGuard risk methodology:

1. **The deterministic risk methodology is the authoritative risk calculation.** Risk levels are computed from observable, verifiable evidence factors — not from model predictions or heuristics.

2. **Amazon Bedrock is an analyst and explanation layer, not the risk engine.** Bedrock translates results into natural language; it does not calculate, override, or invent risk scores.

3. **AI must not invent observations or numerical risk scores.** If a piece of evidence is absent or unavailable, the system must represent that absence explicitly — not fill it with assumptions.

4. **Missing evidence must remain explicitly represented.** Uncertainty is a valid and required output. Gaps in data are surfaced to the analyst, not hidden.

5. **No fake, mock, or hardcoded real-world data will be used.** All thermal events, locations, and evidence values in the system must originate from real data sources or be clearly labelled as synthetic test inputs.

---

## License

License to be determined.

---

## Contributing

Contributions are made by the ThermoGuard team through this repository. Each team member works on assigned components. External contributions are not open at this stage of the hackathon.
