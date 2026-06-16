from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship
from complisoc.backend.database.base import Base


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id = Column(Integer, primary_key=True, index=True)
    target_environment = Column(String(128), nullable=False)
    status = Column(String(50), nullable=False, default="created")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scanner_executions = relationship("ScannerExecution", back_populates="scan_run", cascade="all, delete-orphan")
    compliance_reports = relationship("ComplianceReport", back_populates="scan_run", cascade="all, delete-orphan")
    audit_bundles = relationship("AuditBundle", back_populates="scan_run", cascade="all, delete-orphan")


class ScannerExecution(Base):
    __tablename__ = "scanner_executions"

    id = Column(Integer, primary_key=True, index=True)
    scan_run_id = Column(Integer, ForeignKey("scan_runs.id"), nullable=False)
    scanner_name = Column(String(128), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scan_run = relationship("ScanRun", back_populates="scanner_executions")
    raw_findings = relationship("RawFinding", back_populates="scanner_execution", cascade="all, delete-orphan")


class RawFinding(Base):
    __tablename__ = "raw_findings"

    id = Column(Integer, primary_key=True, index=True)
    scanner_execution_id = Column(Integer, ForeignKey("scanner_executions.id"), nullable=False)
    scanner_finding_id = Column(String(256), nullable=False)
    scanner_name = Column(String(128), nullable=False)
    raw_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    scanner_execution = relationship("ScannerExecution", back_populates="raw_findings")
    normalized_findings = relationship("NormalizedFinding", back_populates="raw_finding", cascade="all, delete-orphan")


class NormalizedFinding(Base):
    __tablename__ = "normalized_findings"

    id = Column(Integer, primary_key=True, index=True)
    raw_finding_id = Column(Integer, ForeignKey("raw_findings.id"), nullable=False)
    scanner_name = Column(String(128), nullable=False)
    finding_type = Column(String(128), nullable=False)
    resource_type = Column(String(128), nullable=False)
    resource_identifier = Column(String(512), nullable=False)
    severity = Column(String(50), nullable=False)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    raw_finding = relationship("RawFinding", back_populates="normalized_findings")
    candidate_controls = relationship("CandidateControl", back_populates="normalized_finding", cascade="all, delete-orphan")
    control_mappings = relationship("ControlMapping", back_populates="normalized_finding", cascade="all, delete-orphan")


class ControlCatalog(Base):
    __tablename__ = "control_catalog"

    id = Column(Integer, primary_key=True, index=True)
    framework_name = Column(String(128), nullable=False)
    control_id = Column(String(128), nullable=False)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(64), nullable=False)
    active_status = Column(Boolean, nullable=False, default=True)
    control_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    candidate_controls = relationship("CandidateControl", back_populates="control_catalog", cascade="all, delete-orphan")
    control_mappings = relationship("ControlMapping", back_populates="control_catalog", cascade="all, delete-orphan")


class CandidateControl(Base):
    __tablename__ = "candidate_controls"

    id = Column(Integer, primary_key=True, index=True)
    normalized_finding_id = Column(Integer, ForeignKey("normalized_findings.id"), nullable=False)
    control_catalog_id = Column(Integer, ForeignKey("control_catalog.id"), nullable=False)
    source = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    normalized_finding = relationship("NormalizedFinding", back_populates="candidate_controls")
    control_catalog = relationship("ControlCatalog", back_populates="candidate_controls")
    control_mappings = relationship("ControlMapping", back_populates="candidate_control", cascade="all, delete-orphan")


class ControlMapping(Base):
    __tablename__ = "control_mappings"

    id = Column(Integer, primary_key=True, index=True)
    normalized_finding_id = Column(Integer, ForeignKey("normalized_findings.id"), nullable=False)
    candidate_control_id = Column(Integer, ForeignKey("candidate_controls.id"), nullable=True)
    control_catalog_id = Column(Integer, ForeignKey("control_catalog.id"), nullable=False)
    rank = Column(Integer, nullable=False, default=1)
    mapping_model = Column(String(256), nullable=False)
    prompt_version = Column(String(128), nullable=False)
    rationale = Column(Text, nullable=True)
    gemini_confidence = Column(Float, nullable=True)
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    normalized_finding = relationship("NormalizedFinding", back_populates="control_mappings")
    candidate_control = relationship("CandidateControl", back_populates="control_mappings")
    control_catalog = relationship("ControlCatalog", back_populates="control_mappings")
    verification_records = relationship("VerificationRecord", back_populates="control_mapping", cascade="all, delete-orphan")
    review_queue_items = relationship("ReviewQueueItem", back_populates="control_mapping", cascade="all, delete-orphan")


class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id = Column(Integer, primary_key=True, index=True)
    control_mapping_id = Column(Integer, ForeignKey("control_mappings.id"), nullable=False)
    verification_model = Column(String(256), nullable=False)
    prompt_version = Column(String(128), nullable=False)
    result = Column(String(50), nullable=False)
    explanation = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    control_mapping = relationship("ControlMapping", back_populates="verification_records")


class ReviewQueueItem(Base):
    __tablename__ = "review_queue_items"

    id = Column(Integer, primary_key=True, index=True)
    control_mapping_id = Column(Integer, ForeignKey("control_mappings.id"), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    reviewer_id = Column(String(128), nullable=True)
    review_reason_code = Column(String(64), nullable=False)
    comments = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    control_mapping = relationship("ControlMapping", back_populates="review_queue_items")


class ComplianceReport(Base):
    __tablename__ = "compliance_reports"

    id = Column(Integer, primary_key=True, index=True)
    scan_run_id = Column(Integer, ForeignKey("scan_runs.id"), nullable=False)
    report_type = Column(String(128), nullable=False)
    generated_by = Column(String(256), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    content_path = Column(String(1024), nullable=True)
    content_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scan_run = relationship("ScanRun", back_populates="compliance_reports")


class AuditBundle(Base):
    __tablename__ = "audit_bundles"

    id = Column(Integer, primary_key=True, index=True)
    scan_run_id = Column(Integer, ForeignKey("scan_runs.id"), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    bundle_path = Column(String(1024), nullable=True)
    checksum = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scan_run = relationship("ScanRun", back_populates="audit_bundles")
