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
from abc import ABC, abstractmethod
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


class BaseScanner(ABC):
    name: str

    def is_available(self) -> bool:
        return bool(shutil.which(self.name))

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

    def run(self, target: str, timeout: int = 300) -> tuple[list[dict[str, Any]], str | None]:
        try:
            proc = subprocess.run(
                ["checkov", "-d", target, "--output", "json", "--compact"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            return [], f"checkov execution failed: {exc}"

        # Checkov returns 1 when misconfigurations are found, which is expected.
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

    def is_available(self) -> bool:
        return all(os.environ.get(env) for env in ["SONAR_HOST_URL", "SONAR_TOKEN"]) and _HAS_REQUESTS

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

    def is_available(self) -> bool:
        return all(os.environ.get(env) for env in ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID"]) and _HAS_REQUESTS

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
    return [{"name": name, "available": runner.is_available()} for name, runner in SCANNER_RUNNERS.items()]


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
