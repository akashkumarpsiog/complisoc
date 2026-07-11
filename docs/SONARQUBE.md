# SonarQube Setup Guide

SonarQube is used as a cloud-style scanner in Complisoc. It reads security issues from a configured SonarQube project via the SonarQube Web API.

## Prerequisites

- A running SonarQube instance (AWS EC2 or SonarCloud)
- A SonarQube project with code analysis already completed
- SonarQube user token with `Execution` + `Browse` permissions

## Environment Variables

Set these in the backend environment before starting the API:

```bash
SONAR_HOST_URL=http://localhost:9000
SONAR_TOKEN=squ_1234abcd...
```

If using SonarCloud, the URL pattern is:

```bash
SONAR_HOST_URL=https://sonarcloud.io
SONAR_TOKEN=your_sonarcloud_token
```

## Option A: SonarQube on AWS EC2 (no Docker required)

1. Launch an EC2 instance (Ubuntu 22.04 LTS recommended, t3.large or better)
2. Install Java 17:

```bash
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk
```

3. Download and start SonarQube:

```bash
wget https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-10.5.1.78531.zip
sudo unzip sonarqube-10.5.1.78531.zip -d /opt
sudo /opt/sonarqube-10.5.1.78531/bin/linux-x86-64/sonar.sh start
```

4. Open port 9000 in the EC2 security group
5. Complete setup at `http://<EC2_PUBLIC_IP>:9000`
6. Generate an auth token from your user profile
7. Set `SONAR_HOST_URL=http://<EC2_PUBLIC_IP>:9000` in Complisoc backend env

## Option B: SonarCloud (SaaS, no infra required)

1. Sign up at https://sonarcloud.io
2. Create an organization and project
3. Generate a token from `My Account > Security > Generate Tokens`
4. Set environment variables:

```bash
SONAR_HOST_URL=https://sonarcloud.io
SONAR_TOKEN=your_token
```

5. Run analysis against your target project:

```bash
sonar-scanner \
  -Dsonar.projectKey=my-project \
  -Dsonar.organization=my-org \
  -Dsonar.host.url=https://sonarcloud.io \
  -Dsonar.token=YOUR_TOKEN
```

## How Complisoc Uses SonarQube

The reusable GitHub Actions workflow (`target-repo-scan.yml`) runs `sonar-scanner` to upload analysis to your SonarQube server. After analysis is processed, it calls the Complisoc backend `/api/v1/scans` endpoint with `scanners: ["sonarqube"]`.

The backend's `SonarQubeScanner` runner (`backend/scanners/runners.py`) then:
1. Queries `GET {SONAR_HOST_URL}/api/issues/search?componentKeys={project_key}`
2. Converts SonarQube issues into the standard raw-finding format:
   - `rule` → `finding_type`
   - `message` → `title` and `description`
   - `severity` → normalized severity
   - `component` → `resource_identifier`
3. Normalizes findings through the same pipeline as Trivy and Checkov
4. Runs candidate narrowing, Gemini mapping, Groq verification, and report generation

**Normalization happens only in the backend.** The GitHub Actions workflow does not parse or normalize SonarQube output. This keeps scanner-specific logic in one place.

## Prerequisites

- A running SonarQube instance (AWS EC2 or SonarCloud)
- A SonarQube project with code analysis already completed
- SonarQube user token with `Execution` + `Browse` permissions
- `sonar-project.properties` committed at the root of the target repository

## Environment Variables

### Backend (required for SonarQube ingestion)

Set these in the Complisoc backend environment before starting the API:

```bash
SONAR_HOST_URL=http://localhost:9000
SONAR_TOKEN=squ_1234abcd...
```

Without these, the backend `SonarQubeScanner` will be unavailable and the pipeline will route SonarQube findings to manual review.

### GitHub Secrets (target repository)

Set these in the target repository under **Settings > Secrets and variables > Actions**:

| Secret | Required | Description |
|--------|----------|-------------|
| `SONAR_HOST_URL` | Yes | SonarQube server URL |
| `SONAR_TOKEN` | Yes | SonarQube token with `Execution` + `Browse` |
| `SONAR_PROJECT_KEY` | Yes | SonarQube project key |
| `COMPLISOC_API_URL` | Yes | Base URL of the Complisoc API |
| `COMPLISOC_API_KEY` | Yes | Bearer token for Complisoc API auth |

## Option A: SonarQube on AWS EC2 (no Docker required)

1. Launch an EC2 instance (Ubuntu 22.04 LTS recommended, t3.large or better)
2. Install Java 17:

```bash
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk
```

3. Download and start SonarQube:

```bash
wget https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-10.5.1.78531.zip
sudo unzip sonarqube-10.5.1.78531.zip -d /opt
sudo /opt/sonarqube-10.5.1.78531/bin/linux-x86-64/sonar.sh start
```

4. Open port 9000 in the EC2 security group
5. Complete setup at `http://<EC2_PUBLIC_IP>:9000`
6. Generate an auth token from your user profile
7. Create a SonarQube project and note the project key

## Option B: SonarCloud (SaaS, no infra required)

1. Sign up at https://sonarcloud.io
2. Create an organization and project
3. Generate a token from `My Account > Security > Generate Tokens`
4. Set environment variables:

```bash
SONAR_HOST_URL=https://sonarcloud.io
SONAR_TOKEN=your_token
```

## Target Repository Configuration

The target repository must contain `sonar-project.properties` at its root:

```properties
sonar.projectKey=your-project-key
sonar.projectName=your-project-name
sonar.sources=.
sonar.sourceEncoding=UTF-8
```

The reusable workflow verifies this file exists and fails fast if missing.

## CI Integration

For target projects using GitHub Actions, add a reusable workflow step:

```yaml
jobs:
  sonarqube:
    uses: your-org/complisoc/.github/workflows/target-repo-scan.yml@main
    secrets:
      SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
      SONAR_PROJECT_KEY: ${{ secrets.SONAR_PROJECT_KEY }}
      COMPLISOC_API_URL: ${{ secrets.COMPLISOC_API_URL }}
      COMPLISOC_API_KEY: ${{ secrets.COMPLISOC_API_KEY }}
```

The reusable workflow:
1. Runs `sonar-scanner` analysis and uploads to SonarQube
2. Polls the SonarQube CE API until analysis is processed
3. Calls Complisoc backend `/api/v1/scans` with `scanners: ["sonarqube"]`
4. Backend fetches findings via `SonarQubeScanner`, normalizes them, and runs the compliance pipeline

## Troubleshooting

- **"sonar-project.properties not found"**: Ensure the file exists at the target repo root. The workflow fails fast if missing.
- **"SonarQube analysis did not complete within timeout"**: The workflow polls for up to 120 seconds. Check SonarQube server health and logs.
- **"SonarQube is not available"**: Ensure `SONAR_HOST_URL` and `SONAR_TOKEN` are set in the backend environment.
- **0 findings returned**: Ensure the SonarQube project has issues and the token has `Browse` permission.
- **Connection errors**: Verify the SonarQube URL is reachable from the backend process. For EC2, check the security group allows inbound 9000.
