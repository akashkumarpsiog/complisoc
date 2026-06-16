from sqlalchemy.orm import Session
from complisoc.backend.models import (
    ScanRun,
    ScannerExecution,
    RawFinding,
    NormalizedFinding,
    ControlCatalog,
    CandidateControl,
    ControlMapping,
    VerificationRecord,
    ReviewQueueItem,
    ComplianceReport,
    AuditBundle,
)


class ScanRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        scan_run = ScanRun(**kwargs)
        self.db.add(scan_run)
        self.db.commit()
        self.db.refresh(scan_run)
        return scan_run

    def get(self, scan_run_id: int):
        return self.db.query(ScanRun).filter(ScanRun.id == scan_run_id).first()

    def list(self):
        return self.db.query(ScanRun).all()


class ScannerExecutionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        execution = ScannerExecution(**kwargs)
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        return execution

    def get(self, execution_id: int):
        return self.db.query(ScannerExecution).filter(ScannerExecution.id == execution_id).first()

    def list_by_scan_run(self, scan_run_id: int):
        return self.db.query(ScannerExecution).filter(ScannerExecution.scan_run_id == scan_run_id).all()


class RawFindingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        raw_finding = RawFinding(**kwargs)
        self.db.add(raw_finding)
        self.db.commit()
        self.db.refresh(raw_finding)
        return raw_finding

    def get(self, finding_id: int):
        return self.db.query(RawFinding).filter(RawFinding.id == finding_id).first()

    def list_by_execution(self, execution_id: int):
        return self.db.query(RawFinding).filter(RawFinding.scanner_execution_id == execution_id).all()


class NormalizedFindingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        normalized_finding = NormalizedFinding(**kwargs)
        self.db.add(normalized_finding)
        self.db.commit()
        self.db.refresh(normalized_finding)
        return normalized_finding

    def get(self, finding_id: int):
        return self.db.query(NormalizedFinding).filter(NormalizedFinding.id == finding_id).first()

    def list_by_scan_run(self, scan_run_id: int):
        return (
            self.db.query(NormalizedFinding)
            .join(NormalizedFinding.raw_finding)
            .join(RawFinding.scanner_execution)
            .filter(ScannerExecution.scan_run_id == scan_run_id)
            .all()
        )


class ControlCatalogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        control = ControlCatalog(**kwargs)
        self.db.add(control)
        self.db.commit()
        self.db.refresh(control)
        return control

    def get(self, control_id: int):
        return self.db.query(ControlCatalog).filter(ControlCatalog.id == control_id).first()

    def list(self):
        return self.db.query(ControlCatalog).all()


class CandidateControlRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        candidate = CandidateControl(**kwargs)
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def bulk_create(self, definitions):
        candidates = [CandidateControl(**kwargs) for kwargs in definitions]
        self.db.bulk_save_objects(candidates)
        self.db.commit()
        return candidates

    def list_by_normalized_finding(self, normalized_finding_id: int):
        return self.db.query(CandidateControl).filter(CandidateControl.normalized_finding_id == normalized_finding_id).all()


class ControlMappingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        mapping = ControlMapping(**kwargs)
        self.db.add(mapping)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def get(self, mapping_id: int):
        return self.db.query(ControlMapping).filter(ControlMapping.id == mapping_id).first()

    def list_by_scan_run(self, scan_run_id: int):
        return (
            self.db.query(ControlMapping)
            .join(ControlMapping.normalized_finding)
            .join(NormalizedFinding.raw_finding)
            .join(RawFinding.scanner_execution)
            .filter(ScannerExecution.scan_run_id == scan_run_id)
            .all()
        )


class VerificationRecordRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        record = VerificationRecord(**kwargs)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_by_mapping(self, mapping_id: int):
        return self.db.query(VerificationRecord).filter(VerificationRecord.control_mapping_id == mapping_id).all()


class ReviewQueueItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        item = ReviewQueueItem(**kwargs)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get(self, item_id: int):
        return self.db.query(ReviewQueueItem).filter(ReviewQueueItem.id == item_id).first()

    def list_pending(self):
        return self.db.query(ReviewQueueItem).filter(ReviewQueueItem.status == "pending").all()


class ComplianceReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        report = ComplianceReport(**kwargs)
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def get(self, report_id: int):
        return self.db.query(ComplianceReport).filter(ComplianceReport.id == report_id).first()

    def list_by_scan_run(self, scan_run_id: int):
        return self.db.query(ComplianceReport).filter(ComplianceReport.scan_run_id == scan_run_id).all()


class AuditBundleRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        bundle = AuditBundle(**kwargs)
        self.db.add(bundle)
        self.db.commit()
        self.db.refresh(bundle)
        return bundle

    def get(self, bundle_id: int):
        return self.db.query(AuditBundle).filter(AuditBundle.id == bundle_id).first()

    def list_by_scan_run(self, scan_run_id: int):
        return self.db.query(AuditBundle).filter(AuditBundle.scan_run_id == scan_run_id).all()
