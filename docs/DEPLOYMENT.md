# Complisoc — Deployment Guide

Complisoc transforms security scanner output (Trivy, Checkov, SonarQube,
Microsoft Defender) into compliance intelligence: findings → normalization →
control mapping (Gemini) → gap analysis (Groq) → structured, auditable
reports.

## 1. Prerequisites

- Python **3.12+** (backend)
- Node.js **20+** (frontend)
- One or more scanners installed on the scan host:
  - **Trivy** — `apt-get install trivy` / `brew install trivy`
  - **Checkov** — `pip install checkov`
  - **SonarQube** — cloud service (set `SONAR_HOST_URL`, `SONAR_TOKEN`)
  - **Defender** — Azure subscription credentials (optional)
- API keys (only required for live AI mapping):
  - `GEMINI_API_KEY` (Gemini 2.5 Flash)
  - `GROQ_API_KEY` (Groq Llama 3.3 70B)

> Without the AI keys the pipeline still runs end-to-end; mappings are routed
> to **manual review** instead of being published.

## 2. Backend

```bash
cd complisoc
python -m venv .venv && .venv\Scripts\activate   # Windows
#   python -m venv .venv && source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt

# Configure secrets (copy and edit)
cp .env.example .env
#   GEMINI_API_KEY=...
#   GROQ_API_KEY=...

# Database is SQLite by default (complisoc.db); no external DB needed.

# The package is imported as `complisoc.backend...`, so the directory that
# *contains* `complisoc` must be on PYTHONPATH. From inside the repo
# root that means pointing at the parent directory.
uvicorn complisoc.backend.api.main:app --host 127.0.0.1 --port 8000
```

> Windows (run from inside `complisoc`):
> ```powershell
> $env:PYTHONPATH = (Resolve-Path ..).Path
> uvicorn complisoc.backend.api.main:app --host 127.0.0.1 --port 8000
> ```
> Linux/macOS (run from inside `complisoc`):
> ```bash
> PYTHONPATH="$(pwd)/.." uvicorn complisoc.backend.api.main:app --host 127.0.0.1 --port 8000
> ```

Health / readiness:

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/readiness
```

Trigger a scan (the API runs the scanners itself):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"target":"./scan_targets/terraform","scanners":["trivy","checkov"]}'
```

## 3. Frontend (dashboard)

```bash
cd complisoc/frontend
npm ci
npm run dev          # http://127.0.0.1:5173
# build static bundle for production:
npm run build && npm run preview
```

The dashboard consumes the four backend views:

- `/api/v1/dashboard/control-coverage`
- `/api/v1/dashboard/severity-distribution`
- `/api/v1/dashboard/gap-summary`
- `/api/v1/dashboard/remediation-backlog`

## 4. Running the test suites

```bash
# Backend (Python) + JUnit XML for CI / Moodle
python -m pytest tests --junitxml=docs/moodle_evidence/test_run_logs/pytest-junit.xml -q

# 15-control gold-standard benchmark
python tests/benchmark/validate_mappings.py

# Frontend (vitest)
cd frontend && npm test
```

## 5. CI (GitHub Actions)

`.github/workflows/ci.yml` runs on push/PR to `main`/`develop`:

1. **python-tests** — installs `requirements.txt`, runs `pytest` with JUnit XML.
2. **frontend-tests** — `npm ci` + `npm test`.
3. **scanner-smoke** (best-effort) — installs Trivy + Checkov and runs them
   against `scan_targets/` to confirm scanners are operational.

The workflow installs `langchain-core`, which is a required dependency: the
compliance pipeline is orchestrated by a LangChain / LCEL chain, so the
equivalence tests run automatically.

## 6. Configuration reference (`backend/core/config.py`)

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | _(none)_ | Enables AI control mapping. |
| `GROQ_API_KEY` | _(none)_ | Enables AI gap-analysis verification. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Mapping model. |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Verification model. |
| `SONAR_HOST_URL` / `SONAR_TOKEN` | _(none)_ | SonarQube scanner. |
| `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` / `AZURE_SUBSCRIPTION_ID` | _(none)_ | Defender scanner. |
