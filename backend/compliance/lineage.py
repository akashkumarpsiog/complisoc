"""Evidence lineage retrieval service.

Provides read-only access to the existing evidence chain:

    ScanRun -> RawFinding -> NormalizedFinding -> ControlMapping -> VerificationRecord

This module does not modify any data. It only queries and serializes existing
relationships.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from complisoc.backend.models import (
    ControlCatalog,
    ControlMapping,
    NormalizedFinding,
    RawFinding,
    ScanRun,
    ScannerExecution,
    VerificationRecord,
)


def get_finding_lineage(db: Session, normalized_finding_id: int) -> dict[str, Any]:
    normalized = db.get(NormalizedFinding, normalized_finding_id)
    if normalized is None:
        raise ValueError("normalized_finding_id must reference an existing NormalizedFinding")

    raw = db.get(RawFinding, normalized.raw_finding_id)
    scanner_execution = None
    scan_run = None
    if raw:
        scanner_execution = db.get(ScannerExecution, raw.scanner_execution_id)
        if scanner_execution:
            scan_run = db.get(ScanRun, scanner_execution.scan_run_id)

    mappings = (
        db.query(ControlMapping)
        .filter(ControlMapping.normalized_finding_id == normalized_finding_id)
        .all()
    )

    mapping_payloads = []
    for mapping in mappings:
        control = db.get(ControlCatalog, mapping.control_catalog_id)
        verification_records = (
            db.query(VerificationRecord)
            .filter(VerificationRecord.control_mapping_id == mapping.id)
            .all()
        )
        mapping_payloads.append({
            "mapping_id": mapping.id,
            "control_catalog_id": control.id if control else None,
            "control_id": control.control_id if control else None,
            "framework_name": control.framework_name if control else None,
            "control_title": control.title if control else None,
            "mapping_status": mapping.mapping_status,
            "gemini_confidence": mapping.gemini_confidence,
            "final_confidence": mapping.final_confidence,
            "verification_status": mapping.verification_status,
            "groq_agreement_value": mapping.groq_agreement_value,
            "rationale": mapping.rationale,
            "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
            "verification_records": [
                {
                    "id": vr.id,
                    "result": vr.result,
                    "explanation": vr.explanation,
                    "agreement_value": vr.agreement_value,
                    "verification_model": vr.verification_model,
                    "timestamp": vr.timestamp.isoformat() if vr.timestamp else None,
                }
                for vr in verification_records
            ],
        })

    return {
        "scan_run": {
            "id": scan_run.id if scan_run else None,
            "target_environment": scan_run.target_environment if scan_run else None,
            "status": scan_run.status if scan_run else None,
            "started_at": scan_run.started_at.isoformat() if scan_run and scan_run.started_at else None,
            "completed_at": scan_run.completed_at.isoformat() if scan_run and scan_run.completed_at else None,
            "created_at": scan_run.created_at.isoformat() if scan_run and scan_run.created_at else None,
        } if scan_run else None,
        "raw_finding": {
            "id": raw.id if raw else None,
            "scanner_finding_id": raw.scanner_finding_id if raw else None,
            "scanner_name": raw.scanner_name if raw else None,
            "raw_json": raw.raw_json if raw else None,
            "created_at": raw.created_at.isoformat() if raw and raw.created_at else None,
        } if raw else None,
        "normalized_finding": {
            "id": normalized.id,
            "scanner_name": normalized.scanner_name,
            "finding_type": normalized.finding_type,
            "resource_type": normalized.resource_type,
            "resource_identifier": normalized.resource_identifier,
            "severity": normalized.severity,
            "title": normalized.title,
            "description": normalized.description,
            "timestamp": normalized.timestamp.isoformat() if normalized.timestamp else None,
            "metadata_json": normalized.metadata_json,
        },
        "mappings": mapping_payloads,
    }
