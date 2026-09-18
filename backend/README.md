# ThermoGuard — Backend

Python FastAPI backend for the ThermoGuard thermal anomaly detection system.

> **Scope note:** This README covers the backend only.
> See the root [`README.md`](../README.md) for the full system overview.

---

## Structure

```
backend/
├── app/
│   ├── __init__.py          # package marker
│   ├── main.py              # FastAPI application factory + entry point
│   ├── config.py            # pydantic-settings configuration
│   └── schemas/
│       └── __init__.py      # shared Pydantic response schemas
├── tests/
│   ├── __init__.py
│   └── test_main.py         # foundation tests (health, error handlers)
└── requirements.txt
```

---

## Quick Start

```bash
# 1. Create and activate a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at <http://localhost:8000>.

| Endpoint         | Description            |
|------------------|------------------------|
| `GET /health`    | Liveness probe (→ 200) |
| `GET /docs`      | Swagger UI             |
| `GET /redoc`     | ReDoc UI               |

---

## Running Tests

```bash
# From the backend/ directory
pytest tests/ -v
```

---

## Configuration

Settings are loaded from environment variables (or an optional `.env` file,
which is excluded from version control).

| Variable       | Default        | Description                    |
|----------------|----------------|--------------------------------|
| `APP_NAME`     | `ThermoGuard`  | Application name               |
| `APP_VERSION`  | `0.1.0`        | Version string                 |
| `DEBUG`        | `false`        | Enable debug mode              |
| `API_PREFIX`   | `/api`         | Prefix for domain API routes   |
| `CORS_ORIGINS` | `["*"]`        | Allowed CORS origins           |
| `LOG_LEVEL`    | `INFO`         | Python logging level           |

---

## Development Notes

- **No AWS code** in this commit — AWS integration is Yusuf's infrastructure scope.
- **No Bedrock** — Bedrock integration is Priyan's scope.
- **No frontend** — frontend is Riya's scope.
- Domain-specific routers (risk engine, analysis API) will be added in later
  commits and attached via `app.include_router(...)` without modifying the
  core application factory.
