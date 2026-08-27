from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from groq import Groq
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from complisoc.backend.core.config import GROQ_API_KEY, GROQ_MODEL
from complisoc.backend.core.json_extract import extract_json

from complisoc.backend.database.session import get_db

from complisoc.backend.api.schemas import (
    AIMetricsRead,
    AuditBundleRead,
    BulkReviewDecision,
    ComplianceReportRead,
    ControlMappingRead,
    ControlRead,
    NormalizedFindingRead,
    ReportCreate,
    ReviewDecision,
    ReviewQueueItemDetailRead,
    ReviewQueueItemRead,
    ScenarioReportCreate,
    ScanRequest,
    ScanRunCreate,
    ScanRunRead,
    ScannerInfo,
    VerificationRecordRead,
)
from complisoc.backend.compliance.workflow import process_scan_run
from complisoc.backend.compliance.langchain_pipeline import run_pipeline
from complisoc.backend.compliance.diff import compare_scans
from complisoc.backend.compliance.lineage import get_finding_lineage as get_finding_lineage_data
from complisoc.backend.scanners.runners import list_scanners, resolve_scanners, run_scanners
from complisoc.backend.models import (
    AuditBundle,
    ComplianceReport,
    ControlCatalog,
    ControlMapping,
    NormalizedFinding,
    RawFinding,
    ReviewQueueItem,
    ScanRun,
    ScannerExecution,
    VerificationRecord,
)
from complisoc.backend.reporting.reports import generate_audit_bundle, generate_compliance_report, generate_scenario_report, verify_audit_bundle

app = FastAPI(title="Complisoc API")


