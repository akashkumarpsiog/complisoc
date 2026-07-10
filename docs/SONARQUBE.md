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

The `SonarQubeScanner` runner calls:

```
GET {SONAR_HOST_URL}/api/issues/search?componentKeys={project_key}&s=SEVERITY&ps=100
```

It converts SonarQube issues into the standard raw-finding format:
- `rule` → `finding_type`
- `message` → `title` and `description`
- `severity` → normalized severity
- `component` → `resource_identifier`

## CI Integration

For target projects using GitHub Actions, add a reusable workflow step:

```yaml
jobs:
  sonarqube:
    if: ${{ secrets.SONAR_HOST_URL != '' && secrets.SONAR_TOKEN != '' }}
    uses: your-org/complisoc/.github/workflows/target-repo-scan.yml@main
    secrets:
      SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
      COMPLISOC_API_URL: ${{ secrets.COMPLISOC_API_URL }}
      COMPLISOC_API_KEY: ${{ secrets.COMPLISOC_API_KEY }}
```

## Troubleshooting

- **"SonarQube is not available"**: Ensure `SONAR_HOST_URL` and `SONAR_TOKEN` are set. The scanner checks both at startup.
- **0 findings returned**: Ensure the SonarQube project has issues and the token has `Browse` permission.
- **Connection errors**: Verify the SonarQube URL is reachable from the backend process. For EC2, check the security group allows inbound 9000.
