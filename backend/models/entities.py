from datetime import datetime
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from complisoc.backend.database.base import Base


class ScanRun(Base):
    __tablename__ = "scan_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_scanrun_status",
        ),
    )

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

    id = Column(Integer, primary_key=True)
    scan_run_id = Column(Integer, ForeignKey("scan_runs.id"), nullable=False, index=True)
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
    __table_args__ = (
        UniqueConstraint(
            "scanner_execution_id",
            "scanner_finding_id",
            name="uq_raw_finding",
        ),
    )

    id = Column(Integer, primary_key=True)
    scanner_execution_id = Column(Integer, ForeignKey("scanner_executions.id"), nullable=False)
    scanner_finding_id = Column(String(256), nullable=False)
    scanner_name = Column(String(128), nullable=False)
    raw_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    scanner_execution = relationship("ScannerExecution", back_populates="raw_findings")
    normalized_findings = relationship("NormalizedFinding", back_populates="raw_finding", cascade="all, delete-orphan")


class NormalizedFinding(Base):
    __tablename__ = "normalized_findings"
    __table_args__ = (
        Index("idx_nf_finding_type", "finding_type"),
        Index("idx_nf_severity", "severity"),
        Index("idx_nf_scanner", "scanner_name"),
        CheckConstraint(
            "severity IN ('critical','high','medium','low','info')",
            name="ck_nf_severity",
        ),
    )

    id = Column(Integer, primary_key=True)
    raw_finding_id = Column(Integer, ForeignKey("raw_findings.id"), nullable=False)
    scanner_name = Column(String(128), nullable=False)
    finding_type = Column(String(128), nullable=False)
    resource_type = Column(String(128), nullable=False)
    resource_identifier = Column(String(512), nullable=False)
    severity = Column(String(50), nullable=False)
    title = Column(String(512), nullable=False)
    description = Column(Text)
    metadata_json = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    raw_finding = relationship("RawFinding", back_populates="normalized_findings")
    candidate_controls = relationship("CandidateControl", back_populates="normalized_finding", cascade="all, delete-orphan")
    control_mappings = relationship("ControlMapping", back_populates="normalized_finding", cascade="all, delete-orphan")


class ControlCatalog(Base):
    __tablename__ = "control_catalog"
    __table_args__ = (
        UniqueConstraint("framework_name", "control_id", name="uq_framework_control"),
    )

    id = Column(Integer, primary_key=True)
    framework_name = Column(String(128), nullable=False)
    framework_version = Column(String(64), nullable=False)
    control_id = Column(String(128), nullable=False)
    control_family = Column(String(256), nullable=False)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=False)
    objective = Column(Text)
    evidence_examples = Column(JSON)
    scanner_signals = Column(JSON)
    keywords = Column(JSON)
    source_url = Column(String(1024), nullable=False)
    active_status = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    candidate_controls = relationship("CandidateControl", back_populates="control_catalog")
    control_mappings = relationship("ControlMapping", back_populates="control_catalog")


class CandidateControl(Base):
    __tablename__ = "candidate_controls"
    __table_args__ = (
        UniqueConstraint(
            "normalized_finding_id",
            "control_catalog_id",
            name="uq_candidate_control",
        ),
        Index("idx_candidate_match_score", "match_score"),
    )

    id = Column(Integer, primary_key=True)
    normalized_finding_id = Column(Integer, ForeignKey("normalized_findings.id"), nullable=False)
    control_catalog_id = Column(Integer, ForeignKey("control_catalog.id"), nullable=False)
    source = Column(String(128))
    match_score = Column(Float)
    rank = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    normalized_finding = relationship("NormalizedFinding", back_populates="candidate_controls")
    control_catalog = relationship("ControlCatalog", back_populates="candidate_controls")
    control_mappings = relationship("ControlMapping", back_populates="candidate_control")


class ControlMapping(Base):
    __tablename__ = "control_mappings"
    __table_args__ = (
        CheckConstraint(
            "mapping_status IN ('generated','validated','verified','published','manual_review','rejected')",
            name="ck_mapping_status",
        ),
        CheckConstraint(
            "verification_status IS NULL OR verification_status IN ('pending','agree','disagree','failed')",
            name="ck_verification_status",
        ),
        Index("idx_mapping_status", "mapping_status"),
        Index("idx_final_confidence", "final_confidence"),
    )

    id = Column(Integer, primary_key=True)
    normalized_finding_id = Column(Integer, ForeignKey("normalized_findings.id"), nullable=False)
    candidate_control_id = Column(Integer, ForeignKey("candidate_controls.id"), nullable=False)
    control_catalog_id = Column(Integer, ForeignKey("control_catalog.id"), nullable=False)
    rank = Column(Integer, nullable=False, default=1)
    mapping_model = Column(String(256), nullable=False)
    prompt_version = Column(String(128), nullable=False)
    rationale = Column(Text)
    gemini_confidence = Column(Float)
    verification_status = Column(String(50))
    final_confidence = Column(Float)
    mapping_status = Column(String(50), nullable=False, default="generated")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    normalized_finding = relationship("NormalizedFinding", back_populates="control_mappings")
    candidate_control = relationship("CandidateControl", back_populates="control_mappings")
    control_catalog = relationship("ControlCatalog", back_populates="control_mappings")
    verification_records = relationship("VerificationRecord", back_populates="control_mapping", cascade="all, delete-orphan")
    review_queue_items = relationship("ReviewQueueItem", back_populates="control_mapping", cascade="all, delete-orphan")


class VerificationRecord(Base):
    __tablename__ = "verification_records"
    __table_args__ = (
        CheckConstraint(
            "result IN ('agree','disagree')",
            name="ck_verification_result",
        ),
    )

    id = Column(Integer, primary_key=True)
    control_mapping_id = Column(Integer, ForeignKey("control_mappings.id"), nullable=False)
    verification_model = Column(String(256), nullable=False)
    prompt_version = Column(String(128), nullable=False)
    result = Column(String(50), nullable=False)
    explanation = Column(Text)
    agreement_value = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    control_mapping = relationship("ControlMapping", back_populates="verification_records")


class ReviewQueueItem(Base):
    __tablename__ = "review_queue_items"
    __table_args__ = (
        Index("idx_review_status", "status"),
    )

    id = Column(Integer, primary_key=True)
    control_mapping_id = Column(Integer, ForeignKey("control_mappings.id"), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    reviewer_id = Column(String(128))
    review_reason_code = Column(String(64), nullable=False)
    comments = Column(Text)
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    control_mapping = relationship("ControlMapping", back_populates="review_queue_items")


class ComplianceReport(Base):
    __tablename__ = "compliance_reports"

    id = Column(Integer, primary_key=True)
    scan_run_id = Column(Integer, ForeignKey("scan_runs.id"), nullable=False)
    report_type = Column(String(128), nullable=False)
    generated_by = Column(String(256), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    content_path = Column(String(1024))
    content_hash = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scan_run = relationship("ScanRun", back_populates="compliance_reports")


class AuditBundle(Base):
    __tablename__ = "audit_bundles"

    id = Column(Integer, primary_key=True)
    scan_run_id = Column(Integer, ForeignKey("scan_runs.id"), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    bundle_path = Column(String(1024))
    checksum = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scan_run = relationship("ScanRun", back_populates="audit_bundles")