def _run_compliance_pipeline(
    db: Session,
    *,
    target_environment: str,
    findings: list[dict],
    scanner_failures: list[dict] | None = None,
    framework: str | None = None,
    selected_scanners: list[str] | None = None,
) -> dict:
    """Run the compliance pipeline.

    The single orchestration implementation is the LangChain / LCEL chain in
    ``complisoc.backend.compliance.langchain_pipeline.run_pipeline`` (exposed
    here as ``process_scan_run`` via the workflow module). It returns the same
    dict shape the rest of the API relies on.
    """
    return run_pipeline(
        db,
        target_environment=target_environment,
        findings=findings,
        scanner_failures=scanner_failures,
        framework=framework,
        selected_scanners=selected_scanners,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def not_found(resource: str):
    raise HTTPException(
        status_code=404,
        detail={"code": "RESOURCE_NOT_FOUND", "message": f"{resource} does not exist"},
    )


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/readiness")
def readiness(db: Session = Depends(get_db)):
    db.query(ScanRun).count()
    return {"status": "ready", "database": "ok"}


@app.post("/api/v1/scan-runs", response_model=ScanRunRead, status_code=201)
def create_scan_run(payload: ScanRunCreate, db: Session = Depends(get_db)):
    result = _run_compliance_pipeline(
        db,
        target_environment=payload.target_environment,
        findings=[finding.model_dump() for finding in payload.findings],
        scanner_failures=[failure.model_dump() for failure in payload.scanner_failures],
    )
    return result["scan_run"]


@app.get("/api/v1/scanners", response_model=list[ScannerInfo])
def list_available_scanners():
    return [ScannerInfo(**item) for item in list_scanners()]


@app.post("/api/v1/scans", response_model=ScanRunRead, status_code=201)
def run_scan(payload: ScanRequest, db: Session = Depends(get_db)):
    findings, scanner_failures = run_scanners(
        payload.target,
        scanners=payload.scanners,
        scan_profile=payload.scan_profile,
    )
    selected = resolve_scanners(payload.scanners, payload.scan_profile)
    result = _run_compliance_pipeline(
        db,
        target_environment=payload.target,
        findings=findings,
        scanner_failures=scanner_failures,
        framework=payload.framework,
        selected_scanners=selected,
    )
    return result["scan_run"]


@app.get("/api/v1/scan-runs", response_model=list[ScanRunRead])
def list_scan_runs(include_archived: bool = False, archived_only: bool = False, db: Session = Depends(get_db)):
    query = db.query(ScanRun).options(joinedload(ScanRun.scanner_executions))
    if archived_only:
        query = query.filter(ScanRun.archived_at.is_not(None))
    elif not include_archived:
        query = query.filter(ScanRun.archived_at.is_(None))
    return query.order_by(ScanRun.id.desc()).all()


@app.get("/api/v1/scan-runs/{scan_run_id}", response_model=ScanRunRead)
def get_scan_run(scan_run_id: int, db: Session = Depends(get_db)):
    scan_run = db.get(ScanRun, scan_run_id, options=[joinedload(ScanRun.scanner_executions)])
    if scan_run is None:
        not_found("Scan run")
    return scan_run


@app.post("/api/v1/scan-runs/{scan_run_id}/archive", response_model=ScanRunRead)
def archive_scan_run(scan_run_id: int, db: Session = Depends(get_db)):
    scan_run = db.get(ScanRun, scan_run_id)
    if scan_run is None:
        not_found("Scan run")
    if scan_run.archived_at is None:
        scan_run.archived_at = datetime.utcnow()
        db.commit()
        db.refresh(scan_run)
    return scan_run


@app.post("/api/v1/scan-runs/{scan_run_id}/restore", response_model=ScanRunRead)
def restore_scan_run(scan_run_id: int, db: Session = Depends(get_db)):
    scan_run = db.get(ScanRun, scan_run_id)
    if scan_run is None:
        not_found("Scan run")
    scan_run.archived_at = None
    db.commit()
    db.refresh(scan_run)
    return scan_run


@app.get("/api/v1/scan-runs/{scan_run_id}/summary")
def get_scan_run_summary(scan_run_id: int, db: Session = Depends(get_db)):
    scan_run = db.get(ScanRun, scan_run_id)
    if scan_run is None:
        not_found("Scan run")
    raw_count = _raw_findings_for_scan_run(db, scan_run_id).count()
    normalized_count = _normalized_findings_for_scan_run(db, scan_run_id).count()
    mappings = _mappings_for_scan_run(db, scan_run_id)
    return {
        "scan_run_id": scan_run_id,
        "status": scan_run.status,
        "raw_findings": raw_count,
        "normalized_findings": normalized_count,
        "mappings": len(mappings),
        "published_mappings": sum(1 for m in mappings if m.mapping_status == "published"),
        "manual_review_mappings": sum(1 for m in mappings if m.mapping_status == "manual_review"),
    }


@app.get("/api/v1/findings", response_model=list[NormalizedFindingRead])
def list_findings(
    scan_run_id: int | None = None,
    severity: str | None = None,
    scanner: str | None = None,
    finding_type: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(NormalizedFinding)
    if scan_run_id is not None:
        query = _normalized_findings_for_scan_run(db, scan_run_id)
    if severity:
        query = query.filter(NormalizedFinding.severity == severity)
    if scanner:
        query = query.filter(NormalizedFinding.scanner_name == scanner)
    if finding_type:
        query = query.filter(NormalizedFinding.finding_type == finding_type)
    return query.order_by(NormalizedFinding.id.desc()).all()


@app.get("/api/v1/findings/{finding_id}", response_model=NormalizedFindingRead)
def get_finding(finding_id: int, db: Session = Depends(get_db)):
    finding = db.get(NormalizedFinding, finding_id)
    if finding is None:
        not_found("Finding")
    return finding


@app.get("/api/v1/findings/{finding_id}/mappings", response_model=list[ControlMappingRead])
def get_finding_mappings(finding_id: int, db: Session = Depends(get_db)):
    if db.get(NormalizedFinding, finding_id) is None:
        not_found("Finding")
    return db.query(ControlMapping).filter(ControlMapping.normalized_finding_id == finding_id).all()


@app.get("/api/v1/mappings", response_model=list[ControlMappingRead])
def list_mappings(
    framework: str | None = None,
    status: str | None = None,
    scan_run_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(ControlMapping)
    if scan_run_id is not None:
        query = _mappings_for_scan_run_query(db, scan_run_id)
    if framework:
        query = query.join(ControlMapping.control_catalog).filter(ControlCatalog.framework_name == framework)
    if status:
        query = query.filter(ControlMapping.mapping_status == status)
    return query.order_by(ControlMapping.id.desc()).all()


@app.get("/api/v1/mappings/{mapping_id}", response_model=ControlMappingRead)
def get_mapping(mapping_id: int, db: Session = Depends(get_db)):
    mapping = db.get(ControlMapping, mapping_id)
    if mapping is None:
        not_found("Mapping")
    return mapping


@app.get("/api/v1/mappings/{mapping_id}/verification", response_model=list[VerificationRecordRead])
def get_mapping_verification(mapping_id: int, db: Session = Depends(get_db)):
    if db.get(ControlMapping, mapping_id) is None:
        not_found("Mapping")
    return db.query(VerificationRecord).filter(VerificationRecord.control_mapping_id == mapping_id).all()


@app.get("/api/v1/review-queue", response_model=list[ReviewQueueItemDetailRead])
def list_review_queue(
    status: str | None = None,
    severity: str | None = None,
    control_id: str | None = None,
    scan_run_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            ReviewQueueItem,
            NormalizedFinding.severity,
            ControlCatalog.control_id,
            ScanRun.id,
        )
        .join(ControlMapping, ReviewQueueItem.control_mapping_id == ControlMapping.id)
        .join(NormalizedFinding, ControlMapping.normalized_finding_id == NormalizedFinding.id)
        .join(ControlCatalog, ControlMapping.control_catalog_id == ControlCatalog.id)
        .join(RawFinding, NormalizedFinding.raw_finding_id == RawFinding.id)
        .join(ScannerExecution, RawFinding.scanner_execution_id == ScannerExecution.id)
        .join(ScanRun, ScannerExecution.scan_run_id == ScanRun.id)
    )
    if status:
        query = query.filter(ReviewQueueItem.status == status)
    if severity:
        query = query.filter(NormalizedFinding.severity == severity)
    if control_id:
        query = query.filter(ControlCatalog.control_id == control_id)
    if scan_run_id:
        query = query.filter(ScanRun.id == scan_run_id)
    rows = query.order_by(ReviewQueueItem.id.desc()).all()
    return [
        ReviewQueueItemDetailRead(
            id=item.id,
            control_mapping_id=item.control_mapping_id,
            status=item.status,
            reviewer_id=item.reviewer_id,
            review_reason_code=item.review_reason_code,
            comments=item.comments,
            reviewed_at=item.reviewed_at,
            severity=sev,
            control_id=cid,
            scan_run_id=srid,
        )
        for item, sev, cid, srid in rows
    ]


@app.get("/api/v1/review-queue/{item_id}", response_model=ReviewQueueItemRead)
def get_review_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ReviewQueueItem, item_id)
    if item is None:
        not_found("Review item")
    return item


@app.post("/api/v1/review-queue/{item_id}/approve", response_model=ReviewQueueItemRead)
def approve_review_item(item_id: int, payload: ReviewDecision, db: Session = Depends(get_db)):
    return _decide_review_item(db, item_id, "approved", "published", payload)


@app.post("/api/v1/review-queue/{item_id}/reject", response_model=ReviewQueueItemRead)
def reject_review_item(item_id: int, payload: ReviewDecision, db: Session = Depends(get_db)):
    return _decide_review_item(db, item_id, "rejected", "rejected", payload)


@app.post("/api/v1/review-queue/bulk-decide", response_model=list[ReviewQueueItemRead])
def bulk_decide_review_items(payload: BulkReviewDecision, db: Session = Depends(get_db)):
    results = []
    for item_id in payload.item_ids:
        item = db.get(ReviewQueueItem, item_id)
        if item is None or item.status != "pending":
            continue
        mapping_status = "published" if payload.action == "approve" else "rejected"
        result = _decide_review_item(
            db,
            item_id,
            "approved" if payload.action == "approve" else "rejected",
            mapping_status,
            ReviewDecision(reviewer_id=payload.reviewer_id, comments=payload.comments),
            commit=False,
        )
        results.append(result)
    db.commit()
    for result in results:
        db.refresh(result)
    return results


@app.post("/api/v1/scan-runs/bulk-archive")
def bulk_archive_scan_runs(payload: dict[str, list[int]], db: Session = Depends(get_db)):
    scan_run_ids = payload.get("scan_run_ids", [])
    for scan_run_id in scan_run_ids:
        scan_run = db.get(ScanRun, scan_run_id)
        if scan_run and scan_run.archived_at is None:
            scan_run.archived_at = datetime.utcnow()
    db.commit()
    return {"archived_count": len(scan_run_ids)}


@app.post("/api/v1/review-queue/cleanup")
def cleanup_old_review_items(payload: dict[str, int] | None = None, db: Session = Depends(get_db)):
    older_than_days = (payload or {}).get("older_than_days", 30)
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    items = db.query(ReviewQueueItem).filter(
        ReviewQueueItem.status == "pending",
        ReviewQueueItem.created_at < cutoff,
    ).all()
    for item in items:
        item.status = "dismissed"
        item.reviewed_at = datetime.utcnow()
        item.reviewer_id = "system-cleanup"
        item.comments = "Auto-dismissed after 30 days without review"
    db.commit()
    return {"dismissed_count": len(items)}


@app.get("/api/v1/controls", response_model=list[ControlRead])
def list_controls(framework: str | None = None, db: Session = Depends(get_db)):
    query = db.query(ControlCatalog)
    if framework:
        query = query.filter(ControlCatalog.framework_name == framework)
    return query.order_by(ControlCatalog.framework_name, ControlCatalog.control_id).all()


@app.get("/api/v1/controls/{control_id}", response_model=ControlRead)
def get_control(control_id: int, db: Session = Depends(get_db)):
    control = db.get(ControlCatalog, control_id)
    if control is None:
        not_found("Control")
    return control


@app.get("/api/v1/reports", response_model=list[ComplianceReportRead])
def list_reports(db: Session = Depends(get_db)):
    return db.query(ComplianceReport).order_by(ComplianceReport.id.desc()).all()


@app.get("/api/v1/reports/{report_id}", response_model=ComplianceReportRead)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(ComplianceReport, report_id)
    if report is None:
        not_found("Report")
    return report


@app.post("/api/v1/reports/engineering", response_model=ComplianceReportRead, status_code=201)
def create_engineering_report(payload: ReportCreate, db: Session = Depends(get_db)):
    _ensure_scan_run(db, payload.scan_run_id)
    return generate_compliance_report(db, scan_run_id=payload.scan_run_id, report_type="engineering")


@app.post("/api/v1/reports/leadership", response_model=ComplianceReportRead, status_code=201)
def create_leadership_report(payload: ReportCreate, db: Session = Depends(get_db)):
    _ensure_scan_run(db, payload.scan_run_id)
    return generate_compliance_report(db, scan_run_id=payload.scan_run_id, report_type="leadership")


@app.post("/api/v1/reports/scenario", response_model=ComplianceReportRead, status_code=201)
def create_scenario_report(payload: ScenarioReportCreate, db: Session = Depends(get_db)):
    _ensure_scan_run(db, payload.scan_run_id)
    try:
        return generate_scenario_report(db, scan_run_id=payload.scan_run_id, scenario=payload.scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/v1/reports/{report_id}/pdf")
def download_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(ComplianceReport, report_id)
    if report is None:
        not_found("Report")
    filename = Path(report.content_path).name
    return _file_response(report.content_path, filename, "application/pdf")


@app.get("/api/v1/audit-bundles", response_model=list[AuditBundleRead])
def list_audit_bundles(db: Session = Depends(get_db)):
    return db.query(AuditBundle).order_by(AuditBundle.id.desc()).all()


@app.get("/api/v1/audit-bundles/{bundle_id}", response_model=AuditBundleRead)
def get_audit_bundle(bundle_id: int, db: Session = Depends(get_db)):
    bundle = db.get(AuditBundle, bundle_id)
    if bundle is None:
        not_found("Audit bundle")
    return bundle


@app.post("/api/v1/audit-bundles", response_model=AuditBundleRead, status_code=201)
def create_audit_bundle(payload: ReportCreate, db: Session = Depends(get_db)):
    _ensure_scan_run(db, payload.scan_run_id)
    return generate_audit_bundle(db, scan_run_id=payload.scan_run_id)


@app.get("/api/v1/audit-bundles/{bundle_id}/download")
def download_audit_bundle(bundle_id: int, db: Session = Depends(get_db)):
    bundle = db.get(AuditBundle, bundle_id)
    if bundle is None:
        not_found("Audit bundle")
    return _file_response(bundle.bundle_path, f"audit-bundle-{bundle_id}.json", "application/json")


@app.get("/api/v1/audit-bundles/{bundle_id}/verify")
def verify_audit_bundle_endpoint(bundle_id: int, db: Session = Depends(get_db)):
    bundle = db.get(AuditBundle, bundle_id)
    if bundle is None:
        not_found("Audit bundle")
    return verify_audit_bundle(bundle)


@app.post("/api/v1/audit-bundles/verify-all")
def verify_all_audit_bundles(db: Session = Depends(get_db)):
    bundles = db.query(AuditBundle).order_by(AuditBundle.id.desc()).all()
    return [verify_audit_bundle(bundle) for bundle in bundles]


def _dashboard_control_coverage(db: Session) -> dict[str, int]:
    mappings = db.query(ControlMapping).filter(ControlMapping.mapping_status == "published").all()
    covered = {mapping.control_catalog_id for mapping in mappings}
    total = db.query(ControlCatalog).filter(ControlCatalog.active_status.is_(True)).count()
    return {"covered_controls": len(covered), "total_controls": total}


@app.get("/api/v1/dashboard/control-coverage")
def dashboard_control_coverage(db: Session = Depends(get_db)):
    return _dashboard_control_coverage(db)


def _dashboard_severity_distribution(db: Session) -> dict[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for finding in db.query(NormalizedFinding).all():
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return {"severity_counts": counts}


@app.get("/api/v1/dashboard/severity-distribution")
def dashboard_severity_distribution(db: Session = Depends(get_db)):
    return _dashboard_severity_distribution(db)


def _dashboard_gap_summary(db: Session) -> dict[str, int | list[dict[str, object]]]:
    failed_controls: list[dict[str, object]] = []
    for status in ("manual_review", "rejected"):
        rows = (
            db.query(
                ControlMapping.control_catalog_id,
                ControlCatalog.control_id,
                ControlCatalog.title,
                func.count(ControlMapping.id).label("count"),
            )
            .join(ControlCatalog, ControlMapping.control_catalog_id == ControlCatalog.id)
            .filter(ControlMapping.mapping_status == status)
            .group_by(ControlMapping.control_catalog_id, ControlCatalog.control_id, ControlCatalog.title)
            .all()
        )
        for control_catalog_id, control_id, title, count in rows:
            failed_controls.append(
                {
                    "control_id": control_id,
                    "control_title": title,
                    "count": int(count),
                    "status": status,
                    "control_catalog_id": int(control_catalog_id),
                }
            )

    return {
        "manual_review_mappings": db.query(ControlMapping).filter(ControlMapping.mapping_status == "manual_review").count(),
        "rejected_mappings": db.query(ControlMapping).filter(ControlMapping.mapping_status == "rejected").count(),
        "failed_controls": sorted(
            failed_controls,
            key=lambda item: (item["status"], str(item["control_id"])),
        ),
    }


@app.get("/api/v1/dashboard/gap-summary")
def dashboard_gap_summary(db: Session = Depends(get_db)):
    return _dashboard_gap_summary(db)


def _dashboard_remediation_backlog(db: Session):
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    query = db.query(ControlMapping).filter(ControlMapping.mapping_status.in_(["manual_review", "rejected"]))
    total = query.count()
    mappings = (
        query.order_by(ControlMapping.id.desc())
        .limit(20)
        .all()
    )
    return {
        "items": [_mapping_backlog_item(mapping) for mapping in mappings],
        "total": total,
    }


@app.get("/api/v1/dashboard/remediation-backlog")
def dashboard_remediation_backlog(db: Session = Depends(get_db)):
    return _dashboard_remediation_backlog(db)


@app.get("/api/v1/dashboard/controls/{control_catalog_id}/drill-down")
def dashboard_control_drill_down(control_catalog_id: int, db: Session = Depends(get_db)):
    """Return traceable, processed findings for a control selected in the dashboard."""
    control = db.get(ControlCatalog, control_catalog_id)
    if control is None:
        not_found("Control")
    mappings = (
        db.query(ControlMapping)
        .filter(
            ControlMapping.control_catalog_id == control_catalog_id,
            ControlMapping.mapping_status.in_(["manual_review", "rejected"]),
        )
        .order_by(ControlMapping.id.desc())
        .all()
    )
    return {
        "control": {
            "id": control.id,
            "framework_name": control.framework_name,
            "control_id": control.control_id,
            "title": control.title,
            "description": control.description,
        },
        "items": [_mapping_backlog_item(mapping) for mapping in mappings],
    }


@app.post("/api/v1/dashboard/remediation-backlog/{mapping_id}/suggestion")
def dashboard_remediation_suggestion(mapping_id: int, db: Session = Depends(get_db)):
    """Generate a suggestion only after the operator asks for one.

    Keeping this out of the list endpoint prevents a large backlog or a slow AI
    provider from blocking the dashboard and keeps automated tests offline.
    """
    mapping = db.get(ControlMapping, mapping_id)
    if mapping is None:
        not_found("Mapping")
    if mapping.mapping_status not in {"manual_review", "rejected"}:
        raise HTTPException(status_code=409, detail={"code": "NOT_IN_BACKLOG", "message": "Mapping is not in remediation backlog"})
    steps, source = _suggested_remediation_steps_with_source(mapping)
    return {"mapping_id": mapping.id, "steps": steps, "source": source}


def _dashboard_trends(db: Session):
    trends = []
    scan_runs = (
        db.query(ScanRun)
        .filter(ScanRun.archived_at.is_(None))
        .order_by(ScanRun.created_at.desc())
        .limit(10)
        .all()
    )
    for scan_run in reversed(scan_runs):
        mappings = _mappings_for_scan_run(db, scan_run.id)
        trends.append(
            {
                "scan_run_id": scan_run.id,
                "created_at": scan_run.created_at,
                "published": len([mapping for mapping in mappings if mapping.mapping_status == "published"]),
                "manual_review": len([mapping for mapping in mappings if mapping.mapping_status == "manual_review"]),
            }
        )
    return {"trends": trends}


@app.get("/api/v1/dashboard/trends")
def dashboard_trends(db: Session = Depends(get_db)):
    return _dashboard_trends(db)


def _dashboard_cloud_findings(db: Session) -> dict[str, int]:
    alerts = (
        db.query(NormalizedFinding)
        .filter(
            NormalizedFinding.scanner_name == "defender",
            func.json_extract(NormalizedFinding.metadata_json, "$.defender_source") == "alerts",
        )
        .count()
    )
    recommendations = (
        db.query(NormalizedFinding)
        .filter(
            NormalizedFinding.scanner_name == "defender",
            func.json_extract(NormalizedFinding.metadata_json, "$.defender_source") == "assessments",
        )
        .count()
    )
    secure_scores = (
        db.query(NormalizedFinding)
        .filter(
            NormalizedFinding.scanner_name == "defender",
            func.json_extract(NormalizedFinding.metadata_json, "$.defender_source") == "secureScores",
        )
        .count()
    )
    return {"alerts": alerts, "recommendations": recommendations, "secure_scores": secure_scores}


@app.get("/api/v1/dashboard/cloud-findings")
def dashboard_cloud_findings(db: Session = Depends(get_db)):
    return _dashboard_cloud_findings(db)


def _dashboard_ai_metrics(db: Session) -> dict[str, Any]:
    mappings = db.query(ControlMapping).all()
    total = len(mappings)
    published = [m for m in mappings if m.mapping_status == "published"]
    manual_review = [m for m in mappings if m.mapping_status == "manual_review"]
    published_confidences = [m.final_confidence for m in published if m.final_confidence is not None]
    gemini_confidences = [m.gemini_confidence for m in mappings if m.gemini_confidence is not None]
    groq_agreements = [m.groq_agreement_value for m in mappings if m.groq_agreement_value is not None]
    verified_records = (
        db.query(VerificationRecord)
        .filter(VerificationRecord.result == "agree")
        .count()
    )
    total_verified = db.query(VerificationRecord).count()
    manual_review_rate = len(manual_review) / total if total else 0.0
    return {
        "total_mappings": total,
        "published_mappings": len(published),
        "manual_review_mappings": len(manual_review),
        "avg_gemini_confidence": sum(gemini_confidences) / len(gemini_confidences) if gemini_confidences else None,
        "avg_groq_agreement": sum(groq_agreements) / len(groq_agreements) if groq_agreements else None,
        "avg_final_confidence": sum(published_confidences) / len(published_confidences) if published_confidences else None,
        "agreement_rate": verified_records / total_verified if total_verified else None,
        "manual_review_rate": manual_review_rate,
    }


@app.get("/api/v1/dashboard/ai-metrics", response_model=AIMetricsRead)
def dashboard_ai_metrics(db: Session = Depends(get_db)):
    return _dashboard_ai_metrics(db)


def _ensure_scan_run(db: Session, scan_run_id: int):
    if db.get(ScanRun, scan_run_id) is None:
        not_found("Scan run")


def _file_response(path: str | None, filename: str, media_type: str = "application/json"):
    if not path or not Path(path).exists():
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "Artifact file does not exist"},
        )
    return FileResponse(path, media_type=media_type, filename=filename)


def _decide_review_item(db: Session, item_id: int, item_status: str, mapping_status: str, payload: ReviewDecision, commit: bool = True):
    item = db.get(ReviewQueueItem, item_id)
    if item is None:
        not_found("Review item")
    mapping = db.get(ControlMapping, item.control_mapping_id)
    if mapping is None:
        not_found("Mapping")
    item.status = item_status
    item.reviewer_id = payload.reviewer_id
    item.comments = payload.comments
    item.reviewed_at = datetime.utcnow()
    mapping.mapping_status = mapping_status
    if commit:
        db.commit()
        db.refresh(item)
    return item


def _raw_findings_for_scan_run(db: Session, scan_run_id: int):
    return (
        db.query(RawFinding)
        .join(RawFinding.scanner_execution)
        .filter(ScannerExecution.scan_run_id == scan_run_id)
    )


def _normalized_findings_for_scan_run(db: Session, scan_run_id: int):
    return (
        db.query(NormalizedFinding)
        .join(NormalizedFinding.raw_finding)
        .join(RawFinding.scanner_execution)
        .filter(ScannerExecution.scan_run_id == scan_run_id)
    )


def _mappings_for_scan_run_query(db: Session, scan_run_id: int):
    return (
        db.query(ControlMapping)
        .join(ControlMapping.normalized_finding)
        .join(NormalizedFinding.raw_finding)
        .join(RawFinding.scanner_execution)
        .filter(ScannerExecution.scan_run_id == scan_run_id)
    )


def _mappings_for_scan_run(db: Session, scan_run_id: int) -> list[ControlMapping]:
    return _mappings_for_scan_run_query(db, scan_run_id).all()


def _coerce_remediation_steps(payload: object) -> list[str]:
    if isinstance(payload, list):
        steps: list[str] = []
        for item in payload:
            if isinstance(item, dict):
                for key in ("step", "text", "action", "detail", "description", "instruction"):
                    value = item.get(key)
                    if value:
                        text = str(value).strip()
                        if text:
                            steps.append(text)
                            break
            else:
                text = str(item).strip()
                if text:
                    steps.append(text)
        return steps

    if isinstance(payload, dict):
        if isinstance(payload.get("steps"), list):
            return _coerce_remediation_steps(payload["steps"])
        if isinstance(payload.get("remediation_steps"), list):
            return _coerce_remediation_steps(payload["remediation_steps"])

        merged: list[str] = []
        for key in ("action", "detail", "suggestion", "summary", "step", "text"):
            value = payload.get(key)
            if value:
                string_value = str(value).strip()
                if string_value:
                    merged.append(string_value)
        if merged:
            return merged

    return []


def _suggested_remediation_steps(mapping: ControlMapping) -> list[str]:
    return _suggested_remediation_steps_with_source(mapping)[0]


def _suggested_remediation_steps_with_source(mapping: ControlMapping) -> tuple[list[str], str]:
    finding = mapping.normalized_finding
    control = mapping.control_catalog
    steps = [
        f"Review {finding.resource_identifier} and remove the root cause behind {finding.title}.",
        f"Apply the required {control.framework_name} {control.control_id} control update to the affected resource or configuration path.",
        "Capture evidence from the fix and re-run validation to confirm the issue is no longer reported.",
    ]

    if not GROQ_API_KEY:
        return steps, "deterministic_fallback"

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a remediation advisor. Return only JSON with a 'steps' array of 2-3 brief, concrete remediation steps.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Finding: {finding.title}\n"
                        f"Resource: {finding.resource_identifier}\n"
                        f"Severity: {finding.severity}\n"
                        f"Control: {control.framework_name} {control.control_id} ({control.title})\n"
                        "Provide 2-3 concrete, code-level or configuration-level remediation steps."
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=500,
            timeout=2.5,
        )
        data = extract_json(response.choices[0].message.content)
        parsed = data.get("steps") or data.get("remediation_steps") or data
        normalized = _coerce_remediation_steps(parsed)
        if len(normalized) >= 2:
            return normalized[:3], "groq"
    except Exception:
        pass
    return steps, "deterministic_fallback"


