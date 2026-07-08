from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from complisoc.backend.database.session import get_db

from complisoc.backend.api.schemas import (
    AuditBundleRead,
    ComplianceReportRead,
    ControlMappingRead,
    ControlRead,
    NormalizedFindingRead,
    ReportCreate,
    ReviewDecision,
    ReviewQueueItemRead,
    ScanRequest,
    ScanRunCreate,
    ScanRunRead,
    ScannerInfo,
    VerificationRecordRead,
)
from complisoc.backend.compliance.workflow import process_scan_run
from complisoc.backend.scanners.runners import list_scanners, run_scanners
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
from complisoc.backend.reporting.reports import generate_audit_bundle, generate_compliance_report

app = FastAPI(title="Complisoc API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
    result = process_scan_run(
        db,
        target_environment=payload.target_environment,
        findings=[finding.model_dump() for finding in payload.findings],
        scanner_failures=[failure.model_dump() for failure in payload.scanner_failures],
    )
    return result["scan_run"]


@app.get("/api/v1/scanners", response_model=list[ScannerInfo])
def list_available_scanners():
    return [ScannerInfo(name=item["name"], available=item["available"]) for item in list_scanners()]


@app.post("/api/v1/scans", response_model=ScanRunRead, status_code=201)
def run_scan(payload: ScanRequest, db: Session = Depends(get_db)):
    findings, scanner_failures = run_scanners(payload.target, payload.scanners)
    result = process_scan_run(
        db,
        target_environment=payload.target,
        findings=findings,
        scanner_failures=scanner_failures,
        framework=payload.framework,
    )
    return result["scan_run"]


@app.get("/api/v1/scan-runs", response_model=list[ScanRunRead])
def list_scan_runs(db: Session = Depends(get_db)):
    return db.query(ScanRun).order_by(ScanRun.id.desc()).all()


@app.get("/api/v1/scan-runs/{scan_run_id}", response_model=ScanRunRead)
def get_scan_run(scan_run_id: int, db: Session = Depends(get_db)):
    scan_run = db.get(ScanRun, scan_run_id)
    if scan_run is None:
        not_found("Scan run")
    return scan_run


@app.get("/api/v1/scan-runs/{scan_run_id}/summary")
def get_scan_run_summary(scan_run_id: int, db: Session = Depends(get_db)):
    scan_run = db.get(ScanRun, scan_run_id)
    if scan_run is None:
        not_found("Scan run")
    mappings = _mappings_for_scan_run(db, scan_run_id)
    return {
        "scan_run_id": scan_run_id,
        "status": scan_run.status,
        "raw_findings": _raw_findings_for_scan_run(db, scan_run_id).count(),
        "normalized_findings": _normalized_findings_for_scan_run(db, scan_run_id).count(),
        "mappings": len(mappings),
        "published_mappings": len([mapping for mapping in mappings if mapping.mapping_status == "published"]),
        "manual_review_mappings": len([mapping for mapping in mappings if mapping.mapping_status == "manual_review"]),
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


@app.get("/api/v1/review-queue", response_model=list[ReviewQueueItemRead])
def list_review_queue(db: Session = Depends(get_db)):
    return db.query(ReviewQueueItem).order_by(ReviewQueueItem.id.desc()).all()


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


@app.get("/api/v1/reports/{report_id}/pdf")
def download_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(ComplianceReport, report_id)
    if report is None:
        not_found("Report")
    return _file_response(report.content_path, f"report-{report_id}.pdf", "application/pdf")


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


@app.get("/api/v1/dashboard/control-coverage")
def dashboard_control_coverage(db: Session = Depends(get_db)):
    mappings = db.query(ControlMapping).filter(ControlMapping.mapping_status == "published").all()
    covered = {mapping.control_catalog_id for mapping in mappings}
    total = db.query(ControlCatalog).filter(ControlCatalog.active_status.is_(True)).count()
    return {"covered_controls": len(covered), "total_controls": total}


@app.get("/api/v1/dashboard/severity-distribution")
def dashboard_severity_distribution(db: Session = Depends(get_db)):
    counts: dict[str, int] = {}
    for finding in db.query(NormalizedFinding).all():
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return {"severity_counts": counts}


@app.get("/api/v1/dashboard/gap-summary")
def dashboard_gap_summary(db: Session = Depends(get_db)):
    return {
        "manual_review_mappings": db.query(ControlMapping).filter(ControlMapping.mapping_status == "manual_review").count(),
        "rejected_mappings": db.query(ControlMapping).filter(ControlMapping.mapping_status == "rejected").count(),
    }


@app.get("/api/v1/dashboard/remediation-backlog")
def dashboard_remediation_backlog(db: Session = Depends(get_db)):
    mappings = db.query(ControlMapping).filter(ControlMapping.mapping_status.in_(["manual_review", "rejected"])).all()
    return {"items": [_mapping_backlog_item(mapping) for mapping in mappings]}


@app.get("/api/v1/dashboard/trends")
def dashboard_trends(db: Session = Depends(get_db)):
    trends = []
    for scan_run in db.query(ScanRun).order_by(ScanRun.created_at).all():
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


def _decide_review_item(db: Session, item_id: int, item_status: str, mapping_status: str, payload: ReviewDecision):
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


def _mapping_backlog_item(mapping: ControlMapping):
    return {
        "mapping_id": mapping.id,
        "status": mapping.mapping_status,
        "severity": mapping.normalized_finding.severity,
        "resource_identifier": mapping.normalized_finding.resource_identifier,
        "control_id": mapping.control_catalog.control_id,
        "control_title": mapping.control_catalog.title,
    }
