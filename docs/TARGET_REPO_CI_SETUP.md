# Complisoc CI Integration for Target Repos

This file explains how to wire Complisoc security scanning into a target project's GitHub Actions workflow.

## Current setup

Your Complisoc project repo: `akashkumarpsiog/complisoc`
Your target repo: `akashkumarpsiog/WordPad`

The workflow file `target-repo-scan.yml` is a **reusable workflow** that lives in the Complisoc repo. The WordPad repo calls it via `uses:` and passes secrets.

## Setup for WordPad

### 1. Create the workflow file in WordPad

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
      COMPLISOC_API_URL: ${{ secrets.COMPLISOC_API_URL }}
      COMPLISOC_API_KEY: ${{ secrets.COMPLISOC_API_KEY }}
```

**Important:** Do NOT copy-paste the entire `target-repo-scan.yml` into WordPad. Only this thin wrapper file belongs in WordPad. The actual workflow logic stays in the Complisoc repo.

### 2. Set secrets in WordPad repo

In the **WordPad repo** on GitHub:
- **Settings → Secrets and variables → Actions → New repository secret**

Add exactly these 2 secrets:

| Name | Value |
|------|-------|
| `COMPLISOC_API_URL` | `https://vanity-ruse-repressed.ngrok-free.dev` |
| `COMPLISOC_API_KEY` | `test-key-123` |

Leave `SONAR_HOST_URL` and `SONAR_TOKEN` empty for now.

### 3. Push to trigger

```bash
cd C:\Users\akash.kumar\OneDrive - psiog.com\Desktop\sem1\WordPad
mkdir -p .github/workflows
# copy the ci.yml content above into .github/workflows/ci.yml
git add .github/workflows/ci.yml
git commit -m "Add Complisoc security scan"
git push origin main
```

### 4. Watch it run

Go to https://github.com/akashkumarpsiog/WordPad/actions

You should see the workflow run. Click into it and watch:
- `security-scan` job runs Trivy + Checkov
- `prepare-findings` job aggregates the reports
- `ingest-to-complisoc` job POSTs findings to your ngrok URL

### 5. Verify locally

Your backend logs should show the POST request, and you can verify:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/scan-runs" -Method GET | ConvertTo-Json
```

---

## How it works

1. On every push to `main`/`develop` (and on PRs), the workflow in WordPad triggers
2. It calls the reusable workflow in `akashkumarpsiog/complisoc`
3. The reusable workflow runs Trivy and Checkov locally in GitHub Actions
4. It aggregates the scanner output into Complisoc's raw-finding format
5. It POSTs the aggregated findings directly to Complisoc's `/api/v1/scan-runs` endpoint

**Important:** This workflow does **not** call `/api/v1/scans`. It calls `/api/v1/scan-runs` with pre-computed findings, so Complisoc does not re-run the scanners. The scanning happens in GitHub Actions; Complisoc only ingests and processes the results.

## Required secrets

Set these in the target repo under **Settings > Secrets and variables > Actions**:

| Secret | Required | Description |
|--------|----------|-------------|
| `COMPLISOC_API_URL` | Yes | Base URL of the Complisoc API |
| `COMPLISOC_API_KEY` | Yes | Bearer token for Complisoc API auth |
| `SONAR_HOST_URL` | No | SonarQube/SonarCloud URL |
| `SONAR_TOKEN` | No | SonarQube/SonarCloud token |

## Notes

- **No SonarQube needed yet** — the SonarQube step only runs if you add those secrets later
- **No Docker needed** — everything runs in GitHub-hosted Ubuntu runners
- **Keep backend running** while the workflow executes, otherwise the ngrok tunnel will fail
- **ngrok URL stability** — free ngrok URLs change on restart. If you restart ngrok later, update the `COMPLISOC_API_URL` secret in GitHub
