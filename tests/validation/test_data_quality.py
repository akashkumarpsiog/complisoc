"""Real Great Expectations (GE 1.18.x) data quality tests.

These tests build a real ``EphemeralDataContext`` with an in-memory pandas
data source, register named ``ExpectationSuite`` instances, and run them
against populated SQLAlchemy sessions. This satisfies the proposal §10.2
requirement:

    Data Validation: Great Expectations

and produces a measurable, auditable GE validation result for each
schema/record shape/lineage check.

Run via pytest:

    pytest tests/validation/test_data_quality.py -v
"""
from __future__ import annotations

from typing import Any, Iterator

import pandas as pd
import pytest

try:
    import great_expectations as ge  # noqa: F401
    from great_expectations import get_context
    from great_expectations.core.expectation_suite import ExpectationSuite
    from great_expectations import expectations as gxe
    _GE_AVAILABLE = True
except ImportError:
    _GE_AVAILABLE = False

from sqlalchemy import create_engine, inspect
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


def _require_ge():
    if not _GE_AVAILABLE:
        pytest.skip("great_expectations not installed")


@pytest.fixture()
def ge_context():
    """A real EphemeralDataContext with a pandas data source registered."""
    _require_ge()
    ctx = get_context(mode="ephemeral")
    return ctx


def _make_batch(ctx, df: pd.DataFrame, asset_name: str = "df_asset"):
    src = ctx.data_sources.add_pandas(name=asset_name)
    asset = src.add_dataframe_asset(name="df_asset")
    bd = asset.add_batch_definition_whole_dataframe(name=f"bd_{asset_name}")
    return bd.get_batch(batch_parameters={"dataframe": df})


def _validate_suite(suite: ExpectationSuite, batch) -> dict[str, Any]:
    """Run a suite against a batch and return a compact diagnostic dict."""
    result = batch.validate(suite)
    return {
        "success": result.success,
        "stats": dict(result.statistics) if result.statistics else {},
        "unsuccessful": [
            r.expectation_config.type
            for r in result.results
            if not r.success
        ],
    }


@pytest.fixture()
def db_session() -> Iterator:
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
        checksum="a" * 64,
    )
    db_session.add(bundle)

    db_session.commit()
    return db_session


def _session_to_df(db_session, model) -> pd.DataFrame:
    rows = db_session.query(model).all()
    cols = [c.name for c in model.__table__.columns]
    return pd.DataFrame([{c: getattr(r, c) for c in cols} for r in rows])