def _mapping_backlog_item(mapping: ControlMapping):
    finding = mapping.normalized_finding
    control = mapping.control_catalog
    return {
        "mapping_id": mapping.id,
        "control_catalog_id": control.id,
        "status": mapping.mapping_status,
        "severity": finding.severity,
        "resource_identifier": finding.resource_identifier,
        "control_id": control.control_id,
        "control_title": control.title,
        "gemini_confidence": mapping.gemini_confidence,
        "groq_agreement_value": mapping.groq_agreement_value,
    }


def _serialize_scan_diff(diff: dict[str, Any]) -> dict[str, Any]:
    return diff


@app.get("/api/v1/scan-runs/{scan_run_id}/drift")
def get_scan_drift(scan_run_id: int, compare_to: int | None = None, db: Session = Depends(get_db)):
    scan_run = db.get(ScanRun, scan_run_id)
    if scan_run is None:
        not_found("Scan run")
    if compare_to is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "MISSING_COMPARE_TO", "message": "Query parameter 'compare_to' is required."},
        )
    try:
        diff = compare_scans(db, compare_to, scan_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _serialize_scan_diff(diff)


@app.get("/api/v1/findings/{finding_id}/lineage")
def get_finding_lineage_endpoint(finding_id: int, db: Session = Depends(get_db)):
    try:
        return get_finding_lineage_data(db, finding_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
