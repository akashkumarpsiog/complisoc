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


class ExternalServiceScanner(BaseScanner):
    """Scanners backed by external services.

    Unavailable until the required environment variables are set. The run method
    reports what is missing rather than raising, keeping the scan auditable.
    """

    def __init__(self, name: str, required_env: list[str], note: str) -> None:
        self.name = name
        self._required_env = required_env
        self._note = note

    def is_available(self) -> bool:
        return all(os.environ.get(env) for env in self._required_env)

    def run(self, target: str, timeout: int = 300) -> tuple[list[dict[str, Any]], str | None]:
        missing = [env for env in self._required_env if not os.environ.get(env)]
        if missing:
            return [], f"{self.name} requires {', '.join(missing)}; {self._note}"
        return [], f"{self.name} client is not implemented yet; set {', '.join(self._required_env)} to enable."


SCANNER_RUNNERS: dict[str, BaseScanner] = {
    "trivy": TrivyScanner(),
    "checkov": CheckovScanner(),
    "sonarqube": ExternalServiceScanner(
        "sonarqube",
        ["SONAR_HOST_URL", "SONAR_TOKEN"],
        "point it at a SonarQube server and implement the client",
    ),
    "defender": ExternalServiceScanner(
        "defender",
        ["AZURE_SUBSCRIPTION_ID"],
        "configure Microsoft Defender for Cloud and implement the client",
    ),
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