class TestDatabaseSchemaValidation:
    """GE expectation suites validating the SQLite schema against GE.

    The "schema" tests are run by materializing one row per required
    column into a one-row DataFrame and asserting via
    ``ExpectTableColumnsToMatchSet`` (which is the GE-native way to
    validate a table's column inventory) that the expected set of
    columns is present. ``ExpectColumnToExist`` is also used on a
    one-row batch for the same set of columns to provide an additional,
    independent GE signal.
    """

    def test_scan_runs_schema_suite_passes(self, ge_context, db_session):
        _require_ge()
        inspector = inspect(db_session.bind)
        actual_columns = sorted(col["name"] for col in inspector.get_columns("scan_runs"))
        required = [
            "id", "target_environment", "status",
            "started_at", "completed_at", "created_at",
        ]

        scan = ScanRun(target_environment="schema_probe", status="completed")
        db_session.add(scan)
        db_session.commit()
        df = _session_to_df(db_session, ScanRun)
        batch = _make_batch(ge_context, df, asset_name="scan_runs_schema")

        suite = ExpectationSuite("scan_runs_schema")
        suite.add_expectation(
            gxe.ExpectTableColumnsToMatchSet(column_set=actual_columns, exact_match=True)
        )
        for col in required:
            suite.add_expectation(gxe.ExpectColumnToExist(column=col))
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="target_environment"))
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="status"))

        report = _validate_suite(suite, batch)
        assert report["success"], f"scan_runs GE validation failed: {report}"

    def test_control_mappings_has_groq_agreement_value(self, ge_context, db_session):
        _require_ge()
        inspector = inspect(db_session.bind)
        actual_columns = sorted(col["name"] for col in inspector.get_columns("control_mappings"))
        assert "groq_agreement_value" in actual_columns, "schema missing groq_agreement_value"

        scan = ScanRun(target_environment="schema_probe", status="completed")
        db_session.add(scan)
        db_session.flush()
        cat = ControlCatalog(
            framework_name="X", framework_version="v", control_id="X.1",
            control_family="X", title="X", description="X", objective="X",
            evidence_examples=[], scanner_signals=[], keywords=[],
            source_url="https://x", active_status=True,
        )
        db_session.add(cat)
        db_session.flush()
        m = ControlMapping(
            normalized_finding_id=1, candidate_control_id=cat.id,
            control_catalog_id=cat.id, rank=1, mapping_model="m",
            prompt_version="v", rationale="r", gemini_confidence=0.5,
            verification_status="agree", final_confidence=0.5,
            groq_agreement_value=0.5, mapping_status="manual_review",
        )
        db_session.add(m)
        db_session.commit()

        df = _session_to_df(db_session, ControlMapping)
        batch = _make_batch(ge_context, df, asset_name="control_mappings_schema")

        suite = ExpectationSuite("control_mappings_schema")
        suite.add_expectation(
            gxe.ExpectTableColumnsToMatchSet(column_set=actual_columns, exact_match=True)
        )
        suite.add_expectation(gxe.ExpectColumnToExist(column="groq_agreement_value"))
        suite.add_expectation(gxe.ExpectColumnToExist(column="gemini_confidence"))
        suite.add_expectation(gxe.ExpectColumnToExist(column="final_confidence"))

        report = _validate_suite(suite, batch)
        assert report["success"], f"control_mappings GE validation failed: {report}"

    def test_raw_findings_has_primary_key(self, ge_context, db_session):
        _require_ge()
        inspector = inspect(db_session.bind)
        pk = inspector.get_pk_constraint("raw_findings")
        assert pk["constrained_columns"] == ["id"]
        actual_columns = sorted(col["name"] for col in inspector.get_columns("raw_findings"))

        # Add one row so the pandas batch has columns to validate against.
        scan = ScanRun(target_environment="schema_probe", status="completed")
        db_session.add(scan)
        db_session.flush()
        execution = ScannerExecution(scan_run_id=scan.id, scanner_name="checkov", status="completed")
        db_session.add(execution)
        db_session.flush()
        raw = RawFinding(
            scanner_execution_id=execution.id,
            scanner_name="checkov",
            scanner_finding_id="CKV_SCHEMA_PROBE",
            raw_json={"probe": True},
        )
        db_session.add(raw)
        db_session.commit()

        df = _session_to_df(db_session, RawFinding)
        assert not df.empty, "raw_findings probe row missing"
        assert set(actual_columns) == set(df.columns), (
            f"schema vs dataframe mismatch: {set(actual_columns) ^ set(df.columns)}"
        )

        suite = ExpectationSuite("raw_findings_schema")
        suite.add_expectation(
            gxe.ExpectTableColumnsToMatchSet(column_set=actual_columns, exact_match=True)
        )
        suite.add_expectation(gxe.ExpectColumnToExist(column="id"))
        suite.add_expectation(gxe.ExpectColumnToExist(column="scanner_finding_id"))
        suite.add_expectation(gxe.ExpectColumnToExist(column="scanner_execution_id"))

        batch = _make_batch(ge_context, df, asset_name="raw_findings_schema")
        report = _validate_suite(suite, batch)
        assert report["success"], f"raw_findings schema-suite failed: {report}"


