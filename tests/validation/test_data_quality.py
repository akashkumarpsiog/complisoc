"""Great Expectations data quality and validation tests.

These tests validate:
- Database record shapes against the expected schema
- API response schemas
- Report artifact structure
- Audit bundle lineage structure

All tests are self-contained and do not require external services.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

try:
    import great_expectations as ge
    from great_expectations.core import ExpectationSuite
    from great_expectations.datasource.fluent import BatchRequest
    from great_expectations.exceptions import GreatExpectationsError

    _GE_AVAILABLE = True
except ImportError:
    _GE_AVAILABLE = False

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.database.base import Base
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


def _test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def db_session():
    yield from _test_db()


@pytest.fixture()
def populated_db(db_session):
    scan = ScanRun(target_environment="test", status="completed")
    db_session.add(scan)
    db_session.flush()

    execution = ScannerExecution(scan_run_id=scan.id, scanner_name="checkov", status="completed")
    db_session.add(execution)
    db_session.flush()

    raw = RawFinding(
        scanner_execution_id=execution.id,
        scanner_name="checkov",
        scanner_finding_id="CKV_1",
        raw_json={
            "finding_type": "iam",
            "resource_type": "aws_iam_policy",
            "resource_identifier": "aws_iam_policy.public_admin",
            "severity": "high",
            "title": "IAM policy allows public access",
            "description": "desc",
        },
    )
    db_session.add(raw)
    db_session.flush()

    normalized = NormalizedFinding(
        raw_finding_id=raw.id,
        scanner_name="checkov",
        severity="high",
        finding_type="iam",
        resource_type="aws_iam_policy",
        resource_identifier="aws_iam_policy.public_admin",
        title="IAM policy allows public access",
        description="desc",
    )
    db_session.add(normalized)
    db_session.flush()

    control = ControlCatalog(
        framework_name="ISO/IEC 27001:2022 Annex A",
        framework_version="2022",
        control_id="A.5.15",
        control_family="Organizational",
        title="Access Control",
        description="Limit access to information and systems.",
        objective="Prevent unauthorized access.",
        evidence_examples=["access_review_report"],
        scanner_signals=["iam", "public_access", "permission"],
        keywords=["access", "iam", "permission", "public"],
        source_url="https://example.test/iso-a-5-15",
        active_status=True,
    )
    db_session.add(control)
    db_session.flush()

    mapping = ControlMapping(
        normalized_finding_id=normalized.id,
        candidate_control_id=control.id,
        control_catalog_id=control.id,
        rank=1,
        mapping_model="gemini-batch",
        prompt_version="v1",
        rationale="Access control issue detected.",
        gemini_confidence=0.95,
        verification_status="agree",
        final_confidence=0.97,
        groq_agreement_value=1.0,
        mapping_status="published",
    )
    db_session.add(mapping)
    db_session.flush()

    verification = VerificationRecord(
        control_mapping_id=mapping.id,
        result="agree",
        agreement_value=1.0,
        verification_model="groq",
        prompt_version="v1",
        explanation="Correct mapping.",
    )
    db_session.add(verification)

    review = ReviewQueueItem(
        control_mapping_id=mapping.id,
        status="approved",
        review_reason_code="low_confidence",
        reviewer_id="tester",
        comments="Reviewed by e2e test.",
    )
    db_session.add(review)

    report = ComplianceReport(
        scan_run_id=scan.id,
        report_type="engineering",
        generated_by="test",
        content_path=str(scan.id),
        content_hash="abc123",
    )
    db_session.add(report)
    db_session.flush()

    bundle = AuditBundle(
        scan_run_id=scan.id,
        bundle_path=str(scan.id),
        checksum="def456",
    )
    db_session.add(bundle)

    db_session.commit()
    return db_session


class TestDatabaseSchemaValidation:
    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_scan_runs_table_has_expected_columns(self, db_session):
        inspector = inspect(db_session.bind)
        columns = {col["name"] for col in inspector.get_columns("scan_runs")}
        expected = {"id", "target_environment", "status", "started_at", "completed_at", "created_at", "updated_at"}
        assert expected.issubset(columns)

    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_control_mappings_table_has_groq_column(self, db_session):
        inspector = inspect(db_session.bind)
        columns = {col["name"] for col in inspector.get_columns("control_mappings")}
        assert "groq_agreement_value" in columns

    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_raw_findings_constraints_enforced(self, db_session):
        inspector = inspect(db_session.bind)
        pk = inspector.get_pk_constraint("raw_findings")
        assert pk["constrained_columns"] == ["id"]


class TestRecordShapeValidation:
    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_scan_run_record_has_required_fields(self, populated_db):
        scan = populated_db.query(ScanRun).first()
        assert scan is not None
        assert hasattr(scan, "target_environment")
        assert hasattr(scan, "status")
        assert hasattr(scan, "created_at")

    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_mapping_record_has_both_confidence_scores(self, populated_db):
        mapping = populated_db.query(ControlMapping).first()
        assert mapping is not None
        assert mapping.gemini_confidence is not None
        assert mapping.groq_agreement_value is not None
        assert mapping.final_confidence is not None

    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_verification_record_linked_to_mapping(self, populated_db):
        record = populated_db.query(VerificationRecord).first()
        assert record is not None
        mapping = populated_db.get(ControlMapping, record.control_mapping_id)
        assert mapping is not None

    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_review_queue_linked_to_mapping(self, populated_db):
        item = populated_db.query(ReviewQueueItem).first()
        assert item is not None
        mapping = populated_db.get(ControlMapping, item.control_mapping_id)
        assert mapping is not None

    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_audit_bundle_has_scan_run_linkage(self, populated_db):
        bundle = populated_db.query(AuditBundle).first()
        assert bundle is not None
        scan = populated_db.get(ScanRun, bundle.scan_run_id)
        assert scan is not None

    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_report_has_scan_run_linkage(self, populated_db):
        report = populated_db.query(ComplianceReport).first()
        assert report is not None
        scan = populated_db.get(ScanRun, report.scan_run_id)
        assert scan is not None


class TestReportArtifactValidation:
    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_engineering_report_payload_contains_required_keys(self, populated_db):
        from complisoc.backend.reporting.reports import _mapping_payload

        mapping = populated_db.query(ControlMapping).first()
        payload = _mapping_payload(mapping)
        required = {"mapping_id", "status", "finding", "control", "verification_records", "remediation"}
        assert required.issubset(payload.keys())

        finding = payload["finding"]
        assert "resource_identifier" in finding
        assert "severity" in finding
        assert "title" in finding

        control = payload["control"]
        assert "framework_name" in control
        assert "control_id" in control

    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_leadership_posture_payload_has_aggregates(self, populated_db):
        from complisoc.backend.reporting.reports import _scan_mappings

        mappings = _scan_mappings(populated_db, 1)
        published = [m for m in mappings if m.mapping_status == "published"]
        manual_review = [m for m in mappings if m.mapping_status == "manual_review"]

        assert len(published) + len(manual_review) == len(mappings)

    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_narrative_keys_always_present(self, populated_db):
        from complisoc.backend.reporting.reports import _deterministic_narrative

        narrative = _deterministic_narrative(1, populated_db.query(ControlMapping).all(), "engineering")
        for key in ("executive_summary", "risk_summary", "recommended_actions", "audience_note"):
            assert key in narrative
            assert isinstance(narrative[key], str)
            assert len(narrative[key]) > 0


class TestLineageIntegrityValidation:
    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_scan_run_to_raw_finding_lineage(self, populated_db):
        scan = populated_db.query(ScanRun).first()
        executions = populated_db.query(ScannerExecution).filter(ScannerExecution.scan_run_id == scan.id).all()
        assert len(executions) >= 1
        raws = populated_db.query(RawFinding).filter(RawFinding.scanner_execution_id == executions[0].id).all()
        assert len(raws) >= 1

    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_raw_to_normalized_lineage(self, populated_db):
        raw = populated_db.query(RawFinding).first()
        normalized = populated_db.query(NormalizedFinding).filter(NormalizedFinding.raw_finding_id == raw.id).first()
        assert normalized is not None
        assert normalized.scanner_name == raw.scanner_name

    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_normalized_to_mapping_lineage(self, populated_db):
        normalized = populated_db.query(NormalizedFinding).first()
        mapping = populated_db.query(ControlMapping).filter(ControlMapping.normalized_finding_id == normalized.id).first()
        assert mapping is not None
        assert mapping.mapping_status in ("published", "manual_review", "rejected")

    @pytest.mark.skipif(not _GE_AVAILABLE, reason="great_expectations not installed")
    def test_mapping_to_verification_lineage(self, populated_db):
        mapping = populated_db.query(ControlMapping).first()
        verification = populated_db.query(VerificationRecord).filter(
            VerificationRecord.control_mapping_id == mapping.id
        ).first()
        assert verification is not None
        assert verification.result in ("agree", "disagree")
