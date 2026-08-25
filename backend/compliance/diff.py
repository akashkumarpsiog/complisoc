"""Compliance drift / scan-to-scan diff service.

Compares two completed scan runs and classifies findings as NEW, RESOLVED,
or UNCHANGED. Also calculates severity drift and control drift from existing
published mappings.

This is a read-only computed view over existing stored data. It does not
modify any pipeline, finding identity, or compliance workflow.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from complisoc.backend.models import ControlCatalog, ControlMapping, NormalizedFinding, RawFinding, ScanRun, ScannerExecution, ScannerExecution


def _finding_fingerprint(normalized: NormalizedFinding) -> str:
    """Deterministic, scan-independent fingerprint for a normalized finding.

    Uses only stable attributes that identify the same issue across scans.
    Excludes database IDs, timestamps, and scan-run context.
    """
    raw = normalized.raw_finding.raw_json if normalized.raw_finding else {}
    rule_id = (
        raw.get("check_id")
        or raw.get("check_name")
        or raw.get("finding_type")
        or normalized.finding_type
    )
    parts = [
        (normalized.scanner_name or "").strip().lower(),
        (normalized.finding_type or "").strip().lower(),
        (normalized.resource_type or "").strip().lower(),
        (normalized.resource_identifier or "").strip().lower(),
        (rule_id or "").strip().lower(),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


@dataclass
class DriftFinding:
    fingerprint: str
    scanner_name: str
    finding_type: str
    resource_type: str
    resource_identifier: str
    severity: str
    title: str
    first_seen: str | None
    last_seen: str | None
    status: str  # NEW | RESOLVED | UNCHANGED
    control_ids: list[str] = field(default_factory=list)


@dataclass
class ScanDiff:
    previous_scan_id: int | None
    current_scan_id: int
    previous_finding_count: int
    current_finding_count: int
    new_count: int
    resolved_count: int
    unchanged_count: int
    new_findings: list[DriftFinding]
    resolved_findings: list[DriftFinding]
    unchanged_findings: list[DriftFinding]
    severity_new: dict[str, int]
    severity_resolved: dict[str, int]
    new_control_ids: list[str]
    resolved_control_ids: list[str]


def _load_normalized_findings(db: Session, scan_run_id: int) -> list[NormalizedFinding]:
    return (
        db.query(NormalizedFinding)
        .join(NormalizedFinding.raw_finding)
        .join(RawFinding.scanner_execution)
        .filter(ScannerExecution.scan_run_id == scan_run_id)
        .all()
    )


def _load_published_control_ids(db: Session, normalized_finding_ids: list[int]) -> dict[int, list[str]]:
    rows = (
        db.query(ControlMapping.normalized_finding_id, ControlCatalog.control_id)
        .join(ControlCatalog, ControlMapping.control_catalog_id == ControlCatalog.id)
        .filter(ControlMapping.normalized_finding_id.in_(normalized_finding_ids))
        .filter(ControlMapping.mapping_status == "published")
        .all()
    )
    result: dict[int, list[str]] = {}
    for nf_id, control_id in rows:
        result.setdefault(nf_id, []).append(control_id)
    return result


def _to_drift_finding(
    normalized: NormalizedFinding,
    status: str,
    control_ids: list[str] | None = None,
) -> DriftFinding:
    raw = normalized.raw_finding.raw_json if normalized.raw_finding else {}
    return DriftFinding(
        fingerprint=_finding_fingerprint(normalized),
        scanner_name=normalized.scanner_name,
        finding_type=normalized.finding_type,
        resource_type=normalized.resource_type,
        resource_identifier=normalized.resource_identifier,
        severity=normalized.severity,
        title=normalized.title,
        first_seen=normalized.timestamp.isoformat() if normalized.timestamp else None,
        last_seen=normalized.timestamp.isoformat() if normalized.timestamp else None,
        status=status,
        control_ids=control_ids or [],
    )


def compare_scans(db: Session, previous_scan_id: int | None, current_scan_id: int) -> ScanDiff:
    if previous_scan_id is None:
        current = db.get(ScanRun, current_scan_id)
        if current is None:
            raise ValueError("current_scan_id must reference an existing ScanRun")
        findings = _load_normalized_findings(db, current_scan_id)
        control_map = _load_published_control_ids(db, [f.id for f in findings])
        drift_findings = [
            _to_drift_finding(f, "NEW", control_map.get(f.id, [])) for f in findings
        ]
        return ScanDiff(
            previous_scan_id=None,
            current_scan_id=current_scan_id,
            previous_finding_count=0,
            current_finding_count=len(findings),
            new_count=len(findings),
            resolved_count=0,
            unchanged_count=0,
            new_findings=drift_findings,
            resolved_findings=[],
            unchanged_findings=[],
            severity_new=Counter(f.severity for f in findings),
            severity_resolved={},
            new_control_ids=sorted({cid for cids in control_map.values() for cid in cids}),
            resolved_control_ids=[],
        )

    previous = db.get(ScanRun, previous_scan_id)
    current = db.get(ScanRun, current_scan_id)
    if previous is None or current is None:
        raise ValueError("Both scan_run_ids must reference existing ScanRuns")
    if previous.status != "completed" or current.status != "completed":
        raise ValueError("Only completed scans can be compared")

    previous_findings = _load_normalized_findings(db, previous_scan_id)
    current_findings = _load_normalized_findings(db, current_scan_id)

    previous_by_fp = {_finding_fingerprint(f): f for f in previous_findings}
    current_by_fp = {_finding_fingerprint(f): f for f in current_findings}

    previous_ids = set(previous_by_fp.keys())
    current_ids = set(current_by_fp.keys())

    new_fps = current_ids - previous_ids
    resolved_fps = previous_ids - current_ids
    common_fps = previous_ids & current_ids

    # Load published control IDs for both scans
    all_current_nf_ids = [f.id for f in current_findings]
    all_previous_nf_ids = [f.id for f in previous_findings]
    current_control_map = _load_published_control_ids(db, all_current_nf_ids)
    previous_control_map = _load_published_control_ids(db, all_previous_nf_ids)

    new_findings = [
        _to_drift_finding(current_by_fp[fp], "NEW", current_control_map.get(current_by_fp[fp].id, []))
        for fp in sorted(new_fps)
    ]
    resolved_findings = [
        _to_drift_finding(previous_by_fp[fp], "RESOLVED", previous_control_map.get(previous_by_fp[fp].id, []))
        for fp in sorted(resolved_fps)
    ]
    unchanged_findings = [
        _to_drift_finding(current_by_fp[fp], "UNCHANGED", current_control_map.get(current_by_fp[fp].id, []))
        for fp in sorted(common_fps)
    ]

    severity_new = Counter(f.severity for f in new_findings)
    severity_resolved = Counter(f.severity for f in resolved_findings)

    previous_control_ids = {cid for cids in previous_control_map.values() for cid in cids}
    current_control_ids = {cid for cids in current_control_map.values() for cid in cids}
    new_control_ids = sorted(current_control_ids - previous_control_ids)
    resolved_control_ids = sorted(previous_control_ids - current_control_ids)

    return ScanDiff(
        previous_scan_id=previous_scan_id,
        current_scan_id=current_scan_id,
        previous_finding_count=len(previous_findings),
        current_finding_count=len(current_findings),
        new_count=len(new_findings),
        resolved_count=len(resolved_findings),
        unchanged_count=len(unchanged_findings),
        new_findings=new_findings,
        resolved_findings=resolved_findings,
        unchanged_findings=unchanged_findings,
        severity_new=dict(severity_new),
        severity_resolved=dict(severity_resolved),
        new_control_ids=new_control_ids,
        resolved_control_ids=resolved_control_ids,
    )


def _serialize_scan_diff(diff: ScanDiff) -> dict[str, Any]:
    return {
        "previous_scan_id": diff.previous_scan_id,
        "current_scan_id": diff.current_scan_id,
        "previous_finding_count": diff.previous_finding_count,
        "current_finding_count": diff.current_finding_count,
        "new_count": diff.new_count,
        "resolved_count": diff.resolved_count,
        "unchanged_count": diff.unchanged_count,
        "net_change": diff.new_count - diff.resolved_count,
        "new_findings": [
            {
                "fingerprint": f.fingerprint,
                "scanner_name": f.scanner_name,
                "finding_type": f.finding_type,
                "resource_type": f.resource_type,
                "resource_identifier": f.resource_identifier,
                "severity": f.severity,
                "title": f.title,
                "first_seen": f.first_seen,
                "last_seen": f.last_seen,
                "status": f.status,
                "control_ids": f.control_ids,
            }
            for f in diff.new_findings
        ],
        "resolved_findings": [
            {
                "fingerprint": f.fingerprint,
                "scanner_name": f.scanner_name,
                "finding_type": f.finding_type,
                "resource_type": f.resource_type,
                "resource_identifier": f.resource_identifier,
                "severity": f.severity,
                "title": f.title,
                "first_seen": f.first_seen,
                "last_seen": f.last_seen,
                "status": f.status,
                "control_ids": f.control_ids,
            }
            for f in diff.resolved_findings
        ],
        "unchanged_findings": [
            {
                "fingerprint": f.fingerprint,
                "scanner_name": f.scanner_name,
                "finding_type": f.finding_type,
                "resource_type": f.resource_type,
                "resource_identifier": f.resource_identifier,
                "severity": f.severity,
                "title": f.title,
                "first_seen": f.first_seen,
                "last_seen": f.last_seen,
                "status": f.status,
                "control_ids": f.control_ids,
            }
            for f in diff.unchanged_findings
        ],
        "severity_new": diff.severity_new,
        "severity_resolved": diff.severity_resolved,
        "new_control_ids": diff.new_control_ids,
        "resolved_control_ids": diff.resolved_control_ids,
    }