class TestRecordShapeValidation:
    """GE expectation suites validating the populated record shapes."""

    def test_scan_run_record_required_fields(self, ge_context, populated_db):
        _require_ge()
        df = _session_to_df(populated_db, ScanRun)
        batch = _make_batch(ge_context, df, asset_name="scan_run_record")

        suite = ExpectationSuite("scan_run_record")
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="id"))
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="target_environment"))
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="status"))
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="created_at"))
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeInSet(
                column="status",
                value_set=["completed", "running", "failed", "pending"],
            )
        )
        suite.add_expectation(gxe.ExpectTableRowCountToEqual(value=1))
        report = _validate_suite(suite, batch)
        assert report["success"], f"scan_run record GE failed: {report}"

    def test_mapping_record_has_both_confidence_scores(self, ge_context, populated_db):
        _require_ge()
        df = _session_to_df(populated_db, ControlMapping)
        batch = _make_batch(ge_context, df, asset_name="control_mapping_record")

        suite = ExpectationSuite("control_mapping_record")
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="gemini_confidence"))
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="groq_agreement_value"))
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="final_confidence"))
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(
                column="gemini_confidence", min_value=0.0, max_value=1.0,
            )
        )
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(
                column="groq_agreement_value", min_value=0.0, max_value=1.0,
            )
        )
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(
                column="final_confidence", min_value=0.0, max_value=1.0,
            )
        )
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeInSet(
                column="mapping_status",
                value_set=["published", "manual_review", "rejected"],
            )
        )
        report = _validate_suite(suite, batch)
        assert report["success"], f"control_mapping record GE failed: {report}"

    def test_verification_record_linked_to_mapping(self, ge_context, populated_db):
        _require_ge()
        df = _session_to_df(populated_db, VerificationRecord)
        batch = _make_batch(ge_context, df, asset_name="verification_record")

        suite = ExpectationSuite("verification_record")
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="control_mapping_id"))
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeInSet(column="result", value_set=["agree", "disagree"])
        )
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(
                column="agreement_value", min_value=0.0, max_value=1.0,
            )
        )
        report = _validate_suite(suite, batch)
        assert report["success"], f"verification record GE failed: {report}"

    def test_review_queue_linked_to_mapping(self, ge_context, populated_db):
        _require_ge()
        df = _session_to_df(populated_db, ReviewQueueItem)
        batch = _make_batch(ge_context, df, asset_name="review_queue")

        suite = ExpectationSuite("review_queue")
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="control_mapping_id"))
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeInSet(
                column="status", value_set=["pending", "approved", "rejected"]
            )
        )
        report = _validate_suite(suite, batch)
        assert report["success"], f"review queue GE failed: {report}"

    def test_audit_bundle_has_scan_run_linkage(self, ge_context, populated_db):
        _require_ge()
        df = _session_to_df(populated_db, AuditBundle)
        batch = _make_batch(ge_context, df, asset_name="audit_bundle")

        suite = ExpectationSuite("audit_bundle")
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="scan_run_id"))
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="checksum"))
        suite.add_expectation(
            gxe.ExpectColumnValuesToMatchRegex(column="checksum", regex=r"^[a-f0-9]{8,64}$")
        )
        report = _validate_suite(suite, batch)
        assert report["success"], f"audit_bundle GE failed: {report}"

    def test_report_has_scan_run_linkage(self, ge_context, populated_db):
        _require_ge()
        df = _session_to_df(populated_db, ComplianceReport)
        batch = _make_batch(ge_context, df, asset_name="compliance_report")

        suite = ExpectationSuite("compliance_report")
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="scan_run_id"))
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeInSet(
                column="report_type", value_set=["engineering", "leadership", "audit"]
            )
        )
        report = _validate_suite(suite, batch)
        assert report["success"], f"compliance_report GE failed: {report}"


class TestReportArtifactValidation:
    """GE expectation suites validating the report payload shapes."""

    def test_engineering_report_payload_contains_required_keys(self, ge_context, populated_db):
        _require_ge()
        from complisoc.backend.reporting.reports import _mapping_payload

        mapping = populated_db.query(ControlMapping).first()
        payload = _mapping_payload(mapping)
        required = {
            "mapping_id", "status", "finding", "control",
            "verification_records", "remediation",
        }

        keys_df = pd.DataFrame({"key": list(payload.keys())})
        batch = _make_batch(ge_context, keys_df, asset_name="engineering_keys")

        suite = ExpectationSuite("engineering_keys")
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="key"))
        suite.add_expectation(
            gxe.ExpectTableRowCountToBeBetween(min_value=len(required), max_value=20)
        )
        report = _validate_suite(suite, batch)
        assert report["success"], f"engineering keys GE failed: {report}"

        missing = required - set(payload.keys())
        assert not missing, f"engineering report missing keys: {missing}"
        assert "resource_identifier" in payload["finding"]
        assert "severity" in payload["finding"]
        assert "title" in payload["finding"]
        assert "framework_name" in payload["control"]
        assert "control_id" in payload["control"]

    def test_leadership_posture_payload_has_aggregates(self, ge_context, populated_db):
        _require_ge()
        from complisoc.backend.reporting.reports import _scan_mappings

        mappings = _scan_mappings(populated_db, 1)
        df = pd.DataFrame([
            {"status": m.mapping_status, "confidence": m.final_confidence or 0.0}
            for m in mappings
        ])
        batch = _make_batch(ge_context, df, asset_name="leadership_aggregates")

        suite = ExpectationSuite("leadership_aggregates")
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeInSet(
                column="status",
                value_set=["published", "manual_review", "rejected"],
            )
        )
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(
                column="confidence", min_value=0.0, max_value=1.0,
            )
        )
        report = _validate_suite(suite, batch)
        assert report["success"], f"leadership aggregates GE failed: {report}"

        published = [m for m in mappings if m.mapping_status == "published"]
        manual_review = [m for m in mappings if m.mapping_status == "manual_review"]
        assert len(published) + len(manual_review) == len(mappings)

    def test_narrative_keys_always_present(self, populated_db):
        _require_ge()
        from complisoc.backend.reporting.reports import _deterministic_narrative

        narrative = _deterministic_narrative(
            1, populated_db.query(ControlMapping).all(), "engineering"
        )
        for key in ("executive_summary", "risk_summary",
                    "recommended_actions", "audience_note"):
            assert key in narrative, f"missing narrative key: {key}"
            assert isinstance(narrative[key], str)
            assert len(narrative[key]) > 0, f"empty narrative value: {key}"


