# SonarQube Setup Guide — AWS EC2

SonarQube analyses source code for security vulnerabilities and code-quality issues. Complisoc retrieves these findings through the SonarQube Web API and processes them through its compliance pipeline.

## 1. Prerequisites
- AWS EC2 instance running Ubuntu 22.04 LTS.
- Java 17, SSH access and an EC2 key pair.
- Required network access to port 9000.

## 2. Connect to EC2

```bash
ssh -i ssh -i "C:\Users\akash.kumar\Downloads\complisoc-key.pem" ubuntu@<EC2_PUBLIC_IP>
```
```bash
ngrok http 8000
```


## 3. Install Java and Dependencies

```bash
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk unzip wget
java -version
```

## 4. Download and Install SonarQube

```bash
cd /tmp
wget https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-10.5.1.78531.zip
sudo unzip sonarqube-10.5.1.78531.zip -d /opt
```

If already downloaded and extracted, skip this step.

## 5. Configure SonarQube User

SonarQube must not run as root.

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin sonar
sudo chown -R sonar:sonar /opt/sonarqube-10.5.1.78531
```

Skip user creation if it already exists.

## 6. Configure Linux Requirements

```bash
sudo tee /etc/sysctl.d/99-sonarqube.conf > /dev/null <<'EOF'
vm.max_map_count=524288
fs.file-max=131072
EOF

sudo sysctl --system
```

## 7. Configure Systemd Service

Create the service file:

```bash
sudo nano /etc/systemd/system/sonarqube.service
```

Add:

```ini
[Unit]
Description=SonarQube
After=network.target

[Service]
Type=forking
User=sonar
Group=sonar
LimitNOFILE=131072
LimitNPROC=8192
ExecStart=/opt/sonarqube-10.5.1.78531/bin/linux-x86-64/sonar.sh start
ExecStop=/opt/sonarqube-10.5.1.78531/bin/linux-x86-64/sonar.sh stop
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sonarqube
sudo systemctl start sonarqube
sudo systemctl status sonarqube
```

Check logs if startup fails:

```bash
sudo tail -f /opt/sonarqube-10.5.1.78531/logs/sonar.log
```

## 8. Configure AWS Security Group

EC2 → Instances → Select instance → Security Groups → Edit inbound rules.

Add:

| Setting | Value |
|---|---|
| Type | Custom TCP |
| Port | 9000 |
| Source | Your IP |
| Description | SonarQube Web UI |

Restrict access to trusted IPs. GitHub Actions and Complisoc must also be able to reach the server.

## 9. Access SonarQube

Open:

```text
http://<EC2_PUBLIC_IP>:9000
```

Default credentials:

```text
Username: admin
Password: admin
```

Change the password when prompted. Create a project and record its project key.

## 10. Generate Authentication Token

Navigate to My Account → Security → Generate Tokens.

Generate a token for the integration. The user needs:
- Browse permission to retrieve issues.
- Execute Analysis permission to upload analysis.

Store the token securely.

## 11. Configure Complisoc Backend

Add to the backend `.env` file:

```env
SONAR_HOST_URL=http://<EC2_PUBLIC_IP>:9000
SONAR_TOKEN=<YOUR_SONARQUBE_TOKEN>
```

Use `localhost` only if the backend runs on the same EC2 instance.

Verify connectivity:

```bash
curl -u "$SONAR_TOKEN:" \
  "$SONAR_HOST_URL/api/system/status"
```

The expected status is `UP`.

## 12. Configure Target Repository

Create `sonar-project.properties` at the repository root:

```properties
sonar.projectKey=your-project-key
sonar.projectName=your-project-name
sonar.sources=.
sonar.sourceEncoding=UTF-8
```

## 13. Configure GitHub Actions Secrets

Under Settings → Secrets and variables → Actions, add:

| Secret | Description |
|---|---|
| `SONAR_HOST_URL` | EC2 SonarQube URL |
| `SONAR_TOKEN` | Authentication token |
| `SONAR_PROJECT_KEY` | SonarQube project key |
| `COMPLISOC_API_URL` | Complisoc backend URL |
| `COMPLISOC_API_KEY` | Complisoc API authentication key |

## 14. Integrate GitHub Actions

Add the reusable workflow to the target repository:

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

Replace `your-org` with the actual repository owner.

## 15. Complisoc Integration Flow

1. GitHub Actions runs SonarQube analysis and uploads results to EC2.
2. The workflow polls the SonarQube Compute Engine API until analysis completes.
3. It calls Complisoc `/api/v1/scans` with `scanners: ["sonarqube"]`.
4. `SonarQubeScanner` in `backend/scanners/runners.py` retrieves issues using `GET /api/issues/search?componentKeys={project_key}`.
5. Findings are converted into Complisoc's raw-finding format and normalized by the backend.
6. Findings proceed through candidate narrowing, Gemini mapping, Groq verification and reporting.

**Architecture:** GitHub Actions uploads analysis; SonarQube stores and processes results; Complisoc retrieves, normalizes and maps findings.

## 16. Useful Commands

```bash
sudo systemctl start sonarqube
sudo systemctl stop sonarqube
sudo systemctl restart sonarqube
sudo systemctl status sonarqube
sudo journalctl -u sonarqube -f
sudo ss -ltnp | grep 9000
```

**Troubleshooting:** For startup failures, inspect `sonar.log`, `web.log` and `es.log`. Check Java, available memory, Linux kernel limits, EC2 security-group rules and token permissions.