from sqlalchemy.orm import Session

from complisoc.backend.models import NormalizedFinding, RawFinding


SEVERITIES = {"critical", "high", "medium", "low", "info"}
SEVERITY_ALIASES = {
    "severe": "critical",
    "moderate": "medium",
    "warning": "medium",
    "unknown": "info",
}


def normalize_severity(value: object) -> str:
    severity = str(value or "info").strip().lower()
    severity = SEVERITY_ALIASES.get(severity, severity)
    if severity not in SEVERITIES:
        raise ValueError(f"Unsupported severity: {value}")
    return severity


def normalize_raw_finding(db: Session, raw_finding: RawFinding) -> NormalizedFinding:
    payload = raw_finding.raw_json or {}
    if not isinstance(payload, dict):
        raise ValueError("raw_json must be an object")

    finding_type = payload.get("finding_type") or payload.get("type") or payload.get("category") or payload.get("check_id")
    resource_type = payload.get("resource_type") or payload.get("resourceType") or payload.get("asset_type") or "unknown"
    resource_identifier = (
        payload.get("resource_identifier")
        or payload.get("resource")
        or payload.get("target")
        or payload.get("file")
        or payload.get("id")
    )
    title = payload.get("title") or payload.get("name") or payload.get("message") or payload.get("check_name") or payload.get("description")
    description = payload.get("description") or payload.get("message") or payload.get("short_description") or payload.get("check_name") or title

    if not finding_type or not resource_identifier or not title:
        raise ValueError("raw finding requires finding_type/type, resource/resource_identifier, and title/message")

    normalized = NormalizedFinding(
        raw_finding_id=raw_finding.id,
        scanner_name=raw_finding.scanner_name,
        finding_type=str(finding_type)[:128],
        resource_type=str(resource_type)[:128],
        resource_identifier=str(resource_identifier)[:512],
        severity=normalize_severity(payload.get("severity")),
        title=str(title)[:512],
        description=str(description)[:1024] if description else None,
        metadata_json=payload,
    )
    db.add(normalized)
    db.commit()
    db.refresh(normalized)
    return normalized

