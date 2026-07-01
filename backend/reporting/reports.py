import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from complisoc.backend.models import AuditBundle, ComplianceReport, ControlMapping, NormalizedFinding, RawFinding, ScanRun, ScannerExecution


ARTIFACT_ROOT = Path("artifacts")


def _write_artifact(kind: str, name: str, payload: dict[str, Any]) -> tuple[str, str]:
    directory = ARTIFACT_ROOT / kind
    directory.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, default=str, indent=2)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    path = directory / f"{name}-{digest[:12]}.json"
    path.write_text(encoded, encoding="utf-8")
    return str(path), digest


def _stable_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _scan_mappings(db: Session, scan_run_id: int) -> list[ControlMapping]:
    return (
        db.query(ControlMapping)
        .join(ControlMapping.normalized_finding)
        .join(NormalizedFinding.raw_finding)
        .join(RawFinding.scanner_execution)
        .filter(ScannerExecution.scan_run_id == scan_run_id)
        .all()
    )


def _mapping_payload(mapping: ControlMapping) -> dict[str, Any]:
    finding = mapping.normalized_finding
    control = mapping.control_catalog
    raw_finding = finding.raw_finding
    return {
        "mapping_id": mapping.id,
        "status": mapping.mapping_status,
        "final_confidence": mapping.final_confidence,
        "verification_status": mapping.verification_status,
        "rationale": mapping.rationale,
        "finding": {
            "id": finding.id,
            "raw_finding_id": raw_finding.id,
            "scanner_name": finding.scanner_name,
            "severity": finding.severity,
            "finding_type": finding.finding_type,
            "resource_type": finding.resource_type,
            "resource_identifier": finding.resource_identifier,
            "title": finding.title,
            "description": finding.description,
        },
        "control": {
            "id": control.id,
            "framework_name": control.framework_name,
            "control_id": control.control_id,
            "title": control.title,
            "family": control.control_family,
        },
        "verification_records": [
            {
                "id": record.id,
                "result": record.result,
                "explanation": record.explanation,
                "timestamp": record.timestamp,
            }
            for record in mapping.verification_records
        ],
        "remediation": _remediation_text(mapping),
    }


def _remediation_text(mapping: ControlMapping) -> str:
    finding = mapping.normalized_finding
    control = mapping.control_catalog
    return (
        f"Review {finding.resource_identifier} for {finding.title}. "
        f"Prioritize remediation against {control.framework_name} {control.control_id}: {control.title}."
    )


def _severity_counts(mappings: list[ControlMapping]) -> dict[str, int]:
    severities: dict[str, int] = {}
    for mapping in mappings:
        severity = mapping.normalized_finding.severity
        severities[severity] = severities.get(severity, 0) + 1
    return severities


def _framework_counts(mappings: list[ControlMapping]) -> dict[str, int]:
    frameworks: dict[str, int] = {}
    for mapping in mappings:
        framework = mapping.control_catalog.framework_name
        frameworks[framework] = frameworks.get(framework, 0) + 1
    return frameworks


def generate_compliance_report(db: Session, *, scan_run_id: int, report_type: str) -> ComplianceReport:
    if report_type not in {"engineering", "leadership"}:
        raise ValueError("report_type must be engineering or leadership")

    mappings = _scan_mappings(db, scan_run_id)
    published = [mapping for mapping in mappings if mapping.mapping_status == "published"]
    manual_review = [mapping for mapping in mappings if mapping.mapping_status == "manual_review"]

    payload = {
        "scan_run_id": scan_run_id,
        "report_type": report_type,
        "summary": {
            "total_mappings": len(mappings),
            "published_mappings": len(published),
            "manual_review_mappings": len(manual_review),
            "severity_counts": _severity_counts(mappings),
            "framework_counts": _framework_counts(mappings),
        },
    }
    if report_type == "engineering":
        payload["findings"] = [_mapping_payload(mapping) for mapping in mappings]
    else:
        coverage = _framework_counts(published)
        payload["posture"] = {
            "published_decisions": len(published),
            "manual_review_count": len(manual_review),
            "severity_counts": _severity_counts(published),
            "framework_coverage": coverage,
            "trend_ready_aggregates": {
                "scan_run_id": scan_run_id,
                "mapped_controls": len({mapping.control_catalog_id for mapping in published}),
                "manual_review_mappings": len(manual_review),
            },
        }
        payload["published_mappings"] = [_mapping_payload(mapping) for mapping in published]

    path, digest = _write_artifact("reports", f"{report_type}-scan-{scan_run_id}", payload)
    report = ComplianceReport(
        scan_run_id=scan_run_id,
        report_type=report_type,
        generated_by="complisoc-deterministic-mvp",
        content_path=path,
        content_hash=digest,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def generate_audit_bundle(db: Session, *, scan_run_id: int) -> AuditBundle:
    scan_run = db.get(ScanRun, scan_run_id)
    if scan_run is None:
        raise ValueError("scan_run_id must reference an existing ScanRun")

    mappings = _scan_mappings(db, scan_run_id)
    raw_findings = (
        db.query(RawFinding)
        .join(RawFinding.scanner_execution)
        .filter(ScannerExecution.scan_run_id == scan_run_id)
        .all()
    )
    normalized_findings = (
        db.query(NormalizedFinding)
        .join(NormalizedFinding.raw_finding)
        .join(RawFinding.scanner_execution)
        .filter(ScannerExecution.scan_run_id == scan_run_id)
        .all()
    )
    payload = {
        "scan_run": {
            "id": scan_run.id,
            "target_environment": scan_run.target_environment,
            "status": scan_run.status,
            "started_at": scan_run.started_at,
            "completed_at": scan_run.completed_at,
            "created_at": scan_run.created_at,
        },
        "raw_finding_ids": [finding.id for finding in raw_findings],
        "raw_finding_checksums": {
            str(finding.id): _stable_checksum(finding.raw_json)
            for finding in raw_findings
        },
        "normalized_findings": [
            {
                "id": finding.id,
                "raw_finding_id": finding.raw_finding_id,
                "scanner_name": finding.scanner_name,
                "finding_type": finding.finding_type,
                "resource_type": finding.resource_type,
                "resource_identifier": finding.resource_identifier,
                "severity": finding.severity,
                "title": finding.title,
                "timestamp": finding.timestamp,
            }
            for finding in normalized_findings
        ],
        "lineage": [_mapping_payload(mapping) for mapping in mappings],
    }
    path, digest = _write_artifact("audit-bundles", f"audit-bundle-scan-{scan_run_id}", payload)
    bundle = AuditBundle(
        scan_run_id=scan_run_id,
        bundle_path=path,
        checksum=digest,
    )
    db.add(bundle)
    db.commit()
    db.refresh(bundle)
    return bundle
