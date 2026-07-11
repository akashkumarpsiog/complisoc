# Complisoc CI Integration for Target Repos

This file explains how to wire Complisoc security scanning into a target project's GitHub Actions workflow.

## Current setup

Your Complisoc project repo: `akashkumarpsiog/complisoc`
Your target repo: `akashkumarpsiog/WordPad`

The workflow file `target-repo-scan.yml` is a **reusable workflow** that lives in the Complisoc repo. The WordPad repo calls it via `uses:` and passes secrets.

## Setup for WordPad

### 1. Add sonar-project.properties to WordPad

The target repository must contain `sonar-project.properties` at its root:

```properties
sonar.projectKey=complisoc-sonarqube
sonar.projectName=complisoc-sonarqube
sonar.sources=.
sonar.sourceEncoding=UTF-8
```

The reusable workflow fails fast if this file is missing.

### 2. Create the workflow file in WordPad

In the **WordPad repo**, create `.github/workflows/ci.yml` with this exact content:

```yaml
name: Complisoc Security Scan

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  security-scan:
    uses: akashkumarpsiog/complisoc/.github/workflows/target-repo-scan.yml@main
    secrets:
      SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
      SONAR_PROJECT_KEY: ${{ secrets.SONAR_PROJECT_KEY }}
      COMPLISOC_API_URL: ${{ secrets.COMPLISOC_API_URL }}
      COMPLISOC_API_KEY: ${{ secrets.COMPLISOC_API_KEY }}
```

**Important:** Do NOT copy-paste the entire `target-repo-scan.yml` into WordPad. Only this thin wrapper file belongs in WordPad. The actual workflow logic stays in the Complisoc repo.

### 3. Set secrets in WordPad repo

In the **WordPad repo** on GitHub:
- **Settings → Secrets and variables → Actions → New repository secret**

Add exactly these secrets:

| Name | Value |
|------|-------|
| `COMPLISOC_API_URL` | `https://vanity-ruse-repressed.ngrok-free.dev` |
| `COMPLISOC_API_KEY` | `test-key-123` |
| `SONAR_HOST_URL` | Your SonarQube server URL |
| `SONAR_TOKEN` | Your SonarQube token |
| `SONAR_PROJECT_KEY` | Your SonarQube project key |

### 4. Configure backend environment variables

The Complisoc backend must have these environment variables set:

```bash
SONAR_HOST_URL=http://your-sonarqube-server:9000
SONAR_TOKEN=your_sonarqube_token
```

Without these, the backend cannot fetch SonarQube findings. The pipeline will still work for Trivy and Checkov.

### 5. Push to trigger

```bash
cd C:\Users\akash.kumar\OneDrive - psiog.com\Desktop\sem1\WordPad
mkdir -p .github/workflows
# copy the ci.yml content above into .github/workflows/ci.yml
git add sonar-project.properties .github/workflows/ci.yml
git commit -m "Add Complisoc security scan"
git push origin main
```

### 6. Watch it run

Go to https://github.com/akashkumarpsiog/WordPad/actions

You should see the workflow run. Click into it and watch:
- `security-scan` job runs Trivy + Checkov
- `sonarqube-analysis` job runs sonar-scanner (if Sonar secrets are set)
- `prepare-findings` job aggregates Trivy + Checkov reports
- `ingest-local-findings` job POSTs findings to Complisoc
- `ingest-sonarqube-findings` job triggers backend SonarQube scan

### 7. Verify locally

Your backend logs should show the POST requests, and you can verify:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/scan-runs" -Method GET | ConvertTo-Json
```

---

## How it works

1. On every push to `main`/`develop` (and on PRs), the workflow in WordPad triggers
2. It calls the reusable workflow in `akashkumarpsiog/complisoc`
3. The reusable workflow runs Trivy, Checkov, and optionally SonarQube:
   - **Trivy + Checkov**: Run in GitHub Actions, aggregate findings, POST to `/api/v1/scan-runs`
   - **SonarQube**: Run `sonar-scanner` analysis in GitHub Actions, then trigger backend `/api/v1/scans` with `scanners: ["sonarqube"]`
4. The backend fetches SonarQube findings via `SonarQubeScanner`, normalizes them, and runs the full compliance pipeline
5. All findings appear in the Complisoc dashboard

**Important:** SonarQube normalization happens only in the backend. The GitHub Actions workflow does not parse SonarQube output. This keeps scanner-specific logic in one place.

## Required secrets

Set these in the target repo under **Settings > Secrets and variables > Actions**:

| Secret | Required | Description |
|--------|----------|-------------|
| `COMPLISOC_API_URL` | Yes | Base URL of the Complisoc API |
| `COMPLISOC_API_KEY` | Yes | Bearer token for Complisoc API auth |
| `SONAR_HOST_URL` | No | SonarQube/SonarCloud URL |
| `SONAR_TOKEN` | No | SonarQube/SonarCloud token |
| `SONAR_PROJECT_KEY` | No | SonarQube project key for analysis |

## Backend requirements for SonarQube

The Complisoc backend must have these environment variables set:

| Variable | Required | Description |
|----------|----------|-------------|
| `SONAR_HOST_URL` | Yes (for SonarQube) | SonarQube server URL |
| `SONAR_TOKEN` | Yes (for SonarQube) | SonarQube token with Browse permission |

Without these, the `SonarQubeScanner` will be unavailable.

## Notes

- **No Docker needed** — everything runs in GitHub-hosted Ubuntu runners
- **Keep backend running** while the workflow executes, otherwise the ngrok tunnel will fail
- **ngrok URL stability** — free ngrok URLs change on restart. If you restart ngrok later, update the `COMPLISOC_API_URL` secret in GitHub
- **SonarQube job runs in parallel** with Trivy/Checkov when configured
- **Partial results are acceptable** — if SonarQube secrets are not set, the pipeline works with Trivy + Checkov only
