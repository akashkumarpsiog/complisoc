"""Live scanner integration.

Each scanner runner invokes an external security scanner (when installed or
configured) and normalizes its output into the raw-finding shape consumed by
``complisoc.backend.scanners.ingestion.ingest_findings``.

Runners degrade gracefully: if a scanner binary is missing or misconfigured, the
runner returns an error string instead of raising. The scan pipeline records that
as a failed ``ScannerExecution`` so the run stays auditable.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

try:
    import requests as _requests

    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


def _fid(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.md5(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]
    return f"{prefix}:{digest}"


def _venv_executable_path(name: str) -> str | None:
    if sys.prefix == sys.base_prefix:
        return None
    scripts = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    if os.name == "nt":
        candidates = [scripts / f"{name}.exe", scripts / f"{name}.cmd", scripts / name]
    else:
        candidates = [scripts / name]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _python_executable() -> str | None:
    return sys.executable if sys.prefix != sys.base_prefix else None


def _module_available(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


class BaseScanner(ABC):
    name: str
    kind = "local"
    label: str | None = None
    description: str | None = None
    required_inputs: list[str] = []

    def is_available(self) -> bool:
        return bool(shutil.which(self.name)) or bool(_venv_executable_path(self.name))

    def missing_config(self) -> list[str]:
        return [] if self.is_available() else [f"{self.name} executable"]

    def metadata(self) -> dict[str, Any]:
        missing = self.missing_config()
        return {
            "name": self.name,
            "available": not missing,
            "kind": self.kind,
            "label": self.label or self.name,
            "description": self.description or "",
            "required_inputs": self.required_inputs,
            "missing_config": missing,
        }

    def _emit(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "scanner_name": self.name,
            "scanner_finding_id": _fid(self.name, raw),
            "raw_json": raw,
        }

    @abstractmethod
    def run(self, target: str, timeout: int = 300) -> tuple[list[dict[str, Any]], str | None]:
        ...


class TrivyScanner(BaseScanner):
    name = "trivy"
    label = "Trivy"
    description = "Scans local repositories, filesystem paths, containers, and IaC for vulnerabilities and misconfigurations."
    required_inputs = ["Target path, for example . or C:/repo"]

    def run(self, target: str, timeout: int = 300) -> tuple[list[dict[str, Any]], str | None]:
        try:
            proc = subprocess.run(
                [
                    "trivy",
                    "fs",
                    "--scanners",
                    "misconfig,vuln",
                    "--severity",
                    "LOW,MEDIUM,HIGH,CRITICAL",
                    "--format",
                    "json",
                    target,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            return [], f"trivy execution failed: {exc}"

        if proc.returncode != 0 and not proc.stdout.strip():
            return [], f"trivy exited with {proc.returncode}: {proc.stderr[:500]}"

        try:
            report = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as exc:
            return [], f"trivy produced invalid JSON: {exc}"

        findings: list[dict[str, Any]] = []
        for result in report.get("Results", []) or []:
            target_path = result.get("Target", target)
            for vuln in result.get("Vulnerabilities", []) or []:
                raw = {
                    "finding_type": vuln.get("VulnerabilityID") or "vulnerability",
                    "resource_type": result.get("Type", "package"),
                    "resource_identifier": f"{target_path}::{vuln.get('PkgName', vuln.get('Resource', ''))}",
                    "severity": vuln.get("Severity", "medium"),
                    "title": vuln.get("Title") or vuln.get("VulnerabilityID", "Vulnerability"),
                    "description": vuln.get("Description"),
                }
                findings.append(self._emit(raw))
            for misc in result.get("Misconfigurations", []) or []:
                cause = misc.get("CauseMetadata", {}) or {}
                raw = {
                    "finding_type": misc.get("ID", "misconfiguration"),
                    "resource_type": misc.get("Type", "iac"),
                    "resource_identifier": f"{cause.get('Filepath', target_path)}::{cause.get('Resource', misc.get('Resource', ''))}",
                    "severity": misc.get("Severity", "medium"),
                    "title": misc.get("Title") or misc.get("ID", "Misconfiguration"),
                    "description": misc.get("Message"),
                }
                findings.append(self._emit(raw))
        return findings, None


class CheckovScanner(BaseScanner):
    name = "checkov"
    label = "Checkov"
    description = "Scans local IaC directories for cloud configuration issues. Supports Terraform, Kubernetes, CloudFormation, and more."
    required_inputs = ["Directory path containing Terraform, Kubernetes, CloudFormation, or other IaC files"]

    def is_available(self) -> bool:
        if super().is_available():
            return True
        if _module_available("checkov"):
            return True
        return False

    def missing_config(self) -> list[str]:
        if self.is_available():
            return []
        return ["checkov executable (pip install checkov) or ensure it is on PATH"]

    def _command(self, target: str) -> list[str]:
        # Checkov scans a directory with `-d` but a single file with `-f`.
        flag = "-f" if os.path.isfile(target) else "-d"
        venv_python = _python_executable()
        scripts_dir = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
        script = None
        if venv_python:
            for candidate in [scripts_dir / self.name, scripts_dir / f"{self.name}.py"]:
                if candidate.exists():
                    script = candidate
                    break
        if venv_python and script:
            return [venv_python, str(script), flag, target, "--output", "json", "--compact"]
        exe = shutil.which(self.name)
        if exe:
            return [exe, flag, target, "--output", "json", "--compact"]
        return ["checkov", flag, target, "--output", "json", "--compact"]

    def run(self, target: str, timeout: int = 300) -> tuple[list[dict[str, Any]], str | None]:
        try:
            proc = subprocess.run(
                self._command(target),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            return [], f"checkov execution failed: {exc}"

        if proc.returncode not in (0, 1) and not proc.stdout.strip():
            return [], f"checkov exited with {proc.returncode}: {proc.stderr[:500]}"

        try:
            report = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as exc:
            return [], f"checkov produced invalid JSON: {exc}"

        findings: list[dict[str, Any]] = []
        results = report.get("results", {}) or {}
        for check in results.get("failed_checks", []) or []:
            raw = {
                "finding_type": check.get("check_id", "iac"),
                "resource_type": check.get("resource_type", "iac"),
                "resource_identifier": f"{check.get('file_path', target)}::{check.get('resource', '')}",
                "severity": check.get("severity", "medium"),
                "title": check.get("check_name") or check.get("check_id", "Checkov finding"),
                "description": check.get("description"),
            }
            findings.append(self._emit(raw))
        return findings, None


class SonarQubeScanner(BaseScanner):
    name = "sonarqube"
    kind = "cloud"
    label = "SonarQube"
    description = "Reads security issues from a configured SonarQube project."
    required_inputs = ["Project key in Target", "SONAR_HOST_URL", "SONAR_TOKEN"]

    def is_available(self) -> bool:
        return all(os.environ.get(env) for env in ["SONAR_HOST_URL", "SONAR_TOKEN"]) and _HAS_REQUESTS

    def missing_config(self) -> list[str]:
        missing = [env for env in ["SONAR_HOST_URL", "SONAR_TOKEN"] if not os.environ.get(env)]
        if not _HAS_REQUESTS:
            missing.append("requests library")
        return missing

    def run(self, target: str, timeout: int = 300) -> tuple[list[dict[str, Any]], str | None]:
        missing = [env for env in ["SONAR_HOST_URL", "SONAR_TOKEN"] if not os.environ.get(env)]
        if missing:
            return [], f"sonarqube requires {', '.join(missing)}"
        if not _HAS_REQUESTS:
            return [], "sonarqube requires the requests library; install it to enable."

        host = os.environ["SONAR_HOST_URL"].rstrip("/")
        token = os.environ["SONAR_TOKEN"]
        auth = (token, "")
        session = _requests.Session()
        session.auth = auth
        session.headers["Accept"] = "application/json"

        findings: list[dict[str, Any]] = []
        page = 1
        while True:
            try:
                resp = session.get(
                    f"{host}/api/issues/search",
                    params={
                        "componentKeys": target,
                        "types": "VULNERABILITY,SECURITY_HOTSPOT",
                        "ps": 100,
                        "p": page,
                    },
                    timeout=timeout,
                )
            except _requests.RequestException as exc:
                return findings, f"sonarqube request failed: {exc}"
            if resp.status_code != 200:
                return findings, f"sonarqube returned {resp.status_code}: {resp.text[:500]}"

            body = resp.json()
            issues = body.get("issues") or []
            if not issues:
                break

            for issue in issues:
                raw = {
                    "finding_type": issue.get("rule", "sonarqube-issue"),
                    "resource_type": issue.get("type", "issue"),
                    "resource_identifier": issue.get("component", target),
                    "severity": (issue.get("severity") or "medium").lower(),
                    "title": issue.get("message") or issue.get("rule", "SonarQube issue"),
                    "description": issue.get("message"),
                }
                findings.append(self._emit(raw))

            if page * 100 >= (body.get("total") or 0):
                break
            page += 1

        return findings, None


class DefenderScanner(BaseScanner):
    name = "defender"
    kind = "cloud"
    label = "Azure Defender"
    description = "Reads Microsoft Defender for Cloud alerts from the configured Azure subscription."
    required_inputs = [
        "Azure subscription/resource scope in Target",
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "AZURE_SUBSCRIPTION_ID",
    ]

    def is_available(self) -> bool:
        return all(os.environ.get(env) for env in ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID"]) and _HAS_REQUESTS

    def missing_config(self) -> list[str]:
        missing = [env for env in ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID"] if not os.environ.get(env)]
        if not _HAS_REQUESTS:
            missing.append("requests library")
        return missing

    def run(self, target: str, timeout: int = 300) -> tuple[list[dict[str, Any]], str | None]:
        missing = [env for env in ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID"] if not os.environ.get(env)]
        if missing:
            return [], f"defender requires {', '.join(missing)}"
        if not _HAS_REQUESTS:
            return [], "defender requires the requests library; install it to enable."

        tenant = os.environ["AZURE_TENANT_ID"]
        client_id = os.environ["AZURE_CLIENT_ID"]
        client_secret = os.environ["AZURE_CLIENT_SECRET"]
        subscription = os.environ["AZURE_SUBSCRIPTION_ID"]
        token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        token_data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://management.azure.com/.default",
        }

        try:
            token_resp = _requests.post(token_url, data=token_data, timeout=timeout)
        except _requests.RequestException as exc:
            return [], f"defender token request failed: {exc}"
        if token_resp.status_code != 200:
            return [], f"defender token endpoint returned {token_resp.status_code}: {token_resp.text[:500]}"

        access_token = token_resp.json().get("access_token")
        if not access_token:
            return [], "defender token response missing access_token"

        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        findings: list[dict[str, Any]] = []
        session = _requests.Session()
        session.headers.update(headers)
        url = f"https://management.azure.com/subscriptions/{subscription}/providers/Microsoft.Security/alerts?api-version=2020-01-01-preview"

        try:
            resp = session.get(url, timeout=timeout)
        except _requests.RequestException as exc:
            return findings, f"defender alerts request failed: {exc}"
        if resp.status_code != 200:
            return findings, f"defender returned {resp.status_code}: {resp.text[:500]}"

        alerts = resp.json().get("value") or []
        for alert in alerts:
            props = alert.get("properties") or {}
            raw = {
                "finding_type": props.get("alertDisplayName") or props.get("alertType") or "defender-alert",
                "resource_type": props.get("resourceType") or "azure-resource",
                "resource_identifier": props.get("resourceIdentities", [{}])[0].get("resourceId") if props.get("resourceIdentities") else target,
                "severity": (props.get("severity") or "medium").lower(),
                "title": props.get("alertDisplayName") or "Microsoft Defender alert",
                "description": props.get("description") or props.get("remediationSteps"),
            }
            findings.append(self._emit(raw))
        return findings, None


SCANNER_RUNNERS: dict[str, BaseScanner] = {
    "trivy": TrivyScanner(),
    "checkov": CheckovScanner(),
    "sonarqube": SonarQubeScanner(),
    "defender": DefenderScanner(),
}


def list_scanners() -> list[dict[str, Any]]:
    return [runner.metadata() for runner in SCANNER_RUNNERS.values()]


def run_scanners(
    target: str,
    scanners: list[str] | None = None,
    timeout: int = 300,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected = scanners or list(SCANNER_RUNNERS.keys())
    findings: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for name in selected:
        runner = SCANNER_RUNNERS.get(name)
        if runner is None:
            failures.append({"scanner_name": name, "error_message": f"Unknown scanner: {name}"})
            continue
        if not runner.is_available():
            failures.append(
                {"scanner_name": name, "error_message": f"{name} is not available (not installed or not configured)"}
            )
            continue
        try:
            scanned, error = runner.run(target, timeout=timeout)
        except Exception as exc:  # Defensive: one scanner must not abort the whole run.
            failures.append({"scanner_name": name, "error_message": f"{name} failed: {exc}"})
            continue
        if error:
            failures.append({"scanner_name": name, "error_message": error})
        else:
            findings.extend(scanned)
    return findings, failures