class TestLineageIntegrityValidation:
    """GE expectation suites validating the lineage graph."""

    def test_scan_run_to_raw_finding_lineage(self, ge_context, populated_db):
        _require_ge()
        df = _session_to_df(populated_db, ScannerExecution)
        batch = _make_batch(ge_context, df, asset_name="scanner_execution")

        suite = ExpectationSuite("scanner_execution")
        suite.add_expectation(gxe.ExpectTableRowCountToEqual(value=1))
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="scan_run_id"))
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeInSet(
                column="scanner_name",
                value_set=["checkov", "trivy", "sonarqube", "defender"],
            )
        )
        report = _validate_suite(suite, batch)
        assert report["success"], f"scanner_execution lineage GE failed: {report}"

    def test_raw_to_normalized_lineage(self, ge_context, populated_db):
        _require_ge()
        raw_df = _session_to_df(populated_db, RawFinding)
        norm_df = _session_to_df(populated_db, NormalizedFinding)

        raw_suite = ExpectationSuite("raw_finding")
        raw_suite.add_expectation(gxe.ExpectTableRowCountToEqual(value=1))
        raw_suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="scanner_execution_id"))
        raw_suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="scanner_finding_id"))
        raw_batch = _make_batch(ge_context, raw_df, asset_name="raw_finding")
        raw_report = _validate_suite(raw_suite, raw_batch)
        assert raw_report["success"], f"raw_finding lineage GE failed: {raw_report}"

        norm_suite = ExpectationSuite("normalized_finding")
        norm_suite.add_expectation(gxe.ExpectTableRowCountToEqual(value=1))
        norm_suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="raw_finding_id"))
        norm_suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="scanner_name"))
        norm_batch = _make_batch(ge_context, norm_df, asset_name="normalized_finding")
        norm_report = _validate_suite(norm_suite, norm_batch)
        assert norm_report["success"], f"normalized_finding lineage GE failed: {norm_report}"

        assert raw_df.iloc[0]["scanner_name"] == norm_df.iloc[0]["scanner_name"]

    def test_normalized_to_mapping_lineage(self, ge_context, populated_db):
        _require_ge()
        df = _session_to_df(populated_db, ControlMapping)
        batch = _make_batch(ge_context, df, asset_name="control_mapping_lineage")

        suite = ExpectationSuite("control_mapping_lineage")
        suite.add_expectation(gxe.ExpectTableRowCountToEqual(value=1))
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="normalized_finding_id"))
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="candidate_control_id"))
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeInSet(
                column="mapping_status",
                value_set=["published", "manual_review", "rejected"],
            )
        )
        report = _validate_suite(suite, batch)
        assert report["success"], f"control_mapping lineage GE failed: {report}"

    def test_mapping_to_verification_lineage(self, ge_context, populated_db):
        _require_ge()
        df = _session_to_df(populated_db, VerificationRecord)
        batch = _make_batch(ge_context, df, asset_name="verification_lineage")

        suite = ExpectationSuite("verification_lineage")
        suite.add_expectation(gxe.ExpectTableRowCountToEqual(value=1))
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="control_mapping_id"))
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeInSet(column="result", value_set=["agree", "disagree"])
        )
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(
                column="agreement_value", min_value=0.0, max_value=1.0,
            )
        )
        report = _validate_suite(suite, batch)
        assert report["success"], f"verification lineage GE failed: {report}"
