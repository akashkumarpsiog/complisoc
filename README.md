# Complisoc

AI-powered automated security compliance testing platform.

## Architecture

```
Scanner Layer → Normalization Layer → Storage Layer → Compliance Intelligence Layer → Reporting Layer → Dashboard Layer
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for full details.

## Validation & recent additions

The platform ships with deterministic, secret-free test suites that prove
the compliance pipeline end-to-end:

- **15-control gold-standard benchmark** — `tests/benchmark/gold_standard.json`
  (15 canonical mappings) validated by `tests/benchmark/validate_mappings.py`
  (reports precision/recall; currently **1.000 / 1.000**).
- **LangChain (LCEL) pipeline** — the compliance orchestration lives in
  `backend/compliance/langchain_pipeline.py`, a single LangChain / LCEL
  chain (`ingest → Gemini mapping → Groq gap analysis → report`). There is
  one implementation; `process_scan_run` is a thin alias to it. The
  `tests/langchain/test_langchain_equivalent.py` suite guards against
  behavioural regression.
- **E2E pipeline test** — `tests/e2e/test_real_pipeline.py` writes a
  temporary Terraform / Kubernetes file with a known bad pattern, invokes
  the real `/api/v1/scans` endpoint, and asserts findings, mappings and
  report artifacts are created (run against both `scan_targets/` targets).
- **Data-integrity validation** — `tests/validation/test_integrity.py`
  verifies the `ScanRun → RawFinding → NormalizedFinding →
  ControlMapping → VerificationRecord` chain is intact with no orphaned
  records, and that audit-bundle checksums match the raw findings.
- **Dashboard** — four views (`control-coverage`, `severity-distribution`,
  `gap-summary`, `remediation-backlog`) are exposed by the API and
  rendered by the React frontend.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for deployment and the
gap-by-gap status used in the Moodle submission.

## Quick Start

### Backend (FastAPI + SQLAlchemy + SQLite)

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If using CMD:

```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

2. Install dependencies:

```powershell
pip install --upgrade pip
pip install sqlalchemy alembic pytest fastapi uvicorn google-genai groq python-dotenv
```

3. Configure AI provider keys:

Copy `.env.example` to `.env` and set `GEMINI_API_KEY` (Gemini 2.5 Flash, primary mapping) and `GROQ_API_KEY` (Groq Llama 3.3 70B, verification). Without these the pipeline falls back to deterministic behavior and logs a warning.

```powershell
cp .env.example .env
```

3. Configure the database (optional):

By default the app uses SQLite at `complisoc.db` in the repository root. To override:

```powershell
$env:DATABASE_URL = "sqlite:///C:/path/to/complisoc.db"
```

4. Apply migrations:

```powershell
alembic upgrade head
```

5. Run tests:

```powershell
python -m pytest -v
```

6. Start the API server:

```powershell
uvicorn complisoc.backend.api.main:app --reload --port 8000
```

Then open `http://127.0.0.1:8000/api/v1/health`.

### Frontend (React + TailwindCSS + Vite)

1. Install dependencies:

```powershell
npm install --prefix complisoc/frontend
```

2. Start development server:

```powershell
npm run dev --prefix complisoc/frontend
```

Then open `http://127.0.0.1:5173`.

3. Build for production:

```powershell
npm run build --prefix complisoc/frontend
```

## Running Both Together

In two terminals:

**Terminal 1 (Backend):**
```powershell
Root repo: C:\Users\akash.kumar\OneDrive - psiog.com\Desktop\sem1
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
.\complisoc\.venv\Scripts\python.exe -m uvicorn complisoc.backend.api.main:app --reload --port 8000
```
## ngrok set up
ngrok config add-authtoken YOUR_AUTHTOKEN
ngrok config check
ngrok http 8000
**Terminal 2 (Frontend):**
```powershell
npm install --prefix complisoc/frontend
npm run dev --prefix complisoc/frontend
```

Note: The frontend expects the backend at `http://127.0.0.1:8000/api/v1`. To use a different backend URL, set `VITE_API_BASE_URL` in the frontend `.env` file.

## API Endpoints

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/readiness` | Dependency readiness |
| `GET` | `/api/v1/scanners` | List available scanners (trivy, checkov, sonarqube, defender) |
| `POST` | `/api/v1/scans` | Run live scanners against a target and ingest results |
| `POST` | `/api/v1/scan-runs` | Create scan run |
| `GET` | `/api/v1/scan-runs` | List scan runs |
| `GET` | `/api/v1/scan-runs/{id}` | Get scan run |
| `GET` | `/api/v1/scan-runs/{id}/summary` | Scan summary |
| `GET` | `/api/v1/findings` | List findings |
| `GET` | `/api/v1/mappings` | List control mappings |
| `GET` | `/api/v1/controls` | List controls |
| `GET` | `/api/v1/reports` | List reports |
| `POST` | `/api/v1/reports/engineering` | Generate engineering report |
| `POST` | `/api/v1/reports/leadership` | Generate leadership report |
| `GET` | `/api/v1/audit-bundles` | List audit bundles |
| `POST` | `/api/v1/audit-bundles` | Generate audit bundle |
| `GET` | `/api/v1/dashboard/control-coverage` | Coverage metrics |
| `GET` | `/api/v1/dashboard/severity-distribution` | Severity metrics |
| `GET` | `/api/v1/dashboard/gap-summary` | Gap analysis |
| `GET` | `/api/v1/dashboard/remediation-backlog` | Remediation queue |
| `GET` | `/api/v1/dashboard/trends` | Historical trends |
| `GET` | `/api/v1/review-queue` | List review items |
| `POST` | `/api/v1/review-queue/{id}/approve` | Approve mapping |
| `POST` | `/api/v1/review-queue/{id}/reject` | Reject mapping |

See [API.md](API.md) for full specification.

## Compliance Workflow

```
NormalizedFinding → Candidate Narrowing → Gemini Mapping → Validation → Groq Verification → Confidence Calculation → Published OR Manual Review
```

See [DATA_MODEL.md](DATA_MODEL.md) for entity relationships and lineage.

## Confidence Threshold

- Publication threshold: `0.70`
- Formula: `(Gemini Confidence × 0.6) + (Groq Agreement × 0.4)`
- Below threshold: routed to manual review

## Features

- **Continuous scanning**: Execute Trivy, Checkov, SonarQube, Microsoft Defender
- **Finding normalization**: Canonical schema with severity standardization
- **Compliance mapping**: Maps findings to SOC2 TSC 2022 and ISO27001:2022 Annex A
- **AI verification**: Independent verification with Groq Llama 3.3 70B
- **Governance reporting**: Engineering and Leadership reports
- **Audit evidence**: Exportable audit bundles with full lineage

## Notes

- Tests validate the complete workflow including lineage tracing
- Migrations are in `complisoc/backend/migrations/`
- Use `.env` for secrets, never commit credentials
- Dashboard consumes processed data only, no compliance calculations